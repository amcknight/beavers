#!/usr/bin/env python3
"""Independent checker for one cell of the BBi tracker, at any depth D from 1 to 19.

Written from CHECKING.md alone, with the standard library only. It rebuilds the cell's corridor walk, runs every
halter to its halt, verifies every certificate in the claims file and compares its own totals with summary.json
(CHECKING.md section 9). When the cell has claims.idx, it reads each group's claims alongside that group's walk
instead, so a certified machine is never run to the depth's bound ("When claims.idx exists"). --plain keeps the
first way. It checks cells of format bbi9-cell/1, bbi9-cell/2, which adds the NONHALT_CPS certificate, bbi9-cell/3,
which adds the NONHALT_RWL certificate, bbi9-cell/4, which adds the NONHALT_FAR certificate, and bbi9-cell/5, which
adds the NONHALT_CPSH certificate. For each NONHALT_CPS claim it computes the sets Lw, Rw and C that section 6 defines,
for each NONHALT_RWL claim the set C of repeated word lists, for each NONHALT_FAR claim the relation R that the machine
and the claim's automaton fix, with rule 4 applied until nothing changes, and then the set a, at every automaton
state, and for each NONHALT_CPSH claim NONHALT_CPS's sets for the history machine M_H, by a closure of its own whose
instructions come from each symbol's base and whose 0 is the blank (0, ()). Section 6's limits are one block of
constants, named as its limits table names them. The indexed check's groups are walked by bbi9check-core, the
compiled core in core/, when it is built, and --python walks them with the Python code, the reference.

A cell may hold an amendment, which reruns its holdouts (section 12). The full check then leaves the holdout lists to
the amendment check when amend.json amends this very summary.json, and --amend is the amendment check. It rests on a
passing check.json, reads the claims file only to count, digest and collect its UNKNOWN texts, verifies every line of
amend.tsv with the certificates its claims_format, bbi9-cell/2 to bbi9-cell/5, allows, and compares amend.json's
counts, the shorter holdout lists and the census rule.

A cell may also hold an import, which marks the holdouts that other people's holdout lists decide (section 13), and
--import is the import check. It rests on the passing full check and amendment check, reads the registry with PyYAML
(the one library beyond the standard library, imported by the import check alone) and every list file it names,
classifies each list's lines by the cell's claims, computes the normal-form map of each imported machine and compares
import.json, import.tsv and the two after-lists files with its own values. A line of import.tsv gives its machine one
of two verdicts, DECIDED_LIST when the list leaves out its map, and NONHALT_PROVEN when it has run past the proven
value that a registry entry records for its domain.

    python bbi9check.py CELL_DIR --census CENSUS_TSV [--jobs N] [--plain | [--gpu] [--python]]
    python bbi9check.py CELL_DIR --amend --census CENSUS_TSV [--jobs N]
    python bbi9check.py CELL_DIR --import --census CENSUS_TSV --lists LISTS_YAML [--data DIR] [--jobs N]

Exit codes: 0 pass, 1 fail, 2 bad usage, 3 bbi9check-core failed.
"""

from __future__ import annotations

import argparse
import codecs
import functools
import gzip
import hashlib
import json
import multiprocessing
import os
import re
import struct
import subprocess
import sys
import threading
import time
import zlib
from array import array
from bisect import insort
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from operator import methodcaller
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import IO, Any, Callable, Iterable, Iterator, Optional, Sequence

CHECKER = "bbi9check 1.10"
# --gpu (section 9, "An accelerated checker"): the UNKNOWN claims' runs are deferred by _use_claim and done in batches on
# the GPU by _gpu_bound_runs after the walk. Set in every process by _set_gpu, as pool workers are spawned.
_GPU = False
GPU_SUFFIX = " gpu"  # appended to CHECKER in a check.json the accelerated checker wrote


def _set_gpu(flag: bool) -> None:
    global _GPU
    _GPU = flag


# Contract limits: CHECKING.md section 6's limits table, the same names with the same values
MAX_CAP = 10_000_000  # section 9 steps 1 and 3: the producer's largest cap, and so the largest j and bound
CPS_MAX_N = 5  # section 6: NONHALT_CPS has 1 <= n <= 5
CPS_MAX_C = 20_000  # section 6: NONHALT_CPS has 1 <= c <= 20,000
RWL_MAX_B = 6  # section 6: NONHALT_RWL has 1 <= b <= 6
RWL_MAX_T = 3  # section 6: NONHALT_RWL has 1 <= T <= 3
RWL_MAX_C = 20_000  # section 6: NONHALT_RWL has 1 <= c <= 20,000
RWL_BLOCK_STEPS = 1_000  # section 6: a block run must leave its block within 1,000 steps
FAR_MAX_N = 10  # section 6: NONHALT_FAR has 1 <= n <= 10
FAR_MAX_E = 102_010  # section 6: NONHALT_FAR has 1 <= e <= 102,010
CPSH_MAX_N = 5  # section 6: NONHALT_CPSH has 1 <= n <= 5
CPSH_MAX_H = 12  # section 6: NONHALT_CPSH has 1 <= H <= 12
CPSH_MAX_C = 20_000  # section 6: NONHALT_CPSH has 1 <= c <= 20,000
# End of the contract limits

FORMAT_1 = "bbi9-cell/1"
FORMAT_2 = "bbi9-cell/2"  # section 5: format 1 with the NONHALT_CPS certificate added
FORMAT_3 = "bbi9-cell/3"  # section 5: format 2 with the NONHALT_RWL certificate added
FORMAT_4 = "bbi9-cell/4"  # section 5: format 3 with the NONHALT_FAR certificate added
FORMAT_5 = "bbi9-cell/5"  # section 5: format 4 with the NONHALT_CPSH certificate added
SUMMARY_FORMATS = (FORMAT_1, FORMAT_2, FORMAT_3, FORMAT_4, FORMAT_5)  # format k is SUMMARY_FORMATS[k - 1]
SUMMARY_NAMED = ", ".join(repr(f) for f in SUMMARY_FORMATS[:-1]) + f" or {SUMMARY_FORMATS[-1]!r}"
CHECK_FORMAT = "bbi9-check/1"
CPS = "NONHALT_CPS"
RWL = "NONHALT_RWL"
FAR = "NONHALT_FAR"
CPSH = "NONHALT_CPSH"
SINCE = {CPS: 2, RWL: 3, FAR: 4, CPSH: 5}  # section 5: the first format with each of these certificates
CAP_SHALLOW = 4_000_000  # section 8: census cap for an ancestor at depths 0 to 7
CAP_DEPTH8 = 100_000  # section 8: census cap for an ancestor at depth 8 or deeper
LIMIT = 9  # section 3: w and t never exceed 9
MAX_STATES = 10  # states A to J
MAX_SYMBOLS = 10  # symbols 0 to 9
MAX_DEPTH = 19  # section 4: D from 1 to 19
MAX_CELL_STATES = 9  # sections 3 and 4: S from 1 to 9, since targets stop at J
CENSUS_DEPTH = 9  # section 8: the census counts depths 0 to 9 and has no count past them
SPLIT_DEPTH = 4  # with --jobs, the walk hands the subtrees below this depth to the pool
GROUPS_PER_JOB = 16
CHUNK_LINES = 20_000  # claims lines per pool task
INDEX_HEADER = "group\tseq\toffset\tbytes\tlines"  # section 5: the first line of claims.idx
TOP_GROUP = "top"  # section 5: the group of the claims at depths below claims_split
BATCH_GROUPS = 32  # with claims.idx, the groups per pool task
PROGRESS_SECS = 30  # seconds between the indexed check's progress lines on stderr
PROGRESS_THREAD = "bbi9check progress"  # the name of the thread that prints them
READ_BYTES = 1 << 15  # compressed bytes fed to the decompressor at a time, so memory never grows with the claims
MAX_DIGITS = 18  # a claims.idx count with more digits is refused rather than converted
TOP = 10
MAX_FAILURES = 50
VERDICTS = ("NONHALT_CYCLER", "NONHALT_TRANSLATED", CPS, RWL, FAR, CPSH, "UNKNOWN")
# The counts every corridor entry has. Each key of SINCE is also a count of every entry from its format on, and an
# older entry must not have it: NONHALT_CPS from format 2, NONHALT_RWL from 3, NONHALT_FAR from 4 and NONHALT_CPSH
# from 5.
ENTRY_KEYS = ("machines", "HALT", "NONHALT_CYCLER", "NONHALT_TRANSLATED", "UNKNOWN", "max_halt_steps")
OWN_KEYS = ("halter_digest", "claims", "claims_digest", "cell_machines", "late_cell_machines", "holdouts",
            "parent_holdouts", "top_halters")
MASK = (1 << 64) - 1
# Amendments (section 12)
AMEND_FORMAT = "bbi9-amend/1"
AMEND_CHECK_FORMAT = "bbi9-amend-check/1"
AMEND_KEYS = ("format", "cell", "depth", "base_summary_sha256", "claims_format", "corridor", "holdouts",
              "parent_holdouts", "amended", "amend_digest")  # the keys of amend.json a checker uses, all required
CLAIMS_FORMATS = (FORMAT_2, FORMAT_3, FORMAT_4, FORMAT_5)  # the claims_format values amend.json may have
CLAIMS_NAMED = ", ".join(repr(f) for f in CLAIMS_FORMATS[:-1]) + f" or {CLAIMS_FORMATS[-1]!r}"
CERTIFICATES = ("NONHALT_CYCLER", "NONHALT_TRANSLATED", CPS, RWL, FAR, CPSH)
SCAN_READ = 1 << 16  # compressed bytes read at a time by the claims scan
SCAN_BLOCK = 1 << 20  # the claims scan hashes blocks of whole lines of about this many bytes
SCAN_TASK = 1 << 20  # with claims.idx, the compressed bytes of claims.tsv.gz per pool task of the claims scan
AMEND_CHUNK = 64  # amend.tsv lines per pool task, few because one certificate may build a large C
DIGITS = "0123456789"
LETTERS = "ABCDEFGHIJ"
# Imports (section 13)
IMPORT_FORMAT = "bbi9-import/2"
IMPORT_CHECK_FORMAT = "bbi9-import-check/1"
IMPORT_KEYS = ("format", "cell", "depth", "base_summary_sha256", "base_amend_sha256", "lists", "decided",
               "never_halts", "maker_holdouts", "maker_holdouts_by_list", "strangers", "holdouts", "parent_holdouts",
               "imported", "import_digest")  # the keys of import.json a checker uses, all required
DECIDED = "DECIDED_LIST"
NEVER = "NONHALT_PROVEN"  # the verdict of a machine run past a registered proven value
REQUIRED = ("id", "label", "credit", "domain", "file", "sha256", "entries", "complete")  # of an entry that decides
LIST_KEYS = ("credit", "entry_sha256", "id", "label", "sha256", "speaks")  # of an object of import.json's lists
LINE_SPACE = " \t\f\v"  # whitespace around and inside a line of a list file. CR and LF end lines.
LIST_READ = 1 << 22  # bytes of a list file read at a time

# A table is flat, indexed by state * width + symbol. A defined entry is (w, move, next_state * width) with move
# -1 for L and +1 for R. An undefined entry is None.
Instruction = tuple[int, int, int]
Table = list[Optional[Instruction]]
# A walk node: (depth, table, rows, s, k, T, late). rows[q] is state q's row text at the cell's full width K, and T is
# the largest state index used as an owner or a target.
Node = tuple[int, Table, list[str], int, int, int, bool]


# ---------------------------------------------------------------------------------------------------------------------
# Digests (section 7)

_UNPACK = struct.Struct(">Q").unpack_from


def _h(data: bytes) -> int:
    """h(x): the first 8 bytes of the SHA-256 of x, as a big-endian unsigned integer."""
    return _UNPACK(hashlib.sha256(data).digest())[0]


def _hex(total: int) -> str:
    return format(total & MASK, "016x")


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def multiset_digest(lines: Iterable[str]) -> str:
    """The digest of a multiset of lines (each given without its newline)."""
    return _hex(sum(_h(x.encode("utf-8")) for x in lines))


# ---------------------------------------------------------------------------------------------------------------------
# Machines and runs (sections 1 and 2)


@dataclass(frozen=True)
class Machine:
    table: Table
    width: int  # symbols per state in the table
    depth: int  # defined pairs


def parse_text(text: str) -> Machine:
    """Parse a machine text. Raises ValueError when the text is not one."""
    if text == "":
        return Machine([None], 1, 0)
    rows = text.split("_")
    n = len(rows[0])
    if n == 0 or n % 3:
        raise ValueError(f"row length {n} is not a positive multiple of 3")
    k = n // 3
    defined: list[tuple[int, int, int, int, int]] = []
    max_w = max_t = 0
    for q, row in enumerate(rows):
        if len(row) != n:
            raise ValueError("rows differ in length")
        for r in range(k):
            cell = row[3 * r:3 * r + 3]
            if cell == "---":
                continue
            w, t, m = DIGITS.find(cell[0]), LETTERS.find(cell[2]), cell[1]
            if w < 0 or t < 0 or m not in ("L", "R"):
                raise ValueError(f"bad cell {cell!r}")
            defined.append((q, r, w, 1 if m == "R" else -1, t))
            max_w, max_t = max(max_w, w), max(max_t, t)
    width = max(k, max_w + 1)
    table: Table = [None] * (max(len(rows), max_t + 1) * width)
    for q, r, w, move, t in defined:
        table[q * width + r] = (w, move, t * width)
    return Machine(table, width, len(defined))


def _run(table: Table, limit: int) -> tuple[bool, int, int, int]:
    """Run from the blank tape for at most limit steps.

    Returns (halted, steps, state * width, symbol). halted is True when the machine halts after steps <= limit steps,
    and then the state and symbol are the halting pair. Otherwise steps is limit.
    """
    half = limit if limit < 64 else 64
    tape = bytearray(2 * half + 1)
    pos = half
    st = 0
    steps = 0
    while True:
        # c steps cannot leave the tape, so the inner loop needs no bounds checks
        c = limit - steps
        if pos < c:
            c = pos
        if len(tape) - 1 - pos < c:
            c = len(tape) - 1 - pos
        for i in range(c):
            ins = table[st + tape[pos]]
            if ins is None:
                return True, steps + i, st, tape[pos]
            tape[pos], move, st = ins
            pos += move
        steps += c
        if steps == limit:
            sym = tape[pos]
            return table[st + sym] is None, steps, st, sym
        size = len(tape)
        if len(tape) - 1 - pos < size // 4:
            tape.extend(bytes(size))
        if pos < size // 4:
            tape[0:0] = bytes(size)
            pos += size


def simulate(text: str, max_steps: int) -> tuple[bool, int]:
    """(True, n) when the machine halts after n <= max_steps steps, else (False, max_steps)."""
    halted, steps, _, _ = _run(parse_text(text).table, max_steps)
    return halted, steps


# ---------------------------------------------------------------------------------------------------------------------
# Certificates (section 6)


def _uint(x: str) -> bool:
    return x.isascii() and x.isdigit()


def _fields_parse(verdict: str, rest: Sequence[str]) -> bool:
    if verdict == "NONHALT_CYCLER":
        return len(rest) == 2 and _uint(rest[0]) and _uint(rest[1])
    if verdict == "NONHALT_TRANSLATED":
        return len(rest) == 3 and rest[0] in ("R", "L") and _uint(rest[1]) and _uint(rest[2])
    if verdict == CPS:
        return len(rest) == 2 and _uint(rest[0]) and _uint(rest[1])
    if verdict == RWL:
        return len(rest) == 3 and all(_uint(x) for x in rest)
    if verdict == FAR:  # side and table are any strings here, and out of range unless _far_certificate takes them
        return len(rest) == 4 and _uint(rest[1]) and _uint(rest[3])
    if verdict == CPSH:
        return len(rest) == 3 and all(_uint(x) for x in rest)
    if verdict == "UNKNOWN":
        return len(rest) == 1 and _uint(rest[0])
    return False


def _cycler(table: Table, i: int, j: int) -> bool:
    """NONHALT_CYCLER i j, for 0 <= i < j."""
    origin = j + 1
    tape = bytearray(2 * j + 3)
    pos = origin
    st = 0
    snap: tuple[int, int, bytes] | None = None
    for n in range(j):
        if n == i:
            snap = (st, pos, bytes(tape))
        ins = table[st + tape[pos]]
        if ins is None:
            return False  # halts after n < j steps
        tape[pos], move, st = ins
        pos += move
    return snap == (st, pos, bytes(tape))


def _translated(table: Table, sign: int, i: int, j: int) -> bool:
    """NONHALT_TRANSLATED R i j (sign +1) or L i j (sign -1), for 1 <= i < j.

    Positions are mirrored by sign, so the L case is checked as the R case of the mirror image.
    """
    origin = j + 1
    tape = bytearray(2 * j + 3)
    pos = origin
    st = 0
    best = 0  # the largest mirrored position after fewer steps than n (p_0 = 0)
    snap_state, snap, p_i, low = 0, b"", 0, 0
    for n in range(j + 1):
        p = sign * (pos - origin)
        if n == i:
            if p <= best:
                return False  # p_i is not a new record
            snap_state, snap, p_i, low = st, bytes(tape), p, p
        elif n > i and p < low:
            low = p
        if n == j:
            if p <= best:
                return False  # p_j is not a new record
            break
        if p > best:
            best = p
        ins = table[st + tape[pos]]
        if ins is None:
            return False  # halts after n < j steps
        tape[pos], move, st = ins
        pos += move
    if st != snap_state:
        return False
    delta = p - p_i
    for c in range(low, p_i + 1):
        if snap[sign * c + origin] != tape[sign * (c + delta) + origin]:
            return False
    return True


class _CpsStop(Exception):
    """Ends a CPS closure early. result is what _cps_closure returns."""

    def __init__(self, result: int) -> None:
        super().__init__(result)
        self.result = result


# A local configuration (u, q, x, v) of section 6, with q given as state * width, as in a Table.
Local = tuple[bytes, int, int, bytes]


def _cps_closure(table: Table, n: int, limit: int) -> int:
    """The number of members of C for this n (section 6), with Lw, Rw and C built until nothing new is added.

    Returns -1 as soon as C holds a member whose pair is undefined, and limit + 1 as soon as C has more than limit
    members, without building further. Words are bytes of n symbols.

    Each member is expanded once, when it leaves the work list, and then waits on the words it uses. A member that
    moves R waits on the words of Rw that start with v2...vn, and one that moves L on the words of Lw that end with
    u1...u(n-1). When such a word enters Rw or Lw later, every member waiting on it gets its successor with that word
    then. So no successor is missed (CHECKING.md, "A member must be expanded again when a word it waits on arrives").
    """
    zero = bytes(n)
    members: set[Local] = set()
    work: list[Local] = []
    in_left: set[bytes] = set()  # Lw
    in_right: set[bytes] = set()  # Rw
    left_by_end: dict[bytes, list[bytes]] = {}  # Lw, keyed by each word's last n - 1 symbols
    right_by_start: dict[bytes, list[bytes]] = {}  # Rw, keyed by each word's first n - 1 symbols
    # Members waiting on words, keyed as above. An L mover waits as (t, u_n, w v1...v(n-1)) on Lw words ending with
    # u1...u(n-1). An R mover waits as (u2...un w, t, v1) on Rw words starting with v2...vn. Members with the same
    # waiting entry have the same successors, so only the first is expanded against the words.
    left_waiters: dict[bytes, set[tuple[int, int, bytes]]] = {}
    right_waiters: dict[bytes, set[tuple[bytes, int, int]]] = {}

    def add(member: Local) -> None:
        if member in members:
            return
        if table[member[1] + member[2]] is None:
            raise _CpsStop(-1)
        members.add(member)
        if len(members) > limit:
            raise _CpsStop(limit + 1)
        work.append(member)

    def enter_left(word: bytes) -> None:
        if word in in_left:
            return
        in_left.add(word)
        key = word[1:]
        left_by_end.setdefault(key, []).append(word)
        for t, x, right in left_waiters.get(key, ()):
            add((word, t, x, right))

    def enter_right(word: bytes) -> None:
        if word in in_right:
            return
        in_right.add(word)
        key = word[:-1]
        right_by_start.setdefault(key, []).append(word)
        for left, t, x in right_waiters.get(key, ()):
            add((left, t, x, word))

    try:
        enter_left(zero)
        enter_right(zero)
        add((zero, 0, 0, zero))
        while work:
            u, st, sym, v = work.pop()
            ins = table[st + sym]
            assert ins is not None  # add refuses a member whose pair is undefined
            w, move, t = ins
            if move > 0:
                left, key, x = u[1:] + bytes((w,)), v[1:], v[0]
                waiting_r = right_waiters.setdefault(key, set())
                if (left, t, x) in waiting_r:
                    continue
                waiting_r.add((left, t, x))
                enter_left(left)
                for right in right_by_start.get(key, ()):
                    add((left, t, x, right))
            else:
                right, key, x = bytes((w,)) + v[:-1], u[:-1], u[-1]
                waiting_l = left_waiters.setdefault(key, set())
                if (t, x, right) in waiting_l:
                    continue
                waiting_l.add((t, x, right))
                enter_right(right)
                for left in left_by_end.get(key, ()):
                    add((left, t, x, right))
    except _CpsStop as stop:
        return stop.result
    return len(members)


def cps_size(text: str, n: int, limit: int = CPS_MAX_C) -> int:
    """The number of members of C for the machine and n (section 6), or -1 when C holds a member whose pair is
    undefined. It stops as soon as C has more than limit members and then returns limit + 1."""
    if n < 1:
        raise ValueError("n must be at least 1")
    return _cps_closure(parse_text(text).table, n, limit)


# NONHALT_RWL (section 6). A list is bytes, each run being its word's b symbols and then one byte for its count, with
# the first run (the one nearest the head) first. A member (L, q, d, R) is (L, q * width, d, R), where d is +1 for the
# side R and -1 for the side L.
RwlMember = tuple[bytes, int, int, bytes]
BlockRun = Optional[tuple[int, int, bytes]]


def _block_run(table: Table, st: int, word: bytes, pos: int) -> BlockRun:
    """Run the machine on the word alone, a tape of len(word) cells, from state st (as state * width) on cell pos.

    Returns (t * width, side, w') when a step moves the head off the right end (side +1) or the left end (side -1),
    where t is the state then and w' the cells' word. Returns None when the run reads an undefined pair first, or when
    RWL_BLOCK_STEPS steps have run and the head is still on the cells.
    """
    cells = bytearray(word)
    b = len(cells)
    for _ in range(RWL_BLOCK_STEPS):
        ins = table[st + cells[pos]]
        if ins is None:
            return None
        cells[pos], move, st = ins
        pos += move
        if pos < 0:
            return st, -1, bytes(cells)
        if pos == b:
            return st, 1, bytes(cells)
    return None


def _rwl_takes(near: bytes, b: int, big_t: int, zero: bytes) -> tuple[tuple[bytes, bytes], ...]:
    """The pairs (w, rest) of taking a block from the near list ("Taking a block")."""
    if not near:
        return ((zero, b""),)
    w, n, tail = near[:b], near[b], near[b + 1:]
    fewer = tail if n == 1 else w + bytes((n - 1,)) + tail  # the run with one copy fewer, or removed when n is 1
    if n < big_t:
        return ((w, fewer),)
    return ((w, fewer), (w, near))  # (w, T) stands for T or more copies, so one fewer is T - 1 or still T or more


def _rwl_put(lst: bytes, w: bytes, b: int, big_t: int) -> bytes:
    """Put the word w on the list ("Putting a block")."""
    if lst[:b] == w:  # an empty list gives b"", never a word of b symbols
        n = lst[b]
        return w + bytes((n + 1 if n < big_t else big_t,)) + lst[b + 1:]
    return w + b"\x01" + lst


def _rwl_trim(lst: bytes, b: int, zero: bytes) -> bytes:
    """Remove the last run while its word is 0^b ("Trimming"). Runs nearer the head stay."""
    size = b + 1
    while lst and lst[-size:-1] == zero:
        lst = lst[:-size]
    return lst


