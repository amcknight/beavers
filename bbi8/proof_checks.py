#!/usr/bin/env python3
"""proof_checks.py -- independent checks for PROOF.md (BBi(8) holdouts #7 and #8 never halt).

Standard library only. Run as:  python proof_checks.py
Each check prints one line starting with PASS or FAIL. The exit status is 1 if any check fails.
Nothing here imports another script of this folder. Every statement is re-implemented from PROOF.md.

Conventions (PROOF.md section 1)
  positions are integers, R = +1, L = -1, bit i is the cell at position -1-i (bit -1 is position 0)
  omega(L, V) is the word of length L: bit i holds 2 if binary digit i of V is 1, and 1 if it is 0
  K(L, V) is state C, head at position 0, tape omega(L, V)
  for #8 every tape symbol is passed through sigma = (0->0, 1->2, 2->3, 3->1)
  h(y) = y - 1 + 2^(nu(y)+2), and a bounce K(L, V) has counter value y = V + 1
"""
from __future__ import annotations

import random
import sys
import time

T0 = time.time()
FAILS = 0


def report(tag: str, ok: bool, detail: str = '') -> None:
    global FAILS
    if not ok:
        FAILS += 1
    print(f'{"PASS" if ok else "FAIL"}  {tag}  {detail}  [{time.time() - T0:.1f}s]', flush=True)


# =====================================================================================================
# Machines and the map h
# =====================================================================================================
M7 = '1RB1LC2LA---_2RC---------_0LA2RC3LC1RC'
M8 = '1RB---2LC3LA_2LC---------_0LA2RC3RC1LC'
A, B, C = 0, 1, 2


def parse(text: str) -> dict:
    table = {}
    for q, part in enumerate(text.split('_')):
        for s in range(4):
            cell = part[3 * s:3 * s + 3]
            if cell != '---':
                table[(q, s)] = (int(cell[0]), +1 if cell[1] == 'R' else -1, 'ABC'.index(cell[2]))
    return table


TM = {7: parse(M7), 8: parse(M8)}
SIG = {7: (0, 1, 2, 3), 8: (0, 2, 3, 1)}       # SIG[mach][symbol of #7] = symbol of mach


def tr(text: str) -> tuple:
    return (int(text[0]), +1 if text[1] == 'R' else -1, 'ABC'.index(text[2]))


def nu(y: int) -> int:
    return (y & -y).bit_length() - 1


def h(y: int) -> int:
    return y - 1 + (1 << (nu(y) + 2))


def check_tables() -> None:
    # [F1] the transition tables of Definition 1.1, read off the machine texts
    want7 = {(A, 0): tr('1RB'), (A, 1): tr('1LC'), (A, 2): tr('2LA'), (B, 0): tr('2RC'),
             (C, 0): tr('0LA'), (C, 1): tr('2RC'), (C, 2): tr('3LC'), (C, 3): tr('1RC')}
    want8 = {(A, 0): tr('1RB'), (A, 2): tr('2LC'), (A, 3): tr('3LA'), (B, 0): tr('2LC'),
             (C, 0): tr('0LA'), (C, 1): tr('2RC'), (C, 2): tr('3RC'), (C, 3): tr('1LC')}
    report('F1   transition tables of #7 and #8 (Definition 1.1)', TM[7] == want7 and TM[8] == want8)
    # [F2] Lemma 2.7: the six shared transitions correspond under sigma, the undefined entries correspond,
    #      and A0, B0 are the two exceptions
    s = SIG[8]
    ok = True
    for key in [(A, 1), (A, 2), (C, 0), (C, 1), (C, 2), (C, 3)]:
        q, a = key
        w, d, q2 = TM[7][key]
        ok &= TM[8].get((q, s[a])) == (s[w], d, q2)
    for key in [(A, 3), (B, 1), (B, 2), (B, 3)]:
        q, a = key
        ok &= key not in TM[7] and (q, s[a]) not in TM[8]
    ok &= TM[8][(A, 0)] != (s[1], +1, B) and TM[8][(B, 0)] != (s[2], +1, C)
    report('F2   Lemma 2.7: sigma-correspondence of A1 A2 C0 C1 C2 C3 and the undefined entries, A0 B0 differ', ok)


