#!/usr/bin/env python3
"""Independent checker for one cell of the BBi(9) tracker.

Written from CHECKING.md alone, with the standard library only. It rebuilds the cell's corridor walk, runs every
halter to its halt, verifies every certificate in the claims file and compares its own totals with summary.json
(CHECKING.md section 9). When the cell has claims.idx, it reads each group's claims alongside that group's walk
instead, so a certified machine is never run to the depth's bound ("When claims.idx exists"). --plain keeps the
first way. It checks cells of format bbi9-cell/1, bbi9-cell/2, which adds the NONHALT_CPS certificate, bbi9-cell/3,
which adds the NONHALT_RWL certificate, and bbi9-cell/4, which adds the NONHALT_FAR certificate. For each NONHALT_CPS
claim it computes the sets Lw, Rw and C that section 6 defines, for each NONHALT_RWL claim the set C of repeated word
lists, and for each NONHALT_FAR claim the relation R that the machine and the claim's automaton fix, with rule 4
applied until nothing changes, and then the set a, at every automaton state.

A cell may hold an amendment, which reruns its holdouts (section 12). The full check then leaves the holdout lists to
the amendment check when amend.json amends this very summary.json, and --amend is the amendment check. It rests on a
passing check.json, reads the claims file only to count, digest and collect its UNKNOWN texts, verifies every line of
amend.tsv and compares amend.json's counts, the shorter holdout lists and the census rule.

    python bbi9check.py CELL_DIR --census CENSUS_TSV [--jobs N] [--plain]
    python bbi9check.py CELL_DIR --amend --census CENSUS_TSV [--jobs N]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import multiprocessing
import struct
import sys
import time
import zlib
from array import array
from bisect import insort
from collections import deque
from dataclasses import dataclass, field
from operator import methodcaller
from pathlib import Path
from typing import IO, Any, Callable, Iterable, Iterator, Optional, Sequence

CHECKER = "bbi9check 1.5"
FORMAT_1 = "bbi9-cell/1"
FORMAT_2 = "bbi9-cell/2"  # section 5: format 1 with the NONHALT_CPS certificate added
FORMAT_3 = "bbi9-cell/3"  # section 5: format 2 with the NONHALT_RWL certificate added
FORMAT_4 = "bbi9-cell/4"  # section 5: format 3 with the NONHALT_FAR certificate added
SUMMARY_FORMATS = (FORMAT_1, FORMAT_2, FORMAT_3, FORMAT_4)  # format k is SUMMARY_FORMATS[k - 1]
SUMMARY_NAMED = ", ".join(repr(f) for f in SUMMARY_FORMATS[:-1]) + f" or {SUMMARY_FORMATS[-1]!r}"
CHECK_FORMAT = "bbi9-check/1"
MAX_BOUND = 10_000_000  # section 9 steps 1 and 3: the producer's largest cap
CPS = "NONHALT_CPS"
CPS_MAX_N = 5  # section 6: 1 <= n <= 5
CPS_MAX_C = 20_000  # section 6: 1 <= c <= 20,000
RWL = "NONHALT_RWL"
RWL_MAX_B = 6  # section 6: 1 <= b <= 6
RWL_MAX_T = 3  # section 6: 1 <= T <= 3
RWL_MAX_C = 20_000  # section 6: 1 <= c <= 20,000
RWL_BLOCK_STEPS = 1_000  # section 6: a block run must leave its block within 1,000 steps
FAR = "NONHALT_FAR"
FAR_MAX_N = 10  # section 6: 1 <= n <= 10
FAR_MAX_E = 102_010  # section 6: 1 <= e <= 102,010
SINCE = {CPS: 2, RWL: 3, FAR: 4}  # section 5: the first format with each of these certificates
CAP_SHALLOW = 4_000_000  # section 8: census cap for an ancestor at depths 0 to 7
CAP_DEPTH8 = 100_000  # section 8: census cap for an ancestor at depth 8
LIMIT = 9  # section 3: w and t never exceed 9
MAX_STATES = 10  # states A to J
MAX_SYMBOLS = 10  # symbols 0 to 9
SPLIT_DEPTH = 4  # with --jobs, the walk hands the subtrees below this depth to the pool
GROUPS_PER_JOB = 16
CHUNK_LINES = 20_000  # claims lines per pool task
INDEX_HEADER = "group\tseq\toffset\tbytes\tlines"  # section 5: the first line of claims.idx
TOP_GROUP = "top"  # section 5: the group of the claims at depths below claims_split
BATCH_GROUPS = 32  # with claims.idx, the groups per pool task
READ_BYTES = 1 << 15  # compressed bytes fed to the decompressor at a time, so memory never grows with the claims
MAX_DIGITS = 18  # a claims.idx count with more digits is refused rather than converted
TOP = 10
MAX_FAILURES = 50
VERDICTS = ("NONHALT_CYCLER", "NONHALT_TRANSLATED", CPS, RWL, FAR, "UNKNOWN")
# The counts every corridor entry has. A format 2 to 4 entry also has NONHALT_CPS, and a format 1 entry must not. A
# format 3 or 4 entry also has NONHALT_RWL, and a format 1 or 2 entry must not. A format 4 entry also has NONHALT_FAR,
# and a format 1 to 3 entry must not.
ENTRY_KEYS = ("machines", "HALT", "NONHALT_CYCLER", "NONHALT_TRANSLATED", "UNKNOWN", "max_halt_steps")
OWN_KEYS = ("halter_digest", "claims", "claims_digest", "cell_machines", "late_cell_machines", "holdouts",
            "parent_holdouts", "top_halters")
MASK = (1 << 64) - 1
# Amendments (section 12)
AMEND_FORMAT = "bbi9-amend/1"
AMEND_CHECK_FORMAT = "bbi9-amend-check/1"
AMEND_KEYS = ("format", "cell", "depth", "base_summary_sha256", "claims_format", "corridor", "holdouts",
              "parent_holdouts", "amended", "amend_digest")  # the keys of amend.json a checker uses, all required
CLAIMS_FORMATS = (FORMAT_2, FORMAT_3, FORMAT_4)  # the claims_format values amend.json may have
CLAIMS_NAMED = ", ".join(repr(f) for f in CLAIMS_FORMATS[:-1]) + f" or {CLAIMS_FORMATS[-1]!r}"
CERTIFICATES = ("NONHALT_CYCLER", "NONHALT_TRANSLATED", CPS, RWL, FAR)
SCAN_READ = 1 << 16  # compressed bytes read at a time by the claims scan
SCAN_BLOCK = 1 << 20  # the claims scan hashes blocks of whole lines of about this many bytes
SCAN_TASK = 1 << 20  # with claims.idx, the compressed bytes of claims.tsv.gz per pool task of the claims scan
AMEND_CHUNK = 64  # amend.tsv lines per pool task, few because one certificate may build a large C
DIGITS = "0123456789"
LETTERS = "ABCDEFGHIJ"

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


def _bounded(x: str) -> int:
    """The value of a string of digits, or MAX_BOUND + 1 for anything larger. A long string is never converted."""
    x = x.lstrip("0")
    if len(x) > len(str(MAX_BOUND)):
        return MAX_BOUND + 1
    return min(int(x or "0"), MAX_BOUND + 1)


def _cps_fields(rest: Sequence[str]) -> tuple[int, int] | None:
    """n and c of a NONHALT_CPS certificate whose fields parse, or None when either is out of range."""
    n, c = _bounded(rest[0]), _bounded(rest[1])
    return (n, c) if 1 <= n <= CPS_MAX_N and 1 <= c <= CPS_MAX_C else None


def _rwl_fields(rest: Sequence[str]) -> tuple[int, int, int] | None:
    """b, T and c of a NONHALT_RWL certificate whose fields parse, or None when any is out of range."""
    b, big_t, c = _bounded(rest[0]), _bounded(rest[1]), _bounded(rest[2])
    in_range = 1 <= b <= RWL_MAX_B and 1 <= big_t <= RWL_MAX_T and 1 <= c <= RWL_MAX_C
    return (b, big_t, c) if in_range else None


def _verify(machine: Machine, verdict: str, rest: Sequence[str], text: str) -> bool:
    """Verify a certificate whose fields already parse, for the machine of the text. One whose j is above MAX_BOUND
    fails without being run, a NONHALT_CPS or NONHALT_RWL certificate with a number out of range fails without being
    computed, and so does a NONHALT_FAR certificate whose side, n, table or e is out of range."""
    if verdict == "UNKNOWN":
        return True
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
    if verdict == "NONHALT_CYCLER":
        i, j = _bounded(rest[0]), _bounded(rest[1])
        return 0 <= i < j <= MAX_BOUND and _cycler(machine.table, i, j)
    i, j = _bounded(rest[1]), _bounded(rest[2])
    return 1 <= i < j <= MAX_BOUND and _translated(machine.table, 1 if rest[0] == "R" else -1, i, j)


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
        child_late = is_late or n > (CAP_DEPTH8 if d == 8 else CAP_SHALLOW)
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
    # The cell's format, 1 to 4. NONHALT_CPS claims may appear in formats 2 to 4, NONHALT_RWL claims in formats 3 and
    # 4, and NONHALT_FAR claims in format 4. In the other formats each one fails.
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


def _claim(t: ClaimTally, raw: bytes, where: str) -> str | None:
    """Step 3 for one claims line, given without its newline: count it, digest it and verify its certificate.

    Returns its verdict, or None when it does not parse. where names the line in messages.
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
    try:
        machine = parse_text(text)
    except ValueError as e:
        t.problem(f"{where}: {text!r} is not a machine text ({e})")
        return None
    verdict, rest = (fields[1], fields[2:]) if len(fields) > 1 else ("", [])
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
    elif verdict in ("NONHALT_CYCLER", "NONHALT_TRANSLATED") and _bounded(rest[-1]) > MAX_BOUND:
        t.invalid += 1
        t.problem(f"{where}: {shown} has j above the bound {MAX_BOUND} of this checker")
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
    if _claim(claims, lines.take(), where) != "UNKNOWN":
        return None  # a certificate, verified by _claim, or a line that does not parse
    halted, n, st, r = _run(table, bound)
    if not halted:
        return None
    claims.defect(f"{where}: {text} at depth {d} is claimed UNKNOWN but halts after {_count(n, 'step')}")
    return n, st, r


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
                   jobs: int, fmt: int) -> tuple[WalkTally, ClaimTally]:
    """Steps 2 and 3 of the indexed check. The top group is walked here. The groups it reaches go to the pool in
    batches as they are reached, with a bounded number pending, and are merged in the order reached."""
    path = str(cell_dir / "claims.tsv.gz")
    walk = WalkTally.empty(cor.depth)
    top_claims, group_claims = ClaimTally(fmt=fmt), ClaimTally()
    pending: deque[Any] = deque()
    batch: list[tuple[Node, str, list[Member]]] = []

    def collect(result: tuple[WalkTally, ClaimTally]) -> None:
        walk.merge(result[0])
        group_claims.merge(result[1])

    def flush() -> None:
        nonlocal batch
        if not batch:
            return
        job, batch = (cor, path, batch, fmt), []
        if pool is None:
            collect(_groups_job(job))
            return
        pending.append(pool.apply_async(_groups_job, (job,)))
        while len(pending) > 2 * jobs:
            collect(pending.popleft().get())

    def emit(node: Node) -> None:
        group = _node_text(node, cor.symbols)
        batch.append((node, group, index.pop(group, [])))
        if len(batch) == BATCH_GROUPS:
            flush()

    root = _root(cor)
    with open(path, "rb") as f:
        lines = _Lines(f, TOP_GROUP, index.pop(TOP_GROUP, []), top_claims)
        walk.merge(_walk(cor, [] if root is None else [root], split, emit, lines, top_claims))
        _drain(lines, top_claims, 0)
    flush()
    while pending:
        collect(pending.popleft().get())
    claims = ClaimTally()
    claims.merge(top_claims)
    claims.merge(group_claims)
    for group in index:
        claims.defect(f"claims.idx names the group {group}, which the walk never reaches")
    return walk, claims


