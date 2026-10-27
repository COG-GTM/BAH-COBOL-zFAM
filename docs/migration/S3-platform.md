# S3 — Front door, security, platform services & ops

Segment **S3** (`platform`) of the zFAM → Java 17 / Spring Boot 3 / PostgreSQL migration.
Covers the HTTP entry point (ZFAM001), authentication/authorization (RACF + FAxxSD), platform services
(named counter, STCKE TOD/UID, L8WAIT), the background TTL expiration task (ZFAMPLT + ZFAM000), and all
install/ops artifacts (JCL, CSD `.rdo`, IDCAMS, CONFIG/REXXREPL). S3 also owns **S3-WP0, the project
skeleton every other segment builds on**.

Wire contract (URIs, query strings, `zFAM-*` headers, status codes/texts in `http_response_codes.md`) must
stay byte-compatible. Line numbers below refer to `master` @ `f57e36a`.

---

## 1. Inventory

| Artifact | LOC | What it does | Mainframe APIs used |
|---|---|---|---|
| `Source/ZFAM001.asm` | 3,778 | Initial HTTP handler for every `/datastore`, `/replicate`, `/deplicate` request (transactions `FAxx`/`FRxx`/`FDxx`, `CSDFA##.rdo` L35–58). Writes `Access-Control-Allow-Origin: *`; `WEB EXTRACT` scheme/method/path/first 3 bytes of query string (`SY_0010`, L363); enforces limits (QS > 8192 → 414-01, path > 512 → 414-02); Basic-Auth decode + RACF verify (`SY_0020`/`SY_0030`, L407–451); loads `FAxxSD`/`FAxxFD` doc templates (`SY_0050`/`SY_0060`, L452–537); chooses mode (`SY_0090`, L538: QS starts `ZQL` → Query Mode); Basic-Mode security (`BM_0010`–`BM_0224`, L587–714); CI detection & `ZFAM-FAXXFD` container (`BM_0300`/`BM_0400`, L715–753); `XCTL ZFAM002` (`BM_0600`, L760); Query-Mode zQL parse into parser array + containers (`QM_0010`–`QM_0510`, L836–2594, **parse logic owned by S2**); Query-Mode security (`QS_0010`–`QS_0310`, L2595–2728); service routing (`QS_0400`–`QS_0500`, L2729–2912); error funnel `ER_xxxxx` → `XCTL ZFAM090` (`ER_XCTL`, L2980) with hard-coded 500 fallback; embedded `ZDECODE` CSECT base64 decoder (L3511–3700). | `WEB EXTRACT/READ HTTPHEADER/WRITE HTTPHEADER/RECEIVE/SEND`, `VERIFY USERID` (RACF), `DOCUMENT CREATE/RETRIEVE`, `GETMAIN`, `PUT CONTAINER` (channel `ZFAM-CHANNEL`), `XCTL`, `ENTER TRACENUM` |
| `Source/ZFAMNC.asm` | 300 | Transaction `ZFNC` (terminal `ZFNC,FAxx` or COMMAREA). `DEFINE DCOUNTER('FAxx_ZFAM')` VALUE 1, MIN 1, MAX `X'FFFFFFFF'` (L145, L244–246); then `START TRANSID('FXxx') FROM('FAxx')` to kick off expiry (L157–); logs to TDQ `@tdq@` + WTO. | `DEFINE DCOUNTER`, `START`, `RECEIVE/SEND`, `WRITEQ TD`, `WRITE OPERATOR`, `ASKTIME/FORMATTIME` |
| `Source/ZUIDSTCK.asm` | 70 | Called (`CALL ZUIDSTCK USING THE-TOD`) by ZFAM002 (L2198, L3312) and used similarly in ZFAM010: returns 16-byte `STCKE` TOD. ZFAM002 uses `THE-TOD(1:6)` + counter halfword as the internal FILE-store key (`FK-FF-IDN`/`FK-FF-NC`) and to build zFAM-UID values. Shared with the separate ZUID repo. | `STCKE` |
| `Source/L8WAIT.asm` | 159 | `LINK`-able threadsafe sleep via `STIMERM` on an L8 TCB. COMMAREA `CA_RC CL4, CA_WAIT F` in 10 ms units clamped 1–90 (10–900 ms), RC `0010`/`0900`/`0000`; wrong COMMAREA length → 2.5 ms (L73–99). ZFAM002 calls it 100 ms × up to 50 for row-lock waits (`3270-WAIT`, L1705). | `STIMERM`, `ENTER TRACENUM` |
| `Source/ZFAMPLT.cbl` | 168 | PLT-PI program (tran `FPLT`). `INQUIRE URIMAP START/NEXT/END`; for each URIMAP named `FAxx` with blank suffix, `START TRANSID('FXxx') FROM(<urimap tran>)` and log (`2100-CHECK-URIMAP`, `2200-START`). | `INQUIRE URIMAP`, `START`, `WRITEQ TD`, `WRITE OPERATOR` |
| `Source/ZFAM000.cbl` | 1,025 | Expiry task `FXxx`. `RETRIEVE` (tran + resume key). If no resume key: sysplex `ENQ CICSGRS_ZFAM000_FXxx` NOSUSPEND (`1200-ENQ`), read/insert/rewrite `FAEXPIRE` control record keyed by `FXxx`; skip run if last run < `FX-INTERVAL` (86 400 s) (`1100`–`1400`). `STARTBR` on `FAxxKEY` from low-values, `READNEXT` loop (`2000`/`3000`). Event Control Records (`FK-ECR='Y'`) expire on `FK-ABS` (`3100`); others read FILE segment 1 and use `FF-ABS` (`4000`). TTL = `RETENTION × 86 400` (type `D`) or `× 31 536 000` (type `Y`), compared in ms against `ASKTIME` ABSTIME. Expired → `5000-DEPLICATE` (L563): if `FAxxDC` type is `AA` or `AS`, `WEB CONVERSE DELETE /deplicate/...` to partner DC; partner `201` with numeric ABS ⇒ adopt partner ABS (`5100-UPDATE-ABS`), otherwise log (`9900-LOG-EXPIRATION`) + delete KEY and all FILE segments (`5200`/`5210`); if the partner call fails the record is left for the next cycle. Missing FILE segment 1 ends the run (`4000-READ-FILE`, L514). `SYNCPOINT` every 10 deletes; after 500 deletes/resets re-`START` itself in 2 s with resume key (`8100-RESTART`); normal re-`START` every 24 h `INTERVAL(240000)` (`8000-RESTART`). | `RETRIEVE`, `ENQ`, `READ/WRITE/REWRITE/DELETE/STARTBR/READNEXT` (VSAM RLS), `SYNCPOINT`, `DELAY`, `START INTERVAL`, `DOCUMENT CREATE` (`FAxxDC`), `WEB PARSE URL/OPEN/CONVERSE/CLOSE`, `INQUIRE URIMAP`, `WRITEQ TD`, `ENTER TRACENUM`, `HANDLE ABEND` |
| `Source/CONFIG.txt` / `JCL/CONFIG.jcl` | 42 / 1,028 | Install-time substitution variables (`@zfam_hlq@`, ports 50200/50201/50202, `@tdq@`=CSSL, SMS classes, CSD list…) applied to all JCL/source via REXXREPL. | TSO/REXX, IEBGENER |
| `Source/REXXREPL.exec` | 42 | Naive token search/replace of `CONFIG` words into members. | REXX `EXECIO` |
| `JCL/ASMZFAM.jcl` | 276 | Translate/assemble/compile/link all programs (DFHEITAL/DFHYITVL). | HLASM, Enterprise COBOL |
| `JCL/CSDZFAM*.jcl`, `Source/CSDZFAM.rdo` (136), `CSDZFAMN/S/R.rdo` | 9 ea. / 6 ea. | `DFHCSDUP` for group `ZFAM`: 24 programs (all THREADSAFE/OPENAPI), transactions `ZFNC`, `FPLT`; TCPIPSERVICEs HTTP `@http_port@`, HTTPS `@https_port@` (SSL, `AUTHENTICATE(@auth@)`), replication `@rep_port@`; all `MAXDATALEN(32768)`, `SOCKETCLOSE(5)`. | CSD |
| `JCL/DEFFA##.jcl`, `Source/CSDFA##.rdo` (97), `ZFAMFILE/ZFAMKEY.idcams` | 88 / 20 ea. | Per-instance group `FAxx`: files `FAxxFILE` (KSDS key 16, rec 100–32 700) and `FAxxKEY` (key 255, rec 512), RLS, `READINTEG(UNCOMMITTED)`, `RECOVERY(BACKOUTONLY)`; TRANCLASSes `TCLFA/FD/FR/FX/FZxx` MAXACTIVE 100; transactions `FAxx/FDxx/FRxx`→ZFAM001, `FXxx`→ZFAM000, `FZxx`→ZFAM100; URIMAPs `/datastore|/deplicate|/replicate|/zComplete|/zRecovery/zFAM/@cc@/@reg@/@org@/@appname@*`. | CSD, IDCAMS |
| `JCL/DEFCI.jcl`, `CSDZFAMC.rdo`, `ZFAMCI.idcams` | 63 / 10 / 20 | Per-instance Column Index file `FAxxCInn` (key 64, rec 68, `RECOVERY(NONE)`). Schema owned by S2; provisioning by S3. | CSD, IDCAMS |
| `JCL/DEFEXPR.jcl`, `CSDZFAMX.rdo`, `FAEXPIRE.idcams` | 58 / 10 / 20 | Per-environment expiry control file `FAEXPIRE` (key 4, rec 80–2048). | CSD, IDCAMS |
| `JCL/FA##FD.jcl`, `FA##SD.jcl`, `FA##DC.jcl` (+ `Source/FA##*.txt`) | 41/44/33 | Load FAxxFD (fields, S2), FAxxSD (security), FAxxDC (replication type `A1/AA/AS` + partner URL, S4) as CICS document templates. | IEBGENER, CSD DOCTEMPLATE |
| `Installation.md`, `System Requirements and Considerations.md`, `howto_define_security.md` | 291/72/84 | Install runbook, sysplex/RLS/CF sizing, security template format and precedence rules. | — |

