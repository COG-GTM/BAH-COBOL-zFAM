#!/usr/bin/env python3
"""Tests for the zFAM Basic Mode multi-row browse program (ZFAM007).

ZFAM007 is built with GnuCOBOL against the CICS stand-in in cics_stub.c and
run against an in-memory KEY/FILE store for every combination of browse
type, start key, ROWS, DELIM, KEYSONLY, zFAM-RangeEnd and zFAM-Select.  Each
response is compared with a Python reference model of the documented
behavior, and a few hand-written golden responses pin the body format.

    python3 tests/test_rows_browse.py
    python3 tests/test_rows_browse.py --baseline <git-ref>

--baseline also builds the pre-consolidation ZFAM007/ZFAM008/ZFAM009 from
<git-ref>, dispatches each scenario the way ZFAM002 did, and reports every
scenario whose response differs from the current ZFAM007.
"""
import argparse
import itertools
import os
import struct
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

KEYLEN = 255
FK_LEN = 512
FF_PREFIX = 356
GETMAIN_LENGTH = 3200000
SEGMENT_SIZE = 32000


# ---------------------------------------------------------------------------
# Data store
# ---------------------------------------------------------------------------
class Record:
    def __init__(self, key, segments, obj="text", media="text/plain",
                 declared_segments=None):
        self.key = key.encode() if isinstance(key, str) else key
        self.segments = [s.encode() if isinstance(s, str) else s
                         for s in segments]
        self.obj = obj
        self.media = media
        self.declared_segments = declared_segments or len(self.segments)

    @property
    def data(self):
        return b"".join(self.segments)


def pad(key, fill=b"\x00"):
    return key + fill * (KEYLEN - len(key))


def build_store(records):
    records = sorted(records, key=lambda r: pad(r.key))
    keys, files = bytearray(), bytearray()
    for i, rec in enumerate(records):
        ff_key = b"ID%04d" % i + b"\x00\x01"
        fk = bytearray(FK_LEN)
        fk[0:KEYLEN] = pad(rec.key)
        fk[256:264] = ff_key
        fk[264:268] = rec.obj.encode().ljust(4)
        fk[268:272] = b"FILE"
        keys += fk
        for seg_no, seg in enumerate(rec.segments, 1):
            ff = bytearray(FF_PREFIX)
            ff[0:8] = ff_key
            ff[8:10] = struct.pack(">H", seg_no)
            ff[28:30] = struct.pack(">H", rec.declared_segments)
            ff[45:300] = pad(rec.key)
            ff[300:356] = rec.media.encode().ljust(56)
            ff += seg
            files += struct.pack(">H", len(ff)) + ff
    return records, bytes(keys), bytes(files)


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class Request:
    def __init__(self, gtype, key, rows, delim=None, keys_only=False,
                 range_end=None, select=None):
        self.gtype = gtype
        self.key = key.encode() if isinstance(key, str) else key
        self.rows = rows
        self.delim = delim
        self.keys_only = keys_only
        self.range_end = range_end
        self.select = select

    def commarea(self):
        return (self.gtype.encode()
                + b"%04d" % self.rows
                + (self.delim.encode() if self.delim else b"\x00")
                + (b"Y" if self.keys_only else b"N")
                + b"N" + b"\x00" * 7
                + struct.pack(">i", len(self.key))
                + pad(self.key))

    def headers(self):
        lines = []
        if self.select is not None:
            lines.append("zFAM-Select\t" + self.select)
        if self.range_end is not None:
            lines.append("zFAM-RangeEnd\t" + self.range_end)
        return "".join(line + "\n" for line in lines)

    def __repr__(self):
        parts = [self.gtype, "key=%r" % self.key.decode(errors="replace")[:20],
                 "rows=%d" % self.rows]
        if self.delim:
            parts.append("delim=%s" % self.delim)
        if self.keys_only:
            parts.append("keysonly")
        if self.range_end is not None:
            parts.append("RangeEnd=%s" % self.range_end)
        if self.select is not None:
            parts.append("Select=%s" % self.select)
        return "?" + ",".join(parts)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
def escape(data):
    out = []
    for b in data:
        if 0x20 <= b < 0x7F and b != 0x5C:
            out.append(chr(b))
        else:
            out.append("\\x%02x" % b)
    return "".join(out)


