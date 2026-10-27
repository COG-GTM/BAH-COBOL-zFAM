# S1 — Basic Mode key/value CRUD + browse: migration plan

Segment: **S1** (`basic-mode`). Target stack: Java 17 + Spring Boot 3, PostgreSQL, Spring Security, Maven, JUnit 5 + Testcontainers (set by the coordinator).
Hard constraint: the REST contract stays wire-compatible. That covers URI shape, query strings, `zFAM-*` headers, status codes and status *text*, and body formats.

Line numbers below refer to `Source/*.cbl` on `master` (files use CRLF; column 7–72 text).

---

## 1. Inventory

| Artifact | LOC | Role | CICS / VSAM / other APIs used |
|---|---|---|---|
| `ZFAM002.cbl` | 4343 | Primary Basic Mode program. Parses the URI, query string and headers, then runs GET/POST/PUT/DELETE, LOB, locking, UID/modulo keys, ECR, replication, and the column-index hooks. Hands off to the browse/range programs. | `WEB EXTRACT/RECEIVE/READ/WRITE/SEND/CONVERSE/OPEN/CLOSE/PARSE`, `READ [UPDATE]/WRITE/REWRITE/DELETE/UNLOCK` on `FA##KEY` and `FA##FILE`, `GET DCOUNTER`, `GET/DEFINE/QUERY/DELETE COUNTER`, `ENQ/DEQ`, `GETMAIN/FREEMAIN`, `GET/PUT CONTAINER` (channel `ZFAM-CHANNEL`), `LINK ZUID001/L8WAIT/ZFAM011/031/041`, `XCTL ZFAM003/004/005/007/008/009/090`, `DOCUMENT CREATE/RETRIEVE` (templates `FA##DC`, `FA##DD`), `SYNCPOINT ROLLBACK`, `HANDLE ABEND`, `WRITEQ TD` (CSSL), `CALL ZUIDSTCK` |
| `ZFAM003.cbl` | 920 | Range DELETE (`zFAM-RangeBegin`/`zFAM-RangeEnd`, plus the undocumented `zFAM-Type: Full\|Generic`). Stops at 1000 rows. | `STARTBR GTEQ/READNEXT/ENDBR/DELETE`, `SYNCPOINT` every 10 deletes, `WEB CONVERSE` (replicates the DELETE), `INQUIRE URIMAP`, `XCTL ZFAM090` |
| `ZFAM004.cbl` | 735 | Single-row read for `ge`/`gt` without `rows`, plus the `ex` existence check. | `READ GTEQ`, `LINK ZFAM006`, `GETMAIN/FREEMAIN`, `WEB SEND` |
| `ZFAM005.cbl` | 557 | Single-row read for `le`/`lt` without `rows`. | `READ GTEQ`, `STARTBR`, `READPREV` |
| `ZFAM006.asm` | 114 | Increments a 255-byte key by one with carry, word by word from the right. Used for `gt` when the key is 255 bytes long. | `DFHEIENT`, `RETURN` |
| `ZFAM007.cbl` | 755 | Multi-row forward browse (`ge`/`gt` + `rows`). | `GETMAIN` 3.2 MB buffer, `STARTBR GTEQ/READNEXT`, `READ` FF segments, `LINK ZFAM006` |
| `ZFAM008.cbl` | 784 | Multi-row backward browse (`le`/`lt` + `rows`). About 180 diff lines vs 007. | `READ GTEQ`, `STARTBR`, `READPREV` |
| `ZFAM009.cbl` | 604 | Multi-row `keysonly`. **Forward only** (`READNEXT`). About 320 diff lines vs 007. | `STARTBR/READNEXT` |
| `ZFAM090.cbl` | 1775 | Error responder. Looks up the 140-entry `STATUS-TABLE` (l.1544) by (status, reason, invoking-program suffix from `ASSIGN INVOKINGPROG`). Sends the HTTP status with text `RR-PPP message`, and logs the status plus the key (4 lines) to the CSSL TD queue. Unknown entries go out as `999 99-PPP`. | `ASSIGN`, `WRITEQ TD`, `DOCUMENT CREATE`, `WEB SEND` |
| `HANDLE.cpy` | 136 | Shared paragraphs: `3290-CHECK-RESPONSE`, `9997-FCT-ERROR`, `9998-ZFAM090` (XCTL to ZFAM090, or `503 99-002` if that fails), `9999-WRITE-CSSL`. | as above |
| `ZFAMHEX.cpy` | 536 | Table mapping two-character hex text (`'00'`…`'FF'`) to one byte. Used to decode `delim=%XX` (ZFAM002 `1430/1431`). | — |
| `ZFAMFKC.cpy` | 19 | Key store record `FK-RECORD` (512 bytes): key X(255), ECR flag, FF key (IDN 6 + NC 2), object `text\|bits`, DDNAME suffix, lock UID X(32), `FK-ABS` COMP-3, lock time, LOB flag `L`, segment count, retention COMP-3, retention type `Y\|D`. | — |
| `ZFAMFFC.cpy` | 22 | File store record `FF-RECORD`. Key is 16 bytes: FF key 8 + segment 2 + suffix 2 + zeroes 4. Holds `FF-ABS`, retention, segment count, media type X(56), back-pointer `FF-FK-KEY`, and `FF-DATA` X(32000). Prefix is 356 bytes. | — |
| **Total** | **11,300** | | |

