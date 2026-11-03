"""ZFAM003 (range delete), ZFAM007/008/009 (multi-row browse), ZFAM000."""

from harness.zfam import Mock, Program

Z003 = Program.get("ZFAM003")
Z007 = Program.get("ZFAM007")
Z008 = Program.get("ZFAM008")
Z009 = Program.get("ZFAM009")
Z000 = Program.get("ZFAM000")


def _ca(kind: str, rows: int) -> str:
    return (f"MOVE '{kind}' TO GET-CA-TYPE\nMOVE {rows} TO GET-CA-ROWS\n"
            "MOVE 3 TO GET-CA-KEY-LENGTH\nMOVE 'abc' TO GET-CA-KEY")


NO_HEADERS = Mock("WEB READ", "NOTFND")


def _browse(verb: str, found: int):
    return [NO_HEADERS, Mock(verb, where={"FILE": "FK-FCT"}, times=found),
            Mock(verb, "ENDFILE", where={"FILE": "FK-FCT"})]


# --- ZFAM007: ge/gt with rows ------------------------------------------------


@Z007.case(_ca("ge", 10), perform="MAIN", mocks=_browse("READNEXT", 2))
def test_zfam007_stops_at_end_of_file(r):
    assert r.end == "CICS"
    assert len(r.calls("READNEXT")) == 3
    assert r.calls("WEB WRITE", HTTPHEADER="zFAM-Rows")


@Z007.case(_ca("ge", 5), perform="MAIN", mocks=[Mock("STARTBR", "NOTFND")])
def test_zfam007_empty_range_returns_204(r):
    assert r.status_codes == [204]
    assert not r.calls("READNEXT")


# --- ZFAM008: le/lt with rows ------------------------------------------------


@Z008.case(_ca("le", 10), perform="MAIN", mocks=_browse("READPREV", 2))
def test_zfam008_reads_backwards_until_start_of_file(r):
    assert len(r.calls("READPREV")) == 3


@Z008.case(_ca("lt", 5), perform="MAIN", mocks=[Mock("STARTBR", "NOTFND")])
def test_zfam008_empty_range_returns_204(r):
    assert r.status_codes == [204]


# --- ZFAM009: keysonly -------------------------------------------------------


@Z009.case(_ca("gt", 10), perform="MAIN", mocks=_browse("READNEXT", 3))
def test_zfam009_keys_only_never_reads_file_store(r):
    assert len(r.calls("READNEXT")) == 4
    assert r.status_codes == [200]
    assert not r.calls("READ", FILE="FA01")


@Z009.case(_ca("gt", 10), perform="MAIN", mocks=[Mock("STARTBR", "NOTFND")])
def test_zfam009_empty_range_returns_204(r):
    assert r.status_codes == [204]


# --- ZFAM003: ?Delete=* range delete -----------------------------------------


@Z003.case(perform="MAIN",
           mocks=[*_browse("READNEXT", 2),
                  Mock("DELETE", where={"FILE": "FF-FCT"}, times=1),
                  Mock("DELETE", "NOTFND", where={"FILE": "FF-FCT"})])
def test_zfam003_deletes_every_key_in_range(r):
    assert r.calls("STARTBR", FILE="FA01KEY")
    assert len(r.calls("READNEXT")) == 3
    assert len(r.calls("DELETE", FILE="FA01KEY")) == 2
    # Each key's FILE segments are deleted until NOTFND.
    assert len(r.calls("DELETE", FILE="FA01FILE")) == 3


@Z003.case(perform="MAIN", mocks=[Mock("STARTBR", "NOTFND")])
def test_zfam003_empty_range_returns_204(r):
    assert r.status_codes == [204]
    assert not r.calls("DELETE")


# --- ZFAM000: background expiration ------------------------------------------


@Z000.case(perform="MAIN")
def test_zfam000_skips_when_expiration_already_ran(r):
    # FAEXPIRE control record present: reschedule only, no browse.
    assert r.calls("ENQ")
    assert r.calls("START")
    assert not r.calls("STARTBR")


@Z000.case(perform="MAIN", mocks=[Mock("READ", "NOTFND", where={"FILE": "FX-FCT"}),
                                  Mock("STARTBR", "NOTFND")])
def test_zfam000_first_run_writes_control_record_and_browses(r):
    assert r.calls("WRITE")
    assert r.calls("STARTBR")