def _rwl_closure(table: Table, b: int, big_t: int, limit: int) -> int:
    """The number of members of C for this b and T (section 6), built from the start until nothing new is added.

    Returns -1 as soon as a block run reads an undefined pair or does not leave its block within RWL_BLOCK_STEPS
    steps, and limit + 1 as soon as C has more than limit members, without building further. Each member is taken and
    run once, since its successors depend on that member alone. The work list is first in, first out, so the lists
    grow no faster than they must and a C that passes the limit is found quickly.
    """
    zero = bytes(b)
    start: RwlMember = (b"", 0, 1, b"")  # (empty, A, R, empty)
    members: set[RwlMember] = {start}
    if len(members) > limit:
        return limit + 1
    work: deque[RwlMember] = deque(members)
    runs: dict[tuple[int, int, bytes], BlockRun] = {}  # the block runs met so far, by (q * width, d, w)
    trim, put = _rwl_trim, _rwl_put
    while work:
        left, st, d, right = work.popleft()
        for w, rest in _rwl_takes(right if d > 0 else left, b, big_t, zero):
            key = (st, d, w)
            if key in runs:
                out = runs[key]
            else:
                # the head enters R's first block at its left cell and L's first block at its right cell
                out = runs[key] = _block_run(table, st, w, 0 if d > 0 else b - 1)
            if out is None:
                return -1
            t, side, written = out
            near_left, near_right = (left, rest) if d > 0 else (rest, right)
            if side > 0:
                succ = (trim(put(near_left, written, b, big_t), b, zero), t, 1, trim(near_right, b, zero))
            else:
                succ = (trim(near_left, b, zero), t, -1, trim(put(near_right, written, b, big_t), b, zero))
            if succ not in members:
                members.add(succ)
                if len(members) > limit:
                    return limit + 1
                work.append(succ)
    return len(members)


def rwl_size(text: str, b: int, big_t: int, limit: int = RWL_MAX_C) -> int:
    """The number of members of C for the machine, b and T (section 6), or -1 when a block run reads an undefined
    pair or does not leave its block within 1,000 steps. It stops as soon as C has more than limit members and then
    returns limit + 1."""
    if not (1 <= b <= 255 and 1 <= big_t <= 255):
        raise ValueError("b and T must be from 1 to 255")
    return _rwl_closure(parse_text(text).table, b, big_t, limit)


# NONHALT_FAR (section 6). A node (i, q) is numbered i * m + q and the node bottom is numbered n * m, so a set of nodes
# is an int with bit x set for each node x in it. out[x][b] is the set of the nodes y with an edge x -b-> y in R, so R
# has as many edges as out has bits set.


@dataclass(frozen=True)
class FarCertificate:
    mirror: bool  # side R, so the rules read the machine's mirror image
    n: int
    delta: tuple[int, ...]  # delta(i, b) is delta[i * k + b], the table's digit i * k + b
    e: int
    k: int  # the machine's symbols
    m: int  # the machine's states