Each instance is identified by CICS transaction `FA##`. `EIBTRNID(3:2)` is copied into the file names `FA##KEY`/`FA##FILE`, the counter name and the doc-template names (ZFAM002 l.779-783). Each instance has up to 100 file-store datasets; the suffix is chosen by doc template `FA##DD` (`8400-DDNAME`).

## 2. Current behaviour (what the Java code must reproduce)

### 2.1 Request parsing (`1000-ACCESS-PARMS`, l.720–786)
- **URI.** The path is scanned until the 7th `/` (`1100/1150`). Fewer than 7 slashes gives `400 02-002`. Everything after the 7th slash is the key, so keys may contain `/` (modulo keys look like `0001/<uid>`). A key over 255 bytes gives `400 03-002`. The key is held in X(255) padded with **LOW-VALUES**.
- A missing key gives a method-specific 400: GET `04-002`, PUT `05-002`, DELETE `06-002`, POST `07-002`. POST without a key is allowed when `zFAM-UID: yes` is sent.
- **Query string, GET** (`1330-GET`). The string is split on `,` into at most **5 parms of 10 bytes each**:
  - The type is one of `eq` (default), `ge`, `gt`, `le`, `lt`, `ex`.
  - `rows=NNNN` is PIC 9(4), so 1–9999. A non-numeric value becomes 1.
  - `delim=c` or `delim=%XX`. `%XX` is decoded through ZFAMHEX. An unknown code falls back to `|` (X'4F').
  - `keysonly` and `ttl` (the latter sets `GET-CA-TTL`; no consumer found).
- **GET dispatch** (l.1109–1140):
  - `ex` → 004.
  - `ge`/`gt` without rows → 004. `le`/`lt` without rows → 005.
  - `ge`/`gt` + rows → 007. `le`/`lt` + rows → 008.
  - **`keysonly` overrides all of these and goes to 009.**
  - `eq` + rows falls through to a plain single-key read.
- **Query string, POST/PUT** (`1310-RETENTION`). Default retention is **7, type `Y` (years)**. Accepted forms:
  - `ret-years=N`, clamped to 1–100.
  - `ret-days=N`, clamped to 1–36500.
  - `ttl=N`, clamped to 1–36500 days.
  - Header `zFAM-TTL: NNNNN` (`1500/1510`) overrides all of these.
