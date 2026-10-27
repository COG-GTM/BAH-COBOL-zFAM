# S4: Parity harness, data migration & cutover, cross-DC replication (v2)

Segment **S4** (`replication-data-testing`). Target stack (fixed): Java 17 + Spring Boot 3, PostgreSQL, Spring Security, `@Scheduled` workers, Maven, JUnit 5 + Testcontainers. Wire compatibility applies to the **client-facing** REST contract (`/datastore/...`, query strings, `zFAM-*` headers, statuses in `http_response_codes.md`). Internal DC-to-DC traffic is not part of that contract.

This version replaces the closed PR #6. It starts from what S4 must achieve and then maps the legacy artifacts onto those goals. §9 maps old to new WP IDs.

---

## 1. Goals (what S4 must deliver)

| Goal | Statement | Done when |
|---|---|---|
| **G1 Data** | Move every record off VSAM (KEY, FILE incl. LOB segments, CI, FAEXPIRE, counters) with provable correctness | Per-instance counts and SHA-256 checksums match the frozen unload, a re-encode round trip matches, and the orphan report is signed off |
| **G2 Traffic** | Move client traffic onto Java/PG with **no change visible to clients** and a **reversible** cutover | Shadow-read diff is clean, the cutover runs inside the agreed freeze window, and the rollback drill passes in rehearsal |
| **G3 Parity** | Prove parity for **every segment** (S1–S4), not only S4 | Every S1/S2/S3 parity-suite WP is green against the golden master (S4-WP1/WP2) |
| **G4 Resilience** | Give the new system cross-DC resilience with guarantees at least as strong as legacy, as observed by clients | Failover drills show the RPO/RTO targets in §4.3 per instance mode |

Three tracks own these goals, so separate squads can run them:
- **Track A, parity harness** (G3): on the critical path, **starts first** (day 0).
- **Track B, data migration & cutover** (G1, G2): owns the legacy bridge.
- **Track C, cross-DC replication** (G4): owns the steady-state topology.

## 2. Legacy artifacts mapped onto the goals

| Artifact | LOC | What it does (facts used below) | Goal it serves | Fate in target |
|---|---|---|---|---|
| `Source/ZFAMKEY.idcams` / `ZFAMFILE.idcams` / `ZFAMCI.idcams` / `FAEXPIRE.idcams` | 20 each | KEY KSDS `KEYS(255 0)` rec 512 (`ZFAMFKC.cpy`). FILE KSDS `KEYS(16 0)` rec 100–32700 with 356-byte header + `FF-DATA X(32000)` (`ZFAMFFC.cpy`). CI KSDS `KEYS(64 0)` rec 68 (`ZFAMCIC.cpy`). FAEXPIRE one control record per `FXxx` | G1 source layouts | Parsed by S4-WP5. DDL is owned by S1-WP2 / S2-WP4 / S3-WP6 |
| `JCL/DEFFA##.jcl` (88), `DEFCI.jcl` (63), `DEFEXPR.jcl` (58) | 209 | Allocate the above per instance. `@ci_nbr@` ≥ 02 = FAxxFD `ID=` | G1 inventory: which datasets exist per instance | Replaced by S3-WP8 provisioning. S4 reads them only to enumerate unload targets |
| `Source/ZFAM101.cbl` CWR | 1223 | Copies a whole instance to the partner via `/replicate` POSTs. Sysplex `ENQ` (`1000-INITIALIZE`), browse `2000`/`3200`, segment reassembly `3500`/`3700`, ECR `4200-COPY-ECR`. No checkpoint. A replicated POST to an existing key returns 409, so it never overwrites | G1 initial sync (legacy way) | **Dropped** (§5.4). Bulk load + bridge inbox covers initial sync; `pg_basebackup` covers standby initialisation |
| `Source/ZFAM102.cbl` | 909 | Query Mode replication. 279-byte COMMAREA (`CA-TYPE` CREATE/UPDATE/DELETE, `CA-NAME`, `CA-KEY`). Re-reads and POSTs/PUTs the whole document. DELETE sends zQL `9998-CREATE-ZQL` | G2 bridge, G4 | Bridge only (S4-WP8). Not a steady-state mechanism |
| `ZFAM010/030/040.asm` "zFAM Replication" (`ZR_0010`, ~60 LOC each) | ~180 | LINK ZFAM102 **only when `DC_ENV='AS'`**, before WEB SEND | G2 bridge | Replaced by the S2-WP7 hook SPI → `ReplicationPort` |
| `ZFAM002.cbl` replication (`4300`/`5300`/`6400`/`7400`, `4500`/`5400`/`6600`/`7600`, `5500-DEPLICATE-DELETE`, `8000-GET-URL`) | ~400 | AA replicates before WEB SEND, AS after. Partner status ignored (`NOHANDLE`). Loop guard `WEB-PATH(1:10)='/datastore'`. Forwards `zFAM-ECR/LOB/Append` and the query string, but **not** `FF-ABS` | G2 bridge, G4 (defines the observed guarantees) | Bridge only (S4-WP7/WP15) |
| `ZFAM000.cbl` `5000-DEPLICATE` (S3-owned) | — | On expiry under AA/AS, sends `DELETE /deplicate`. On 201 + numeric ABS it adopts the partner ABS (`5100`). On any other response it deletes. **If WEB OPEN/CONVERSE fails it does neither, so the record survives until the next cycle** (nested IFs, L563–590) | G4 | Unnecessary with one logical database (§4). S4-WP9 makes it local-only |
| `CSDZFAMR.rdo` `ZFAMREPL`, `ZFAM001.asm` `/replicate` bypass (S3) | — | Replication port with no SSL and no authentication. The `/replicate` prefix skips every security check | — | **Not carried over** (master D2). Bridge traffic uses the S3-WP7 dedicated mTLS listener |