def _far_shape(text: str, machine: Machine) -> tuple[int, int] | str:
    """k and m of a machine for NONHALT_FAR (section 6), or why this checker fails every NONHALT_FAR certificate for
    its text.

    k is 1 plus the largest w, or 1 when no pair is defined. m is 1 plus the largest state index used as an owner or a
    target, and A is always a state, so the empty machine has m = 1 and k = 1. Every text in the tree has exactly k
    cells in each row and has a row only for a state that owns an instruction (section 2). The contract lets a checker
    fail a text whose rows have another width, and this checker also fails a row that owns no instruction, which is
    not a row of a machine text, and more than 10 states.
    """
    defined = [ins for ins in machine.table if ins is not None]
    k = 1 + max((ins[0] for ins in defined), default=0)
    if text == "":
        return k, 1  # the root: no owner and no target, and still the one state A
    rows = text.split("_")  # parse_text has made sure that they all have the same length
    if len(rows[0]) != 3 * k:
        return f"its rows have {len(rows[0]) // 3} cells, not k = {k}"
    if len(rows) > MAX_STATES:
        return f"it has {len(rows)} rows, more than {MAX_STATES}"
    for q, row in enumerate(rows):
        if row == "---" * k:
            return f"its row {LETTERS[q]} owns no instruction"
    # machine.width is k here, since the rows have k cells and no w is k or more
    m = max(len(rows), 1 + max((ins[2] // machine.width for ins in defined), default=0))
    return k, m


def _far_certificate(text: str, machine: Machine, rest: Sequence[str]) -> FarCertificate | str:
    """The certificate of a NONHALT_FAR claim whose fields parse, or, when it fails without computing, the words that
    follow it in the failure message. Long numbers are never converted."""
    shape = _far_shape(text, machine)
    if isinstance(shape, str):
        return f"fails for {text}, since {shape}"
    k, m = shape
    side, table = rest[0], rest[2]
    n, e = _bounded(rest[1]), _bounded(rest[3])
    why = None
    if side not in ("L", "R"):
        why = f"side {side!r} is not L or R"
    elif not 1 <= n <= FAR_MAX_N:
        why = f"n is not from 1 to {FAR_MAX_N}"
    elif len(table) != n * k:
        why = f"the table has {len(table)} characters, not n * k = {n * k} digits"
    elif not (table.isascii() and table.isdigit()):
        why = "the table is not all digits"
    elif table[0] != "0":
        why = "the table's first digit is not 0"
    elif any(ord(c) - 48 >= n for c in table):
        why = f"a digit of the table is not below n = {n}"
    elif not 1 <= e <= FAR_MAX_E:
        why = f"e is not from 1 to {FAR_MAX_E}"
    if why is not None:
        return f"has side, n, table or e out of range ({why})"
    return FarCertificate(side == "R", n, tuple(ord(c) - 48 for c in table), e, k, m)


def _far_closure(table: Table, k: int, m: int, n: int, delta: Sequence[int], mirror: bool) -> tuple[int, bool]:
    """The number of edges of R and whether the node (0, A) is in a (section 6).

    table is the machine's, with k symbols per state (its width) and m states. delta(i, b) is delta[i * k + b] for the
    automaton states i from 0 to n - 1. With mirror, the rules read the machine's mirror image (side R), every L read
    as R and every R as L.

    Rules 1 to 3 do not read R, so each is applied once. Rule 4 reads R, so whole passes over all its instances are
    repeated until a pass adds no edge (CHECKING.md, "Rule 4 must be applied again when the edges it reads change").
    Every rule is applied at every automaton state, reachable from 0 or not. Then a grows from bottom by every node
    with a 0-edge into a, until nothing is added, so it holds every node with a path of 0-edges to bottom.
    """
    bottom = n * m
    bot = 1 << bottom
    out = [[0] * k for _ in range(bottom)] + [[bot] * k]  # rule 1: bottom -b-> bottom for every b
    lefts: list[tuple[int, int, int, int]] = []  # (q, r, w, t) for every pair whose instruction moves L
    for q in range(m):
        for r in range(k):
            ins = table[q * k + r]
            if ins is None:  # rule 2: (i, q) -r-> bottom
                for i in range(n):
                    out[i * m + q][r] |= bot
                continue
            w, move, t = ins[0], -ins[1] if mirror else ins[1], ins[2] // k
            if move > 0:  # rule 3: (i, q) -r-> (delta(i, w), t)
                for i in range(n):
                    out[i * m + q][r] |= 1 << (delta[i * k + w] * m + t)
            else:
                lefts.append((q, r, w, t))
    # Rule 4: for each L pair (q, r) with (w, L, t), each i and each b, (delta(i, b), q) -r-> y for every y that
    # (i, t) reaches by reading b and then w. Each instance holds the edges out of (i, t), b, w, the edges out of
    # (delta(i, b), q) and r.
    instances = [(out[i * m + t], b, w, out[delta[i * k + b] * m + q], r)
                 for q, r, w, t in lefts for i in range(n) for b in range(k)]
    changed = True
    while changed:
        changed = False
        for first, b, w, source, r in instances:
            via = first[b]  # the nodes y' with (i, t) -b-> y'
            reached = 0
            while via:
                low = via & -via
                reached |= out[low.bit_length() - 1][w]
                via ^= low
            if reached & ~source[r]:
                source[r] |= reached
                changed = True
    edges = sum(targets.bit_count() for row in out for targets in row)
    in_a = bot
    grew = True
    while grew:
        grew = False
        for x in range(bottom):
            if not in_a >> x & 1 and out[x][0] & in_a:
                in_a |= 1 << x
                grew = True
    return edges, bool(in_a & 1)  # (0, A) is node 0


def far_size(text: str, side: str, n: int, table: str) -> tuple[int, bool]:
    """The number of edges of R and whether (0, A) is in a (section 6), for the machine and a side, n and table in
    range. Raises ValueError when they are not."""
    machine = parse_text(text)
    cert = _far_certificate(text, machine, [side, str(n), table, "1"])
    if isinstance(cert, str):
        raise ValueError(f"NONHALT_FAR {side} {n} {table} {cert}")
    return _far_closure(machine.table, cert.k, cert.m, cert.n, cert.delta, cert.mirror)


# NONHALT_CPSH (section 6). The closure numbers the symbols of the history machine M_H as it makes them, starting with
# the blank (0, ()) as 0, so a word is a tuple of n symbol numbers. The numbers pass a byte, so words are not bytes as
# in NONHALT_CPS. A member (u, q, x, v) is (u, q * width, x, v), with x a symbol number.
HistoryLocal = tuple[tuple[int, ...], int, int, tuple[int, ...]]


def _cpsh_closure(table: Table, n: int, h: int, limit: int) -> int:
    """The number of members of C for M_H with this n and H (section 6), with Lw, Rw and C built until nothing new is
    added, as _cps_closure builds them for M. table is M's.

    Returns -1 as soon as C holds a member whose pair is undefined, and limit + 1 as soon as C has more than limit
    members, without building further.

    M_H's pair (q, (b, hist)) is undefined exactly when M's (q, b) is, and its instruction otherwise writes
    (w, first H of ((q, b),) + hist), moves m and goes to t, where (w, m, t) is M's instruction on (q, b). So the
    instruction is read from the symbol's base b, never from its number, and a symbol is made, and numbered, when an
    instruction first writes it. The blank is the symbol 0 wherever the rules say 0: the words 0^n of Lw and Rw and
    the start member (0^n, A, (0, ()), 0^n). Members wait on the words they use and are expanded again when such a word
    arrives, as in _cps_closure (CHECKING.md, "Waiting members are expanded again here too").
    """
    base = [0]  # base[x] is the base b of the symbol numbered x
    hist: list[tuple[tuple[int, int], ...]] = [()]  # hist[x] is its history, pairs (q * width, b), newest first
    numbers: dict[tuple[int, tuple[tuple[int, int], ...]], int] = {(0, ()): 0}
    instructions: dict[tuple[int, int], Optional[tuple[int, int, int]]] = {}  # (q * width, x) -> M_H's, or None

    def instruction(st: int, x: int) -> Optional[tuple[int, int, int]]:
        """M_H's instruction on (q, x) as (written symbol number, move, t * width), or None when it is undefined."""
        key = (st, x)
        if key in instructions:
            return instructions[key]
        b = base[x]
        ins = table[st + b]
        out = None
        if ins is not None:
            w, move, t = ins
            written = (w, (((st, b),) + hist[x])[:h])
            y = numbers.get(written)
            if y is None:
                y = numbers[written] = len(base)
                base.append(w)
                hist.append(written[1])
            out = (y, move, t)
        instructions[key] = out
        return out

    zero = (0,) * n
    members: set[HistoryLocal] = set()
    work: list[HistoryLocal] = []
    in_left: set[tuple[int, ...]] = set()  # Lw
    in_right: set[tuple[int, ...]] = set()  # Rw
    left_by_end: dict[tuple[int, ...], list[tuple[int, ...]]] = {}  # Lw, keyed by each word's last n - 1 symbols
    right_by_start: dict[tuple[int, ...], list[tuple[int, ...]]] = {}  # Rw, keyed by each word's first n - 1 symbols
    # Members waiting on words, keyed and shaped as in _cps_closure
    left_waiters: dict[tuple[int, ...], set[tuple[int, int, tuple[int, ...]]]] = {}
    right_waiters: dict[tuple[int, ...], set[tuple[tuple[int, ...], int, int]]] = {}

    def add(member: HistoryLocal) -> None:
        if member in members:
            return
        if instruction(member[1], member[2]) is None:
            raise _CpsStop(-1)
        members.add(member)
        if len(members) > limit:
            raise _CpsStop(limit + 1)
        work.append(member)

    def enter_left(word: tuple[int, ...]) -> None:
        if word in in_left:
            return
        in_left.add(word)
        key = word[1:]
        left_by_end.setdefault(key, []).append(word)
        for t, x, right in left_waiters.get(key, ()):
            add((word, t, x, right))

    def enter_right(word: tuple[int, ...]) -> None:
        if word in in_right:
            return
        in_right.add(word)
        key = word[:-1]
        right_by_start.setdefault(key, []).append(word)
        for left, t, x in right_waiters.get(key, ()):
            add((left, t, x, word))

    try:
        enter_left(zero)
        enter_right(zero)
        add((zero, 0, 0, zero))
        while work:
            u, st, sym, v = work.pop()
            ins = instruction(st, sym)
            assert ins is not None  # add refuses a member whose pair is undefined
            w, move, t = ins
            if move > 0:
                left, key, x = u[1:] + (w,), v[1:], v[0]
                waiting_r = right_waiters.setdefault(key, set())
                if (left, t, x) in waiting_r:
                    continue
                waiting_r.add((left, t, x))
                enter_left(left)
                for right in right_by_start.get(key, ()):
                    add((left, t, x, right))
            else:
                right, key, x = (w,) + v[:-1], u[:-1], u[-1]
                waiting_l = left_waiters.setdefault(key, set())
                if (t, x, right) in waiting_l:
                    continue
                waiting_l.add((t, x, right))
                enter_right(right)
                for left in left_by_end.get(key, ()):
                    add((left, t, x, right))
    except _CpsStop as stop:
        return stop.result
    return len(members)


def cpsh_size(text: str, n: int, h: int, limit: int = CPSH_MAX_C) -> int:
    """The size of C for the machine's history machine M_H with this n and H (section 6), from 1 to limit. Otherwise
    the result is not a valid size: -1 when C holds a member whose pair is undefined, and limit + 1 when C has more
    than limit members, where the closure stops. Raises ValueError when n or H is below 1."""
    if n < 1 or h < 1:
        raise ValueError("n and H must be at least 1")
    return _cpsh_closure(parse_text(text).table, n, h, limit)


def _bounded(x: str) -> int:
    """The value of a string of digits, or MAX_CAP + 1 for anything larger. A long string is never converted."""
    x = x.lstrip("0")
    if len(x) > len(str(MAX_CAP)):
        return MAX_CAP + 1
    return min(int(x or "0"), MAX_CAP + 1)


def _cps_fields(rest: Sequence[str]) -> tuple[int, int] | None:
    """n and c of a NONHALT_CPS certificate whose fields parse, or None when either is out of range."""
    n, c = _bounded(rest[0]), _bounded(rest[1])
    return (n, c) if 1 <= n <= CPS_MAX_N and 1 <= c <= CPS_MAX_C else None


def _rwl_fields(rest: Sequence[str]) -> tuple[int, int, int] | None:
    """b, T and c of a NONHALT_RWL certificate whose fields parse, or None when any is out of range."""
    b, big_t, c = _bounded(rest[0]), _bounded(rest[1]), _bounded(rest[2])
    in_range = 1 <= b <= RWL_MAX_B and 1 <= big_t <= RWL_MAX_T and 1 <= c <= RWL_MAX_C
    return (b, big_t, c) if in_range else None


def _cpsh_fields(rest: Sequence[str]) -> tuple[int, int, int] | None:
    """n, H and c of a NONHALT_CPSH certificate whose fields parse, or None when any is out of range."""
    n, h, c = _bounded(rest[0]), _bounded(rest[1]), _bounded(rest[2])
    in_range = 1 <= n <= CPSH_MAX_N and 1 <= h <= CPSH_MAX_H and 1 <= c <= CPSH_MAX_C
    return (n, h, c) if in_range else None


def _verify(machine: Machine, verdict: str, rest: Sequence[str], text: str) -> bool:
    """Verify a certificate whose fields already parse, for the machine of the text. One whose j is above MAX_CAP
    fails without being run, a NONHALT_CPS, NONHALT_RWL or NONHALT_CPSH certificate with a number out of range fails
    without being computed, and so does a NONHALT_FAR certificate whose side, n, table or e is out of range."""
    if verdict == "UNKNOWN":
        return True
    if verdict == CPSH:
        nhc = _cpsh_fields(rest)
        return nhc is not None and _cpsh_closure(machine.table, nhc[0], nhc[1], nhc[2]) == nhc[2]
    if verdict == FAR:
        cert = _far_certificate(text, machine, rest)
        if isinstance(cert, str):
            return False
        return _far_closure(machine.table, cert.k, cert.m, cert.n, cert.delta, cert.mirror) == (cert.e, False)
    if verdict == CPS:
        nc = _cps_fields(rest)
        return nc is not None and _cps_closure(machine.table, nc[0], nc[1]) == nc[1]
    if verdict == RWL:
        btc = _rwl_fields(rest)
        return btc is not None and _rwl_closure(machine.table, btc[0], btc[1], btc[2]) == btc[2]
    return _verify_run(machine.table, verdict, rest)


def _verify_run(table: Table, verdict: str, rest: Sequence[str]) -> bool:
    """Verify a NONHALT_CYCLER or NONHALT_TRANSLATED certificate whose fields already parse, on the machine's table."""
    if verdict == "NONHALT_CYCLER":
        i, j = _bounded(rest[0]), _bounded(rest[1])
        return 0 <= i < j <= MAX_CAP and _cycler(table, i, j)
    i, j = _bounded(rest[1]), _bounded(rest[2])
    return 1 <= i < j <= MAX_CAP and _translated(table, 1 if rest[0] == "R" else -1, i, j)


def verify_certificate(text: str, fields: list[str]) -> bool:
    """Whether the claim fields after the text (for example ["NONHALT_CYCLER", "2", "4"]) are a valid certificate."""
    try:
        machine = parse_text(text)
    except ValueError:
        return False
    if not fields or not _fields_parse(fields[0], fields[1:]):
        return False
    return _verify(machine, fields[0], fields[1:], text)


# ---------------------------------------------------------------------------------------------------------------------
# The corridor walk (sections 3, 4 and 9 step 2)


@dataclass(frozen=True)
class Corridor:
    states: int  # S
    symbols: int  # K
    depth: int  # D
    bounds: tuple[int, ...]  # B_0 to B_D


@dataclass
class WalkTally:
    machines: list[int]
    halters: list[int]
    unhalted: list[int]
    max_steps: list[int]
    halt_steps: list[int]  # the sum of the halters' steps at each depth
    late: int = 0  # late machines at depth D
    halter_sum: int = 0
    unhalted_sum: int = 0
    top: list[tuple[int, str]] = field(default_factory=list)  # (-steps, text) for the top halters at depth D

    @classmethod
    def empty(cls, depth: int) -> WalkTally:
        n = depth + 1
        return cls([0] * n, [0] * n, [0] * n, [0] * n, [0] * n)

    def merge(self, other: WalkTally) -> None:
        for d in range(len(self.machines)):
            self.machines[d] += other.machines[d]
            self.halters[d] += other.halters[d]
            self.unhalted[d] += other.unhalted[d]
            self.max_steps[d] = max(self.max_steps[d], other.max_steps[d])
            self.halt_steps[d] += other.halt_steps[d]
        self.late += other.late
        self.halter_sum = (self.halter_sum + other.halter_sum) & MASK
        self.unhalted_sum = (self.unhalted_sum + other.unhalted_sum) & MASK
        self.top = sorted(self.top + other.top)[:TOP]


@dataclass
class Progress:
    """How far the indexed check has walked, for its progress lines on stderr.

    steps counts each halter's steps and the depth's bound for each machine claimed UNKNOWN. A certified machine adds
    none. So when a passing check ends, steps is the sum over summary.json's corridor of halt_steps plus UNKNOWN times
    max_halt_steps.
    """
    started: float  # a time.perf_counter() value
    machines: int = 0
    steps: int = 0

    def add(self, walk: WalkTally, claims: ClaimTally, bounds: Sequence[int]) -> None:
        """Count one finished walk and the claims it read."""
        unknown = sum(claims.counts.get((d, "UNKNOWN"), 0) * b for d, b in enumerate(bounds))
        self.machines += sum(walk.machines)
        self.steps += sum(walk.halt_steps) + unknown

    def line(self, now: float) -> str:
        return f"progress: {self.machines} machines, {self.steps} steps, {now - self.started:.1f} s"


@contextmanager
def _reporting(progress: Progress) -> Iterator[None]:
    """Print progress.line to stderr every PROGRESS_SECS seconds while the block runs, and stop when it ends, even
    when it raises. The checking thread writes the counters and the reporting thread reads them, with no lock, and a
    batch counts once its result is collected, so a line may show the work a few batches behind."""
    stop = threading.Event()

    def report() -> None:
        while not stop.wait(PROGRESS_SECS):
            print(progress.line(time.perf_counter()), file=sys.stderr, flush=True)

    thread = threading.Thread(target=report, name=PROGRESS_THREAD, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


def _in_corridor(cor: Corridor, d: int, s: int, k: int) -> bool:
    room = cor.depth - d
    return s <= cor.states and k <= cor.symbols and cor.states - s <= room and cor.symbols - k <= room


def _root(cor: Corridor) -> Node | None:
    """The empty machine, or None when even it is outside the corridor."""
    if not _in_corridor(cor, 0, 0, 1):
        return None
    table: Table = [None] * ((cor.states + 2) * cor.symbols)
    return (0, table, ["---" * cor.symbols] * cor.states, 0, 1, 0, False)


def _node_text(node: Node, big_k: int) -> str:
    _, _, rows, s, k, _, _ = node
    if s == 0:
        return ""
    if k == big_k:
        return "_".join(rows[:s])
    return "_".join([row[:3 * k] for row in rows[:s]])


def late_cap(d: int) -> int:
    """The census cap of an ancestor at depth d (section 8), CAP_SHALLOW at depths 0 to 7 and CAP_DEPTH8 at depth 8 or
    deeper. A child is late when its parent is late or halted after more steps than this."""
    return CAP_SHALLOW if d <= 7 else CAP_DEPTH8


def _walk(cor: Corridor, nodes: Sequence[Node], split: int | None = None, emit: Callable[[Node], None] | None = None,
          lines: _Lines | None = None, claims: ClaimTally | None = None) -> WalkTally:
    """Walk the corridor from the given nodes, each in canonical order (section 3).

    Children at depth split are handed to emit, in canonical order, instead of being walked. With lines, the walk
    reads that group's claims alongside and tallies them into claims (section 9, "When claims.idx exists", step 2).
    Without, every machine runs for its depth's bound (step 2).
    """
    big_s, big_k, big_d, bounds = cor.states, cor.symbols, cor.depth, cor.bounds
    tally = WalkTally.empty(big_d)
    machines, halters, unhalted, max_steps, top = tally.machines, tally.halters, tally.unhalted, tally.max_steps, []
    halt_steps = tally.halt_steps
    late = halter_sum = unhalted_sum = 0
    ins_of = [[[(w, move, t * big_k) for t in range(LIMIT + 1)] for move in (-1, 1)] for w in range(LIMIT + 1)]
    cell_of = [[[f"{w}{m}{LETTERS[t]}" for t in range(LIMIT + 1)] for m in "LR"] for w in range(LIMIT + 1)]
    h, run = _h, _run
    stack = list(reversed(nodes))
    while stack:
        d, table, rows, s, k, top_state, is_late = stack.pop()
        if s == 0:
            text = ""
        elif k == big_k:
            text = "_".join(rows[:s])
        else:
            w3 = 3 * k
            text = "_".join([row[:w3] for row in rows[:s]])
        machines[d] += 1
        if d == big_d and is_late:
            late += 1
        if lines is not None and lines.text == text:
            claimed = _use_claim(lines, claims, text, d, table, bounds[d])
            if claimed is None:
                unhalted[d] += 1
                unhalted_sum += h(text.encode())
                continue
            n, st, r = claimed
        else:
            halted, n, st, r = run(table, bounds[d])
            if not halted:
                unhalted[d] += 1
                unhalted_sum += h(text.encode())
                if lines is not None:
                    claims.defect(f"group {lines.group}: {text} at depth {d} does not halt within "
                                  f"{_count(bounds[d], 'step')} and is not the group's next claim")
                continue
        halters[d] += 1
        halt_steps[d] += n
        if n > max_steps[d]:
            max_steps[d] = n
        halter_sum += h(f"{text}\t{n}".encode())
        if d == big_d:
            if len(top) < TOP or -n <= top[-1][0]:
                key = (-n, text)
                if len(top) < TOP:
                    insort(top, key)
                elif key < top[-1]:
                    insort(top, key)
                    top.pop()
            continue
        # Children (section 3), keeping those in the corridor at depth d + 1 (section 4)
        child_d = d + 1
        room = big_d - child_d
        q = st // big_k
        child_s = s + 1 if q == s else s
        if child_s > big_s or big_s - child_s > room:
            continue
        child_late = is_late or n > late_cap(d)
        base = max(top_state, q)
        idx = st + r
        row = rows[q]
        pre, suf = row[:3 * r], row[3 * r + 3:]
        moves = (1,) if d == 0 else (0, 1)  # L before R
        t_max = min(LIMIT, top_state + 1)
        kids: list[Node] = []
        add = kids.append
        for w in range(min(LIMIT, k) + 1):  # k is W + 1
            child_k = k if w < k else w + 1
            if child_k > big_k or big_k - child_k > room:
                continue
            for m in moves:
                ins_wm, cell_wm = ins_of[w][m], cell_of[w][m]
                for t in range(t_max + 1):
                    child = table.copy()
                    child[idx] = ins_wm[t]
                    child_rows = rows.copy()
                    child_rows[q] = pre + cell_wm[t] + suf
                    add((child_d, child, child_rows, child_s, child_k, t if t > base else base, child_late))
        if child_d == split:
            for kid in kids:
                emit(kid)
        else:
            kids.reverse()  # so the first child is popped first
            stack.extend(kids)
    tally.late = late
    tally.halter_sum = halter_sum & MASK
    tally.unhalted_sum = unhalted_sum & MASK
    tally.top = top
    return tally


def _walk_job(job: tuple[Corridor, list[Node]]) -> WalkTally:
    """Pool worker: walk a group of subtrees."""
    cor, nodes = job
    return _walk(cor, nodes)


def _walk_cell(cor: Corridor, pool: Any, jobs: int) -> WalkTally:
    root = _root(cor)
    if root is None:
        return WalkTally.empty(cor.depth)
    tasks: list[Node] = []
    tally = _walk(cor, [root], min(SPLIT_DEPTH, cor.depth), tasks.append)
    if pool is None:
        tally.merge(_walk(cor, tasks))
        return tally
    n = max(1, min(len(tasks), jobs * GROUPS_PER_JOB))
    for part in pool.imap_unordered(_walk_job, [(cor, tasks[g::n]) for g in range(n)]):
        tally.merge(part)
    return tally


def corridor_counts(states: int, symbols: int, depth: int, bounds: Sequence[int]) -> list[int]:
    """The corridor machines at each depth 0 to depth, where machines not halting within bounds[d] steps have no
    children."""
    cor = Corridor(states, symbols, depth, tuple(bounds[:depth + 1]))
    root = _root(cor)
    if root is None:
        return [0] * (depth + 1)
    return _walk(cor, [root]).machines


# ---------------------------------------------------------------------------------------------------------------------
# The claims (section 9 step 3)


@dataclass
class ClaimTally:
    # The cell's format, 1 to 5. NONHALT_CPS claims may appear in formats 2 to 5, NONHALT_RWL claims in formats 3 to 5,
    # NONHALT_FAR claims in formats 4 and 5, and NONHALT_CPSH claims in format 5. In the other formats each one fails.
    fmt: int = 1
    lines: int = 0
    counts: dict[tuple[int, str], int] = field(default_factory=dict)  # (depth, verdict) -> claims
    claims_sum: int = 0
    claimed_sum: int = 0
    unknown: dict[int, list[str]] = field(default_factory=dict)  # depth -> UNKNOWN texts
    invalid: int = 0  # certificates that parse but are not valid
    problems: int = 0  # lines with any problem, invalid certificates included
    defects: int = 0  # failures of the indexed check's walk and grouped claims, apart from the lines' own problems
    messages: list[str] = field(default_factory=list)  # the first MAX_FAILURES problems and defects
    amend: bool = False  # the lines are amend.tsv's, and fmt is amend.json's claims_format (section 12)
    deferred: list[tuple[str, int, str]] = field(default_factory=list)  # --gpu: (text, depth, where) of UNKNOWN claims

    def problem(self, message: str) -> None:
        self.problems += 1
        if len(self.messages) < MAX_FAILURES:
            self.messages.append(message)

    def defect(self, message: str, at: int | None = None) -> None:
        """Record a defect, with its message at position at among the messages (default last)."""
        self.defects += 1
        if len(self.messages) < MAX_FAILURES:
            self.messages.insert(len(self.messages) if at is None else at, message)
        elif at is not None and at < MAX_FAILURES:
            self.messages.insert(at, message)
            self.messages.pop()

    def merge(self, other: ClaimTally) -> None:
        self.lines += other.lines
        for key, count in other.counts.items():
            self.counts[key] = self.counts.get(key, 0) + count
        self.claims_sum = (self.claims_sum + other.claims_sum) & MASK
        self.claimed_sum = (self.claimed_sum + other.claimed_sum) & MASK
        for d, texts in other.unknown.items():
            self.unknown.setdefault(d, []).extend(texts)
        self.invalid += other.invalid
        self.problems += other.problems
        self.defects += other.defects
        self.messages.extend(other.messages[:MAX_FAILURES - len(self.messages)])
        self.deferred.extend(other.deferred)


_RUN_ONLY = ("NONHALT_CYCLER", "NONHALT_TRANSLATED")  # certificates that depend on the machine's run alone


def _claim(t: ClaimTally, raw: bytes, where: str, known: tuple[int, Table] | None = None) -> str | None:
    """Step 3 for one claims line, given without its newline: count it, digest it and verify its certificate.

    Returns its verdict, or None when it does not parse. where names the line in messages. known is (depth, table)
    of the walk's machine when the walk has matched the line's text to its own text for that machine. Then a
    NONHALT_CYCLER or NONHALT_TRANSLATED certificate, which depends only on the machine's run, is checked on the walk's
    table, the same machine, and the text is not parsed again. Every other verdict parses the text.
    """
    t.lines += 1
    t.claims_sum += _h(raw)
    t.claimed_sum += _h(raw.split(b"\t", 1)[0])
    try:
        line = raw.decode("utf-8")
    except UnicodeDecodeError:
        t.problem(f"{where} is not UTF-8")
        return None
    fields = line.split("\t")
    text = fields[0]
    verdict, rest = (fields[1], fields[2:]) if len(fields) > 1 else ("", [])
    if known is not None and verdict in _RUN_ONLY:
        depth, table = known
        if not _fields_parse(verdict, rest):
            t.problem(f"{where}: the fields of {line!r} do not parse")
            return None
        key = (depth, verdict)
        t.counts[key] = t.counts.get(key, 0) + 1
        if _bounded(rest[-1]) > MAX_CAP:
            t.invalid += 1
            t.problem(f"{where}: {verdict} {' '.join(rest)} has j above the bound {MAX_CAP} of this checker")
        elif not _verify_run(table, verdict, rest):
            t.invalid += 1
            t.problem(f"{where}: {verdict} {' '.join(rest)} is not a valid certificate for {text}")
        return verdict
    try:
        machine = parse_text(text)
    except ValueError as e:
        t.problem(f"{where}: {text!r} is not a machine text ({e})")
        return None
    if not _fields_parse(verdict, rest):
        t.problem(f"{where}: the fields of {line!r} do not parse")
        return None
    key = (machine.depth, verdict)
    t.counts[key] = t.counts.get(key, 0) + 1
    shown = f"{verdict} {' '.join(rest)}"
    if verdict == "UNKNOWN":
        t.unknown.setdefault(machine.depth, []).append(text)
    elif verdict in SINCE and t.fmt < SINCE[verdict]:
        t.invalid += 1
        if t.amend:
            t.problem(f"{where}: {shown} for {text} is not allowed by claims_format {SUMMARY_FORMATS[t.fmt - 1]!r}, "
                      f"which has no {verdict} lines")
        else:
            t.problem(f"{where}: {shown} for {text} is in a format {t.fmt} cell, which has no {verdict} claims")
    elif verdict == CPS and _cps_fields(rest) is None:
        t.invalid += 1
        t.problem(f"{where}: {shown} has n or c out of range (n from 1 to {CPS_MAX_N}, c from 1 to {CPS_MAX_C})")
    elif verdict == RWL and _rwl_fields(rest) is None:
        t.invalid += 1
        t.problem(f"{where}: {shown} has b, T or c out of range (b from 1 to {RWL_MAX_B}, T from 1 to {RWL_MAX_T}, "
                  f"c from 1 to {RWL_MAX_C})")
    elif verdict == FAR and isinstance(far := _far_certificate(text, machine, rest), str):
        t.invalid += 1
        t.problem(f"{where}: {shown} {far}")
    elif verdict == CPSH and _cpsh_fields(rest) is None:
        t.invalid += 1
        t.problem(f"{where}: {shown} has n, H or c out of range (n from 1 to {CPSH_MAX_N}, H from 1 to {CPSH_MAX_H}, "
                  f"c from 1 to {CPSH_MAX_C})")
    elif verdict in ("NONHALT_CYCLER", "NONHALT_TRANSLATED") and _bounded(rest[-1]) > MAX_CAP:
        t.invalid += 1
        t.problem(f"{where}: {shown} has j above the bound {MAX_CAP} of this checker")
    elif not _verify(machine, verdict, rest, text):
        t.invalid += 1
        t.problem(f"{where}: {shown} is not a valid certificate for {text}")
    return verdict


def _claims_job(job: tuple[int, list[bytes], int]) -> ClaimTally:
    """Pool worker: parse, count and verify a chunk of claims lines, which start at line number job[0]. job[2] is the
    cell's format."""
    start, lines, fmt = job
    t = ClaimTally(fmt=fmt)
    for offset, raw in enumerate(lines):
        no = start + offset
        if raw.endswith(b"\n"):
            raw = raw[:-1]
        else:
            t.problem(f"claims line {no} does not end with a newline")
        _claim(t, raw, f"claims line {no}")
    t.claims_sum &= MASK
    t.claimed_sum &= MASK
    return t


def _open_claims(cell_dir: Path) -> tuple[str, IO[bytes]] | None:
    plain, packed = cell_dir / "claims.tsv", cell_dir / "claims.tsv.gz"
    if plain.is_file():
        return plain.name, open(plain, "rb")
    if packed.is_file():
        return packed.name, gzip.open(packed, "rb")
    return None


def _check_claims(cell_dir: Path, pool: Any, jobs: int, fmt: int) -> tuple[ClaimTally, str | None]:
    """Stream the claims file in chunks. Returns the tally and an error message if the file could not be read."""
    tally = ClaimTally()
    pending: deque[Any] = deque()

    def submit(job: tuple[int, list[bytes], int]) -> None:
        if pool is None:
            tally.merge(_claims_job(job))
            return
        pending.append(pool.apply_async(_claims_job, (job,)))
        while len(pending) > 2 * jobs:  # bounded memory whatever the file size
            tally.merge(pending.popleft().get())

    opened = _open_claims(cell_dir)
    if opened is None:
        return tally, "the cell has no claims.tsv or claims.tsv.gz"
    name, stream = opened
    error = None
    try:
        with stream:
            chunk: list[bytes] = []
            start = 1
            for raw in stream:
                chunk.append(raw)
                if len(chunk) == CHUNK_LINES:
                    submit((start, chunk, fmt))
                    start += len(chunk)
                    chunk = []
            if chunk:
                submit((start, chunk, fmt))
    except (OSError, EOFError, zlib.error) as e:
        error = f"{name} could not be read to the end: {e}"
    while pending:
        tally.merge(pending.popleft().get())
    return tally, error


# ---------------------------------------------------------------------------------------------------------------------
# The grouped claims (section 5 "claims.idx", and section 9 "When claims.idx exists")

BESIDE = "claims.tsv exists beside claims.idx, and section 5 says it must not"


@dataclass(frozen=True)
class Member:
    """One row of claims.idx: a gzip member of claims.tsv.gz."""
    seq: int
    offset: int
    size: int  # bytes
    lines: int


def _list(values: Sequence[int]) -> str:
    shown = ", ".join(str(v) for v in values[:10])
    return shown + (", ..." if len(values) > 10 else "")


def _parse_index(path: Path, failures: list[str]) -> dict[str, list[Member]] | None:
    """Each group's members in seq order, groups in file order, or None, with a failure, when claims.idx is not
    readable as a header and rows."""
    fail = failures.append
    try:
        raw = path.read_bytes()
    except OSError as e:
        fail(f"claims.idx could not be read: {e}")
        return None
    try:
        lines = raw.decode("utf-8").split("\n")
    except UnicodeDecodeError:
        fail("claims.idx is not UTF-8")
        return None
    if lines.pop() != "":
        fail("claims.idx does not end with a newline")
        return None
    if not lines or lines[0] != INDEX_HEADER:
        fail(f"claims.idx does not start with the header line {INDEX_HEADER!r}")
        return None
    groups: dict[str, list[Member]] = {}
    for no, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        if len(fields) != 5 or not all(_uint(x) and len(x) <= MAX_DIGITS for x in fields[1:]):
            fail(f"claims.idx line {no} is not a group and four counts: {line!r}")
            return None
        seq, offset, size, count = (int(x) for x in fields[1:])
        groups.setdefault(fields[0], []).append(Member(seq, offset, size, count))
    for g, members in groups.items():
        members.sort(key=lambda m: m.seq)
        seqs = [m.seq for m in members]
        if seqs != list(range(len(seqs))):
            fail(f"claims.idx group {g} has the seq values {_list(seqs)}, not 0, 1, 2 and so on")
    return groups


def _check_tiling(groups: dict[str, list[Member]], size: int, failures: list[str]) -> None:
    """Sorted by offset, the members tile claims.tsv.gz from its first byte to its last (section 5)."""
    rows = sorted((m.offset, m.size, m.seq, g) for g, members in groups.items() for m in members)
    end = 0
    for offset, length, seq, g in rows:
        if offset != end or length == 0:
            what = f"starts at byte {offset}, not at byte {end}" if offset != end else "has no bytes"
            failures.append(f"claims.idx does not tile claims.tsv.gz: member {seq} of group {g} {what}")
            return
        end = offset + length
    if end != size:
        failures.append(f"claims.idx does not tile claims.tsv.gz: its members end at byte {end}, and the file has "
                        f"{size} bytes")


def _read_index(cell_dir: Path, summary: dict[str, Any], cor: Corridor,
                failures: list[str]) -> tuple[int, dict[str, list[Member]]] | None:
    """Step 1 of the indexed check. Returns claims_split and the groups, or None, with failures, when the check must
    stop at once."""
    before = len(failures)
    fail = failures.append
    if (cell_dir / "claims.tsv").exists():
        fail(BESIDE)
    split = summary.get("claims_split")
    if "claims_split" not in summary:
        fail("summary.json has no claims_split, which claims.idx requires")
    elif not (_uint_value(split) and 1 <= split <= cor.depth):
        fail(f"claims_split {_json(split)} is not a depth from 1 to {cor.depth}")
    for d, entry in enumerate(summary["corridor"]):
        if "halt_steps" not in entry:
            fail(f"summary.json corridor entry {d} has no halt_steps, which claims.idx requires")
    try:
        size: int | None = (cell_dir / "claims.tsv.gz").stat().st_size
    except OSError:
        fail("claims.idx exists but claims.tsv.gz does not")
        size = None
    groups = _parse_index(cell_dir / "claims.idx", failures)
    if groups is not None and size is not None:
        _check_tiling(groups, size, failures)
    if len(failures) > before or groups is None:
        return None
    return split, groups


def _member_lines(f: IO[bytes], group: str, m: Member, claims: ClaimTally) -> Iterator[bytes]:
    """The claims lines of one member, each without its newline. The member is streamed, so memory stays constant,
    and it must be exactly one gzip member that decompresses to whole lines, as many as claims.idx says."""
    where = f"member {m.seq} of group {group} at byte {m.offset}"
    z = zlib.decompressobj(wbits=31)
    pos, end = m.offset, m.offset + m.size
    part = b""
    count = 0
    try:
        while pos < end and not z.eof:
            f.seek(pos)
            data = f.read(min(READ_BYTES, end - pos))
            if not data:
                claims.defect(f"{where} runs past the end of claims.tsv.gz")
                return
            pos += len(data)
            out = z.decompress(data)
            if out:
                pieces = (part + out).split(b"\n")
                part = pieces.pop()
                count += len(pieces)
                yield from pieces
    except (OSError, zlib.error) as e:
        claims.defect(f"{where} could not be decompressed: {e}")
        return
    rest = len(z.unused_data) + end - pos
    if not z.eof:
        claims.defect(f"{where} is not a complete gzip member")
    elif rest:
        claims.defect(f"{where} is not exactly one gzip member ({_count(rest, 'byte')} follow its end)")
    elif part:
        claims.defect(f"{where} does not decompress to whole lines (its last line has no newline)")
    elif count != m.lines:
        claims.defect(f"{where} holds {_count(count, 'claims line')}, and claims.idx says {m.lines}")


class _Lines:
    """One group's claims lines in seq order, read a member at a time, with one line of lookahead."""

    def __init__(self, f: IO[bytes], group: str, members: Sequence[Member], claims: ClaimTally) -> None:
        self.group = group
        self.taken = 0
        self._it = (line for m in members for line in _member_lines(f, group, m, claims))
        self.next: bytes | None = None
        self.text: str | None = None  # the next line's text
        self._advance()

    def _advance(self) -> None:
        self.next = next(self._it, None)
        self.text = None if self.next is None else self.next.split(b"\t", 1)[0].decode("utf-8", "replace")

    def where(self) -> str:
        """The next line's name in messages."""
        return f"group {self.group} line {self.taken + 1}"

    def take(self) -> bytes:
        line = self.next
        assert line is not None
        self.taken += 1
        self._advance()
        return line


def _use_claim(lines: _Lines, claims: ClaimTally, text: str, d: int, table: Table,
               bound: int) -> tuple[int, int, int] | None:
    """The next line is M's claim. Returns None when M is unhalted, or (steps, state * width, symbol) when M is
    claimed UNKNOWN but halts, which fails."""
    where = lines.where()
    if _claim(claims, lines.take(), where, (d, table)) != "UNKNOWN":
        return None  # a certificate, verified by _claim, or a line that does not parse
    if _GPU:
        # the run happens in _gpu_bound_runs after the walk. Until then M counts as unhalted, which is what it is in
        # every passing check; a halt found later is the same defect, and the check fails.
        claims.deferred.append((text, d, where))
        return None
    halted, n, st, r = _run(table, bound)
    if not halted:
        return None
    claims.defect(_unknown_halts(where, text, d, n))
    return n, st, r


def _unknown_halts(where: str, text: str, d: int, n: int) -> str:
    return f"{where}: {text} at depth {d} is claimed UNKNOWN but halts after {_count(n, 'step')}"


def _gpu_bound_runs(cor: Corridor, claims: ClaimTally) -> None:
    """--gpu: run the deferred UNKNOWN claims to their depths' bounds on the GPU (experiments/bbi/bbi9/gpu), each
    depth as one batch, and record the defect for each one that halts. The GPU runner falls back to _run for a machine
    whose tape outgrows every width it tries, so every verdict is _run's."""
    if not claims.deferred:
        return
    root = Path(__file__).resolve().parents[4]  # the repository, where experiments.bbi.bbi9.gpu lives
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from experiments.bbi.bbi9.gpu.bound import BoundRunner, Stats
    started = time.perf_counter()
    by_depth: dict[int, list[tuple[str, str]]] = {}
    for text, d, where in claims.deferred:
        by_depth.setdefault(d, []).append((text, where))
    tables = {d: [parse_text(text).table for text, _ in items] for d, items in by_depth.items()}
    runner = BoundRunner(table_max=max(len(t) for ts in tables.values() for t in ts))
    stats = Stats()
    halts = 0
    for d in sorted(by_depth):
        results = runner.run(tables[d], cor.bounds[d], stats=stats, fallback=_run)
        for (text, where), r in zip(by_depth[d], results):
            if r.halted:
                halts += 1
                claims.defect(_unknown_halts(where, text, d, r.steps))
    print(f"gpu: {len(claims.deferred)} UNKNOWN machines run to their bounds, {halts} halt, "
          f"{stats.cpu_fallback} on the CPU, {time.perf_counter() - started:.1f} s", file=sys.stderr, flush=True)
    claims.deferred = []


def _drain(lines: _Lines, claims: ClaimTally, at: int) -> None:
    """When a group's walk ends, its lines must be used up. Lines left over are still counted and verified.

    The message for lines left over goes at position at, where the group's messages start, so a long run of
    machines that lost their place behind a misplaced line cannot push it out.
    """
    left = 0
    while lines.next is not None:
        where = lines.where()
        _claim(claims, lines.take(), where)
        left += 1
    if left:
        claims.defect(f"group {lines.group}: its walk ends with {_count(left, 'claims line')} unread", at)


def _groups_job(job: tuple[Corridor, str, list[tuple[Node, str, list[Member]]], int]) -> tuple[WalkTally, ClaimTally]:
    """Pool worker: walk a batch of groups, each reading its own claims alongside. job[3] is the cell's format."""
    cor, path, batch, fmt = job
    walk, claims = WalkTally.empty(cor.depth), ClaimTally(fmt=fmt)
    with open(path, "rb") as f:
        for node, group, members in batch:
            at = len(claims.messages)
            lines = _Lines(f, group, members, claims)
            walk.merge(_walk(cor, [node], lines=lines, claims=claims))
            _drain(lines, claims, at)
    claims.claims_sum &= MASK
    claims.claimed_sum &= MASK
    return walk, claims


def _check_indexed(cell_dir: Path, cor: Corridor, split: int, index: dict[str, list[Member]], pool: Any,
                   jobs: int, fmt: int, core: CoreRun | None = None) -> tuple[WalkTally, ClaimTally]:
    """Steps 2 and 3 of the indexed check. The top group is walked here. The groups it reaches go to the pool in
    batches as they are reached, with a bounded number pending, and are merged in the order reached. While they are
    walked, a progress line goes to stderr every PROGRESS_SECS seconds. With core, bbi9check-core walks the batches
    (_core_groups_job), and core counts them."""
    path = str(cell_dir / "claims.tsv.gz")
    walk = WalkTally.empty(cor.depth)
    top_claims, group_claims = ClaimTally(fmt=fmt), ClaimTally()
    pending: deque[Any] = deque()
    batch: list[tuple[Node, str, list[Member]]] = []
    progress = Progress(time.perf_counter())
    worker: Callable[[Any], Any] = _groups_job if core is None else _core_groups_job

    def collect(result: tuple[Any, ...]) -> None:
        walk.merge(result[0])
        group_claims.merge(result[1])
        progress.add(result[0], result[1], cor.bounds)
        if core is not None:
            core.batches += 1
            core.redone += int(result[2])
            core.backend = result[3]

    def flush() -> None:
        nonlocal batch
        if not batch:
            return
        job: tuple[Any, ...] = (cor, path, batch, fmt) if core is None else (cor, path, batch, fmt, str(core.exe))
        batch = []
        if pool is None:
            collect(worker(job))
            return
        pending.append(pool.apply_async(worker, (job,)))
        while len(pending) > 2 * jobs:
            collect(pending.popleft().get())

    def emit(node: Node) -> None:
        group = _node_text(node, cor.symbols)
        batch.append((node, group, index.pop(group, [])))
        if len(batch) == BATCH_GROUPS:
            flush()

    root = _root(cor)
    try:
        with _reporting(progress):
            with open(path, "rb") as f:
                lines = _Lines(f, TOP_GROUP, index.pop(TOP_GROUP, []), top_claims)
                top_walk = _walk(cor, [] if root is None else [root], split, emit, lines, top_claims)
                walk.merge(top_walk)
                _drain(lines, top_claims, 0)
            progress.add(top_walk, top_claims, cor.bounds)
            flush()
            while pending:
                collect(pending.popleft().get())
    finally:
        if core is not None:
            _core_close()  # this process's core. A pool worker's core reads EOF on stdin when the pool ends.
    claims = ClaimTally()
    claims.merge(top_claims)
    claims.merge(group_claims)
    for group in index:
        claims.defect(f"claims.idx names the group {group}, which the walk never reaches")
    return walk, claims


# ---------------------------------------------------------------------------------------------------------------------
# The compiled core (section 9, An accelerated checker)
#
# bbi9check-core (core/, Rust) walks a batch of groups as _groups_job does, counting each NONHALT_CYCLER or
# NONHALT_TRANSLATED claim it finds valid and written cleanly, and hands every other claims line back as a RARE line,
# which _claim reads here as it would in _groups_job. A batch the core cannot walk exactly as _groups_job would (a
# member it refuses, a machine that does not halt and is not claimed, lines left over, a count past 64 bits) comes
# back REDO, and _groups_job walks it again, so every failure message is the Python checker's own.

CORE_DIR = Path(__file__).resolve().parent / "core"
CORE_MANIFEST = CORE_DIR / "Cargo.toml"
CORE_EXE = CORE_DIR / "target" / "release" / ("bbi9check-core.exe" if os.name == "nt" else "bbi9check-core")
CORE_PROTOCOL = "1"
CORE_SUFFIX = " core"  # appended to CHECKER in a check.json when the core walked at least one batch
CORE_CLOSE_SECS = 10  # how long _Core.close waits for the core to exit before killing it
_CORE_VERDICTS = ("NONHALT_CYCLER", "NONHALT_TRANSLATED")
_CORE_LISTS = ("machines", "halters", "unhalted", "max_steps", "halt_steps")
_CORE_SUMS = ("late", "halter_sum", "unhalted_sum", "lines", "claims_sum", "claimed_sum")


class CoreError(RuntimeError):
    """bbi9check-core failed, or answered outside its protocol."""


@dataclass
class CoreRun:
    """The core an indexed check walks with, and what it did: the batches it walked, how many of them the Python code
    walked again, and the core's SHA-256 backend."""
    exe: Path
    batches: int = 0
    redone: int = 0
    backend: str = ""


def _core_stale(exe: Path, core_dir: Path) -> bool:
    """Whether a file under core_dir / "src", or core_dir / "Cargo.toml", was changed after exe was built. A time that
    cannot be read warns of nothing, since the warning is advice and the check is done."""
    try:
        built = exe.stat().st_mtime
        sources = [f for f in (core_dir / "src").rglob("*") if f.is_file()] + [core_dir / "Cargo.toml"]
        return any(f.stat().st_mtime > built for f in sources if f.is_file())
    except OSError:
        return False


def _core_command(exe: str, path: str, cor: Corridor) -> list[str]:
    """The core's start line for the cell. The late caps are read now, so a patched CAP_SHALLOW reaches the core."""
    return [exe, "serve", path, "--cell", f"{cor.states},{cor.symbols},{cor.depth}",
            "--bounds", ",".join(str(b) for b in cor.bounds), "--late-caps", f"{CAP_SHALLOW},{CAP_DEPTH8}"]


def _core_request(groups: Sequence[tuple[bool, str, Sequence[Member]]]) -> bytes:
    """One batch's request: the BATCH line and a GROUP line per group, with its late flag, root and members."""
    lines = [f"BATCH\t{len(groups)}\n"]
    for late, text, members in groups:
        parts = ["GROUP", "1" if late else "0", text] + [f"{m.offset}:{m.size}:{m.lines}" for m in members]
        lines.append("\t".join(parts) + "\n")
    return "".join(lines).encode("utf-8")


def _core_int(x: bytes) -> int:
    if not (x.isdigit() and len(x) <= MAX_DIGITS):
        raise CoreError(f"bbi9check-core sent {x!r} where a number belongs")
    return int(x)


class _Core:
    """One bbi9check-core serve process for one cell."""

    def __init__(self, command: list[str]) -> None:
        self.command = command
        # D, from the start line's --cell S,K,D, bounds the depth of a RARE line
        cell = command[command.index("--cell") + 1].split(",") if "--cell" in command[:-1] else []
        if not (len(cell) == 3 and _uint(cell[2])):
            raise CoreError(f"bbi9check-core was given no --cell S,K,D: {command!r}")
        self.depth = int(cell[2])
        try:
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        except OSError as e:
            raise CoreError(f"bbi9check-core could not be started: {e}") from e
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.stdin, self.stdout = self.proc.stdin, self.proc.stdout
        try:
            first = self.stdout.readline()
        except OSError as e:
            self._kill()
            raise CoreError(f"bbi9check-core could not be read: {e}") from e
        if not first:
            self._kill()
            raise CoreError(f"bbi9check-core exited before it was ready (exit {self.proc.returncode})")
        parts = first.rstrip(b"\n").split(b"\t")
        if not (first.endswith(b"\n") and len(parts) == 4 and parts[0] == b"READY" and parts[1] == b"bbi9check-core"
                and parts[2] == CORE_PROTOCOL.encode()):
            self._kill()
            got = parts[2].decode("utf-8", "replace") if len(parts) >= 3 else repr(first)
            raise CoreError(f"bbi9check-core speaks protocol {got}, and this checker speaks protocol {CORE_PROTOCOL}")
        self.backend: str = parts[3].decode("utf-8", "replace")

    def _kill(self) -> None:
        try:
            self.proc.kill()
        except OSError:
            pass
        self.proc.wait()

    def batch(self, groups: Sequence[tuple[bool, str, Sequence[Member]]]
              ) -> tuple[list[tuple[int, int, int, bytes]], dict[str, Any] | None]:
        """Walk one batch of (late, root text, members). Returns the RARE lines as (group index, line number in the
        group, depth, raw line) in walk order and the tally, or ([], None) when the core answers REDO."""
        try:
            self.stdin.write(_core_request(groups))  # the whole request before the first read, so no pipe fills
            self.stdin.flush()
        except OSError as e:  # BrokenPipeError among them
            raise CoreError(f"bbi9check-core could not be sent a batch: {e}") from e
        rare: list[tuple[int, int, int, bytes]] = []
        while True:
            try:
                line = self.stdout.readline()
            except OSError as e:
                raise CoreError(f"bbi9check-core could not be read: {e}") from e
            if not line.endswith(b"\n"):
                raise CoreError("bbi9check-core exited in the middle of a batch")
            if line.startswith(b"RARE\t"):
                parts = line[:-1].split(b"\t", 4)  # never rstrip: the claims line may end with a CR
                if len(parts) != 5:
                    raise CoreError(f"bbi9check-core sent a RARE line without five fields: {line[:200]!r}")
                g, no, d = (_core_int(x) for x in parts[1:4])
                if g >= len(groups) or no < 1 or d > self.depth:
                    raise CoreError(f"bbi9check-core sent a RARE line outside the batch: {line[:200]!r}")
                rare.append((g, no, d, parts[4]))
            elif line.startswith(b"TALLY\t"):
                try:
                    tally = json.loads(line[6:])
                except ValueError as e:
                    raise CoreError(f"bbi9check-core sent a TALLY that is not JSON: {e}") from e
                if not isinstance(tally, dict):
                    raise CoreError("bbi9check-core sent a TALLY that is not an object")
                return rare, tally
            elif line.startswith(b"REDO\t"):
                return [], None
            else:
                raise CoreError(f"bbi9check-core sent a line that is not RARE, TALLY or REDO: {line[:200]!r}")

    def close(self) -> None:
        """Close stdin, so an idle core reads EOF at a request boundary and exits, and stdout, so a core still writing
        a reply nobody will read fails its write and exits rather than block, and kill it if it has not exited within
        CORE_CLOSE_SECS."""
        for pipe in (self.stdin, self.stdout):
            try:
                pipe.close()
            except OSError:
                pass
        try:
            self.proc.wait(CORE_CLOSE_SECS)
        except subprocess.TimeoutExpired:
            self._kill()


_CORE: _Core | None = None  # this process's core, kept between batches


def _core_for(command: list[str]) -> _Core:
    """This process's core for the command, started or restarted when the command differs."""
    global _CORE
    if _CORE is None or _CORE.command != command:
        _core_close()
        _CORE = _Core(command)
    return _CORE


def _core_close() -> None:
    global _CORE
    core, _CORE = _CORE, None
    if core is not None:
        core.close()


def _from_core(tally: dict[str, Any], depth: int, fmt: int) -> tuple[WalkTally, ClaimTally]:
    """The core's TALLY as the tallies _groups_job returns, without the messages RARE lines add."""
    def uint(x: object) -> bool:
        return type(x) is int and 0 <= x <= MASK

    for key in _CORE_LISTS + _CORE_SUMS + ("top", "counts"):
        if key not in tally:
            raise CoreError(f"bbi9check-core sent a TALLY without {key}")
    for key in _CORE_LISTS:
        v = tally[key]
        if not (isinstance(v, list) and len(v) == depth + 1 and all(uint(x) for x in v)):
            raise CoreError(f"bbi9check-core sent a TALLY whose {key} is not {depth + 1} counts")
    for key in _CORE_SUMS:
        if not uint(tally[key]):
            raise CoreError(f"bbi9check-core sent a TALLY whose {key} is not a count below 2^64")
    top = tally["top"]
    if not (isinstance(top, list) and len(top) <= TOP and all(
            isinstance(x, list) and len(x) == 2 and uint(x[0]) and isinstance(x[1], str) for x in top)):
        raise CoreError("bbi9check-core sent a TALLY whose top is not a list of [steps, text]")
    keyed = [(-steps, text) for steps, text in top]  # WalkTally's order: most steps first, then text
    if keyed != sorted(keyed):
        raise CoreError("bbi9check-core sent a TALLY whose top is not in order")
    counts: dict[tuple[int, str], int] = {}
    entries = tally["counts"]
    if not isinstance(entries, list):
        raise CoreError("bbi9check-core sent a TALLY whose counts is not a list")
    for x in entries:
        if not (isinstance(x, list) and len(x) == 3 and uint(x[0]) and x[0] <= depth and x[1] in _CORE_VERDICTS
                and uint(x[2]) and x[2] > 0 and (x[0], x[1]) not in counts):
            raise CoreError(f"bbi9check-core sent a TALLY with the count {x!r}")
        counts[(x[0], x[1])] = x[2]
    walk = WalkTally(*(list(tally[key]) for key in _CORE_LISTS), late=tally["late"],
                     halter_sum=tally["halter_sum"], unhalted_sum=tally["unhalted_sum"], top=keyed)
    claims = ClaimTally(fmt=fmt, lines=tally["lines"], counts=counts, claims_sum=tally["claims_sum"],
                        claimed_sum=tally["claimed_sum"])
    return walk, claims


def _zlib_accepts_members(path: str, batch: Sequence[tuple[Node, str, Sequence[Member]]]) -> bool:
    """Whether zlib, making exactly _member_lines's calls, accepts every member of the batch as one whole gzip
    member. The output is discarded: lines and counts are left to the core, which answers REDO for them."""
    try:
        with open(path, "rb") as f:
            for _, _, members in batch:
                for m in members:
                    z = zlib.decompressobj(wbits=31)
                    pos, end = m.offset, m.offset + m.size
                    while pos < end and not z.eof:
                        f.seek(pos)
                        data = f.read(min(READ_BYTES, end - pos))
                        if not data:
                            return False
                        pos += len(data)
                        z.decompress(data)
                    if not z.eof or len(z.unused_data) + end - pos:
                        return False
    except (OSError, zlib.error):
        return False
    return True


def _core_groups_job(job: tuple[Corridor, str, list[tuple[Node, str, list[Member]]], int, str]
                     ) -> tuple[WalkTally, ClaimTally, bool, str]:
    """Pool worker: _groups_job by the core. job is _groups_job's job and the core's path. Returns the tallies,
    whether the batch was redone by _groups_job, and the core's backend."""
    cor, path, batch, fmt, exe = job
    core = _core_for(_core_command(exe, path, cor))
    if not _zlib_accepts_members(path, batch):  # zlib judges every member, as _member_lines does
        return (*_groups_job((cor, path, batch, fmt)), True, core.backend)
    rare, tally = core.batch([(node[6], group, members) for node, group, members in batch])
    if tally is None:
        return (*_groups_job((cor, path, batch, fmt)), True, core.backend)
    walk, claims = _from_core(tally, cor.depth, fmt)
    for g, no, d, raw in rare:  # walk order, so messages come in _groups_job's order
        where = f"group {batch[g][1]} line {no}"
        if _claim(claims, raw, where) != "UNKNOWN":
            continue
        text = raw.split(b"\t", 1)[0].decode("ascii")
        machine = parse_text(text)
        if machine.depth != d:  # the core's depth sets the bound, so it is checked, never trusted
            raise CoreError(f"bbi9check-core gave depth {d} for {text}, which has depth {machine.depth}")
        if _GPU:
            claims.deferred.append((text, d, where))
        elif _run(machine.table, cor.bounds[d])[0]:  # claimed UNKNOWN but halts: walk it as Python does
            return (*_groups_job((cor, path, batch, fmt)), True, core.backend)
    claims.claims_sum &= MASK
    claims.claimed_sum &= MASK
    return walk, claims, False, core.backend


# ---------------------------------------------------------------------------------------------------------------------
# The census (section 8)


def census_count(census: Path, states: int, symbols: int, depth: int) -> int | None:
    """nodes in the row (D, S, K) when D <= 8, pred in the row (9, S, K) when D = 9, and 0 for a missing row. For D
    from 10 on there is no census count, and the result is None without the file being read."""
    if depth > CENSUS_DEPTH:
        return None
    with open(census, encoding="utf-8") as f:
        header = f.readline().rstrip("\r\n").split("\t")
        try:
            cols = [header.index(c) for c in ("depth", "states", "symbols", "nodes" if depth <= 8 else "pred")]
        except ValueError as e:
            raise ValueError(f"the census header lacks a column: {e}") from None
        want = (depth, states, symbols)
        for line in f:
            if not line.strip():
                continue
            fields = line.rstrip("\r\n").split("\t")
            if (int(fields[cols[0]]), int(fields[cols[1]]), int(fields[cols[2]])) == want:
                return int(fields[cols[3]])
    return 0


# ---------------------------------------------------------------------------------------------------------------------
# The check (section 9)


def _uint_value(x: object) -> bool:
    return type(x) is int and x >= 0


def _format_number(summary: dict[str, Any]) -> int:
    """1 to 5 for a summary whose format is one of SUMMARY_FORMATS."""
    return SUMMARY_FORMATS.index(summary["format"]) + 1


def _read_summary(cell_dir: Path, result: dict[str, Any], failures: list[str]) -> tuple[dict[str, Any], Corridor] | None:
    """Step 1. Returns None, with failures, when the check must stop at once."""
    try:
        raw = (cell_dir / "summary.json").read_bytes()
    except OSError as e:
        failures.append(f"summary.json could not be read: {e}")
        return None
    result["summary_sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        summary = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        failures.append(f"summary.json is not JSON: {e}")
        return None
    if not isinstance(summary, dict) or not isinstance(summary.get("format"), str) or \
            summary["format"] not in SUMMARY_FORMATS:
        failures.append(f"summary.json does not have format {SUMMARY_NAMED}")
        return None
    fmt = _format_number(summary)
    cell, depth = summary.get("cell"), summary.get("depth")
    if not (isinstance(cell, list) and len(cell) == 2 and all(_uint_value(x) for x in cell) and _uint_value(depth)):
        failures.append("summary.json has no valid cell [S, K] and depth D")
        return None
    big_s, big_k = cell
    result["cell"], result["depth"] = [big_s, big_k], depth
    if not (1 <= depth <= MAX_DEPTH and 1 <= big_s <= MAX_CELL_STATES and 1 <= big_k <= MAX_SYMBOLS):
        failures.append(f"cell {big_s}x{big_k} at depth {depth} is outside what this checker accepts")
        return None
    corridor = summary.get("corridor")
    if not isinstance(corridor, list) or len(corridor) != depth + 1:
        failures.append(f"summary.json corridor is not a list of {depth + 1} entries")
        return None
    for d, entry in enumerate(corridor):
        if not isinstance(entry, dict) or type(entry.get("depth")) is not int or entry["depth"] != d:
            failures.append(f"summary.json corridor entry {d} does not describe depth {d}")
            return None
        # NONHALT_CPS belongs to formats 2 to 5, NONHALT_RWL to formats 3 to 5, NONHALT_FAR to formats 4 and 5, and
        # NONHALT_CPSH to format 5 (section 5)
        counted = ENTRY_KEYS
        for key, since in SINCE.items():
            if fmt >= since and key not in entry:
                failures.append(f"summary.json corridor entry {d} has no {key}, which format {summary['format']!r} "
                                "requires")
                return None
            if fmt < since and key in entry:
                failures.append(f"summary.json corridor entry {d} has {key}, which format {summary['format']!r} "
                                "does not have")
                return None
            if fmt >= since:
                counted += (key,)
        bad = [key for key in counted if not _uint_value(entry.get(key))]
        if "halt_steps" in entry and not _uint_value(entry["halt_steps"]):  # optional (section 5)
            bad.append("halt_steps")
        if bad:
            failures.append(f"summary.json corridor entry {d} lacks a count for {', '.join(bad)}")
            return None
    bounds = tuple(entry["max_halt_steps"] for entry in corridor)
    over = [(d, b) for d, b in enumerate(bounds) if b > MAX_CAP]
    for d, b in over:
        failures.append(f"depth {d} max_halt_steps {b} is above the bound {MAX_CAP} of this checker "
                        "(such cells need a faster checker)")
    if over:
        return None
    return summary, Corridor(big_s, big_k, depth, bounds)


def _json(x: object) -> str:
    return json.dumps(x, sort_keys=True)


def _holdout_list(cell_dir: Path, name: str, texts: list[str], what: str) -> str | None:
    expected = "".join(t + "\n" for t in sorted(texts, key=lambda t: t.encode("utf-8"))).encode("utf-8")
    try:
        actual = (cell_dir / name).read_bytes()
    except OSError:
        return f"{name} is missing"
    if actual != expected:
        lines = actual.count(b"\n")
        return f"{name} does not hold exactly the {len(texts)} sorted UNKNOWN texts {what} (it has {lines} lines)"
    return None


def _amends_this_summary(cell_dir: Path, summary_sha256: str) -> bool:
    """Whether amend.json exists, is a JSON object and has the base_summary_sha256 summary_sha256, so that the full
    check leaves the holdout lists to the amendment check (section 12, "The full check of an amended cell")."""
    try:
        amend = json.loads((cell_dir / "amend.json").read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    return isinstance(amend, dict) and amend.get("base_summary_sha256") == summary_sha256


def _compare(cell_dir: Path, summary: dict[str, Any], cor: Corridor, walk: WalkTally, claims: ClaimTally,
             claims_error: str | None, result: dict[str, Any], failures: list[str], amended: bool = False) -> None:
    """Step 4. Fills the checker's own values into result and appends a message for each mismatch. With amended, the
    holdout lists are left to the amendment check."""
    big_d = cor.depth
    fail = failures.append
    if claims_error:
        fail(claims_error)
    for d, entry in enumerate(summary["corridor"]):
        for key, ours in (("machines", walk.machines[d]), ("HALT", walk.halters[d]),
                          ("max_halt_steps", walk.max_steps[d])):
            if entry[key] != ours:
                fail(f"depth {d}: summary.json has {key} {entry[key]}, the walk finds {ours}")
        if "halt_steps" in entry and entry["halt_steps"] != walk.halt_steps[d]:
            fail(f"depth {d}: summary.json has halt_steps {entry['halt_steps']}, the walk finds {walk.halt_steps[d]}")
        total = 0
        for verdict in VERDICTS:
            ours = claims.counts.get((d, verdict), 0)
            total += ours
            # a format 1 entry has no NONHALT_CPS, a format 1 or 2 entry no NONHALT_RWL, a format 1 to 3 entry no
            # NONHALT_FAR and a format 1 to 4 entry no NONHALT_CPSH. Their counts are taken as 0.
            theirs = entry.get(verdict, 0)
            if theirs != ours:
                fail(f"depth {d}: summary.json has {verdict} {theirs}, the claims file has {ours}")
        if total != walk.unhalted[d]:
            fail(f"depth {d}: the claims file has {total} claims, the walk finds {walk.unhalted[d]} unhalted machines")
    beyond = sum(count for (d, _), count in claims.counts.items() if d > big_d)
    if beyond:
        fail(f"{beyond} claims are machines of depth above {big_d}")
    if walk.unhalted_sum != claims.claimed_sum:
        fail(f"the claimed texts are not the unhalted machines (unhalted digest {_hex(walk.unhalted_sum)}, "
             f"claimed digest {_hex(claims.claimed_sum)})")

    holdouts = claims.unknown.get(big_d, [])
    parents = [t for d, texts in claims.unknown.items() if d < big_d for t in texts]
    own: dict[str, Any] = {
        "halter_digest": _hex(walk.halter_sum),
        "claims": claims.lines,
        "claims_digest": _hex(claims.claims_sum),
        "cell_machines": walk.machines[big_d],
        "late_cell_machines": walk.late,
        "holdouts": len(holdouts),
        "parent_holdouts": len(parents),
        "top_halters": [{"machine": text, "steps": -n} for n, text in walk.top],
    }
    for key in OWN_KEYS:
        if key not in summary:
            fail(f"summary.json has no {key}")
        elif _json(summary[key]) != _json(own[key]):
            fail(f"{key}: summary.json has {_json(summary[key])}, the checker finds {_json(own[key])}")
    result.update({k: own[k] for k in ("cell_machines", "late_cell_machines", "holdouts", "parent_holdouts",
                                       "top_halters", "halter_digest", "claims_digest")})
    result["unknown_digest"] = _hex(sum(_h(t.encode("utf-8")) for texts in claims.unknown.values()
                                        for t in texts) & MASK)

    if amended:
        result["holdout_lists"] = "amendment"
    else:
        result["holdout_lists"] = "checked"
        stem = f"BBi{big_d}_{cor.states}x{cor.symbols}"
        for message in (_holdout_list(cell_dir, f"{stem}_holdouts_unofficial.txt", holdouts, f"at depth {big_d}"),
                        _holdout_list(cell_dir, f"{stem}_parent_holdouts_unofficial.txt", parents,
                                      f"at depths below {big_d}")):
            if message:
                fail(message)

    if claims.invalid:
        fail(f"{claims.invalid} certificates are not valid")
    if claims.problems > claims.invalid:
        fail(f"{claims.problems - claims.invalid} claims lines do not parse")
    if claims.defects:
        fail(f"the indexed check finds {_count(claims.defects, 'problem')} with the grouped claims")

    census = result["census"]
    if own["parent_holdouts"] == 0 and census is not None:
        result["census_match"] = own["cell_machines"] - own["late_cell_machines"] == census
        if not result["census_match"]:
            fail(f"census rule: cell_machines {own['cell_machines']} minus late_cell_machines "
                 f"{own['late_cell_machines']} is not the census count {census}")
    else:
        result["census_match"] = None

    failures.extend(claims.messages)  # line by line problems last, so the totals above are never cut off


def _walk_and_claims(cell_dir: Path, cor: Corridor, index: tuple[int, dict[str, list[Member]]] | None, pool: Any,
                     jobs: int, fmt: int, core: CoreRun | None = None) -> tuple[WalkTally, ClaimTally, str | None]:
    """Steps 2 and 3, or the indexed check's steps 2 and 3 when index holds claims_split and the groups. fmt is the
    cell's format, which says whether NONHALT_CPS claims (formats 2 to 5), NONHALT_RWL claims (formats 3 to 5),
    NONHALT_FAR claims (formats 4 and 5) and NONHALT_CPSH claims (format 5) may appear. core, when given, walks the
    indexed check's groups. The check without claims.idx never uses it."""
    if index is not None:
        return (*_check_indexed(cell_dir, cor, index[0], index[1], pool, jobs, fmt, core), None)
    walk = _walk_cell(cor, pool, jobs)
    return (walk, *_check_claims(cell_dir, pool, jobs, fmt))


def _check(cell_dir: Path, census: Path, jobs: int, plain: bool = False, gpu: bool = False,
           python: bool = False) -> tuple[dict[str, Any], int]:
    started = time.perf_counter()
    _set_gpu(gpu)
    # holdout_lists stays null when the check stops before step 4
    result: dict[str, Any] = {
        "format": CHECK_FORMAT, "checker": CHECKER + GPU_SUFFIX if gpu else CHECKER, "cell": None, "depth": None,
        "pass": False, "failures": [],
        "cell_machines": None, "census": None, "late_cell_machines": None, "census_match": None, "holdouts": None,
        "parent_holdouts": None, "holdout_lists": None, "top_halters": None, "halter_digest": None,
        "claims_digest": None, "unknown_digest": None, "seconds": 0.0, "summary_sha256": None,
    }
    failures: list[str] = []
    read = _read_summary(cell_dir, result, failures)
    if read is not None:
        summary, cor = read
        fmt = _format_number(summary)
        try:
            result["census"] = census_count(census, cor.states, cor.symbols, cor.depth)
        except (OSError, ValueError, IndexError) as e:
            failures.append(f"the census {census} could not be read: {e}")
        index = None
        core: CoreRun | None = None
        stop = False
        if (cell_dir / "claims.idx").exists():
            if not plain:
                index = _read_index(cell_dir, summary, cor, failures)
                stop = index is None
            elif (cell_dir / "claims.tsv").exists():
                failures.append(BESIDE)
                stop = True
        if index is not None and not python:
            if CORE_EXE.is_file():
                core = CoreRun(CORE_EXE)
            else:
                _say(f"core: {CORE_EXE} is not built, so the Python walk checks this cell (cargo build --release "
                     f"--manifest-path {CORE_MANIFEST})", sys.stderr)
        if not stop:
            if jobs > 1:
                with multiprocessing.get_context("spawn").Pool(jobs, initializer=_set_gpu, initargs=(gpu,)) as pool:
                    walk, claims, claims_error = _walk_and_claims(cell_dir, cor, index, pool, jobs, fmt, core)
            else:
                walk, claims, claims_error = _walk_and_claims(cell_dir, cor, index, None, 1, fmt, core)
            # "core" only when the core itself walked a batch, not when the Python code walked every batch again
            walked = core is not None and core.batches > core.redone
            result["checker"] = CHECKER + (CORE_SUFFIX if walked else "") + (GPU_SUFFIX if gpu else "")
            if core and core.batches:
                stale = (f". Its build is older than its sources, so rebuild it (cargo build --release --manifest-path "
                         f"{CORE_MANIFEST})") if _core_stale(CORE_EXE, CORE_DIR) else ""
                _say(f"core: {core.batches} batches walked by bbi9check-core ({core.backend} SHA-256), {core.redone} "
                     f"walked again by the Python code{stale}", sys.stderr)
            if gpu:
                _gpu_bound_runs(cor, claims)
            amended = _amends_this_summary(cell_dir, result["summary_sha256"])
            _compare(cell_dir, summary, cor, walk, claims, claims_error, result, failures, amended)
    result["pass"] = not failures
    result["failures"] = failures[:MAX_FAILURES]
    result["seconds"] = round(time.perf_counter() - started, 3)
    with open(cell_dir / "check.json", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(result, indent=2) + "\n")
    return result, len(failures)


def check_cell(cell_dir: Path, census: Path, jobs: int = 1, plain: bool = False, gpu: bool = False,
               python: bool = False) -> dict[str, Any]:
    """Check one cell directory against the census, write check.json into it and return its object.

    A cell with claims.idx gets the indexed check unless plain is set (section 9, "When claims.idx exists"). With gpu,
    the indexed check runs the UNKNOWN claims on the GPU (section 9, "An accelerated checker"). The indexed check's
    groups are walked by bbi9check-core when it is built, and by the Python code, the reference, when it is not or
    when python is set. A failure of the core raises CoreError, and no check.json is written.
    """
    return _check(Path(cell_dir), Path(census), jobs, plain, gpu, python)[0]


# ---------------------------------------------------------------------------------------------------------------------
# The claims scan of the amendment check (section 12 step 3): every line counted and digested, the UNKNOWN lines kept

_DIGEST = methodcaller("digest")
_WORDS = array("Q").itemsize == 8  # an array of "Q" reads 8-byte words, as on every common platform


def _sum_h(lines: list[bytes]) -> int:
    """The sum of h over the lines (section 7), modulo 2^64. The hashes are made and summed in C loops: the first 8
    bytes of each 32-byte SHA-256 digest are every fourth 8-byte word, read big-endian."""
    if not _WORDS:
        return sum(_h(x) for x in lines) & MASK
    words = array("Q", b"".join(map(_DIGEST, map(hashlib.sha256, lines))))
    if sys.byteorder == "little":
        words.byteswap()
    return sum(words[::4]) & MASK


def _unknown_lines(block: bytes) -> list[bytes]:
    """The lines of block whose verdict, the field after the text, is UNKNOWN, each without its newline, in order."""
    found = []
    at = block.find(b"\tUNKNOWN")
    while at >= 0:
        start = block.rfind(b"\n", 0, at) + 1
        end = block.find(b"\n", at)
        if end < 0:
            end = len(block)
        line = block[start:end]
        if line.split(b"\t", 2)[1] == b"UNKNOWN":  # a text has no TAB, so its line's first TAB starts the verdict
            found.append(line)
        at = block.find(b"\tUNKNOWN", end)
    return found


# The texts that the import check looks for among the claims texts (section 13, "Speaking our language"). It is empty
# for the amendment check. A pool's workers get it through _set_find.
_FIND: frozenset[bytes] = frozenset()
_TEXT_FIELD = re.compile(rb"^([^\t\n]*)\t", re.M)  # the text of each claims line, the field before its first TAB


def _set_find(texts: frozenset[bytes]) -> None:
    global _FIND
    _FIND = texts


def _scan_block(block: bytes) -> tuple[int, int, list[bytes], bool, set[bytes]]:
    """Pool worker: the number of lines in a block of lines, the sum of h over them, its UNKNOWN lines, whether it
    ends with a newline, and the texts of _FIND that are texts of its lines. A last line without a newline still
    counts."""
    lines = block.split(b"\n")
    last = lines.pop()
    if last:
        lines.append(last)
    found = _FIND.intersection(_TEXT_FIELD.findall(block)) if _FIND else set()
    return len(lines), _sum_h(lines), _unknown_lines(block), not last, found


def _blocks(chunks: Iterable[bytes]) -> Iterator[bytes]:
    """The bytes of chunks regrouped into blocks of whole lines of about SCAN_BLOCK bytes or more. Only the last
    block may end without a newline."""
    held: list[bytes] = []
    size = 0
    for chunk in chunks:
        held.append(chunk)
        size += len(chunk)
        if size >= SCAN_BLOCK:
            data = b"".join(held)
            cut = data.rfind(b"\n") + 1
            if cut:
                yield data[:cut]
                held, size = [data[cut:]], len(data) - cut
            else:
                held = [data]
    if size:
        yield b"".join(held)


def _gunzip(f: IO[bytes], start: int, end: int | None) -> Iterator[bytes]:
    """The decompressed bytes of the gzip members (RFC 1952) from byte start of f to byte end, or to the end of f,
    one member after another. Raises EOFError when the bytes stop inside a member and zlib.error on bad data."""
    f.seek(start)
    pos = start
    z = zlib.decompressobj(wbits=31)
    fed = False  # whether z holds part of a member it has not finished
    while end is None or pos < end:
        data = f.read(SCAN_READ if end is None else min(SCAN_READ, end - pos))
        if not data:
            break
        pos += len(data)
        while data:
            fed = True
            out = z.decompress(data)
            if out:
                yield out
            if not z.eof:
                break
            data = z.unused_data
            z = zlib.decompressobj(wbits=31)
            fed = False
    if end is not None and pos < end:
        raise EOFError(f"the file ends at byte {pos}, before byte {end}")
    if fed:
        raise EOFError("the file ends inside a gzip member")


@dataclass
class ScanTally:
    lines: int = 0
    total: int = 0  # the sum of h over the lines, modulo 2^64
    unknown: list[bytes] = field(default_factory=list)  # the UNKNOWN lines without their newlines, in file order
    errors: list[str] = field(default_factory=list)  # reads that failed, so that U may be incomplete
    ragged: str | None = None  # the message when the file's last line has no newline
    found: set[bytes] = field(default_factory=set)  # the texts of _FIND that are claims texts

    def add(self, scanned: tuple[int, int, list[bytes], bool, set[bytes]]) -> bool:
        """Add a _scan_block result and return whether its block ends with a newline."""
        n, total, unknown, whole, found = scanned
        self.lines += n
        self.total = (self.total + total) & MASK
        self.unknown.extend(unknown)
        self.found |= found
        return whole

    def merge(self, other: ScanTally) -> None:
        self.lines += other.lines
        self.total = (self.total + other.total) & MASK
        self.unknown.extend(other.unknown)
        self.errors.extend(other.errors)
        self.found |= other.found


def _scan_range(job: tuple[str, int, int]) -> ScanTally:
    """Pool worker: scan the gzip members of claims.tsv.gz from byte job[1] to byte job[2], which must decompress to
    whole lines (section 5, "claims.idx")."""
    path, start, end = job
    t = ScanTally()
    whole = True
    try:
        with open(path, "rb") as f:
            for block in _blocks(_gunzip(f, start, end)):
                whole = t.add(_scan_block(block))
    except (OSError, EOFError, zlib.error) as e:
        t.errors.append(f"claims.tsv.gz could not be read from byte {start} to byte {end}: {e}")
    else:
        if not whole:
            t.errors.append(f"the gzip members of claims.tsv.gz from byte {start} to byte {end} do not decompress "
                            "to whole lines")
    return t


def _scan_ranges(cell_dir: Path) -> list[tuple[int, int]] | None:
    """Byte ranges of claims.tsv.gz, each of whole members of about SCAN_TASK bytes or more, that together are the
    file, for a scan split by claims.idx. None when there is no claims.idx or it does not tile claims.tsv.gz as
    section 5 says. The scan then reads the file from start to end, as a checker may always do. The ranges depend on
    the file alone, never on --jobs."""
    index = cell_dir / "claims.idx"
    if not index.is_file():
        return None
    unused: list[str] = []
    groups = _parse_index(index, unused)
    try:
        size = (cell_dir / "claims.tsv.gz").stat().st_size
    except OSError:
        return None
    if groups is None or unused:
        return None
    _check_tiling(groups, size, unused)
    if unused:
        return None
    ranges: list[tuple[int, int]] = []
    start = 0
    for offset, length in sorted((m.offset, m.size) for members in groups.values() for m in members):
        if offset + length - start >= SCAN_TASK:
            ranges.append((start, offset + length))
            start = offset + length
    if start < size:
        ranges.append((start, size))
    return ranges


def _scan_claims(cell_dir: Path, pool: Any, jobs: int) -> ScanTally | None:
    """Read every line of the claims file by section 5's rules: claims.tsv if it exists, and otherwise claims.tsv.gz,
    all its gzip members in order. None when neither exists. With a claims.idx that tiles claims.tsv.gz, the scan is
    split by gzip member, and the pool scans the ranges. Otherwise the pool hashes blocks of lines as they are read."""
    plain, packed = cell_dir / "claims.tsv", cell_dir / "claims.tsv.gz"
    if plain.is_file():
        path, ranges = plain, None
    elif packed.is_file():
        path, ranges = packed, _scan_ranges(cell_dir)
    else:
        return None
    t = ScanTally()
    if ranges is not None:
        tasks = [(str(packed), start, end) for start, end in ranges]
        for part in (map(_scan_range, tasks) if pool is None else pool.imap(_scan_range, tasks)):
            t.merge(part)
        return t
    pending: deque[Any] = deque()
    whole = True

    def collect(scanned: tuple[int, int, list[bytes], bool, set[bytes]]) -> None:
        nonlocal whole
        whole = t.add(scanned)

    try:
        with open(path, "rb") as f:
            chunks = iter(lambda: f.read(SCAN_BLOCK), b"") if path == plain else _gunzip(f, 0, None)
            for block in _blocks(chunks):
                if pool is None:
                    collect(_scan_block(block))
                    continue
                pending.append(pool.apply_async(_scan_block, (block,)))
                while len(pending) > 2 * jobs:  # bounded memory whatever the file size
                    collect(pending.popleft().get())
    except (OSError, EOFError, zlib.error) as e:
        t.errors.append(f"{path.name} could not be read to the end: {e}")
    while pending:
        collect(pending.popleft().get())
    if not whole and not t.errors:
        t.ragged = f"the last line of {path.name} does not end with a newline"
    return t


# ---------------------------------------------------------------------------------------------------------------------
# The amendment check (section 12, "The amendment check")


def _same(theirs: object, ours: object) -> bool:
    """Whether a JSON value is the checker's own value, compared as JSON, so that 4.0 and true are not 4. A value with
    no JSON, such as a YAML date in a registry entry, equals nothing."""
    try:
        return _json(theirs) == _json(ours)
    except (TypeError, ValueError, RecursionError):
        return False


def _summary_problem(summary: dict[str, Any]) -> str | None:
    """Why summary.json lacks what the amendment check reads from it before step 7 (format, cell, depth and each
    corridor entry's depth and UNKNOWN), or None. A cell whose full check passed has all of them."""
    if summary.get("format") not in SUMMARY_FORMATS:
        return f"summary.json does not have format {SUMMARY_NAMED}"
    cell, depth = summary.get("cell"), summary.get("depth")
    if not (isinstance(cell, list) and len(cell) == 2 and all(_uint_value(x) for x in cell) and _uint_value(depth)
            and 1 <= depth <= MAX_DEPTH and 1 <= cell[0] <= MAX_CELL_STATES and 1 <= cell[1] <= MAX_SYMBOLS):
        return "summary.json has no valid cell [S, K] and depth D"
    corridor = summary.get("corridor")
    if not isinstance(corridor, list) or len(corridor) != depth + 1:
        return f"summary.json corridor is not a list of {depth + 1} entries"
    for d, entry in enumerate(corridor):
        if not (isinstance(entry, dict) and type(entry.get("depth")) is int and entry["depth"] == d
                and _uint_value(entry.get("UNKNOWN"))):
            return f"summary.json corridor entry {d} does not give the UNKNOWN count of depth {d}"
    return None


def _load(path: Path, fail: Callable[[str], None], why: str = "") -> tuple[bytes, Any] | None:
    """The bytes of a JSON file and its object, or None with a failure when it is missing, not JSON or not an
    object. why ends the message for a missing file."""
    try:
        raw = path.read_bytes()
    except OSError:
        fail(f"{path.name} is missing or could not be read{why}")
        return None
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        fail(f"{path.name} is not JSON")
        return raw, None
    if not isinstance(obj, dict):
        fail(f"{path.name} is not a JSON object")
        return raw, None
    return raw, obj


def _amend_base(cell_dir: Path, result: dict[str, Any], fail: Callable[[str], None],
                rests: str = ", and an amendment rests on a passing full check") -> dict[str, Any] | None:
    """Step 1. Returns summary.json's object, or None when the check cannot go on without it. rests ends the
    messages about check.json."""
    read = _load(cell_dir / "summary.json", fail)
    summary = None
    if read is not None:
        result["summary_sha256"] = hashlib.sha256(read[0]).hexdigest()
        summary = read[1]
    read = _load(cell_dir / "check.json", fail, rests)
    if read is not None and read[1] is not None:
        check = read[1]
        if check.get("pass") is not True:
            fail(f"check.json does not pass{rests}")
        if result["summary_sha256"] is not None and check.get("summary_sha256") != result["summary_sha256"]:
            fail("check.json's summary_sha256 is not the SHA-256 of summary.json, so it checked another summary.json")
    if summary is None:
        return None
    problem = _summary_problem(summary)
    if problem is not None:
        fail(problem)
        return None
    result["cell"], result["depth"] = list(summary["cell"]), summary["depth"]
    return summary


def _amend_corridor(corridor: object, big_d: int, claims_format: object, fail: Callable[[str], None]) -> bool:
    """Step 2's check of amend.json's corridor. Returns whether it is fit for step 5."""
    if not isinstance(corridor, list) or len(corridor) != big_d + 1:
        fail(f"amend.json corridor is not a list of {big_d + 1} entries")
        return False
    ok = True
    for d, entry in enumerate(corridor):
        if not isinstance(entry, dict) or type(entry.get("depth")) is not int or entry["depth"] != d:
            fail(f"amend.json corridor entry {d} does not describe depth {d}")
            ok = False
            continue
        for key in ("NONHALT_CYCLER", "NONHALT_TRANSLATED", CPS, "UNKNOWN"):
            if key not in entry:
                fail(f"amend.json corridor entry {d} has no {key}")
                ok = False
        if claims_format not in CLAIMS_FORMATS:  # step 2 has failed it already
            continue
        number = SUMMARY_FORMATS.index(claims_format) + 1
        # NONHALT_RWL from "bbi9-cell/3" on, NONHALT_FAR from "bbi9-cell/4" on and NONHALT_CPSH from "bbi9-cell/5" on
        for key in (RWL, FAR, CPSH):
            if number >= SINCE[key] and key not in entry:
                fail(f"amend.json corridor entry {d} has no {key}, which claims_format {claims_format!r} requires")
                ok = False
            elif number < SINCE[key] and key in entry:
                fail(f"amend.json corridor entry {d} has {key}, which claims_format {claims_format!r} does not have")
                ok = False
    return ok


def _read_amend(cell_dir: Path, summary: dict[str, Any], result: dict[str, Any],
                fail: Callable[[str], None]) -> tuple[dict[str, Any] | None, int | None, bool]:
    """Step 2. Returns amend.json's object, its claims_format as 2 to 5 when that is usable, and whether its
    corridor is fit for step 5."""
    read = _load(cell_dir / "amend.json", fail)
    if read is None:
        return None, None, False
    result["amend_sha256"] = hashlib.sha256(read[0]).hexdigest()
    amend = read[1]
    if amend is None:
        return None, None, False
    for key in AMEND_KEYS:
        if key not in amend:
            fail(f"amend.json has no {key}")
    if "format" in amend and amend["format"] != AMEND_FORMAT:
        fail(f"amend.json has format {_json(amend['format'])}, not {AMEND_FORMAT!r}")
    claims_fmt = None
    if "claims_format" in amend:
        cf = amend["claims_format"]
        if not (isinstance(cf, str) and cf in CLAIMS_FORMATS):
            fail(f"amend.json has claims_format {_json(cf)}, which is not {CLAIMS_NAMED}")
        elif SUMMARY_FORMATS.index(cf) < SUMMARY_FORMATS.index(summary["format"]):
            fail(f"amend.json has claims_format {cf!r}, which is older than summary.json's format "
                 f"{summary['format']!r}")
        else:
            claims_fmt = SUMMARY_FORMATS.index(cf) + 1
    for key in ("cell", "depth"):
        if key in amend and not _same(amend[key], summary[key]):
            fail(f"amend.json has {key} {_json(amend[key])}, and summary.json has {_json(summary[key])}")
    corridor_ok = "corridor" in amend and _amend_corridor(amend["corridor"], summary["depth"],
                                                         amend.get("claims_format"), fail)
    if "base_summary_sha256" in amend and amend["base_summary_sha256"] != result["summary_sha256"]:
        fail("amend.json's base_summary_sha256 is not the SHA-256 of summary.json, so it amends another summary.json")
    return amend, claims_fmt, corridor_ok


def _list_texts(cell_dir: Path, summary: dict[str, Any],
                fail: Callable[[str], None]) -> list[tuple[str, list[str]]] | None:
    """The two holdout lists of the cell, each as its name and the texts on its lines. None when one is missing."""
    stem = f"BBi{summary['depth']}_{summary['cell'][0]}x{summary['cell'][1]}"
    files: list[tuple[str, list[str]]] = []
    for name in (f"{stem}_holdouts_unofficial.txt", f"{stem}_parent_holdouts_unofficial.txt"):
        try:
            data = (cell_dir / name).read_bytes()
        except OSError:
            fail(f"{name} is missing, and without the claims file U is built from it")
            return None
        files.append((name, data.decode("utf-8", "replace").split("\n")[:-1] if data else []))
    return files


def _base_from_lists(cell_dir: Path, summary: dict[str, Any], fail: Callable[[str], None],
                     amended: bool = True) -> dict[str, int] | None:
    """Step 3 without the claims file. U, each text with its depth, from the two lists and, when amended, the texts of
    amend.tsv, checked against check.json's unknown_digest and summary.json's UNKNOWN counts. None when U cannot be
    built. The amendment check always passes amended; the import check passes whether the cell has an amendment."""
    read = _load(cell_dir / "check.json", fail)
    digest = read[1].get("unknown_digest") if read is not None and read[1] is not None else None
    if not isinstance(digest, str):
        fail("the cell has no claims file, and check.json has no unknown_digest")
        return None
    big_d = summary["depth"]
    files = _list_texts(cell_dir, summary, fail)
    if files is None:
        return None
    if amended:
        tsv = _read_amend_tsv(cell_dir, fail)
        if tsv is None:
            return None
        files.append((tsv[0], [line.split("\t")[0] for line in tsv[1].decode("utf-8", "replace").split("\n")[:-1]]))
    src = "the lists and amend.tsv" if amended else "the two holdout lists"
    base: dict[str, int] = {}
    ok = True
    for name, texts in files:
        for t in texts:
            if t in base:
                fail(f"the text {t} is in two of {src}")
                ok = False
                continue
            try:
                base[t] = parse_text(t).depth
            except ValueError:
                fail(f"the text {t!r} in {name} does not parse")
                ok = False
    if not ok:
        return None
    ours = _hex(sum(_h(t.encode("utf-8")) for t in base))
    if ours != digest:
        fail(f"unknown_digest: check.json has {digest}, {src} give {ours}")
    unknown = [0] * (big_d + 1)
    beyond = 0
    for d in base.values():
        if d <= big_d:
            unknown[d] += 1
        else:
            beyond += 1
    for d, entry in enumerate(summary["corridor"]):
        if entry["UNKNOWN"] != unknown[d]:
            fail(f"depth {d}: summary.json has UNKNOWN {entry['UNKNOWN']}, {src} have {unknown[d]}")
    if beyond:
        fail(f"{src} have {_count(beyond, 'text')} at depths above {big_d}")
    return base


def _base_set(cell_dir: Path, summary: dict[str, Any], pool: Any, jobs: int, fail: Callable[[str], None],
              found: set[str] | None = None) -> dict[str, int] | None:
    """Step 3. U, each text with its depth, or None when the claims file could not be read to the end. found, when
    given, gets the texts of _FIND that are claims texts."""
    big_d = summary["depth"]
    if found is None and not any((cell_dir / name).is_file() for name in ("claims.tsv", "claims.tsv.gz")):
        return _base_from_lists(cell_dir, summary, fail)  # the amendment check, not the import check
    if (cell_dir / "claims.idx").exists() and (cell_dir / "claims.tsv").exists():
        fail(BESIDE)
    scan = _scan_claims(cell_dir, pool, jobs)
    if scan is None:
        fail("the cell has no claims.tsv or claims.tsv.gz")
        return None
    if found is not None:
        found.update(t.decode("utf-8", "replace") for t in scan.found)
    for message in scan.errors + ([scan.ragged] if scan.ragged else []):
        fail(message)
    if not _same(summary.get("claims"), scan.lines):
        fail(f"claims: summary.json has {_json(summary.get('claims'))}, the claims file has {scan.lines} lines")
    if not _same(summary.get("claims_digest"), _hex(scan.total)):
        fail(f"claims_digest: summary.json has {_json(summary.get('claims_digest'))}, the claims file's digest is "
             f"{_json(_hex(scan.total))}")
    base: dict[str, int] = {}
    unknown = [0] * (big_d + 1)
    beyond = 0
    for raw in scan.unknown:
        line = raw.decode("utf-8", "replace")
        fields = line.split("\t")
        try:
            depth = parse_text(fields[0]).depth
        except ValueError:
            depth = -1
        if depth < 0 or not _fields_parse("UNKNOWN", fields[2:]):
            fail(f"the claims file's UNKNOWN line {line!r} does not parse")
            continue
        if fields[0] in base:
            fail(f"the claims file has the UNKNOWN text {fields[0]} on more than one line")
            continue
        base[fields[0]] = depth
        if depth <= big_d:
            unknown[depth] += 1
        else:
            beyond += 1
    for d, entry in enumerate(summary["corridor"]):
        if entry["UNKNOWN"] != unknown[d]:
            fail(f"depth {d}: summary.json has UNKNOWN {entry['UNKNOWN']}, the claims file has {unknown[d]} UNKNOWN "
                 "lines")
    if beyond:
        fail(f"the claims file has {_count(beyond, 'UNKNOWN line')} at depths above {big_d}")
    return None if scan.errors else base


def _read_amend_tsv(cell_dir: Path, fail: Callable[[str], None]) -> tuple[str, bytes] | None:
    """Step 4's read: amend.tsv, or amend.tsv.gz when there is no amend.tsv. Returns the name and the bytes."""
    plain, packed = cell_dir / "amend.tsv", cell_dir / "amend.tsv.gz"
    path = plain if plain.is_file() else packed if packed.is_file() else None
    if path is None:
        fail("neither amend.tsv nor amend.tsv.gz exists")
        return None
    try:
        if path == plain:
            return path.name, path.read_bytes()
        with open(path, "rb") as f:
            return path.name, b"".join(_gunzip(f, 0, None))
    except (OSError, EOFError, zlib.error) as e:
        fail(f"{path.name} could not be read: {e}")
        return None


def _backfill_expected(cell_dir: Path, check: dict[str, Any], summary_sha: str, fail: Callable[[str], None]
                       ) -> tuple[list[str], int, int] | None:
    """The refusals of --unknown-digest that depend on how U is known. Returns the tsv's texts (empty when the cell is
    unamended) and the expected counts of U at depth D and below D, or None after a failure."""
    amend_path = cell_dir / "amend.json"
    amend = None
    if amend_path.is_file():
        read = _load(amend_path, fail)
        if read is None or read[1] is None:
            return None
        amend_raw, amend = read
        if amend.get("base_summary_sha256") != summary_sha:
            amend = None  # it amends another summary.json, so it is not part of this cell's U
    if amend is None:
        if check.get("holdout_lists", "checked") != "checked":
            fail("check.json left the holdout lists to an amendment check, and there is no amend.json for this "
                 "summary.json")
            return None
        return [], check.get("holdouts"), check.get("parent_holdouts")
    read = _load(cell_dir / "amend_check.json", fail, ", and the amendment rests on a passing amendment check")
    if read is None or read[1] is None:
        return None
    ac = read[1]
    if ac.get("pass") is not True:
        fail("amend_check.json does not pass")
        return None
    if ac.get("summary_sha256") != summary_sha:
        fail("amend_check.json's summary_sha256 is not the SHA-256 of summary.json")
        return None
    if ac.get("amend_sha256") != hashlib.sha256(amend_raw).hexdigest():
        fail("amend_check.json's amend_sha256 is not the SHA-256 of amend.json")
        return None
    tsv = _read_amend_tsv(cell_dir, fail)
    if tsv is None:
        return None
    texts = [line.split("\t")[0] for line in tsv[1].decode("utf-8", "replace").split("\n")[:-1]]
    return texts, ac.get("holdouts"), ac.get("parent_holdouts")


def backfill_unknown_digest(cell_dir: Path) -> tuple[int, str]:
    """Add unknown_digest to a passing check.json that lacks it, from the lists the check compared (section 12,
    "Backfilling unknown_digest"). Returns the exit code, 0 added or kept and 1 refused, and the line to print."""
    cell_dir = Path(cell_dir)
    problems: list[str] = []
    cell = str(cell_dir)

    def refuse() -> tuple[int, str]:
        return 1, f"FAIL {cell}: {problems[0]}"

    read = _load(cell_dir / "summary.json", problems.append)
    if read is None or read[1] is None:
        return refuse()
    summary_raw, summary = read
    problem = _summary_problem(summary)
    if problem is not None:
        problems.append(problem)
        return refuse()
    big_d = summary["depth"]
    cell = f"{summary['cell'][0]}x{summary['cell'][1]} depth {big_d}"
    summary_sha = hashlib.sha256(summary_raw).hexdigest()
    read = _load(cell_dir / "check.json", problems.append)
    if read is None or read[1] is None:
        return refuse()
    check = read[1]
    if check.get("pass") is not True:
        problems.append("check.json does not pass, and the digest rests on a passing check")
        return refuse()
    if check.get("summary_sha256") != summary_sha:
        problems.append("check.json's summary_sha256 is not the SHA-256 of summary.json, so it checked another "
                        "summary.json")
        return refuse()
    expected = _backfill_expected(cell_dir, check, summary_sha, problems.append)
    files = _list_texts(cell_dir, summary, problems.append) if expected is not None else None
    if expected is None or files is None:
        return refuse()
    tsv_texts, want_here, want_below = expected
    files.append(("amend.tsv", tsv_texts))
    base: dict[str, int] = {}
    for name, texts in files:
        for t in texts:
            if t in base:
                problems.append(f"the text {t} is in two of the lists and amend.tsv")
                continue
            try:
                base[t] = parse_text(t).depth
            except ValueError:
                problems.append(f"the text {t!r} in {name} does not parse")
    if problems:
        return refuse()
    here = sum(d == big_d for d in base.values())
    below = sum(d < big_d for d in base.values())
    if type(want_here) is int and type(want_below) is int:  # the lists hold what the lines left, so add the lines
        want_here += sum(base[t] == big_d for t in tsv_texts)
        want_below += sum(base[t] < big_d for t in tsv_texts)
    if (here, below) != (want_here, want_below):
        problems.append(f"the lists and amend.tsv have {here} texts at depth {big_d} and {below} below it, and the "
                        f"checks recorded {_json(want_here)} and {_json(want_below)}")
        return refuse()
    if here + below != len(base):
        problems.append(f"the lists and amend.tsv have texts at depths above {big_d}")
        return refuse()
    ours = _hex(sum(_h(t.encode("utf-8")) for t in base) & MASK)
    if "unknown_digest" in check:
        if check["unknown_digest"] == ours:
            return 0, f"KEPT {cell}: unknown_digest {ours}"
        problems.append(f"check.json has unknown_digest {_json(check['unknown_digest'])}, the lists give {ours}")
        return refuse()
    updated: dict[str, Any] = {}
    for key, value in check.items():
        updated[key] = value
        if key == "claims_digest":
            updated["unknown_digest"] = ours
    if "unknown_digest" not in updated:
        updated["unknown_digest"] = ours
    with open(cell_dir / "check.json", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(updated, indent=2) + "\n")
    return 0, f"ADDED {cell}: unknown_digest {ours}"


def _amend_job(job: tuple[str, int, list[bytes], int]) -> ClaimTally:
    """Pool worker: parse, count, digest and verify a chunk of amend.tsv's lines, which start at line number job[1].
    job[3] is amend.json's claims_format as 2 to 5, which says whether NONHALT_RWL, NONHALT_FAR and NONHALT_CPSH lines
    may appear."""
    name, start, lines, fmt = job
    t = ClaimTally(fmt=fmt, amend=True)
    for offset, raw in enumerate(lines):
        _claim(t, raw, f"{name} line {start + offset}")
    t.claims_sum &= MASK
    t.claimed_sum &= MASK
    return t


def _amend_lines(name: str, data: bytes, base: dict[str, int], claims_fmt: int, pool: Any,
                 fail: Callable[[str], None]) -> tuple[ClaimTally, ClaimTally, set[str]]:
    """Step 4. Returns the lines' problems of form, U, repetition and order, the lines' tally with their
    certificates verified, and the texts the lines name."""
    lines = data.split(b"\n")
    last = lines.pop()
    if last:
        lines.append(last)
    order = ClaimTally()
    named: set[str] = set()
    prev: bytes | None = None
    for no, raw in enumerate(lines, 1):
        where = f"{name} line {no}"
        if last and no == len(lines):
            order.problem(f"{where} does not end with a newline")
        head = raw.split(b"\t", 2)
        text = head[0].decode("utf-8", "replace")
        if len(head) > 1 and head[1] == b"UNKNOWN":
            order.problem(f"{where}: {text} is UNKNOWN, and {name} has no UNKNOWN lines")
        if text not in base:
            order.problem(f"{where}: {text} is not in U, the UNKNOWN texts of the claims file")
        if text in named:
            order.problem(f"{where}: {text} is on an earlier line too")
        named.add(text)
        if prev is not None and raw <= prev:
            order.problem(f"{where} does not come after the line before it in byte order")
        prev = raw
    tasks = [(name, start, lines[start - 1:start - 1 + AMEND_CHUNK], claims_fmt)
             for start in range(1, len(lines) + 1, AMEND_CHUNK)]
    certs = ClaimTally()
    for part in (map(_amend_job, tasks) if pool is None else pool.imap(_amend_job, tasks)):
        certs.merge(part)
    if certs.invalid:
        fail(f"{certs.invalid} certificates in {name} are not valid")
    if certs.problems > certs.invalid:
        fail(f"{certs.problems - certs.invalid} lines of {name} do not parse")
    return order, certs, named


def _compare_amendment(amend: dict[str, Any], corridor_ok: bool, big_d: int, name: str, certs: ClaimTally,
                       left: list[int], fail: Callable[[str], None]) -> dict[str, Any]:
    """Step 5. left[d] is the number of machines of U at depth d that no line names. Returns the checker's own
    holdouts, parent_holdouts, amended and amend_digest."""
    if corridor_ok:
        for d, entry in enumerate(amend["corridor"]):
            for verdict in CERTIFICATES:
                ours = certs.counts.get((d, verdict), 0)
                # a "bbi9-cell/2" entry has no NONHALT_RWL, a "bbi9-cell/2" or "bbi9-cell/3" entry no NONHALT_FAR, and
                # a "bbi9-cell/2" to "bbi9-cell/4" entry no NONHALT_CPSH. Their counts are taken as 0.
                theirs = entry.get(verdict, 0)
                if not _same(theirs, ours):
                    fail(f"depth {d}: amend.json has {verdict} {_json(theirs)}, {name} has {ours}")
            if not _same(entry["UNKNOWN"], left[d]):
                fail(f"depth {d}: amend.json has UNKNOWN {_json(entry['UNKNOWN'])}, and {left[d]} machines of U at "
                     f"depth {d} are left")
    own = {"holdouts": left[big_d], "parent_holdouts": sum(left[:big_d]), "amended": certs.lines,
           "amend_digest": _hex(certs.claims_sum)}
    for key, ours in own.items():
        if key in amend and not _same(amend[key], ours):
            fail(f"{key}: amend.json has {_json(amend[key])}, the checker finds {_json(ours)}")
    return own


def _amend_rest(cell_dir: Path, summary: dict[str, Any], amend: dict[str, Any] | None, claims_fmt: int | None,
                corridor_ok: bool, pool: Any, jobs: int, result: dict[str, Any], fail: Callable[[str], None],
                details: list[ClaimTally]) -> None:
    """Steps 3 to 7. Steps 4 to 7 need U, amend.json and its claims_format, and are skipped without them."""
    base = _base_set(cell_dir, summary, pool, jobs, fail)
    if base is None or amend is None or claims_fmt is None:
        return
    read = _read_amend_tsv(cell_dir, fail)
    if read is None:
        return
    name, data = read
    order, certs, named = _amend_lines(name, data, base, claims_fmt, pool, fail)
    details.extend((order, certs))
    big_d = summary["depth"]
    left_texts = [(text, d) for text, d in base.items() if text not in named and d <= big_d]
    left = [0] * (big_d + 1)
    for _, d in left_texts:
        left[d] += 1
    result.update(_compare_amendment(amend, corridor_ok, big_d, name, certs, left, fail))
    # Step 6
    stem = f"BBi{big_d}_{summary['cell'][0]}x{summary['cell'][1]}"
    for list_name, texts, what in (
            (f"{stem}_holdouts_unofficial.txt", [t for t, d in left_texts if d == big_d], f"at depth {big_d}"),
            (f"{stem}_parent_holdouts_unofficial.txt", [t for t, d in left_texts if d < big_d],
             f"at depths below {big_d}")):
        message = _holdout_list(cell_dir, list_name, texts, f"{what} that {name} leaves")
        if message:
            fail(message)
    # Step 7
    census = result["census"]
    if result["parent_holdouts"] == 0 and census is not None:
        machines, late = summary.get("cell_machines"), summary.get("late_cell_machines")
        if not (_uint_value(machines) and _uint_value(late)):
            fail("summary.json has no valid cell_machines and late_cell_machines for the census rule")
        else:
            result["census_match"] = machines - late == census
            if not result["census_match"]:
                fail(f"census rule: cell_machines {machines} minus late_cell_machines {late} is not the census "
                     f"count {census}")


def _amend_check(cell_dir: Path, census: Path, jobs: int) -> tuple[dict[str, Any], int]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "format": AMEND_CHECK_FORMAT, "checker": CHECKER, "cell": None, "depth": None, "pass": False, "failures": [],
        "holdouts": None, "parent_holdouts": None, "amended": None, "amend_digest": None, "census": None,
        "census_match": None, "seconds": 0.0, "summary_sha256": None, "amend_sha256": None,
    }
    failures: list[str] = []
    fail = failures.append
    details: list[ClaimTally] = []  # line by line problems of amend.tsv, reported last
    summary = _amend_base(cell_dir, result, fail)
    if summary is not None:
        try:
            result["census"] = census_count(census, summary["cell"][0], summary["cell"][1], summary["depth"])
        except (OSError, ValueError, IndexError) as e:
            fail(f"the census {census} could not be read: {e}")
        amend, claims_fmt, corridor_ok = _read_amend(cell_dir, summary, result, fail)
        if jobs > 1:
            with multiprocessing.get_context("spawn").Pool(jobs) as pool:
                _amend_rest(cell_dir, summary, amend, claims_fmt, corridor_ok, pool, jobs, result, fail, details)
        else:
            _amend_rest(cell_dir, summary, amend, claims_fmt, corridor_ok, None, 1, result, fail, details)
    count = len(failures) + sum(t.problems for t in details)
    for t in details:
        failures.extend(t.messages)
    result["pass"] = count == 0
    result["failures"] = failures[:MAX_FAILURES]
    result["seconds"] = round(time.perf_counter() - started, 3)
    with open(cell_dir / "amend_check.json", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(result, indent=2) + "\n")
    return result, count


def amend_check(cell_dir: Path, census: Path, jobs: int = 1) -> dict[str, Any]:
    """Check one cell's amendment against the census (section 12), write amend_check.json into the cell directory and
    return its object. It never writes check.json."""
    return _amend_check(Path(cell_dir), Path(census), jobs)[0]


# ---------------------------------------------------------------------------------------------------------------------
# Pairs, lines and the normal-form map (section 13)

_SLOT = r"(?:---|[0-9][LR][A-J])"
# A non-blank line of a list file, with the whitespace around it removed. An optional index number and whitespace,
# then the machine, rows of 1 to 10 slots separated by _, at most 10 rows ("Pairs, lines and shapes"). [0-9] is ASCII
# alone.
_LIST_LINE = re.compile(rf"(?:[0-9]+[ \t\f\v]+)?({_SLOT}{{1,10}}(?:_{_SLOT}{{1,10}}){{0,9}})")
_SPACES = re.compile(r"[ \t\f\v]+")
_CELL = re.compile(r"(10|[1-9])x(10|[1-9])")  # the cell of a cell list, without a leading zero


def _code(q: int, r: int, w: int, right: bool, t: int) -> int:
    """The pair (q, r) with its instruction (w, m, t) as one number, right being True when m is R."""
    return (((q * 10 + r) * 10 + w) * 2 + right) * 10 + t


def _decode(c: int) -> tuple[int, int, int, bool, int]:
    """(q, r, w, right, t) of a pair made by _code."""
    c, t = divmod(c, 10)
    c, right = divmod(c, 2)
    c, w = divmod(c, 10)
    q, r = divmod(c, 10)
    return q, r, w, bool(right), t


def _machine_codes(machine: str) -> list[int]:
    """The pairs of a machine written as rows of three-character slots, as _LIST_LINE's machine is."""
    out = []
    for q, row in enumerate(machine.split("_")):
        for r in range(len(row) // 3):
            slot = row[3 * r:3 * r + 3]
            if slot != "---":
                out.append(_code(q, r, ord(slot[0]) - 48, slot[1] == "R", ord(slot[2]) - 65))
    return out


def _shape(codes: Iterable[int]) -> tuple[int, int]:
    """(s, k), the number of states that own a pair and 1 plus the largest symbol written (section 2)."""
    owners, k = set(), 1
    for c in codes:
        q, _, w, _, _ = _decode(c)
        owners.add(q)
        k = max(k, w + 1)
    return len(owners), k


def _codes_text(codes: Iterable[int]) -> str | None:
    """A set of pairs written as a section 2 text, in its own letters. None when the states that own its pairs are not
    A to the s-th letter, s their number, or when a pair's symbol is not below k, 1 plus the largest symbol written.
    No claims text is such a set."""
    cells: dict[tuple[int, int], str] = {}
    k = 1
    for c in codes:
        q, r, w, right, t = _decode(c)
        cells[(q, r)] = f"{w}{'R' if right else 'L'}{LETTERS[t]}"
        k = max(k, w + 1)
    s = len({q for q, _ in cells})
    if any(q >= s or r >= k for q, r in cells):
        return None
    return "_".join("".join(cells.get((q, r), "---") for r in range(k)) for q in range(s))


def _flat(codes: Iterable[int]) -> Table:
    """The table of a set of pairs at width 10, for _run and _discover."""
    table: Table = [None] * (MAX_STATES * MAX_SYMBOLS)
    for c in codes:
        q, r, w, right, t = _decode(c)
        table[q * 10 + r] = (w, 1 if right else -1, t * 10)
    return table


def _discover(table: Table, st: int, limit: Callable[[int], int]) -> tuple[list[int], list[int], str]:
    """Run a width 10 table from the blank tape in state st (as state * 10). Returns its defined pairs in the order the
    run first reads them, each as state * 10 + symbol, the round of each first read, and why the run stopped. While i
    pairs have been read, the run goes on through round limit(i) at most. It stops with "all" once every defined pair
    has been read, with "undefined" when it reads an undefined pair, and with "limit"."""
    total = sum(x is not None for x in table)
    known: Table = [None] * len(table)  # the pairs read so far, so that the fast loop stops at every new one
    order: list[int] = []
    rounds: list[int] = []
    tape = bytearray(129)
    pos = 64
    steps = 0
    while True:
        cap = limit(len(order))
        c = min(cap + 1 - steps, pos, len(tape) - 1 - pos)  # c steps cannot leave the tape or pass round cap
        for i in range(c):
            ins = known[st + tape[pos]]
            if ins is None:
                steps += i
                break
            tape[pos], move, st = ins
            pos += move
        else:
            steps += max(c, 0)
            if steps > cap:
                return order, rounds, "limit"
            size = len(tape)
            if size - 1 - pos < size // 4:
                tape.extend(bytes(size))
            if pos < size // 4:
                tape[0:0] = bytes(size)
                pos += size
            continue
        idx = st + tape[pos]
        ins = table[idx]
        if ins is None:
            return order, rounds, "undefined"
        order.append(idx)
        rounds.append(steps)
        known[idx] = ins
        tape[pos], move, st = ins
        pos += move
        steps += 1
        if len(order) == total:
            return order, rounds, "all"


def _prefix_codes(codes: Iterable[int], bounds: Sequence[int]) -> list[list[int]]:
    """The run prefixes of a line, the sets of the first j distinct pairs its run reads, for each j such that the run
    reads its j-th distinct pair within round B_(j-1) and that pair is defined.

    Every claims text below the line is one of them, so the checker looks for a line's candidates among these alone.
    A claims text M is a corridor machine. Its ancestors M_0 to M_j = M each halted within its depth's bound, after
    n_i <= B_i steps, on the pair that the next one adds (sections 3 and 4). When M is a subset of the line, each M_i
    agrees with the line, so it runs as the line runs until it halts. By induction M_i is the set of the first i
    distinct pairs that the line's run reads, and the line reads the next one in round n_i <= B_i.
    """
    by_index = {}
    for c in codes:
        q, r, _, _, _ = _decode(c)
        by_index[q * 10 + r] = c
    order, _, _ = _discover(_flat(by_index.values()), 0, lambda i: bounds[i] if i < len(bounds) else -1)
    pairs = [by_index[i] for i in order]
    return [pairs[:j] for j in range(1, len(pairs) + 1)]


def prefix_texts(machine: str, bounds: Sequence[int]) -> list[str]:
    """The texts of the run prefixes (_prefix_codes) of a line that can be written as section 2 texts, shortest
    first. bounds is B_0 to B_D."""
    texts = (_codes_text(p) for p in _prefix_codes(_machine_codes(machine), bounds))
    return [t for t in texts if t is not None]


@dataclass(frozen=True)
class NormalForm:
    """m(t) of section 13, in the community's letters."""
    text: str
    codes: frozenset[int]
    prefixes: tuple[frozenset[int], ...]  # its first j pairs in step 2's order, for j from 1 to its depth less 1
    kept: int  # |M'|, the pairs of M' used or not, so the depth of text is at most kept
    prefix: int  # p, the steps of step 1


def _normal_form(codes: Iterable[int], bound: int) -> NormalForm | str:
    """The normal-form map of a machine with the bound B_d ("The normal-form map"), or why it has none."""
    table: dict[int, tuple[int, bool, int]] = {}  # state * 10 + symbol -> (w, right, t)
    for c in codes:
        q, r, w, right, t = _decode(c)
        table[q * 10 + r] = (w, right, t)
    owners = {i // 10 for i in table}
    for _, _, t in table.values():
        if t not in owners:
            return f"an instruction goes into {LETTERS[t]}, which owns nothing"
    # Step 1. The tape stays all 0s, so the current pair is always (q, 0).
    q, entered, prefix = 0, {0}, []
    while True:
        ins = table.get(q * 10)
        if ins is None:
            return f"the prefix reads the undefined pair ({LETTERS[q]}, 0)"
        if ins[0] != 0:
            break
        prefix.append(q)
        q = ins[2]
        if q in entered:
            return f"the prefix enters {LETTERS[q]} twice"
        entered.add(q)
    s = q
    # Step 1b
    dropping = True
    while dropping:
        dropping = False
        for p in prefix:
            if p * 10 in table and all(t != p for _, _, t in table.values()):
                del table[p * 10]
                dropping = True
    kept = len(table)
    # Step 2. A pair first read in round n runs in step n + 1, so the last new pair must be read by round B_d - 1. At
    # the bound the map is built from the pairs that ran, the order as it stands.
    flat: Table = [None] * (MAX_STATES * MAX_SYMBOLS)
    for i, (w, right, t) in table.items():
        flat[i] = (w, 1 if right else -1, t * 10)
    order, _, why = _discover(flat, s * 10, lambda _: bound - 1)
    if why == "undefined":
        return f"the run from {LETTERS[s]} reads an undefined pair within the bound"
    if not order:
        return f"no pair ran from {LETTERS[s]} within the bound"
    # Step 3. A state entered before the last step was read in the next round, so its first pair is its first entry.
    # The last step may enter a state whose pairs never ran, the last state entered, and a pair that ran targets it.
    letter: dict[int, int] = {}
    for i in order:
        letter.setdefault(i // 10, len(letter))
    for i in order:
        letter.setdefault(table[i][2], len(letter))
    mirror = not table[order[0]][1]  # order[0] is (s, 0), and its move is the first move from s
    pairs = []
    for i in order:
        w, right, t = table[i]
        pairs.append(_code(letter[i // 10], i % 10, w, right != mirror, letter[t]))
    # Step 4
    text = _codes_text(pairs)
    if text is None:  # cannot happen, since each pair read a symbol written before it or 0
        return "the relabelled table is not a text"
    if not text.startswith("1RB"):
        return f"the map would start {text[:3]}"
    return NormalForm(text, frozenset(pairs), tuple(frozenset(pairs[:j]) for j in range(1, len(pairs))), kept,
                      len(prefix))


def normal_form_map(text: str, bound: int) -> str | None:
    """m(t) for a machine text with the bound B_d, or None when the machine has no map (section 13)."""
    nf = _normal_form(_machine_codes(text), bound)
    return None if isinstance(nf, str) else nf.text


# ---------------------------------------------------------------------------------------------------------------------
# The registry and the list files (section 13 step 3)


@dataclass
class ListData:
    """A registry entry with decides: true that covers the cell, and what its list file holds."""
    id: str
    form: str  # "states", "bbi" or "cell"
    states: int = MAX_STATES  # S of a {states: S, symbols: K} list
    symbols: int = MAX_SYMBOLS  # K of it
    bbi: int = 0  # N of a {bbi: N} list or a cell list
    proven: int | None = None  # a domain list's proven value P, None when it has none or step 3 refused it
    entry: dict[str, Any] = field(default_factory=dict)
    entry_sha256: str | None = None  # None when the entry has no JSON
    readable_name: bool = False  # whether file is a name the checker reads
    read: bool = False  # whether every line of the list file was read
    sha256: str | None = None  # the SHA-256 hex of the list file as stored, once read
    lines: int = 0  # its non-blank lines
    kept: dict[frozenset[int], str] = field(default_factory=dict)  # a domain list's kept lines, each as first written
    texts: set[str] = field(default_factory=set)  # a cell list's lines
    candidates: dict[frozenset[int], list[tuple[int, str]]] = field(default_factory=dict)  # see _candidates
    by_pair: dict[int, list[frozenset[int]]] | None = None  # the kept lines by each of their pairs
    speaks: bool | None = None  # None until step 4 can tell
    strangers: int | None = None
    kinds: list[int] | None = None
    maker: list[frozenset[int]] = field(default_factory=list)  # its kind 1 lines


def _domain(domain: Any) -> tuple[str, int, int, int] | None:
    """(form, S, K, N) of a domain of one of the three forms, with 0 for what its form lacks, or None. A YAML true or
    false is not a whole number."""
    def whole(x: Any, top: int) -> bool:
        return type(x) is int and 1 <= x <= top

    if not isinstance(domain, dict):
        return None
    keys = set(domain)
    if keys == {"states", "symbols"} and whole(domain["states"], MAX_STATES) and whole(domain["symbols"], MAX_SYMBOLS):
        return "states", domain["states"], domain["symbols"], 0
    if keys == {"bbi"} and whole(domain["bbi"], 9):
        return "bbi", 0, 0, domain["bbi"]
    if keys == {"bbi", "cell"} and whole(domain["bbi"], 9) and isinstance(domain["cell"], str):
        m = _CELL.fullmatch(domain["cell"])
        if m:
            return "cell", int(m.group(1)), int(m.group(2)), domain["bbi"]
    return None


def _covers(dom: tuple[str, int, int, int], big_s: int, big_k: int, big_d: int) -> bool:
    form, s, k, n = dom
    if form == "states":
        return big_s <= s and big_k <= k
    if form == "bbi":
        return big_d >= n  # every cell at depth N and above
    return big_d == n and (big_s, big_k) == (s, k)


def _proven_problems(entry: dict[str, Any]) -> list[str]:
    """Why step 3 refuses the entry's proven, each as a clause, or [] when it has none or step 3 accepts it. A proven
    value is a whole number from 0 up, and a YAML true or false or a null is not one. It leaves an empty domain
    list."""
    if "proven" not in entry:
        return []
    proven = _shown(entry["proven"])
    out = []
    if not (type(entry["proven"]) is int and entry["proven"] >= 0):
        out.append(f"has proven {proven}, which is not a whole number from 0 up")
    if not (type(entry.get("entries")) is int and entry["entries"] == 0):
        out.append(f"has proven {proven} and entries {_shown(entry.get('entries'))}, not 0")
    if (_domain(entry.get("domain")) or ("",))[0] == "cell":
        out.append("is a cell list and has proven, which is for a domain list")
    return out


def _new_list(list_id: str, dom: tuple[str, int, int, int], entry: dict[str, Any]) -> ListData:
    form, s, k, n = dom
    proven = entry["proven"] if "proven" in entry and not _proven_problems(entry) else None  # as step 3 accepts it
    if form == "states":
        return ListData(list_id, form, states=s, symbols=k, proven=proven, entry=entry)
    return ListData(list_id, form, bbi=n, proven=proven, entry=entry)


def _shown(x: Any) -> str:
    try:
        return _json(x)
    except (TypeError, ValueError):
        return repr(x)


def _relative_name(name: Any) -> bool:
    """Whether name is a file name relative to --data that a file system may hold. A NUL never is."""
    return (isinstance(name, str) and name != "" and "\0" not in name and not PurePosixPath(name).is_absolute()
            and not PureWindowsPath(name).anchor)


def _registry(path: Path, big_s: int, big_k: int, big_d: int, fail: Callable[[str], None]) -> list[ListData] | None:
    """Step 3's reading of the registry. Returns the entries with decides: true that cover the cell, in registry
    order, or None when the registry is not a sequence of mappings that yaml.safe_load can read."""
    try:
        import yaml  # PyYAML, the one library beyond the standard library, for the import check alone
    except ImportError:
        fail("PyYAML is not installed, so the registry cannot be read")
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        fail(f"the registry {path} is missing or could not be read")
        return None
    try:
        entries = yaml.safe_load(raw)
    except Exception as e:  # PyYAML raises YAMLError and others for a file it cannot read
        fail(f"yaml.safe_load cannot read the registry {path} ({(str(e).splitlines() or [type(e).__name__])[0]})")
        return None
    if entries is None and not raw.strip():  # an empty file is a registry with no entries
        entries = []
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        fail(f"the registry is not a sequence of mappings ({path})")
        return None
    out: list[ListData] = []
    first_with: dict[str, int] = {}
    for no, e in enumerate(entries, 1):
        name = f"registry entry {no}" + (f" ({e['id']})" if isinstance(e.get("id"), str) else "")
        if isinstance(e.get("id"), str):
            if e["id"] in first_with:
                fail(f"{name} shares its id with registry entry {first_with[e['id']]}")
            else:
                first_with[e["id"]] = no
        if "decides" in e and type(e["decides"]) is not bool:
            fail(f"{name} has decides {_shown(e['decides'])}, which is neither true nor false")
        for why in _proven_problems(e):  # whether or not the entry decides
            fail(f"{name} {why}")
        if e.get("decides") is not True:
            continue
        for key in REQUIRED:
            if key not in e:
                fail(f"{name} has decides: true and no {key}")
        if "complete" in e and not (isinstance(e["complete"], str) and e["complete"].strip()):
            fail(f"{name} has a complete that is empty or not a string")
        dom = _domain(e["domain"]) if "domain" in e else None
        if "domain" in e and dom is None:
            fail(f"{name} has a domain of none of the three forms")
        if dom is not None and dom[0] == "cell":
            if "made_from" not in e:
                fail(f"{name} is a cell list with decides: true and no made_from")
            elif not isinstance(e["made_from"], str):
                fail(f"{name} has a made_from that is not a string")
        # CHECKING.md gives no type for these keys, so a value that cannot be what the key names fails
        if "id" in e and not (isinstance(e["id"], str) and e["id"]):
            fail(f"{name} has an id that is not a string of one or more characters")
        if "file" in e and not _relative_name(e["file"]):
            fail(f"{name} has a file that is not a name relative to --data")
        if "sha256" in e and not isinstance(e["sha256"], str):
            fail(f"{name} has a sha256 that is not a string")
        if "entries" in e and not _uint_value(e["entries"]):
            fail(f"{name} has entries that are not a whole number")
        if dom is None or not _covers(dom, big_s, big_k, big_d) or not (isinstance(e.get("id"), str) and e["id"]):
            continue
        lst = _new_list(e["id"], dom, e)
        try:
            lst.entry_sha256 = hashlib.sha256(json.dumps(e, sort_keys=True, separators=(",", ":"),
                                                         ensure_ascii=False).encode("utf-8")).hexdigest()
        except (TypeError, ValueError, RecursionError) as err:
            fail(f"{name} has decides: true, covers the cell and has no JSON for its entry_sha256 ({err})")
        lst.readable_name = _relative_name(e.get("file"))
        out.append(lst)
    return out


@functools.cache
def _beyond(letters: int, symbols: int) -> re.Pattern[str] | None:
    """A pattern for a target letter at index letters or past it, or a written digit at symbols or past it. In a
    machine the letters A to J are its targets and the digits its written symbols."""
    chars = LETTERS[letters:] + DIGITS[symbols:]
    return re.compile(f"[{chars}]") if chars else None


@functools.cache
def _inside(states: int, symbols: int) -> re.Pattern[str]:
    """A machine of a {states: S, symbols: K} list that defines no pair outside the domain. Every slot after the K-th
    of a row and every row after the S-th hold nothing but ---, which owns nothing (section 13 step 3)."""
    row = rf"{_SLOT}{{1,{symbols}}}(?:---)*"
    return re.compile(rf"{row}(?:_{row}){{0,{states - 1}}}(?:_(?:---)+)*")


def _form_problem(line: str) -> str:
    """Why a non-blank line, stripped, is neither a machine nor an index number and a machine."""
    tokens = _SPACES.split(line)
    if len(tokens) > 2 or (len(tokens) == 2 and not (tokens[0].isascii() and tokens[0].isdigit())):
        return "is not a machine or an index and a machine"
    if "Z" in tokens[-1]:
        return f"{tokens[-1]} has a Z"
    return f"{tokens[-1]} does not parse"


def _line_problems(machine: str, rows: int, defined: int, lst: ListData) -> list[str]:
    """Step 3's checks of a domain list's line that parses, each failure as a clause."""
    out = []
    if not machine.startswith("1RB"):
        out.append("does not start with 1RB at (A, 0)")
    top = max((LETTERS.index(ch) for ch in machine if ch in LETTERS), default=-1)
    if top > rows:
        out.append(f"targets {LETTERS[top]}, past its {_count(rows, 'row')} plus one")
    if lst.form == "states":
        if top >= lst.states:
            out.append(f"targets {LETTERS[top]}, a state at or past S = {lst.states}")
        w = max((int(ch) for ch in machine if ch in DIGITS), default=0)
        if w >= lst.symbols:
            out.append(f"writes the symbol {w}, at or past K = {lst.symbols}")
        pairs = [(q, r) for q, row in enumerate(machine.split("_")) for r in range(len(row) // 3)
                 if row[3 * r:3 * r + 3] != "---"]
        r = max((r for _, r in pairs if r >= lst.symbols), default=-1)
        if r >= 0:
            out.append(f"defines a pair reading the symbol {r}, at or past K = {lst.symbols}")
        q = max((q for q, _ in pairs if q >= lst.states), default=-1)
        if q >= 0:
            out.append(f"defines a pair of the state {LETTERS[q]}, at or past S = {lst.states}")
    if lst.form == "bbi" and defined > lst.bbi:
        out.append(f"has {defined} instructions, more than N = {lst.bbi}")
    return out


def _take_lines(lst: ListData, lines: Iterable[str], start: int, big_d: int, problem: Callable[[str], None],
                where: str) -> None:
    """Read lines, numbered from start, into lst by the reading rules of section 13, with step 3's checks of each line
    of a domain list. A domain list keeps the pairs of its lines of at most big_d instructions, and a cell list its
    lines as texts. A line that fails is not kept."""
    match = _LIST_LINE.fullmatch
    domain = lst.form != "cell"
    letters = lst.states if lst.form == "states" else MAX_STATES + 1
    symbols = lst.symbols if lst.form == "states" else MAX_SYMBOLS
    most = lst.bbi if lst.form == "bbi" else MAX_STATES * MAX_SYMBOLS
    inside = _inside(lst.states, lst.symbols).fullmatch if lst.form == "states" else None
    width = 3 * lst.symbols + 1  # a row of exactly K slots and its _
    kept = lst.kept
    count = 0
    for no, raw in enumerate(lines, start):
        line = raw.strip(LINE_SPACE)
        if not line:
            continue
        count += 1
        m = match(line)
        if m is None:
            problem(f"{where} line {no} {_form_problem(line)}")
            continue
        machine = m.group(1)
        if not domain:
            lst.texts.add(machine)
            continue
        rows = machine.count("_") + 1
        beyond = _beyond(rows + 1 if rows + 1 < letters else letters, symbols)
        defined = (len(machine) - rows + 1) // 3 - machine.count("---")
        # At most S rows of exactly K slots each define nothing outside the domain, and _inside judges the rest
        if machine.startswith("1RB") and (beyond is None or beyond.search(machine) is None) and defined <= most \
                and (inside is None or (rows <= lst.states and len(machine) == rows * width - 1
                                        and machine[width - 1::width].count("_") == rows - 1) or inside(machine)):
            if defined <= big_d:
                codes = frozenset(_machine_codes(machine))
                if codes not in kept:
                    kept[codes] = machine
            continue
        for why in _line_problems(machine, rows, defined, lst):
            problem(f"{where} line {no} {machine} {why}")
    lst.lines += count


def _hashed(chunks: Iterable[bytes], sha: Any) -> Iterator[bytes]:
    for chunk in chunks:
        sha.update(chunk)
        yield chunk


def _members(chunks: Iterable[bytes]) -> Iterator[bytes]:
    """The decompressed contents of the gzip members in the bytes of chunks, one member after another."""
    z = zlib.decompressobj(wbits=31)
    fed = False  # whether z holds part of a member it has not finished
    for data in chunks:
        while data:
            fed = True
            out = z.decompress(data)
            if out:
                yield out
            if not z.eof:
                break
            data = z.unused_data
            z = zlib.decompressobj(wbits=31)
            fed = False
    if fed:
        raise EOFError("the file ends inside a gzip member")


def _universal(text: str) -> list[str]:
    """text split at each CRLF, LF and bare CR, as Python's universal newlines split it."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _read_list_file(lst: ListData, data: Path, big_d: int, problem: Callable[[str], None]) -> None:
    """Read lst's list file below data, gunzipped when its name ends in .gz, and check its SHA-256, its lines and its
    number of non-blank lines (step 3). It is UTF-8, a byte-order mark at its start is ignored, and CRLF, LF and a
    bare CR each end a line."""
    name = lst.entry["file"]
    where = f"list {lst.id} file {name}"
    sha = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    carry = ""  # the end of the text read so far, after its last whole line
    no = 1
    try:
        with open(data / name, "rb") as f:
            chunks = _hashed(iter(lambda: f.read(LIST_READ), b""), sha)
            for chunk in (_members(chunks) if name.endswith(".gz") else chunks):
                text = carry + decoder.decode(chunk)
                hold = ""
                if text.endswith("\r"):  # a CR at the end may be the first half of a CRLF
                    text, hold = text[:-1], "\r"
                lines = _universal(text)
                carry = lines.pop() + hold
                _take_lines(lst, lines, no, big_d, problem, where)
                no += len(lines)
            _take_lines(lst, _universal(carry + decoder.decode(b"", final=True)), no, big_d, problem, where)
    except UnicodeDecodeError:
        problem(f"{where} is not UTF-8")
        return
    except (EOFError, zlib.error) as e:
        problem(f"{where} could not be decompressed as gzip ({e})")
        return
    except (OSError, ValueError):  # ValueError for a name open() refuses
        problem(f"{where} is missing or could not be read")
        return
    lst.read = True
    lst.sha256 = sha.hexdigest()
    registered = lst.entry.get("sha256")
    if not (isinstance(registered, str) and registered.lower() == lst.sha256):
        problem(f"{where} has the SHA-256 {lst.sha256}, and the registry's sha256 is {_shown(registered)}")
    if _uint_value(lst.entry.get("entries")) and lst.entry["entries"] != lst.lines:
        problem(f"{where} has {_count(lst.lines, 'non-blank line')}, and the registry's entries is "
                f"{lst.entry['entries']}")


def list_data(list_id: str, domain: Any, lines: Iterable[str], big_d: int) -> tuple[ListData, list[str]]:
    """A list of the given domain read from lines as from its list file, for the cell depth big_d, and the problems
    that step 3 finds in its lines."""
    dom = _domain(domain)
    if dom is None:
        raise ValueError(f"{domain!r} is a domain of none of the three forms")
    lst = _new_list(list_id, dom, {})
    problems: list[str] = []
    _take_lines(lst, lines, 1, big_d, problems.append, f"list {list_id}")
    lst.read = True
    return lst, problems


# ---------------------------------------------------------------------------------------------------------------------
# Kinds and decisions (section 13, "Speaking our language" and "Which machines a list decides")


def _candidates(lst: ListData, cor: Corridor) -> None:
    """For each kept line in the corridor, its run prefixes that can be written as section 2 texts, each as (j, text)
    with j its number of pairs. The claims texts among them are the line's candidates (_prefix_codes)."""
    for codes in lst.kept:
        s, k = _shape(codes)
        if not _in_corridor(cor, len(codes), s, k):
            continue
        out = []
        for prefix in _prefix_codes(codes, cor.bounds):
            text = _codes_text(prefix)
            if text is not None:
                out.append((len(prefix), text))
        lst.candidates[codes] = out


def _classify(lst: ListData, cor: Corridor, v: dict[str, int], found: set[str]) -> None:
    """Step 4 for a domain list. Each kept line in the corridor gets the first of the four kinds that holds. v is V,
    each text with its depth, and found the candidate texts that are claims texts."""
    kinds = [0, 0, 0, 0]
    maker = []
    for codes, cands in lst.candidates.items():
        d = len(codes)
        if any(j < d and text in v for j, text in cands):
            kind = 1  # a claims text in V is a proper subset
        elif any((j == d and text in v) or (text in found and text not in v) for j, text in cands):
            kind = 2  # the line's own text is in V, or a certified claims text is a subset or equal
        elif _run(_flat(codes), cor.bounds[d])[0]:
            kind = 3  # halts within B_d from the start
        else:
            kind = 4
        kinds[kind - 1] += 1
        if kind == 1:
            maker.append(codes)
    lst.kinds, lst.strangers, lst.speaks, lst.maker = kinds, kinds[3], kinds[3] == 0, maker


def _supersets(lst: ListData, codes: frozenset[int]) -> list[frozenset[int]]:
    """The kept lines whose pairs are a proper superset of codes, in the order they were first written."""
    if lst.by_pair is None:
        lst.by_pair = {}
        for line in lst.kept:
            for c in line:
                lst.by_pair.setdefault(c, []).append(line)
    if not codes:
        return [line for line in lst.kept if line]
    smallest = min((lst.by_pair.get(c, []) for c in codes), key=len)
    return [line for line in smallest if codes < line]


def decide_problems(lst: ListData, text: str, bound: int, big_d: int, holdout_texts: set[str] | frozenset[str],
                    maps: dict[str, NormalForm | str] | None = None, verdict: str = DECIDED) -> list[str]:
    """Why the list may not give the machine of V with this text the verdict, DECIDED or NEVER, each reason a clause,
    or [] when it gives it. bound is B_d for the text's depth d, holdout_texts the texts of the cell's depth-D holdout
    list, and maps a cache of maps by text. It does not ask whether the list speaks ("Which machines a list
    decides")."""
    if verdict == NEVER:
        if lst.form == "cell":
            return [f"{lst.id} is a cell list, and a proven value is for a domain list"]
        if lst.proven is None:
            return [f"{lst.id} has no proven value"]
    elif lst.form == "cell":
        if len(_machine_codes(text)) < big_d:
            return [f"{lst.id} is a cell list and the text is a parent holdout"]
        out = []
        if text not in holdout_texts:
            out.append(f"the text is not in the cell's depth-{big_d} holdout list")
        if text in lst.texts:
            out.append(f"the text is a line of {lst.id}")
        return out
    nf = maps.get(text) if maps is not None else None
    if nf is None:
        nf = _normal_form(_machine_codes(text), bound)
        if maps is not None:
            maps[text] = nf
    if isinstance(nf, str):
        return [f"the text has no map with the bound {bound} ({nf})"]
    out = []
    if verdict == NEVER:
        assert lst.proven is not None
        if lst.form == "bbi" and len(nf.codes) > lst.bbi:  # m(t) is not in the domain
            out.append(f"its map {nf.text} has {_count(len(nf.codes), 'instruction')}, more than N = {lst.bbi}")
        if bound - nf.prefix <= lst.proven:
            out.append(f"B_d less the prefix, {bound} - {nf.prefix} = {bound - nf.prefix}, is not above the proven "
                       f"value {lst.proven} of {lst.id}")
        return out
    if lst.form == "bbi" and nf.kept > lst.bbi:  # some machine of the chain, at most M', may lie outside the domain
        out.append(f"its pairs after step 1b, {nf.kept}, exceed N = {lst.bbi}")
    if nf.codes in lst.kept:
        out.append(f"a kept line of {lst.id} equals its map {nf.text}")
    for prefix in nf.prefixes:
        if prefix in lst.kept:
            out.append(f"a kept line of {lst.id} equals the prefix {_codes_text(prefix)} of its map {nf.text}")
    for line in _supersets(lst, nf.codes):
        out.append(f"the kept line {lst.kept[line]} of {lst.id} is a proper superset of its map {nf.text}")
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The import check (section 13, "The import check")


class _Failures:
    """The import check's failures, kept by step so that they are reported in step order, at most MAX_FAILURES a
    step, and all of them counted."""

    def __init__(self) -> None:
        self.by_step: list[list[str]] = [[] for _ in range(8)]
        self.count = 0

    def at(self, step: int) -> Callable[[str], None]:
        def fail(message: str) -> None:
            self.count += 1
            if len(self.by_step[step]) < MAX_FAILURES:
                self.by_step[step].append(message)
        return fail

    def first(self) -> list[str]:
        return [m for messages in self.by_step for m in messages][:MAX_FAILURES]


def _text_list(cell_dir: Path, name: str, texts: Iterable[str], what: str) -> str | None:
    """Why the file is not exactly the texts sorted in byte order, each followed by a newline, or None."""
    texts = sorted(texts, key=lambda t: t.encode("utf-8"))
    expected = "".join(t + "\n" for t in texts).encode("utf-8")
    try:
        actual = (cell_dir / name).read_bytes()
    except OSError:
        return f"{name} is missing"
    if actual != expected:
        lines = actual.count(b"\n")
        return f"{name} does not hold exactly the {_count(len(texts), 'sorted text')} of V {what} (it has " \
               f"{_count(lines, 'line')})"
    return None


def _counts(sets: Iterable[frozenset[int]], big_d: int) -> dict[str, int]:
    depths = [len(x) for x in sets]
    return {"holdouts": sum(d == big_d for d in depths), "parent_holdouts": sum(d < big_d for d in depths)}


class _Import:
    """The steps of the import check for a cell whose summary.json was read."""

    def __init__(self, cell_dir: Path, summary: dict[str, Any], registry: Path, data: Path | None, jobs: int,
                 result: dict[str, Any], failures: _Failures) -> None:
        self.dir, self.summary, self.registry, self.data, self.jobs = cell_dir, summary, registry, data, jobs
        self.result = result
        self.fail = [failures.at(step) for step in range(8)]  # self.fail[n] adds a failure of step n
        self.big_s, self.big_k = summary["cell"]
        self.big_d = summary["depth"]
        self.stem = f"BBi{self.big_d}_{self.big_s}x{self.big_k}"
        self.cor: Corridor | None = None
        self.has_amend = (cell_dir / "amend.json").exists()
        self.amend: dict[str, Any] | None = None
        self.imp: dict[str, Any] | None = None
        self.lists: list[ListData] | None = None
        self.v: dict[str, int] | None = None  # V, each text with its depth
        self.found: set[str] = set()  # the candidate texts that are claims texts
        self.holdout_texts: set[str] = set()  # the texts of the cell's depth-D holdout list
        self.holdout_sha256: str | None = None
        self.tsv: list[bytes] | None = None  # the lines of import.tsv, each without its newline
        self.maps: dict[str, NormalForm | str] = {}

    def run(self) -> None:
        self.bounds()
        self.amendment()
        self.import_json()
        self.read_lists()
        self.claims()
        self.classify()
        self.compare_lists()
        self.import_tsv()
        self.counts()
        self.after_lists()
        if self.lists is not None:
            self.result["lists"] = [{"id": x.id, "sha256": x.sha256, "speaks": x.speaks} for x in self.lists]

    def bounds(self) -> None:
        """B_0 to B_D, the bounds of the map and of the kind 3 test."""
        bounds = []
        for d, entry in enumerate(self.summary["corridor"]):
            b = entry.get("max_halt_steps")
            if not (_uint_value(b) and b <= MAX_CAP):
                self.fail[1](f"summary.json corridor entry {d} has no max_halt_steps from 0 to {MAX_CAP}")
                return
            bounds.append(b)
        self.cor = Corridor(self.big_s, self.big_k, self.big_d, tuple(bounds))

    def amendment(self) -> None:
        """Step 1 for an amended cell. Its amendment check must pass for the same files."""
        if not self.has_amend:
            return
        fail = self.fail[1]
        why = ", and an import into an amended cell rests on a passing amendment check"
        read = _load(self.dir / "amend_check.json", fail, why)
        if read is not None and read[1] is not None:
            check = read[1]
            if check.get("pass") is not True:
                fail(f"amend_check.json does not pass{why}")
            if check.get("summary_sha256") != self.result["summary_sha256"]:
                fail("amend_check.json's summary_sha256 is not the SHA-256 of summary.json")
            if self.result["amend_sha256"] is None or check.get("amend_sha256") != self.result["amend_sha256"]:
                fail("amend_check.json's amend_sha256 is not the SHA-256 of amend.json")
        read = _load(self.dir / "amend.json", fail)
        if read is not None and read[1] is not None:
            self.amend = read[1]
            for key in ("amended", "amend_digest"):
                if key not in self.amend:
                    fail(f"amend.json has no {key}")

    def import_json(self) -> None:
        """Step 2."""
        fail = self.fail[2]
        read = _load(self.dir / "import.json", fail)
        if read is None or read[1] is None:
            return
        imp = self.imp = read[1]
        for key in IMPORT_KEYS:
            if key not in imp:
                fail(f"import.json has no {key}")
        if "format" in imp and imp["format"] != IMPORT_FORMAT:
            fail(f"import.json has format {_shown(imp['format'])}, not {IMPORT_FORMAT!r}")
        for key in ("cell", "depth"):
            if key in imp and not _same(imp[key], self.summary[key]):
                fail(f"import.json has {key} {_shown(imp[key])}, and summary.json has {_json(self.summary[key])}")
        if "base_summary_sha256" in imp and imp["base_summary_sha256"] != self.result["summary_sha256"]:
            fail("import.json's base_summary_sha256 is not the SHA-256 of summary.json, so it imports into another "
                 "summary.json")
        if "base_amend_sha256" in imp:
            base = imp["base_amend_sha256"]
            if not self.has_amend:
                if base is not None:
                    fail("import.json's base_amend_sha256 is not null, and the cell has no amend.json")
            elif base is None or base != self.result["amend_sha256"]:
                fail("import.json's base_amend_sha256 is not the SHA-256 of amend.json")

    def read_lists(self) -> None:
        """Step 3's reading of the registry and of every list file, and each kept line's candidates."""
        self.lists = _registry(self.registry, self.big_s, self.big_k, self.big_d, self.fail[3])
        if self.lists and self.data is None:
            self.fail[3](f"the registry {self.registry} has no directory two levels above its own, so the list files "
                         "need --data")
        for lst in self.lists or []:
            if lst.readable_name and self.data is not None:
                _read_list_file(lst, self.data, self.big_d, self.fail[3])
            if lst.read and lst.form != "cell" and self.cor is not None:
                _candidates(lst, self.cor)

    def claims(self) -> None:
        """Step 1. One scan of the claims file binds it to summary.json, gives V and finds which candidate texts are
        claims texts. Then the amendment's lines leave V, and the holdout lists must be V. A cell without a claims file
        whose lists have no kept line in the corridor, so that step 4 looks nothing up among the claims, takes U from
        its holdout lists and amend.tsv instead, bound by check.json's unknown_digest (_base_from_lists)."""
        fail = self.fail[1]
        find = frozenset(text.encode("utf-8") for lst in self.lists or [] for cands in lst.candidates.values()
                         for _, text in cands)
        lines_in_corridor = any(lst.candidates for lst in self.lists or [])
        if not lines_in_corridor and not any((self.dir / n).is_file() for n in ("claims.tsv", "claims.tsv.gz")):
            base = _base_from_lists(self.dir, self.summary, fail, self.has_amend)
        elif self.jobs > 1:
            with multiprocessing.get_context("spawn").Pool(self.jobs, initializer=_set_find,
                                                           initargs=(find,)) as pool:
                base = _base_set(self.dir, self.summary, pool, self.jobs, fail, self.found)
        else:
            _set_find(find)
            try:
                base = _base_set(self.dir, self.summary, None, 1, fail, self.found)
            finally:
                _set_find(frozenset())
        try:
            raw = (self.dir / f"{self.stem}_holdouts_unofficial.txt").read_bytes()
            self.holdout_sha256 = hashlib.sha256(raw).hexdigest()
            self.holdout_texts = set(raw.decode("utf-8", "replace").split("\n")[:-1])
        except OSError:
            pass
        if base is None:
            return
        v = {text: d for text, d in base.items() if d <= self.big_d}
        if self.has_amend:
            if self.amend is None:
                return
            read = _read_amend_tsv(self.dir, fail)
            if read is None:
                return
            name, data = read
            lines = data.split(b"\n")
            last = lines.pop()
            if last:
                lines.append(last)
            if "amended" in self.amend and not _same(self.amend["amended"], len(lines)):
                fail(f"amend.json has amended {_shown(self.amend['amended'])}, and {name} has "
                     f"{_count(len(lines), 'line')}")
            amend_digest = _hex(_sum_h(lines))
            if "amend_digest" in self.amend and not _same(self.amend["amend_digest"], amend_digest):
                fail(f"amend.json has amend_digest {_shown(self.amend['amend_digest'])}, and the digest of {name} is "
                     f"{_json(amend_digest)}")
            for raw in lines:
                v.pop(raw.split(b"\t", 1)[0].decode("utf-8", "replace"), None)
        self.v = v
        for name, texts, what in (
                (f"{self.stem}_holdouts_unofficial.txt", [t for t, d in v.items() if d == self.big_d],
                 f"at depth {self.big_d}"),
                (f"{self.stem}_parent_holdouts_unofficial.txt", [t for t, d in v.items() if d < self.big_d],
                 f"at depths below {self.big_d}")):
            message = _text_list(self.dir, name, texts, what)
            if message:
                fail(message)

    def classify(self) -> None:
        """Step 4's kinds and speaks for each list."""
        for lst in self.lists or []:
            if lst.form == "cell":
                lst.strangers = 0
                if lst.read and self.holdout_sha256 is not None:
                    made = lst.entry.get("made_from")
                    lst.speaks = (isinstance(made, str) and made.lower() == self.holdout_sha256
                                  and lst.texts <= self.holdout_texts)
            elif lst.read and self.v is not None and self.cor is not None:
                _classify(lst, self.cor, self.v, self.found)

    def maker(self) -> tuple[dict[str, int], dict[str, dict[str, int]]] | None:
        """maker_holdouts and maker_holdouts_by_list, or None while some list's speaks is unknown."""
        if self.lists is None:
            return None
        union: set[frozenset[int]] = set()
        by_list = {}
        for lst in self.lists:
            if lst.form == "cell" or lst.speaks is False:
                by_list[lst.id] = {"holdouts": 0, "parent_holdouts": 0}
                continue
            if lst.speaks is None:
                return None
            by_list[lst.id] = _counts(lst.maker, self.big_d)
            union.update(lst.maker)
        return _counts(union, self.big_d), by_list

    def compare_lists(self) -> None:
        """Step 3's comparison of lists and strangers, and step 4's of speaks and the maker holdouts."""
        imp, lists = self.imp, self.lists
        maker = self.maker()
        if maker is not None:
            self.result["maker_holdouts"] = maker[0]
        if imp is None or lists is None:
            return
        fail3, fail4 = self.fail[3], self.fail[4]
        by_id: dict[str, Any] = {}
        if "lists" in imp:
            theirs = imp["lists"]
            if not isinstance(theirs, list):
                fail3("import.json's lists is not a list")
                theirs = []
            ids = [x.get("id") if isinstance(x, dict) else None for x in theirs]
            want = [lst.id for lst in lists]
            if ids != want:
                fail3(f"import.json's lists has the ids {_shown(ids)}, and the registry's entries with decides: true "
                      f"that cover the cell are {_json(want)} in registry order")
            for x in theirs:
                if isinstance(x, dict) and isinstance(x.get("id"), str):
                    by_id.setdefault(x["id"], x)
            for lst in lists:
                x = by_id.get(lst.id)
                if x is None:
                    continue
                if set(x) != set(LIST_KEYS):
                    fail3(f"import.json's lists entry {lst.id} does not have exactly the keys credit, entry_sha256, "
                          "id, label, sha256 and speaks")
                registered = lst.entry.get("sha256")
                for key, ours in (("sha256", registered.lower() if isinstance(registered, str) else None),
                                  ("entry_sha256", lst.entry_sha256), ("credit", lst.entry.get("credit")),
                                  ("label", lst.entry.get("label"))):
                    if key in x and (ours is not None or key in lst.entry) and not _same(x[key], ours):
                        fail3(f"import.json's lists entry {lst.id} has {key} {_shown(x[key])}, and the registry "
                              f"entry gives {_shown(ours)}")
        if "strangers" in imp and all(lst.strangers is not None for lst in lists):
            ours = {lst.id: lst.strangers for lst in lists}
            if not _same(imp["strangers"], ours):
                fail3(f"import.json has strangers {_shown(imp['strangers'])}, and the checker finds {_json(ours)}")
        for lst in lists:
            x = by_id.get(lst.id)
            if x is not None and "speaks" in x and lst.speaks is not None and not _same(x["speaks"], lst.speaks):
                fail4(f"import.json's lists entry {lst.id} has speaks {_shown(x['speaks'])}, and the checker finds "
                      f"{_json(lst.speaks)}")
        if maker is not None:
            for key, ours in (("maker_holdouts", maker[0]), ("maker_holdouts_by_list", maker[1])):
                if key in imp and not _same(imp[key], ours):
                    fail4(f"import.json has {key} {_shown(imp[key])}, and the checker finds {_json(ours)}")

    def import_tsv(self) -> None:
        """Step 5."""
        fail = self.fail[5]
        plain, packed = self.dir / "import.tsv", self.dir / "import.tsv.gz"
        path = plain if plain.is_file() else packed if packed.is_file() else None
        if path is None:
            fail("neither import.tsv nor import.tsv.gz exists")
            return
        try:
            if path == plain:
                data = path.read_bytes()
            else:
                with open(path, "rb") as f:
                    data = b"".join(_gunzip(f, 0, None))
        except (OSError, EOFError, zlib.error) as e:
            fail(f"{path.name} could not be read ({e})")
            return
        lines = data.split(b"\n")
        last = lines.pop()
        if last:
            lines.append(last)
        self.tsv = lines
        position = {lst.id: i for i, lst in enumerate(self.lists or [])}
        seen: set[str] = set()
        prev: bytes | None = None
        for no, raw in enumerate(lines, 1):
            where = f"{path.name} line {no}"
            if last and no == len(lines):
                fail(f"{where} does not end with a newline")
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError:
                fail(f"{where} is not UTF-8")
                line = raw.decode("utf-8", "replace")
            if prev is not None and raw <= prev:
                fail(f"{where} does not come after the line before it in byte order")
            prev = raw
            fields = line.split("\t")
            text = fields[0]
            repeated = text in seen
            seen.add(text)
            if len(fields) != 3:
                fail(f"{where} does not have exactly three fields separated by TAB")
                continue
            verdict, list_id = fields[1], fields[2]
            known = verdict in (DECIDED, NEVER)
            if not known:
                fail(f"{where} has the verdict {verdict}, not {DECIDED} or {NEVER}")
            in_v = self.v is not None and text in self.v
            if self.v is not None and not in_v:
                fail(f"{where} has {text}, which is not in V")
            if repeated:
                fail(f"{where} has {text}, which an earlier line has too")
            if self.lists is None:
                continue
            if list_id not in position:
                fail(f"{where} names {list_id}, which is not in lists")
                continue
            lst = self.lists[position[list_id]]
            if lst.speaks is False:
                fail(f"{where} names {list_id}, whose speaks is false")
            if not (known and in_v and lst.read and self.cor is not None):
                continue
            assert self.v is not None
            bound = self.cor.bounds[self.v[text]]
            for why in decide_problems(lst, text, bound, self.big_d, self.holdout_texts, self.maps, verdict):
                fail(f"{where} names {list_id} for {text}, but {why}")
            # The first-list rule: the first list that gives NONHALT_PROVEN, or when none does the first that gives
            # DECIDED_LIST
            for earlier in self.lists[:position[list_id]]:
                if self.gives(earlier, text, bound, verdict):
                    fail(f"{where} names {list_id} for {text}, but {earlier.id}, earlier in registry order, would also "
                         + ("decide it" if verdict == DECIDED else f"give it {NEVER}"))
                    break
            if verdict == DECIDED:
                for other in self.lists:
                    if self.gives(other, text, bound, NEVER):
                        fail(f"{where} names {list_id} for {text} as {DECIDED}, but {other.id} would give it {NEVER}")
                        break

    def gives(self, lst: ListData, text: str, bound: int, verdict: str) -> bool:
        """Whether the list speaks and gives the machine of V with this text the verdict."""
        return bool(lst.speaks and lst.read and not decide_problems(lst, text, bound, self.big_d, self.holdout_texts,
                                                                     self.maps, verdict))

    def named(self) -> set[str]:
        assert self.tsv is not None
        return {raw.split(b"\t", 1)[0].decode("utf-8", "replace") for raw in self.tsv}

    def counts(self) -> None:
        """Step 6."""
        if self.tsv is None:
            return
        fail = self.fail[6]
        own: dict[str, Any] = {"imported": len(self.tsv), "import_digest": _hex(_sum_h(self.tsv))}
        if self.v is not None:
            named = self.named()
            left = [d for text, d in self.v.items() if text not in named]
            own["holdouts"] = sum(d == self.big_d for d in left)
            own["parent_holdouts"] = sum(d < self.big_d for d in left)
        self.result.update(own)
        imp = self.imp
        if imp is None:
            return
        if self.lists is not None and self.v is not None:
            # decided counts the lines that name each list, with either verdict, and never_halts those of NONHALT_PROVEN
            decided = {lst.id: {"holdouts": 0, "parent_holdouts": 0} for lst in self.lists}
            never = {lst.id: {"holdouts": 0, "parent_holdouts": 0} for lst in self.lists}
            for raw in self.tsv:
                fields = raw.decode("utf-8", "replace").split("\t")
                if len(fields) != 3 or fields[2] not in decided:
                    continue
                d = self.v.get(fields[0])
                if d is None:
                    m = _LIST_LINE.fullmatch(fields[0])
                    d = len(_machine_codes(m.group(1))) if m and m.start(1) == 0 else None
                if d is not None and d <= self.big_d:
                    where = "holdouts" if d == self.big_d else "parent_holdouts"
                    decided[fields[2]][where] += 1
                    if fields[1] == NEVER:
                        never[fields[2]][where] += 1
            for key, ours in (("decided", decided), ("never_halts", never)):
                if key in imp and not _same(imp[key], ours):
                    fail(f"import.json has {key} {_shown(imp[key])}, and the checker finds {_json(ours)}")
        for key in ("holdouts", "parent_holdouts", "imported", "import_digest"):
            if key in own and key in imp and not _same(imp[key], own[key]):
                fail(f"import.json has {key} {_shown(imp[key])}, and the checker finds {_json(own[key])}")

    def after_lists(self) -> None:
        """Step 7."""
        if self.v is None or self.tsv is None:
            return
        named = self.named()
        left = {text: d for text, d in self.v.items() if text not in named}
        for name, texts, what in (
                (f"{self.stem}_holdouts_after_lists_unofficial.txt", [t for t, d in left.items() if d == self.big_d],
                 f"at depth {self.big_d} that no line of import.tsv names"),
                (f"{self.stem}_parent_holdouts_after_lists_unofficial.txt",
                 [t for t, d in left.items() if d < self.big_d], f"at depths below {self.big_d} that no line of "
                                                                  "import.tsv names")):
            message = _text_list(self.dir, name, texts, what)
            if message:
                self.fail[7](message)


def _file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _import_check(cell_dir: Path, census: Path, registry: Path, data: Path | None,
                  jobs: int) -> tuple[dict[str, Any], int]:
    """The import check. The census is named on the command line but not otherwise used (section 13)."""
    started = time.perf_counter()
    result: dict[str, Any] = {
        "format": IMPORT_CHECK_FORMAT, "checker": CHECKER, "cell": None, "depth": None, "pass": False, "failures": [],
        "holdouts": None, "parent_holdouts": None, "maker_holdouts": None, "imported": None, "import_digest": None,
        "lists": None, "seconds": 0.0, "summary_sha256": None, "amend_sha256": None, "import_sha256": None,
    }
    result["amend_sha256"] = _file_sha256(cell_dir / "amend.json")
    result["import_sha256"] = _file_sha256(cell_dir / "import.json")
    if data is None:  # the directory two levels above the directory that holds the registry
        parents = registry.resolve().parents
        data = parents[2] if len(parents) > 2 else None
    failures = _Failures()
    summary = _amend_base(cell_dir, result, failures.at(1), ", and an import rests on a passing full check")
    if summary is not None:
        _Import(cell_dir, summary, registry, data, jobs, result, failures).run()
    result["pass"] = failures.count == 0
    result["failures"] = failures.first()
    result["seconds"] = round(time.perf_counter() - started, 3)
    with open(cell_dir / "import_check.json", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(result, indent=2) + "\n")
    return result, failures.count


def import_check(cell_dir: Path, census: Path, lists: Path, data: Path | None = None, jobs: int = 1) -> dict[str, Any]:
    """Check one cell's import against the registry lists and its list files (section 13), write import_check.json
    into the cell directory and return its object. data is the directory that the registry's file names are relative
    to, by default the directory two levels above the registry's own. It never writes check.json or amend_check.json."""
    return _import_check(Path(cell_dir), Path(census), Path(lists), None if data is None else Path(data), jobs)[0]


# ---------------------------------------------------------------------------------------------------------------------
# The command line


def _jobs(x: str) -> int:
    n = int(x)
    if n < 1:
        raise argparse.ArgumentTypeError("--jobs must be at least 1")
    return n


def _say(line: str, stream: IO[str] | None = None) -> None:
    """Print a line that may quote text from the cell or a list file. A character that the stream's encoding cannot
    write is printed as a backslash escape, so the line prints under any encoding, cp1252 among them. The JSON files
    keep the text as it is."""
    stream = sys.stdout if stream is None else stream
    encoding = getattr(stream, "encoding", None) or "utf-8"
    print(line.encode(encoding, "backslashreplace").decode(encoding), file=stream)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bbi9check.py", description="Check one BBi cell (CHECKING.md).")
    parser.add_argument("cell_dir", type=Path, metavar="CELL_DIR")
    parser.add_argument("--census", type=Path, metavar="CENSUS_TSV")
    parser.add_argument("--jobs", type=_jobs, default=1, metavar="N")
    parser.add_argument("--plain", action="store_true",
                        help="check every machine to its depth's bound and read the claims apart, even with claims.idx")
    parser.add_argument("--amend", action="store_true",
                        help="check the cell's amendment (CHECKING.md section 12) instead of the cell")
    parser.add_argument("--import", dest="import_", action="store_true",
                        help="check the cell's import from other people's lists (CHECKING.md section 13)")
    parser.add_argument("--lists", type=Path, metavar="LISTS_YAML", help="the registry of lists, with --import")
    parser.add_argument("--data", type=Path, metavar="DIR",
                        help="the directory of the list files, with --import (default two levels above the registry's)")
    parser.add_argument("--unknown-digest", dest="unknown_digest", action="store_true",
                        help="add unknown_digest to a passing check.json from the lists the check compared "
                             "(CHECKING.md section 12)")
    parser.add_argument("--gpu", action="store_true",
                        help="run the UNKNOWN claims to their bounds on the GPU (CHECKING.md section 9, 'An "
                             "accelerated checker'); needs an NVIDIA card and the CUDA toolkit")
    parser.add_argument("--python", action="store_true",
                        help="walk every group of the indexed check with the Python code, the reference, even when "
                             "bbi9check-core is built")
    args = parser.parse_args(argv)  # exits with 2 on bad usage
    if args.python and (args.amend or args.import_ or args.plain or args.unknown_digest):
        parser.error("--python with --amend, --import, --plain or --unknown-digest is bad usage")
    if args.gpu and (args.amend or args.import_ or args.plain or args.unknown_digest):
        parser.error("--gpu with --amend, --import, --plain or --unknown-digest is bad usage")
    if args.unknown_digest and (args.amend or args.import_ or args.plain):
        parser.error("--unknown-digest with --amend, --import or --plain is bad usage")
    if args.census is None and not args.unknown_digest:
        parser.error("--census is required")
    if args.amend and args.plain:
        parser.error("--amend with --plain is bad usage")  # exits with 2
    if args.import_ and (args.amend or args.plain):
        parser.error("--import with --amend or --plain is bad usage")
    if args.import_ and args.lists is None:
        parser.error("--import without --lists is bad usage")
    if not args.import_ and (args.lists is not None or args.data is not None):
        parser.error("--lists or --data without --import is bad usage")
    if not args.cell_dir.is_dir():
        _say(f"bbi9check.py: {args.cell_dir} is not a directory", sys.stderr)
        return 2
    if args.unknown_digest:
        code, line = backfill_unknown_digest(args.cell_dir)
        _say(line)
        return code
    if not args.census.is_file():
        _say(f"bbi9check.py: {args.census} is not a file", sys.stderr)
        return 2
    if args.import_:
        r, count = _import_check(args.cell_dir, args.census, args.lists, args.data, args.jobs)
        cell = f"{r['cell'][0]}x{r['cell'][1]} depth {r['depth']}" if r["cell"] else str(args.cell_dir)
        if r["pass"]:
            maker = r["maker_holdouts"]
            _say(f"PASS {cell} import: {r['imported']} imported from {len(r['lists'])} lists, {r['holdouts']} holdouts "
                 f"and {r['parent_holdouts']} parent holdouts after the lists, {maker['holdouts']} and "
                 f"{maker['parent_holdouts']} maker holdouts, {r['seconds']} s")
            return 0
        _say(f"FAIL {cell} import: {count} failures, the first is: {r['failures'][0]}")
        return 1
    if args.amend:
        r, count = _amend_check(args.cell_dir, args.census, args.jobs)
    else:
        try:
            r, count = _check(args.cell_dir, args.census, args.jobs, args.plain, args.gpu, args.python)
        except CoreError as e:  # no check.json is written, and an older one is left as it is
            _say(f"core: {e}", sys.stderr)
            return 3
    cell = f"{r['cell'][0]}x{r['cell'][1]} depth {r['depth']}" if r["cell"] else str(args.cell_dir)
    match = {True: "matches", None: "skipped"}.get(r["census_match"], "differs")
    # past depth 9 there is no census count (section 8)
    census = "no census past depth 9" if r["census"] is None else f"census {r['census']} {match}"
    if args.amend:
        if r["pass"]:
            _say(f"PASS {cell} amendment: {r['amended']} amended, {r['holdouts']} holdouts, {r['parent_holdouts']} "
                 f"parent holdouts, {census}, {r['seconds']} s")
            return 0
        _say(f"FAIL {cell} amendment: {count} failures, the first is: {r['failures'][0]}")
        return 1
    lists = ", holdout lists left to the amendment check" if r["holdout_lists"] == "amendment" else ""
    if r["pass"]:
        _say(f"PASS {cell}: {r['cell_machines']} machines ({r['late_cell_machines']} late), {r['holdouts']} holdouts, "
             f"{r['parent_holdouts']} parent holdouts, {census}{lists}, {r['seconds']} s")
        return 0
    _say(f"FAIL {cell}{lists}: {count} failures, the first is: {r['failures'][0]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