- **Size limits.** The body limit is 3,200,000 bytes; exceeding it gives `413 01-001`. If `zFAM-LOB` is present on POST/PUT, or `zFAM-Append` on PUT, the limit rises to **258,000,000** (`1600/1610`). Usage.md says 200 MB. A zero-length body gives `411 01-001`.
- **Text vs binary.** A body is treated as text when Content-Type is `text*`, `application/xml` or `application/json`. Text is received with `SRVCONVERT` (ASCII→EBCDIC) and stored as `FK-OBJECT='text'`. Anything else is stored raw as `bits` (l.817–828, 2210–2215).

### 2.2 Storage model: two-level key store → file store
- `FK` holds one row per user key. `FF` holds 1..N segments of **32,000 bytes** each, keyed by an internal 8-byte id: TOD(6) from `ZUIDSTCK` plus the low 2 bytes of the `FA##_ZFAM` DCOUNTER.
- Segment count is `ceil(len/32000)` (`9001-SEGMENTS`). The maximum is 65535 segments (`SIXTY-FIVE-KB`), about 2.09 GB.
- **POST** (`4000/4100/4200/4300`):
  1. Write FK. On `DUPREC` return `409 02-002`.
  2. Write the FF segments. On error, `SYNCPOINT ROLLBACK` and return `507 06-002`.
  3. If a FAxxFD container exists, `LINK ZFAM011` for the column index.
  4. Respond `200 OK` with a CRLF body.
  5. Add the `zFAM-UID`/`zFAM-Modulo`/`zFAM-LOB`/`zFAM-ECR` response headers when they apply.
- **PUT is copy-on-write** (`6000`–`6400`):
  1. `READ UPDATE` the FK row.
  2. Write the new FF segments under a *new* internal key.
  3. `REWRITE` FK, clearing the lock fields.
  4. Send the 200.
  5. *Then* delete the old FF segments (`6700`, after the response).

  A missing key gives `204 03-002`. A PUT on an ECR row gives `409 04-002`.
- **GET** (`3000`–`3610`):
  - Read FK, then the FF segments, assembled into a GETMAIN buffer.
  - If FF is `NOTFND` (it lost a race with PUT), the read is retried once by re-reading FK. If the same internal key comes back, return `507 02-002` (`3290`, l.1772).
  - The response media type is the stored `FF-MEDIA`, defaulting to `text/plain`.
  - If the 6th URI segment ends in `.LAT`, GET also rewrites `FF-ABS`. This gives sliding expiry from the last access time (l.1804).
- **DELETE** (`5000`–`5300`):
  - Read FK; missing gives `204 02-002`.
  - Delete FK, then delete FF segments 1..n until `NOTFND`.
  - If a FAxxFD container exists, `LINK ZFAM041` with the old record first.
  - Exactly one of RangeBegin/RangeEnd gives `400 10-002`. Begin > End gives `400 11-002`. Otherwise `XCTL ZFAM003` (`5010/5020`).
- **ECR (Event Control Record)**, header `zFAM-ECR: Yes`, undocumented:
  - The row is key-only: `FK-FF-KEY=HIGH-VALUES`, `FK-ECR='Y'`, and no FF row is written.
  - GET returns the *key* as the body (`3620`). The response echoes `zFAM-ECR: Yes`.
- **Row locking**, headers `zFAM-Lock`, `zFAM-Time`, `zFAM-Action`, `zFAM-LockID`, `zFAM-Status`; undocumented in Usage.md but present in the status table:
  - `GET` with `zFAM-Lock: yes` reads FK for update. If the row is free or the lock has expired, it stamps `FK-UID` (from ZUID001), `FK-ABS` and `FK-LOCK-TIME` (1–5 s, default 5), then returns `zFAM-LockID` and `zFAM-Status: Lock successful`.
  - Otherwise, `zFAM-Action: nowait` fails immediately with `409 01-002`. `wait` loops through `L8WAIT` up to 50 times before failing (`3220`–`3280`).
  - `PUT` must present a matching `zFAM-LockID` while the lock is active, or it gets `409 03-002 Lock not active` (`6040`).