def response(status, text, headers, media, convert, body):
    lines = ["HEADER %s: %s" % (name, escape(value)) for name, value in headers]
    lines += ["STATUS %d %s" % (status, escape(text)),
              "MEDIATYPE %s" % media,
              "CONVERT %s" % convert,
              "BODYLEN %d" % len(body),
              "BODY %s" % escape(body)]
    return "\n".join(lines) + "\n"


def not_found():
    return response(204, b"Record not found",
                    [("zFAM-LastKey", b""), ("zFAM-Rows", b"0000")],
                    "text/plain", "SRVCONVERT", b"")


# ---------------------------------------------------------------------------
# Reference model of ZFAM007
# ---------------------------------------------------------------------------
def increment(key):
    value = (int.from_bytes(key, "big") + 1) % (1 << (8 * KEYLEN))
    return value.to_bytes(KEYLEN, "big")


def model(records, req):
    keys = [pad(r.key) for r in records]
    backward = req.gtype in ("le", "lt")
    select = (req.select or "text").encode()[:6].ljust(6)
    convert_fields = not req.keys_only and select[:4] != b"text"

    if not backward:
        start = pad(req.key)
        if req.gtype == "gt":
            start = (start[:254] + b"\x01" if len(req.key) < KEYLEN
                     else increment(start))
        idx = next((i for i, k in enumerate(keys) if k >= start), None)
        if idx is None:
            return not_found()
        fk_key, order = start, list(range(idx, len(keys)))
    else:
        req_key = pad(req.key)
        idx = next((i for i, k in enumerate(keys) if k >= req_key), None)
        if idx is None:
            fk_key, first = b"\xff" * KEYLEN, len(keys) - 1
        else:
            fk_key, first = keys[idx], idx
            if ((req.gtype == "le" and keys[idx] > req_key)
                    or (req.gtype == "lt" and keys[idx] >= req_key)):
                first = idx - 1
        order = list(range(first, -1, -1))

    def conv(field):
        return field.upper() if convert_fields else field

    body, count, rows_count = b"", 0, 0
    previous, range_exceeded, buffer_full = fk_key, False, False
    media = None
    rng = req.range_end.encode() if req.range_end is not None else None

    for i in order + [None]:
        previous = fk_key
        if i is None:
            break
        rec, fk_key = records[i], keys[i]
        if rng is not None:
            head = fk_key[:len(rng)]
            if (head > rng) if not backward else (head < rng):
                range_exceeded = True
                break
        if req.keys_only:
            selected = True
        else:
            selected = (select[:4] == b"text") == (rec.obj == "text")
        if selected:
            key = rec.key
            row = (conv(b"%03d" % len(key)) if not req.delim
                   else (req.delim.encode() if count else b"")) + conv(key)
            if not req.keys_only:
                row += b"\0" * (7 if not req.delim else 1)
            if len(row) > GETMAIN_LENGTH - len(body):
                buffer_full = True
                break
            if req.keys_only:
                body += row
                count += 1
            elif rec.segments:
                media = rec.media
                logical = rec.declared_segments * SEGMENT_SIZE
                if logical > GETMAIN_LENGTH - len(body) - len(row):
                    buffer_full = True
                    break
                data = rec.data
                if not req.delim:
                    row = row[:-7] + conv(b"%07d" % len(data)) + data
                else:
                    row = row[:-1] + conv(req.delim.encode()) + data
                body += row
                count += 1
            rows_count = count
        if rows_count == req.rows:
            break

    if count == 0:
        return not_found()
    if buffer_full or range_exceeded:
        last, status = previous, 206 if buffer_full else 200
    else:
        last, status = fk_key, 200
    last = last.rstrip(b"\x00")
    if req.keys_only or not media.strip():
        media = "text/plain"
    convert = ("SRVCONVERT" if media.startswith(("text", "application/xml",
                                                 "application/json"))
               else "NOSRVCONVERT")
    return response(status, last,
                    [("zFAM-LastKey", last), ("zFAM-Rows", b"%04d" % count)],
                    media, convert, body)


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------
def build(source, program_id, output):
    subprocess.run([os.path.join(HERE, "build.sh"), source, program_id, output],
                   check=True)


def run(executable, store, req, workdir):
    _, keys, files = store
    with open(os.path.join(workdir, "commarea.bin"), "wb") as f:
        f.write(req.commarea())
    with open(os.path.join(workdir, "keys.bin"), "wb") as f:
        f.write(keys)
    with open(os.path.join(workdir, "file.bin"), "wb") as f:
        f.write(files)
    with open(os.path.join(workdir, "headers.txt"), "w") as f:
        f.write(req.headers())
    result = subprocess.run([executable, workdir], capture_output=True,
                            text=True, errors="replace")
    return result.stdout + result.stderr


