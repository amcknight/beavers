#!/usr/bin/env bash
# Build and check the Baker's Dozen proof from scratch:
#
#   bash build.sh
#
# 1. Fetch Jeff Ketchersid's busy-beaver repository and busycoq, each at a pinned commit, into ./deps.
#    Set BUSY_BEAVER (a busy-beaver checkout) or BUSYCOQ (a busycoq verify/ directory with Flip.vo and
#    Individual.vo built) to use an existing copy instead.
# 2. Build busycoq's Flip.vo and Individual.vo.
# 3. Assemble BB132.v, Individual132.v, BB13_BakersDozen.v and BB13_BakersDozen_bound.v into ./build from
#    the .v.in templates and Jeff's files (assemble.py), checking every SHA-256.
# 4. Compile those four files in ./build, then probe.v, and fail unless every Print Assumptions in probe.v
#    is closed. Finally compare build/probe.log with the recorded probe.log.
#
# Needs bash, git, make, python3 and Coq 8.20.1 (coqc and coq_makefile on PATH). With opam:
#   opam exec --switch=<your 8.20.1 switch> -- bash build.sh
set -euo pipefail
cd "$(dirname "$0")"

DEPS=${DEPS:-deps}
JEFF_URL=https://github.com/jeff87654/busy-beaver
JEFF_COMMIT=f7975bf527c92fb25e10ad4c72cb81da30d044a1
BUSYCOQ_URL=https://github.com/meithecatte/busycoq
BUSYCOQ_COMMIT=bd2e36f6aa204eb011742d2ca6c8741102b2e59e

fetch() {  # url dir commit: a shallow checkout of that one commit
  if [ ! -d "$2/.git" ]; then
    git init --quiet "$2"
    git -C "$2" remote add origin "$1"
  fi
  git -C "$2" fetch --quiet --depth 1 origin "$3"
  git -C "$2" -c advice.detachedHead=false checkout --quiet "$3"
}

version=$(coqc --version | head -n 1)
echo "== $version"
case "$version" in
  *"version 8.20"*) ;;
  *) echo "   warning: the recorded build used Coq 8.20.1" >&2 ;;
esac

if [ -z "${BUSY_BEAVER:-}" ]; then
  echo "== fetching $JEFF_URL at ${JEFF_COMMIT:0:7}"
  fetch "$JEFF_URL" "$DEPS/busy-beaver" "$JEFF_COMMIT"
  BUSY_BEAVER=$DEPS/busy-beaver
fi
if [ -z "${BUSYCOQ:-}" ]; then
  echo "== fetching $BUSYCOQ_URL at ${BUSYCOQ_COMMIT:0:7}"
  fetch "$BUSYCOQ_URL" "$DEPS/busycoq" "$BUSYCOQ_COMMIT"
  echo "== building busycoq's Flip.vo and Individual.vo"
  start=$SECONDS
  make --no-print-directory -C "$DEPS/busycoq/verify" Flip.vo Individual.vo > "$DEPS/busycoq-make.log" 2>&1 ||
    { tail -n 20 "$DEPS/busycoq-make.log" >&2; exit 1; }
  echo "   ok, $((SECONDS - start)) s"
  BUSYCOQ=$DEPS/busycoq/verify
fi
BUSYCOQ=$(cd "$BUSYCOQ" && pwd)

echo "== assembling"
python3 assemble.py "$BUSY_BEAVER"

echo "== compiling in build/"
cp probe.v build/
cd build
rm -f ./*.vo ./*.vok ./*.vos ./*.glob ./.*.aux
# The logical path BB8 is the one Jeff's BB132.v and Individual132.v expect.
for f in BB132 Individual132 BB13_BakersDozen BB13_BakersDozen_bound; do
  start=$SECONDS
  coqc -Q "$BUSYCOQ" BusyCoq -Q . BB8 "$f.v"
  echo "   $f.v ok, $((SECONDS - start)) s"
done

echo "== probe"
coqc -Q "$BUSYCOQ" BusyCoq -Q . BB8 probe.v > probe.log
closed=$(grep -c 'Closed under the global context' probe.log || true)
total=$(grep -c '^Print Assumptions' probe.v || true)
if grep -q 'Axioms:' probe.log; then
  echo "   AXIOMS FOUND, see build/probe.log" >&2
  exit 1
fi
echo "   $closed of $total Print Assumptions closed under the global context (main theorems and rules)"
[ "$closed" = "$total" ]
if cmp -s probe.log ../probe.log; then
  echo "   build/probe.log is identical to the recorded probe.log"
else
  echo "   note: build/probe.log differs from the recorded probe.log"
fi
echo "== done"
