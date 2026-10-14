#!/bin/sh
# Build a zFAM CICS COBOL program into a harness executable.
# Usage: build.sh <source.cbl> <program-id> <output>
set -e
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
python3 "$here/cics_preprocess.py" "$1" "$work/prog.cbl"
cobc -c -fstatic-call -Wno-others -I "$here/../Source" -o "$work/prog.o" "$work/prog.cbl"
gcc -DZFAM_PROGRAM="$2" $(cob-config --cflags) -Wno-format-truncation \
    -o "$3" "$here/cics_stub.c" "$work/prog.o" $(cob-config --libs)
