#!/usr/bin/env bash
# Build and check the Baker's Dozen proof from scratch:
#
#   bash build.sh
#
# 1. Fetch busycoq at a pinned commit into ./deps and build its Flip.vo and Individual.vo.
#    Set BUSYCOQ (a busycoq verify/ directory with Flip.vo and Individual.vo built) to use an existing copy instead.
# 2. Copy the .v files to ./build and compile them there in dependency order, then probe.v. Fail unless every
#    Print Assumptions in probe.v is closed. Finally compare build/probe.log with the recorded probe.log.
#
# Needs bash, git, make and Coq 8.20.1 (coqc on PATH). With opam:
#   opam exec --switch=<your 8.20.1 switch> -- bash build.sh
# (Adapted from Jeff Ketchersid's BB12/verify_m12/multifile/compile_clean.sh.)
set -euo pipefail
cd "$(dirname "$0")"

DEPS=${DEPS:-deps}
BUSYCOQ_URL=https://github.com/meithecatte/busycoq
BUSYCOQ_COMMIT=bd2e36f6aa204eb011742d2ca6c8741102b2e59e

version=$(coqc --version | head -n 1)
echo "== $version"
case "$version" in
  *"version 8.20"*) ;;
  *) echo "   warning: the recorded build used Coq 8.20.1" >&2 ;;
esac

if [ -z "${BUSYCOQ:-}" ]; then
  echo "== fetching $BUSYCOQ_URL at ${BUSYCOQ_COMMIT:0:7}"
  if [ ! -d "$DEPS/busycoq/.git" ]; then
    git init --quiet "$DEPS/busycoq"
    git -C "$DEPS/busycoq" remote add origin "$BUSYCOQ_URL"
  fi
  git -C "$DEPS/busycoq" fetch --quiet --depth 1 origin "$BUSYCOQ_COMMIT"
  git -C "$DEPS/busycoq" -c advice.detachedHead=false checkout --quiet "$BUSYCOQ_COMMIT"
  echo "== building busycoq's Flip.vo and Individual.vo"
  start=$SECONDS
  make --no-print-directory -C "$DEPS/busycoq/verify" Flip.vo Individual.vo > "$DEPS/busycoq-make.log" 2>&1 ||
    { tail -n 20 "$DEPS/busycoq-make.log" >&2; exit 1; }
  echo "   ok, $((SECONDS - start)) s"
  BUSYCOQ=$DEPS/busycoq/verify
fi
BUSYCOQ=$(cd "$BUSYCOQ" && pwd)

# Compile in build/ so that deps/ is not under the directory bound to BB8.
echo "== compiling in build/"
mkdir -p build
cp BB132.v Individual132.v BB13_BakersDozen.v BB13_BakersDozen_bound.v probe.v build/
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
