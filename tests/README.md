# zFAM COBOL unit tests

Behavioral tests for the zFAM COBOL programs, run on Linux with GnuCOBOL.
The original sources in `Source/` are not modified.

## Running

    sudo apt-get install gnucobol3     # provides cobc 3.x
    pip install -r requirements-test.txt
    make test                          # or: python -m pytest

The run ends with a paragraph coverage table per program; details are written
to `build/tests/coverage.json`.

## How it works

`tests/harness/zfam.py` builds a testable copy of each program under
`build/tests/`:

- `COPY` members are expanded inline.
- Each `EXEC CICS ... END-EXEC` block is replaced by a hook that logs the
  call (`ZT|CICS|id|verb|option=value`), sets `EIBRESP` from a mock (default
  `NORMAL`) and ends the run on `RETURN` / `XCTL` / `ABEND`.
  `SET(ptr)` options get real storage.
- `DFHRESP(...)` / `DFHVALUE(...)` are resolved to constants and an EIB stub is
  added to WORKING-STORAGE. HLASM routines (e.g. `ZUIDSTCK`) are replaced by
  stubs in `tests/stubs/`.
- Every test becomes a generated paragraph: it sets fields, `PERFORM`s a
  paragraph (or `MAIN`, the program's own mainline) and `DISPLAY`s chosen
  output fields.

Writing a test:

```python
from harness.zfam import Mock, Program

Z = Program.get("ZFAM002")

@Z.case("MOVE 'ret-years=250' TO WEB-QUERYSTRING\nMOVE 13 TO WEB-QUERYSTRING-LENGTH",
        perform="1310-RETENTION", outputs=["FF-RETENTION"])
def test_retention_capped(r):
    assert r.num("FF-RETENTION") == 100

@Z.case(..., perform=["1000-ACCESS-PARMS", "2000-PROCESS-REQUEST"],
        mocks=[Mock("READ", "NOTFND", where={"FILE": "FK-FCT"})])
def test_missing_key(r):
    assert r.xctl == "ZFAM090"
```

`Mock(verb, resp, where={option: source-text}, times=n, then="COBOL")` matches
CICS blocks by verb and source option text. `then` runs COBOL after the mock
fires, e.g. to fill an `INTO` area.