# ---------------------------------------------------------------------------------------------------------------------
# The census (section 8)


def census_count(census: Path, states: int, symbols: int, depth: int) -> int:
    """nodes in the row (D, S, K) when D <= 8, pred in the row (9, S, K) when D = 9, and 0 for a missing row."""
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
    """1 to 4 for a summary whose format is one of SUMMARY_FORMATS."""
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
    if not (1 <= depth <= 9 and 1 <= big_s <= MAX_STATES and 1 <= big_k <= MAX_SYMBOLS):
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
        # NONHALT_CPS belongs to formats 2 to 4, NONHALT_RWL to formats 3 and 4, and NONHALT_FAR to format 4 (section 5)
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
    over = [(d, b) for d, b in enumerate(bounds) if b > MAX_BOUND]
    for d, b in over:
        failures.append(f"depth {d} max_halt_steps {b} is above the bound {MAX_BOUND} of this checker "
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
            # a format 1 entry has no NONHALT_CPS, a format 1 or 2 entry no NONHALT_RWL, and a format 1 to 3 entry no
            # NONHALT_FAR. Their counts are taken as 0.
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
                     jobs: int, fmt: int) -> tuple[WalkTally, ClaimTally, str | None]:
    """Steps 2 and 3, or the indexed check's steps 2 and 3 when index holds claims_split and the groups. fmt is the
    cell's format, which says whether NONHALT_CPS claims (formats 2 to 4), NONHALT_RWL claims (formats 3 and 4) and
    NONHALT_FAR claims (format 4) may appear."""
    if index is not None:
        return (*_check_indexed(cell_dir, cor, index[0], index[1], pool, jobs, fmt), None)
    walk = _walk_cell(cor, pool, jobs)
    return (walk, *_check_claims(cell_dir, pool, jobs, fmt))


