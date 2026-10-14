# zFAM local tests

Runs zFAM CICS COBOL programs on Linux with GnuCOBOL, without a z/OS
mainframe, by translating `EXEC CICS` commands into calls to a small CICS
stand-in.

| File | Purpose |
| --- | --- |
| `cics_preprocess.py` | Minimal CICS translator: replaces `EXEC CICS` with `CALL`s, adds the EIB and DFHCOMMAREA to `PROCEDURE DIVISION USING`, and widens 31-bit address arithmetic fields to 64-bit. |
| `cics_stub.c` | CICS commands used by the browse programs (GETMAIN, WEB READ/WRITE/SEND, STARTBR, READ, READNEXT, READPREV, LINK ZFAM006, RETURN) over an in-memory KEY/FILE store, and a `main` that runs one request and prints the HTTP response. |
| `build.sh` | Builds one program into a harness executable. |
| `test_rows_browse.py` | Tests for the multi-row browse program ZFAM007. |

## Requirements

GnuCOBOL 3.x (`cobc`, `cob-config`), a C compiler and Python 3.

```sh
sudo apt-get install gnucobol gcc python3
```

## Running

```sh
python3 tests/test_rows_browse.py
```

Every combination of browse type, start key, `rows`, `delim`, `keysonly`,
`zFAM-RangeEnd` and `zFAM-Select` is run against a sample table and compared
with a Python reference model of the documented behavior. Hand-written golden
responses pin the response body formats.

```sh
python3 tests/test_rows_browse.py --baseline <git-ref>
```

Also builds `ZFAM007`, `ZFAM008` and `ZFAM009` as of `<git-ref>`, runs each
scenario through the program ZFAM002 used to dispatch it to, and reports the
scenarios whose response differs from the current ZFAM007 (`-v` shows all
of them).

## Limitations

The stub models only the CICS behavior these programs rely on. EBCDIC to
ASCII conversion (`zFAM-Select` other than `text*`) is shown as upper-casing
so that the converted bytes are visible in the response body.
