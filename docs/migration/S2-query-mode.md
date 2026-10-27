# S2 — Query Mode / zQL engine + column indexes: migration plan

Segment: **S2** (`query-mode`). Target stack (fixed by the coordinator): Java 17, Spring Boot 3, PostgreSQL, Spring Security, Maven, JUnit 5 + Testcontainers.
The REST contract has to stay wire-compatible: `?zQL,...` query strings, zQL bodies, `zFAM-*` headers, and the status/reason codes in `http_response_codes.md`.

Line numbers refer to `master` with CRLF stripped.

---

## 1. Inventory

### 1.1 Programs

| Artifact | LOC | Role | CICS / VSAM / RACF APIs |
|---|---|---|---|
| `Source/ZFAM010.asm` | 1734 | Query Mode **POST / INSERT**. Reads the parser array and FD containers, builds the fixed-layout logical record, and writes three things in order: the FAxxKEY record (keyed by primary-key value), the FAxxFILE segment(s) (32,000 bytes each, keyed by internal key + segment), and one FAxxCInn record per non-blank secondary field. Handles `zFAM-UID` / `zFAM-Concat` (composite key) and TTL, then calls the replication hook. Paragraphs: `SY_0000`–`SY_0300`, `FK_0010`–`FK_0100`, `FF_0010`–`FF_0100`, `CI_0010` (l.1079), `HH_0010`, `PK_0010`–`PK_9000`, `ZR_0010`–`ZR_0099`. | GET CONTAINER, GETMAIN, INQUIRE FILE (key length), GET COUNTER (named counter → internal key NC), ASKTIME + STCKE (TOD → internal key IDN), DOCUMENT CREATE/RETRIEVE (FAxxDD data-store name, FAxxDC replication), WRITE FILE ×3, WEB READ HTTPHEADER, LINK ZUID001, LINK ZFAM102, WEB SEND, XCTL ZFAM090 |
| `Source/ZFAM020.asm` | 1477 | Query Mode **GET / SELECT by primary key**. Returns one row. Reads FAxxKEY and then FAxxFILE, walks the parser array segment by segment (`SY_0150`–`SY_0270`, with spanned-field handling in `SY_0200`–`SY_0220`) and renders FIXED/JSON/XML/DELIM output (`RJ_0010`–`RJ_0062`). `WITH(CR)` becomes `READ ... UPDATE` (`FK_00CR`, l.945) and `WITH(UR)` a plain READ. The `SY_0400` "secondary CI section" is an empty stub. | GET CONTAINER, WEB RECEIVE (to get the media type only), GETMAIN, READ FILE (± UPDATE), WEB WRITE HTTPHEADER, WEB SEND, ENTER TRACENUM, XCTL ZFAM090 |
| `Source/ZFAM022.asm` | 2379 | Query Mode **GET / SELECT by secondary CI**. The first secondary WHERE predicate drives `STARTBR GTEQ` and then `READNEXT` on FAxxCInn (`SY_0080`–`SY_0096`). Supports operators `=`, `>`, `+`(>=) and a `*` prefix wildcard (`SY_0041`, `SY_0078`). Every other WHERE field is applied as a filter against the primary record (`SY_0400`–). Stops at `ROWS` (`SY_0090`, l.833). Response is sent **chunked** (`CHUNKYES`/`CHUNKEND`, l.1658–1781). Returns 206 when the response buffer exceeds its maximum (`SY_0920`). Filter values over 256 bytes get 412 (`SY_0040`). A CI field longer than 56 gets 412 (`SY_0070`). | as ZFAM020, plus STARTBR/READNEXT, FREEMAIN, DELETE (container), WEB READ HTTPHEADER (TE) |
| `Source/ZFAM030.asm` | 1269 | Query Mode **PUT / UPDATE**. The primary key is required. Reads FAxxKEY, then for each segment reads FAxxFILE and overlays the updated fields, padding C with spaces and N with zeros (`SY_0185`–`SY_0200`). REWRITEs each segment (`FF_0030`). For each updated secondary field it **writes the new CI first** and deletes the old CI only if the value changed (`SY_0210`/`SY_0220`, l.652–695). TTL is handled in `TL_0010`/`TL_0020`. Replication hook at `ZR_0010`. | GET CONTAINER, READ FILE UPDATE, REWRITE, WRITE/DELETE FILE (CI), ASKTIME, DOCUMENT (DC), LINK ZFAM102, WEB SEND |
| `Source/ZFAM040.asm` | 1184 | Query Mode **DELETE** (by primary key only). Builds its own parser array from **every** FAxxFD entry with ID>001 (`SY_0012`). Reads the record and deletes each FAxxCInn entry (`SY_0300`/`SY_0310`). Then deletes FAxxKEY, and deletes FAxxFILE with `GENERIC` (all segments, l.773). Replication hook. | GETMAIN, GET CONTAINER, READ FILE, DELETE FILE (CI, KEY, FILE GENERIC), DOCUMENT (DC), LINK ZFAM102, WEB SEND |
| `Source/ZFAM011.cbl` | 328 | **Basic Mode** POST on a table that has a schema. ZFAM002 LINKs to it (`ZFAM002.cbl` l.2708). For each FD entry with `FD-INDEX > 1` it writes a CI record (`3200-WRITE-CI`), **skipping values that are blank or all nulls**. | ASSIGN CHANNEL, GET CONTAINER (`ZFAM-FAXXFD`, `ZFAM-NEW-REC`, `ZFAM-NEW-KEY`), WRITE FILE, WRITEQ TD (CSSL, unused path) |
| `Source/ZFAM031.cbl` | 434 | **Basic Mode** PUT on a table with a schema (LINKed from ZFAM002 l.3548, l.3603). `ZFAM-PROCESS`=`DELETE` removes the old CI using `ZFAM-OLD-REC`/`OLD-KEY`; `INSERT` writes the new CI (`5200-WRITE-CI`) **without** the blank check. | as ZFAM011, plus DELETE FILE |
| `Source/ZFAM041.asm` | 332 | **Basic Mode** DELETE on a table with a schema (LINKed from ZFAM002 l.3042). Deletes every CI for the old record. The `.asm` extension is misleading: the file is **COBOL**. | ASSIGN CHANNEL, GET CONTAINER, DELETE FILE |
| `Source/ZFAM001.asm` (S3-owned file) | l.836–2913 (~2,100 of 3,778) | The **zQL parser and Query Mode security** live here, not in ZFAM010–040. `QM_0100` INSERT, `QM_0200` SELECT, `QM_0300` UPDATE and `QM_0400` DELETE build the **parser array** (`PA_DSECT` l.293) and one container per field. `QS_0010`–`QS_0310` do Query Mode security including the field-level check. `QS_0400`–`QS_0489` choose the program. `QS_0500` does the XCTL. **S2 owns re-implementing this logic. S3 owns the HTTP entry point that calls it.** | WEB RECEIVE (SRVCONVERT, 3.2 MB max), GETMAIN, PUT CONTAINER, WEB READ HTTPHEADER (`zFAM-Stream`), XCTL |