S3 total: **≈ 4,500 LOC of program source** (ZFAM001 3,778 + ZFAM000 1,025 + ZFAMNC 300 + ZFAMPLT 168 + L8WAIT 159 + ZUIDSTCK 70) plus ≈ 2,100 lines of JCL/RDO/IDCAMS/config.

---

## 2. Target design

### 2.1 Module / package layout (S3-WP0 creates it)

Single Maven project, Spring Boot 3.x, Java 17, artifact `zfam-service`. Root package `com.cognition.zfam` (final name TBD by coordinator):

| Package | Owner | Contents |
|---|---|---|
| `…platform.web` | S3 | `ZfamFrontDoorController` (catch-all `/{prefix}/zFAM/**`), `ZfamRequestContext` (replaces `ZFAM-CHANNEL` + containers), `InstancePathResolver`, `ModeRouter`, `CorsHeaderFilter`, `RequestLimitsFilter` |
| `…platform.error` | S3 (contract) / S1 (catalogue) | `ZfamException(status, reason, context)`, `ZfamErrorResponder` — Java port of ZFAM090 catalogue is S1's; S3 defines the exception type and handler |
| `…platform.security` | S3 | `SecurityConfig`, `ZfamBasicAuthFilter`, `CredentialVerifier` (RACF replacement SPI), `SecurityDefinitionService`, `RowAccessAuthorizer`, `FieldAccessAuthorizer` |
| `…platform.config` | S3 | `ZfamInstance`, `InstanceRegistry`, Flyway migrations for platform tables, import tooling for FAxxSD/FAxxDC/CONFIG |
| `…platform.ids` | S3 | `TodClock`, `ZfamUidGenerator`, `CounterService` |
| `…platform.concurrency` | S3 | `LockWaiter` (L8WAIT), per-instance `Bulkhead` (TRANCLASS) |
| `…platform.expiry` | S3 | `ExpiryScheduler`, `ExpiryWorker`, `ExpiryControlRepository` |
| `…basic` / `…query` / `…replication` | S1 / S2 / S4 | Implement `BasicModeService`, `QueryModeService`, `ReplicationClient` interfaces declared by S3 |