# =====================================================================================================
# A direct simulator on a sparse tape
# =====================================================================================================
def bitpos(i: int) -> int:
    return -1 - i


def omega(mach: int, L: int, V: int) -> dict:
    s = SIG[mach]
    return {bitpos(i): s[2] if (V >> i) & 1 else s[1] for i in range(L)}


def decode(mach: int, tape: dict):
    """(L, V) if the nonzero cells of tape are exactly sigma(omega(L, V)) for some L >= 1, else None."""
    s = SIG[mach]
    inv = {s[2]: 1, s[1]: 0}
    nz = {x: v for x, v in tape.items() if v != 0}
    L = len(nz)
    if L == 0 or set(nz) != {bitpos(i) for i in range(L)}:
        return None
    V = 0
    for i in range(L):
        v = nz[bitpos(i)]
        if v not in inv:
            return None
        V |= inv[v] << i
    return (L, V)


def clean(tape: dict) -> dict:
    return {x: v for x, v in tape.items() if v}


def run_steps(mach: int, q: int, x: int, tape: dict, n: int):
    """Exactly n steps. Returns (q, x, tape) or None if the machine halts first."""
    T = TM[mach]
    for _ in range(n):
        t = T.get((q, tape.get(x, 0)))
        if t is None:
            return None
        w, d, q = t
        tape[x] = w
        x += d
    return q, x, tape


def run_to_bounce(mach: int, q: int, x: int, tape: dict, min_steps: int = 1, cap: int = 10 ** 6):
    """Run until state C at position 0 after at least min_steps steps, or a halt.
    Returns ('bounce', tape, steps) or ('halt', q, symbol, x, steps)."""
    T = TM[mach]
    steps = 0
    while steps < cap:
        if steps >= min_steps and q == C and x == 0:
            return ('bounce', tape, steps)
        a = tape.get(x, 0)
        t = T.get((q, a))
        if t is None:
            return ('halt', q, a, x, steps)
        w, d, q = t
        tape[x] = w
        x += d
        steps += 1
    raise RuntimeError('step cap')


# =====================================================================================================
# Section 2 checks (the tape)
# =====================================================================================================
def check_start() -> None:
    # [F3] Lemma 2.5 and its #8 form in Lemma 2.8: blank tape, state A at position -2
    ok = True
    for mach, n in ((7, 2), (8, 4)):
        r = run_to_bounce(mach, A, -2, {}, min_steps=1)
        ok &= r[0] == 'bounce' and r[2] == n and decode(mach, r[1]) == (2, 1)
    report('F3   start: #7 reaches K(2,1) after 2 steps, #8 after 4 steps (counter value y = 2)', ok)


def check_sweeps() -> None:
    """Lemma 2.1 parts 1, 2, 3 and their #8 forms, blocks of length k <= 9 at bits j <= 6, random other cells."""
    rng = random.Random(3)
    ok = True
    n = 0
    for mach in (7, 8):
        s = SIG[mach]
        for j in range(0, 7):
            for k in range(0, 10):
                for _ in range(4):
                    block = [bitpos(j + r) for r in range(k)]
                    base = {bitpos(i): rng.randrange(4) for i in range(-3, j + k + 4)}
                    # part 1: C over sigma(2) leftwards, writing sigma(3)
                    tape = dict(base)
                    for x in block:
                        tape[x] = s[2]
                    want = dict(tape)
                    for x in block:
                        want[x] = s[3]
                    r = run_steps(mach, C, bitpos(j), tape, k)
                    ok &= r is not None and r[0] == C and r[1] == bitpos(j + k) and clean(r[2]) == clean(want)
                    # part 2: C over sigma(3) rightwards, writing sigma(1)
                    tape = dict(base)
                    for x in block:
                        tape[x] = s[3]
                    want = dict(tape)
                    for x in block:
                        want[x] = s[1]
                    r = run_steps(mach, C, bitpos(j + k - 1), tape, k)
                    ok &= r is not None and r[0] == C and r[1] == bitpos(j - 1) and clean(r[2]) == clean(want)
                    # part 3: A over sigma(2) leftwards, tape unchanged
                    tape = dict(base)
                    for x in block:
                        tape[x] = s[2]
                    want = dict(tape)
                    r = run_steps(mach, A, bitpos(j), tape, k)
                    ok &= r is not None and r[0] == A and r[1] == bitpos(j + k) and clean(r[2]) == clean(want)
                    n += 3
    report('L2.1 sweeps (parts 1, 2, 3), both machines, j <= 6, k <= 9, random other cells', ok, f'{n} runs')


