# BBi(9) holdouts, unofficial

Version 2026-11-16, the first version.

An unofficial list of the Turing machines with at most 9 instructions whose halting from the blank tape is not yet
decided, the holdouts of BBi(9), the instruction-limited busy beaver. It has 37,666 lines, one machine per line in the
standard text format, and every line starts with `1RB`.

## Credits

Other people's holdout lists decide much of this list.

- Nick Drozd shared the open BBi(8) holdouts (2026-10-25), and Loader3229 uploaded the list to the wiki. Nick Drozd
  also proposed BBi(9) as a community project.
- Andrew Ducharme listed the holdouts of BB(2,5) (2026-10-09), BB(2,6) (2026-10-17) and BB(4,3) (2026-05-09 and
  2026-10-23).
- Terry Ligocki listed the holdouts of BB(2,6) (2025-10-06).
- XnoobSpeakable listed the holdouts of BB(3,4) (2026-05-11).
- mxdys listed the holdouts of BB(3,3) (2025-08-27) and BB(6) (2026-10-24).
- The bbchallenge wiki's Instruction-Limited Busy Beaver page gives the value of BBi(7).

The method rests on others' work too.

- Allen Brady's Tree Normal Form generates the machines.
- [Coq-BB5](https://github.com/ccz181078/Coq-BB5) proves the cycler and translated-cycler method in its Loop decider.
  Its NGramCPS decider is the model for n-gram CPS, and its RepWL decider, in spirit, for repeated word lists.
- The [bbchallenge deciders paper](https://arxiv.org/abs/2504.20563) and Justin Blanchard's decider describe finite
  automata reduction (FAR), which Coq-BB5 verifies in Verifier_FAR.
- Coq-BB5's fixed-length history augmentation, TM_history, run under its NGramCPS decider, is the model for history
  n-gram CPS.

## How it was made

Every machine was enumerated in Tree Normal Form, cell by cell, a cell being a number of states and a number of
symbols. Each machine ran to 10^7 steps. Then came cyclers, translated cyclers, n-gram CPS (n up to 5), n-gram CPS with
a fixed-length history (history 6 and 12), repeated word lists and FAR (up to 10 states and 10^6 search nodes). History
n-gram CPS decided most of what the other deciders left. A second program, written only from `CHECKING.md`, rechecked
every certificate. The survivors ran on a GPU to 4×10^9 steps. 1,004 of them halted, and a CPU rerun confirmed each
halt. Community holdout lists were imported wherever one covers a cell, as they stood on 2026-11-15.

## Standard form

The enumeration also holds machines whose first step writes a blank. Each was mapped to its standard form by skipping
the opening that writes a blank, relettering the states in order of first entry and mirroring when the first move is
left. That took 41,226 machines in our own form to 37,666 lines. 3,185 merged with a line already listed, 361 were
dropped because the standard form is decided by a certificate, and 204 were kept in standard form as 190 distinct
lines. `merged_and_dropped.tsv` gives each merged or dropped machine with its standard form and the reason.

## Lines by cell

| Cell | Lines |
|------|------:|
| 2x5 | 37 |
| 2x6 | 251 |
| 2x7 | 15 |
| 3x3 | 6 |
| 3x4 | 7,726 |
| 3x5 | 8,019 |
| 3x6 | 658 |
| 4x3 | 3,707 |
| 4x4 | 10,617 |
| 4x5 | 2,925 |
| 4x6 | 48 |
| 5x3 | 1,897 |
| 5x4 | 1,470 |
| 5x5 | 169 |
| 5x6 | 3 |
| 6x3 | 81 |
| 6x4 | 34 |
| 6x5 | 3 |
| Total | 37,666 |

## Caveats

- The list is unofficial and has not been peer reviewed.
- Seven lines have 8 instructions. Six are the BB(3,3) holdouts. The seventh,
  `1RB---------_0RC2RB3LB1LB_2LA1RC---3RB`, is hipparcos's machine, accepted as halting after about 2.58×10^31
  steps. It stands in for its 9-instruction extensions, which are not yet listed.
- Two BBi(8) machines, `1RB1LC2LA---_2RC---------_0LA2RC3LC1RC` and `1RB---2LC3LA_2LC---------_0LA2RC3RC1LC`, are
  treated as non-halting on a Rocq proof (LINK-TO-ROCQ-PROOF).
- Most lines, 25,939 of them, lie in cells with no community list to cross-check against, every cell other than 2x5,
  2x6, 3x3, 3x4 and 4x3.
- The bbchallenge wiki reports smaller holdout counts for BB(2,6) and BB(4,3). Their files are not posted, so they are
  not applied here.
- Well-known open machines are in the list, among them Daniel Yuan's Hydra (`1RB3RB---3LA1RA_2LA3RA4LB0LB0LA`) and
  Bonus Cryptid (`1RB3RB---3LA1RA_2LA3RA4LB0LB1LB`) and Shawn Ligocki's Bigfoot (`1RB2RA1LC_2LC1RB2RB_---2LA1LA`).

## Found a halter, a proof or a decider?

Send it to CONTACT.

- For a halter, the machine in standard text and its exact step count. Every halter is confirmed by direct simulation
  before it leaves the list.
- For a non-halter, a certificate or a link to a proof.
- For a decider or a holdout list of your own, the list file in the standard text format, one machine per line.

Each one is credited in the next version.

## The spec and the checker

`CHECKING.md` is the spec that every certificate follows. `checker/bbi9check.py` is the independent checker written
from it alone, in Python with the standard library (its import check also reads YAML with PyYAML). It checks one cell's
run files, its claims and summary, which are not part of this folder. Without its optional compiled core it walks every
cell in Python, and its `--gpu` option needs code that is not published.

The tables of every BBi cell are at [amcknight.ca/beavers/bbi](../index.html), and BBi(9)'s at
[its own page](../bbi9/index.html).

## Files

- `BBi9_holdouts_37666_unofficial_2026-11-16.txt` holds the whole list, 37,666 lines.
- `by_cell/` holds the same lines split by cell, named `BBi9_<cell>_holdouts_<count>.txt`.
- `merged_and_dropped.tsv` holds the 3,546 machines in our own form that merged or were dropped, with the reason.
- `CHECKING.md` is the spec.
- `checker/bbi9check.py` is the independent checker.
- `README.md` is this file.