### 1.2 Copybooks / DSECT macros / templates / JCL

| Artifact | LOC | Content |
|---|---|---|
| `Source/ZFAMCIC.cpy` | 13 | COBOL CI record. `CI-KEY` is `CI-FIELD X(56)` + `CI-ID X(6)` + `CI-NC X(2)` (64-byte key), followed by `CI-DS X(4)` (data-store DD name, `'FILE'` or `DS01`–`DS99`). |
| `Source/ZFAMCIA.mac` | 16 | Same layout as an HLASM DSECT (`CI_REC`, `E_CI`=68). |
| `Source/ZFAMDFA.mac` | 25 | FAxxFILE segment. 16-byte key (`DF_IDN` 6 + `DF_NC` 2 + `DF_SEG` 2 + `DF_SUFX` 2 + null 4), `DF_ABS` PL8, `DF_TTL` PL4, `DF_SEGS`, `DF_TYPE` (D/Y), `DF_K_KEY` CL255, `DF_MEDIA` CL56, `DF_DATA` CL32000. |
| `Source/ZFAMDKA.mac`, `ZFAMFKA.mac` | 34 / 33 | FAxxKEY record (DSECT and working copy). `DK_KEY` CL255, `DK_ECR`, internal key `DK_F_IDN`+`DK_F_NC`, `DK_OBJ` text/bits, `DK_DD`, `DK_UID` (lock), `DK_ABS`, `DK_LOCK`, `DK_LOB`, `DK_SEGS`, `DK_TTL` PL4, `DK_TTL_T`. **Shared with S1.** |
| `Source/FA##FD.txt`, `JCL/FA##FD.jcl` | 10 / 41 | Field-definition doc template. Each line is a fixed 66 characters (`ID=nnn,Col=nnnnnnn,Len=nnnnnn,Type=C\|N,Sec=nn,Name=<16>\|`) followed by CRLF. The JCL loads it with IEBGENER and runs `DEFINE DOCTEMPLATE ... APPENDCRLF(YES) TYPE(EBCDIC)`. |
| `Source/FA##SD.txt`, `JCL/FA##SD.jcl` | 13 / 44 | Security doc template. Two header lines (`Basic Mode Read Only: yea\|nay`, `Query Mode Read Only:`), then 56-character `User=xxxxxxxx,Read  \|Write \|Delete,<33 flags>` lines. Flag 0 (col 22) is Basic Mode. Flags 1–32 (cols 23–54) match `Sec=01..32`. |
| `Source/FA##DC.txt` | 1 | Replication target (`type: AS` + URL). **S4 owns this.** Listed only because ZFAM010/030/040 read it. |
| `JCL/DEFCI.jcl`, `Source/ZFAMCI.idcams`, `Source/CSDZFAMC.rdo` | 63 / 20 / 10 | One KSDS per secondary index: `FAxxCInn`, `KEYS(64 0)`, `RECORDSIZE(68 68)`, `LOG(UNDO)`, RLS, `READINTEG(UNCOMMITTED)`. `nn` must equal the FD `ID=`. |
| `howto_define_query_mode.md`, `example_query_mode.md`, `Usage.md` §Query Mode | 54 / 96 / ~85 | User-facing spec. It is **incomplete compared with the code** (see §5). |

**Total S2 LOC:** about 9,630 in the dedicated files, plus about 2,100 lines of zQL/security logic inside ZFAM001.

### 1.3 Runtime flow today