### 2.2 Construct mapping

| Mainframe construct | Java / Spring replacement |
|---|---|
| URIMAP `FAxx` path `/datastore/zFAM/cc/reg/org/app*` + TCPIPSERVICE | Single servlet mapping; `InstancePathResolver` matches path prefix against `zfam_instance.base_path` (longest-prefix) → instance id `FAxx`. Prefixes `/datastore`, `/replicate`, `/deplicate` keep distinct semantics (`/zComplete`, `/zRecovery` → ZFAM100, see open questions). |
| `EIBTRNID` suffix (`FAxx` → `FAxxFILE`, `FAxxSD`, …) | `ZfamRequestContext.instanceId`; all repositories take instance id explicitly (no per-instance tables; S1 decides physical layout). |
| `WEB EXTRACT` / `READ HTTPHEADER` / `WEB RECEIVE` | `HttpServletRequest`; body limit 3 200 000 bytes (`S_WR_LEN`). |
| Mode detection (`SY_0090`) | `queryString.length() >= 3 && queryString.substring(0,3).equalsIgnoreCase("zql")` → Query Mode; else Basic Mode. |
| `XCTL ZFAM002/010/020/022/030/040` with `CHANNEL(ZFAM-CHANNEL)` | Direct method call on `BasicModeService.handle(ctx)` / `QueryModeService.insert/select/selectByIndex/update/delete(ctx)`; containers become typed fields on `ZfamRequestContext` (`fieldDefs` ← ZFAM-FAXXFD, `parsedQuery` ← ZFAM-ARRAY, `options` ← ZFAM-OPTIONS, `ttl` ← ZFAM-TTL, `primaryKey` ← ZFAM-KEY, `mediaType` ← ZFAM-MEDIA). |
| `XCTL ZFAM090` COMMAREA `C_LOG` (status, reason, userid, prog, file, field) | `throw new ZfamException(status, reason, ...)` → `@ControllerAdvice` delegates to S1's catalogue for status text; fallback text `03-001 Service unavailable and logging disabled` (500). |
| `ZDECODE` base64 + `VERIFY USERID/PASSWORD` | Spring Security `BasicAuthenticationFilter` + `AuthenticationProvider` backed by `CredentialVerifier` SPI (impl: LDAP/AD bind, or `zfam_user` table with BCrypt). User id upper-cased, 8-char compatible. |
| `FAxxSD` doc template | Tables `zfam_security_def` + `zfam_security_user` (below); cached per instance (Caffeine, refresh on admin change). |
| `FAxxDC` doc template | `zfam_instance.replication_type`, `partner_url` (consumed by S4 and the expiry worker). |
| DCOUNTER `FAxx_ZFAM` (1..2^32-1) / `FAxx_ZFAM_MODULO` (1..99, defined lazily in ZFAM002) | PostgreSQL sequences `zfam_ctr_<inst>` (`MINVALUE 1 MAXVALUE 4294967295 NO CYCLE`) and `zfam_mod_<inst>` (`1..99 CYCLE`) via `CounterService.next(instance, CounterType)`. |
| `STCKE` (ZUIDSTCK) | `TodClock.stcke()` returning 16 bytes: epoch-1900 TOD from `Instant` with a per-JVM monotonic sub-µs counter + node id in the low bytes to guarantee uniqueness across pods. |
| L8WAIT (STIMERM) | `LockWaiter.sleep(units10ms)` with identical clamping; S1 should prefer DB row locks (`SELECT … FOR UPDATE NOWAIT` + retry) but keep the 100 ms × 50 timing contract. |
| PLT `ZFAMPLT` + `START FXxx` ICE chain | `ExpiryScheduler` (`@Scheduled`, cron per instance, default every 24 h) started on `ApplicationReadyEvent` for each enabled instance. |
| `ENQ CICSGRS_ZFAM000_FXxx` (sysplex) | `pg_try_advisory_lock(hash('expiry:'||instance))` or ShedLock (JDBC provider). |
| `FAEXPIRE` control record | Table `zfam_expiry_control`. |
| `SYNCPOINT` every 10 deletes / restart after 500 | `TransactionTemplate` batches of 10; worker yields after 500 and reschedules in 2 s with resume key. |
| ABSTIME (packed ms since 1900-01-01) | `timestamptz` in DB; helper `AbsTime.toInstant/fromInstant` for wire/replication and data migration (S4). |
| `WRITEQ TD CSSL` / `WRITE OPERATOR` / `ENTER TRACENUM` | SLF4J structured JSON logs (`logger=zfam.expiry`, `zfam.audit`), Micrometer counters/timers, OpenTelemetry spans. |
| TRANCLASS MAXACTIVE(100) per instance | Resilience4j `Bulkhead` per instance+prefix (config-driven, default 100). |
| CSD/JCL/IDCAMS/REXXREPL/CONFIG | Flyway migrations + `application.yml` profiles + Helm chart values; provisioning REST API `/admin/instances` and CLI. |

