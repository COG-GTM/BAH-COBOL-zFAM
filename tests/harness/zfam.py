"""GnuCOBOL unit-test harness for the zFAM CICS COBOL programs.

Each program in ``Source/`` is preprocessed into a standalone, runnable
GnuCOBOL executable:

* ``COPY`` members are expanded inline from ``Source/*.cpy``.
* Every ``EXEC CICS ... END-EXEC`` block is replaced by a call to a mock
  hook.  The hook logs the command (verb plus key arguments such as
  PROGRAM, FILE or STATUSCODE), applies any per-test mock response, sets
  ``EIBRESP`` and the block's ``RESP(...)`` variable, and ends the run on
  ``RETURN`` / ``XCTL`` / ``ABEND`` just as CICS would.
* ``DFHRESP(..)`` / ``DFHVALUE(..)`` become numeric literals and an EIB
  stub is injected into WORKING-STORAGE.
* A test dispatcher is prepended to the PROCEDURE DIVISION.  Each test
  case is a generated paragraph containing the test's COBOL statements
  (typically field setup plus ``PERFORM <paragraph> THRU <exit>``); the
  requested output fields are DISPLAYed when the case finishes.

The original sources are never modified.  All cases registered for a
program are compiled into one executable, and each case runs as its own
process selected by the ``ZT_CASE`` environment variable.
"""

from __future__ import annotations

import functools
import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "Source"
BUILD_DIR = Path(os.environ.get("ZT_BUILD_DIR", ROOT / "build" / "tests"))
COBC = os.environ.get("COBC", "cobc")
COBC_FLAGS = ["-x", "-std=ibm", "-w", "-ftrace", "-fnot-reserved=COL"]
RUN_TIMEOUT = 20

# Values returned by DFHRESP(); these are the documented CICS RESP codes.
DFHRESP = {
    "NORMAL": 0,
    "NOTFND": 13,
    "DUPREC": 14,
    "INVREQ": 16,
    "NOTOPEN": 19,
    "ENDFILE": 20,
    "LENGERR": 22,
    "ENQBUSY": 55,
    "DISABLED": 84,
}

# DFHVALUE() CVDAs are only moved into option fields that are passed back to
# the (mocked) CICS API, so stable distinct stand-in values are sufficient.
DFHVALUE = {
    "IMMEDIATE": 1001,
    "POST": 1002,
    "PUT": 1003,
    "DELETE": 1004,
    "HTTP": 1005,
    "HTTPS": 1006,
    "CLICONVERT": 1007,
    "NOCLICONVERT": 1008,
    "SRVCONVERT": 1009,
    "NOSRVCONVERT": 1010,
}

TERMINAL_VERBS = {"RETURN", "XCTL", "ABEND"}
LOGGED_OPTIONS = (
    "PROGRAM", "FILE", "TRANSID", "QUEUE", "HTTPHEADER", "CONTAINER",
    "STATUSCODE", "COUNTER", "POOL", "URIMAP", "PATH", "RESOURCE",
)
SIMPLE_ARG = re.compile(r"^(?:[A-Z0-9][A-Z0-9_-]*(?:\([A-Z0-9_:+ -]+\))?|'[^']*')$")

