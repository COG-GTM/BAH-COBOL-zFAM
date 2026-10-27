# S4: Replication, VSAM→PostgreSQL data migration, and parity testing

Segment: **S4** (`replication-data-testing`). Target stack (fixed by the coordinator): Java 17 + Spring Boot 3, PostgreSQL, Spring Security, `@Scheduled` workers, Maven, JUnit 5 + Testcontainers. The REST wire contract stays the same, and that includes the inter-DC `/replicate` and `/deplicate` paths.

Line numbers below point at the raw files in `Source/` and `JCL/` (CRLF files; the numbering is the same as `grep -n`).

---

## 1. Inventory

| Artifact | LOC | What it does | CICS / VSAM / RACF APIs |
|---|---|---|---|
| `Source/ZFAM101.cbl` | 1223 | **CWR (Copy-While-Replicating).** A started or terminal task that copies a whole zFAM instance to the partner DC over HTTP. `1000-INITIALIZE` (L307) takes a sysplex-wide `ENQ CICSGRS_zFAM_CWR_<tranid>` with NOSUSPEND. If the ENQ is busy, the task exits. `1200-GET-URL` (L349) reads the partner URL from the `FAxxDC` doc template. `2000-START-BROWSE` (L392) issues STARTBR on `FAxxKEY` at LOW-VALUES, GTEQ. `3200-READ-KEY` (L474) READNEXTs to ENDFILE. Per key: an ECR goes to `4200-COPY-ECR` (L827), which POSTs the key as the body with `zFAM-ECR: Yes`. A non-LOB record goes to `3300/3400/3500` (L525–611), which reads FILE segment 1 and then 2..`FF-SEGMENTS` into a GETMAIN buffer of `segments*32000`. `4000-COPY-RECORD` (L778) then POSTs `/replicate/...<key>?ret-days=nnnnn` or `?ret-years=` (`3999-SET-TTL`, L759). A LOB goes to `3700-LOB` (L663): segment 1 is POSTed with `zFAM-LOB: yes`, and segments 2..`FK-SEGMENTS` are PUT with `zFAM-Append: yes` (L793–826). `9999-CREATE-URI` (L1206) builds `<urimap path>/<key>`. Partner HTTP status is **never checked**. | ENQ, INQUIRE URIMAP, DOCUMENT CREATE/RETRIEVE, WEB PARSE/OPEN/CONVERSE/WRITE HTTPHEADER/CLOSE, STARTBR/READNEXT, READ, GETMAIN/FREEMAIN, ASSIGN STARTCODE, WRITEQ TD (CSSL), ASKTIME/FORMATTIME, ENTER TRACENUM |
| `Source/ZFAM102.cbl` | 909 | **Query Mode replication.** LINKed with a 279-byte COMMAREA (L257: `CA-TYPE` CREATE/UPDATE/DELETE, `CA-NAME` = PK field name, `CA-KEY-LENGTH`, `CA-KEY`). For CREATE/UPDATE it re-reads KEY+FILE (`3200`–`3500`, L394–562), reassembles segments, and POSTs or PUTs the whole document to `/replicate/.../<key>` (`4100`/`4200`, L592–621; `8100`, L661). For DELETE it sends `DELETE /replicate/.../?zql,DELETE,(WHERE(<name>=<key>))` (`9998-CREATE-ZQL`, L860). **No TTL is forwarded**: `THE-RET '?ttl='` is defined but never used. Status is ignored. | INQUIRE URIMAP, DOCUMENT, WEB *, READ, GETMAIN/FREEMAIN, WRITEQ TD |
| `ZFAM010.asm` "zFAM Replication" | ~60 (L1413–1483; call at L823) | After a zQL INSERT, `ZR_0010` reads `FAxxDC`. It LINKs ZFAM102 (CREATE) **only when `DC_ENV = 'AS'`**: `CLC DC_ENV,ZP_AS / BC B'0111',ZR_0099`. This happens **before** `WS_0010` WEB SEND (L823–824). | DOCUMENT, LINK |
| `ZFAM030.asm` "zFAM Replication" | ~60 (L1056–1126; call at L752) | The same logic for zQL UPDATE (ZP_UPD). | DOCUMENT, LINK |
| `ZFAM040.asm` "zFAM Replication" | ~60 (L971–1040; call at L780; ZP_NAME at L393) | The same logic for zQL DELETE (ZP_DEL). The DC template tranid is forced to `FA` + EIBTRNID+2. | DOCUMENT, LINK |
| `ZFAM002.cbl` replication logic | ~400 of 4343 | Basic Mode outbound replication. `4300-SEND-RESPONSE` (L2299–2340, POST), `5300` (L2848–2882, DELETE), `6400` (L3379–3412, PUT), `7400` (L3752–3785, PUT append): **AA → replicate before WEB SEND; AS → replicate after WEB SEND**, and only when `WEB-PATH(1:10) = '/datastore'` (loop guard). The replicate paragraphs are `4500` (L2445), `5400` (L2889), `6600` (L3466), and `7600` (L3834, adds the `zFAM-Append` and `zFAM-LOB` headers). `8000-GET-URL` (L3892–3935) falls back to `A1` when the template is missing or ≤10 bytes. `8200-WEB-CONVERSE` (L3960) rewrites `/datastore` to `/replicate` and forwards the original query string. `8210` (L4040) is the ECR variant. **Inbound deplication:** `5500-DEPLICATE-DELETE` / `5600-CHECK-RET` / `5700-SEND-ABS` (L2917–2983). The partner keeps its record if it hasn't expired yet and replies **201** with its `FF-ABS` in the body and status text. | DOCUMENT, WEB *, READ, ASKTIME |
| Related, owned elsewhere | n/a | `ZFAM001.asm` L388–390, L588, L2597: a `/replicate` prefix sets `W_PREFIX=X'FF'`, which **bypasses all security** (S3). `ZFAM000.cbl` `5000-DEPLICATE` (L563) and `7200` (L793): the TTL task sends `DELETE /deplicate/...`. On a 201 + numeric ABS it updates the local ABS (`5100`). Otherwise it deletes, including when the partner is unreachable (S3). `ZFAM003.cbl` `2000-REPLICATE` (L340) replicates range DELETEs (S1). `CSDFA##.rdo` L73–96: URIMAPs `/datastore` (FA##), `/deplicate` (FD##), `/replicate` (FR##), `/zComplete` and `/zRecovery` (FZ##→**ZFAM100, which is not in the repo**). `CSDZFAMR.rdo`: TCPIPSERVICE `ZFAMREPL`, `AUTHENTICATE(NO) SSL(NO)`. `FA##DC.txt`: `type: AS` + `http://host:@rep_port@`. | n/a |
| `Source/ZFAMKEY.idcams` | 20 | `FAxxKEY` KSDS, `KEYS(255 0)`, `RECORDSIZE(512 512)`, CI 32K, `LOG(UNDO)`, SHR(2 3). Layout `ZFAMFKC.cpy`: `FK-KEY X(255)` (LOW-VALUE padded), `FK-ECR X`, `FK-FF-KEY` (`IDN X(6)` + `NC X(2)`), `FK-OBJECT X(4)`, `FK-DDNAME X(4)`, `FK-UID X(32)`, `FK-ABS S9(15) COMP-3`, `FK-LOCK-TIME 9(1)`, `FK-LOB X`, `FK-SEGMENTS 9(4) COMP`, `FK-RETENTION S9(7) COMP-3`, `FK-RETENTION-TYPE X` (D/Y), `FILLER X(191)`. | VSAM KSDS (RLS) |
| `Source/ZFAMFILE.idcams` | 20 | `FAxxFILE` KSDS, `KEYS(16 0)`, `RECORDSIZE(100 32700)`, CI 32K. Layout `ZFAMFFC.cpy`: key = `IDN X(6) NC X(2) SEGMENT 9(4) COMP SUFFIX 9(4) COMP ZEROES 9(8) COMP`, then `FF-ABS S9(15) COMP-3`, `FF-RETENTION S9(7) COMP-3`, `FF-SEGMENTS 9(4) COMP`, `FF-RETENTION-TYPE X`, `FF-EXTRA X(14)`, `FF-FK-KEY X(255)` (back-pointer), `FF-MEDIA X(56)`, `FF-DATA X(32000)`. The data length is `record length − FF-PREFIX(356)`. `FK-DDNAME` can redirect a key to a different FILE dataset. | VSAM KSDS |
| `Source/ZFAMCI.idcams` | 20 | `FAxxCIyy` KSDS (yy = FAxxFD `ID=` ≥ 02), `KEYS(64 0)`, `RECORDSIZE(68 68)`. Layout `ZFAMCIC.cpy`: `CI-FIELD X(56)` + `CI-ID X(6)` + `CI-NC X(2)` + `CI-DS X(4)`='FILE'. | VSAM KSDS |
| `Source/FAEXPIRE.idcams` | 20 | `FAEXPIRE` KSDS, `KEYS(4 0)`, `RECORDSIZE(80 2048)`. One control record per instance tranid (`ZFAM000` `FX-RECORD`: `FX-ABSTIME COMP-3`, `FX-INTERVAL`/`FX-RESTART S9(7) COMP-3` = 86400, date/time/applid/taskid). | VSAM KSDS |
| `JCL/DEFFA##.jcl` | 88 | REXXREPL-substitutes `@id@`, `@cc@/@reg@/@org@/@appname@`, cylinders. Runs DFHCSDUP on `CSDFA##`, then IDCAMS ZFAMFILE and ZFAMKEY. | IEBGENER, IKJEFT1B, DFHCSDUP, IDCAMS |
| `JCL/DEFCI.jcl` | 63 | Defines one CI cluster (`@ci_nbr@` starts at 02 and matches `ID=` in FAxxFD) and `CSDZFAMC`. | same |
| `JCL/DEFEXPR.jcl` | 58 | Defines FAEXPIRE and `CSDZFAMX` (`RECOVERY(NONE)`). | same |

S4 source in scope comes to about 2.6k LOC (101/102 + replication blocks + IDCAMS/JCL). The parity strategy in §5 covers the whole 27.4k-line estate (`Source/*.cbl` + `*.asm`).

## 2. Legacy replication semantics that must be preserved

1. **Topology configuration.** The per-instance `FAxxDC` template sets `type` ∈ {`A1`, `AA`, `AS`} plus the partner URL. A missing or short template means `A1` (ZFAM002 L3932).
2. **Basic Mode ordering.** AA replicates synchronously *before* the client response. AS replicates *after* the response, in the same task. In neither case is the partner status checked (`NOHANDLE`; `WEB-STATUS-CODE` unused), so the client gets 200 even if the partner fails. The guarantee is best-effort ordering, not durability.
3. **Query Mode inverts this.** Only `AS` triggers ZFAM102, synchronously before the response. **`AA` does not replicate Query Mode writes at all.** This is either a bug or deliberate; see Q1. ZFAM102 sends no TTL, so replicas get the partner's default retention.
4. **Loop prevention by path prefix.** Outbound requests rewrite `/datastore`→`/replicate`. Receivers replicate only when the prefix is `/datastore`. ZFAM003 nulls `DC-TYPE` on a replicate.
5. **Inbound `/replicate` has no authentication.** It bypasses FAxxSD/RACF (ZFAM001 `BM_0010`/`QS_0010`) on a separate port (`ZFAMREPL`, no SSL).
6. **No conflict resolution.** Each DC applies whatever arrives, so the last write wins locally. A replicated POST to an existing key gets 409 at the partner (ignored), which means **CWR never overwrites newer partner data**. Divergence is possible and nothing reconciles it, apart from TTL deplication.
7. **Replicated metadata.** The headers `zFAM-ECR`, `zFAM-LOB`, and `zFAM-Append`, plus the original query string (`ret-days`/`ret-years`/...), are forwarded. `FF-ABS` (creation time) is **not**, so replica TTL clocks restart at receipt time.
8. **Deplication handshake.** On expiry, the local side DELETEs `/deplicate/...`. If the partner copy is younger, the partner returns `201` with its 15-digit ABSTIME and the local side adopts it. Otherwise both sides delete. Partner errors also mean a local delete.
9. **CWR behaviour.** A single instance runs sysplex-wide (ENQ). There is no checkpoint or restart: a failure restarts from LOW-VALUES. There is no throttling. Orphan keys (FILE record missing) are skipped and logged with `50702-MESSAGE`. If a later key references the same missing internal key, the whole copy aborts (`3290`, L500–523).
10. **Text conversion.** The payload is EBCDIC↔ASCII converted (`CLICONVERT`) only for media types starting `text`, `application/xml`, or `application/json` (ZFAM101 `8100`, L869). Everything else is binary.

## 3. Target design

### 3.1 Replication: recommend an **application-level transactional outbox + HTTP partner client**, not PostgreSQL logical replication

| Criterion | PG logical replication | App-level outbox → partner HTTP `/replicate` (**chosen**) |
|---|---|---|
| Can talk to a legacy zFAM DC during migration (mixed estate) | No | **Yes.** The same wire protocol lets legacy and Java act as each other's partner, which is the basis of the cutover plan in §4.7. |
| AA (before response) vs AS (after response) per instance | No (always async, all or nothing per publication) | Yes, per instance mode |
| Deplication 201/ABS negotiation, ECR/LOB/append semantics | Not expressible | Ported 1:1 |
| Active/active conflicts | Bidirectional (`origin=none`, PG16+) stops the apply worker on PK conflict | Same semantics as legacy (partner 409 ignored and logged), plus an optional reconciler |
| Replicates CI/derived tables blindly | Yes, so schema changes must stay in lockstep | Only logical operations are replicated; the partner rebuilds CI |

Logical or physical replication remains an option *inside* one DC for HA (PG streaming replica). That replaces VSAM RLS/sysplex HA (A1) and is an infrastructure concern, not app code.

**Packages and components** (`com.<org>.zfam.replication`):
- `ReplicationProperties`: `zfam.instances.<FAxx>.replication.mode=A1|AA|AS`, `partner-url`, `timeout`, `strict-legacy=true`. This replaces `FAxxDC` and the `DOCUMENT CREATE/RETRIEVE` + `WEB PARSE` calls.
- `ReplicationMode` enum. `ReplicationEvent` record: instance, op (POST/PUT/DELETE/APPEND/ZQL_INSERT/UPDATE/DELETE), key bytes, payload ref, media type, original query string, flags (ecr, lob, append), pk name.
- `ReplicationService` (implements the `ReplicationPort` SPI that S1/S2 depend on). `record(event)` is called by S1/S2 services inside the data transaction (writes the outbox row). `ReplicationService.deliverBeforeResponse()` is called after commit and before the response for AA; for AS, `TransactionSynchronization.afterCommit` wakes the dispatcher.
- `replication_outbox` table, written in the **same DB transaction** as the data change. Columns: `id bigserial`, `instance`, `op`, `key bytea`, `query_string`, `headers jsonb`, `media_type`, **`payload bytea`** (an immutable copy of the bytes sent: the full body for POST/PUT, only the appended segment for APPEND/LOB segments, the key bytes for ECR POSTs (legacy `8210-WEB-CONVERSE`/ZFAM101 `4200-COPY-ECR` send the key as the body), NULL for DELETE; bodies above `zfam.replication.inline-max` go to `replication_outbox_segment(outbox_id, seg_no, data)`), `status` (PENDING/SENT/FAILED), `attempts`, `last_http_status`, `created_at`, `sent_at`. Rows are self-contained, so a later update or delete of the key never changes what a pending event sends. Each instance is dispatched in `id` order, so a POST→PUT→DELETE sequence replays in order. Rows are purged once SENT.
  - **AA:** commit the local change and its outbox row first. Then, *still on the request thread and before the response is written*, send to the partner and record SENT/FAILED in a separate transaction. A rolled-back local write therefore never reaches the partner. Legacy sends before the CICS syncpoint, so an abend after replication could leave the partner ahead; the target deliberately closes that window while keeping "partner attempted before the client sees the response."
  - **AS:** commit, respond, then `OutboxDispatcher` (`@Scheduled(fixedDelay=…)`, `FOR UPDATE SKIP LOCKED`, **one in-flight row per instance**, strictly in `id` order) drains the rows. Per-instance rather than per-key serialization is needed because a ZFAM003 range DELETE covers many keys and must not be overtaken by a later write to a covered key.
  - With `strict-legacy=true`, failures are logged and not retried, which matches legacy. With `false`, rows retry with backoff (recommended after cutover).
- `PartnerClient` (Spring `RestClient`). Rewrites `/datastore`→`/replicate`. Sets `zFAM-ECR`/`zFAM-LOB`/`zFAM-Append`. Sends UTF-8 for the text media types listed in §2.10 and raw bytes for the rest. Builds the zQL DELETE query string exactly as ZFAM102 `9998-CREATE-ZQL`.
- `ReplicationInbound` contract for S3's front door: requests under `/replicate/**` and `/deplicate/**` skip user auth and FAxxSD checks (legacy parity), but **must** pass partner authentication (mTLS client cert or HMAC header, on a dedicated port matching `ZFAMREPL`). This is a deliberate security hardening; see R5.
- `DeplicationClient` (used by S3's TTL job) and `DeplicationHandler` (serves `DELETE /deplicate/**`, ports ZFAM002 L2917–2983, returns `201` + 15-digit ABS).
- `CopyWhileReplicatingJob` (ZFAM101). Triggered by `POST /admin/zfam/{instance}/cwr` (ops role). The ENQ becomes `pg_try_advisory_lock(hash('zFAM_CWR_'||instance))`, so a second start returns `409`, the equivalent of ENQBUSY. STARTBR/READNEXT becomes keyset pagination `WHERE key > :last ORDER BY key LIMIT 500`. A `cwr_checkpoint(instance, last_key, rows, started_at, updated_at)` table enables restart (an improvement; the legacy job always restarts from scratch). GETMAIN segment buffers become a streamed `InputStream`. Orphans and partner statuses are counted in Micrometer metrics instead of CSSL. CSSL `WRITEQ TD` becomes SLF4J `log.warn` with the same message text.

**Construct map:** `EXEC CICS LINK ZFAM102 COMMAREA` → `ReplicationService.replicate(ZqlEvent)`. `WEB OPEN/CONVERSE/CLOSE` → `RestClient` with a pooled HttpClient. `ENQ` → advisory lock. `GETMAIN`/`FREEMAIN` → none needed. `ASKTIME ABSTIME` → `Clock` (injectable for tests). `INQUIRE URIMAP PATH` → `zfam.instances.<id>.base-path`.

### 3.2 Data model mapping (S4 proposal; S1/S2 own the final DDL, see §6)

| VSAM | PostgreSQL | Notes |
|---|---|---|
| `FAxxKEY` | `zfam_key(instance char(4), key bytea, key_text text, ecr bool, file_id bigint, ddname char(4), object char(4), uid char(32), created_at timestamptz, created_abs bigint, lock_time smallint, lob bool, segments int, retention int, retention_type char(1), PRIMARY KEY(instance,key))` | `key` is stored as the **EBCDIC bytes with LOW-VALUE padding stripped**, so `ORDER BY key` reproduces VSAM collation for browse (`ge/gt/le/lt`, ZFAM007/008/009). `key_text` is the UTF-8 form. |
| `FAxxFILE` (+ any `FK-DDNAME` alt datasets) | `zfam_file(instance, file_id, created_at, created_abs, retention, retention_type, media_type varchar(56), size bigint)` + `zfam_file_segment(file_id, seg_no int, data bytea, PRIMARY KEY(file_id,seg_no))` | Segments are kept because a LOB can reach 2 GB, above the bytea limit of 1 GB. An alternative is `oid` large objects (Q4). `FF-IDN`+`FF-NC` (8 bytes) map to `file_id` via a mapping table kept for audit. |
| `FAxxCIyy` | `zfam_ci(instance, ci_nbr smallint, field_value bytea, file_id bigint)`, index `(instance,ci_nbr,field_value)` | **Rebuilt** from documents, not copied (§4.4). |
| `FAEXPIRE` | `zfam_expire_control(instance, last_run_at, interval_s, restart_s, applid, task)` | S3 owns this. Migrate only the last run time. |
| `ABSTIME` (COMP-3 ms since 1900-01-01) | `timestamptz` + raw `bigint` | Keep the raw value for byte-exact `201` deplication replies and lock-time logic. |

## 4. VSAM → PostgreSQL data migration plan

1. **Unload.** Run per instance `FAxx` inside a **write freeze** that stops *every* writer of the instance's VSAM datasets: POST/PUT/DELETE on `/datastore`, inbound `/replicate` and `/deplicate` (FR##/FD## URIMAPs), the TTL task (`FPLT`/ZFAM000), CWR (ZFAM101), and admin jobs. If the instance has a legacy partner DC, freeze **both** sides, because legacy outbound replication never retries and a write the partner sends while `/replicate` is disabled is lost for good. Reads stay up. A REPRO of a live RLS KSDS is not a consistent snapshot, and a fuzzy snapshot can't be reconciled with replayed appends, which are not idempotent. Use `IDCAMS REPRO INFILE(FAxxKEY) OUTFILE(SEQ)` to an `RECFM=VB` sequential file, and the same for every `FAxxFILE` DDNAME found in `FK-DDNAME`, every `FAxxCIyy`, and `FAEXPIRE`. Also export the `FAxxFD`/`FAxxSD`/`FAxxDC` templates. Transfer **binary** (FTP `BINARY` / `quote site rdw`, or Connect:Direct) and keep RDWs. Never use ASCII transfer mode. Capture the IDCAMS `RECORDS PROCESSED` counts as control totals.
2. **Parse.** The Maven module `zfam-migration` is a CLI with Spring Batch chunks. Layouts are hand-coded from `ZFAMFKC`/`ZFAMFFC`/`ZFAMCIC` (or JRecord). Codecs: `COMP` → unsigned big-endian. `COMP-3` → `BigDecimal` (sign nibble C/F = +, D = −). EBCDIC uses the CCSID agreed in Q2 (expected IBM-1047 or 037).
3. **Transform.**
   - **Keys.** Strip trailing X'00'. Keep the EBCDIC bytes in `key` and convert to UTF-8 for `key_text`. Flag any key that doesn't round-trip.
   - **Payload.** Group `FAxxFILE` rows by `IDN+NC`. Order by `FF-SEGMENT`. Check the count against `FF-SEGMENTS` (non-LOB) or `FK-SEGMENTS` (LOB). Concatenate `data[0 : reclen−356]`. Convert EBCDIC→UTF-8 **only** for the text media types listed in §2.10 and leave other payloads untouched. Query Mode documents are fixed-layout per FAxxFD. `C` fields are converted. `N` fields are zoned-decimal display, so convert digits and check for a sign overpunch. The byte offsets (`Col=`) change if UTF-8 expands multibyte characters, so S2 must decide between columnar storage and a fixed-width ASCII blob (X-S2-1).
   - **TTL.** `created_at = 1900-01-01T00:00 + FF-ABS ms`, adjusted from LPAR local time to UTC (Q3). `expires_at = created_at + retention × (86400 s for 'D' | 31,536,000 s for 'Y')`, the same arithmetic as ZFAM000 L30–31 (no leap years).
   - **ECRs.** These have KEY rows only, no FILE (ZFAM000 `3100`). Expiry uses `FK-ABS`.
4. **CI rebuild.** After the load, call S2's `SecondaryIndexMaintainer.rebuild(instance)` (S2-WP4) to regenerate `zfam_ci` from documents and FAxxFD `ID>0` fields. Then diff the result against the unloaded `FAxxCIyy` rows (as a set of `(field,IDN+NC)`) and report extras or missing rows. Legacy CI drift is expected; the rebuilt index is the source of truth.
5. **Load.** `COPY` into `stg_*` tables, then `INSERT … SELECT` into the final tables in one transaction per instance. Reseed the sequences that replace named counters (`FK-FF-NC`, UID modulo; S3) to max+1.
6. **Reconcile** (gate for every rehearsal and for the cutover):
   - Counts: KEY rows, FILE rows, segments, CI rows, per instance and DDNAME, compared with the IDCAMS totals.
   - Checksums: SHA-256 over the canonical `(key EBCDIC bytes ‖ reassembled payload bytes as unloaded)`, computed in the parser. Then a **round-trip check**: re-encode the PG content back to EBCDIC and compare the hashes.
   - Orphan reports: keys without FILE (legacy 50702), FILE rows without keys, segment gaps, bad COMP-3 values.
   - HTTP sampling: 1% of keys (minimum 1,000), `GET` against both legacy and Java, comparing status, `zFAM-*` headers, and body bytes.
7. **Cutover and rollback with dual-run** (uses §3.1 wire compatibility):
   - (a) Deploy Java zFAM in the new DC with its inbound `/replicate` already in **inbox mode**: requests are persisted in arrival order to `replication_inbox` (same columns as the outbox) and answered 200, but not applied. Leave legacy `FAxxDC` unchanged for now, so Java receives nothing yet.
   - (b) Backfill, in this order:
     1. Start the write freeze (step 1 scope).
     2. Run **all** REPROs (KEY, every FILE DDNAME, CI, FAEXPIRE) and verify the IDCAMS control totals while still frozen.
     3. Set legacy `FAxxDC` to `type: AS` → Java. Inbox capture is already active, and AS is the only mode in which Query Mode replicates. Then lift the freeze. Every write after the snapshot is captured in the inbox, and none was applied to Java early.
     4. Parse and load the frozen unload (steps 2–5) into empty final tables, so there are no PK conflicts.
     5. Apply the inbox in order with normal handler semantics: a DELETE after the snapshot removes the row, and a replayed POST of a snapshot key gets 409, as in legacy. Deleted records can't be resurrected because no snapshot row is loaded after the deletes are applied.
     6. Switch Java to live apply through a **fenced handoff**. Inbound requests keep enqueuing while the replay worker drains the inbox. When the inbox is empty, the worker takes the per-instance advisory lock that inbound handlers also take, re-checks that it is empty, and flips the mode in the same transaction. No live request can overtake a queued one. WP12 tests this under continuous POST/PUT/DELETE/APPEND traffic.

     The loader uses `INSERT … ON CONFLICT DO NOTHING` only so that a failed load can be re-run against a partial target; it never overwrites a newer row. **ZFAM101 CWR is not a safe live backfill.** Its race (read K → legacy deletes K → replicated DELETE is a no-op at Java → CWR POSTs K) resurrects deletes, and legacy DC rebuilds have the same exposure. Use CWR only inside a write freeze.
   - (c) Run nightly reconciliation (step 6) until zero diffs for N days.
   - (d) Shadow reads: mirror GET traffic at the load balancer and diff the responses (§5 L6).
   - (e) Flip DNS or the load balancer to Java. Set Java to `mode=AS` with `partner-url` = legacy, so the legacy side stays warm.
   - (f) **Rollback** means flipping DNS back. Both sides are current within the replication lag. Run a reconciliation of the outbox `FAILED` rows first.
   - (g) Decommission after the soak period: disable replication and run DELETE CLUSTER.

## 5. Parity and regression testing strategy (whole migration)

| Layer | What | Tooling | Owner |
|---|---|---|---|
| L0 Codecs | COMP, COMP-3, zoned, EBCDIC, ABSTIME vectors | GnuCOBOL (`cobc`) programs write known values through the real copybooks, and `iconv IBM-1047` provides EBCDIC. JUnit asserts the decode. | S4-WP4 |
| L1 COBOL oracle harness | Runs the Basic Mode COBOL programs (ZFAM002–005, 007–009, 090, 101, 102) with no mainframe | Preprocess `EXEC CICS` into `CALL` C stubs: indexed files via GnuCOBOL BDB/VBISAM for KSDS, captured WEB RECEIVE/SEND/CONVERSE/headers, a fake partner for replication. Build with `-fnotrunc` (TRUNC(BIN)) and widen pointer REDEFINES to `COMP-5 S9(18)`. Emits golden request/response fixtures. HLASM programs (ZFAM001/006/010/020/022/030/040/041, ZFAMNC, ZUIDSTCK) cannot run, so they are covered by L2/L3. | S4-WP3 |
| L2 Golden master | Recorded HTTP exchanges against legacy zFAM if any z/OS test LPAR, ZD&T, or Wazi image is available (Q5); otherwise L1 output plus spec fixtures | Fixtures in YAML (method, path, query, headers, base64 body → status, status text, `zFAM-*` headers, body). Normalizers mask `zFAM-UID`, ABSTIME/date, `Date`/`Server` headers, and header case and order. Replayed with JUnit 5 `@ParameterizedTest` against Spring Boot + Testcontainers PG. | S4-WP1 |
| L3 Contract tests per endpoint | Every documented behaviour: Basic CRUD/browse/LOB/ECR/UID/modulo/TTL/locks (`Usage.md`, `example_basic_mode.md`), zQL (`example_query_mode.md`, `howto_define_query_mode.md`), security (`howto_define_security.md`), and **each of the 94 lines in `http_response_codes.md`**, asserting HTTP status + `SSS RR-RRR` reason text | Fixture-driven. A coverage report fails CI if a code has no test. | S4-WP2 (catalogue); each segment fills in its rows |
| L4 Replication | Two Spring contexts + two PG containers (DC-A/DC-B), plus WireMock for partner faults | A1/AA/AS ordering (response timing captured), path rewrite, no loop, ECR/LOB/append headers, query-string forwarding, Query Mode AS-only rule, deplicate 201/ABS, CWR restart/idempotency/409. **Interop:** replay `/replicate` requests captured from L1 (ZFAM101/102/002 stubs) into Java. | S4-WP11 |
| L5 Migration | Synthetic VSAM unloads (GnuCOBOL writes VB files from the copybooks: multi-segment, LOB, orphans, ECR, binary + text media, every TTL type) → converter → PG → reconciliation must be green. Property-based tests (jqwik) for the codecs. | | S4-WP5/6 |
| L6 Dual-run | Shadow traffic comparator and nightly reconciliation in pre-prod and prod (§4.7) | | S4-WP12 |
| L7 Performance | Gatling: single-key GET/POST p99, browse, 32K/3.2MB/LOB append, CWR throughput, compared with legacy SLAs (Q6) | | S4-WP13 |

**How other segments' WPs are verified.** Every S1/S2/S3 WP PR must (1) add or enable its rows in the L3 contract catalogue, (2) pass the L2 golden-master corpus for its endpoints, and (3) keep the L3 coverage gate green.
- **S1** (Basic CRUD/browse) is additionally diffed against the L1 COBOL oracle on the same inputs, with explicit EBCDIC-collation browse tests (mixed case, digits, LOW-VALUE padding).
- **S2** (zQL/CI) gets a parser corpus from the examples plus negative syntax cases (400 06–09-001), fuzzing of the zQL query string, and a CI-consistency invariant: after any write, `zfam_ci` equals `rebuild()`.
- **S3** (front door, security, platform) gets a security matrix (HTTP vs HTTPS, FAxxSD levels, 401 xx-001 codes), URI shape checks (seven slashes, 414s), TTL expiry with an injected `Clock`, UID/named-counter format tests, and the `/replicate` partner-auth tests.

## 6. Interfaces with other segments

**Needs from S1:**
- (X-S1-1, S1-WP2) KEY/FILE schema and repositories, with `key bytea` in EBCDIC order or an agreed collation, plus the segment/LOB storage choice.
- (X-S1-2, S1-WP12, after S4-WP7) Hook calls through the `ReplicationPort` SPI at the ZFAM002 points listed in §1, distinguishing AA-before and AS-after response.
- (X-S1-3) Exposing `ecr`/`lob`/`append` flags and the original query string.
- (X-S1-4) ZFAM003 range-delete replication hook.
- (X-S1-5) A FileStore read API for CWR and deplication.

**Needs from S2:**
- (X-S2-1, S2-WP3 `FixedRecordCodec`) The document storage format (affects conversion).
- (X-S2-2, S2-WP7 hook SPI, S2-WP10, S2-WP11) Hooks at ZFAM010/030/040 `ZR_0010`, passing pk name and value.
- (X-S2-3, S2-WP4) `SecondaryIndexMaintainer.rebuild(instance)`.
- (X-S2-4, S2-WP11) Inbound handling of `DELETE ?zql,DELETE,(WHERE(name=key))` on `/replicate`.

**Needs from S3:**
- (X-S3-1, S3-WP2) Front-door routing of the `/replicate` and `/deplicate` prefixes, with security bypass replaced by partner auth.
- (X-S3-2, S3-WP1) An instance config registry (replaces the `FAxx*` templates and URIMAP path).
- (X-S3-3, S3-WP6) The TTL job calls a `DeplicationPort`. S3-WP6 ships a no-op implementation; S4-WP9 provides the real one (201/ABS handling) and wires it.
- (X-S3-4, S3-WP5) Sequences replacing named counters, with reseed support.
- (X-S3-5, S3-WP0) The Spring Boot skeleton, Testcontainers base, and CI pipeline.

**S4 exposes:** `ReplicationService`, `DeplicationClient`/`Handler`, the CWR admin endpoint, the `zfam-codec` library, the parity harness with fixture format, the L3 catalogue and coverage gate, and the `zfam-migration` CLI.

**Provisional decisions** (coordinator, pending user sign-off):
- **P1.** Keys are stored as EBCDIC-ordered `bytea` (R1).
- **P2.** LOBs are stored as segment rows (`zfam_file_segment`), not a single `bytea`, to get around the 1 GB limit (R3, Q4).
- **P3.** Strict parity first. Retries (`strict-legacy=false`), partner mTLS auth and TTL forwarding are flagged follow-ups (R4, R5, R7, Q9). Launch still needs a partner control: the replication port must be network-restricted to the partner DC (firewall/private link allowlist, as legacy `ZFAMREPL` relies on). An unauthenticated `/replicate` on a reachable port is a go-live blocker.

## 7. Work packages (one PR each)

| ID | Title | Source | Description / acceptance criteria | Est (d) | Depends on |
|---|---|---|---|---|---|
| S4-WP1 | Golden-master harness | all | Fixture format, normalizers, replay runner (JUnit 5 + Testcontainers). AC: a sample fixture replays green; a mismatch gives a readable diff. | 4 | S3-WP0 skeleton (X-S3-5) |
| S4-WP2 | Contract catalogue + coverage gate | `http_response_codes.md`, `Usage.md`, `example_*.md`, `howto_*.md` | AC: 94 codes enumerated with an owner segment; CI fails on any uncovered code; Basic and zQL example flows encoded. | 5 | WP1 |
| S4-WP3 | GnuCOBOL stubbed-CICS oracle | ZFAM002–005, 007–009, 090, 101, 102 | AC: preprocessor + C stubs; ZFAM002 POST/GET/PUT/DELETE and ZFAM101 run headless; emitted fixtures load into WP1. | 8 | WP1 |
| S4-WP4 | `zfam-codec` | ZFAMFKC/FFC/CIC | EBCDIC (CCSID configurable), COMP, COMP-3, zoned, ABSTIME↔Instant. AC: L0 vectors pass, including negative and max values. | 3 | none |
| S4-WP5 | VSAM unload parser/transformer | `*.idcams`, copybooks, ZFAM101 `3400/3700` | RDW parsing, segment/LOB reassembly, media-based conversion, TTL, orphan report. AC: L5 synthetic corpus parses with expected counts and reports. | 6 | WP4, S1-WP2, S2-WP3 (`FixedRecordCodec`) |
| S4-WP6 | Loader, CI rebuild, reseed, reconciliation | `DEFCI.jcl`, `ZFAMCI.idcams` | AC: COPY load and round-trip SHA-256 equal; CI diff report; sequences reseeded; HTTP sampler compares two base URLs. | 6 | WP5, S2-WP4 (`SecondaryIndexMaintainer.rebuild`), S3-WP5 |
| S4-WP7 | Replication core (Basic Mode) | ZFAM002 L2299–2475, 2848–2910, 3379–3480, 3752–4060; FA##DC | Properties, outbox, `PartnerClient`, AA/AS/A1 timing, path rewrite, headers, inbound partner auth. AC: L4 Basic tests green; `strict-legacy` toggles retry. | 6 | S1-WP4, S3-WP1, S3-WP2. Defines the `ReplicationPort` SPI + outbox; S1-WP12 wires the S1 hooks afterwards. |
| S4-WP8 | Query Mode replication (ZFAM102) | ZFAM102; ZFAM010/030/040 ZR blocks | AC: AS-only rule, zQL DELETE string byte-equal to `9998-CREATE-ZQL`, full-document POST/PUT, no TTL forwarded (configurable). | 3 | WP7, S2-WP7 (hook SPI), S2-WP10, S2-WP11 |
| S4-WP9 | Deplication | ZFAM002 L2917–2983; ZFAM000 `5000`/`7200` | Handler (201 + ABS when younger) and client. AC: L4 two-DC expiry scenarios, including partner down → local delete. | 3 | WP7, S3-WP6 (ships a no-op `DeplicationPort`; S4-WP9 implements and wires it) |
| S4-WP10 | CWR job | ZFAM101 | Advisory lock, keyset browse, checkpoint, ECR/LOB/append, metrics, admin endpoint. AC: copies 10k-key corpus incl. LOBs; second start returns 409; restart resumes. | 5 | WP7 |
| S4-WP11 | Two-DC + legacy interop suite | ZFAM101/102/002 | L4 suite plus replay of `/replicate` traffic captured by WP3. AC: all modes green in CI. | 4 | WP3, WP7–10 |
| S4-WP12 | Dual-run tooling + cutover/rollback runbook | §4.7 | Shadow comparator, nightly reconciler, runbook with go/no-go criteria. AC: rehearsal on a synthetic instance, both directions. | 6 | WP2, WP6, WP10 |
| S4-WP13 | Performance baseline | n/a | Gatling scenarios + report against SLAs. | 3 | WP7, S1-WP4, S2-WP8–S2-WP11 |

Total: **62 engineer-days**. Critical path: WP1→WP3→WP11 and WP4→WP5→WP6→WP12.

## 8. Risks and quirks

- **R1 Collation.** VSAM orders keys as EBCDIC bytes (lowercase < uppercase < digits). UTF-8/`C` collation inverts this and breaks browse parity. Mitigation: an EBCDIC `bytea` key (§3.2).
- **R2 CCSID / codepage** mismatches corrupt text (`[ ] ¬ |`). Run L0 round-trip tests on real unload samples.
- **R3 LOB > 1 GB** exceeds the `bytea` limit, so segment rows or `oid` are needed. Streaming is needed in CWR and GET.
- **R4 Silent replication loss** is legacy behaviour (status ignored). Parity mode keeps it; the outbox makes it observable. Changing behaviour needs product sign-off.
- **R5 Unauthenticated `/replicate`** is a security gap if ported literally. Plan: mTLS or HMAC, documented as an intentional deviation.
- **R6 Query Mode replicates only under AS** (ZFAM010 L1446–1447 and equivalents). Porting it "fixed" changes behaviour; porting it literally keeps a probable bug (Q1).
- **R7 TTL drift.** Replicas restart their TTL clock (no `FF-ABS` forwarded). ZFAM002 `5600-CHECK-RET` (L2945–2946) appears to compare age against `FF-RETENTION` treated as **seconds** (`RET-SECONDS`→`RET-TIME` ×1000), while ZFAM000 multiplies by day or year. Suspected bug, to be confirmed with the L1 harness before porting.
- **R8 CWR abort quirk** (`3290`): a FILE-less key whose internal key equals `INTERNAL-KEY` (initially LOW-VALUES) aborts the copy. This may trigger on ECR rows if their `FK-FF-KEY` is LOW-VALUES. Verify in L1.
- **R9 ABSTIME timezone.** Values may be LPAR local time, giving hour-level skew in TTL and lock tests (Q3).
- **R10 No mainframe access** limits golden masters to the L1 oracle plus spec. HLASM paths (ZFAM001/010/020/030/040) have no executable oracle.
- **R11 Dual-run divergence** is possible because there is no conflict resolution. Nightly reconciliation plus a defined source of truth per phase.
- **R12 Backfill races:** live replication plus snapshot/CWR backfill can resurrect deleted or stale keys. Mitigated by the freeze + inbox ordering in §4.7(b).

## 9. Open questions

- Q1. Is "Query Mode does not replicate under AA" intended? Should the target replicate Query Mode under AA?
- Q2. Which EBCDIC CCSID does the production LPAR use (1047, 037, 1140)? Are any keys or payloads DBCS?
- Q3. Is `ASKTIME ABSTIME` on the target LPARs UTC or local time? What is the TZ offset history (DST)?
- Q4. Should LOBs be stored as segment rows (proposed) or PG large objects or external object storage?
- Q5. Is any z/OS test environment (ZD&T/Wazi/test LPAR) available for recording golden masters?
- Q6. What are the performance and replication-lag SLAs for AA vs AS?
- Q7. `ZFAM100` (`/zComplete`, `/zRecovery`, tran FZ##) is defined in `CSDFA##.rdo`/`CSDZFAM.rdo` but its source is missing. Is it in scope, and does recovery depend on it?
- Q8. Which transaction ID starts ZFAM101? None is defined in `*.rdo`, yet the program derives `FA##` from `EIBTRNID(3:2)`. How is CWR scheduled operationally?
- Q9. After cutover, may the target improve on legacy (retries, partner auth, TTL preservation via a `zFAM-ABS` header), or is strict parity required for an initial release?