def check_add(maxL: int = 11) -> None:
    """Lemma 2.2 (a) and (b), and the #8 step count of Lemma 2.8, every L <= maxL, every j <= L, every V."""
    ok = True
    n = 0
    bad = ''
    for mach in (7, 8):
        for L in range(1, maxL + 1):
            for j in range(0, L + 1):
                for V in range(1 << L):
                    W = V + (1 << j)
                    if W < (1 << L):
                        qb = j
                        while (V >> qb) & 1:
                            qb += 1
                        steps, Lstar = 2 * (qb - j) + 1, L
                    else:
                        steps, Lstar = 2 * (L - j) + (3 if mach == 7 else 5), L + 2
                    r = run_steps(mach, C, bitpos(j), omega(mach, L, V), steps)
                    good = r is not None and r[0] == C and r[1] == bitpos(j - 1) and \
                        clean(r[2]) == omega(mach, Lstar, W)
                    if not good and ok:
                        bad = f'mach {mach} L {L} j {j} V {V}'
                    ok &= good
                    n += 1
    report(f'L2.2 adding 2^j: (a) same length, (b) two new cells, exact step counts, both machines, L <= {maxL}',
           ok, f'{n} runs {bad}')


def check_add_down(maxL: int = 10) -> None:
    """Lemma 2.3, every L <= maxL, every j in -1..L, every V < 2^L."""
    ok = True
    n = 0
    for mach in (7, 8):
        for L in range(1, maxL + 1):
            for j in range(-1, L + 1):
                for V in range(1 << L):
                    Vs = V + (1 << (j + 1)) - 1
                    Ls = L if Vs < (1 << L) else L + 2
                    r = run_to_bounce(mach, C, bitpos(j), omega(mach, L, V), min_steps=0)
                    ok &= r[0] == 'bounce' and decode(mach, r[1]) == (Ls, Vs) and Vs < (1 << Ls)
                    n += 1
    report(f'L2.3 adding 2^(j+1)-1 down to the right end reaches K(L*, V*), both machines, L <= {maxL}', ok, f'{n} runs')


def check_bounce(maxL: int = 14) -> None:
    """Theorem 2.4 on every K(L, V), L <= maxL, both machines."""
    ok = True
    n = 0
    for mach in (7, 8):
        s = SIG[mach]
        for L in range(1, maxL + 1):
            for V in range(1 << L):
                y = V + 1
                r = run_to_bounce(mach, C, 0, omega(mach, L, V))
                if y == 1 << L:
                    ok &= r[0] == 'halt' and r[1] == B and r[2] == s[2] and r[4] == L + 2
                else:
                    Lp = L if h(y) <= (1 << L) else L + 2
                    ok &= r[0] == 'bounce' and decode(mach, r[1]) == (Lp, h(y) - 1) and h(y) <= (1 << Lp)
                n += 1
    report(f'T2.4 bounce: K(L, y-1) -> K(L\', h(y)-1), and y = 2^L halts after L+2 steps, both machines, L <= {maxL}',
           ok, f'{n} configurations')
    # negative control: a wrong rule must be rejected somewhere
    caught = False
    for L in range(2, 6):
        for V in range((1 << L) - 1):
            y = V + 1
            r = run_to_bounce(7, C, 0, omega(7, L, V))
            wrong = y - 1 + (1 << (nu(y) + 1))
            if r[0] == 'bounce' and decode(7, r[1])[1] != wrong - 1:
                caught = True
    report('NEG  negative control: the comparison rejects the wrong rule y - 1 + 2^(nu(y)+1)', caught)


