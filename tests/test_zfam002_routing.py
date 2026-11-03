"""ZFAM002 (Basic Mode CRUD) - URI parsing and GET query-string routing."""

from harness.cobol import method, query_string, web_path
from harness.zfam import Mock, Program

Z = Program.get("ZFAM002")
PATH = "/datastore/zFAM/cc/div/BU_SBU/FA01/"
GET_OUT = ["GET-CA-TYPE", "GET-CA-ROWS", "GET-CA-DELIM", "GET-CA-KEYS",
           "GET-CA-TTL", "GET-CA-KEY-LENGTH", "GET-CA-KEY", "QS-PROGRAM"]
ERR_OUT = ["CA090-STATUS", "CA090-REASON"]


NO_TTL = Mock("WEB READ", "NOTFND", where={"HTTPHEADER": "HTTP-TTL"})


def _access(path: str, verb: str = "DELETE", qs: str = "", outputs=()):
    body = "\n".join(filter(None, [method(verb), web_path(path), query_string(qs) if qs else ""]))
    return Z.case(body, perform="1000-ACCESS-PARMS",
                  outputs=["URI-KEY", "URI-KEY-LENGTH", "SLASH-COUNTER", *ERR_OUT, *outputs],
                  mocks=[NO_TTL])


@_access(PATH + "customer-123")
def test_uri_key_extracted_after_seventh_slash(r):
    assert r.end == "DONE"
    assert r.num("SLASH-COUNTER") == 7
    assert r.num("URI-KEY-LENGTH") == len("customer-123")
    assert r.out["URI-KEY"].startswith("customer-123")


@_access("/datastore/zFAM/cc/div/key")
def test_uri_with_too_few_slashes_rejected_400_02(r):
    assert r.xctl == "ZFAM090"
    assert r.num("CA090-STATUS") == 400
    assert r.out["CA090-REASON"] == "02"


@_access(PATH + "k" * 256)
def test_uri_key_longer_than_255_rejected_400_03(r):
    assert r.xctl == "ZFAM090"
    assert r.num("CA090-STATUS") == 400
    assert r.out["CA090-REASON"] == "03"


@_access(PATH, verb="GET")
def test_get_without_key_rejected_400_04(r):
    assert r.xctl == "ZFAM090"
    assert (r.num("CA090-STATUS"), r.out["CA090-REASON"]) == (400, "04")


@_access(PATH, verb="PUT")
def test_put_without_key_rejected_400_05(r):
    assert r.xctl == "ZFAM090"
    assert (r.num("CA090-STATUS"), r.out["CA090-REASON"]) == (400, "05")


@_access(PATH + "abc", verb="POST", qs="ret-days=10", outputs=["FF-RETENTION"])
def test_post_parses_retention_and_receives_payload(r):
    assert r.num("FF-RETENTION") == 10
    assert r.calls("WEB RECEIVE")


def _get(qs: str, key: str = "abc"):
    body = "\n".join([method("GET"), query_string(qs), "MOVE 3 TO URI-KEY-LENGTH",
                      f"MOVE '{key}' TO URI-KEY"])
    return Z.case(body, perform="1330-GET", outputs=GET_OUT)


@_get("")
def test_get_without_query_reads_single_record(r):
    assert r.end == "DONE"
    assert r.out["GET-CA-TYPE"] == "eq"
    assert r.num("GET-CA-ROWS") == 1
    assert r.out["QS-PROGRAM"] == ""
    assert r.xctl is None


@_get("gt")
def test_get_gt_routes_to_forward_browse_zfam004(r):
    assert r.xctl == "ZFAM004"
    assert r.out["GET-CA-TYPE"] == "gt"
    assert r.num("GET-CA-KEY-LENGTH") == 3
    assert r.out["GET-CA-KEY"].startswith("abc")


@_get("ex")
def test_get_ex_routes_to_existence_check_zfam004(r):
    assert r.xctl == "ZFAM004"


@_get("le")
def test_get_le_routes_to_backward_browse_zfam005(r):
    assert r.xctl == "ZFAM005"


@_get("ge,rows=25")
def test_get_ge_rows_routes_to_multi_row_zfam007(r):
    assert r.xctl == "ZFAM007"
    assert r.num("GET-CA-ROWS") == 25


@_get("lt,rows=10")
def test_get_lt_rows_routes_to_multi_row_backward_zfam008(r):
    assert r.xctl == "ZFAM008"
    assert r.num("GET-CA-ROWS") == 10


@_get("gt,rows=5,keysonly")
def test_get_keysonly_routes_to_zfam009(r):
    assert r.xctl == "ZFAM009"
    assert r.out["GET-CA-KEYS"] == "Y"


@_get("gt,rows=")
def test_get_rows_without_count_still_routes_to_multi_row(r):
    assert r.xctl == "ZFAM007"


@_get("gt,ttl")
def test_get_ttl_flag(r):
    assert r.out["GET-CA-TTL"] == "Y"


@_get("gt,delim=;")
def test_get_literal_delimiter(r):
    # A literal comma cannot be used: ',' separates query parameters.
    assert r.out["GET-CA-DELIM"] == ";"


@_get("gt,delim=%2c")
def test_get_hex_encoded_delimiter_is_decoded(r):
    # %2C is translated through the ZFAMHEX table into the single byte X'2C'.
    assert r.out["GET-CA-DELIM"] == ","


@_get("bogus,gt")
def test_get_unknown_parameters_are_ignored(r):
    assert r.xctl == "ZFAM004"
    assert r.out["GET-CA-TYPE"] == "gt"


def _delete(qs: str, path: str = PATH.rstrip("/") + ".ADR/"):
    body = "\n".join([query_string(qs), web_path(path),
                      "MOVE 'FA01.ADR' TO URI-FIELD-06"])
    return Z.case(body, perform="1320-DELETE", outputs=["CA-TYPE", "CA-URI-FIELD-01"])


@_delete("Delete=*")
def test_range_delete_xctls_to_zfam003(r):
    assert r.xctl == "ZFAM003"
    assert r.out["CA-TYPE"] == "ADR"
    assert r.out["CA-URI-FIELD-01"] == "/datastore"


@_delete("Delete=x")
def test_delete_without_star_stays_in_zfam002(r):
    assert r.xctl is None