def sample_records():
    return [
        Record("mlb/angels", ["Los Angeles Angels"]),
        Record("mlb/braves", ["Atlanta ", "Braves"]),
        Record("mlb/cubs", ["Chicago Cubs"]),
        Record("mlb/dodgers", ["\x01\x02logo"], obj="bin",
               media="application/octet-stream"),
        Record("mlb/mets", ["New York Mets"], media=""),
        Record("nba/bulls", ['{"team":"Chicago Bulls"}'],
               media="application/json"),
        Record("nba/celtics", ["Boston Celtics"]),
        Record("z" * KEYLEN, ["max key"]),
    ]


def scenarios():
    starts = ["a", "mlb/angels", "mlb/c", "mlb/cubs", "mlb/zz", "nba/celtics",
              "zzz", "z" * KEYLEN, "~"]
    for gtype, key, rows, delim, keys_only, range_end, select in itertools.product(
            ["ge", "gt", "le", "lt", "eq"], starts, [1, 2, 3, 9999],
            [None, "|"], [False, True], [None, "mlb/d", "mlb"],
            [None, "binary"]):
        if gtype == "eq" and not keys_only:
            continue  # ZFAM002 only XCTLs eq to ZFAM007 for KEYSONLY
        if keys_only and select is not None:
            continue  # zFAM-Select does not apply to KEYSONLY
        yield Request(gtype, key, rows, delim, keys_only, range_end, select)


def golden_cases():
    """Hand-written responses that pin the documented body formats."""
    a = b"mlb/angels"
    b = b"mlb/braves"
    c = b"mlb/cubs"
    return [
        (Request("ge", "mlb", 2),
         response(200, b, [("zFAM-LastKey", b), ("zFAM-Rows", b"0002")],
                  "text/plain", "SRVCONVERT",
                  b"010mlb/angels0000018Los Angeles Angels"
                  b"010mlb/braves0000014Atlanta Braves")),
        (Request("ge", "mlb", 3, delim="|"),
         response(200, c, [("zFAM-LastKey", c), ("zFAM-Rows", b"0003")],
                  "text/plain", "SRVCONVERT",
                  b"mlb/angels|Los Angeles Angels|mlb/braves|Atlanta Braves"
                  b"|mlb/cubs|Chicago Cubs")),
        (Request("ge", "mlb", 3, keys_only=True),
         response(200, c, [("zFAM-LastKey", c), ("zFAM-Rows", b"0003")],
                  "text/plain", "SRVCONVERT",
                  b"010mlb/angels010mlb/braves008mlb/cubs")),
        (Request("lt", "mlb/cubs", 9999, delim=",", keys_only=True),
         response(200, a, [("zFAM-LastKey", a), ("zFAM-Rows", b"0002")],
                  "text/plain", "SRVCONVERT", b"mlb/braves,mlb/angels")),
        (Request("le", "mlb/cubs", 9999, keys_only=True, range_end="mlb/b"),
         response(200, b, [("zFAM-LastKey", b), ("zFAM-Rows", b"0002")],
                  "text/plain", "SRVCONVERT", b"008mlb/cubs010mlb/braves")),
        (Request("gt", "mlb/angels", 2, range_end="mlb/b"),
         response(200, b, [("zFAM-LastKey", b), ("zFAM-Rows", b"0001")],
                  "text/plain", "SRVCONVERT",
                  b"010mlb/braves0000014Atlanta Braves")),
        (Request("ge", "~", 5), not_found()),
        (Request("lt", "mlb/angels", 5), not_found()),
    ]


