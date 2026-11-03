"""ZFAM002 (Basic Mode CRUD) - end-to-end request flows with mocked CICS."""

from harness.cobol import method, web_path
from harness.zfam import Mock, Program

Z = Program.get("ZFAM002")
PATH = "/datastore/zFAM/cc/div/BU_SBU/FA01/abc"
FLOW = ["1000-ACCESS-PARMS", "2000-PROCESS-REQUEST"]
OUT = ["CA090-STATUS", "CA090-REASON", "FF-SEGMENTS", "FF-KEY"]

NO_HEADERS = Mock("WEB READ", "NOTFND")
KEY_FOUND = Mock("READ", where={"FILE": "FK-FCT"},
                 then="MOVE 'ABCDEF01' TO FK-FF-KEY")
PAYLOAD = Mock("WEB RECEIVE", then="MOVE 5 TO RECEIVE-LENGTH")


def request(verb: str, *mocks: Mock, path: str = PATH):
    return Z.case("\n".join([method(verb), web_path(path)]), perform=FLOW,
                  outputs=OUT, mocks=[NO_HEADERS, *mocks])


def _err(r):
    return r.num("CA090-STATUS"), r.out["CA090-REASON"]


# --- GET -------------------------------------------------------------------


@request("GET", KEY_FOUND)
def test_get_existing_key_returns_200(r):
    assert r.end == "DONE"
    assert r.status_codes == [200]
    assert r.calls("READ", FILE="FA01KEY")
    assert r.calls("READ", FILE="FA01FILE")
    assert r.xctl is None


@request("GET", Mock("READ", "NOTFND", where={"FILE": "FK-FCT"}))
def test_get_missing_key_returns_204(r):
    assert r.xctl == "ZFAM090"
    assert _err(r) == (204, "01")
    assert not r.calls("READ", FILE="FA01FILE")


@request("GET", Mock("READ", "NOTOPEN", where={"FILE": "FK-FCT"}))
def test_get_key_store_io_error_returns_507(r):
    assert r.xctl == "ZFAM090"
    assert _err(r) == (507, "01")
    assert r.calls("WRITEQ TD")


@request("GET")
def test_get_key_pointing_at_internal_key_returns_507_02(r):
    # A KEY record whose FILE key is LOW-VALUES is corrupt.
    assert r.xctl == "ZFAM090"
    assert _err(r) == (507, "02")


@request("GET", KEY_FOUND, Mock("READ", "NOTFND", where={"FILE": "FF-FCT"}))
def test_get_missing_file_record_returns_error(r):
    assert r.xctl == "ZFAM090"
    assert r.num("CA090-STATUS") in (204, 507)


# --- DELETE ----------------------------------------------------------------


@request("DELETE", KEY_FOUND,
         Mock("DELETE", where={"FILE": "FF-FCT"}, times=2),
         Mock("DELETE", "NOTFND", where={"FILE": "FF-FCT"}))
def test_delete_removes_key_and_all_segments(r):
    assert r.end == "DONE"
    assert r.status_codes == [200]
    assert len(r.calls("DELETE", FILE="FA01KEY")) == 1
    # Segments are deleted until the FILE store reports NOTFND.
    assert len(r.calls("DELETE", FILE="FA01FILE")) == 3
    assert r.calls("LINK", PROGRAM="ZFAM041")


@request("DELETE", Mock("READ", "NOTFND", where={"FILE": "FK-FCT"}))
def test_delete_missing_key_returns_204(r):
    assert r.xctl == "ZFAM090"
    assert _err(r) == (204, "02")
    assert not r.calls("DELETE")


@request("DELETE", path="/datastore/zFAM/cc/div/BU_SBU/FA01/")
def test_delete_without_key_returns_400(r):
    assert r.xctl == "ZFAM090"
    assert _err(r) == (400, "06")


# --- POST ------------------------------------------------------------------


@request("POST", PAYLOAD)
def test_post_writes_key_and_file_records(r):
    assert r.end == "DONE"
    assert r.status_codes == [200]
    assert r.calls("WRITE", FILE="FA01KEY")
    assert r.calls("WRITE", FILE="FA01FILE")
    assert r.calls("CALL", PROGRAM="ZUIDSTCK")
    assert r.num("FF-SEGMENTS") == 1


@request("POST", PAYLOAD, Mock("WRITE", "DUPREC", where={"FILE": "FK-FCT"}))
def test_post_duplicate_key_is_rejected(r):
    assert r.xctl == "ZFAM090"
    assert r.num("CA090-STATUS") == 409
    assert not r.calls("WRITE", FILE="FA01FILE")


# --- PUT -------------------------------------------------------------------


@request("PUT", PAYLOAD, KEY_FOUND, Mock("DELETE", "NOTFND", where={"FILE": "FF-FCT"}))
def test_put_existing_key_rewrites_records(r):
    assert r.end == "DONE"
    assert r.status_codes == [200]
    assert r.calls("REWRITE", FILE="FA01KEY")
    assert r.calls("WRITE", FILE="FA01FILE")
    # The previous FILE record is removed after the new one is committed.
    assert r.calls("DELETE", FILE="FA01FILE")
    assert len(r.calls("LINK", PROGRAM="ZFAM031")) == 2


@request("PUT", PAYLOAD, Mock("READ", "NOTFND", where={"FILE": "FK-FCT"}))
def test_put_missing_key_returns_204(r):
    assert r.xctl == "ZFAM090"
    assert r.num("CA090-STATUS") == 204
