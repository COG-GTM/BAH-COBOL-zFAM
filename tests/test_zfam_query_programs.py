"""ZFAM004/005 (single-row browse), ZFAM090 (error responses), ZFAMPLT."""

from harness.zfam import Mock, Program

Z004 = Program.get("ZFAM004")
Z005 = Program.get("ZFAM005")
Z090 = Program.get("ZFAM090")
PLT = Program.get("ZFAMPLT")

KEY_ABC = "MOVE 3 TO GET-CA-KEY-LENGTH\nMOVE 'abc' TO GET-CA-KEY"


def _ca(kind: str) -> str:
    return f"MOVE '{kind}' TO GET-CA-TYPE\n{KEY_ABC}"


# --- ZFAM004: gt / ge / ex ---------------------------------------------------


@Z004.case(_ca("gt"), perform="MAIN")
def test_zfam004_gt_returns_next_record(r):
    assert r.status_codes == [200]
    assert r.calls("READ", FILE="FA01KEY")
    assert r.calls("WEB WRITE", HTTPHEADER="zFAM-LastKey")


@Z004.case(_ca("gt"), perform="2000-CHECK-KEY",
           outputs=["GET-CA-KEY-LENGTH"])
def test_zfam004_gt_augments_short_key_without_link(r):
    # Keys shorter than 255 bytes get X'01' appended in byte 255; no LINK.
    assert not r.calls("LINK")


@Z004.case("MOVE 'gt' TO GET-CA-TYPE\nMOVE 255 TO GET-CA-KEY-LENGTH",
           perform="2000-CHECK-KEY")
def test_zfam004_gt_full_length_key_links_zfam006(r):
    assert r.calls("LINK", PROGRAM="ZFAM006")


@Z004.case(_ca("ge"), perform="2000-CHECK-KEY")
def test_zfam004_ge_does_not_augment_key(r):
    assert not r.calls("LINK")


@Z004.case(_ca("gt"), perform="MAIN", mocks=[Mock("READ", "NOTFND")])
def test_zfam004_no_next_record_returns_204(r):
    assert r.status_codes == [204]


@Z004.case(_ca("ex"), perform="MAIN")
def test_zfam004_existence_check_found(r):
    assert r.status_codes and r.status_codes[-1] == 200
    assert not r.calls("READ", FILE="FA01")


@Z004.case(_ca("ex"), perform="MAIN", mocks=[Mock("READ", "NOTFND")])
def test_zfam004_existence_check_not_found(r):
    assert r.status_codes == [204]


# --- ZFAM005: lt / le --------------------------------------------------------


@Z005.case(_ca("le"), perform="MAIN")
def test_zfam005_le_reads_backwards(r):
    assert r.status_codes == [200]
    assert r.calls("READ", FILE="FA01KEY")
    assert r.calls("READ", FILE="FA01")


@Z005.case(_ca("lt"), perform="MAIN")
def test_zfam005_lt_browses_with_readprev(r):
    assert r.calls("STARTBR", FILE="FA01KEY")
    assert r.calls("READPREV", FILE="FA01KEY")
    assert r.status_codes == [200]


@Z005.case(_ca("lt"), perform="MAIN", mocks=[Mock("READ", "NOTFND"), Mock("STARTBR", "NOTFND")])
def test_zfam005_nothing_before_key_returns_204(r):
    assert r.status_codes == [204]


# --- ZFAM090: status/reason lookup -------------------------------------------


def _invoked_by(program: str) -> Mock:
    return Mock("ASSIGN", then=f"MOVE '{program}' TO INVOKING-PROGRAM")


def _err(status: int, reason: int, program: str = "ZFAM002"):
    body = f"MOVE {status} TO CA-STATUS\nMOVE {reason} TO CA-REASON\nMOVE 'FA01KEY' TO CA-FILE"
    return Z090.case(body, perform="MAIN", outputs=["HTTP-STATUS-TEXT", "TD-STATUS"],
                     mocks=[_invoked_by(program)])


@_err(204, 1)
def test_zfam090_known_status_is_sent(r):
    assert r.status_codes == [204]
    assert r.calls("WRITEQ TD")
    assert r.out["HTTP-STATUS-TEXT"].strip()


@_err(400, 2)
def test_zfam090_uri_slash_error(r):
    assert r.status_codes == [400]


@_err(507, 1)
def test_zfam090_file_error_reports_file_name(r):
    assert r.status_codes == [507]
    assert "FA01KEY" in r.out["HTTP-STATUS-TEXT"]


@_err(123, 45)
def test_zfam090_unknown_status_falls_back_to_999(r):
    assert r.status_codes == [999]


@_err(204, 1, program="ZFAMXYZ")
def test_zfam090_status_is_program_specific(r):
    assert r.status_codes == [999]


# --- ZFAMPLT: start expiration tasks for each FAxx URIMAP --------------------


def _urimap(name: str, path: str = "/datastore/zFAM/x") -> Mock:
    return Mock("INQUIRE", where={"NEXT": ""}, times=1,
                then=f"MOVE '{name}' TO URI-MAP\nMOVE '{path}' TO URI-PATH\n"
                     "MOVE 'FA01' TO URI-TRAN")


PLT_END = Mock("INQUIRE", "ENDFILE", where={"NEXT": ""})


@PLT.case(perform="MAIN", mocks=[_urimap("FA01"), _urimap("XX01"), _urimap("FA02R"), PLT_END])
def test_plt_starts_expiration_only_for_basic_faxx_urimaps(r):
    assert r.end == "CICS"
    starts = r.calls("START")
    assert len(starts) == 1
    assert len(r.calls("WRITEQ TD")) == 1
    assert r.calls("INQUIRE")[-1].verb == "INQUIRE"


@PLT.case(perform="MAIN", mocks=[PLT_END])
def test_plt_no_urimaps_starts_nothing(r):
    assert not r.calls("START")