EIB_STUB = """\
       01  DFHEIBLK.
           02  EIBTIME            PIC S9(07) COMP-3 VALUE ZEROES.
           02  EIBDATE            PIC S9(07) COMP-3 VALUE ZEROES.
           02  EIBTRNID           PIC  X(04) VALUE 'FA01'.
           02  EIBTASKN           PIC S9(07) COMP-3 VALUE 1234.
           02  EIBTRMID           PIC  X(04) VALUE SPACES.
           02  EIBCPOSN           PIC S9(04) COMP VALUE ZEROES.
           02  EIBCALEN           PIC S9(04) COMP VALUE ZEROES.
           02  EIBAID             PIC  X(01) VALUE SPACES.
           02  EIBFN              PIC  X(02) VALUE LOW-VALUES.
           02  EIBRCODE           PIC  X(06) VALUE LOW-VALUES.
           02  EIBDS              PIC  X(08) VALUE SPACES.
           02  EIBREQID           PIC  X(08) VALUE SPACES.
           02  EIBRSRCE           PIC  X(08) VALUE SPACES.
           02  EIBRESP            PIC S9(08) COMP VALUE ZEROES.
           02  EIBRESP2           PIC S9(08) COMP VALUE ZEROES.
       01  ZT-CONTROL.
           02  ZT-CASE-NO         PIC  9(04) VALUE ZEROES.
           02  ZT-CICS-ID         PIC  9(04) VALUE ZEROES.
           02  ZT-RESP            PIC S9(08) COMP VALUE ZEROES.
           02  ZT-MATCHED         PIC  X(01) VALUE 'N'.
           02  ZT-TERMINAL        PIC  X(01) VALUE 'N'.
           02  ZT-END-REASON      PIC  X(08) VALUE 'DONE'.
           02  ZT-HOOK-COUNT      PIC  9(08) COMP VALUE ZEROES.
           02  ZT-PTR             USAGE POINTER.
           02  ZT-MOCK-LEFT       PIC S9(08) COMP OCCURS 64 TIMES.
"""


class HarnessError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Source loading and preprocessing
# --------------------------------------------------------------------------

def _read(path: Path) -> list[str]:
    return path.read_text(encoding="latin-1").replace("\r", "").split("\n")


def _is_comment(line: str) -> bool:
    return len(line) > 6 and line[6] in "*/"


def _code(line: str) -> str:
    """Program text area (columns 8-72)."""
    return line[7:72] if len(line) > 7 else ""