- **LOB**:
  - POST/PUT with `zFAM-LOB` sets `FK-LOB='L'`.
  - `PUT` with `zFAM-Append` (`7000`–`7400`) appends segments `n+1..` under the **same** internal key, in place (no copy-on-write). Going over 65535 segments gives `413 02-002`.
  - `GET` with `zFAM-LOB` streams the segments using `WEB SEND CHUNKYES`/`CHUNKEND`, i.e. HTTP chunked transfer (`3700`–`3720`), with no buffer.
- **UID / modulo** (`4700`–`4770`):
  - `zFAM-UID: yes` replaces the URI key with a 32-character `ZUID001` UID.
  - Adding `zFAM-Modulo: NN` produces `NNNN/<uid>`. NNNN comes from named counter `FA##_ZFAM_MODULO`, defined with min 1, max NN and `WRAP`. If max changes, the counter is redefined under `ENQ CICSGRS_FA##`. A DEFINE failure gives `400 08-002`.
  - The response writes headers `zFAM-UID` and `zFAM-Modulo`. Usage.md says the key comes back in the status text, which does not match the code.

### 2.3 Browse
- **Key ordering is VSAM KSDS byte order, i.e. EBCDIC** (lower-case < upper-case < digits). The key is padded with X'00' to 255 bytes.
- **`gt`** is done as `GTEQ` on the key with byte 255 set to X'01'. For a 255-byte key, ZFAM006 adds +1 with carry instead (ZFAM004 `2100`, ZFAM007 l.297).
- **Single-row (004/005)**:
  - Returns the value with `STATUSTEXT` = the found key, trailing nulls stripped (004 l.484-506).
  - `le`/`lt` (005 `2000`): `READ GTEQ`, `STARTBR`, `READPREV`, plus one extra `READPREV` when the key found is greater than, or for `lt` equal to, the requested key.
  - Orphan FK rows (FF missing) are skipped by moving on to the next key (004 l.361-365).
  - `ex` returns 200 with the key in the status text and a CRLF body, or `204`.
- **Multi-row (007/008/009)**:
  - The 3.2 MB buffer is filled with rows.
  - Default format: `KKK` (3-digit key length), key, `VVVVVVV` (7-digit value length), value.
  - With `delim=c`: `key c value c …`.
  - `keysonly` format: `KKK` + key.
  - Response headers `zFAM-Rows` and `zFAM-LastKey`; the status text is the last key.
  - A buffer overflow gives `206 01-007` (partial result).
  - No rows gives 204.
  - `zFAM-RangeEnd` is a generic prefix stop: `FK-KEY(1:len) > RangeEnd(1:len)` (007 `3210`).
  - **Rows are filtered by the request `Content-Type`.** The default is `text`, which returns only `text` objects; a non-text Content-Type returns only `bits` objects (007 l.364-373).
- **Range delete (003)**:
  - Begins with `STARTBR GTEQ RangeBegin`.
  - In `Full` mode, a first key greater than Begin gives `204 02-003`, so the Begin key must exist.
  - The end test is `Full` (key > End) or `Generic` (prefix compare).
  - It **syncpoints every 10 deletes and restarts the browse**, so the operation is not atomic.
  - It stops at 1000 rows with `206 01-003`. If nothing was deleted it returns `204 03-003`.
  - It replicates the DELETE to the partner data centre.

## 3. Target design