```
HTTP ─▶ ZFAM001 ─(query string starts "zQL")─▶ QM_0010 parse ─▶ QS_0010 security ─▶ QS_0400 choose:
   POST ▶ XCTL ZFAM010   GET ▶ ZFAM020 (no secondary WHERE) | ZFAM022 (secondary WHERE)
   PUT  ▶ XCTL ZFAM030   DELETE ▶ ZFAM040
Basic Mode on a table with FAxxFD: ZFAM002 ─LINK▶ ZFAM011 (POST) | ZFAM031 (PUT, twice: DELETE old + INSERT new) | ZFAM041 (DELETE)
```
All data moves on channel `ZFAM-CHANNEL`. The containers are `ZFAM-ARRAY` (parser array), `ZFAM-OPTIONS` (options table `O_TABLE`), `ZFAM-KEY`, `ZFAM-TTL`, `ZFAM-FAXXFD`, `ZFAM-MEDIA`, and one container **named after each field** holding its raw value. Basic Mode also uses `ZFAM-NEW-REC`/`OLD-REC` (record pointer), `ZFAM-NEW-KEY`/`OLD-KEY` (8-byte internal key) and `ZFAM-PROCESS`.

Parser-array entry (`PA_DSECT`, 32 bytes, at most 256 entries = 8,192 bytes):

| Field | Format | Meaning |
|---|---|---|
| `P_ID` | PL2 | Index ID (0 = none, 1 = primary, 2–99 = secondary CI). Set to 999 once processed or ineligible. |
| `P_SEC` | PL2 | Security slot, 1–32 |
| `P_COL` | PL4 | Column offset |
| `P_LEN` | PL4 | Length |
| `P_TYPE` | — | `C` or `N` |
| `P_WHERE` | — | `x'00'` = INSERT/UPDATE field, `N` = SELECT field, `=`/`>`/`+` = WHERE operator |
| `P_SEG` | H | Segment |
| `P_NAME` | CL16 | Field name |

---

## 2. Target design

### 2.1 Packages (module `zfam-query`, base `com.zfam.query`)

| Package | Classes | Replaces |
|---|---|---|
| `zql` | `ZqlParser` (hand-written recursive descent that keeps the byte-level grammar below), `ZqlStatement` (sealed): `Select(fields, predicates, isolation, options)`, `Insert(assignments, ttlDays)`, `Update(assignments, predicates, ttlDays)`, `Delete(primaryKeyPredicate)`. Also `FieldRef`, `Assignment(name, rawValue)`, `Predicate(field, Op{EQ,GT,GE}, rawValue)`, `SelectOptions(format, distinct, mode, sort, rows)`, `Isolation{UR,CR}`, `ZqlSyntaxException(status, reason, field)` | ZFAM001 `QM_0100`–`QM_0510`, the parser array, and the per-field containers |
| `schema` | `FieldDefinition(id, column, length, type, secSlot, name)` record, `ColumnType{C,N}`, `TableSchema` (primary, secondaries, `byName`, logical record length = max(col+len−1)), `FieldDefinitionParser` (66-character FD format, used for import and validation), `SchemaRepository` (cached, keyed by instance id) | FAxxFD doc template, `FD_DSECT`, `SY_0030`–`SY_0050` in ZFAM010 |
| `record` | `FixedRecordCodec`: `get(byte[] rec, FieldDefinition)` and `put(rec, field, raw)`. C values are right-padded with spaces and N values left-padded with zeros. Overlapping fields are allowed. `SegmentMath` exists **only** for migration and parity (32,000-byte segments, 1-based column). | `SY_0170`–`SY_0220` segment logic (repeated in 010/020/022/030/040) |
| `index` | `ColumnIndexRepository` (JDBC), `SecondaryIndexMaintainer` with `onInsert(schema, internalKey, newRec, skipBlank)`, `onUpdate(schema, internalKey, oldRec, newRec, changedFields)`, `onDelete(schema, internalKey, oldRec)` | ZFAM011/031/041, `CI_0010` in ZFAM010, `SY_0210`/`CI_0010`/`CI_0020` in ZFAM030, `SY_0300` in ZFAM040 |
| `security` | `FieldLevelAuthorizer.check(principal, HttpMethod, Collection<FieldDefinition>)` → 401 `14-001` | `QS_0220`–`QS_0310` |
| `service` | `QueryInsertService` (010), `PrimaryKeySelectService` (020), `SecondaryIndexSelectService` (022), `QueryUpdateService` (030), `QueryDeleteService` (040). Each method is `@Transactional`; one CICS task UOW maps to one DB transaction. **Exception: `SecondaryIndexSelectService`** returns a `StreamingResponseBody`, and its callback runs after the handler has returned. The callback therefore opens its own read-only transaction (`TransactionTemplate`) and holds the connection and JDBC cursor until it finishes or fails, then closes them in `finally`. Parse, authorization and validation errors are raised **before** the body is returned, so they still become normal status codes. | ZFAM010/020/022/030/040 |
| `web` | `QueryModeController` (Spring `@Component`, not a separate URL mapping) with `ResponseEntity<?> handle(ZfamRequest ctx)`. It parses, authorizes, routes using the `QS_0400` rules, and returns a `ResponseEntity` (plain, or `StreamingResponseBody` for chunked 022 output). | ZFAM001 `QS_0400`–`QS_0500` XCTL routing |
| `format` | `ResultFormatter` strategy: `FixedFormatter`, `JsonFormatter`, `XmlFormatter`, `DelimitedFormatter`, plus `FormatResolver`. Content-Type of the request wins over `OPTIONS(FORMAT=)` (`ZFAM020` `SY_0011`). | `RJ_*` / XML / pipe routines in 020/022 |
| `spi` | `QueryReplicationHook` (§4) and `QueryAuditTrace` (replaces `ENTER TRACENUM(46)`, done with Micrometer/SLF4J) | `ZR_0010`–`ZR_0099`, `TR_0010` |