def _check(cell_dir: Path, census: Path, jobs: int, plain: bool = False) -> tuple[dict[str, Any], int]:
    started = time.perf_counter()
    # holdout_lists stays null when the check stops before step 4
    result: dict[str, Any] = {
        "format": CHECK_FORMAT, "checker": CHECKER, "cell": None, "depth": None, "pass": False, "failures": [],
        "cell_machines": None, "census": None, "late_cell_machines": None, "census_match": None, "holdouts": None,
        "parent_holdouts": None, "holdout_lists": None, "top_halters": None, "halter_digest": None,
        "claims_digest": None, "seconds": 0.0, "summary_sha256": None,
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
        stop = False
        if (cell_dir / "claims.idx").exists():
            if not plain:
                index = _read_index(cell_dir, summary, cor, failures)
                stop = index is None
            elif (cell_dir / "claims.tsv").exists():
                failures.append(BESIDE)
                stop = True
        if not stop:
            if jobs > 1:
                with multiprocessing.get_context("spawn").Pool(jobs) as pool:
                    walk, claims, claims_error = _walk_and_claims(cell_dir, cor, index, pool, jobs, fmt)
            else:
                walk, claims, claims_error = _walk_and_claims(cell_dir, cor, index, None, 1, fmt)
            amended = _amends_this_summary(cell_dir, result["summary_sha256"])
            _compare(cell_dir, summary, cor, walk, claims, claims_error, result, failures, amended)
    result["pass"] = not failures
    result["failures"] = failures[:MAX_FAILURES]
    result["seconds"] = round(time.perf_counter() - started, 3)
    with open(cell_dir / "check.json", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(result, indent=2) + "\n")
    return result, len(failures)


def check_cell(cell_dir: Path, census: Path, jobs: int = 1, plain: bool = False) -> dict[str, Any]:
    """Check one cell directory against the census, write check.json into it and return its object.

    A cell with claims.idx gets the indexed check unless plain is set (section 9, "When claims.idx exists").
    """
    return _check(Path(cell_dir), Path(census), jobs, plain)[0]


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


def _scan_block(block: bytes) -> tuple[int, int, list[bytes], bool]:
    """Pool worker: the number of lines in a block of lines, the sum of h over them, its UNKNOWN lines, and whether it
    ends with a newline. A last line without one still counts."""
    lines = block.split(b"\n")
    last = lines.pop()
    if last:
        lines.append(last)
    return len(lines), _sum_h(lines), _unknown_lines(block), not last


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

    def add(self, scanned: tuple[int, int, list[bytes], bool]) -> bool:
        """Add a _scan_block result and return whether its block ends with a newline."""
        n, total, unknown, whole = scanned
        self.lines += n
        self.total = (self.total + total) & MASK
        self.unknown.extend(unknown)
        return whole

    def merge(self, other: ScanTally) -> None:
        self.lines += other.lines
        self.total = (self.total + other.total) & MASK
        self.unknown.extend(other.unknown)
        self.errors.extend(other.errors)


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

    def collect(scanned: tuple[int, int, list[bytes], bool]) -> None:
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
    """Whether a JSON value is the checker's own value, compared as JSON, so that 4.0 and true are not 4."""
    return _json(theirs) == _json(ours)


def _summary_problem(summary: dict[str, Any]) -> str | None:
    """Why summary.json lacks what the amendment check reads from it before step 7 (format, cell, depth and each
    corridor entry's depth and UNKNOWN), or None. A cell whose full check passed has all of them."""
    if summary.get("format") not in SUMMARY_FORMATS:
        return f"summary.json does not have format {SUMMARY_NAMED}"
    cell, depth = summary.get("cell"), summary.get("depth")
    if not (isinstance(cell, list) and len(cell) == 2 and all(_uint_value(x) for x in cell) and _uint_value(depth)
            and 1 <= depth <= 9 and 1 <= cell[0] <= MAX_STATES and 1 <= cell[1] <= MAX_SYMBOLS):
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


def _amend_base(cell_dir: Path, result: dict[str, Any], fail: Callable[[str], None]) -> dict[str, Any] | None:
    """Step 1. Returns summary.json's object, or None when the check cannot go on without it."""
    read = _load(cell_dir / "summary.json", fail)
    summary = None
    if read is not None:
        result["summary_sha256"] = hashlib.sha256(read[0]).hexdigest()
        summary = read[1]
    rests = ", and an amendment rests on a passing full check"
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
        for key in (RWL, FAR):  # NONHALT_RWL from "bbi9-cell/3" on, and NONHALT_FAR from "bbi9-cell/4" on
            if number >= SINCE[key] and key not in entry:
                fail(f"amend.json corridor entry {d} has no {key}, which claims_format {claims_format!r} requires")
                ok = False
            elif number < SINCE[key] and key in entry:
                fail(f"amend.json corridor entry {d} has {key}, which claims_format {claims_format!r} does not have")
                ok = False
    return ok


def _read_amend(cell_dir: Path, summary: dict[str, Any], result: dict[str, Any],
                fail: Callable[[str], None]) -> tuple[dict[str, Any] | None, int | None, bool]:
    """Step 2. Returns amend.json's object, its claims_format as 2, 3 or 4 when that is usable, and whether its
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


def _base_set(cell_dir: Path, summary: dict[str, Any], pool: Any, jobs: int,
              fail: Callable[[str], None]) -> dict[str, int] | None:
    """Step 3. U, each text with its depth, or None when the claims file could not be read to the end."""
    big_d = summary["depth"]
    if (cell_dir / "claims.idx").exists() and (cell_dir / "claims.tsv").exists():
        fail(BESIDE)
    scan = _scan_claims(cell_dir, pool, jobs)
    if scan is None:
        fail("the cell has no claims.tsv or claims.tsv.gz")
        return None
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


def _amend_job(job: tuple[str, int, list[bytes], int]) -> ClaimTally:
    """Pool worker: parse, count, digest and verify a chunk of amend.tsv's lines, which start at line number job[1].
    job[3] is amend.json's claims_format as 2, 3 or 4, which says whether NONHALT_RWL and NONHALT_FAR lines may
    appear."""
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
                # a "bbi9-cell/2" entry has no NONHALT_RWL, and a "bbi9-cell/2" or "bbi9-cell/3" entry no NONHALT_FAR.
                # Their counts are taken as 0.
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
# The command line


def _jobs(x: str) -> int:
    n = int(x)
    if n < 1:
        raise argparse.ArgumentTypeError("--jobs must be at least 1")
    return n


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bbi9check.py", description="Check one BBi(9) cell (CHECKING.md).")
    parser.add_argument("cell_dir", type=Path, metavar="CELL_DIR")
    parser.add_argument("--census", type=Path, required=True, metavar="CENSUS_TSV")
    parser.add_argument("--jobs", type=_jobs, default=1, metavar="N")
    parser.add_argument("--plain", action="store_true",
                        help="check every machine to its depth's bound and read the claims apart, even with claims.idx")
    parser.add_argument("--amend", action="store_true",
                        help="check the cell's amendment (CHECKING.md section 12) instead of the cell")
    args = parser.parse_args(argv)  # exits with 2 on bad usage
    if args.amend and args.plain:
        parser.error("--amend with --plain is bad usage")  # exits with 2
    if not args.cell_dir.is_dir():
        print(f"bbi9check.py: {args.cell_dir} is not a directory", file=sys.stderr)
        return 2
    if not args.census.is_file():
        print(f"bbi9check.py: {args.census} is not a file", file=sys.stderr)
        return 2
    if args.amend:
        r, count = _amend_check(args.cell_dir, args.census, args.jobs)
    else:
        r, count = _check(args.cell_dir, args.census, args.jobs, args.plain)
    cell = f"{r['cell'][0]}x{r['cell'][1]} depth {r['depth']}" if r["cell"] else str(args.cell_dir)
    census = {True: "matches", None: "skipped"}.get(r["census_match"], "differs")
    if args.amend:
        if r["pass"]:
            print(f"PASS {cell} amendment: {r['amended']} amended, {r['holdouts']} holdouts, {r['parent_holdouts']} "
                  f"parent holdouts, census {r['census']} {census}, {r['seconds']} s")
            return 0
        print(f"FAIL {cell} amendment: {count} failures, the first is: {r['failures'][0]}")
        return 1
    lists = ", holdout lists left to the amendment check" if r["holdout_lists"] == "amendment" else ""
    if r["pass"]:
        print(f"PASS {cell}: {r['cell_machines']} machines ({r['late_cell_machines']} late), {r['holdouts']} holdouts, "
              f"{r['parent_holdouts']} parent holdouts, census {r['census']} {census}{lists}, {r['seconds']} s")
        return 0
    print(f"FAIL {cell}{lists}: {count} failures, the first is: {r['failures'][0]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