def buffer_full_cases():
    """Response buffer full (206) cases, each with its own table."""
    k1, k2 = b"k1", b"k2"
    cases = []

    # The segments of k2 can not fit in the response buffer.
    records = [
        Record("k1", ["first"]),
        Record("k2", ["second"], declared_segments=GETMAIN_LENGTH // SEGMENT_SIZE),
        Record("k3", ["third"]),
    ]
    expected = response(206, k1, [("zFAM-LastKey", k1), ("zFAM-Rows", b"0001")],
                        "text/plain", "SRVCONVERT", b"002k10000005first")
    cases.append((records, Request("ge", "k", 10), expected))
    cases.append((records, Request("le", "k3", 10, keys_only=True), None))

    # k1 and k2 leave fewer bytes in the response buffer than the key and
    # framing of k3, which must not be written past the end of the buffer.
    short = 30
    full = b"x" * SEGMENT_SIZE
    records = [
        Record("k1", [full] * 98 + [full[:-short]]),
        Record("k2", [full]),
        Record("k3", ["third"]),
    ]
    cases.append((records, Request("ge", "k", 10), None))
    cases.append((records, Request("ge", "k", 10, delim="|"), None))
    return cases


def missing_data_cases():
    """KEY store entries whose FILE store record is missing are skipped."""
    records = [
        Record("a", [], declared_segments=1),
        Record("b", ["bee"]),
        Record("c", ["sea"]),
    ]
    b = b"b"
    expected = response(200, b, [("zFAM-LastKey", b), ("zFAM-Rows", b"0001")],
                        "text/plain", "SRVCONVERT", b"001b0000003bee")
    return records, [(Request("ge", "a", 1), expected),
                     (Request("le", "c", 9999, delim=","), None),
                     (Request("ge", "a", 2), None)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--baseline", metavar="GIT_REF",
                        help="report differences from ZFAM007/8/9 at GIT_REF")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        exe = os.path.join(tmp, "zfam007")
        build(os.path.join(REPO, "Source", "ZFAM007.cbl"), "ZFAM007", exe)

        failures, total = [], 0
        store = build_store(sample_records())
        work = os.path.join(tmp, "run")
        os.mkdir(work)

        def check(store, req, expected):
            nonlocal total
            total += 1
            actual = run(exe, store, req, work)
            if actual != expected:
                failures.append((req, expected, actual))

        for req in scenarios():
            check(store, req, model(store[0], req))
        for req, expected in golden_cases():
            check(store, req, expected)
        for records, req, expected in buffer_full_cases():
            bf_store = build_store(records)
            check(bf_store, req, expected or model(bf_store[0], req))
        md_records, md_cases = missing_data_cases()
        md_store = build_store(md_records)
        for req, expected in md_cases:
            check(md_store, req, expected or model(md_store[0], req))

        for req, expected, actual in failures[:10]:
            print("FAIL %r\n--- expected\n%s--- actual\n%s" % (req, expected,
                                                               actual))
        print("%d/%d ZFAM007 scenarios passed" % (total - len(failures), total))

        if args.baseline:
            baseline_report(args.baseline, tmp, store, exe, args.verbose)

    return 1 if failures else 0


def baseline_report(ref, tmp, store, exe, verbose):
    old = {}
    for prog in ("ZFAM007", "ZFAM008", "ZFAM009"):
        src = os.path.join(tmp, prog + ".old.cbl")
        with open(src, "wb") as f:
            f.write(subprocess.run(["git", "-C", REPO, "show",
                                    "%s:Source/%s.cbl" % (ref, prog)],
                                   check=True, capture_output=True).stdout)
        old[prog] = os.path.join(tmp, prog.lower() + ".old")
        build(src, prog, old[prog])

    def old_program(req):
        if req.keys_only:
            return "ZFAM009"
        return "ZFAM008" if req.gtype in ("le", "lt") else "ZFAM007"

    work = os.path.join(tmp, "baseline")
    os.mkdir(work)
    diffs, total = Counter(), Counter()
    examples = {}
    cases = [(store, req) for req in scenarios()]
    cases += [(build_store(records), req)
              for records, req, _ in buffer_full_cases()]
    md_records, md_cases = missing_data_cases()
    md_store = build_store(md_records)
    cases += [(md_store, req) for req, _ in md_cases]
    for store, req in cases:
        prog = old_program(req)
        total[prog] += 1
        before = run(old[prog], store, req, work)
        after = run(exe, store, req, work)
        if before != after:
            diffs[prog] += 1
            examples.setdefault(prog, []).append((req, before, after))
    print("\nBaseline %s: scenarios whose response changed" % ref)
    for prog in sorted(total):
        print("  %s: %d of %d" % (prog, diffs[prog], total[prog]))
    for prog, items in sorted(examples.items()):
        for req, before, after in items[: (len(items) if verbose else 3)]:
            print("\n[%s] %r\n--- before\n%s--- after\n%s" % (prog, req, before,
                                                              after))


if __name__ == "__main__":
    sys.exit(main())