**Why there is no separate `@RestController`:** zQL query strings such as `?zQL,SELECT,(FIELDS(a)),...` are not `key=value` pairs, so Spring `params=` matching cannot select them. S3's front controller already has to tell Basic Mode from Query Mode, exactly as ZFAM001 does at l.539–544. It delegates to `QueryModeController.handle`.

### 2.2 zQL grammar (spec to implement in S2-WP2)

```
query-get    := "zQL" "," select                                   (URI query string, ≤ 8192 bytes, else 414 01-001)
query-delete := "zQL" "," "DELETE" "," "(" "WHERE" "(" pk-name "=" value ")" ")"      (exactly one predicate, must be primary key, else 400 09-001)
body-post    := "INSERT" [ "," clause-i { "," clause-i } ]          clause-i := "(" ( fields-assign | ttl ) ")"   (each at most once)
body-put     := "UPDATE" "," clause-u { "," clause-u }               clause-u := "(" ( fields-assign | ttl | where ) ")"
select       := "SELECT" "," clause-s { "," clause-s }               clause-s := "(" ( fields-list | where | with | options ) ")"
fields-assign:= "FIELDS" "(" name "=" value ")" { "," "(" name "=" value ")" }
fields-list  := "FIELDS" "(" name ")" { "," "(" name ")" }
where        := "WHERE" "(" pred ")" { ( "," | "AND" ) "(" pred ")" }   pred := name ( "=" | ">" | "+" ) value
with         := "WITH" "(" ( "UR" | "CR" ) ")"
options      := "OPTIONS" "(" opt { "," opt } ")"   opt := FORMAT=(FIXED|XML|JSON|DELIMITER) | DISTINCT=(YES|NO) | MODE=(ONLINE|OFFLINE) | SORT=name | ROWS=digits(1-5)
ttl          := "TTL" "(" digit{1,5} ")"
name         := 1..16 bytes, matched case-sensitively against FAxxFD  (unknown → 412 01-001 for INSERT/UPDATE, 400 xx-001 for SELECT)
value        := any bytes up to the next ")"  (no quoting, no escaping; embedded spaces/commas kept; max 64000 bytes)
```
Parsing notes:
- Commands and keywords are compared **after `OC x'40'`**, so they are case-insensitive: INSERT, SELECT, FIELDS, WHERE, WITH, OPTIONS, TTL, UR/CR.
- `AND` and the OPTIONS parameter names are compared **without** that step, so they are case-sensitive and must be upper-case (`QM_0247`, `QM_0251`).
- Syntax errors map by verb: INSERT → 400 `06-001`, SELECT → `07-001`, UPDATE → `08-001` (see Q15), DELETE → `09-001`.
- Wrong verb for the HTTP method → 405 `01-001` (POST), `02-001` (GET), `03-001` (PUT) or `04-001` (DELETE), from `ER_40501`–`ER_40504`.
- More than 256 fields → 414 `03-001`.
- Defaults (`QM_0200`): FORMAT=FIXED, DISTINCT=NO, MODE=ONLINE, ROWS=0 (meaning all rows), SORT blank, WITH=UR.

### 2.3 PostgreSQL schema (S2-owned tables; key/file tables owned by S1)

```sql
CREATE TABLE zfam_field_def (            -- replaces FAxxFD doc template
  instance_id  varchar(4)  NOT NULL,     -- 'FA01'
  field_name   varchar(16) NOT NULL,     -- case-sensitive
  index_id     smallint    NOT NULL CHECK (index_id BETWEEN 0 AND 99),  -- 0 none, 1 primary, 2-99 secondary
  col_offset   integer     NOT NULL CHECK (col_offset >= 1),            -- 1-based
  length       integer     NOT NULL,     -- C≤262144 (≤56 if indexed), N≤31
  col_type     char(1)     NOT NULL CHECK (col_type IN ('C','N')),
  sec_slot     smallint    NOT NULL CHECK (sec_slot BETWEEN 1 AND 32),
  ordinal      smallint    NOT NULL,     -- line order of the template (primary first)
  PRIMARY KEY (instance_id, field_name));
CREATE UNIQUE INDEX ON zfam_field_def(instance_id, index_id) WHERE index_id > 0;

CREATE TABLE zfam_column_index (         -- replaces every FAxxCInn KSDS
  instance_id  varchar(4)  NOT NULL,
  index_id     smallint    NOT NULL,     -- nn of FAxxCInn
  field_value  bytea       NOT NULL,     -- exactly the field's Len bytes (≤56) copied from the record slice; no padding up to 56
  internal_key bytea       NOT NULL,     -- 8 bytes IDN+NC (S1/S3 may expose as bigint – see §4)
  data_store   char(4)     NOT NULL DEFAULT 'FILE',
  PRIMARY KEY (instance_id, index_id, field_value, internal_key),
  FOREIGN KEY (instance_id, internal_key) REFERENCES zfam_file_header(instance_id, internal_key) ON DELETE CASCADE);
```
- `field_value` is stored as `bytea`, or as `text COLLATE "C"`, so that `>` / `>=` / `STARTBR GTEQ` run as a btree range scan with byte ordering.
- **One canonical key encoding.** In the legacy 56-byte CI key, the bytes after the field length are `LOW-VALUES` (x'00'): ZFAM011/031 `MOVE LOW-VALUES TO CI-KEY` and ZFAM030 does `XC CI_FIELD,CI_FIELD`. ZFAM022 only ever compares `CA_F_LEN` bytes. So the target stores just the `Len`-byte slice. S4's import must cut each copied KSDS key to the field's `Len` (dropping the x'00' suffix); otherwise new writes and deletes would not match copied rows. Rebuilding with `SecondaryIndexMaintainer.rebuild` produces the same encoding by construction. WP12 includes a test that updates and queries a copied row.
- The `ON DELETE CASCADE` is new behaviour. It fixes orphaned CI rows left after TTL expiry (ZFAM000 never touches CI files). The FK target name depends on S1.
- FAxxSD field flags: S3 owns the `zfam_security_user` table (instance, userid, access_type, flags bit(33)). S2 reads flags 1–32 through the interface in §4.