### 2.3 Platform tables (Flyway, owned by S3)

```
zfam_instance(instance_id char(4) PK, base_path varchar(256) UNIQUE, cc, reg, org, app_name,
              environment varchar(8), scheme_policy varchar(5) /*HTTP|HTTPS*/, enabled bool,
              replication_type char(2) default 'A1', partner_url varchar(160),
              expiry_interval_s int default 86400, max_active int default 100, created_at timestamptz)
zfam_security_def(instance_id PK/FK, bm_read_only bool, qm_read_only bool)   -- row exists ⇔ "FAxxSD defined"
zfam_security_user(instance_id FK, user_id varchar(8), access_type varchar(6) /*READ|WRITE|DELETE*/,
                   basic_allowed bool /*col 22*/, field_levels bit(32) /*cols 23-54 = Sec=01..32*/,
                   PK(instance_id,user_id,access_type))
zfam_user(user_id varchar(8) PK, password_hash varchar(100), enabled bool)   -- only if DB credential store chosen
zfam_expiry_control(instance_id PK, last_run_at timestamptz, last_node varchar(64), last_task_id bigint,
                    resume_key bytea, interval_s int default 86400, restart_s int default 86400)
sequences: zfam_ctr_<inst>, zfam_mod_<inst>
```
S3 **requires** from S1's key-store table: `instance_id`, `key` (≤255 bytes), `ecr bool`, `retention_type char(1)`, `retention int`, `abs timestamptz`, and an index on `(instance_id, key)`; recommend a derived `expires_at` column + index so the worker can do `WHERE expires_at < now()` instead of a full browse.