### 3.1 Packages / Spring components
```
com.zfam.basic.web
  BasicModeController        @RestController for GET/POST/PUT/DELETE on /{p1}/.../{p6}/** (ZFAM002 1000/2000)
  BasicRequestParser         URI key extraction, 5-parm query parser, header binding (1100-1620)
  DelimDecoder               %XX → byte (ZFAMHEX.cpy); fallback '|'
  ZfamHeaders                constants for zFAM-* header names
  MultiRowBodyWriter         KKK/VVVVVVV, delim, keysonly formats (007/008/009 4000)
  LobStreamingResponse       StreamingResponseBody, chunked (3700-3720)
com.zfam.basic.service
  KeyValueService            create/read/update/delete, copy-on-write PUT, ECR, TTL, .LAT (002 3000-6900)
  BrowseService              single + multi-row, direction FWD/BACK, keysOnly, rangeEnd, buffer cap (004/005/007/008/009)
  RangeDeleteService         batch delete with 10-row commits and 1000-row cap (003)
  RowLockService             zFAM-Lock / LockID semantics, wait loop (3220-3280, 6020-6080)
  LobService                 append, 65535-segment limit, streaming read (7000-7800)
  KeyGenerationService       zFAM-UID / zFAM-Modulo (4700-4770); delegates to S3 UidGenerator + CounterService
  RetentionPolicy            ret-years / ret-days / ttl / zFAM-TTL clamping
  IndexHookPort / ReplicationPort   interfaces implemented by S2 / S4 (no-ops by default)
com.zfam.basic.repo
  KeyStoreRepository         JdbcClient: findByKey, findForUpdate (SELECT … FOR UPDATE), insert, update, delete, browse
  FileStoreRepository        segment insert/select/delete, streamed reads
com.zfam.common.error  (shared with S2/S3; S1 owns it)
  ZfamStatus                 140 entries generated from ZFAM090 STATUS-TABLE: (http, reason, programSuffix, template)
  ZfamException              (ZfamStatus, file, key, field, program)
  ZfamErrorResponder         @ControllerAdvice: writes status line "RR-PPP text", CRLF body, CSSL-equivalent log
```
Plain JDBC (`JdbcClient`) is used rather than JPA. The browse and segment streaming need explicit SQL and cursors, and `bytea` keys work best with hand-written queries.

### 3.2 PostgreSQL schema (replaces `FA##KEY` / `FA##FILE`)
```sql
CREATE TABLE zfam_key_store (
  instance_id     char(2)      NOT NULL,          -- '##' of FA##
  k               bytea        NOT NULL CHECK (octet_length(k) BETWEEN 1 AND 255),
  blob_id         bigint,                         -- FK-FF-KEY (NULL for ECR)
  ecr             boolean      NOT NULL DEFAULT false,
  object_type     varchar(4)   NOT NULL,          -- 'text' | 'bits'
  is_lob          boolean      NOT NULL DEFAULT false,
  segments        integer      NOT NULL,
  retention       integer      NOT NULL,
  retention_type  char(1)      NOT NULL,          -- 'Y' | 'D'
  lock_id         char(32), lock_at timestamptz, lock_seconds smallint,
  created_at      timestamptz  NOT NULL,          -- FK-ABS
  PRIMARY KEY (instance_id, k));
CREATE TABLE zfam_file_store (
  instance_id char(2) NOT NULL, blob_id bigint NOT NULL, segment integer NOT NULL,
  media_type varchar(56), retention integer, retention_type char(1), segments integer,
  last_access timestamptz NOT NULL,               -- FF-ABS (also used by .LAT and TTL)
  k bytea NOT NULL, data bytea NOT NULL CHECK (octet_length(data) <= 32000),
  PRIMARY KEY (instance_id, blob_id, segment));
CREATE SEQUENCE zfam_blob_id_seq;                 -- replaces ZUIDSTCK TOD + DCOUNTER
```
- Keeping 32,000-byte segments preserves LOB semantics. It also keeps each row well under the 1 GB `bytea` limit and lets reads stream. The 100 DDNAME datasets collapse into one table, optionally partitioned by `instance_id`.
- The key is `bytea`, so `ORDER BY k` is byte order. To get EBCDIC parity, an optional generated `k_ebcdic bytea` column with an index can drive the browse (see Q1).

