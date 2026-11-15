# BBi(8) holdouts #7 and #8 never halt

- #7 `1RB1LC2LA---_2RC---------_0LA2RC3LC1RC`
- #8 `1RB---2LC3LA_2LC---------_0LA2RC3RC1LC`

The two machines are lines 8 and 9 of Nick Drozd's BBi(8) holdout list (2026-10-25). Neither halts from the blank
tape. The proof was worked out with Claude, an AI model, and a second Claude agent acting as referee checked this written
proof on 2026-11-14, before Theorem 3.3 was restated around slow zeros with the same engine (Proposition 3.2). The result is also formalised in Rocq, in the folder `coq/`. It builds with
Coq 8.20.1 on top of busycoq (ccz181078/busycoq, branch BB6, commit 4ea6784) plus two framework files for 3-state
4-symbol machines, and `Print Assumptions` reports "Closed under the global context" for both `nonhalt` theorems.
`proof_checks.py` checks every finite fact below and tests every statement on small cases.

## Overview

**1. The tape is a number, and each bounce is one rule.** At each bounce off the right end of the tape, read the word
between the blank cells as a binary number with 2 as the digit one and 1 as the digit zero, and add 1. Call the result
y. Each bounce does

  y → h(y) = y − 1 + 2^(ν(y)+2),

where ν(y) is the number of trailing zeros of y in binary. When y outgrows the word, the word gains two cells and the
same rule goes on. The machine starts at y = 2.

**2. Halting needs y to be a 1 followed by zeros.** The machine halts only on the all-2 word. There y = 2^L, a 1
followed by L zeros, where L is the word length. L is always even, so that y would be a power of 4.

**3. The rule makes trailing zeros too slowly.** For every m ≥ 2, the first value on the orbit of 2 that is divisible
by 2^m is (2m − 1)·2^m, which is 2m − 1 times too big to be 2^m. Every later multiple of 2^m is bigger still. So no
value on the orbit except 2 itself is a power of 2, and the machine never halts.

| m | halting value 2^m | first orbit value divisible by 2^m | ratio 2m − 1 |
|---|---:|---:|---:|
| 2 | 4 | 12 | 3 |
| 3 | 8 | 40 | 5 |
| 4 | 16 | 112 | 7 |
| 5 | 32 | 288 | 9 |
| 6 | 64 | 704 | 11 |

**Why the zeros come slowly.** From a multiple Q·2^m the orbit's next multiple of 2^m is (h(Q) + 2m)·2^m. This
self-similarity is an induction on m, because one step at level m+1 is two steps at level m. It rests on the identities
h(2Q) = 2h(Q) + 1 and h(Q) = Q + 3 for odd Q. Write x_m = (2m − 1)·2^m. Since 2m − 1 is odd, x_m is not divisible by
2^(m+1), and its next multiple of 2^m is (2m + 2 + 2m)·2^m = (2m + 1)·2^(m+1) = x_(m+1). So the first multiple of
2^(m+1) on the orbit is x_(m+1), and the table continues forever.

The figure shows the start of the orbit, with the word length L and the old counter U = 2^L − y.

```
y        2 |    9   12 |   27   30   37   40 |   71   74   81   84   99  102  109  112   ...
L        2 |    4    4 |    6    6    6    6 |    8    8    8    8    8    8    8    8   ...
U        2 |    7    4 |   37   34   27   24 |  185  182  175  172  157  154  147  144   ...
first      |       x_2 |                 x_3 |                                     x_4
```

The bars separate word lengths. x_2 = 12, x_3 = 40 and x_4 = 112 are the first values divisible by 4, 8 and 16. The
powers of 4 that a halt would need at the first three word lengths are 4, 16 and 64, and the orbit passes them by.
From 40 = 5·2^3 the next multiple of 8 is (h(5) + 6)·8 = (8 + 6)·8 = 112, as the self-similarity says.

## 1. Conventions

**Definition 1.1** (the machines). Symbols are 0, 1, 2, 3, and 0 is the blank. States are A, B, C. A transition `xDY`
writes x, moves in direction D (L or R) and enters state Y. "C2" names the transition of state C reading 2.

| | read 0 | read 1 | read 2 | read 3 |
|---|---|---|---|---|
| #7, A | 1RB | 1LC | 2LA | undefined |
| #7, B | 2RC | undefined | undefined | undefined |
| #7, C | 0LA | 2RC | 3LC | 1RC |
| #8, A | 1RB | undefined | 2LC | 3LA |
| #8, B | 2LC | undefined | undefined | undefined |
| #8, C | 0LA | 2RC | 3RC | 1LC |

