#!/usr/bin/env bash
# preprocess-cics.sh - Preprocess COBOL source files for GnuCOBOL compilation.
#
# Transforms IBM COBOL/CICS source into GnuCOBOL-compatible source by:
#   1. Stripping CRLF line endings
#   2. Removing CBL compiler directive lines
#   3. Replacing EXEC CICS ... END-EXEC blocks with CONTINUE
#   4. Replacing DFHRESP(xxx) calls with stub variable references
#   5. Replacing DFHVALUE(xxx) calls with stub variable references
#   6. Injecting CICS EIB stub copybook into WORKING-STORAGE

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STUBS_DIR="${SCRIPT_DIR}/cics-stubs"

usage() {
    echo "Usage: $0 <input.cbl> <output.cbl>"
    echo "  Preprocesses a COBOL/CICS source file for GnuCOBOL compilation."
    exit 1
}

if [ $# -lt 2 ]; then
    usage
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file not found: $INPUT_FILE" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

# First strip carriage returns, then apply awk preprocessing
tr -d '\r' < "$INPUT_FILE" | awk -v stubs_dir="$STUBS_DIR" '
BEGIN {
    in_exec_cics = 0
    eib_injected = 0
}

# Remove CBL compiler directive lines (e.g., "       CBL CICS(SP)")
/^       CBL / {
    print "      * [PREPROCESSED] " substr($0, 8)
    next
}

# Detect start of EXEC CICS block
/EXEC CICS/ {
    print "      * [CICS] " substr($0, 8)
    if ($0 ~ /END-EXEC/) {
        if ($0 ~ /END-EXEC[[:space:]]*\./) {
            print "           CONTINUE."
        } else {
            print "           CONTINUE"
        }
    } else {
        in_exec_cics = 1
    }
    next
}

# Inside EXEC CICS block - comment out lines until END-EXEC
in_exec_cics == 1 {
    print "      * [CICS] " substr($0, 8)
    if ($0 ~ /END-EXEC/) {
        in_exec_cics = 0
        # Preserve period/no-period from original END-EXEC line
        if ($0 ~ /END-EXEC[[:space:]]*\./) {
            print "           CONTINUE."
        } else {
            print "           CONTINUE"
        }
    }
    next
}

# Replace DFHRESP(xxx) with stub variable DFHRESP-xxx
/DFHRESP\(/ {
    line = $0
    while (match(line, /DFHRESP\([A-Z]+\)/)) {
        prefix = substr(line, 1, RSTART - 1)
        matched = substr(line, RSTART, RLENGTH)
        suffix = substr(line, RSTART + RLENGTH)
        gsub(/DFHRESP\(/, "", matched)
        gsub(/\)/, "", matched)
        line = prefix "DFHRESP-" matched suffix
    }
    $0 = line
}

# Replace DFHVALUE(xxx) with stub variable DFHVALUE-xxx
/DFHVALUE\(/ {
    line = $0
    while (match(line, /DFHVALUE\([A-Z]+\)/)) {
        prefix = substr(line, 1, RSTART - 1)
        matched = substr(line, RSTART, RLENGTH)
        suffix = substr(line, RSTART + RLENGTH)
        gsub(/DFHVALUE\(/, "", matched)
        gsub(/\)/, "", matched)
        line = prefix "DFHVALUE-" matched suffix
    }
    $0 = line
}

# Comment out IBM-specific FUNCTION DISPLAY-OF / NATIONAL-OF blocks
# These are multi-line MOVE statements for EBCDIC/ASCII conversion.
# Pattern: MOVE FUNCTION / DISPLAY-OF / (FUNCTION NATIONAL-OF / (...) / TO ...
/MOVE FUNCTION[[:space:]]*$/ {
    ibm_func_line = $0
    ibm_func_buf = ""
    ibm_func_active = 1
    next
}
ibm_func_active == 1 {
    ibm_func_buf = ibm_func_buf "\n" $0
    if ($0 ~ /\.$/) {
        # End of statement - comment out the whole block
        print "      * [IBM-FUNC] " substr(ibm_func_line, 8)
        n = split(ibm_func_buf, lines, "\n")
        for (i = 1; i <= n; i++) {
            if (lines[i] != "") {
                print "      * [IBM-FUNC] " substr(lines[i], 8)
            }
        }
        print "           CONTINUE."
        ibm_func_active = 0
    }
    next
}

# Rename COL variable to WS-COL (COL is reserved in GnuCOBOL)
# Must handle: variable declarations, references, and reference modifications
{
    # Match COL as a standalone word (not part of COLUMN etc.)
    # Boundaries: space, (, ), :, .
    while (match($0, /(^|[[:space:](,:.])COL([[:space:]).,(:]|$)/)) {
        prefix_len = 0
        if (substr($0, RSTART, 1) != "C") prefix_len = 1
        before = substr($0, 1, RSTART - 1 + prefix_len)
        after = substr($0, RSTART + prefix_len + 3)
        $0 = before "WS-COL" after
    }
}

# Inject EIB stub after WORKING-STORAGE SECTION header
/WORKING-STORAGE SECTION/ && eib_injected == 0 {
    print $0
    print ""
    print "      * [PREPROCESSED] CICS EIB stub fields injected below"
    while ((getline stubline < (stubs_dir "/DFHEIBLK.cpy")) > 0) {
        print stubline
    }
    close(stubs_dir "/DFHEIBLK.cpy")
    print ""
    while ((getline stubline < (stubs_dir "/DFHRESP.cpy")) > 0) {
        print stubline
    }
    close(stubs_dir "/DFHRESP.cpy")
    print ""
    while ((getline stubline < (stubs_dir "/DFHVALUE.cpy")) > 0) {
        print stubline
    }
    close(stubs_dir "/DFHVALUE.cpy")
    print ""
    eib_injected = 1
    next
}

# Pass through all other lines
{ print }
' > "$OUTPUT_FILE"

echo "Preprocessed: $INPUT_FILE -> $OUTPUT_FILE"