### 2.4 Request flow (replaces ZFAM001)

1. `CorsHeaderFilter`: always set `Access-Control-Allow-Origin: *` (L363) — including on errors.
2. `RequestLimitsFilter`: raw query string > 8192 → 414/01; path > 512 → 414/02.
3. `InstancePathResolver` → `ZfamInstance` (unknown path → 404, matching CICS no-URIMAP behaviour).
4. Effective scheme = request scheme honoring `X-Forwarded-Proto` from trusted proxies only.
5. If HTTPS and prefix is `/datastore`: require `Authorization: Basic …` (failures map to `ER_40101`–`ER_40103`; WP3 pins the exact branch→reason mapping from `SY_0020`/`SY_0030`). HTTP requests and `/replicate`/`/deplicate` skip authentication (preserved quirk, §5).
6. Load `SecurityDefinition` + field defs (S2) for instance.
7. Mode detect. Basic → `RowAccessAuthorizer` (§2.5) → set `fieldDefs` on ctx only if any non-PK field has `ID>000` → `BasicModeService`. Query → requires field defs (error path per `SY_0060`) → S2 parser → `FieldAccessAuthorizer` → route: POST→`insert`, GET→`select` or `selectByIndex` when WHERE starts on a secondary CI (`QS_0480`), PUT→`update`, DELETE→`delete`; unsupported methods → 405 (`ER_40501`–`ER_40505`).

### 2.5 Authorization rules (exact port of `BM_0010`–`BM_0224`, `QS_*`, `howto_define_security.md`)

* `/replicate` → no checks. No SD row → full access (both schemes).
* HTTP + SD: GET allowed only if `bm_read_only` (BM) / `qm_read_only` (QM); writes denied.
* HTTPS + SD, Basic Mode: scan user entries for `(user_id, access_type)` where GET→READ, POST/PUT→WRITE, DELETE→DELETE; no matching user or col 22 ≠ `X` (case-insensitive) → 401 (`ER_40104`–`ER_40110`).
* HTTPS + SD, Query Mode: `qm_read_only` grants read to all; otherwise user lookup and every referenced field's `Sec=nn` bit must be set (`ER_40111`–`ER_40114`).
* Exact branch→reason-code mapping is extracted from `BM_*`/`QS_*` in WP4, table-driven and unit-tested against `http_response_codes.md`.