def check_direct_run(maxL: int = 24) -> None:
    """Theorem 2.6: both machines from the blank tape, every bounce up to the first bounce of word length maxL,
    compared with the orbit y_0 = 2, y_(i+1) = h(y_i) and the word lengths L_i of Definition 2.6."""
    for mach in (7, 8):
        s = SIG[mach]
        T = TM[mach]
        inv = {s[2]: 1, s[1]: 0}
        N, off = 80, 60                      # array index = position + off
        tape = [0] * N
        q, x = A, -2
        L, y = 2, 2
        bounces = steps = 0
        ok = True
        while True:
            t = T.get((q, tape[x + off]))
            if t is None or x > 0:
                ok = False
                break
            w, d, q = t
            tape[x + off] = w
            x += d
            steps += 1
            if q == C and x == 0:
                good = all(tape[i] == 0 for i in range(off, N)) and all(tape[i] == 0 for i in range(0, off - L))
                V = 0
                for i in range(L):
                    v = tape[off - 1 - i]
                    if v not in inv:
                        good = False
                        break
                    V |= inv[v] << i
                if not (good and V == y - 1 and y <= (1 << L) and L % 2 == 0):
                    ok = False
                    break
                bounces += 1
                if L >= maxL or y == 1 << L:
                    break
                y2 = h(y)
                L = L if y2 <= (1 << L) else L + 2
                y = y2
        report(f'T2.6 direct run of #{mach} from the blank tape: bounce i is K(L_i, y_i - 1)', ok,
               f'{bounces} bounces, {steps} steps, to the first bounce of word length {maxL}')


# =====================================================================================================
# Section 3 checks (the orbit of 2)
# =====================================================================================================
def check_h_facts() -> None:
    ok = True
    for y in range(1, 1 << 18):
        ok &= h(y) >= y + 3 and h(2 * y) == 2 * h(y) + 1
        if y & 1:
            ok &= h(y) == y + 3
    report('L3.1 h(y) >= y+3, h(y) = y+3 for odd y, h(2y) = 2h(y)+1', ok, 'all y < 2^18')
    # [F4] the first two steps of the orbit of 2
    report('F4   h(2) = 9, h(9) = 12 = 3*2^2', h(2) == 9 and h(9) == 12 == 3 * 4)


def check_selfsim() -> None:
    rng = random.Random(9)
    cases = [(m, Q) for m in range(0, 13) for Q in range(1, 101)]
    cases += [(m, rng.randrange(1, 1 << 20)) for m in range(0, 15) for _ in range(5)]
    ok = True
    for m, Q in cases:
        y = Q << m
        target = (h(Q) + 2 * m) << m
        y = h(y)
        while y < target:
            if y % (1 << m) == 0:
                ok = False
                break
            y = h(y)
        ok &= y == target
    report('P3.2 orbit of Q*2^m reaches (h(Q)+2m)*2^m, no multiple of 2^m strictly between', ok,
           f'{len(cases)} cases, m <= 14')


def check_ladder(limit_bits: int = 26) -> None:
    """Theorem 3.3 (slow zeros) and Corollary 3.4 along the orbit of 2, directly, up to 2^limit_bits."""
    first = {}                     # m -> first value on the orbit of 2 divisible by 2^m
    pow2_seen = []
    y = 2
    n = 0
    lchar = True
    L = 2
    while y < (1 << limit_bits):
        for m in range(2, nu(y) + 1):
            first.setdefault(m, y)
        if y & (y - 1) == 0:
            pow2_seen.append(y)
        # Theorem 2.6 claim: 2^(L-2) < y <= 2^L, so L_i is the least even L with 2^L >= y_i
        lmin = 2
        while (1 << lmin) < y:
            lmin += 2
        lchar &= lmin == L and (1 << (L - 2)) < y <= (1 << L)
        y2 = h(y)
        L = L if y2 <= (1 << L) else L + 2
        y = y2
        n += 1
    ms = [m for m in range(2, limit_bits + 1) if ((2 * m - 1) << m) < (1 << limit_bits)]
    ok = all(first.get(m) == (2 * m - 1) << m for m in ms) and \
        all(m in ms for m in first)
    report('T3.3 slow zeros: the first value on the orbit of 2 divisible by 2^m is (2m-1)*2^m', ok,
           f'm = 2..{max(ms)}, {n} orbit values below 2^{limit_bits}')
    report('C3.4 the only power of 2 on the orbit of 2 is 2 (so no power of 4)', pow2_seen == [2], f'below 2^{limit_bits}')
    report('T2.6 bound 2^(L_i-2) < y_i <= 2^(L_i) along the orbit (L_i is the least even L with 2^L >= y_i)', lchar,
           f'{n} orbit values')


