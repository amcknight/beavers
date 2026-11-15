# Two BBi(8) holdouts never halt

    1RB1LC2LA---_2RC---------_0LA2RC3LC1RC
    1RB---2LC3LA_2LC---------_0LA2RC3RC1LC

Two 3-state, 4-symbol Turing machines with 8 instructions each, from [Nick Drozd](https://github.com/nickdrozd)'s
list of BBi(8) holdouts of 25 October 2026. BBi(n) is his instruction-limited Busy Beaver, the longest halting run
among machines with n instructions. Neither machine halts from the blank tape. The second is the first with its
symbols relabelled, apart from two transitions.

There is a [visual explainer](https://amcknight.ca/beavers/bbi8/) with every number computed live, a
[written proof](PROOF.md) and a [Coq proof](coq/).

## The idea

1. **The tape is a number.** The machine sweeps over a word of two symbols. At each bounce off the right end, read
   the word in binary and add 1. Call that y. Each bounce takes y to y − 1 + 2<sup>ν(y)+2</sup>, where ν(y) is the
   number of trailing zeros of y. The same rule holds when the word grows.
2. **Halting needs a power of 2.** The machine halts only on a word of all ones, where y = 2<sup>L</sup> for the word
   length L. And 2<sup>m</sup> ends in exactly m zeros.
3. **The rule makes zeros too slowly.** Starting from y = 2, every y that ends in m zeros is at least
   (2m − 1)·2<sup>m</sup>, for m ≥ 2. So y is never a power of 2.

| zeros at the end | halting value | smallest y ending in that many zeros |
|---|---|---|
| 2 | 4 | 12 = 3·4 |
| 3 | 8 | 40 = 5·8 |
| 4 | 16 | 112 = 7·16 |
| 5 | 32 | 288 = 9·32 |

Step 3 holds because the rule looks the same at every scale. From Q·2<sup>m</sup> the next multiple of 2<sup>m</sup>
is always (h(Q) + 2m)·2<sup>m</sup>, where h is the rule. That follows by induction from two identities, h(Q) = Q + 3
for odd Q and h(2Q) = 2h(Q) + 1.

## What is proved

In Coq 8.20.1, on [busycoq](https://github.com/ccz181078/busycoq) (branch `BB6`, commit `4ea6784`), for each machine

    Theorem nonhalt: ~halts tm c0.

`Print Assumptions` reports "Closed under the global context" for both. The statement file also pins all 12 cells of
each transition table by a lemma, so the text parser is not part of what a reader has to trust. The main arithmetic
statement is

    Theorem slow_zeros : forall z m, reach 2 z -> 2 <= m -> z mod 2 ^ m = 0 -> (2 * m - 1) * 2 ^ m <= z.

## Consequences

- A machine that never halts never reads an undefined cell. So every machine made by filling in the empty cells of
  either machine never halts either.
- `0RB2LA3RA1LA_1LC1RA2RB---_2LA---------` and `0RB2LA3LA1RA_1LC---2RA3RB_2RA---------` make one move on the blank
  tape and then run the two machines mirrored and relabelled. So they never halt. The written proof has the details.
- Nick Drozd noted on 24 October 2026 that if `1RB---------_0RC2RB3LB1LB_2LA1RC---3RB` halts, the BBi(8) holdouts
  are the BB(3,3) holdouts plus these two machines. With this proof they are the BB(3,3) holdouts alone, on the same
  condition.

## Files

| file | what |
|---|---|
| [index.html](index.html) | the explainer |
| [PROOF.md](PROOF.md) | the written proof |
| [proof_checks.py](proof_checks.py) | checks every finite fact of the written proof and tests each statement on small cases, with its own simulator (`python proof_checks.py`, a few seconds) |
| [coq/BB34.v](coq/BB34.v), [coq/Individual34.v](coq/Individual34.v) | busycoq instantiated to 3 states and 4 symbols, adapted from its `BB33.v` and `Individual33.v` |
| [coq/BBi8_3x4/BBi8_3x4_Arith.v](coq/BBi8_3x4/BBi8_3x4_Arith.v) | the rule h, self-similarity, slow zeros, no power of 2 on the orbit of 2 |
| [coq/BBi8_3x4/BBi8_3x4_Tape.v](coq/BBi8_3x4/BBi8_3x4_Tape.v) | one bounce of the tape is one step of h, for any machine with three tape lemmas |
| [coq/BBi8_3x4/BBi8_3x4_M7.v](coq/BBi8_3x4/BBi8_3x4_M7.v), [BBi8_3x4_M8.v](coq/BBi8_3x4/BBi8_3x4_M8.v) | the three tape lemmas and the start, for each machine |
| [coq/BBi8_3x4/BBi8_3x4.v](coq/BBi8_3x4/BBi8_3x4.v) | the two theorems and the transition tables |

## Building

    git clone https://github.com/ccz181078/busycoq && cd busycoq && git checkout 4ea6784
    cd verify && make Makefile.coq && make -f Makefile.coq Individual33.vo
    BUSYCOQ=/path/to/busycoq bash /path/to/beavers/bbi8/coq/build.sh

The script copies the files into `verify/` and compiles them in the order of `coq/ORDER`. It takes a few seconds and
ends with `BUILD OK`.

## How it was made

The reduction, the written proof and the Coq were worked out with Claude, Anthropic's AI model, directed by Andrew
McKnight. The Coq compiler is the check that counts. The written proof was also read by a second Claude agent that
had no access to the scripts, and both machines were simulated directly for tens of millions of steps against the
rule.

## Credit

- [Nick Drozd](https://github.com/nickdrozd) for BBi and the holdout list.
- busycoq by [Maja Kądziołka](https://github.com/meithecatte/busycoq), in the fork of
  [ccz181078](https://github.com/ccz181078/busycoq). `BB34.v` and `Individual34.v` are adapted from it under its MIT
  licence.