### 2.4 Construct mapping

| Mainframe | Java/PostgreSQL |
|---|---|
| XCTL ZFAM0x0 (from ZFAM001) | `QueryModeController` calls the matching service method |
| LINK ZFAM011/031/041 (from ZFAM002) | S1's `BasicModeService` calls `SecondaryIndexMaintainer` directly, in the same transaction |
| Channel + containers (`ZFAM-ARRAY`, per-field) | `ZqlStatement` AST passed as a Java object; per-field values held in `Assignment`/`Predicate` |
| `DOCUMENT CREATE/RETRIEVE` FAxxFD / FAxxSD / FAxxDD | `SchemaRepository` / S3 `SecurityDefinitionRepository` / S1 data-store resolver, cached with Caffeine and evicted on admin update |
| `READ FILE` (FAxxKEY) | `SELECT ... FROM zfam_key WHERE instance_id=? AND key=?` |
| `READ ... UPDATE` for WITH(CR) | `... FOR UPDATE` |
| WITH(UR) | plain `SELECT` (PostgreSQL cannot read uncommitted data; READ COMMITTED is the closest) |
| `WRITE` / `REWRITE` / `DELETE` (incl. `GENERIC`) | `INSERT` / `UPDATE` / `DELETE`; `DUPREC`(14) → 409; `NOTFND` → 204; `NOSPACE`/`NOTOPEN`/`DISABLED` → 507 through `DataAccessException` translation |
| `STARTBR GTEQ` + `READNEXT` | `SELECT internal_key, field_value FROM zfam_column_index WHERE instance_id=? AND index_id=? AND field_value >= ? ORDER BY field_value, internal_key`, read with a JDBC cursor (`fetchSize`) and stopped early on mismatch or `ROWS` |
| Wildcard `*` (`SY_0078`: nulls after `*`, compare prefix) | `field_value >= prefix AND substring(field_value,1,len(prefix)) = prefix`, early exit |
| Packed decimal PL2/PL4/PL8, zoned TTL | `int`/`long`; TTL becomes `int days`; `DF_ABS` becomes `timestamptz` |
| EBCDIC record bytes + `SRVCONVERT` | UTF-8 `byte[]` record. **Field lengths stay byte counts** (see §5.1). |
| `GET COUNTER` + `STCKE` internal key | S3 `InternalKeyGenerator.next()` (PostgreSQL sequence or UUIDv7) |
| `LINK ZUID001` (zFAM-UID) | S3 `UidService.newUid(PLAIN)` |
| `WEB SEND CHUNKYES/CHUNKEND` | `StreamingResponseBody` (Transfer-Encoding: chunked) |
| `XCTL ZFAM090` (error log + status) | throw `ZfamException(status, reason, program, field)`; S1/S3 `@ControllerAdvice` renders the status text |
| `ENTER TRACENUM(46)`, `WRITEQ TD CSSL` | SLF4J DEBUG / WARN + Micrometer counters |

---

## 3. Work packages

Estimates are engineer-days for a human team. Each WP is one PR with unit tests, and Testcontainers tests where it touches the DB.

| ID | Title | Source | Est. | Depends on |
|---|---|---|---|---|
| S2-WP1 | Schema model, `zfam_field_def`, FD template importer | FA##FD.txt/.jcl, `FD_DSECT`, howto_define_query_mode.md | 3 | S3-WP0 (project skeleton / Flyway baseline) |
| S2-WP2 | zQL grammar, `ZqlParser`, AST, error mapping | ZFAM001 `QM_0100`–`QM_0510` | 6 | WP1 |
| S2-WP3 | `FixedRecordCodec` + segment math | 010 `SY_0170`–`SY_0195`, 020/030/040 `SY_0170`–`SY_0220` | 3 | WP1 |
| S2-WP4 | `zfam_column_index` + `SecondaryIndexMaintainer` | ZFAM011/031/041, ZFAMCIC/ZFAMCIA, DEFCI.jcl, ZFAMCI.idcams | 4 | WP1, WP3, S1 key/file-store WP |
| S2-WP5 | Field-level authorizer | ZFAM001 `QS_0010`–`QS_0310`, FA##SD | 2 | WP2, S3 auth/security-definition WP |
| S2-WP6 | Result formatters + format negotiation | 020 `SY_0011`, `RJ_*`; 022 equivalents | 3 | WP3 |
| S2-WP7 | `QueryModeController` + INSERT + replication SPI | ZFAM010, ZFAM001 `QS_0400`–`QS_0500` | 5 | WP2–WP5, S1 key/file-store WP, S3 front controller / UID / internal-key WP |
| S2-WP8 | SELECT by primary key | ZFAM020 | 3 | WP6, WP7 |
| S2-WP9 | SELECT by secondary index (streaming) | ZFAM022 | 6 | WP4, WP6, WP8 |
| S2-WP10 | UPDATE | ZFAM030 | 4 | WP4, WP7 |
| S2-WP11 | DELETE | ZFAM040 | 2 | WP4, WP7 |
| S2-WP12 | Query Mode parity suite | example_query_mode.md, http_response_codes.md | 4 | WP7–WP11, S4 parity harness WP |
| | **Total** | | **45** | |