def check_mirrors(steps: int = 20000) -> None:
    """[F5] Corollary 5.2: the mirror machines. Transition correspondence, then the two runs side by side."""
    pairs = [(7, '0RB2LA3RA1LA_1LC1RA2RB---_2LA---------'), (8, '0RB2LA3LA1RA_1LC---2RA3RB_2RA---------')]
    pi = {A: B, B: C, C: A}
    for mach, text in pairs:
        T, M = TM[mach], parse(text)
        ok = all(M.get((pi[q], a)) == ((T[(q, a)][0], -T[(q, a)][1], pi[T[(q, a)][2]]) if (q, a) in T else None)
                 for q in (A, B, C) for a in range(4))
        t1, x1, q1 = {}, 0, A                     # the machine from (A, 0, blank)
        w, d, q2 = M[(A, 0)]                      # the mirror machine's first step on the blank tape
        t2, x2 = {0: w}, d
        ok &= (q2, x2, clean(t2)) == (B, 1, {})
        for _ in range(steps):
            mirrored = {1 - x: v for x, v in clean(t1).items()}
            if q2 != pi[q1] or x2 != 1 - x1 or clean(t2) != mirrored:
                ok = False
                break
            w, d, q1 = T[(q1, t1.get(x1, 0))]
            t1[x1] = w
            x1 += d
            w, d, q2 = M[(q2, t2.get(x2, 0))]
            t2[x2] = w
            x2 += d
        report(f'F5   mirror of #{mach}: {text} is #{mach} with states A->B, B->C, C->A and moves reversed,'
               f' and after one blank move runs as the mirror image of #{mach}', ok, f'{steps} steps side by side')

def check_also_true() -> None:
    # A1: the U-form counter of the previous version is the same map: U = 2^L - y
    ok = True
    for L in range(1, 15):
        for U in range(1, 1 << L):
            f = U + 1 - (1 << (nu(U) + 2))
            Lu, Uu = (L, f) if f >= 0 else (L + 2, 3 * (1 << L) + f)
            y = (1 << L) - U
            Ly = L if h(y) <= (1 << L) else L + 2
            ok &= (Lu, Uu) == (Ly, (1 << Ly) - h(y))
    report('A1   also true: U = 2^L - y turns h into the U-counter of the previous version', ok, 'L <= 14, all U')
    # A2: the residue cycle at level m (the two paths of the previous version)
    ok = True
    for m in range(2, 13):
        for Q in range(1, 41):
            y = h(Q << m)
            ok &= y == (h(Q) << m) + (1 << m) - 1
            kinds = []
            while y % (1 << m):
                y2 = h(y)
                dq = (y2 >> m) - (y >> m)
                if dq:
                    r = y2 % (1 << m)
                    kinds.append('S' if dq == 2 else ('Z' if r == 0 else 'o'))
                    if dq == 2:
                        ok &= y % (1 << m) == 1 << (m - 1)          # the double carry starts from remainder 2^(m-1)
                    ok &= dq in (1, 2)
                y = y2
            ok &= kinds == ['o'] * (m - 1) + ['S'] + ['o'] * (m - 2) + ['Z']
    report('A2   also true: from a multiple of 2^m, m-1 single carries, one double (from remainder 2^(m-1)),'
           ' m-2 single, one onto 0', ok,
           'm = 2..12, Q <= 40')


def main() -> int:
    print('proof_checks.py: checks for PROOF.md (BBi(8) #7 and #8)', flush=True)
    check_tables()
    check_start()
    check_sweeps()
    check_add(11)
    check_add_down(10)
    check_bounce(14)
    check_direct_run(24)
    check_h_facts()
    check_selfsim()
    check_ladder(26)
    check_mirrors(20000)
    check_also_true()
    print(f'{"ALL PASS" if FAILS == 0 else str(FAILS) + " FAILED"}  total {time.time() - T0:.1f}s', flush=True)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
