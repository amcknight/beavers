# The Baker's Dozen

    1RB1RA_1RI1RC_0LD1LG_0RE1LD_1LK1RF_1RG0RA_1RA0LH_1LG1LH_1RE0LJ_1LH1LI_0LM0LL_1RL1LK_0LG---

A 13-state, 2-symbol [Busy Beaver](https://en.wikipedia.org/wiki/Busy_beaver) Turing machine that halts from the
blank tape after four rounds, each of size f<sub>ω+2</sub> in the
[fast-growing hierarchy](https://en.wikipedia.org/wiki/Fast-growing_hierarchy).

It is a variant of [M12](https://github.com/jeff87654/busy-beaver/tree/main/BB12), the 12-state machine of
[Jeff Ketchersid](https://github.com/jeff87654/busy-beaver) and Argon, a Gemini agent he runs. M12's engine, whose
slots already appear in [Racheline's 21-state machine of 2024](https://wiki.bbchallenge.org/wiki/Talk:Champions),
and both of its counters are unchanged. Two transitions change, L0 from 0LH to 1RL and K0 from the halt to 0LM, and
one state is new, M = (0LG, ---). Together they turn the sweep with which M12 builds a new countdown into a restart,
so the machine rereads its whole tape as a new countdown and starts over, four times. The name is a nod to its
parent, since a [baker's dozen](https://en.wikipedia.org/wiki/Baker%27s_dozen) is twelve plus one.

**Superseded.** On 28 October 2026, the morning after this proof was finished, Jeff Ketchersid and Argon published
[M13b](https://github.com/jeff87654/busy-beaver/tree/main/BB13), another 13-state variant of M12 with a larger
proved bound, f<sub>ω+2</sub><sup>6</sup>(f<sub>ω+1</sub>(f<sub>ω+1</sub>(3))) < σ. M13b reloads where M12 halts
and gets six rounds. Their 14-state [M14b](https://github.com/jeff87654/busy-beaver/tree/main/BB14) gets nine. The
Baker's Dozen was found independently and restarts from a different point, so it stays here as a record.

## What is proved

The proof is in Coq 8.20.1 with [busycoq](https://github.com/meithecatte/busycoq) at commit `bd2e36f`, built on Jeff
Ketchersid's Coq development for M12 ([BB12/verify_m12](https://github.com/jeff87654/busy-beaver/tree/main/BB12)).
It reuses two of his files whole and about 770 lines of his proofs unchanged. This repository does not copy them.
[coq/build.sh](coq/build.sh) fetches his repository at a pinned commit and splices his lines into place, checking
every file's SHA-256. See [coq/](coq/).

- `halt : halts tm c0`. The machine halts from the blank tape.
- `score_exact`. The halting tape holds an explicit number of ones, written in terms of the four round outputs.
- `sigma_lower_bound`. The number of ones N satisfies
  f_ω2(f_ω2(f_ω2(f_ω2(f_ω(f_ω(4)))))) < N, with the standard hierarchy f_0(n) = n + 1,
  f_(k+1)(n) = f_k^n(n), f_ω(n) = f_n(n), f_ω1(n) = f_ω^n(n), f_ω2(n) = f_ω1^n(n).
- `sigma_lower_bound_strong`. A stronger form that keeps an extra f_ω from each round.
- `beats_M12_bound` and `beats_M14_bound`. N is above the proved lower bounds of M12,
  f_ω2(f_ω1(f_ω1(3))), and of M14, f_ω2(f_ω2(f_ω2(15))), as stated in Jeff Ketchersid's Coq files. Those machines
  halt on a 0 and score N + 1, so `< N` is the matching comparison.

Every theorem is closed under the global context (no axioms). `probe.v` checks the compiled transition table against
the machine string entry by entry. `bash coq/build.sh` fetches everything, builds and checks it in under 20 seconds.

The machine halts reading a 1 (M1 is undefined), so its score σ is N.

## Read more

- [index.html](index.html), a write-up with diagrams of how the machine works and why it stops after four rounds.
- [coq/README.md](coq/README.md), the proof outline, exactly what is reused from Jeff Ketchersid's development, and
  how to rebuild.

Made by Andrew McKnight with Claude (Fable 5.1 and Opus 5.5), October 2026.