Acceptance criteria:

- **S2-WP1** — Java records `FieldDefinition`, `TableSchema`, `ColumnType`; Flyway migration for `zfam_field_def`; `FieldDefinitionParser`, which reads the exact 66-character line layout (`ID=`/`Col=`/`Len=`/`Type=`/`Sec=`/`Name=`, `|` terminator) and loads it into the DB; cached `SchemaRepository`.
  - *Accepts* `Source/FA##FD.txt` and both examples in howto_define_query_mode.md.
  - *Enforces* the documented rules: first line is ID=001 at Col=1, IDs unique, names unique, C indexed length ≤56, N length ≤31, Sec in 1–32.
  - *Rejects* a template that breaks a rule, with a clear message.
  - Overlapping columns are allowed.
  - A missing schema returns what ZFAM001 `QM_0010` actually returns: `ER_40505`, i.e. **405 `05-001`**. http_response_codes.md says 403 `01-001`, which does not match the code (OQ-8).

- **S2-WP2** — Implement the §2.2 grammar exactly, keeping the quirks in §5.
  - Status and reason codes are byte-identical to ZFAM001 for every `ER_4xxxx` branch reachable from `QM_*`. On the wire, ZFAM090 renders `SSS RR-PPP`, where PPP is the program number (`001`, `010`, `020` …).
  - Golden tests: at least one case per `QM_*` error branch (about 60), plus the 7 examples in example_query_mode.md.
  - Fuzz test: the parser never throws an unchecked exception.

- **S2-WP3** — Fixed-layout logical record. C values are padded right with spaces and N values left with `'0'`, matching `SY_0180`/`SY_0190` in ZFAM010.
  - A value longer than the field is truncated. Both ZFAM010 and ZFAM030 use `EX MVC` with the field length, so this must be confirmed (OQ-3).
  - The record length is computed from the schema.
  - Property tests compare `SegmentMath` with the `SY_0180` worked examples (column 50 and column 64,075).

- **S2-WP4** — One maintainer that implements three different legacy behaviours, chosen by flag:
  - (a) ZFAM010/ZFAM011 do not write a CI row for blank or null values.
  - (b) ZFAM031 INSERT writes blank values too.
  - (c) ZFAM030 writes the new row before deleting the old one, and skips the delete when the value is unchanged. The target **compares the old and new keys first and does nothing when they match**. Unlike a VSAM WRITE that returns DUPREC and is ignored, a PostgreSQL insert of the existing row would violate the primary key and roll back the whole update. Inserts use `ON CONFLICT DO NOTHING` so that re-indexing is idempotent.

  Basic Mode POST/PUT/DELETE on a table with a schema keeps the CI table correct, in the same transaction as S1's writes. A unit test exists per legacy behaviour; whether to keep the inconsistency is OQ-2.

- **S2-WP5** — GET needs `Read`, POST/PUT need `Write`, DELETE needs `Delete`. **Every** field in the statement is checked, including WHERE fields and the primary key on DELETE: `flags[secSlot]` must be `x`/`X`, otherwise 401 `14-001`.
  - HTTP with FAxxSD present: GET is allowed only when `Query Mode Read Only: yea`; anything else gets 401 `11-001`/`12-001`.
  - Legacy behaviour: requests with the `/replicate` prefix skip **all** security (`QS_0010`). The target does **not** trust the path. The field check is skipped only for a principal that S3 has authenticated as a replication peer (`ROLE_ZFAM_REPLICATION`, via mTLS or a service account). A `/replicate` request without that role is checked like any other request.
  - Legacy behaviour: with no FAxxSD, anyone has full access, including anonymous writes over HTTP. The target puts this behind `zfam.security.allow-unsecured-instances` (default `false`; `true` only in dev or test profiles). With the flag off, an instance with no security definition returns 401 for writes (OQ-9).
  - The decision table in howto_define_security.md "Query Mode" is fully covered by tests.