def _expand_copybooks(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        m = re.match(r"^\s*COPY\s+([A-Z0-9#@$]+)\s*\.\s*$", _code(line))
        if m and not _is_comment(line):
            member = SOURCE_DIR / f"{m.group(1)}.cpy"
            out.append(f"      *ZT  COPY {m.group(1)} expanded inline")
            out.extend(_expand_copybooks(_read(member)))
        else:
            out.append(line)
    return out


def _split_options(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Split the text of an EXEC CICS block into verb words and options."""
    text = re.sub(r"\s+\(", "(", " ".join(text.split()))
    verb: list[str] = []
    opts: list[tuple[str, str]] = []
    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] == " ":
            i += 1
        start = i
        while i < n and text[i] not in " (":
            i += 1
        word = text[start:i]
        if not word:
            break
        arg = ""
        if i < n and text[i] == "(":
            depth, j = 0, i
            in_lit = False
            while j < n:
                ch = text[j]
                if ch == "'":
                    in_lit = not in_lit
                elif not in_lit and ch == "(":
                    depth += 1
                elif not in_lit and ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            arg = text[i + 1:j].strip()
            i = j + 1
            opts.append((word, arg))
        elif not opts:
            verb.append(word)
        else:
            opts.append((word, ""))
    return verb, opts


@dataclass
class CicsBlock:
    id: int
    verb: str
    options: list[tuple[str, str]]
    line: int  # 1-based line in the original program file (0 for copybooks)

    def option(self, name: str) -> str | None:
        for key, value in self.options:
            if key == name:
                return value
        return None


def _resolve_dfh(text: str) -> str:
    def resp(m: re.Match) -> str:
        if m.group(1) not in DFHRESP:
            raise HarnessError(f"unknown DFHRESP({m.group(1)})")
        return str(DFHRESP[m.group(1)])

    def value(m: re.Match) -> str:
        if m.group(1) not in DFHVALUE:
            raise HarnessError(f"unknown DFHVALUE({m.group(1)})")
        return str(DFHVALUE[m.group(1)])

    text = re.sub(r"DFHRESP\(\s*([A-Z0-9]+)\s*\)", resp, text)
    return re.sub(r"DFHVALUE\(\s*([A-Z0-9]+)\s*\)", value, text)


def _stmt(text: str) -> str:
    return " " * 11 + text


def _display_lines(parts: list[str]) -> list[str]:
    out = [_stmt("DISPLAY")]
    for part in parts:
        if part.startswith("'"):
            body = part[1:-1]
            while len(body) > 50:
                out.append(_stmt(f"    '{body[:50]}'"))
                body = body[50:]
            out.append(_stmt(f"    '{body}'"))
        else:
            out.append(_stmt(f"    {part}"))
    return out


def _cics_replacement(block: CicsBlock, period: bool) -> list[str]:
    out = [_stmt(f"MOVE {block.id} TO ZT-CICS-ID")]
    parts = [f"'ZT|CICS|{block.id}|{block.verb}'"]
    for key in LOGGED_OPTIONS:
        arg = block.option(key)
        if arg is not None and SIMPLE_ARG.match(arg):
            parts.append(f"'|{key}='")
            parts.append(arg)
    out.extend(_display_lines(parts))
    terminal = block.verb.split()[0] in TERMINAL_VERBS
    out.append(_stmt(f"MOVE '{'Y' if terminal else 'N'}' TO ZT-TERMINAL"))
    out.append(_stmt("PERFORM ZT-HOOK THRU ZT-HOOK-EXIT"))
    resp = block.option("RESP")
    if resp:
        out.append(_stmt(f"MOVE ZT-RESP TO {resp}"))
    if period:
        out[-1] += "."
    return out


@dataclass
class Prepared:
    program: str
    lines: list[str]
    blocks: list[CicsBlock]
    paragraphs: list[str]
    linkage_items: list[str]


@functools.lru_cache(maxsize=None)
def prepare(program: str) -> Prepared:
    raw = _read(SOURCE_DIR / f"{program}.cbl")
    origin = list(range(1, len(raw) + 1))
    # Expand copybooks while tracking which lines came from the program.
    lines: list[str] = []
    line_no: list[int] = []
    for idx, line in enumerate(raw):
        expanded = _expand_copybooks([line])
        lines.extend(expanded)
        line_no.extend([origin[idx] if len(expanded) == 1 else 0] * len(expanded))

    out: list[str] = []
    blocks: list[CicsBlock] = []
    paragraphs: list[str] = []
    linkage: list[str] = []
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        code = _code(line)
        if _is_comment(line) or not code.strip():
            out.append(line)
            i += 1
            continue
        stripped = code.strip()
        if re.match(r"^CBL\b|^PROCESS\b", stripped):
            out.append("      *ZT  " + stripped)
            i += 1
            continue
        if stripped.startswith("WORKING-STORAGE SECTION"):
            section = "WS"
            out.append(line)
            out.extend(EIB_STUB.rstrip("\n").split("\n"))
            i += 1
            continue
        if stripped.startswith("LINKAGE SECTION"):
            section = "LINKAGE"
        elif stripped.startswith("PROCEDURE DIVISION"):
            section = "PROC"
            out.append(line)
            out.append(_stmt("PERFORM ZT-MAIN THRU ZT-MAIN-EXIT."))
            i += 1
            continue
        if section == "LINKAGE":
            m = re.match(r"^01\s+([A-Z0-9-]+)", stripped)
            if m:
                linkage.append(m.group(1))
        if section == "PROC":
            m = re.match(r"^([A-Z0-9][A-Z0-9-]*)\.$", stripped)
            if m and line[7] != " ":
                paragraphs.append(m.group(1))

        if "EXEC CICS" in code:
            start = i
            if code[: code.index("EXEC CICS")].strip():
                raise HarnessError(f"{program}:{line_no[i]} code before EXEC CICS")
            buf = [code[code.index("EXEC CICS") + len("EXEC CICS"):]]
            while "END-EXEC" not in buf[-1]:
                i += 1
                if not _is_comment(lines[i]):
                    buf.append(_code(lines[i]))
            last = buf[-1]
            tail = last[last.index("END-EXEC") + len("END-EXEC"):].strip()
            if tail not in ("", "."):
                raise HarnessError(f"{program}:{line_no[i]} text after END-EXEC")
            buf[-1] = last[: last.index("END-EXEC")]
            verb, opts = _split_options(_resolve_dfh(" ".join(buf)))
            block = CicsBlock(len(blocks) + 1, " ".join(verb), opts, line_no[start])
            blocks.append(block)
            for j in range(start, i + 1):
                out.append("      *ZT  " + _code(lines[j]).rstrip())
            out.extend(_cics_replacement(block, tail == "."))
            i += 1
            continue

        if stripped.startswith("MOVE FUNCTION") and "DISPLAY-OF" in _code(lines[i + 1]):
            # EBCDIC->ASCII conversion; the harness already runs in ASCII.
            while True:
                out.append("      *ZT  " + _code(lines[i]).rstrip())
                if _code(lines[i]).rstrip().endswith("."):
                    break
                i += 1
            out.append(_stmt("CONTINUE."))
            i += 1
            continue

        out.append(line[:7] + _resolve_dfh(line[7:72]))
        i += 1

    return Prepared(program, out, blocks, paragraphs, linkage)


# --------------------------------------------------------------------------
# Test case model
# --------------------------------------------------------------------------

@dataclass
class Mock:
    """Mocked response for EXEC CICS commands.

    ``verb`` matches the command verb (e.g. ``"READ"``, ``"WEB READ"``).
    ``where`` optionally restricts it to blocks whose option equals a value,
    e.g. ``{"HTTPHEADER": "HTTP-TTL"}``.  ``resp`` is a DFHRESP name or a
    number.  ``times`` limits how often the mock applies (``None`` means
    always).  ``then`` holds COBOL statements executed each time the mock
    fires (used to populate INTO/SET areas).
    """

    verb: str
    resp: str | int = "NORMAL"
    where: dict[str, str] = field(default_factory=dict)
    times: int | None = None
    then: str = ""

    def resp_value(self) -> int:
        return self.resp if isinstance(self.resp, int) else DFHRESP[self.resp]


@dataclass
class Case:
    name: str
    body: str
    outputs: list[str]
    mocks: list[Mock]


@dataclass
class CicsCall:
    id: int
    verb: str
    args: dict[str, str]


@dataclass
class Result:
    stdout: str
    end: str
    out: dict[str, str]
    cics: list[CicsCall]
    displays: list[str]

    def num(self, name: str) -> int:
        value = self.out[name].strip()
        sign = -1 if value.endswith("-") or value.startswith("-") else 1
        digits = re.sub(r"[^0-9]", "", value)
        return sign * int(digits or 0)

    def calls(self, verb: str | None = None, **args: str) -> list[CicsCall]:
        found = []
        for call in self.cics:
            if verb is not None and call.verb != verb:
                continue
            if all(call.args.get(k, "").rstrip() == v for k, v in args.items()):
                found.append(call)
        return found

    @property
    def xctl(self) -> str | None:
        calls = self.calls("XCTL")
        return calls[-1].args.get("PROGRAM", "").strip() if calls else None

    @property
    def status_codes(self) -> list[int]:
        return [int(c.args["STATUSCODE"]) for c in self.cics
                if c.verb == "WEB SEND" and c.args.get("STATUSCODE", "").strip().isdigit()]


def _body_lines(body: str) -> list[str]:
    out = []
    for raw in body.strip("\n").split("\n"):
        text = raw.strip()
        if not text:
            continue
        line = _stmt(text)
        if len(line) > 72:
            raise HarnessError(f"test COBOL line exceeds column 72: {text!r}")
        out.append(line)
    return out


# --------------------------------------------------------------------------
# Program builder / runner
# --------------------------------------------------------------------------

class Program:
    """A zFAM program under test.  Register cases with :meth:`case`."""

    _all: dict[str, "Program"] = {}

    def __init__(self, name: str):
        self.name = name
        self.cases: dict[str, Case] = {}
        self._exe: Path | None = None
        self._exe_cases: tuple[str, ...] = ()
        Program._all[name] = self

    @classmethod
    def get(cls, name: str) -> "Program":
        return cls._all.get(name) or cls(name)

    @property
    def prepared(self) -> Prepared:
        return prepare(self.name)

    def paragraph_exists(self, name: str) -> bool:
        return name in self.prepared.paragraphs

    def case(self, body: str = "", *, perform: str | list[str] | None = None,
             outputs: list[str] | None = None, mocks: list[Mock] | None = None):
        """Decorator turning ``def test_x(r): ...`` into a harness-backed test."""

        def wrap(fn):
            key = f"{fn.__module__}.{fn.__name__}"
            stmts = body
            for target in ([perform] if isinstance(perform, str) else perform or []):
                stmts += "\n" + self._perform(target)
            self._check_mocks(mocks or [])
            self.cases[key] = Case(key, stmts, outputs or [], mocks or [])

            @functools.wraps(fn)
            def test():
                return fn(self.run(key))

            test.__signature__ = __import__("inspect").Signature()
            return test

        return wrap

    def _perform(self, target: str) -> str:
        if target not in self.prepared.paragraphs:
            raise HarnessError(f"{self.name} has no paragraph {target}")
        prefix = target.split("-")[0]
        exit_para = f"{prefix}-EXIT"
        if exit_para in self.prepared.paragraphs:
            return f"PERFORM {target} THRU {exit_para}"
        return f"PERFORM {target}"

    def _check_mocks(self, mocks: list[Mock]) -> None:
        for mock in mocks:
            if not self._mock_block_ids(mock):
                raise HarnessError(f"{self.name}: mock {mock} matches no EXEC CICS block")

    def _mock_block_ids(self, mock: Mock) -> list[int]:
        ids = []
        for block in self.prepared.blocks:
            if block.verb != mock.verb:
                continue
            if all((block.option(k) or "").replace(" ", "") == v.replace(" ", "")
                   for k, v in mock.where.items()):
                ids.append(block.id)
        return ids

    # -- source generation ---------------------------------------------------

    def _generate(self, names: tuple[str, ...]) -> str:
        prep = self.prepared
        lines = list(prep.lines)
        while lines and not lines[-1].strip():
            lines.pop()
        end_program = None
        if lines and "END PROGRAM" in lines[-1]:
            end_program = lines.pop()

        g: list[str] = [""]
        para = lambda name: g.append(f"       {name}.")  # noqa: E731
        para("ZT-MAIN")
        for item in prep.linkage_items:
            g.append(_stmt(f"ALLOCATE LENGTH OF {item} CHARACTERS"))
            g.append(_stmt("    INITIALIZED RETURNING ZT-PTR"))
            g.append(_stmt(f"SET ADDRESS OF {item} TO ZT-PTR"))
        g.append(_stmt("ACCEPT ZT-CASE-NO FROM ENVIRONMENT 'ZT_CASE'"))
        g.append(_stmt("EVALUATE ZT-CASE-NO"))
        for n, _ in enumerate(names, 1):
            g.append(_stmt(f"  WHEN {n} PERFORM ZT-CASE-{n}"))
        g.append(_stmt("  WHEN OTHER DISPLAY 'ZT|NOCASE'"))
        g.append(_stmt("END-EVALUATE"))
        g.append(_stmt("PERFORM ZT-FINISH."))
        para("ZT-MAIN-EXIT")
        g.append(_stmt("EXIT."))

        para("ZT-HOOK")
        g.append(_stmt("ADD 1 TO ZT-HOOK-COUNT"))
        g.append(_stmt("IF ZT-HOOK-COUNT > 200000"))
        g.append(_stmt("    MOVE 'LOOPGUARD' TO ZT-END-REASON"))
        g.append(_stmt("    PERFORM ZT-FINISH"))
        g.append(_stmt("END-IF"))
        g.append(_stmt("MOVE 0 TO ZT-RESP"))
        g.append(_stmt("MOVE 'N' TO ZT-MATCHED"))
        g.append(_stmt("EVALUATE ZT-CASE-NO"))
        for n, name in enumerate(names, 1):
            if self.cases[name].mocks:
                g.append(_stmt(f"  WHEN {n} PERFORM ZT-MOCKS-{n}"))
        g.append(_stmt("  WHEN 9999 CONTINUE"))
        g.append(_stmt("  WHEN OTHER CONTINUE"))
        g.append(_stmt("END-EVALUATE"))
        g.append(_stmt("MOVE ZT-RESP TO EIBRESP"))
        g.append(_stmt("MOVE 0 TO EIBRESP2"))
        g.append(_stmt("IF ZT-TERMINAL = 'Y' AND ZT-RESP = 0"))
        g.append(_stmt("    MOVE 'CICS' TO ZT-END-REASON"))
        g.append(_stmt("    PERFORM ZT-FINISH"))
        g.append(_stmt("END-IF."))
        para("ZT-HOOK-EXIT")
        g.append(_stmt("EXIT."))

        para("ZT-FINISH")
        g.append(_stmt("DISPLAY 'ZT|END|' ZT-END-REASON"))
        g.append(_stmt("EVALUATE ZT-CASE-NO"))
        for n, name in enumerate(names, 1):
            if self.cases[name].outputs:
                g.append(_stmt(f"  WHEN {n} PERFORM ZT-DUMP-{n}"))
        g.append(_stmt("  WHEN 9999 CONTINUE"))
        g.append(_stmt("  WHEN OTHER CONTINUE"))
        g.append(_stmt("END-EVALUATE"))
        g.append(_stmt("STOP RUN."))

        for n, name in enumerate(names, 1):
            case = self.cases[name]
            para(f"ZT-CASE-{n}")
            for m, mock in enumerate(case.mocks, 1):
                left = mock.times if mock.times is not None else 99999999
                g.append(_stmt(f"MOVE {left} TO ZT-MOCK-LEFT({m})"))
            g.extend(_body_lines(case.body) or [_stmt("CONTINUE")])
            g[-1] += "."
            if case.mocks:
                para(f"ZT-MOCKS-{n}")
                for m, mock in enumerate(case.mocks, 1):
                    ids = self._mock_block_ids(mock)
                    cond = " OR ".join(f"ZT-CICS-ID = {i}" for i in ids)
                    g.append(_stmt("IF ZT-MATCHED = 'N'"))
                    g.append(_stmt(f"   AND ZT-MOCK-LEFT({m}) > 0"))
                    for chunk in _wrap_condition(cond):
                        g.append(_stmt(f"   {chunk}"))
                    g.append(_stmt("    MOVE 'Y' TO ZT-MATCHED"))
                    g.append(_stmt(f"    SUBTRACT 1 FROM ZT-MOCK-LEFT({m})"))
                    g.append(_stmt(f"    MOVE {mock.resp_value()} TO ZT-RESP"))
                    for stmt in _body_lines(mock.then):
                        g.append("    " + stmt)
                    g.append(_stmt("END-IF"))
                g.append(_stmt("CONTINUE."))
            if case.outputs:
                para(f"ZT-DUMP-{n}")
                for out in case.outputs:
                    g.extend(_display_lines([f"'ZT|OUT|{out}|'", out]))
                g[-1] += "."

        src = lines + g
        if end_program:
            src.append(end_program)
        return "\n".join(src) + "\n"

    # -- build & run ---------------------------------------------------------

    def build(self) -> Path:
        names = tuple(sorted(self.cases))
        if self._exe is not None and self._exe_cases == names:
            return self._exe
        if shutil.which(COBC) is None:
            raise HarnessError("GnuCOBOL (cobc) is required to run the zFAM tests")
        source = self._generate(names)
        digest = hashlib.sha1((source + " ".join(COBC_FLAGS)).encode()).hexdigest()[:12]
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        src_path = BUILD_DIR / f"{self.name}.cbl"
        exe = BUILD_DIR / f"{self.name}-{digest}"
        src_path.write_text(source, encoding="latin-1")
        if not exe.exists():
            proc = subprocess.run([COBC, *COBC_FLAGS, "-o", str(exe), str(src_path)],
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                raise HarnessError(f"cobc failed for {self.name}:\n{proc.stderr}")
        self._exe, self._exe_cases = exe, names
        return exe

    def run(self, key: str) -> Result:
        exe = self.build()
        number = self._exe_cases.index(key) + 1
        trace = BUILD_DIR / f"{self.name}-{number}.trace"
        env = dict(os.environ, ZT_CASE=str(number), COB_SET_TRACE="Y",
                   COB_TRACE_FILE=str(trace))
        proc = subprocess.run([str(exe)], capture_output=True, text=True,
                              env=env, timeout=RUN_TIMEOUT, encoding="latin-1")
        if trace.exists():
            coverage.record(self.name, trace.read_text(encoding="latin-1"))
            trace.unlink()
        if proc.returncode != 0:
            raise HarnessError(f"{self.name} case {key} failed rc={proc.returncode}:\n"
                               f"{proc.stdout}\n{proc.stderr}")
        return _parse(proc.stdout)


def _wrap_condition(cond: str) -> list[str]:
    words = cond.split(" ")
    chunks, cur = [], "AND ("
    for word in words:
        if len(cur) + len(word) + 1 > 55:
            chunks.append(cur)
            cur = "    "
        cur += ("" if cur.endswith("(") or cur.isspace() else " ") + word
    chunks.append(cur + ")")
    return chunks


def _parse(stdout: str) -> Result:
    end = ""
    out: dict[str, str] = {}
    cics: list[CicsCall] = []
    displays: list[str] = []
    for line in stdout.split("\n"):
        if line.startswith("ZT|CICS|"):
            _, _, ident, rest = line.split("|", 3)
            verb, *pairs = rest.split("|")
            args = {}
            for pair in pairs:
                k, _, v = pair.partition("=")
                args[k] = v
            cics.append(CicsCall(int(ident), verb, args))
        elif line.startswith("ZT|OUT|"):
            _, _, name, value = line.split("|", 3)
            out[name] = value.rstrip()
        elif line.startswith("ZT|END|"):
            end = line[len("ZT|END|"):].strip()
        elif line:
            displays.append(line)
    return Result(stdout, end, out, cics, displays)


# --------------------------------------------------------------------------
# Paragraph coverage (from GnuCOBOL -ftrace output)
# --------------------------------------------------------------------------

class Coverage:
    def __init__(self):
        self.hit: dict[str, set[str]] = {}

    def record(self, program: str, trace: str) -> None:
        hits = self.hit.setdefault(program, set())
        for m in re.finditer(r"Paragraph:\s+([A-Z0-9][A-Z0-9-]*)", trace):
            hits.add(m.group(1))

    def report(self, programs: list[str] | None = None) -> list[tuple[str, int, int]]:
        rows = []
        names = programs or sorted(p.stem for p in SOURCE_DIR.glob("*.cbl"))
        for name in names:
            paras = [p for p in prepare(name).paragraphs if not p.endswith("-EXIT")]
            hit = [p for p in paras if p in self.hit.get(name, set())]
            rows.append((name, len(hit), len(paras)))
        return rows


coverage = Coverage()
