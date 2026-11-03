"""ZFAM002 (Basic Mode CRUD) - query string and retention parsing."""

from harness.cobol import method, query_string
from harness.zfam import Mock, Program

Z = Program.get("ZFAM002")
RET_OUT = ["FF-RETENTION", "FK-RETENTION", "FF-RETENTION-TYPE", "FK-RETENTION-TYPE"]


def _retention(qs: str):
    return Z.case(query_string(qs) if qs else "", perform="1310-RETENTION", outputs=RET_OUT)


@_retention("")
def test_retention_defaults_to_seven_years(r):
    assert r.num("FF-RETENTION") == 7
    assert r.num("FK-RETENTION") == 7
    assert r.out["FF-RETENTION-TYPE"] == "Y"
    assert r.out["FK-RETENTION-TYPE"] == "Y"


@_retention("ret-years=25")
def test_retention_years_within_range(r):
    assert r.num("FF-RETENTION") == 25
    assert r.out["FF-RETENTION-TYPE"] == "Y"


@_retention("ret-years=250")
def test_retention_years_capped_at_100(r):
    assert r.num("FF-RETENTION") == 100
    assert r.num("FK-RETENTION") == 100


@_retention("ret-years=0")
def test_retention_years_minimum_one(r):
    assert r.num("FF-RETENTION") == 1


@_retention("ret-days=30")
def test_retention_days_sets_day_type(r):
    assert r.num("FF-RETENTION") == 30
    assert r.out["FF-RETENTION-TYPE"] == "D"
    assert r.out["FK-RETENTION-TYPE"] == "D"


@_retention("ret-days=99999")
def test_retention_days_capped_at_36500(r):
    assert r.num("FF-RETENTION") == 36500


@_retention("ret-days=0")
def test_retention_days_minimum_one(r):
    assert r.num("FF-RETENTION") == 1


@_retention("ttl=45")
def test_ttl_only_updates_file_record(r):
    assert r.num("FF-RETENTION") == 45
    assert r.out["FF-RETENTION-TYPE"] == "D"
    # ?ttl= intentionally leaves the KEY record at the 7-year default.
    assert r.num("FK-RETENTION") == 7
    assert r.out["FK-RETENTION-TYPE"] == "Y"


@_retention("ttl=99999")
def test_ttl_capped_at_36500(r):
    assert r.num("FF-RETENTION") == 36500


@_retention("unknown=12")
def test_unknown_query_keeps_default(r):
    assert r.num("FF-RETENTION") == 7


# --- HTTP header TTL (zFAM-TTL) ------------------------------------------


@Z.case("MOVE '00090' TO HTTP-TTL-VALUE", perform="1500-READ-TTL", outputs=RET_OUT)
def test_ttl_header_sets_retention_days(r):
    assert r.num("FF-RETENTION") == 90
    assert r.num("FK-RETENTION") == 90
    assert r.out["FK-RETENTION-TYPE"] == "D"
    assert r.calls("WEB READ", HTTPHEADER="HTTP-TTL") or r.calls("WEB READ")


@Z.case("MOVE '99999' TO HTTP-TTL-VALUE", perform="1500-READ-TTL", outputs=RET_OUT)
def test_ttl_header_capped(r):
    assert r.num("FF-RETENTION") == 36500


@Z.case("MOVE '00000' TO HTTP-TTL-VALUE", perform="1500-READ-TTL", outputs=RET_OUT)
def test_ttl_header_minimum_one_day(r):
    assert r.num("FF-RETENTION") == 1


@Z.case("MOVE 3 TO FF-RETENTION FK-RETENTION\nMOVE '00090' TO HTTP-TTL-VALUE",
        perform="1500-READ-TTL", outputs=RET_OUT,
        mocks=[Mock(
            "WEB READ", "NOTFND", where={"HTTPHEADER": "HTTP-TTL"})])
def test_missing_ttl_header_leaves_retention(r):
    assert r.num("FF-RETENTION") == 3