---

## 3. Work packages

Estimates are engineer-days for a human team. Each WP = one PR.

| ID | Title | Source | Description / acceptance criteria | Est. | Depends on |
|---|---|---|---|---|---|
| **S3-WP0** | Project skeleton | ASMZFAM.jcl, CSDZFAM.rdo | Maven multi-profile build, Spring Boot 3 + Java 17, package layout §2.1, empty service interfaces (`BasicModeService`, `QueryModeService`, `ReplicationClient`, `FieldDefinitionProvider`), `ZfamRequestContext`, `ZfamException` + `@ControllerAdvice` stub, Flyway baseline, Testcontainers PostgreSQL base test class, Dockerfile, GitHub Actions (build, unit, IT, Spotless/Checkstyle, dependency scan). **AC:** `mvn verify` green in CI; container starts and `/actuator/health` = UP against Testcontainers PG; other segments can add packages without touching build files. | 4 | — |
| **S3-WP1** | Instance & security configuration model | CSDFA##.rdo, DEFFA##.jcl, FA##SD/DC.jcl, CONFIG.txt | Flyway tables §2.3, JPA entities/repos, `InstanceRegistry` with cache, importers that parse legacy `FAxxSD` (56-col format) and `FAxxDC` text into tables, `application.yml` replacing CONFIG.txt variables. **AC:** importing `howto_define_security.md` sample yields expected rows; unknown instance → empty; ITs on Testcontainers. | 5 | S3-WP0; S2 FAxxFD model WP (for FD storage contract) |
| **S3-WP2** | Front door: routing, limits, mode dispatch | ZFAM001 `SY_0010`, `SY_0090`, `BM_0300`–`BM_0600`, `QS_0400`–`QS_0500`, `ER_XCTL` | Filters + controller §2.4 steps 1–4, 6–7 (auth stubbed open). CORS header, 414 limits, 3.2 MB body cap, prefix handling, Basic/Query dispatch, GET CI routing (020 vs 022), error funnel to S1 catalogue, 500 fallback text, per-instance bulkhead. **AC:** MockMvc tests for every routing branch and limit; header present on all responses; dispatch verified with mocked S1/S2 services. | 6 | S3-WP0, S3-WP1 |
| **S3-WP3** | Authentication (RACF replacement) | ZFAM001 `SY_0020`/`SY_0030`, `ZDECODE` | Spring Security config, `ZfamBasicAuthFilter` reproducing `ER_40101`–`ER_40103` reason codes, HTTPS-only for `/datastore`, `CredentialVerifier` SPI with LDAP and BCrypt-table impls, user id upper-casing, audit log of failures. **AC:** matrix test (scheme × prefix × header present/malformed/bad creds/good) gives legacy status+text; no credentials logged. | 5 | S3-WP2 |
| **S3-WP4** | Authorization (FAxxSD rules) | ZFAM001 `BM_0010`–`BM_0224`, `QS_0010`–`QS_0310`, howto_define_security.md | `RowAccessAuthorizer` + `FieldAccessAuthorizer` §2.5; API `authorizeFields(instance, user, accessType, Collection<FieldDef>)` consumed by S2. **AC:** parameterized tests cover every precedence branch in `howto_define_security.md` and `ER_40104`–`ER_40114`. | 5 | S3-WP3, S3-WP1; S2 zQL parser WP (field list) |
| **S3-WP5** | IDs, counters & wait utilities | ZFAMNC, ZUIDSTCK, L8WAIT | `TodClock` (16-byte STCKE-compatible), `ZfamUidGenerator` (32/37-char formats per ZFAM002/010 — format rules confirmed with S1/S2), `CounterService` over PG sequences (instance + MODULO; exhaustion → mapped error), `LockWaiter` with L8WAIT clamping/RCs, admin op replacing `ZFNC` (create counters + enable expiry). **AC:** 1M UIDs across 8 threads × 2 JVMs unique and monotonic per node; counter max/no-wrap verified; LockWaiter clamping table tests. | 4.5 | S3-WP1 |
| **S3-WP6** | TTL expiration worker | ZFAMPLT, ZFAM000, FAEXPIRE.idcams | Scheduler per instance, advisory-lock serialization, `zfam_expiry_control` interval gating, ECR vs regular expiry using retention D/Y math (365-day year), batch delete KEY + all FILE segments (10/tx), 500-per-slice with 2 s resume, AA/AS partner `/deplicate` DELETE via S4 `ReplicationClient` (201 ⇒ adopt partner timestamp; partner failure ⇒ keep row), structured expiry log line equivalent to `TD-EXPIRE`. **AC:** Testcontainers IT with clock injection: expired rows deleted, unexpired kept, two app instances never run concurrently, resume after interruption, AA path verified with WireMock partner. | 6 | S3-WP1, S3-WP5; S1 key/file store repository WP; S4 replication client WP |
| **S3-WP7** | Observability & runtime ops | TDQ/WTO/TRACE usage, CSDZFAMN/S/R.rdo, System Requirements | Micrometer metrics (requests by instance/mode/status, auth failures, expiry deletes, counter usage), JSON logging, OTel tracing, health/readiness incl. DB, TLS config for HTTPS listener or ingress, separate replication port/listener, Helm chart + docker-compose. **AC:** dashboards/alerts defined as code; chart deploys to kind in CI smoke test. | 5 | S3-WP0, S3-WP2, S3-WP6 |
| **S3-WP8** | Provisioning API & CLI (replaces JCL/CSD/IDCAMS) | DEFFA##, DEFCI, DEFEXPR, FA##SD/FD/DC jcl, CONFIG/REXXREPL | `/admin/instances` CRUD (create instance, upload FD/SD/DC docs, create CI indexes via S2 DDL hook, create counters, enable expiry), protected by admin role; CLI wrapper; runbook replacing `Installation.md`. **AC:** fresh environment → instance usable end-to-end via API only; idempotent re-runs. | 4 | S3-WP1, S3-WP5, S3-WP6; S2 CI DDL WP |
| **S3-WP9** | Front-door parity test pack | ZFAM001 (all branches), http_response_codes.md | Golden HTTP tests (status line, status text, headers) for routing/auth/limit matrix, plugged into S4's parity harness for side-by-side runs against legacy captures. **AC:** 100 % of ZFAM001 `ER_*` labels covered by at least one golden case. | 3 | S3-WP2, S3-WP3, S3-WP4; S4 parity harness WP |

