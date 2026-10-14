#!/usr/bin/env python3
"""Translate a zFAM CICS COBOL program into plain GnuCOBOL.

This is a minimal stand-in for the CICS translator, used only to run zFAM
programs under the local test harness.  Each EXEC CICS command is replaced
with a CALL to a C function in cics_stub.c, the EIB and DFHCOMMAREA are added
to the PROCEDURE DIVISION USING list, and 31-bit address arithmetic fields
(PIC S9(08) COMP redefining a POINTER) are widened to 64-bit native binary.
"""
import re
import sys

DFHRESP = {"NORMAL": 0, "NOTFND": 13, "ENDFILE": 20, "LENGERR": 22}
DFHVALUE = {"IMMEDIATE": 1}

EIB = """       01  DFHEIBLK.
           02  EIBTRNID           PIC  X(04).
           02  EIBRESP            PIC S9(08) COMP-5.
           02  EIBRESP2           PIC S9(08) COMP-5.
"""

# command -> (C entry point, ordered argument options, flag options)
COMMANDS = {
    "GETMAIN": ("CICSGETMAIN", ["SET", "FLENGTH", "INITIMG"], []),
    "WEB READ": ("CICSWEBREAD",
                 ["HTTPHEADER", "NAMELENGTH", "VALUE", "VALUELENGTH", "RESP"],
                 []),
    "WEB WRITE": ("CICSWEBWRITE",
                  ["HTTPHEADER", "NAMELENGTH", "VALUE", "VALUELENGTH"], []),
    "WEB SEND": ("CICSWEBSEND",
                 ["FROM", "DOCTOKEN", "FROMLENGTH", "MEDIATYPE", "STATUSCODE",
                  "STATUSTEXT", "STATUSLEN"],
                 ["SRVCONVERT", "NOSRVCONVERT"]),
    "STARTBR": ("CICSSTARTBR", ["FILE", "RIDFLD"], ["GTEQ"]),
    "READ": ("CICSREAD", ["FILE", "INTO", "RIDFLD", "LENGTH"], ["GTEQ"]),
    "READNEXT": ("CICSREADNEXT", ["FILE", "INTO", "RIDFLD", "LENGTH"], []),
    "READPREV": ("CICSREADPREV", ["FILE", "INTO", "RIDFLD", "LENGTH"], []),
    "LINK": ("CICSLINK", ["PROGRAM", "COMMAREA"], []),
    "RETURN": ("CICSRETURN", [], []),
}
NOOPS = {"DOCUMENT", "ENTER", "ASKTIME", "FORMATTIME", "WRITEQ"}

# FUNCTION DISPLAY-OF/NATIONAL-OF with CCSIDs is not supported by GnuCOBOL.
ASCII_RE = re.compile(
    r"MOVE\s+FUNCTION\s+DISPLAY-OF\s+\(FUNCTION\s+NATIONAL-OF\s+"
    r"\((\S+?),\s*EBCDIC-CCSID\)\s*ASCII-CCSID\)\s+TO\s+[^\s.]+", re.S)
EXEC_RE = re.compile(r"EXEC\s+CICS\s+(.*?)\s*END-EXEC(\.?)", re.S)
OPTION_RE = re.compile(r"([A-Z0-9-]+)\s*(?:\(\s*([^)]*?)\s*\))?")


def translate_exec(match):
    body, period = match.group(1), match.group(2)
    words = body.split()
    verb = words[0]
    if verb in NOOPS:
        return "CONTINUE" + period
    name = " ".join(words[:2]) if verb == "WEB" else verb
    entry, arg_names, flag_names = COMMANDS[name]
    rest = body.split(None, len(name.split()))[-1] if len(words) > len(
        name.split()) else ""
    options = {}
    for opt, arg in OPTION_RE.findall(rest):
        options[opt] = arg
    using = []
    for arg in arg_names:
        using.append(options[arg] if options.get(arg) else "OMITTED")
    flag = next((f for f in flag_names if f in options), "")
    parts = [f"CALL '{entry}' USING"]
    parts += [f"BY REFERENCE {a}" for a in using]
    if flag_names:
        parts.append(f"BY CONTENT '{flag:<12}'")
    if not using and not flag_names:
        parts = [f"CALL '{entry}'"]
    lines = ["CALL" + parts[0][4:]] + ["                " + p for p in parts[1:]]
    return "\n".join(lines) + period


def preprocess(src):
    src = src.replace("\r\n", "\n")
    lines = src.split("\n")
    if lines and lines[0].lstrip().startswith("CBL"):
        lines = lines[1:]
    src = "\n".join(lines)
    src = re.sub(r"(REDEFINES\s+\S+-ADDRESS\s+PIC\s+)S9\(08\)\s+COMP\b",
                 r"\1S9(18) COMP-5", src)
    src = re.sub(r"DFHRESP\((\w+)\)", lambda m: str(DFHRESP[m.group(1)]), src)
    src = re.sub(r"DFHVALUE\((\w+)\)", lambda m: str(DFHVALUE[m.group(1)]),
                 src)
    src = src.replace("       LINKAGE SECTION.\n",
                      "       LINKAGE SECTION.\n" + EIB, 1)
    src = src.replace("       PROCEDURE DIVISION.",
                      "       PROCEDURE DIVISION USING DFHEIBLK DFHCOMMAREA.",
                      1)
    src = ASCII_RE.sub(
        r"CALL 'ZFAMASCII' USING\n                BY REFERENCE \1\n"
        r"                BY REFERENCE FIELD-LENGTH", src)
    return EXEC_RE.sub(translate_exec, src)


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        out = preprocess(f.read())
    with open(sys.argv[2], "w") as f:
        f.write(out)