- **S2-WP6** — Request Content-Type `text/plain` | `*json` | `*xml` | `text/delimited` takes priority over `OPTIONS(FORMAT=)`.
  - FIXED: fields concatenated with their padding.
  - JSON: `[{ "k":"v", "n":040 }]`. Numeric values are emitted **unquoted with leading zeros**, which is not valid JSON but is the wire format (example_query_mode.md #5).
  - XML and pipe-delimited outputs are byte-identical to the mainframe captures.
  - The primary key is always output first (`O_P_*`).

- **S2-WP7** — Routing (`QS_0400`):
  - POST → insert.
  - GET → by-primary unless any WHERE field has id ≥ 2, in which case by-secondary.
  - PUT → update.
  - DELETE → delete.

  INSERT writes the key, file and CI rows atomically:
  - Duplicate key → 409 `01-010`.
  - `zFAM-UID` / `zFAM-Concat` rules from ZFAM010 `PK_0010`–`PK_1000` → 400 `01-010`/`02-010`/`03-010`/`04-010`/`05-010`/`06-010`/`07-010`.
  - `TTL(n)` is stored as days.
  - The media type is stored.
  - `QueryReplicationHook.afterInsert` runs after commit; the default is a no-op bean.

- **S2-WP8** — One row by primary key.
  - `WITH(CR)` takes a row lock (`FOR UPDATE`).
  - Missing key → 204 `01-020` (KEY not found, ZFAM020 `ER_20401`) or 204 `02-020` (FILE not found, `ER_20402`).
  - A SELECT whose first predicate is not the primary key and not a CI → 400 `01-020`.
  - Fields that span 32,000-byte segments come back correctly.

- **S2-WP9** — Range scan on the first secondary predicate, using its operator `=`/`>`/`+` and the optional `*` prefix wildcard.
  - Remaining predicates filter the primary record.
  - Stops after `ROWS` rows (0 = all).
  - Streams with chunked encoding.
  - Response larger than the configured maximum → 206 `01-022`.
  - CI field longer than 56 → 412; filter longer than 256 → 412.
  - Ordering is byte order (§5.1).
  - Load test: 100k-row index, first row in under 50 ms.

- **S2-WP10** — UPDATE requires the primary-key predicate (400 `01-030`).
  - Read with lock, overlay fields, maintain CI with behaviour (c), apply TTL (resets `abs` time, type `D`), then `afterUpdate` hook.
  - Missing key → 204.

- **S2-WP11** — DELETE by primary key: delete all CI rows (cascade), the key row, and all file segments, then `afterDelete` hook.
  - Missing key → 204 `01-040` (ZFAM040 `ER_20401`).
  - Primary key absent → 400 `01-040` / `09-001`.

- **S2-WP12** — Testcontainers PostgreSQL. Replays the MLB walkthrough and every Query Mode row of http_response_codes.md against the app.
  - Where S4 can supply mainframe captures, the suite diffs the app's responses against them.
  - Includes EBCDIC-vs-UTF-8 collation regression cases (§5.1).
  - Runs in CI.

---

## 4. Interfaces with other segments

**S2 needs:**

- **From S3:**
  - `ZfamRequest` (method, scheme, raw query string, body bytes, headers, authenticated principal, instance id `FAxx`, `/replicate` flag). Query Mode is detected when the query string starts with `zQL`, compared case-insensitively.
  - The front controller hands Query Mode requests to `QueryModeController.handle`.
  - `SecurityDefinitionRepository.find(instance)` → `{basicReadOnly, queryReadOnly, users: [{userid, accessType, flags[0..32]}]}`.
  - `InternalKeyGenerator.next()`, an 8-byte (or `long`) key that replaces TOD+NC.
  - `UidService.plainUid()` (ZUID001).
  - TTL expiry worker (ZFAM000 replacement) deletes through S1's repository; the CI cascade then removes index rows.
  - Flyway / Spring Boot skeleton.

- **From S1:**
  - `KeyStoreRepository` / `FileStoreRepository`, the tables replacing FAxxKEY/FAxxFILE (`zfam_key`, `zfam_file_header`, segment or record table), with methods `insert`, `findByKey(forUpdate)`, `updateRecord`, `deleteByInternalKey`.
  - Record bytes stored as one `bytea` logical record. S2 recommends no segmentation in PostgreSQL.
  - Shared `ZfamException` + `@ControllerAdvice` (ZFAM090 replacement) that renders `STATUSTEXT` exactly, e.g. `"206 01-022 Respo..."`.
  - Data-store resolver (FAxxDD → `data_store`).
  - S1's Basic Mode POST/PUT/DELETE calls S2's `SecondaryIndexMaintainer` when a schema exists. This replaces the LINKs at ZFAM002 l.2708, 3042, 3548 and 3603.

- **From S4:**
  - Implementation of `QueryReplicationHook`.
  - Migration of FAxxFD/FAxxSD templates and FAxxCInn KSDS → `zfam_field_def` / `zfam_column_index`. CI rows can also be **rebuilt** from migrated records using `SecondaryIndexMaintainer.rebuild(instance)`; S2 provides this.
  - Parity harness and capture format.

**S2 exposes:**

```java
public interface QueryModeHandler { ResponseEntity<?> handle(ZfamRequest req); }          // S3 calls
public interface SecondaryIndexMaintainer {                                                // S1, S4 call
  void onInsert(TableSchema s, byte[] internalKey, byte[] newRecord, BlankPolicy p);
  void onUpdate(TableSchema s, byte[] internalKey, byte[] oldRecord, byte[] newRecord);
  void onDelete(TableSchema s, byte[] internalKey, byte[] oldRecord);
  void rebuild(String instanceId); }
public interface SchemaRepository { Optional<TableSchema> find(String instanceId); }       // S1 (has-schema check), S4
public interface QueryReplicationHook {                                                    // S4 implements; replaces LINK ZFAM102 (ZP_TYPE/ZP_NAME/ZP_KEY)
  default void afterInsert(String instance, String fieldName, byte[] primaryKey) {}
  default void afterUpdate(String instance, String fieldName, byte[] primaryKey) {}
  default void afterDelete(String instance, String fieldName, byte[] primaryKey) {} }
```
The hook fires from `TransactionSynchronization.afterCommit`. On the mainframe, ZFAM102 is LINKed inside the task, before `WEB SEND`. S4 decides whether a synchronous call is still required (OQ-5).

---

## 5. Risks, behaviour that must be preserved, open questions

### 5.1 Top risks

1. **EBCDIC vs UTF-8 collation.** CI range scans (`>`, `+`, `STARTBR GTEQ`) and row order in SELECT output currently follow EBCDIC byte order, where lower-case < upper-case < digits. UTF-8/ASCII order is digits < upper < lower. Results of `WHERE(city>M)` will differ after migration.
   - Mitigation: decide (OQ-1) between accepting ASCII order and documenting it, or storing an EBCDIC-order sort key (`field_value_ebcdic bytea`, encoded with IBM-037).
   - Field `Len` values are **byte** lengths. Multi-byte UTF-8 characters can overflow a field that held the same text as single-byte EBCDIC. The codec must truncate on a character boundary, or reject the value.

2. **Wire-format quirks.** The non-standard JSON (unquoted zero-padded numbers), fixed padding, `STATUSTEXT` strings and the 206 partial-response behaviour all have to stay byte-for-byte. Spring's default JSON serializers must not be used.

3. **Logic sits in ZFAM001 (S3's file).** If S3 also re-implements parsing, the work is duplicated or drifts. The contract is that **S2 owns `ZqlParser` and Query Mode security, and S3 only routes.**

4. **Secondary-index consistency.** The legacy code ignores CI write and delete failures (`NOHANDLE`, no RESP check in `CI_0010` and ZFAM011/031/041), so the KSDS indexes can already be inconsistent. A rebuild is safer than a copy during migration (S4).

5. **Concurrency.** WITH(UR) cannot be reproduced in PostgreSQL. WITH(CR) becomes `FOR UPDATE`, which blocks writers for the length of the request; RLS behaved the same. Run load tests.

6. **Large records.** Non-indexed C fields can be up to 256 KB and the logical record has no fixed maximum. Storing it as one `bytea` is fine up to 1 GB, but SELECT should read the record once rather than per segment.

### 5.2 Quirks to preserve, or to decide on deliberately

- **Q1. ZFAM021 never runs.** `QS_0480` sets `W_CI='1'` and then always overwrites it with `'2'` after reading `zFAM-Stream`. Any secondary WHERE goes to ZFAM022, and the `zFAM-Stream` value is read but never used.
- **Q2. GET routing looks at any WHERE field.** A secondary WHERE field in **any** position routes the request to ZFAM022, which then uses the **first secondary** predicate it finds for the index scan (`SY_0062`). That is not necessarily the first predicate written.
- **Q3. Both PUT branches go to ZFAM030.** `QS_0433` and `QS_0434` (spanned-segment / CI-update case) both XCTL to ZFAM030. There is no separate program.
- **Q4. Commands are case-insensitive, `AND` and OPTIONS parameters are not.** `OC x'40'` also changes non-letter bytes in place. Only the keyword comparisons need this behaviour; field values are not affected.
- **Q5. A value is everything up to the next `)`.** A value cannot contain `)`. Commas and spaces in values are kept.
- **Q6. No length check on INSERT values.** `QM_0136` compares against `MAX_LEN` but never branches, so INSERT values are effectively unlimited. UPDATE (`QM_0336`/`QM_0346`) and WHERE (`QM_0246`) do enforce 64,000.
- **Q7. ROWS has five digits at most.** `QM_0256A` rejects a length of 6. The docs say 1–9999; the code accepts up to 99999, and 0 means all rows.
- **Q8. DISTINCT, MODE, SORT and XML/DELIMITER are parsed but mostly unused.** ZFAM020/022 never read `O_DIST`, `O_MODE` or `O_SORT`. Parse them and ignore them.
- **Q9. DELETE accepts exactly one predicate, on the primary key.** Anything else is 400 `09-001`.
- **Q10. Blank secondary values are inconsistent.** ZFAM010 and ZFAM011 skip CI rows for blank values; ZFAM031 writes them. As a result, Basic Mode PUT makes blank values searchable.
- **Q11. Orphaned CI rows.** The TTL expiry task ZFAM000 does not delete CI rows. The planned cascade changes this, which is an intended fix.
- **Q12. ZFAM041 is COBOL in a `.asm` file.** The "Query Mode" header comment in ZFAM022 refers to ZFAM021.
- **Q13. Media type wins over OPTIONS.** The request media type is read by doing a `WEB RECEIVE` on a GET, and it takes priority over `OPTIONS(FORMAT=)`.
- **Q14. Field-level security covers WHERE fields too.** A user needs the flag for every predicate column, not only for the projected columns.
- **Q15. Some UPDATE syntax errors use the SELECT code.** Errors in the UPDATE verb and the comma after it (`QM_0300`) branch to `ER_40007` and return SELECT's 400 `07-001`. Only errors in later clauses return `08-001`.

### 5.3 Open questions

- **OQ-1** — Keep EBCDIC collation for CI ranges and ordering, or accept ASCII order? (Needs a business owner.)
- **OQ-2** — Make the blank-value CI policy consistent (Q10), or keep it bug-for-bug?
- **OQ-3** — Truncate or reject over-length values on INSERT/UPDATE (Q6)? The mainframe silently truncates through `EX MVC`.
- **OQ-4** — Should schema (FAxxFD) and security (FAxxSD) remain file-based templates (GitOps), or become DB rows managed through an admin API? The proposal is DB rows plus an importer that accepts the legacy text format.
- **OQ-5** — Replication timing: in-transaction (as on the mainframe) or after-commit/outbox? S4 decides.
- **OQ-6** — Internal key type, `bytea(8)` or `bigint` (S1/S3)? The CI primary key depends on it.
- **OQ-7** — Should `zFAM-Stream` and `MODE=OFFLINE` get real behaviour? Today they are no-ops.
- **OQ-9** — The plan does not carry forward two legacy permissions by default: unauthenticated `/replicate` and "no FAxxSD = full access". Can any instance in production rely on either? If so, those instances need an explicit migration exception.
- **OQ-8** — Where http_response_codes.md and the code disagree (FAxxFD missing: doc 403 `01-001`, code 405 `05-001`), which one is the contract? The plan follows the code until told otherwise.