## 3. Client-observable guarantees today (the bar for G2/G4)

From the code, not the docs:
1. **AA:** the partner write is *attempted* before the client response (Basic Mode), but failures are ignored, so the client gets 200 even if the partner never got the write. RPO on DC loss is therefore *not* zero, and divergence is permanent: nothing reconciles it except TTL deplication.
2. **AS:** the partner write is attempted after the response, in the same task. Same failure behaviour.
3. **Query Mode replicates only under AS.** Under AA, Query Mode writes never reach the partner (master D5, S2 OQ-2).
4. **Both DCs accept writes** under AA, and they keep accepting writes during a WAN partition (divergence follows).
5. **Replica TTL clocks restart** on receipt, because `FF-ABS` is not forwarded.
6. **Failover is client-side:** clients or GSLB switch DC. There is no promotion step.

Strict parity (D5) applies to request/response behaviour on `/datastore`. The items above describe what can be *lost*. Clients can't depend on loss, so the target may be stronger (fewer losses) but must not be weaker on anything clients see: write availability in each DC, latency, and statuses.

## 4. Track C: steady-state cross-DC replication

### 4.1 Options, judged against §3

| Option | AA ("partner has it before the response") | AS (async) | Write in both DCs | Partition behaviour | Failover | Covers CI, TTL, LOB, counters | Fit |
|---|---|---|---|---|---|---|---|
| **C1 PG physical streaming replication**: one primary, a hot standby in the other DC, app tier active in both DCs | **Stronger:** `SET LOCAL synchronous_commit = on/remote_apply` per transaction for AA instances gives RPO 0 | `synchronous_commit = local` for AS/A1 instances: RPO = WAL lag (seconds), the same window as legacy | Yes at the app tier. Standby-DC app nodes write to the primary across the WAN | Standby-DC writes fail until promotion (weaker than legacy AA, see R3) | Patroni or managed promotion, RTO ≈ 30–60 s, one consistent dataset | Yes, everything (WAL) | **Recommended** |
| C2 PG logical replication, bidirectional (`origin=none`, PG16+) | No sync per instance | Yes | Yes | Diverges, and the apply worker **stops** on PK conflict | Manual | Tables only. Sequences don't replicate, which breaks counters | Rejected: operationally fragile, no conflict resolution |
| C3 Managed multi-region (Aurora Global DB with write forwarding, Azure PG Flexible cross-region replica, Cloud SQL cross-region replica) | Varies; mostly async | Yes | Single writer + forwarding | As C1 | Managed (RTO ≈ 1 min) | Yes | **Acceptable substitute for C1** if hosting is a cloud (Q2). Same app design |
| C4 App outbox → partner HTTP `/replicate` (the PR #6 design) | Best-effort, as legacy | Yes | Yes | Diverges, as legacy | Client-side | Only what the app ports (ECR/LOB/append/deplication/CI rebuild by hand) | Rejected for steady state: re-implements replication and keeps legacy divergence. Kept **only as the migration bridge** (§5) |

### 4.2 Recommendation

**C1: a single-writer PostgreSQL primary with a cross-DC streaming standby. The Java app runs active in both DCs. Durability is chosen per instance through the existing `ReplicationPort` SPI.**
- The `FAxxDC` `type` maps to `zfam_instance.replication_type` (S3-WP1). The steady-state `ReplicationPort` implementation (`DurabilityReplicationPort`, S4-WP14) issues `SET LOCAL synchronous_commit` inside the caller's transaction: `AA` → `remote_apply` (the partner DC can read it before the client gets the response), `AS`/`A1` → `local`.
- `remote_apply` only waits for a standby listed in `synchronous_standby_names`, so the cluster names the cross-DC standbys explicitly: `synchronous_standby_names = 'FIRST 1 (dc2_a, dc2_b)'`. With Patroni this is done by `synchronous_mode: true`, which also limits automatic failover to a standby that was synchronous. Deployment and promotion runbooks check `pg_stat_replication.sync_state = 'sync'` for a DC2 member. AS/A1 transactions opt out with `local` and never wait.
- **AA when no synchronous standby is available.** The default is `synchronous_mode_strict: false`. Patroni drops the sync requirement, AA commits continue with asynchronous acknowledgement, a `zfam_aa_degraded` alert fires, and RPO is > 0 until a standby re-syncs. This keeps write availability at least as good as legacy AA, which never failed a write because the partner was down. The alternative, `strict: true`, keeps RPO 0 but makes AA writes block or time out while DC2 is down. That choice is Q1b.
- Deplication, CWR, loop guards and the Query-Mode-AS-only gap disappear: there is one logical dataset, so TTL runs on the primary and its deletes replicate. Fixing the Query Mode gap makes the system strictly *more* consistent than legacy and is flagged under D5 (Q1).
- Standby-DC app nodes route writes to the primary (JDBC multi-host `targetServerType=primary`). Reads can use the local standby only for `WITH UR`-equivalent requests (S2-WP8). Everything else reads from the primary, to keep read-your-writes, which legacy gives within a DC.
- A1 instances are replicated too (WAL is cluster-wide). If an instance must stay in one DC, for residency for example, it needs its own cluster (Q3).

### 4.3 Targets

| Mode | RPO on DC loss | RTO | Write latency added in the standby DC |
|---|---|---|---|
| AA | 0 while a DC2 sync standby is healthy; > 0 only in the alerted degraded state (§4.2) | ≤ 60 s (promotion) | 1 WAN RTT per transaction (+ sync wait) |
| AS / A1 | ≤ replication lag (alert at 5 s) | ≤ 60 s | 1 WAN RTT per statement round trip (S1/S2 keep one round trip per request) |

### 4.4 When the bridge retires

The `/replicate`/`/deplicate` wire protocol exists only while legacy and Java coexist (§5). It is retired per instance when **all** of these hold: (1) the rollback window agreed in Q6 has elapsed (default 30 days) without a rollback, (2) the legacy instance is set read-only and decommissioned, (3) the outbox is empty. Retirement disables the `LegacyBridgeReplicationPort`, drops `replication_outbox`/`replication_inbox`, and removes the `/replicate` routes from the mTLS listener (S3-WP7 config). From then on `ReplicationPort` is only `DurabilityReplicationPort`.

## 5. Track B: data migration and cutover

### 5.1 Pipeline (G1)

1. **Unload** per instance inside a **write freeze** that stops every writer of the instance's datasets: `/datastore` POST/PUT/DELETE, inbound `/replicate`/`/deplicate` (FR##/FD## URIMAPs), the TTL task `FPLT`/ZFAM000, CWR, and admin jobs. If a legacy partner DC exists, freeze both sides, because legacy outbound replication never retries. Reads stay up. Run `IDCAMS REPRO` for KEY, every FILE DDNAME seen in `FK-DDNAME`, each `FAxxCIyy`, and FAEXPIRE. Transfer in binary with RDWs. Capture the `RECORDS PROCESSED` control totals.
2. **Parse** (S4-WP5) with `zfam-codec` (S4-WP4): `COMP` = unsigned big-endian, `COMP-3` → `BigDecimal` (C/F +, D −), EBCDIC CCSID per Q4.
3. **Transform.** *Keys:* strip X'00' padding and keep the EBCDIC bytes as `key bytea` (provisional P1). *Payload:* group FILE rows by `IDN+NC`, order by `FF-SEGMENT`, check against `FF-SEGMENTS`/`FK-SEGMENTS`, take `data[0:reclen−356]`, and convert to UTF-8 **only** for `text/*`, `application/xml`, `application/json` (as ZFAM101 `8100` L869). Query Mode documents go through S2-WP3 `FixedRecordCodec`. *LOBs:* stay as segment rows (provisional P2). *TTL:* `created_at = 1900-01-01 + FF-ABS ms` (local→UTC per Q5); keep the raw ABS as well. *ECRs:* KEY row only.
4. **Load** (S4-WP6): `COPY` into staging, then `INSERT … SELECT` into empty final tables, one transaction per instance. Reseed the S3-WP5 sequences to max+1. Rebuild CI with S2-WP4 `SecondaryIndexMaintainer.rebuild(instance)`, then diff the result against the unloaded CI. The rebuilt CI is authoritative and legacy drift is reported.
5. **Reconcile** (gate for every rehearsal and for cutover): counts against the IDCAMS totals; SHA-256 over `(EBCDIC key ‖ payload bytes as unloaded)`; re-encode PG → EBCDIC and compare the hashes; orphan report (key without FILE = legacy 50702, FILE without key, segment gaps, bad COMP-3).

### 5.2 Cutover (G2): pick the variant by freeze budget

Rehearsal measures `T = unload + transfer + load + reconcile` per instance.

- **Variant 1, no inbound bridge (preferred when T fits the agreed maintenance window, Q7).** Freeze → unload → load → reconcile → shadow-read diff on a sample → switch GSLB to Java → enable the outbound bridge (Java → legacy) → lift the freeze. S4-WP15 is not built.
- **Variant 2, inbound bridge (when T is too long).** Java's `/replicate` runs in **inbox mode** (S4-WP15) before anything is pointed at it. Freeze → run all REPROs → set legacy `FAxxDC` to `AS` → Java (inbox active) → lift the freeze → load from the frozen unload → replay the inbox in order with normal handler semantics → **fenced handoff** to live apply (inbound handlers and the replayer share a per-instance advisory lock; the mode flips only after a re-check that the inbox is empty). Legacy never retries, so a lost legacy→Java request shows up as a reconciliation diff. The inbox can't prove its own completeness: a write that never arrived leaves no inbox row. So the gate does not use it. Under a **final freeze**, a second `REPRO` of the instance is parsed by S4-WP5 and compared key by key (SHA-256 of key ‖ payload, every key) against a Java export. Keys that differ, are missing or are extra are repaired from that second unload before the traffic switch. The final freeze therefore lasts unload + compare, with no full load.

In both variants, after the switch Java is primary and the **outbound bridge** keeps legacy current for rollback. `LegacyBridgeReplicationPort` (S4-WP7) writes a self-contained outbox row in the data transaction: full body for POST/PUT, appended segment for APPEND, key bytes for an ECR POST, NULL for DELETE. One in-flight row per instance, in `id` order, so ZFAM003 range DELETEs are never overtaken. Delivery **retries** with backoff. That is allowed because this is internal traffic, not client behaviour. Not every write is safe to repeat (APPEND adds segments again; a replicated POST to a key that now exists returns 409). So when an outcome is **ambiguous** (timeout, or a reset after the request was sent), the worker verifies before retrying. Each outbox row stores the expected post-write state of the key: length + SHA-256, or absent for a DELETE. The worker GETs the key from legacy. If it matches the post state, the row is marked SENT. If it matches the pre state (also stored), the row is retried. Otherwise the instance is flagged `DIVERGED`, its rollback is marked unavailable, and the key is repaired with a full-value PUT/LOB rewrite. The bridge sends **all** writes, Query Mode included under any mode, so the rollback target is complete.

### 5.3 Rollback

Freeze → the outbound outbox drains to 0 (if it can't drain within the window, rollback is declared unavailable and the incident path is roll-forward) → **verify legacy byte for byte**: legacy `REPRO` → S4-WP5 → compare every key's SHA-256 against a Java export, and repair any diff from Java → switch GSLB back to legacy → lift the freeze. Draining the outbox alone doesn't prove legacy matches. Legacy is then primary. Java can be re-seeded later by repeating §5.1. Rollback is rehearsed in every dress rehearsal (S4-WP12 AC).

### 5.4 Scope dropped versus PR #6

- **CWR port (old S4-WP10) dropped.** Initial sync is §5.1 bulk load (+ inbox in Variant 2). The standby DC is seeded by `pg_basebackup`/managed replica creation. Re-sync after an outage is WAL catch-up. Nothing needs a key-by-key HTTP copier, and §5.1 shows CWR is unsafe outside a freeze anyway (it resurrects deletes).
- **AA-before-response replication timing, partner deplication handshake and 201/ABS negotiation** are not ported as steady-state features. They exist only in the bridge, where needed.
- **Unauthenticated replication port** is not carried over (D2).

## 6. Track A: parity harness (G3, critical path, starts day 0)

**Oracles,** in order of fidelity:
1. **Recorded legacy traffic.** A capture point at the TLS-terminating load balancer or proxy in front of CICS records request/response pairs (body, `zFAM-*` headers, status line and **status text**). Credentials are scrubbed. This is the only oracle for the HLASM paths (ZFAM001/010–040) without a z/OS LPAR (D8).
2. **GnuCOBOL + stubbed-CICS harness** for the Basic Mode COBOL (ZFAM002–009, ZFAM090) as an executable oracle that needs no mainframe. Known build notes: preprocess `EXEC CICS`, use `cobc -fnotrunc` for `TRUNC(BIN)`, keep the CRLF fixed-format sources.
3. **Spec-derived contract cases** from `http_response_codes.md`, `Usage.md` and `example_*.md`. Where they disagree, the code wins (D6).

**Harness** (S4-WP1): fixture = YAML request + expected response + normalizers (UID, timestamps, ABS, `Date`); a JUnit 5 + Testcontainers replay runner against the Java service; a side-by-side mode against two base URLs, which also powers the shadow-read diff in §5.2.

**How each segment's WPs are verified:**

| Segment | Parity WP that consumes S4-WP1/WP2 | Oracle used |
|---|---|---|
| S1 Basic Mode | S1-WP13 | GnuCOBOL harness (S4-WP3) + recorded traffic. Browse ordering checked against EBCDIC fixtures |
| S2 Query Mode | S2-WP12 | Recorded traffic (HLASM) + spec cases. CI results checked against `SecondaryIndexMaintainer.rebuild` |
| S3 Front door, TTL | S3-WP9 | Recorded traffic for status line/text. TTL math from S4-WP4 ABS fixtures |
| S4 Migration | S4-WP6 reconcile, S4-WP12 shadow diff | Frozen unload checksums; legacy vs Java side by side |
| S4 Resilience | S4-WP11 | Failover/partition drills against §4.3. Bridge interop against the GnuCOBOL ZFAM002 harness |

Coverage gate (S4-WP2): every `/datastore` method × mode × documented status/reason code has at least one fixture, and CI fails if one is missing.

## 7. Interfaces with other segments

**S4 needs:** S1-WP2 (key/file schema: `key bytea`, segment rows), S1-WP4 (CRUD services that call `ReplicationPort`), S2-WP3 (`FixedRecordCodec`), S2-WP4 (`SecondaryIndexMaintainer.rebuild`), S2-WP7 hook SPI + S2-WP10/S2-WP11 (Query Mode write hooks), S2-WP11 (applying a bridged zQL DELETE), S3-WP0 (skeleton), S3-WP1 (`zfam_instance.replication_type`/`partner_url`), S3-WP2 (routing of `/replicate`/`/deplicate`, bridge only), S3-WP5 (sequences + reseed), S3-WP6 (TTL worker with no-op `DeplicationPort`), S3-WP7 (D2 dedicated mTLS listener).

**S4 exposes (IDs unchanged):** `zfam-codec` (S4-WP4 → S1-WP2); harness + contract gate (S4-WP1/WP2 → S1-WP13, S2-WP12, S3-WP9); `ReplicationPort` SPI `record(ReplicationEvent)` called inside the data transaction (S4-WP7 → S1-WP12 wires the ZFAM002/003 hook points; S4-WP8 implements the S2-WP7 SPI); `DeplicationPort` implementation (S4-WP9, after S3-WP6); `zfam-migration` CLI (S4-WP5/WP6).

**Provisional decisions** (pending user sign-off; unchanged from the coordinator's list):
- **P1** Keys stored as EBCDIC-ordered `bytea` (master D1). First principles agree: browse and range-delete results depend on VSAM order.
- **P2** LOBs stored as segment rows (master D4). First principles agree: 2 GB > the 1 GB `bytea` limit, and streaming needs segments.
- **P3** Strict parity first for **client** behaviour (D5). Improvements (TTL forwarding, Query-Mode-AA replication) are flagged follow-ups. Under C1 both happen automatically in steady state and are flagged for sign-off (Q1). Retries exist only on internal bridge traffic. **Partner mTLS is not a follow-up:** the bridge uses the D2 mTLS listener from go-live.

## 8. Work packages (one PR each)

| ID | Track | Title | Source | Description / acceptance criteria | Est. (d) | Depends on |
|---|---|---|---|---|---|---|
| S4-WP1 | A | Golden-master harness + traffic capture | all | Fixture format, normalizers, replay runner, side-by-side mode, LB capture adapter. AC: a sample fixture replays green; a mismatch gives a readable diff; capture scrubs credentials | 4 | S3-WP0 |
| S4-WP2 | A | Contract catalogue + coverage gate | `http_response_codes.md`, `Usage.md`, `example_*.md` | AC: CI fails when any method × mode × status/reason lacks a fixture | 5 | S4-WP1 |
| S4-WP3 | A | GnuCOBOL stubbed-CICS oracle | ZFAM002–009, 090 | AC: oracle runs Basic Mode fixtures headless in CI and matches recorded traffic where available | 8 | S4-WP1 |
| S4-WP4 | A | `zfam-codec` | `ZFAMFKC/FFC/CIC.cpy` | EBCDIC (CCSID-configurable), COMP, COMP-3, zoned, ABSTIME. AC: property tests round-trip; EBCDIC order fixtures | 3 | — |
| S4-WP5 | B | VSAM unload parser/transformer | `*.idcams`, copybooks | RDW parse, segment/LOB reassembly, media-based conversion, TTL, orphans. AC: synthetic corpus parses with expected checksums | 6 | S4-WP4, S1-WP2, S2-WP3 |
| S4-WP6 | B | Loader, CI rebuild, reseed, reconciliation | `DEFCI.jcl`, `ZFAMCI.idcams` | AC: round-trip SHA-256 equal; CI diff report; sequences reseeded; side-by-side GET sampler | 6 | S4-WP5, S2-WP4, S3-WP5 |
| S4-WP7 | B | `ReplicationPort` SPI + outbox + outbound legacy bridge | ZFAM002 `4500/5400/6600/7600` | SPI `record(event)` in the data transaction; `LegacyBridgeReplicationPort` with self-contained outbox, per-instance ordered delivery, retries that verify first on an ambiguous outcome, mTLS client cert. AC: Java → GnuCOBOL ZFAM002 interop for POST/PUT/APPEND/DELETE/ECR/LOB; range DELETE not overtaken; a lost response on APPEND/POST never double-applies | 4 | S1-WP4, S3-WP1 |
| S4-WP8 | B | Query Mode bridge hook | ZFAM102, ZFAM010/030/040 `ZR_0010` | Implements the S2-WP7 SPI → `ReplicationPort`. All modes are bridged. AC: zQL DELETE string byte-equal to `9998-CREATE-ZQL`; full-document POST/PUT | 2 | S4-WP7, S2-WP7, S2-WP10, S2-WP11 |
| S4-WP15 | B | Inbound legacy bridge (Variant 2 only) | ZFAM002 inbound, CSDFA## FR/FD | `/replicate`, `/deplicate` handlers on the D2 mTLS listener; inbox mode; ordered replay; fenced handoff. AC: no request overtakes a queued one under continuous POST/PUT/DELETE/APPEND. **Skip if Q7 allows Variant 1** | 3 | S3-WP2, S3-WP7, S1-WP4, S2-WP11 |
| S4-WP12 | B | Dual-run, cutover & rollback | — | Freeze orchestration, shadow-read diff, final reconcile, GSLB switch, bridge flip, rollback drill, bridge retirement checklist (§4.4). AC: full dress rehearsal incl. rollback on prod-sized data | 6 | S4-WP2, S4-WP6, S4-WP7, S4-WP8 |
| S4-WP14 | C | Cross-DC PostgreSQL topology + `DurabilityReplicationPort` | FA##DC | Primary + named cross-DC sync standbys (`synchronous_standby_names`, Patroni `synchronous_mode`, or managed, Q2); per-instance `SET LOCAL synchronous_commit`; alert and runbook for the degraded state; primary routing from the standby DC; promotion/fencing runbook; lag alerts. AC: AA write visible on the standby before the response; promotion ≤ 60 s | 6 | S3-WP0, S3-WP1, S4-WP7 |
| S4-WP9 | C | `DeplicationPort` implementation | ZFAM000 `5000`, ZFAM002 `5500/5600` | Steady state: local delete, run on the primary only (advisory lock + `pg_is_in_recovery()` guard). AC: TTL never runs on the standby; expiry deletes replicate | 2 | S3-WP6, S4-WP14 |
| S4-WP11 | C | Resilience & bridge interop suite | — | Failover drills per mode (RPO/RTO per §4.3), WAN-partition behaviour, bridge interop both ways. AC: drills automated in a two-DC Testcontainers/Kind setup | 4 | S4-WP3, S4-WP8, S4-WP9, S4-WP14 |
| S4-WP13 | A | Performance baseline | — | Gatling per endpoint, incl. standby-DC write latency. AC: report against SLAs (Q8) | 3 | S4-WP1, S4-WP14, S1-WP4, S2-WP8, S2-WP9, S2-WP10, S2-WP11 |

Totals: **Track A 23 d** (WP1–4, 13), **Track B 27 d** (24 d if WP15 is skipped), **Track C 12 d**, **62 d** overall. The old CWR WP (5 d) is gone, and replication is no longer on the client-request critical path. No S4 WP is depended on by a WP it depends on: S3-WP6 ships the no-op port, and S1-WP12 wires hooks after S4-WP7.

## 9. Old → new WP mapping (PR #6 → v2)

| PR #6 | v2 | Change |
|---|---|---|
| S4-WP1–WP6 | same IDs | WP1 adds traffic capture; otherwise unchanged interfaces |
| S4-WP7 "Replication core: outbox, PartnerClient, AA/AS/A1" | S4-WP7 | Same SPI and outbox; now the migration bridge only (Java → legacy, retries, mTLS). Dropped the S3-WP2 dependency (outbound only) |
| S4-WP8 Query Mode replication | S4-WP8 | Bridge hook; all modes bridged |
| S4-WP9 Deplication | S4-WP9 | Local-only implementation; depends on S4-WP14 instead of WP7 |
| S4-WP10 CWR copy job | **dropped** | Covered by bulk load + bridge + `pg_basebackup` |
| S4-WP11 Two-DC replication + interop | S4-WP11 | Becomes the resilience (failover) + interop suite |
| S4-WP12 Dual-run + runbook | S4-WP12 | Adds the variant choice, shadow diff and bridge retirement |
| S4-WP13 Perf baseline | S4-WP13 | Adds standby-DC write latency |
| — | **S4-WP14 (new)** | Cross-DC PG topology + `DurabilityReplicationPort` |
| — | **S4-WP15 (new, optional)** | Inbound legacy bridge (inbox, fenced handoff) |

The master plan (PR #8) critical path `… S1-WP4 → S4-WP7 → S4-WP10 → S4-WP12` becomes `… S1-WP4 → S4-WP7 → S4-WP12`.

## 10. Risks and quirks to preserve

- **R1 Collation.** UTF-8 order breaks browse/range parity. Mitigated by P1.
- **R2 CCSID mismatch** corrupts text. Mitigated by the round-trip check plus a CCSID probe on a known sample (Q4).
- **R3 Partition availability.** Under C1, standby-DC writes fail while the primary is unreachable. Legacy AA kept accepting them, and diverged. This is a client-visible availability change that needs sign-off (Q1). Fallback: C4-style multi-writer per instance, keeping the outbox from S4-WP7.
- **R4 Cross-DC write latency** for clients in the standby DC (+1 WAN RTT). Measured in S4-WP13. Mitigated by one DB round trip per request or by routing writes to the primary DC's app tier.
- **R5 Freeze length.** A REPRO of a live RLS KSDS is not a consistent snapshot, so the freeze is mandatory. Its length decides Variant 1 vs 2.
- **R6 Legacy never retries** legacy → Java bridge traffic, so losses become reconciliation diffs. The key-level diff gates the switch.
- **R7 Rollback freshness** depends on the outbound outbox draining. The lag is alerted, and rollback is declared unavailable above a threshold.
- **R8 Legacy-side mTLS.** The legacy `/replicate` handler skips all security, so peer authentication must happen at the transport. An IP allowlist alone is **not** acceptable, because any host at an allowed address could write or delete. Two options: (a) change the `ZFAMREPL` CSD to `SSL(CLIENTAUTH)` with a RACF keyring that trusts only the Java bridge client cert, or (b) use a z/OS AT-TLS policy that requires a client certificate on that port, which needs no CICS change. In Variant 2 the legacy → Java direction needs a legacy client certificate: `WEB OPEN … CERTIFICATE` or outbound AT-TLS. If neither (a) nor (b) is available, the outbound bridge cannot go live, and that is a cutover blocker, not a D2 exception.
- **R9 ABSTIME timezone** errors would mass-expire data after load (Q5). Mitigated by dry-running TTL in shadow before enabling it.
- **R10 Deplication correction.** PR #6 said a failed partner call deletes locally. Per `5000-DEPLICATE` it does **not**: the record survives to the next cycle. This only matters during the bridge (legacy TTL is disabled on whichever side isn't primary).
- **Quirks to keep for clients:** 409 on POST to an existing key; `zFAM-*` headers; status text on 401s; the suspected seconds-vs-days retention check in ZFAM002 `5600-CHECK-RET` (strict parity until signed off, D5).

## 11. Open questions

- Q1. Accept C1's stronger consistency (Query Mode writes visible in both DCs under AA, no replica TTL restart) and weaker partition availability (R3)?
- Q1b. When DC2 is down, should AA degrade to async (default, legacy-like availability) or block/fail (strict RPO 0)?
- Q2. Hosting: on-prem PG (Patroni) or a cloud managed service (C3)?
- Q3. Must any A1 instance stay in a single DC (residency)? If so, it needs a separate cluster.
- Q4. Production EBCDIC CCSID (1047 / 037 / 1140)? Any DBCS?
- Q5. Is ABSTIME LPAR local time or UTC?
- Q6. Length of the rollback window before the bridge retires?
- Q7. Maximum write-freeze window per instance? This decides whether S4-WP15 is needed.
- Q8. Latency/throughput SLAs per endpoint, and the acceptable replication lag for AS?
- Q9. Can a traffic capture point be placed in front of CICS in production, and is there any z/OS test LPAR (D8)?
- Q10. ZFAM100 (`/zComplete`, `/zRecovery`) is missing from the repo (D7). Out of scope until it is found.
