#!/bin/bash
# Compile the Rocq proof of BBi(8) #7 and #8 inside a busycoq checkout (branch BB6 of ccz181078/busycoq).
#   bash build.sh            copies the files of this folder into $BUSYCOQ/verify and compiles them in ORDER
# BUSYCOQ defaults to ~/busycoq-bbi8. The framework files it needs (Individual33.vo and what it imports) must be
# built there first: make Makefile.coq && make -f Makefile.coq Individual33.vo
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DST="${BUSYCOQ:-$HOME/busycoq-bbi8}/verify"
mkdir -p "$DST/BBi8_3x4"
for f in "$SRC"/*.v; do [ -e "$f" ] && tr -d '\r' < "$f" > "$DST/$(basename "$f")"; done
for f in "$SRC"/BBi8_3x4/*.v; do [ -e "$f" ] && tr -d '\r' < "$f" > "$DST/BBi8_3x4/$(basename "$f")"; done
cd "$DST"
for f in $(tr -d '\r' < "$SRC/ORDER"); do
    echo "COQC $f"
    coqc -Q . BusyCoq "$f"
done
echo "BUILD OK"