### 3.3 Construct mapping
| Mainframe | Java/Postgres |
|---|---|
| `XCTL ZFAM00x` with `GET-COMMAREA` | `BrowseService.browse(BrowseRequest)`, a record of type, rows, delim, keysOnly, key |
| `XCTL ZFAM090` (`9998`) | `throw new ZfamException(ZfamStatus.S507_06_002, …)` |
| `LINK ZFAM011/031/041` + containers | `IndexHookPort.onInsert/onUpdate/onDelete(oldKey, oldRec, newKey, newRec)` (S2) |
| `READ UPDATE` / `REWRITE` / `UNLOCK` | `SELECT … FOR UPDATE` in a `@Transactional` method; commit or rollback |
| `STARTBR/READNEXT/READPREV` | `WHERE k >= ? ORDER BY k [DESC] LIMIT ?` (keyset pagination, fetch size 100) |
| `SYNCPOINT` / `SYNCPOINT ROLLBACK` | transaction commit/rollback (`TransactionTemplate` for 003's 10-row batches) |
| `HANDLE ABEND` → `400 09-002` | catch-all `@ExceptionHandler(RuntimeException)` that rolls back and returns `400 09-002` |
| `GETMAIN` 3.2 MB / `FREEMAIN` | `ByteArrayOutputStream` capped at 3,200,000 bytes; LOB reads stream instead |
| COMP-3 `FK-ABS`/`FF-ABS` (ms since 1900) | `timestamptz`; S4 converts the ABS epoch during migration |
| `SRVCONVERT` EBCDIC↔ASCII | Bytes stored exactly as received (no conversion). Text rows are converted EBCDIC→UTF-8 once at migration (S4). |
| `WEB SEND CHUNKYES` | `StreamingResponseBody` (Tomcat chunked) |
| `L8WAIT` loop | `Thread.sleep(intervalMs)` × 50 inside `RowLockService` (interval from S3 config) |
| `WRITEQ TD CSSL` | SLF4J logger `zfam.cssl` with structured fields (tranid → instance) |

## 4. Work packages (one PR each)

| ID | Title | Source | Est. (eng-days) | Depends on |
|---|---|---|---|---|
| S1-WP1 | Error catalog + responder | ZFAM090, HANDLE.cpy | 3 | S3 app skeleton WP |
| S1-WP2 | Key/file store schema + repositories | ZFAMFKC, ZFAMFFC | 4 | S1-WP1; S4 data-model review |
| S1-WP3 | Basic Mode request parsing | ZFAM002 1000–1620, ZFAMHEX | 4 | S1-WP1; S3 routing/auth WP |
| S1-WP4 | Single-key CRUD (non-LOB): POST/GET/PUT/DELETE, segmentation, TTL, copy-on-write PUT, ECR, `.LAT`, `ex` | ZFAM002 2000–6900 | 8 | S1-WP2, S1-WP3 |
| S1-WP5 | UID / modulo key generation | ZFAM002 4700–4770 | 2 | S1-WP4; S3 UID + counter WP |
| S1-WP6 | Row-level locking | ZFAM002 3120–3280, 6000–6080 | 4 | S1-WP4 |
| S1-WP7 | LOB append + chunked streaming GET | ZFAM002 1600/1610, 3700–3720, 7000–7800 | 6 | S1-WP4 |
| S1-WP8 | Single-row browse ge/gt/le/lt | ZFAM004, ZFAM005, ZFAM006 | 3 | S1-WP4 |
| S1-WP9 | Consolidated multi-row browse | ZFAM007, ZFAM008, ZFAM009 | 6 | S1-WP8 |
| S1-WP10 | Range DELETE | ZFAM003 | 3 | S1-WP4 |
| S1-WP11 | Column-index hook port | ZFAM002 4800/5800/6800/6900 | 2 | S1-WP4; S2 index WP |
| S1-WP12 | Replication hook port | ZFAM002 4500/5400/5500/6600/7600/8000–8300, ZFAM003 2000/7000 | 2 | S1-WP4, S1-WP10; S4 replication WP |
| S1-WP13 | Basic Mode parity suite | all | 5 | S1-WP4…WP12; S4 parity harness WP |
| | **Total** | | **52** | |

**Acceptance criteria per WP**
- **WP1**
  - `ZfamStatus` is generated from or checked against the full ZFAM090 table (140 entries), including the program-suffix dimension (e.g. `204 01-002` ≠ `204 01-004`).
  - Status text is byte-identical to the mainframe output: the `RR-PPP` prefix and the 64-byte message text.
  - Unknown entries map to `999 99-PPP`.
  - The 503 fallback path is covered by tests.
- **WP2**
  - Flyway migration creates the tables and sequence.
  - Repositories pass Testcontainers tests for byte-order browse in both directions, `FOR UPDATE` semantics, and 65535-segment metadata.
- **WP3**
  - Table-driven tests cover every parse branch in §2.1: the 7-slash rule, keys containing `/`, the 255-byte limit, the 5×10-byte parm truncation, non-numeric `rows` → 1, `delim=%7C`, retention clamps and precedence (header > query), and the 3.2 MB / 258 MB / 0-length limits.
- **WP4**
  - The example_basic_mode.md scenarios 1, 6, 7 and 8 reproduce exactly (status, text, body CRLF).
  - Duplicate POST → `409 02-002`. Missing key on PUT/GET/DELETE → `204 03-002 / 01-002 / 02-002`.
  - A concurrent GET during PUT never sees partial data.
  - `.LAT` updates `last_access`.
  - ECR round-trips.
- **WP5**
  - The `zFAM-UID` and `zFAM-Modulo` headers are returned.
  - The modulo wraps 1..NN, and redefining NN resets the counter. This is tested with concurrent POSTs.
- **WP6**
  - Lock acquire, wait, nowait, expiry and PUT-with-LockID all behave as in §2.2. Status headers and the `409 01-002 / 03-002` codes match.
- **WP7**
  - POST + 2×PUT append of a 550 MB synthetic object round-trips byte-exact with constant heap (streaming).
  - Exceeding 65535 segments → `413 02-002`.
- **WP8**
  - `ge/gt/le/lt` tests run against keys at the edges: the first or last key, a 255-byte key with carry, orphan FK rows.
  - The status text is the found key.
- **WP9**
  - A single `BrowseService` with `Direction` × `keysOnly` × `delim` replaces 007, 008 and 009.
  - Example scenarios 2–5 reproduce exactly, including `zFAM-Rows`, `zFAM-LastKey`, the status text, the `206 01-007` overflow, the Content-Type text/bits filter, and the RangeEnd prefix stop.
  - The quirks Q2 and Q3 are kept or fixed according to the decision recorded in the PR.
- **WP10**
  - `Full`/`Generic` modes work. The Begin key must exist in `Full` mode.
  - The cap gives `206 01-003`.
  - A crash after N batches leaves N×10 rows deleted, which matches the mainframe.
- **WP11 / WP12**
  - The ports are called with the same before/after images and in the same order as the CICS LINK/CONVERSE calls.
  - For active/standby, replication is called *after* the client response; for active/active, *before* it (l.2318–2337).
  - The default no-op beans keep S1 deployable on its own.
- **WP13**
  - The S4 harness replays recorded mainframe request/response pairs for every Basic Mode code path.
  - Status line, headers and body are diffed. Zero unexplained diffs is required to pass.

## 5. Interfaces with other segments

**S1 needs from S3**
- The Spring Boot skeleton and the `FA##` → `instance_id` resolution, i.e. the URIMAP equivalent: path prefix → instance + mode.
- The Basic Mode security decision from ZFAM001/FAxxSD. S1 assumes the request has already been authorised when it reaches the controller.
- `UidGenerator` (ZUID001, 32-character PLAIN format).
- `CounterService.next(name, min, max, wrap)` plus redefine (named counters).
- The L8WAIT interval config.
- The TTL expiration job (ZFAM000). It reads `retention`, `retention_type`, `last_access` and `created_at` from S1's tables, and must apply the FF-side retention (see Q4).

**S1 needs from S2**
- `IndexHookPort` implementation (ZFAM011 insert, ZFAM031 update, ZFAM041 delete), invoked only when the instance has a FAxxFD definition (the `ZFAM-FAXXFD` container exists).

**S1 needs from S4**
- `ReplicationPort` implementation (`/replicate`, `/deplicate`, `/datastore` path conventions, the `FA##DC` partner URL).
- The VSAM → Postgres loader for FK/FF, including EBCDIC→UTF-8 conversion of `text` rows only, ABS → timestamptz, and TOD+NC → `blob_id`.
- The parity harness.

**S1 exposes**
- `ZfamStatus` / `ZfamException` / `ZfamErrorResponder` (common error contract used by S2 and S3).
- `KeyStoreRepository` / `FileStoreRepository` (used by S3 TTL and S4 migration and replication).
- `KeyValueService` (used by S4's replication receiver to apply replicated writes).

## 6. Risks and quirks to preserve

1. **Collation (high).** VSAM browses in EBCDIC byte order. Browsing in ASCII/UTF-8 order changes the results of `ge/gt/le/lt`, `rows`, `RangeEnd` and range DELETE whenever keys mix case, digits or punctuation. Needs a decision (Q1).
2. **LOB size and streaming (high).** The 258 MB body limit and 2 GB objects require streaming receive and send, servlet/Tomcat `maxPostSize` tuning, and Postgres `work_mem`/TOAST sizing. Non-streaming code will run out of memory.
3. **Text conversion (high).** The text/bits decision is made from Content-Type *at write time*. Migrated text rows must be converted from EBCDIC exactly once, and `bits` rows must never be converted. A wrong `FK-OBJECT` value corrupts data.
4. **Status text as a data channel.** Clients read keys from the HTTP reason phrase (browse, `ex`). HTTP/2 has no reason phrase, and Tomcat drops custom reason phrases by default. The service must run HTTP/1.1 with a custom reason enabled, and add `zFAM-LastKey`/`zFAM-Key` headers as a fallback.
5. **Undocumented features that clients may use:** ECR, row locking, `zFAM-Type`, `ret-years/ret-days`, `.LAT`, and the Content-Type filter on multi-row.
6. **Non-atomic range delete and copy-on-write PUT.** These must keep their externally visible behaviour (partial deletes, readers never seeing torn values). Postgres transactions make the PUT atomic, which is acceptable.
7. **Error-path fidelity.** The same reason code means different things in different programs, so the program suffix must travel with every `ZfamException`.
8. **`keysonly` ignores direction (Q2)** and `eq,rows=N` is silently a single read. Clients may depend on both.

## 7. Open questions
- **Q1.** Browse order: keep EBCDIC order (generated `k_ebcdic` column) or switch to byte/ASCII order and announce the change to clients? This blocks WP2 and WP8–10.
- **Q2.** ZFAM009 handles `le/lt,keysonly` as a *forward* browse. Preserve that as a bug-for-bug quirk, or fix it?
- **Q3.** Should the multi-row Content-Type filter (text vs bits) be kept? It is invisible to most clients and probably surprising.
- **Q4.** `1313-TTL` sets only `FF-RETENTION`. `FK-RETENTION` keeps the default of 7 years (l.1025–1034), while `ret-days` and `zFAM-TTL` set both. Which field does ZFAM000 expire on? This affects WP4 and S3.
- **Q5.** Usage.md says the UID/modulo key is returned in the status text; the code writes `zFAM-UID`/`zFAM-Modulo` headers. Which do clients actually use?
- **Q6.** `http_response_codes.md` text for `400 11-002` says "Begin is less than End", but the code rejects Begin **greater than** End. Treat the code as authoritative?
- **Q7.** Are CFDT/shared-data-table file stores (ZFAM002 header comment) used anywhere? If so, latency expectations may require a cache in front of Postgres.
- **Q8.** `GET ?ttl` sets `GET-CA-TTL`, but no consumer exists in 004–009. Drop it?