**Total ≈ 47.5 engineer-days.** Critical path: WP0 → WP1 → WP2 → WP3 → WP4 → WP9.

---

## 4. Interfaces with other segments

**S3 exposes**
* S3-WP0 build, package conventions, `ZfamRequestContext`, `ZfamException`, Testcontainers base class (all segments).
* `BasicModeService.handle(ZfamRequestContext)` (S1 implements); ctx carries instance, method, key path, query string, headers, body stream, authenticated user, optional `fieldDefs` (non-null ⇔ CI processing required, mirrors `ZFAM-FAXXFD` container presence).
* `QueryModeService` (S2 implements) `insert/select/selectByIndex/update/delete(ctx)`; ctx carries `ParsedQuery` (S2 type), `QueryOptions`, `mediaType`, `streamHeader` (`zFAM-Stream`).
* `FieldAccessAuthorizer`, `RowAccessAuthorizer` (S2 calls field authorizer after parse if S2 owns parsing order).
* `TodClock`, `ZfamUidGenerator`, `CounterService`, `LockWaiter` (S1/S2).
* `InstanceRegistry` incl. `replicationType`/`partnerUrl` (S4).
* `AbsTime` conversion helper (S4 data migration).

**S3 needs**
* S1: ZFAM090 status-text catalogue (`ZfamErrorCatalogue.text(status, reason, ctx)`), key/file-store repository with delete-by-key (all segments) + expiry query fields (§2.3).
* S2: `FieldDefinitionProvider.forInstance(id)` (FAxxFD model, `Sec=nn`, `ID>000` ⇒ CI), zQL parser producing referenced fields + "WHERE starts on secondary CI" flag, CI table DDL hook for provisioning.
* S4: `ReplicationClient.deplicateDelete(instance, key) → (status, partnerAbs)`; parity harness; security model for `/replicate` + `/deplicate` traffic; migration of ABSTIME, counters (set sequence `START` > max legacy value) and FAEXPIRE rows.

---

## 5. Behavioural quirks to preserve (or consciously change)