**Definition 1.2** (runs). Cells are indexed by the integers, R means +1 and L means −1. A tape τ maps the integers to
symbols with finitely many nonzero values. A configuration (q, x, τ) has a state q, a head position x and a tape τ. If
the transition of q reading τ(x) is `bDY`, one step leads to (Y, x + d, τ') where d is +1 for R and −1 for L and τ' is
τ with τ'(x) = b. If that transition is undefined the configuration is halting. We write c ⊢^n c' for exactly n steps,
c ⊢* c' for some n ≥ 0 and c ⊢+ c' for some n ≥ 1. The machine halts from c if c ⊢* c' for a halting c'. Each
configuration has at most one successor, so the run from c is unique. The start is (A, −2, 0), state A at position −2
on the blank tape. Translating a run gives a run, so the starting position is a free choice.

**Definition 1.3** (bits and words). For i ≥ −1, *bit i* is the cell at position pos(i) = −1 − i. So bit 0 is
position −1, bit −1 is position 0, and a left move goes from bit i to bit i+1. Digit i of a number V ≥ 0 is
⌊V/2^i⌋ mod 2. For L ≥ 1 and 0 ≤ V < 2^L the *word* ω(L, V) is the tape whose bit i holds 2 if digit i of V is 1 and
holds 1 if digit i is 0, for 0 ≤ i ≤ L−1, with 0 at every other position. The *bounce configuration* is
K(L, V) = (C, 0, ω(L, V)), with the head on the blank cell just right of the word.

*Example.* Two bounces of #7, computed by direct simulation. Each row shows the word, high bits on the left, and the
blank cell under the head at the right end. The digits are written under the symbols.

```
bit                  5  4  3  2  1  0  head
y = 9,  L = 4              2  1  1  1  0       digits 1 0 0 0, V = 8
y = 12, L = 4              2  1  2  2  0       digits 1 0 1 1, V = 11    (4 steps later)
y = 27, L = 6        1  2  2  1  2  1  0       digits 0 1 1 0 1 0, V = 26    (18 steps later)
```

The first bounce adds 3 = 2^(ν(9)+2) − 1 within the word. In the second, ν(12) = 2, so the machine adds
2^4 − 1 = 15 to V = 11. The addition at bit 3 overflows, the word gains bits 4 and 5 (digits 1 and 0), and the sum
26 fits in length 6. For #8 every symbol is relabelled by σ (Definition 1.5), so the three rows read 3222, 3233 and
233232.

**Definition 1.4** (the map h). For an integer y ≥ 1, ν(y) is the exponent of the largest power of 2 dividing y, and
h(y) = y − 1 + 2^(ν(y)+2). The *orbit* of y is the sequence y, h(y), h(h(y)), …, written h^k(y) for k ≥ 0. A number is
*on the orbit* if it equals some h^k(y).

**Definition 1.5** (relabelling). σ maps symbols by σ(0) = 0, σ(1) = 2, σ(2) = 3, σ(3) = 1. For a tape τ, στ is the
tape x ↦ σ(τ(x)). For #8 the bounce configuration is Kσ(L, V) = (C, 0, σω(L, V)).

## 2. From the tape to the map h

Lemmas 2.1 to 2.6 are about #7. Lemma 2.8 and Theorem 2.9 carry them to #8.

**Lemma 2.1** (sweeps). Let τ be a tape, j ≥ 0 and k ≥ 0. Call bits j to j+k−1 the block.

1. If the block holds 2, then (C, pos(j), τ) ⊢^k (C, pos(j+k), τ1), where τ1 is τ with the block set to 3.
2. If the block holds 3, then (C, pos(j+k−1), τ) ⊢^k (C, pos(j−1), τ2), where τ2 is τ with the block set to 1.
3. If the block holds 2, then (A, pos(j), τ) ⊢^k (A, pos(j+k), τ).

*Proof.* Each part is an induction on k, for all j and τ. For k = 0 each configuration reaches itself in 0 steps.

Part 1, from k to k+1. The block j to j+k−1 holds 2, so after k steps the configuration is (C, pos(j+k), τ1) with
τ1(bit j+k) = τ(bit j+k) = 2. C2 is `3LC`. It writes 3 on bit j+k and moves left to bit j+k+1 in state C.

Part 2, from k to k+1. The block is bits j to j+k, and the head starts on bit j+k, which holds 3. C3 is `1RC`. It
writes 1 there and moves right to bit j+k−1 in state C. Bits j to j+k−1 still hold 3, and the case k for that block
gives k more steps that set them to 1 and end on bit j−1.

Part 3, from k to k+1. After k steps the configuration is (A, pos(j+k), τ), and bit j+k holds 2. A2 is `2LA`. It writes
2 over 2 and moves left to bit j+k+1 in state A. ∎

**Lemma 2.2** (adding 2^j). Let L ≥ 1, 0 ≤ j ≤ L and 0 ≤ V < 2^L.

- (a) If V + 2^j < 2^L, let q be the least i ≥ j with digit i of V equal to 0. Then
  (C, pos(j), ω(L, V)) ⊢^(2(q−j)+1) (C, pos(j−1), ω(L, V + 2^j)).
- (b) If V + 2^j ≥ 2^L, then (C, pos(j), ω(L, V)) ⊢^(2(L−j)+3) (C, pos(j−1), ω(L+2, V + 2^j)).

In words, the head on bit j in state C adds 2^j to the word and moves one cell right. If the sum does not fit, the
word gains two cells on the left.

*Proof.* Digits j to L−1 of V are all 1 exactly when ⌊V/2^j⌋ = 2^(L−j) − 1, that is when V ≥ 2^L − 2^j. So case (a)
is the case where one of these digits is 0, and case (b) the case where all are 1.

(a) Here q exists and j ≤ q ≤ L−1. Digits j to q−1 are 1, so bits j to q−1 hold 2, and bit q holds 1. Lemma 2.1 part 1
with k = q−j gives (C, pos(q)) after q−j steps, with bits j to q−1 holding 3. C1 is `2RC`. It writes 2 on bit q and
moves to bit q−1 in state C. Lemma 2.1 part 2 on bits j to q−1 gives q−j more steps that set them to 1 and end on bit
j−1. As digits, j to q−1 went from 1 to 0 and q went from 0 to 1, so the value grew by 2^q − (2^q − 2^j) = 2^j. No
other cell changed. The tape is ω(L, V + 2^j), which is a word because V + 2^j < 2^L.

(b) Bits j to L−1 hold 2. Lemma 2.1 part 1 with k = L−j gives (C, pos(L)) after L−j steps, with those bits holding 3.
Bit L holds 0. C0 is `0LA`. It writes 0 and moves to bit L+1 in state A. Bit L+1 holds 0. A0 is `1RB`. It writes 1 on
bit L+1 and moves to bit L in state B. Bit L holds 0. B0 is `2RC`. It writes 2 on bit L and moves to bit L−1 in state
C. Lemma 2.1 part 2 on bits j to L−1 gives L−j more steps that set them to 1 and end on bit j−1. Now bits below j are
unchanged, bits j to L−1 hold 1 (digit 0), bit L holds 2 (digit 1), bit L+1 holds 1 (digit 0), and every other cell
holds 0. That is the word of length L+2 with value V − (2^L − 2^j) + 2^L = V + 2^j, which is less than 2^(L+1). The
step count is (L−j) + 3 + (L−j). ∎

When j = L only case (b) occurs, and both sweeps are empty.

**Lemma 2.3** (adding 2^(j+1) − 1). Let L ≥ 1, −1 ≤ j ≤ L and 0 ≤ V < 2^L. Put V* = V + 2^(j+1) − 1, and let L* = L
if V* < 2^L and L* = L+2 otherwise. Then V* < 2^(L*) and (C, pos(j), ω(L, V)) ⊢* K(L*, V*).

*Proof.* Induction on j, from j = −1. The induction hypothesis for j−1 is the statement for every L and V.

Case j = −1. Then V* = V, L* = L and pos(−1) = 0, so the configuration is K(L, V) itself.

Case j ≥ 0. Lemma 2.2 gives (C, pos(j−1), ω(L1, V + 2^j)), where L1 = L if V + 2^j < 2^L and L1 = L+2 otherwise, and
V + 2^j < 2^(L1). Since −1 ≤ j−1 ≤ L1, the induction hypothesis for j−1, L1 and V + 2^j gives K(L**, V*) with
V* = (V + 2^j) + 2^j − 1 < 2^(L**), where L** = L1 if V* < 2^(L1) and L** = L1 + 2 otherwise. It remains to see
L** = L*.
- If L1 = L, the definitions of L** and L* agree.
- If L1 = L+2, then V + 2^j ≥ 2^L, so V* ≥ 2^L and L* = L+2. Also V* < 2^L + 2^(j+1) ≤ 2^L + 2^(L+1) < 2^(L+2), so
  L** = L1 = L+2. ∎

**Theorem 2.4** (the bounce). Let L ≥ 1 and 1 ≤ y ≤ 2^L.

- (i) If y = 2^L, then #7 halts from K(L, y−1) after L+2 steps, in state B reading 2.
- (ii) If y < 2^L, then K(L, y−1) ⊢+ K(L', h(y) − 1), where L' = L if h(y) ≤ 2^L and L' = L+2 otherwise. Moreover
  h(y) ≤ 2^(L').

*Proof.* Let V = y − 1 and n = ν(y). Then y − 2^n is a multiple of 2^(n+1), and V = (y − 2^n) + (2^n − 1). So digits
0 to n−1 of V are 1, and digit n of V is 0 when n ≤ L−1. In K(L, V) the head is on position 0, which holds 0. C0 is
`0LA`. It writes 0 and moves to bit 0 in state A.

(i) Here V = 2^L − 1 and all L bits hold 2. Lemma 2.1 part 3 with k = L gives (A, pos(L)) after L more steps. Bit L
holds 0. A0 is `1RB`. It writes 1 there and moves to bit L−1 in state B. Bit L−1 holds 2 and B2 is undefined. That is
1 + L + 1 steps.

(ii) Here n ≤ L−1 because 2^n ≤ y < 2^L. Lemma 2.1 part 3 with k = n gives (A, pos(n)) after n more steps, and bit n
holds 1. A1 is `1LC`. It writes 1 over 1 and moves to bit n+1 in state C. The tape is still ω(L, V) and n+2 ≥ 2 steps
have passed. Lemma 2.3 with j = n+1 ≤ L gives K(L*, V + 2^(n+2) − 1). Now V + 2^(n+2) − 1 = h(y) − 1, and
h(y) − 1 < 2^L exactly when h(y) ≤ 2^L, so L* = L' and h(y) − 1 < 2^(L'). ∎

**Lemma 2.5** (the start). (A, −2, 0) ⊢^2 K(2, 1).

*Proof.* A0 is `1RB`. It writes 1 at position −2 and moves to −1 in state B. B0 is `2RC`. It writes 2 at −1 and moves
to 0 in state C. Bit 1 (position −2) holds 1 and bit 0 (position −1) holds 2, which is ω(2, 1). ∎

**Theorem 2.6** (#7 follows the orbit of 2). Let y_0 = 2 and y_(i+1) = h(y_i). Let L_0 = 2, and L_(i+1) = L_i if
y_(i+1) ≤ 2^(L_i) and L_(i+1) = L_i + 2 otherwise. Then #7 halts from the start if and only if the orbit of 2
contains a power of 4.

*Proof.* Claim. For every i such that y_k ≠ 2^(L_k) for all k < i, the start reaches K(L_i, y_i − 1) in at least i
steps, L_i is even, and 2^(L_i − 2) < y_i ≤ 2^(L_i). Induction on i. The base is Lemma 2.5, with 1 < 2 ≤ 4. For the
step, y_i < 2^(L_i), and Theorem 2.4(ii) gives K(L_(i+1), y_(i+1) − 1) with y_(i+1) ≤ 2^(L_(i+1)). L_(i+1) is even.
For the lower bound, if L_(i+1) = L_i then y_(i+1) = h(y_i) > y_i > 2^(L_i − 2) by Lemma 3.1(a), and if
L_(i+1) = L_i + 2 then y_(i+1) > 2^(L_i) = 2^(L_(i+1) − 2) by the definition of L_(i+1).

Only if. If no y_i equals 2^(L_i), the claim holds for every i, so the run from the start has configurations after
arbitrarily many steps. A halting run is finite, and the run is unique, so #7 does not halt. So if #7 halts, some
y_i = 2^(L_i), and since L_i is even, 2^(L_i) = 4^(L_i/2) is a power of 4.

If. Let i be the least index with y_i a power of 4, say y_i = 4^k. For k' < i, y_k' is not a power of 4, so it is not
2^(L_k') either, and the claim holds for i. So 2^(L_i − 2) < 2^(2k) ≤ 2^(L_i) with L_i even, which forces 2k = L_i
and y_i = 2^(L_i). The run reaches K(L_i, 2^(L_i) − 1) and halts there by Theorem 2.4(i). ∎

Only the "only if" direction is needed for Theorems 4.1 and 4.2. The claim also shows that L_i is the least even L
with 2^L ≥ y_i.

**Lemma 2.7** (the correspondence for #8). For each of the transitions A1, A2, C0, C1, C2, C3 of #7, say state s
reading a writes b, moves d and enters s', machine #8 in state s reading σ(a) writes σ(b), moves d and enters s'.
Explicitly, #7 A1 `1LC` matches #8 A2 `2LC`, #7 A2 `2LA` matches #8 A3 `3LA`, #7 C0 `0LA` matches #8 C0 `0LA`, #7 C1
`2RC` matches #8 C2 `3RC`, #7 C2 `3LC` matches #8 C3 `1LC`, and #7 C3 `1RC` matches #8 C1 `2RC`. The undefined entries
match as well. #7 A3, B1, B2, B3 are undefined, and so are #8 A1, B2, B3, B1, the entries at σ(3), σ(1), σ(2), σ(3).
The remaining two transitions differ. #8 A0 is `1RB`, which does not write σ(1) = 2, and #8 B0 is `2LC`, which moves
left. (Finite fact F2.)

By induction on the number of steps, a stretch of a #7 run that uses only A1, A2, C0, C1, C2, C3 becomes a stretch of a
#8 run of the same length, with the same states and head positions, when σ is applied to every tape.

**Lemma 2.8** (the #8 versions). In the statements of Lemmas 2.1, 2.2, 2.5 and Theorem 2.4(i), replace every tape τ by
στ, every symbol x named in a hypothesis or conclusion by σ(x), and K by Kσ. Then

- Lemma 2.1 and Lemma 2.2(a) hold for #8 with the same step counts.
- Lemma 2.2(b) holds for #8 with 2(L−j)+5 steps in place of 2(L−j)+3.
- Theorem 2.4(i) holds for #8 in the form "#8 halts from Kσ(L, 2^L − 1) after L+2 steps, in state B reading 3".
- (A, −2, 0) ⊢^4 Kσ(2, 1) for #8.

*Proof.* Lemma 2.1 part 1 uses only C2, part 2 only C3, part 3 only A2. Lemma 2.2(a) uses parts 1 and 2 and C1. These
are among the six transitions of Lemma 2.7, so these statements carry over with the same step counts.

Lemma 2.2(b) for #8. Bits j to L−1 hold σ(2) = 3. Part 1 for #8 (through #8 C3 `1LC`) gives state C on bit L after L−j
steps, with those bits holding σ(3) = 1. Bit L holds 0. #8 C0 `0LA` writes 0 and moves to bit L+1 in state A. Bit L+1
holds 0. #8 A0 `1RB` writes 1 there and moves to bit L in state B. Bit L holds 0. #8 B0 `2LC` writes 2 there and moves
left to bit L+1 in state C. Bit L+1 holds 1. #8 C1 `2RC` writes 2 there and moves to bit L in state C. Bit L holds 2.
#8 C2 `3RC` writes 3 there and moves to bit L−1 in state C. Now bit L+1 holds 2 = σ(1) and bit L holds 3 = σ(2), as in
#7 under σ, after 5 steps in place of 3. Part 2 for #8 (through #8 C1 `2RC`) then sets bits j to L−1 to σ(1) = 2 in
L−j steps and ends on bit j−1.

Theorem 2.4(i) for #8. #8 C0 `0LA` moves to bit 0 in state A. All L bits hold σ(2) = 3, and part 3 for #8 (through #8
A3 `3LA`) brings the head to bit L in state A after L more steps. Bit L holds 0. #8 A0 `1RB` writes 1 there and moves to
bit L−1 in state B. Bit L−1 holds 3 and #8 B3 is undefined. That is L+2 steps.

The start for #8. At position −2, #8 A0 `1RB` writes 1 and moves to −1 in state B. Position −1 holds 0, and #8 B0 `2LC`
writes 2 and moves to −2 in state C. Position −2 holds 1, and #8 C1 `2RC` writes 2 and moves to −1 in state C. Position
−1 holds 2, and #8 C2 `3RC` writes 3 and moves to 0 in state C. Bit 1 holds 2 = σ(1) and bit 0 holds 3 = σ(2), so this
is Kσ(2, 1), after 4 steps. ∎

**Theorem 2.9** (#8 follows the same orbit). Lemma 2.3 and Theorems 2.4 and 2.6 hold for #8, with Kσ in place of K and
the #8 start of Lemma 2.8 in place of Lemma 2.5. In particular, #8 halts from the start if and only if the orbit of 2
contains a power of 4.

*Proof.* Transfer the three proofs in order, replacing each cited lemma by its #8 version and each tape by its image
under σ. The proof of Lemma 2.3 uses only Lemma 2.2 (Lemma 2.8 for #8). The proof of Theorem 2.4(ii) uses Lemma 2.1
part 3, Lemma 2.3 (just transferred), arithmetic on V and y, and the transitions C0 and A1 of #7 (for #8, C0 and A2,
by Lemma 2.7). The proof of Theorem 2.6 uses Lemma 2.5, Theorem 2.4 (part (i) from Lemma 2.8, part (ii) just
transferred) and the arithmetic Lemma 3.1. The statements of Lemma 2.3, Theorem 2.4(ii) and
Theorem 2.6 mention only ⊢*, ⊢+ and the existence of a halting run, so the changed step counts do not matter. ∎

## 3. The orbit of 2

**Lemma 3.1** (three facts about h). For every y ≥ 1,

- (a) h(y) ≥ y + 3, so every orbit is strictly increasing,
- (b) h(y) = y + 3 if y is odd,
- (c) h(2y) = 2h(y) + 1.

*Proof.* (a) 2^(ν(y)+2) ≥ 4. (b) ν(y) = 0. (c) ν(2y) = ν(y) + 1, so
h(2y) = 2y − 1 + 2^(ν(y)+3) = 2(y − 1 + 2^(ν(y)+2)) + 1. ∎

By (a), if z is on the orbit of y, then the orbit of z consists of exactly the numbers on the orbit of y that are at
least z.

**Proposition 3.2** (self-similarity). For every m ≥ 0 and Q ≥ 1, the orbit of Q·2^m contains (h(Q) + 2m)·2^m, and no
number on that orbit strictly between Q·2^m and (h(Q) + 2m)·2^m is divisible by 2^m.

*Proof.* Induction on m. The induction hypothesis for m is the statement for m and every Q ≥ 1.

Base m = 0. The orbit of Q contains h(Q). By Lemma 3.1(a) no number on it lies strictly between Q and h(Q).

Step from m to m+1. Let Q ≥ 1 and y0 = Q·2^(m+1) = (2Q)·2^m. The hypothesis for 2Q, with h(2Q) = 2h(Q) + 1 from Lemma
3.1(c), says that the orbit of y0 contains y1 = (2h(Q) + 1 + 2m)·2^m, with no multiple of 2^m on the orbit strictly
between y0 and y1. Put Q1 = 2h(Q) + 2m + 1. It is odd, so h(Q1) = Q1 + 3 by Lemma 3.1(b). The hypothesis for Q1 says
that the orbit of y1 contains y2 = (Q1 + 3 + 2m)·2^m = (2h(Q) + 4m + 4)·2^m = (h(Q) + 2(m+1))·2^(m+1), with no multiple
of 2^m on it strictly between y1 and y2. The orbit of y1 is part of the orbit of y0, so the orbit of y0 contains y2.

Let z be on the orbit of y0 with y0 < z < y2, and suppose 2^(m+1) divides z. Then 2^m divides z. If z < y1, this
contradicts the first application. If z = y1, it contradicts the oddness of Q1. If z > y1, then z is on the orbit of
y1, which contradicts the second application. ∎

**Theorem 3.3** (slow zeros). For every m ≥ 2, the first number on the orbit of 2 that is divisible by 2^m is
x_m = (2m − 1)·2^m. So every number on the orbit of 2 that is divisible by 2^m is at least x_m.

*Proof.* Induction on m. Base m = 2. The orbit begins 2, 9, 12 (finite fact F4). Neither 2 nor 9 is divisible by 4,
and 12 = x_2.

Step from m to m+1. By the induction hypothesis x_m is on the orbit of 2, and every number on it divisible by 2^m, and
so every number divisible by 2^(m+1), is at least x_m. The number x_m itself is not divisible by 2^(m+1), because 2m − 1
is odd. Apply Proposition 3.2 with Q = 2m − 1. It is odd, so h(Q) = 2m + 2 by Lemma 3.1(b). The orbit of x_m, which is
the part of the orbit of 2 from x_m on, contains (2m + 2 + 2m)·2^m = (2m + 1)·2^(m+1) = x_(m+1), and no number on it
strictly between x_m and x_(m+1) is divisible by 2^m, let alone by 2^(m+1). Since x_(m+1) is divisible by 2^(m+1), it
is the first such number on the orbit of 2. ∎

**Corollary 3.4** (no powers of 2). The only power of 2 on the orbit of 2 is 2 itself. In particular the orbit of 2
contains no power of 4.

*Proof.* The orbit starts at 2 and increases (Lemma 3.1(a)), so 1 is not on it. If 2^m were on it with m ≥ 2, then 2^m
would be divisible by 2^m, and Theorem 3.3 would give 2^m ≥ (2m − 1)·2^m ≥ 3·2^m, which is false. The powers of 4 are 1
and 2^(2k) with 2k ≥ 2. ∎

## 4. The main theorems

**Theorem 4.1.** #7 does not halt from the blank tape.

*Proof.* If it halted, Theorem 2.6 would put a power of 4 on the orbit of 2, against Corollary 3.4. ∎

**Theorem 4.2.** #8 does not halt from the blank tape.

*Proof.* If it halted, Theorem 2.9 would put a power of 4 on the orbit of 2, against Corollary 3.4. ∎

## 5. Consequences

**Corollary 5.1** (filling in the undefined cells). Let M be a machine obtained from #7 by defining any of its
undefined entries A3, B1, B2, B3, each with any symbol, direction and state among A, B, C. Then M does not halt from the
blank tape. The same holds for #8 and its undefined entries A1, B1, B2, B3.

*Proof.* By Theorem 4.1 no configuration of the run of #7 from the start is halting, so at each of them #7 uses a
defined entry. M has the same entry there. By induction on the number of steps, the run of M from the start is the run
of #7, and none of its configurations is halting for M. The same argument with Theorem 4.2 covers #8. ∎

**Corollary 5.2** (two mirror images). Let

- #7' = `0RB2LA3RA1LA_1LC1RA2RB---_2LA---------`
- #8' = `0RB2LA3LA1RA_1LC---2RA3RB_2RA---------`

and let π rename the states A → B, B → C, C → A. Whenever #7 in state q reading a writes b, moves d and enters q', the
machine #7' in state π(q) reading a writes b, moves −d and enters π(q'), and #7' is undefined at (π(q), a) exactly where
#7 is undefined at (q, a). The same holds for #8 and #8' (finite fact F5). Neither #7' nor #8' halts from the blank tape.

*Proof.* Let Φ(q, x, τ) = (π(q), 1 − x, τ') with τ'(x) = τ(1 − x), the mirror image in the point 1/2 with the states
renamed. If (q, x, τ) ⊢ (q', x + d, τ'') in #7, then #7' in Φ(q, x, τ) reads τ(x), writes the same symbol at 1 − x,
moves to 1 − x − d = 1 − (x + d) and enters π(q'), which is Φ(q', x + d, τ''). A configuration of #7 is halting exactly
when its Φ-image is halting for #7'. The first step of #7' from (A, 0, 0) is its entry A0 = `0RB`, the image of #7 C0
`0LA`, which leads to (B, 1, 0) = Φ(A, 0, 0). From there, by induction on the number of steps, the run of #7' is the
Φ-image of the run of #7 from (A, 0, 0). That run is a translate of the run from the start of Definition 1.2, so it never
halts by Theorem 4.1, and #7' never halts. The same argument with Theorem 4.2 covers #8'. ∎

## Finite facts used

Line numbers refer to `proof_checks.py`.

- **F1.** The transition tables of Definition 1.1 are those of the two machine texts. Lines 66-72.
- **F2.** The correspondence of Lemma 2.7, with its undefined entries and the two exceptions A0 and B0. Lines 73-85.
- **F3.** The start traces of Lemma 2.5 (#7, 2 steps) and Lemma 2.8 (#8, 4 steps). Lines 156-162.
- **F4.** h(2) = 9 and h(9) = 12 = 3·2^2, used in Theorem 3.3. Lines 334-335.
- **F5.** The transition correspondence of Corollary 5.2 for #7' and #8', used only in Section 5. Lines 389-413, which
  also run each pair side by side for 20,000 steps.

Every other step is proved in the text for all values.

The script also tests the statements themselves. It runs both machines through every case of Lemma 2.2 with L ≤ 11,
Lemma 2.3 with L ≤ 10, Theorem 2.4 with L ≤ 14, and the sweeps of Lemma 2.1 with random surrounding cells. It runs both
machines directly from the blank tape for 1.5 million steps and compares each of the 125,952 bounces with K(L_i, y_i − 1).
It checks Lemma 3.1 for y < 2^18, Proposition 3.2 on 1,375 pairs (m, Q) with m ≤ 14, and Theorem 3.3 and Corollary 3.4
along the orbit of 2 up to 2^26 (m = 2 to 20). It also checks the bound 2^(L_i − 2) < y_i ≤ 2^(L_i) of Theorem 2.6
along the orbit and the statements A1 and A2 below, and it contains a negative control. The whole run takes about 3
seconds on one core.

## Also true

These statements are not used above. Proofs of A1 and A2 are in the previous version (commit 194e0dcb), in its own
notation. The script checks both.

- **A1.** In the variable U = 2^L − y of the previous version the bounce reads U → U + 1 − 2^(ν(U)+2) while this is at
  least 0, and otherwise the word grows and U → 3·2^L + U + 1 − 2^(ν(U)+2). Both cases are the single map h.
- **A2.** From a multiple Q·2^m (m ≥ 2) the orbit next visits h(Q)·2^m + 2^m − 1. From there, counting the moments when
  ⌊y/2^m⌋ changes, it makes m−1 carries of one onto a nonzero remainder, one carry of two (from remainder 2^(m−1)),
  m−2 carries of one onto a nonzero remainder, and a final carry of one onto remainder 0. That is the "two paths"
  theorem of the previous version (the S path and the Z path), and Proposition 3.2 is its total count,
  (m+1) + (m−1) = 2m.
- The previous version also describes each era by level tables and shows that at each word length exactly one era
  start halts. These are statements about other starting values, not about the orbit of 2.

## Notes on this version

- The tape layer reads the word as V with 2 as the digit one, where the previous version used U = 2^L − 1 − V. With
  this reading the decrement lemma becomes an addition (Lemma 2.2), and the left exit is the same addition with two new
  cells. So the exit no longer needs its own formula.
- The counter variable y = V + 1 obeys one map h with no eras. The level tables, the ids a_t and b_t, the defects c(·),
  the map R and the terminals Z and S of the previous version are gone. Their content is Proposition 3.2, whose proof is
  four sentences long.
- Theorem 3.3 states the slow-zeros fact directly. An earlier wording placed the orbit on rungs x_m and argued that
  each power of 4 falls strictly between two rungs. The corollary that follows from slow zeros needs no case analysis.
- The bare inequality y ≥ (2ν(y) − 1)·2^ν(y) is not preserved by h on its own (13 → 16), so slow zeros needs a fact
  about the orbit and cannot come from a one-step invariant of y alone. Proposition 3.2 supplies that fact.

## Appendix. The Rocq formalisation

The files are in `coq/` (see its README). `BBi8_3x4_Arith.v` holds Section 3 and the invariant, `BBi8_3x4_Tape.v` holds
Section 2 for any machine with three local tape lemmas, `BBi8_3x4_M7.v` and `BBi8_3x4_M8.v` prove those lemmas and the
start for each machine, and `BBi8_3x4.v` states the two theorems. In the tape file the digit symbols are parameters
`d1` and `d0` (2 and 1 for #7, 3 and 2 for #8), so #8 is proved directly and Lemmas 2.7 to 2.9 have no counterpart.
Theorem 2.4(i), the "if" half of Theorem 2.6 and Section 5 are not formalised.

| written statement | Rocq name |
|---|---|
| Definition 1.3, words and K | `tobits`, `word`, `Kw` (Tape) |
| Definition 1.4, ν and h | `nu`, `h` (Arith), orbit membership `reach` |
| Lemma 2.1, sweeps | `sweep_C2`, `sweep_C3`, `sweep_A2` (M7), `sweep_C3`, `sweep_C1`, `sweep_A3` (M8) |
| Lemma 2.2 (a) and (b) | `carry`, `overflow` (each machine file, hypotheses of `Section Bounce`) |
| Lemma 2.3 | `add_one`, `add_down` (Tape) |
| Theorem 2.4(ii) | `sweepA` (each machine file) and `bounce` (Tape) |
| Lemma 2.5 and Lemma 2.8, the starts | `start` (each machine file) |
| Theorem 2.6, only if | `Inv`, `Inv_start`, `Inv_not_full`, `Inv_next` (Arith), `counter_nonhalt` (Tape) |
| Lemma 3.1 | `h_gt`, `h_odd`, `h_double` |
| Proposition 3.2 | `selfsim`, with `gap` for "no multiple strictly between" |
| Theorem 3.3 | `rung`, `rung_step`, `ladder`, `slow_zeros` |
| Corollary 3.4 | `no_pow2`, `no_pow4` |
| Theorems 4.1 and 4.2 | `TM7.nonhalt`, `TM8.nonhalt` (`BBi8_3x4.v`) |

The invariant is `Inv L V := 2 <= L /\ V < 2 ^ L /\ reach 2 (V + 1)`, which carries the range bound.
