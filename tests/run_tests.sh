#!/usr/bin/env bash
# run_tests.sh - Test suite for zFAM COBOL build system.
#
# Tests cover:
#   1. Preprocessor correctness (CICS removal, stub injection)
#   2. Syntax validation of all COBOL programs
#   3. Full compilation of all COBOL programs
#   4. Copybook integrity checks
#   5. Source structure validation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

pass() {
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
    echo "  PASS  $1"
}

fail() {
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "  FAIL  $1"
    if [ -n "${2:-}" ]; then
        echo "        $2"
    fi
}

echo "========================================"
echo " zFAM Test Suite"
echo "========================================"
echo ""

# --- Test Group 1: Preprocessor Tests ---
echo "--- Preprocessor Tests ---"

cd "$PROJECT_DIR"

# Ensure preprocessed files exist
make -s build/preprocessed/ZFAM000.cbl 2>/dev/null

# Test 1.1: CBL directive is removed
if grep -q '\* \[PREPROCESSED\] CBL' build/preprocessed/ZFAM000.cbl; then
    pass "CBL directive commented out in preprocessed output"
else
    fail "CBL directive not handled" "Expected CBL line to be commented"
fi

# Test 1.2: EXEC CICS blocks are replaced (check non-comment lines only)
if ! grep -v '^      \*' build/preprocessed/ZFAM000.cbl | grep -q "EXEC CICS"; then
    pass "EXEC CICS blocks removed from active code"
else
    fail "EXEC CICS blocks still present" "Found raw EXEC CICS in non-comment line"
fi

# Test 1.3: CICS blocks are commented
if grep -q '\* \[CICS\]' build/preprocessed/ZFAM000.cbl; then
    pass "EXEC CICS blocks preserved as comments"
else
    fail "EXEC CICS blocks not commented" "Expected [CICS] comment markers"
fi

# Test 1.4: CONTINUE statements replace EXEC CICS
CONTINUE_COUNT=$(grep -c "CONTINUE" build/preprocessed/ZFAM000.cbl || true)
CICS_COUNT=$(grep -c "EXEC CICS" Source/ZFAM000.cbl || true)
if [ "$CONTINUE_COUNT" -ge "$CICS_COUNT" ]; then
    pass "CONTINUE replaces EXEC CICS ($CONTINUE_COUNT CONTINUE vs $CICS_COUNT EXEC CICS)"
else
    fail "Not enough CONTINUE replacements" "Got $CONTINUE_COUNT, expected >= $CICS_COUNT"
fi

# Test 1.5: EIB stub is injected
if grep -q "DFHEIBLK" build/preprocessed/ZFAM000.cbl; then
    pass "EIB stub (DFHEIBLK) injected into WORKING-STORAGE"
else
    fail "EIB stub not injected" "DFHEIBLK not found in preprocessed output"
fi

# Test 1.6: DFHRESP replaced with stub variables
if grep -q "DFHRESP-NORMAL" build/preprocessed/ZFAM000.cbl && \
   ! grep -q "DFHRESP(NORMAL)" build/preprocessed/ZFAM000.cbl; then
    pass "DFHRESP() calls replaced with stub variables"
else
    fail "DFHRESP() not replaced" "Expected DFHRESP-NORMAL, not DFHRESP(NORMAL)"
fi

# Test 1.7: DFHVALUE replaced with stub variables
make -s build/preprocessed/ZFAM002.cbl 2>/dev/null
if grep -q "DFHVALUE-" build/preprocessed/ZFAM002.cbl 2>/dev/null; then
    pass "DFHVALUE() calls replaced with stub variables"
else
    fail "DFHVALUE() not replaced"
fi

# Test 1.8: COL reserved word renamed
make -s build/preprocessed/ZFAM011.cbl 2>/dev/null
if grep -q "WS-COL" build/preprocessed/ZFAM011.cbl && \
   ! grep -v '^      \*' build/preprocessed/ZFAM011.cbl | grep -qP '(?<![-\w])COL(?![-\w])'; then
    pass "COL reserved word renamed to WS-COL"
else
    fail "COL reserved word not fully renamed"
fi

# Test 1.9: CRLF stripped from preprocessed output
if ! file build/preprocessed/ZFAM000.cbl | grep -q "CRLF"; then
    pass "CRLF line endings stripped from preprocessed output"
else
    fail "CRLF not stripped" "Preprocessed file still has Windows line endings"
fi

echo ""

# --- Test Group 2: Syntax Validation ---
echo "--- Syntax Validation ---"

COBOL_SRCS="ZFAM000 ZFAM002 ZFAM003 ZFAM004 ZFAM005 ZFAM007 ZFAM008 ZFAM009 ZFAM011 ZFAM031 ZFAM090 ZFAM101 ZFAM102 ZFAMPLT"

for prog in $COBOL_SRCS; do
    make -s "build/preprocessed/${prog}.cbl" 2>/dev/null
    if cobc -fsyntax-only -std=default -w -I build/copybooks -I build/cics-stubs "build/preprocessed/${prog}.cbl" 2>/dev/null; then
        pass "Syntax check: $prog"
    else
        fail "Syntax check: $prog" "$(cobc -fsyntax-only -std=default -w -I build/copybooks -I build/cics-stubs "build/preprocessed/${prog}.cbl" 2>&1 | head -1)"
    fi
done

echo ""

# --- Test Group 3: Full Compilation ---
echo "--- Full Compilation ---"

make -s clean 2>/dev/null
if make -s all 2>/dev/null; then
    pass "Full compilation of all 14 programs"
else
    fail "Full compilation" "make all returned non-zero"
fi

# Verify object files were created
OBJ_COUNT=$(ls build/obj/*.o 2>/dev/null | wc -l || true)
if [ "$OBJ_COUNT" -eq 14 ]; then
    pass "All 14 object files generated"
else
    fail "Object file count" "Expected 14, got $OBJ_COUNT"
fi

echo ""

# --- Test Group 4: Copybook Integrity ---
echo "--- Copybook Integrity ---"

# Test 4.1: All required copybooks exist
REQUIRED_CPYS="ZFAMFKC ZFAMFFC ZFAMHEX ZFAMCIC"
for cpy in $REQUIRED_CPYS; do
    if [ -f "Source/${cpy}.cpy" ]; then
        pass "Copybook exists: ${cpy}.cpy"
    else
        fail "Copybook missing: ${cpy}.cpy"
    fi
done

# Test 4.2: Copybooks have valid record definitions
if grep -q "FK-RECORD" Source/ZFAMFKC.cpy; then
    pass "ZFAMFKC defines FK-RECORD (key store layout)"
else
    fail "ZFAMFKC missing FK-RECORD definition"
fi

if grep -q "FF-RECORD" Source/ZFAMFFC.cpy; then
    pass "ZFAMFFC defines FF-RECORD (file store layout)"
else
    fail "ZFAMFFC missing FF-RECORD definition"
fi

echo ""

# --- Test Group 5: Source Structure ---
echo "--- Source Structure ---"

# Test 5.1: All programs have PROGRAM-ID
for prog in $COBOL_SRCS; do
    if grep -q "PROGRAM-ID" "Source/${prog}.cbl"; then
        pass "PROGRAM-ID present: $prog"
    else
        fail "PROGRAM-ID missing: $prog"
    fi
done

echo ""

# --- Summary ---
echo "========================================"
echo " Results: $PASS passed, $FAIL failed (of $TOTAL)"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi

exit 0