1. **Auth only on HTTPS `/datastore`.** `SY_0010` checks `W_PATH(10)='/datastore'`; `/replicate` and `/deplicate` never read `Authorization`, and `/replicate` bypasses SD checks (`BM_0010`, `QS_0010`). Preserve on the wire, but lock down via mTLS/network policy on the replication listener.
2. **HTTP scheme never authenticates**; with no `FAxxSD` every caller has full access (dev mode). Scheme detection behind a TLS-terminating proxy must be exact.
3. **Credential size limits**: encoded value ≤ 24 bytes, user ≤ 8, password ≤ 8, user id upper-cased (`C_DECODE`, `OC C_USER,HEX_40`). Decide whether to keep rejecting longer values (wire behaviour) or relax.
4. Mode detection uses only the **first 3 bytes** of the query string, case-insensitive (`ZQL`).
5. Query Mode **PUT always routes to ZFAM030**; the spanned-segment scan in `QS_0430`–`QS_0434` computes but does not change the target. `zFAM-Stream` header is read in `QS_0483` but its value is not used by ZFAM001; `ZFAM021` is never used. Do not port dead branches.
6. Basic Mode passes field defs to ZFAM002 only when a non-PK field has `ID>000` (`BM_0310`).
7. `Access-Control-Allow-Origin: *` on every response, written before any validation.
8. Error fallback when ZFAM090 unavailable: 500, text `03-001 Service unavailable and logging disabled`, body CRLF, `text/plain`.
9. Expiry: interval gate 86 400 s, 24 h restart, year = 365 days, ECRs use KEY-store ABS, FILE segment 1 ABS for others; for `AA`/`AS` a failed partner call leaves the record undeleted until the next cycle (`5000-DEPLICATE` nested IFs); missing FILE record aborts the whole run until next cycle (`4000-READ-FILE`).
10. Counter `FAxx_ZFAM` has MAX 2^32-1 and no wrap; MODULO counter 1..99.
11. ZFAM000 header comment refers to "zECSPLT / ZCxx" and Installation.md refers to transaction `ZPLT` while CSD defines `FPLT` — copy/paste artefacts; target uses neither.

---

## 6. Risks

1. **RACF replacement**: RACF password hashes cannot be exported; requires an enterprise IdP/LDAP or re-enrolment; behaviour of revoked/expired passwords (`VERIFY` RESP2 variants all → 401/03) must be matched.
2. **Unauthenticated replication/deplication endpoints** become internet-exposed if deployed naïvely on one port.
3. **Distributed expiry correctness**: losing the sysplex-wide ENQ semantics could double-delete or race with S4 replication; time-base conversion (ABSTIME ms since 1900 vs epoch) errors would mass-expire data.
4. **Counter/UID collisions** after migration if sequences are not seeded above legacy max, or if multiple pods generate identical TOD values (STCKE uniqueness was guaranteed by hardware).
5. **Payload limits** conflict: TCPIPSERVICE `MAXDATALEN(32768)` vs ZFAM001 `S_WR_LEN` 3.2 MB vs 2 GB LOB append (S1) — the effective legacy limit must be measured before choosing gateway/servlet limits.
6. **ZFAM100** (`FZxx`, `/zComplete`, `/zRecovery`) is defined in `CSDFA##.rdo` but its source is not in the repo.

## 7. Open questions

1. Credential store target: corporate LDAP/AD bind, OIDC with Basic-to-token bridge, or local BCrypt table?
2. Keep the 8/8 user/password length limits and HTTP-without-auth behaviour, or tighten as a documented breaking change?
3. How should `/replicate` and `/deplicate` be secured (mTLS on a dedicated listener is proposed)?
4. Is ZFAM100 (`/zComplete`, `/zRecovery`) in scope? Source is missing.
5. Physical DB layout per instance (shared tables keyed by `instance_id` vs schema-per-instance) — S1/S2 decision affects provisioning (WP8) and expiry queries.
6. Should expiry move from a 24 h browse to continuous `expires_at`-indexed sweeps (behaviour change in timing only)?
7. Exact 32 vs 37-char zFAM-UID formatting and where it lives (ZFAM002/ZFAM010) — S1/S2 to confirm; S3 provides the TOD/counter primitives.
8. Required parity for status *text* on 401s (some clients may parse it) — confirm with S4's capture data.
