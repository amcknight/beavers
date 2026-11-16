# Checking a BBi cell

This is everything needed to write a checker for one cell of the BBi(n) tracker without reading the program that
produced the cell. A checker rebuilds the cell's search tree, runs every halter to its halt, verifies every
non-halting certificate and compares its totals with the producer's. It never searches for a certificate itself.
Computing the sets that a NONHALT_CPS or NONHALT_RWL certificate names (section 6) is not a search, since the
machine and the certificate fix them. Computing the relation R and the set a that a NONHALT_FAR certificate names is
not a search either, and nor is computing the sets that a NONHALT_CPSH certificate names, which are NONHALT_CPS's
sets for a history machine that the machine and the certificate's H fix.

## 1. Machines and runs

- States are A, B, C and so on, with indices 0, 1, 2 and so on. Symbols are 0 to 9.
- A machine is a partial table. Each defined pair (q, r) holds an instruction (w, m, t), which writes symbol w,
  moves the head m (L or R) and goes to state t.
- A run starts in state A with the head at position 0 on a tape of 0s.
- Each round reads the symbol r under the head in the current state q.
  - If (q, r) is undefined, the run halts. That round is not a step.
  - Otherwise the machine writes w, moves the head to the next position (R adds 1, L subtracts 1), enters t, and the
    step count goes up by 1.
- "Halts after n steps" means exactly n steps run and then an undefined pair is read. That pair is the halting
  pair.
- The configuration after n steps is the state, the head position and the whole tape after n steps. The
  configuration after 0 steps is the start.
- A machine's depth is its number of defined pairs.

## 2. Shape and text

- The owned states s count the states with at least one defined pair. The symbols k are 1 plus the largest w over
  the defined pairs, or 1 if there are none. The shape is (s, k).
- Every machine in the tree below owns exactly the states with indices 0 to s − 1, and its defined pairs all have
  symbols below k. At most one more state, index s, appears as a target. A checker may assert these facts.
- The text of a machine has one row per owned state, A first, joined by `_`. A row has k cells for symbols 0 to
  k − 1. An undefined cell is `---`. A defined cell is the digit w, then `L` or `R`, then the letter of t.
- The empty machine's text is the empty string.

Examples. `1RB1LB_1LA---` has shape (2, 2). `0RB` has shape (1, 1), and its target B is not owned. The record
holder `1RB3LA4RB0RB2LA_1LB2LA3LA1RA---` has shape (2, 5).

## 3. The tree

This is plain Tree Normal Form after Allen Brady, as the wiki's Instruction-Limited Busy Beaver page enumerates it.

- The root is the empty machine. It halts after 0 steps on the pair (A, 0).
- Only machines that halt have children. A machine M that halts on (q, r) has one child for each instruction put
  into (q, r), with
  - w from 0 to min(9, W + 1), where W is the largest w in M (0 if M is empty)
  - m equal to R when M is the root, and L or R otherwise
  - t from 0 to min(9, T + 1), where T is the largest state index M uses as an owner or a target (0 if M is empty)
- So the root has four children, with texts `0RA`, `0RB`, `1RA---` and `1RB---`. Children of one parent differ,
  and the tree has no repeats.
- The canonical walk of a corridor visits a machine before its children, and a halter's children in increasing w,
  then L before R, then increasing t.
- The limits of 9 never remove a child inside a corridor (section 4). That holds because a cell has at most nine
  states. A machine whose ten states all own an instruction could target an eleventh state K and keep shape (10, k),
  so a 10×k cell at depth 10 or more would lose children to the limit. Such cells are outside this contract.

## 4. Cells and corridors

- The cell (S, K) at depth D holds the machines of depth D and shape (S, K). BBi(n) uses D = n. A checker accepts
  any D from 1 to 19, with S from 1 to 9 and K from 1 to 10. The fixtures use smaller depths.
- A machine at depth d ≤ D with shape (s, k) is in the corridor of (S, K, D) when s ≤ S, k ≤ K, S − s ≤ D − d and
  K − k ≤ D − d.
- From parent to child, s and k never fall and each rises by at most 1. So every ancestor of a cell machine is in
  the corridor, and the corridor at depth D is the cell itself.
- The corridor walk starts at the root. A corridor machine at depth d < D that halts adds those of its children
  that are in the corridor at depth d + 1. Children outside the corridor are dropped without being run.

## 5. What the producer writes

One directory per cell. For D = 9 it is `bbi9/cells/SxK`, for example `bbi9/cells/9x1`, and for any other D it is
`bbiD/cells/SxK`, for example `bbi10/cells/2x5`. It holds four files, and a fifth, `claims.idx`, when the claims are
grouped (below). A cell may also hold an amendment, which reruns its holdouts. Its files are `amend.json`,
`amend.tsv` or `amend.tsv.gz` and, once checked, `amend_check.json`, and section 12 describes them. A cell may also
hold an import (section 13), which marks the holdouts that other people's holdout lists decide.

A cell's claims and digests reproduce with the producer that the RUNS.md row of its full run names, in the
`producer` column. An amendment's lines reproduce with the producer its own row names (section 12). A later producer may certify more machines, or certify them differently, and then a rerun gives other claims and other
digests. A checker checks whatever cell it is given by these rules, whichever producer made it.

### summary.json

A JSON object. A checker uses these keys and ignores any others.

- `format` is `"bbi9-cell/1"`, `"bbi9-cell/2"`, `"bbi9-cell/3"`, `"bbi9-cell/4"` or `"bbi9-cell/5"`. Format 2 is
  format 1 with the NONHALT_CPS certificate (section 6) added, format 3 is format 2 with the NONHALT_RWL certificate
  added, format 4 is format 3 with the NONHALT_FAR certificate added, and format 5 is format 4 with the NONHALT_CPSH
  certificate added. A format 1 cell has no NONHALT_CPS claims, a format 1 or 2 cell has no NONHALT_RWL claims, a
  format 1 to 3 cell has no NONHALT_FAR claims, and a format 1 to 4 cell has no NONHALT_CPSH claims.
- `cell` is `[S, K]` and `depth` is D.
- `corridor` is a list of D + 1 objects. Entry d describes depth d and has the keys
  - `depth`, which is d
  - `machines`, the corridor machines at depth d
  - `HALT`, `NONHALT_CYCLER`, `NONHALT_TRANSLATED` and `UNKNOWN`, how many of them got each verdict
  - `NONHALT_CPS`, how many got that verdict, in formats 2 to 5. A format 1 entry does not have this key.
  - `NONHALT_RWL`, how many got that verdict, in formats 3 to 5. A format 1 or 2 entry does not have this key.
  - `NONHALT_FAR`, how many got that verdict, in formats 4 and 5. A format 1 to 3 entry does not have this key.
  - `NONHALT_CPSH`, how many got that verdict, in format 5 only. A format 1 to 4 entry does not have this key.
  - `max_halt_steps`, the most steps any halter at depth d ran (0 if there is none)
- `cell_machines` is the number of machines in the cell, which equals entry D's `machines`.
- `late_cell_machines` counts the cell machines with a late ancestor (section 8).
- `holdouts` counts the UNKNOWN claims at depth D, and `parent_holdouts` the UNKNOWN claims at depths below D.
- `top_halters` lists up to 10 objects `{"machine": text, "steps": n}`. They are the cell's halters with the most
  steps, most steps first, with ties in byte order of text.
- `halter_digest` is the digest (section 7) of the lines `text<TAB>n`, one per halter in the corridor at every
  depth, where n is its steps. The root gives the line `<TAB>0`.
- `claims` is the number of lines in the claims file, and `claims_digest` is the digest of those lines.
- `claims_split` is a depth s from 1 to D. It is required when `claims.idx` exists and ignored otherwise.
- A corridor entry may also have `halt_steps`, the sum of the steps of the halters at that depth. It is required in
  every entry when `claims.idx` exists.

The keys `producer`, `caps`, `tc_windows`, `tc_records`, `cps_max_n`, `cps_limit`, `rwl_max_b`, `rwl_max_t`,
`rwl_first_limit`, `rwl_limit`, `rwl_run_budget`, `far_max_n`, `far_budget`, `cpsh_tries`, `cpsh_limit`, `threads`
and `seconds` are for people to read. `rwl_max_b` and `rwl_max_t` are the largest b and T the producer tries, and
`rwl_limit` is the producer's own cap on the members of C, 3,000 for producer 0.3.0. That cap may be below the 20,000
that section 6 allows, and a checker never uses it. `far_max_n` is the largest n the producer tries for a NONHALT_FAR
certificate, and `far_budget` is its cap on the search nodes it spends on one machine (section 10), 10 and 1,000,000
for producer 0.5.0. A checker never uses them either.

Producer 0.6.0 also writes `rwl_first_limit` and `rwl_run_budget`, the member cap of RWL's first pass and its cap on
the runs a closure's members hold in all (section 10), and `tc_records`, how many of the steps that take the head
farther out than ever before it keeps on each side when it looks for a translated cycler. It writes `cpsh_tries`,
the (n, H) it tries for a NONHALT_CPSH certificate, in order, as a string such as `"3:6,3:12,5:12"`, and
`cpsh_limit`, its cap on the members of C in each try. Its standard settings for these five keys are 300, 100,000,
4,096, `"3:6,3:12,5:12"` and 20,000. Each decider can be switched off for a run, and a decider the run switched off
has none of its keys. NONHALT_CPS's keys are `cps_max_n` and `cps_limit`, NONHALT_RWL's
are the five keys that start with `rwl_`, NONHALT_FAR's are `far_max_n` and `far_budget`, and NONHALT_CPSH's are
`cpsh_tries` and `cpsh_limit`. A checker never uses any of these keys.

Producer 0.7.0 may also write `decider_order`, the order in which it tries NONHALT_CPS, NONHALT_RWL, NONHALT_FAR and
NONHALT_CPSH on a machine that rung 0 leaves UNKNOWN, as a string such as `"cps,cpsh,rwl,far"`, written only when it
is not `cps,rwl,far,cpsh`. A checker never uses it.

### claims.tsv

There is one line for every corridor machine the producer did not show to halt, and there are no other lines.
Fields are separated by TAB and every line ends with a newline. Without `claims.idx` the lines are in no particular
order. The file may be `claims.tsv.gz` instead, the gzip of the same bytes. It may hold several gzip members one
after another (RFC 1952), and then the claims bytes are their decompressed contents in order. If both exist, a checker reads `claims.tsv`.

| line | meaning |
|---|---|
| `text  NONHALT_CYCLER  i  j` | a cycler certificate |
| `text  NONHALT_TRANSLATED  R  i  j` or `... L  i  j` | a translated-cycler certificate |
| `text  NONHALT_CPS  n  c` | an n-gram CPS certificate, in formats 2 to 5 |
| `text  NONHALT_RWL  b  T  c` | a repeated-word-list certificate, in formats 3 to 5 |
| `text  NONHALT_FAR  side  n  table  e` | a finite-automata-reduction certificate, in formats 4 and 5 |
| `text  NONHALT_CPSH  n  H  c` | a history n-gram CPS certificate, in format 5 only |
| `text  UNKNOWN  n` | the producer ran n steps and decided nothing |

### claims.idx (optional)

The producer may group the claims so that a checker can read them alongside its walk. It then writes `claims.idx`
beside `claims.tsv.gz`, and `claims.tsv` must not exist.

- The top group holds the claims of the corridor machines at depths below s. Each corridor machine R at depth s
  roots a group that holds the claims of R's corridor subtree, R included.
- Within a group, the claims lines are in the order of the group's canonical walk (section 3). That is the walk
  from R, or for the top group the walk from the root that does not enter depth s.
- `claims.idx` is TAB-separated, with the header line `group seq offset bytes lines` and one line per gzip member
  of `claims.tsv.gz`. `group` is R's text, or `top` for the top group. `seq` numbers a group's members from 0 in
  order. `offset` and `bytes` place the member in the file, and `lines` is its number of claims lines.
- Sorted by offset, the members tile the file from its first byte to its last, with no gaps and no overlaps. Each
  member is exactly one complete gzip member and decompresses to whole lines, each ending with a newline. A group's
  lines are its members' lines in `seq` order. A group with no claims has no members.
- `claims.tsv.gz` is still a claims file as described above, so a checker may ignore `claims.idx`.

### Holdout lists

- `BBi{D}_{S}x{K}_holdouts_unofficial.txt` holds the texts of the UNKNOWN claims at depth D, for example
  `BBi9_9x1_holdouts_unofficial.txt`.
- `BBi{D}_{S}x{K}_parent_holdouts_unofficial.txt` holds the texts of the UNKNOWN claims at depths below D.

Both are sorted in byte order, one text per line, each line ending with a newline. A list with no machines is an
empty file. In a cell with an amendment, the lists hold instead the UNKNOWN texts that the amendment leaves
(section 12).

## 6. Certificates

Let p_n be the head position after n steps.

- **NONHALT_CYCLER i j** is valid when 0 ≤ i < j, the machine runs at least j steps without halting, and the
  configurations after i steps and after j steps are equal (the same state, head position and symbol at every
  position).
- **NONHALT_TRANSLATED R i j** is valid when all of these hold.
  - 1 ≤ i < j, and the machine runs at least j steps without halting.
  - p_i is larger than every p_n with n < i, and p_j is larger than every p_n with n < j.
  - The state after i steps equals the state after j steps.
  - Let a be the smallest of p_i, p_(i+1), …, p_j, and let δ = p_j − p_i. For every position c from a to p_i, the
    symbol at c after i steps equals the symbol at c + δ after j steps.
- **NONHALT_TRANSLATED L i j** is the mirror image. p_i and p_j are smaller than every earlier position, b is the
  largest of p_i, …, p_j, δ = p_j − p_i, and for every c from p_i to b the symbol at c after i steps equals the
  symbol at c + δ after j steps.
- **NONHALT_CPS n c** is valid when 1 ≤ n ≤ 5, 1 ≤ c ≤ 20,000, no member of the set C defined below has an
  undefined pair, and C has exactly c members. A checker fails a certificate whose n or c is out of range without
  computing anything.
- **NONHALT_RWL b T c** is valid when 1 ≤ b ≤ 6, 1 ≤ T ≤ 3 and 1 ≤ c ≤ 20,000, every block run of every member of
  the set C defined below leaves its block within 1,000 steps without reading an undefined pair, and C has exactly c
  members. A checker fails a certificate whose b, T or c is out of range without computing anything.
- **NONHALT_FAR side n table e** is valid when side is `L` or `R`, 1 ≤ n ≤ 10, table is a string of exactly n·k
  ASCII digits whose first digit is 0 and each of which is below n, 1 ≤ e ≤ 102,010, and, for the edges R and the
  nodes a defined below, the node (0, A) is not in a and R has exactly e edges. A checker fails a certificate whose
  side, n, table or e is out of range without computing anything.
- **NONHALT_CPSH n H c** is valid when 1 ≤ n ≤ 5, 1 ≤ H ≤ 12 and 1 ≤ c ≤ 20,000, and NONHALT_CPS's sets Lw, Rw
  and C, computed with this n for the history machine M_H defined below, close with exactly c members in C, none of
  which has an undefined pair. A checker fails a certificate whose n, H or c is out of range without computing
  anything.
- **UNKNOWN n** has nothing to verify. The machine is a holdout.

Why these prove the machine never halts. A cycler returns to an earlier configuration, so it repeats forever. In
the translated case every cell beyond p_i is blank after i steps, and between steps i and j the head stays at a or
beyond. So from step j the machine sees a shifted copy of what it saw from step i, and it repeats with a shift of δ
forever. This is the Lin recurrence, which Coq-BB5 proves in Rocq as its Loop decider.

**Limits.**

The bullets above and section 9 are the contract, and the table names their numbers for programs.

| limit | value |
|---|---|
| `MAX_CAP` | 10,000,000 |
| `CPS_MAX_N` | 5 |
| `CPS_MAX_C` | 20,000 |
| `RWL_MAX_B` | 6 |
| `RWL_MAX_T` | 3 |
| `RWL_MAX_C` | 20,000 |
| `RWL_BLOCK_STEPS` | 1,000 |
| `FAR_MAX_N` | 10 |
| `FAR_MAX_E` | 102,010 |
| `CPSH_MAX_N` | 5 |
| `CPSH_MAX_H` | 12 |
| `CPSH_MAX_C` | 20,000 |

### NONHALT_CPS

This is n-gram CPS (closed position set), and it follows Coq-BB5's NGramCPS decider. It looks at the tape only
through the n cells on each side of the head. In this section n is always the certificate's n, never a number of
steps.

- A word is a sequence of n symbols. 0ⁿ is the word of n 0s.
- A local configuration (u, q, x, v) has a word u = u₁…uₙ for the n cells left of the head, a state q, the symbol x
  under the head, and a word v = v₁…vₙ for the n cells right of the head. Both words read left to right along the
  tape, so uₙ and v₁ are the two cells next to the head. The pair of (u, q, x, v) is (q, x).
- Lw and Rw are sets of words, and C is a set of local configurations. They are the smallest sets that obey these
  rules.
  - 0ⁿ is in Lw and in Rw, and (0ⁿ, A, 0, 0ⁿ) is in C.
  - Take any member (u, q, x, v) of C whose pair (q, x) is defined, with instruction (w, m, t).
    - If m is R, the word u₂…uₙw is in Lw. For every symbol y such that v₂…vₙy is in Rw, the local configuration
      (u₂…uₙw, t, v₁, v₂…vₙy) is in C.
    - If m is L, the word wv₁…vₙ₋₁ is in Rw. For every symbol y such that yu₁…uₙ₋₁ is in Lw, the local
      configuration (yu₁…uₙ₋₁, t, uₙ, wv₁…vₙ₋₁) is in C.
- A pair is undefined as in section 1. That includes every pair of a state that owns no instructions, such as B in
  `0RB`. A member of C whose pair is undefined adds nothing, and it makes the certificate invalid.

When n = 1, the words v₂…vₙ and u₁…uₙ₋₁ are empty. A member that moves R then puts the word w in Lw and
(w, t, v₁, y) in C for every symbol y in Rw. A member that moves L puts the word w in Rw and (y, t, u₁, w) in C for
every symbol y in Lw.

A checker computes the three sets by applying the rules until nothing new is added. They are the smallest sets that
obey the rules, so their sizes do not depend on the order of the work. A checker may fail as soon as C has more than
c members or holds a member whose pair is undefined. The number c bounds the checker's work and cross-checks the
producer. A certificate whose c is not exactly the size of C is invalid, even when no member's pair is undefined.

**A member must be expanded again when a word it waits on arrives.** A member that moves R uses every word of Rw
that starts with v₂…vₙ, and a member that moves L uses every word of Lw that ends with u₁…uₙ₋₁. When n = 1 that is
every word of Rw or Lw. Such a word can enter Rw or Lw after the member was first expanded, and then the member has
a new successor in C. A work list that expands each member once, against Lw and Rw as they stand at that moment,
misses those successors and accepts machines that halt. For example `0RB---_0RC---_1LD---_0LA---` halts after 6
steps on (C, 1). One such pass at n = 1, starting from (0, A, 0, 0), stops with the 4 members (0, A, 0, 0),
(0, B, 0, 0), (0, C, 0, 0) and (0, D, 0, 1). But expanding (0, C, 0, 0) puts 1 in Rw after (0, A, 0, 0) was
expanded, and (0, A, 0, 0) moves R. So the true C also holds (0, B, 0, 1), and then (0, C, 1, 0), whose pair (C, 1)
is undefined. No NONHALT_CPS certificate is valid for this machine at any n. Repeating whole passes over C until a
pass adds nothing to Lw, Rw or C is correct. So is keeping, for each word, the members that wait on it, and
expanding them again when it enters Lw or Rw.

Why it proves the machine never halts. Take the real run after any number of steps. Every run of n consecutive cells
wholly left of the head is a word in Lw, every such run wholly right of the head is a word in Rw, and the local
configuration around the head is in C. This holds at the start, where the tape is all 0s. A step that moves R
writes w and leaves the left part with exactly one new run of n cells, u₂…uₙw, which is in Lw. The new right word
v₂…vₙy, where y is the cell n + 1 places right of the old head, was already a run of n cells in the right part, so it
is in Rw, and the R rule puts the new local configuration in C. A step that moves L is the mirror image. So every
pair the run reads is the pair of a member of C. None is undefined, so the run never halts.

### NONHALT_RWL

This is repeated word lists (RWL), and it follows Coq-BB5's RepWL decider in spirit. The rules below are this
tracker's own and may differ from Coq-BB5's in detail. RWL sees the whole tape, cut into blocks of b cells, with each
run of equal blocks written once with a count. It suits bouncers, machines whose head sweeps back and forth across a
tape that grows a little with each sweep. In this section b and T are always the certificate's numbers, and a count
is a number of blocks, never a number of steps.

- **Blocks and words.** Block j is the b cells at positions jb to jb + b − 1, for every integer j. The run starts at
  position 0, the left cell of block 0. A word is a sequence of b symbols, and 0ᵇ is the word of b 0s. The word of a
  block is its b symbols read left to right along the tape, on either side of the head.
- **Runs and lists.** A run (w, n) is a word w and a count n from 1 to T. A count below T stands for exactly n copies
  of w in a row, and the count T stands for T or more copies. A list is a finite sequence of runs, possibly empty. Its
  first run is the one nearest the head, and its last run is the one farthest from it.
- **Members.** A member (L, q, d, R) has two lists L and R, a state q and a side d, which is L or R. It stands for
  every configuration of this shape. Some block boundary splits the tape. Right of the boundary are the copies that
  R's runs stand for, R's first run nearest the boundary, then 0s forever. Left of it are the copies that L's runs
  stand for, L's first run nearest the boundary, then 0s forever. The state is q. The head is on the cell just right
  of the boundary when d is R, and just left of it when d is L. Two members are the same when their lists, states and
  sides are the same.
- **The start.** (empty, A, R, empty) is in C. It stands for the start of the run, with the boundary just left of
  position 0.
- **Taking a block.** The near list is R when d is R and L when d is L. Taking a block from it gives one or two pairs
  (w, rest).
  - From an empty list, the one pair (0ᵇ, empty).
  - When the first run is (w, n) with n < T, the one pair of the word w and the list with that run replaced by
    (w, n − 1), or removed when n is 1.
  - When the first run is (w, T), two pairs. One is the word w with the list that has that run replaced by
    (w, T − 1), or removed when T is 1. The other is the word w with the list unchanged, still starting with (w, T).
- **The block run.** For each pair (w, rest), run the machine on the word w alone, a tape of b cells, starting in
  state q on its left cell when d is R and on its right cell when d is L. Steps are as in section 1, and the run goes
  on until a step moves the head off either end. If it reads an undefined pair first, the certificate is invalid. A
  block run has 1,000 steps to leave. One whose 1,000th step moves the head off its block has left, and one whose
  head is still on its block after 1,000 steps fails, which makes the certificate invalid. With b = 6 the start's
  block run of each of the holdouts `0RB---3LA---------_1LA2RB---4LA5LA1LA` and
  `1RB------------_2LC0LC3RB---1LC_---1RB---4LC---` leaves after 912 steps, close to the limit. When a block run
  leaves, the head is off the right end or the left end in some state t, and the b cells hold a word w′.
- **Putting a block.** Putting w′ on a list gives the list with its first run replaced by (w′, min(n + 1, T)) when
  that first run is (w′, n), and otherwise the list with the run (w′, 1) added in front. Putting w′ on an empty list
  gives the list of the one run (w′, 1).
- **Trimming.** Trimming a list removes its last run while that run's word is 0ᵇ, again and again until the list is
  empty or its last run's word is not 0ᵇ. A 0ᵇ run with a run of another word between it and the far end stays.
- **The successor.** Let left and right be the member's lists after the take, with the pair's rest in place of the
  near list and the other list unchanged. When the block run leaves off the right end, the successor is
  (trim(put(left, w′)), t, R, trim(right)). When it leaves off the left end, the successor is
  (trim(left), t, L, trim(put(right, w′))). Each pair whose block run leaves gives one successor.
- **C** is the smallest set of members that holds the start and every successor of its members.

A checker computes C by applying the rules until nothing new is added. C is the smallest set that obeys them, so its
size does not depend on the order of the work. A member's successors depend on that member alone, so each member is
taken and run once. A checker may fail as soon as C has more than c members or a block run fails. The number c bounds
the checker's work and cross-checks the producer. A certificate whose c is not exactly the size of C is invalid, even
when every block run leaves its block.

**Each shortcut below accepts a machine that halts.** The first three get one of the rules above wrong, and the
fourth adds a rule that this contract does not have.

- Taking from (w, T) and giving only the pair that keeps (w, T), dropping the case of exactly T − 1 copies left.
  `1RB------_2LB2LA1RB` halts, and with b = 1 and T = 2 that shortcut closes with 6 members.
- Putting w′ beside (w′, n) and leaving the count at n. `1RB0RA---_2LB2LA1LA` halts, and with b = 1 and T = 2 that
  shortcut closes with 7 members.
- Trimming 0ᵇ runs at the front of a list, next to the head, as well as at the far end. `1RB---0RB_2LB1RA---` halts,
  and with b = 1 and T = 2 that shortcut closes with 4 members.
- A repeat rule, which is not part of this contract but a natural addition. It treats a block run that comes back to
  an earlier state and head cell as one that never leaves, without comparing the block's contents. With b = 2 it
  accepts the BB(2) champion `1RB1LB_1LA---`, which halts after 5 steps. The start's block run is back in state A on
  the left cell after 2 steps, so the start would have no successor and C would be the start alone. This contract has
  no repeat rule at all. A block run must leave its block within 1,000 steps.

The true rules refuse all four of these machines at every b from 1 to 6 and T from 1 to 3. When T is 1, a count of 1
stands for 1 or more copies, so taking from (w, 1) gives two rests, one with the run removed and one with it kept.
Reading a count of 1 as exact when T is 1 also accepts halters. With b = 1 and T = 1 it closes `1RB------_2LB2LA1RB`
with 5 members, `1RB0RA---_2LB2LA1LA` with 7 and `1RB---0RB_2LB1RA---` with 6.

Why it proves the machine never halts. Take the real run at the start and after every step that moves the head into
another block. Its configuration then is one that some member of C stands for. This holds at the start. From such a
configuration the machine runs inside the head's block, seeing only that block, until a step moves the head into the
next block. The block's real contents and the rest of the near side match one of the take's pairs, because every way
the real counts can be is covered. n copies less one are exactly n − 1 copies, and T or more copies less one are
exactly T − 1 or still T or more. So the run inside the block is that pair's block run, which reads no undefined pair
and leaves. Putting the written block on the list it now belongs to raises a count or starts a run, and T or more
copies plus one are still T or more. Trimming removes only blocks of 0s at the far end, beside the 0s that already
fill the rest of the tape. So the configuration after the crossing is one that the successor stands for. Every pair
the real run reads is read in some block run, and none of them is undefined. So the run never halts.

### NONHALT_FAR

This is finite automata reduction (FAR) in its direct form, as the bbchallenge deciders paper (arXiv 2504.20563,
section 6) and Justin Blanchard's decider (UncombedCoconut/bbchallenge-deciders) state it, and as Coq-BB5 verifies it
in Verifier_FAR. The rules below are this tracker's own statement of it, for k symbols, with the machine's mirror
image as side R. It suits counters, machines that keep a number on the tape and add to it forever. The certificate's
table is a small deterministic automaton that reads the tape left of the head. From the machine and that table alone,
a checker builds a second automaton for the head's cell and the tape right of it, by applying four rules until
nothing changes. Together the two accept every configuration about to halt and every configuration that leads to one,
and the certificate says that they do not accept the start.

In this section n is always the certificate's n, never a number of steps, and k is the machine's number of symbols
(section 2), 1 plus the largest w it writes, or 1 when it has no defined pair. Every text in the tree has exactly k
cells in each row, and a checker may fail a certificate for a text whose rows have another width. Taking k from the
largest w keeps every symbol the machine can write in the alphabet, and refusing other widths leaves no doubt about
the table's length.

- **The machine.** For side L it is the machine itself. For side R it is its mirror image, the same table with L and
  R swapped in every instruction and nothing else changed. Its states are A up to the largest state index the machine
  uses as an owner or a target, m states in all. A is always one of them, so m is at least 1, and the empty machine
  has the one state A (m = 1) and k = 1. The symbols are 0 to k − 1, and a pair (q, r) has one of the m states q and
  one of the k symbols r. A state that owns no instructions, such as B in `0RB` or A in the empty machine, has every
  pair undefined.
- **The automaton.** Digit i·k + b of the table is δ(i, b), for the automaton states i from 0 to n − 1 and the
  symbols b from 0 to k − 1. So the table is δ(0, 0), δ(0, 1), …, δ(0, k − 1), δ(1, 0) and so on, and its first digit
  is δ(0, 0) = 0. For a word u, D(u) is the state reached from 0 by reading u from left to right, and D of the empty
  word is 0. The automaton need not be in any canonical form. A state that is never reached from 0 is allowed and
  obeys the rules below like any other.
- **Nodes and edges.** A node is a pair (i, q) of an automaton state i and a machine state q, or the one extra node
  ⊥, so there are n·m + 1 nodes. An edge x –b→ y goes from node x to node y and carries a symbol b. Edges with the
  same ends and different symbols are different edges.
- **R** is the smallest set of edges that obeys these four rules.
  1. **Bottom.** ⊥ –b→ ⊥ for every symbol b.
  2. **Halt.** For every undefined pair (q, r) and every automaton state i, (i, q) –r→ ⊥.
  3. **Right.** For every pair (q, r) whose instruction is (w, R, t) and every i, (i, q) –r→ (δ(i, w), t).
  4. **Left.** For every pair (q, r) whose instruction is (w, L, t), every i and every symbol b, and every node y
     such that R holds edges (i, t) –b→ y′ and y′ –w→ y for some node y′, R holds (δ(i, b), q) –r→ y. That is, the
     source is the node of state δ(i, b), and the targets are every node reached from (i, t) by reading b and then w.
- **a** is the smallest set of nodes that holds ⊥ and every node x with an edge x –0→ y for some y in a. So a holds
  exactly the nodes from which some path of 0-edges, possibly empty, reaches ⊥.

A checker computes R by applying the rules until nothing new is added, and then a in the same way. They are the
smallest sets that obey their rules, so they do not depend on the order of the work. The number e cross-checks the
producer. A certificate whose e is not exactly the number of edges of R is invalid, even when (0, A) is not in a. R
never has more than k·(n·m + 1)² edges, and with n, m and k at most 10 that is at most 102,010. The table already
bounds the checker's work, so e is not needed for that, but with it every valid certificate compares the producer's
whole relation with the checker's.

**Rule 4 must be applied again when the edges it reads change.** Its targets depend on the edges out of (i, t) on b
and out of their ends on w, and rules 3 and 4 can add such edges later. A pass that applies each instance of rule 4
once, against R as it stands at that moment, misses edges and accepts machines that halt. For example
`0RB---_1LA---` halts after 3 steps on (B, 1). With side R and the table `0111` (n = 2), one pass over the instances,
i and then b in increasing order, uses the empty set of 0-edges of (1, A) for (i, b) = (0, 0), adds (1, A) –0→ ⊥ only
afterwards for (0, 1), and stops with 9 edges, (0, A) outside a. The true R also holds (0, A) –0→ ⊥, 10 edges, so
(0, A) is in a. Repeating whole passes until one adds no edge is correct. So is keeping a work list of the instances
whose input edges changed.

**a is a closure, and the start is checked against all of it.** a is not ⊥ alone, which every machine passes since
(0, A) is never ⊥ itself, and not ⊥ with the nodes one 0-edge from it. `0RB` halts after 1 step, and with side L and
the table `0`, R holds (0, A) –0→ (0, B) and (0, B) –0→ ⊥, since B owns no instructions. So (0, A) is in a, though it
has no 0-edge straight to ⊥.

Why it proves the machine never halts. Write a configuration of the machine as a word u q v. Here u is the tape from
some position left of every non-0 cell up to the cell left of the head, q is the state, and v is the head's cell and
the tape right of it up to some position right of every non-0 cell, so v is never empty. Call the configuration
marked when some path of edges of R from (D(u), q) reads v and ends at a node of a.

- Whether a configuration is marked does not depend on how many 0s its word takes at either end. A 0 more on the left
  changes nothing, because δ(0, 0) = 0. A 0 more on the right changes nothing, because a node is in a exactly when it
  is ⊥ or has a 0-edge to a node of a, and ⊥ –0→ ⊥.
- A configuration about to halt, in state q reading r with (q, r) undefined, is marked. Rule 2 gives
  (D(u), q) –r→ ⊥, and rule 1 reads the rest of v from ⊥.
- When the configuration after a step is marked, so is the one before it. Let the step read r in state q, with
  v = r v′. If it moves R with (w, R, t), the configuration after it is u w t v′ (with a 0 for v′ when v′ is empty),
  so a path from (D(uw), t) reads v′ and ends in a, and rule 3 gives (D(u), q) –r→ (D(uw), t), since
  D(uw) = δ(D(u), w). If it moves L with (w, L, t), write u = u′ b, putting a 0 on the left first when u is empty.
  The configuration after the step is u′ t b w v′, so a path from (D(u′), t) reads b, then w, then v′, and ends in a.
  Rule 4 gives (D(u), q), whose state is δ(D(u′), b), an edge on r to the node that path reaches after b and w.
- So if the machine halted, every configuration of its run back to the start would be marked. The start is the word
  A0, which is marked exactly when (0, A) is in a. The certificate says it is not, so the machine never halts. For
  side R, the mirror image's run is the mirror image of the machine's run, so one halts exactly when the other does.

Each shortcut in the table below gets one rule or check wrong and accepts a machine that halts. Each certificate
shown is the one the shortcut itself accepts, with the shortcut's own edge count, and the true rules refuse every one.

**NONHALT_FAR shortcuts.**

| shortcut | machine | halts after | the shortcut accepts |
|---|---|---|---|
| a = {⊥}, which every machine passes, the root included | `1RB---` | 1 step | `NONHALT_FAR L 1 00 6` |
| a = ⊥ and the nodes with a 0-edge straight to ⊥, or the start checked only for a 0-edge straight to ⊥ | `0RB` | 1 step | `NONHALT_FAR L 1 0 3` |
| rule 2 only for states that own instructions, so a target that owns none gets no edge to ⊥ | `0RB` | 1 step | `NONHALT_FAR L 1 0 2` |
| rule 1 only for b = 0 | `1RB---` | 1 step | `NONHALT_FAR R 1 00 4` |
| rule 4 only for b = 0, as if the cell left of the head were always 0 | `0RB---_1LA---` | 3 steps | `NONHALT_FAR R 1 00 5` |
| rule 4 reading w before b | `1RB---_0LB---` | 2 steps | `NONHALT_FAR L 1 00 5` |
| rule 4 reading only w from (i, t), without b | `0RB---_1LA---` | 3 steps | `NONHALT_FAR R 2 0111 10` |
| rule 4 applied once per instance, in one pass | `0RB---_1LA---` | 3 steps | `NONHALT_FAR R 2 0111 9` |
| rule 3 moving the automaton by the symbol read, δ(i, r), instead of the symbol written | `0RB---_1LA---` | 3 steps | `NONHALT_FAR R 2 0101 9` |
| not requiring δ(0, 0) = 0 | `0RB` | 1 step | `NONHALT_FAR R 2 11 4` |

The shortcut that reads only w from (i, t) computes the true number of edges, 10, with a different relation. So the
edge count alone does not catch every wrong construction, and the start check must be made.

**A is always a state.** The empty machine, the root, has no owner and no target. A checker that took m as 1 plus the
largest index over that empty set would get m = 0, no node (0, A), and R = {⊥ –0→ ⊥}. Then "(0, A) is not in a"
would hold vacuously, and it would accept `NONHALT_FAR L 1 0 1` for the root, which halts after 0 steps. In the
indexed walk of section 9 a valid certificate on a group's machine skips running it, so such a claim on the root would
hide the whole corridor from the walk. With m = 1, R holds (0, A) –0→ ⊥ and ⊥ –0→ ⊥, 2 edges, and (0, A) is in a.

The rules hold at every automaton state, reachable from 0 or not. Applying them only at the states reachable from 0
is harmless for soundness, but it changes e when the table has unreachable states, so a checker applies them at every
state. For example, for `0RA` with side L and the table `01` (n = 2), R has the 3 edges (0, A) –0→ (0, A),
(1, A) –0→ (1, A) and ⊥ –0→ ⊥, though state 1 is never reached. So `NONHALT_FAR L 2 01 3` is valid, and
`NONHALT_FAR L 2 01 2`, the count at the reachable states only, is not.

### NONHALT_CPSH

This is history n-gram CPS. It runs the closure of NONHALT_CPS on the history machine M_H, a copy of the machine
whose cells also remember the last H pairs (state, symbol) that were read there. Cells that hold the same symbol but
were written in different ways then look different to the closure, which can keep apart configurations that plain
n-gram CPS merges. It follows Coq-BB5's `TM_history` (CoqBB5/BB5/TM.v), which Coq-BB5 runs under its NGramCPS
decider, and it is the transform that the bbchallenge wiki's NGram CPS page calls fixed-length history augmentation.
In this section n and H are always the certificate's numbers, never numbers of steps, and k is the machine's number
of symbols (section 2).

- **Histories.** A history is a sequence of at most H pairs (q, b), each of a state q and a symbol b of the machine
  M. The empty history is ().
- **Symbols.** A symbol of M_H is a pair (b, h) of a symbol b of M, its base, and a history h. Two symbols of M_H are
  equal exactly when their bases are equal and their histories are of the same length and equal entry by entry.
- **The blank.** The blank of M_H is (0, ()), the base 0 with the empty history. M_H's run starts in state A with the
  head at position 0 on a tape of blanks.
- **Instructions.** M_H has M's states. Its pair (q, (b, h)) is undefined exactly when M's pair (q, b) is undefined
  (section 1), whatever h is. That includes every pair of a state that owns no instructions. Otherwise let (w, m, t)
  be M's instruction on (q, b). M_H's instruction on (q, (b, h)) writes the symbol (w, h′), moves the head m and goes
  to state t, where h′ is the first H entries of the sequence that puts (q, b) in front of h. So h′ is (q, b)
  followed by h, less h's last entry when h already has H entries.

The sets Lw, Rw and C of a NONHALT_CPSH certificate are the sets of the NONHALT_CPS subsection above, word for word,
with M_H in place of the machine and with this n. A word is a sequence of n symbols of M_H, the symbol x under the
head of a local configuration is a symbol of M_H, and its pair (q, x) is a pair of M_H. A member's instruction is
M_H's, so the symbol it writes, the w of the NONHALT_CPS rules, is the symbol (w, h′) of M_H. A checker computes the
sets as the NONHALT_CPS subsection says. It may fail as soon as C has more than c members or holds a member whose pair
is undefined, and a certificate whose c is not exactly the size of C is invalid, even when no member's pair is
undefined.

M_H has finitely many symbols, since a history has at most H entries and there are finitely many pairs, but far too
many to list. The closure meets only the blank and the symbols that M_H's instructions write, so a checker can make
each symbol when an instruction first writes it. It may number the symbols in any way, as long as the blank is
(0, ()) wherever the NONHALT_CPS rules say 0 and each instruction comes from the base, as the first two warnings below
say.

**The instruction comes from (q, b) alone.** Whether the pair (q, (b, h)) is defined, and the base w, the move m and
the state t of its instruction, depend on the state q and the base b and on nothing else. The history h shapes only
the history h′ of the written symbol. A checker that numbers the symbols of M_H and then uses a symbol's number in
place of its base, for example the number modulo k, reads the instructions of another machine, and it accepts
machines that halt (the shortcut table below).

**Every 0 of section 6 is the blank (0, ()).** The word 0ⁿ that is in Lw and in Rw is the word of n blanks (0, ()),
and the start member is (0ⁿ, A, (0, ()), 0ⁿ). It is never another symbol whose base is 0, and never whichever symbol
a checker happens to number 0. A checker that numbers symbols as they are written, and lets number 0 be the first
symbol written, the one the machine's first step writes on the blank, starts the closure from a tape that the run
never has, and it accepts a machine that halts (the shortcut table below). A blank with some fixed non-empty history
would also give a sound closure, but it is not this certificate, and its c can differ.

**Waiting members are expanded again here too.** The NONHALT_CPS rule that a member must be expanded again when a
word it waits on arrives holds for M_H word for word. A member that moves R waits on the words of Rw that start with
v₂…vₙ, and a member that moves L on the words of Lw that end with u₁…uₙ₋₁. Section 6's trap machine
`0RB---_0RC---_1LD---_0LA---` does not test this rule here. At every n from 1 to 5 and every H from 1 to 12, a
closure that expands each member once refuses that machine, as the true closure does. The first two rows of the
shortcut table below are machines that do test it.

Why it proves the machine never halts. Run M and M_H side by side, each from its blank tape. By induction on the
steps, after every number of steps they are in the same state with the head at the same position, and every cell of
M_H's tape holds a symbol whose base is M's symbol in that cell. This holds at the start, where every cell of M's tape
holds 0 and every cell of M_H's tape holds (0, ()), whose base is 0. If it holds before a step, M reads (q, b) and
M_H reads (q, (b, h)) for some h. These two pairs are undefined together, and when they are defined, both
instructions write the base w, move the head m and go to state t, so it holds after the step. So M halts after s
steps exactly when M_H does. The NONHALT_CPS argument above holds for any machine whose tape starts with the symbol of
the start words in every cell, and M_H's tape starts with (0, ()) in every cell. So a valid certificate shows that M_H
never halts, and then M never halts.

Each shortcut in the table below gets one rule wrong and accepts a machine that halts. Each certificate shown is the
one the shortcut itself accepts, with the shortcut's own count of C, the same whether its work list is a stack or a
queue. In the third and fourth rows the symbols are numbered in the order they are made, the blank 0.

**NONHALT_CPSH shortcuts.**

| shortcut | machine | halts after | the shortcut accepts |
|---|---|---|---|
| each member expanded once, against Lw and Rw as they stand at that moment | `1RB2LB---_2LA2RB1LB` | 37 steps | `NONHALT_CPSH 3 6 26` |
| each member expanded once, against Lw and Rw as they stand at that moment | `1RB2LA1RA_1LB1LA1RC_---2LA2RB` | 11,597,631 steps | `NONHALT_CPSH 3 6 61` |
| the symbol's number modulo k used as its base, for the instruction and the history entry | `1RB1RB_1LA---` | 3 steps | `NONHALT_CPSH 3 6 15` |
| the symbol's number modulo k used as its base, for the instruction and the history entry | `1RB1LB_1LA---` | 5 steps | `NONHALT_CPSH 3 6 11` |
| every 0 of section 6 read as the first symbol written, not the blank | `1RB1LA_1LA---` | 4 steps | `NONHALT_CPSH 3 6 4` |

The second machine is a late halter of BBi(8)'s 3×3 cell (`experiments/bbi/late_halters.tsv`). No NONHALT_CPSH
certificate is valid for any of the five machines, or for the trap machine, at any n from 1 to 5 and any H from 1
to 12. Using only the symbol's number modulo k for the instruction, with the history entry from the true base, is
wrong as well and accepts `1RB1RB_1LA---` with 16 members.

## 7. Digests

- h(x) is the first 8 bytes of the SHA-256 hash of the UTF-8 bytes of the line x (without its newline), read as a
  big-endian unsigned integer.
- The digest of a multiset of lines is the sum of h over the lines, modulo 2^64, written as 16 lowercase hex digits.
  Order does not matter, and a repeated line counts twice.

## 8. The census

`census.tsv` is TAB-separated with a header line and the columns `depth states symbols nodes halt late nonhalt
unknown max_steps pred pred_unknown pred_unknown_fresh`. The census count of (S, K, D) is `nodes` in the row
(D, S, K) when D ≤ 8, and `pred` in the row (9, S, K) when D = 9. A missing row means 0. For D from 10 to 19 there
is no census count. The census rule is skipped and `census_match` is null. The check then rests on section 9 step 4
alone, the checker's own walk of the corridor against the producer's counts and digests, which is what it rests on at
every depth. The census is a third count that the two walks must also match where it exists.

The census counted a machine only if every ancestor halted within that ancestor's census cap. The cap is 4,000,000
steps for an ancestor at depths 0 to 7, and 100,000 steps for an ancestor at depth 8 or deeper. A cell machine is
**late** when some ancestor halted after more steps than its cap. Late machines are missing from the census. Late
machines are counted and compared at every D. At D ≥ 10 they are missing from no census, and the count only has to
agree. The census file's own `late` column counts something else, the halters that took more than 10,000 steps and
were still counted. A checker does not use it.

The census rule is this. When there are no parent holdouts, `cell_machines` minus `late_cell_machines` equals the
census count. With parent holdouts the comparison is skipped, because an undecided parent may hide machines the
census counted.

## 9. What the checker does

The inputs are a cell directory and the census file.

1. Read `summary.json`. If its `format` is not `"bbi9-cell/1"`, `"bbi9-cell/2"`, `"bbi9-cell/3"`, `"bbi9-cell/4"`
   or `"bbi9-cell/5"`, fail. If a format 2 to 5 corridor entry lacks `NONHALT_CPS`, or a format 1 corridor entry has
   it, fail. If a format 3 to 5 corridor entry lacks `NONHALT_RWL`, or a format 1 or 2 corridor entry has it, fail. If
   a format 4 or 5 corridor entry lacks `NONHALT_FAR`, or a format 1 to 3 corridor entry has it, fail. If a format 5
   corridor entry lacks `NONHALT_CPSH`, or a format 1 to 4 corridor entry has it, fail. Let B_d be corridor entry d's
   `max_halt_steps`. If any B_d is above 10,000,000, the producer's largest cap, fail at once.
2. Walk the corridor of (S, K, D), running each machine at depth d for at most B_d steps.
   - If it halts after n ≤ B_d steps, it is a halter. Add `text<TAB>n` to the halter digest. If d < D, add its
     corridor children. Each child is late if its parent is late or if n is above the cap for depth d.
   - Otherwise it is unhalted. Add its text to the unhalted digest. It has no children.
   - Count machines, halters and unhalted machines at each depth, and late machines at depth D. Keep the top 10
     halters at depth D.
3. Read the claims one line at a time. Check that the fields parse, verify the certificate (section 6), count the
   claim by depth and verdict, add the line to the claims digest and its text to the claimed digest, and keep the
   UNKNOWN texts by depth. A certificate whose j is above 10,000,000 fails without being run, because the producer
   never writes one. A NONHALT_CPS certificate whose n or c is out of range fails without being computed, and so
   do a NONHALT_RWL certificate whose b, T or c is out of range, a NONHALT_FAR certificate whose side, n, table or
   e is out of range and a NONHALT_CPSH certificate whose n, H or c is out of range. In a format 1 cell every
   NONHALT_CPS claim fails, in a format 1 or 2 cell every NONHALT_RWL claim fails, in a format 1 to 3 cell every
   NONHALT_FAR claim fails, and in a format 1 to 4 cell every NONHALT_CPSH claim fails.
4. Compare. Each mismatch is a failure with a message.
   - At every depth d, the walk's machines, halters and most halter steps equal entry d's `machines`, `HALT` and
     `max_halt_steps`.
   - When the corridor entries have `halt_steps`, each equals the sum of the steps of the walk's halters at that
     depth.
   - At every depth d, the claims by verdict equal entry d's `NONHALT_CYCLER`, `NONHALT_TRANSLATED`, `NONHALT_CPS`,
     `NONHALT_RWL`, `NONHALT_FAR`, `NONHALT_CPSH` and `UNKNOWN`, and their total equals the walk's unhalted count at
     d. A format 1 entry has no `NONHALT_CPS`, and its NONHALT_CPS count is taken as 0. A format 1 or 2 entry has no
     `NONHALT_RWL`, and its NONHALT_RWL count is taken as 0. A format 1 to 3 entry has no `NONHALT_FAR`, and its
     NONHALT_FAR count is taken as 0. A format 1 to 4 entry has no `NONHALT_CPSH`, and its NONHALT_CPSH count is
     taken as 0.
   - The unhalted digest equals the claimed digest. With the counts, this shows the claims cover exactly the
     unhalted machines.
   - `halter_digest`, `claims`, `claims_digest`, `cell_machines`, `late_cell_machines`, `holdouts`,
     `parent_holdouts` and `top_halters` equal the checker's own values.
   - Both holdout lists hold exactly the sorted UNKNOWN texts. This one comparison is skipped for a cell with an
     amendment of this very summary.json, as section 12 says.
   - The UNKNOWN texts at every depth are digested (section 7, each text without a newline) as `unknown_digest`,
     which check.json records. It is `0000000000000000` when there are none.
   - Every certificate is valid.
   - The census rule (section 8) holds.
5. Write `check.json` into the cell directory, print one line starting with `PASS` or `FAIL`, and exit with 0 on a
   pass, 1 on a fail and 2 on bad usage.

### When claims.idx exists

A checker may check a cell with `claims.idx` this way instead of steps 2 and 3. Steps 1, 4 and 5 stay.

1. Fail if `claims.tsv` exists, if `claims_split` or any entry's `halt_steps` is missing, if the index does not tile
   `claims.tsv.gz` as section 5 says, or if a group's `seq` values do not run 0, 1, 2 and so on.
2. Walk the top group. Then walk every corridor machine at depth s that the top walk reaches, each as its own group,
   whether or not the index names it. Each walk is canonical (section 3) and reads its group's lines in order. For
   each machine M at depth d:
   - If the next unread line's text is M's text, that line is M's claim. A non-halting certificate (cycler,
     translated cycler, NONHALT_CPS, NONHALT_RWL, NONHALT_FAR or NONHALT_CPSH) is verified as in step 3 of the main
     list, and M is unhalted.
     An UNKNOWN claim makes M run for B_d steps. If it halts, fail. Otherwise M is unhalted.
   - Otherwise M runs for B_d steps and must halt, or the check fails. A halter is handled as in step 2 of the main
     list.
   - When a group's walk ends, its lines must be used up.
3. Fail if the index names a group the walk never reaches.
4. Count, digest and compare as in steps 3 and 4 of the main list.

A correct cell passes both ways with the same results. The checker's `--plain` uses steps 2 and 3 even when
`claims.idx` exists.

### check.json and the command line

`check.json` has the keys `format` (`"bbi9-check/1"`), `checker` (name and version), `cell`, `depth`, `pass`,
`failures` (the first 50 messages), `cell_machines`, `census`, `late_cell_machines`, `census_match` (true, false,
or null when skipped), `holdouts`, `parent_holdouts`, `holdout_lists`, `top_halters`, `halter_digest`,
`claims_digest`, `unknown_digest`, `seconds` and `summary_sha256`, the SHA-256 hex of the bytes of `summary.json`. `census` is the
census count of section 8, and null at D ≥ 10, where there is none. `holdout_lists` is `"checked"` when step 4
compared the holdout lists and `"amendment"` when it skipped them (section 12). A check.json written before this key
existed has no `holdout_lists`, and its check compared the lists. A check.json without `unknown_digest` was written
by a checker before 1.7, and section 12 says what that costs. The tracker trusts a check only while
`summary_sha256` matches the current `summary.json`, and a check whose `holdout_lists` is `"amendment"` only with a
passing amendment check as well.

The command line is `python bbi9check.py CELL_DIR --census CENSUS_TSV [--jobs N] [--plain | --python]`, for Python 3.11
or later with the standard library only. Besides the exit codes of step 5, this checker exits with 3 when
`bbi9check-core` (below) fails during a check, and then it writes no check.json. `--jobs` spreads the walk and the
certificate checks over N processes, and it changes no result except `seconds`. When the check uses claims.idx it prints
a line to stderr every 30 seconds while it walks, `progress: M machines, S steps, T s`, the machines walked so far, the
steps simulated for them (each halter's steps and each UNKNOWN machine's bound) and the seconds since the walk began,
and these lines change no result either. The amendment check of section 12 is the same program with `--amend`. The
import check of section 13 is the same program with `--import`, and it alone also uses PyYAML.

**An accelerated checker.** The reference checker is the program above with `--python` (or with `bbi9check-core` not
built), standard-library Python, and its verdict is the one that counts. An accelerated checker is any program that
writes the same check.json as the reference checker would for the same cell, byte for byte apart from `seconds` and
`checker`, and it is sound only insofar as it does. `python bbi9check.py CELL_DIR --census CENSUS_TSV --gpu [--jobs N]`
is one: the indexed check with the UNKNOWN claims run to their bounds on an NVIDIA GPU (`experiments/bbi/bbi9/gpu`) in
batches after the walk, instead of one by one during it. The walk counts each UNKNOWN claim as unhalted meanwhile, which
is what it is in every passing check, and a machine that turns out to halt fails the check with the reference checker's
own message, so a passing `--gpu` check and a passing reference check are the same check.json apart from those two keys,
while a failing `--gpu` check may list other failures than the reference checker's. The GPU runner falls back to the
reference run for a machine whose tape outgrows every width it tries, so every verdict is the reference run's. Its
check.json names the checker `bbi9check 1.10 gpu`, or `bbi9check 1.10 core gpu` when `bbi9check-core` (below) walked, it
prints one more line to stderr, `gpu: ...`, with its counts and seconds, and `--gpu` with `--plain`, `--amend`,
`--import` or `--unknown-digest` is bad usage. A cell without claims.idx is checked the plain way, `--gpu` or not.

The indexed check with `bbi9check-core`, a Rust program in `checker/core` written from this document and the reference
checker and never from the producer, is another, and it runs whenever the program is built. The program walks every
group but the top one, the groups rooted at depth `claims_split`, runs and digests their halters, digests their claims
lines and verifies their NONHALT_CYCLER and NONHALT_TRANSLATED certificates. It hands every other claims line back to
the reference code, which verifies it and runs the UNKNOWN claims as before. Before the program reads a batch of groups,
the reference code inflates every gzip member of the batch with zlib and walks the batch itself when zlib refuses one,
so zlib remains the judge of every member. When the program meets anything it does not handle, such as a gzip member
with header flags, a machine that is neither the next claim nor a halter, lines left over or an UNKNOWN claim that
halts, the reference code walks that batch again. So every failure message is the reference checker's, and a failing
check lists the same failures either way. When the program walked at least one batch itself, check.json names the
checker `bbi9check 1.10 core`, or `bbi9check 1.10 core gpu` with `--gpu`, and otherwise it names the checker as the
reference code does. When the check took on any batch for the program, it prints one more line to stderr, `core: ...`.
Its first number is the batches the check took on, counting those zlib refused before the program saw them, its second
is those the reference code walked itself, and the line also says when the program's build is older than its sources.
`--python` makes the reference code walk every group, and `--python` with `--plain`, `--amend`, `--import` or
`--unknown-digest` is bad usage. When the program is not built, the reference code walks and a `core:` line says so.
When the program fails during a check, the check stops, writes no check.json and exits with 3, and stderr says why.
`cargo build --release` in `checker/core` builds it, and its one dependency is the flate2 crate the producer already
uses.

## 10. Control numbers

**Runs.** `1RB1LB_1LA---` halts after 5 steps on (B, 1). `0RB---_1LA---` halts after 3 steps on (B, 1). `0RB` halts
after 1 step on (B, 0). `0RA` never halts.

**Valid certificates.**

| machine | certificate |
|---|---|
| `0RA` | `NONHALT_TRANSLATED R 1 2` |
| `1RA---` | `NONHALT_TRANSLATED R 1 2` |
| `1RB---_0LB1RB` | `NONHALT_CYCLER 2 4` and `NONHALT_CYCLER 1 3` |
| `1RB---_1LB1LB` | `NONHALT_TRANSLATED L 3 4` |
| `1RB------_2RC------_2LC---2RC` | `NONHALT_TRANSLATED R 2 5` |
| `1RB------_2LB2RB2RB` | `NONHALT_TRANSLATED R 4 7` |

**Invalid certificates.**

| machine | certificate | why |
|---|---|---|
| `1RB---_0LB1RB` | `NONHALT_CYCLER 1 2` | the head positions differ |
| `0RA` | `NONHALT_TRANSLATED R 0 1` | i must be at least 1 |
| `0RA` | `NONHALT_CYCLER 0 1` | the head moved |
| `0RA` | `NONHALT_TRANSLATED L 1 2` | the head goes right |
| `1RB1LB_1LA---` | `NONHALT_CYCLER 0 5` | the configurations differ |
| `1RB------_2RC------_2LC---2RC` | `NONHALT_TRANSLATED R 1 5` | the states after 1 and 5 steps differ |
| `1RB------_2RC------_2LC---2RC` | `NONHALT_CYCLER 2 4` | same state and position, different tape |
| `1RB------_2LB2RB2RB` | `NONHALT_TRANSLATED R 1 4` | the head cell matches, but the window from a to p_i does not |

**Valid NONHALT_CPS certificates.**

| machine | certificate |
|---|---|
| `0RA` | `NONHALT_CPS 1 1` |
| `1RA---` | `NONHALT_CPS 1 2` and `NONHALT_CPS 3 4` |
| `1RB---_0LB1RB` | `NONHALT_CPS 1 4` and `NONHALT_CPS 2 3` |
| `0RB0LA_1LA1RB` | `NONHALT_CPS 1 16` and `NONHALT_CPS 2 40` |
| `1RB---0RB_2LB2RA0LA` | `NONHALT_CPS 2 50` and `NONHALT_CPS 3 73` |
| `1RB0LB---_2LA---0RA` | `NONHALT_CPS 3 17` |
| `0RB---_1LC1RA_0LD---_0RA0LA` | `NONHALT_CPS 4 44` and `NONHALT_CPS 5 62` |

**Invalid NONHALT_CPS certificates.**

| machine | certificate | why |
|---|---|---|
| `1RB1LB_1LA---` | `NONHALT_CPS 2 7` | the machine halts, and C reaches the undefined pair (B, 1) |
| `0RB---_0RC---_1LD---_0LA---` | `NONHALT_CPS 1 4` | it halts after 6 steps on (C, 1), and C reaches that pair, though a pass that expands each member once stops at 4 |
| `1RB---0RB_2LB2RA0LA` | `NONHALT_CPS 1 22` | with n = 1, C reaches an undefined pair |
| `1RB0LB---_2LA---0RA` | `NONHALT_CPS 2 35` | with n = 2, C reaches an undefined pair, though n = 3 closes |
| `1RB0LB---_2LA---0RA` | `NONHALT_CPS 3 16` | C has 17 members, not 16 |
| `1RB0LB---_2LA---0RA` | `NONHALT_CPS 3 18` | C has 17 members, not 18 |
| `0RA` | `NONHALT_CPS 0 1` | n must be at least 1 |
| `0RA` | `NONHALT_CPS 6 1` | n must be at most 5 |
| `1RB2RA1LA_2LA2RB---` | `NONHALT_CPS 5 192` | an undecided depth-5 machine that no n up to 5 closes, and at n = 5 C reaches the undefined pair (B, 2) |
| `0RB` | `NONHALT_CPS 1 2` | B owns no instructions, so C reaches the undefined pair (B, 0) |

A machine can have valid certificates at several n, and a checker accepts each of them. The producer tries n = 1,
2, 3, 4 and 5 in turn and writes the first that closes. When its first rung leaves them UNKNOWN, it gives
`0RB0LA_1LA1RB` the certificate `NONHALT_CPS 1 16`, `1RB---0RB_2LB2RA0LA` `NONHALT_CPS 2 50`, `1RB0LB---_2LA---0RA`
`NONHALT_CPS 3 17` and `0RB---_1LC1RA_0LD---_0RA0LA` `NONHALT_CPS 4 44`.

**Valid NONHALT_RWL certificates.**

| machine | certificate |
|---|---|
| `0RA` | `NONHALT_RWL 1 2 1` |
| `1RA---` | `NONHALT_RWL 1 1 2`, `NONHALT_RWL 1 2 3` and `NONHALT_RWL 1 3 4` |
| `0RB_0LA` | `NONHALT_RWL 1 2 3` |
| `1RB------_2LB2LA0RB` | `NONHALT_RWL 1 2 14`, `NONHALT_RWL 1 3 27`, `NONHALT_RWL 2 2 32`, `NONHALT_RWL 3 2 47`, `NONHALT_RWL 5 2 75` and `NONHALT_RWL 6 3 160` |
| `1RB---------_2LB3LA0RB0RB` | `NONHALT_RWL 1 2 16` and `NONHALT_RWL 2 3 50` |
| `1RB0LB_1LC1RB_---1LA` | `NONHALT_RWL 2 2 45`, `NONHALT_RWL 2 3 72`, `NONHALT_RWL 4 2 93` and `NONHALT_RWL 6 2 141` |
| `1RB2RA1LA_2LA2RB---` | `NONHALT_RWL 1 2 25` and `NONHALT_RWL 3 3 148` |

**Invalid NONHALT_RWL certificates.**

| machine | certificate | why |
|---|---|---|
| `1RB1LB_1LA---` | `NONHALT_RWL 1 2 3` | the machine halts, and a block run reads an undefined pair |
| `0RB` | `NONHALT_RWL 1 2 1` | B owns no instructions, so the second member's block run reads (B, 0) |
| `0RB_0LA` | `NONHALT_RWL 2 2 1` | the first block run never leaves its 2 cells, so it fails at 1,000 steps |
| `1RB0LB_1LC1RB_---1LA` | `NONHALT_RWL 1 2 45` | with b = 1 a block run reads an undefined pair, though b = 2 closes |
| `1RB0LB_1LC1RB_---1LA` | `NONHALT_RWL 5 2 93` | with b = 5 a block run reads an undefined pair, as it does with T = 3, though b = 4 and b = 6 close |
| `1RB------_2LB2LA0RB` | `NONHALT_RWL 1 2 13` | C has 14 members, not 13 |
| `1RB------_2LB2LA0RB` | `NONHALT_RWL 1 2 15` | C has 14 members, not 15 |
| `0RB0LA_1LA1RB` | `NONHALT_RWL 2 2 20000` | a binary counter, and C passes 20,000 members |
| `1RB------_2LB2LA1RB` | `NONHALT_RWL 1 2 6` | it halts, though keeping only (w, T) after a take stops at 6 members |
| `1RB0RA---_2LB2LA1LA` | `NONHALT_RWL 1 2 7` | it halts, though not raising the count when putting stops at 7 members |
| `1RB---0RB_2LB1RA---` | `NONHALT_RWL 1 2 4` | it halts, though trimming 0ᵇ runs next to the head stops at 4 members |
| `1RB1LB_1LA---` | `NONHALT_RWL 2 2 1` | the BB(2) champion, which a repeat rule that ignores the block's contents would accept |
| `0RA` | `NONHALT_RWL 0 2 1` | b must be at least 1 |
| `0RA` | `NONHALT_RWL 7 2 1` | b must be at most 6 |
| `0RA` | `NONHALT_RWL 1 0 1` | T must be at least 1 |
| `0RA` | `NONHALT_RWL 1 4 1` | T must be at most 3 |
| `0RA` | `NONHALT_RWL 1 2 0` | c must be at least 1 |
| `0RA` | `NONHALT_RWL 1 2 20001` | c must be at most 20,000 |

A machine can have valid certificates at several b and T, and a checker accepts each of them. The producer tries
RWL when its first rung and n-gram CPS leave a machine UNKNOWN. It makes two passes, the first allowing at most 300
members and the second at most 3,000. Each pass tries b from 1 to 6, and for each b, T = 2 and then T = 3. Once a
block run fails for some (b, T), that (b, T) is skipped from then on. The producer also gives up a closure whose
members hold more than 100,000 runs in all, and it does not try that (b, T) again in the second pass. `rwl_limit` in
summary.json records only the cap on members, not this cap on runs. The producer writes the first certificate that
closes, so it gives `1RB------_2LB2LA0RB` the certificate `NONHALT_RWL 1 2 14`, `1RB0LB_1LC1RB_---1LA`
`NONHALT_RWL 2 2 45` and `1RB2RA1LA_2LA2RB---` `NONHALT_RWL 1 2 25`.

**Valid NONHALT_FAR certificates.**

| machine | certificate |
|---|---|
| `0RA` | `NONHALT_FAR L 1 0 2` and `NONHALT_FAR R 1 0 1` and `NONHALT_FAR L 2 01 3` |
| `1RA---` | `NONHALT_FAR L 1 00 4` and `NONHALT_FAR R 2 0111 5` |
| `0RB_0LA` | `NONHALT_FAR L 1 0 2` and `NONHALT_FAR R 1 0 2` |
| `1RB---_0LB1RB` | `NONHALT_FAR L 1 00 5` and `NONHALT_FAR R 1 00 4` |
| `0RB0LA_1LA1RB` | `NONHALT_FAR L 1 00 6` and `NONHALT_FAR R 1 00 5` |
| `1RB0LD_1LC1RA_0RB0LC_---1LA` | `NONHALT_FAR L 2 0100 21` and `NONHALT_FAR R 6 010223453355 75` |
| `0RB0LA_1LA1RC_1RB---` | `NONHALT_FAR L 2 0100 14` and `NONHALT_FAR R 4 01231133 27` |
| `1RB1LC_0LA0RB_1LA---` | `NONHALT_FAR R 2 0100 14` and `NONHALT_FAR L 4 01231133 27` |
| `1LB1RC_0RA0LB_1RA---` | `NONHALT_FAR L 2 0100 14` |
| `0RB---0LA_1LA2RC---_2RB------` | `NONHALT_FAR L 3 012011010 30` and `NONHALT_FAR R 4 012322222112 40` |
| `0RB0LA---_1RC------_2LA---1RB` | `NONHALT_FAR L 3 012002022 30` and `NONHALT_FAR R 4 012111311212 40` |
| `1RB2RA1LA_2LA2RB---` | `NONHALT_FAR L 2 010011 18` and `NONHALT_FAR R 3 001212222 26` |
| `1RB0LB---_2LA---0RA` | `NONHALT_FAR L 4 012232113333 31` and `NONHALT_FAR R 4 012111311112 31` |
| `1RB---------------_2LB3LA0RB4RB5LB3RB` | `NONHALT_FAR R 2 010000111111 36` and `NONHALT_FAR L 3 011111121111222222 45` |

**Invalid NONHALT_FAR certificates.**

| machine | certificate | why |
|---|---|---|
| `1RB1LB_1LA---` | `NONHALT_FAR L 1 00 6` | the BB(2) champion halts, and (0, A) is in a |
| `1RB1LB_1LA---` | `NONHALT_FAR R 2 0100 12` | the same on side R |
| `0RB` | `NONHALT_FAR L 1 0 3` | it halts after 1 step, (0, A) –0→ (0, B) –0→ ⊥, though the shortcut that takes a as ⊥ and the nodes with a 0-edge straight to ⊥ accepts it |
| `1RB0LD_1LC1RA_0RB0LC_---1LA` | `NONHALT_FAR R 2 0100 23` | the table that works on side L fails on side R |
| `1RB0LD_1LC1RA_0RB0LC_---1LA` | `NONHALT_FAR L 1 00 16` | with n = 1, (0, A) is in a |
| `1RB0LD_1LC1RA_0RB0LC_---1LA` | `NONHALT_FAR L 2 0101 24` | another table with n = 2, and (0, A) is in a |
| `1RB0LD_1LC1RA_0RB0LC_---1LA` | `NONHALT_FAR L 2 0100 20` | R has 21 edges, not 20 |
| `1RB0LD_1LC1RA_0RB0LC_---1LA` | `NONHALT_FAR L 2 0100 22` | R has 21 edges, not 22 |
| `0RB0LA_1LC0RD_1LA---_0RE1RD_1RA---` | `NONHALT_FAR L 2 0100 34` | a BBi(8) 5×2 holdout that no table with n up to 6 closes on either side |
| `1RB0LD_1LC1RA_0RB0LC_---1LA` | `NONHALT_FAR L 2 0102 21` | the digit 2 is not below n = 2 |
| `0RB` | `NONHALT_FAR R 2 11 4` | δ(0, 0) must be 0, and the shortcut that does not require it accepts this for a machine that halts after 1 step |
| `0RA` | `NONHALT_FAR X 1 0 2` | side must be L or R |
| `0RA` | `NONHALT_FAR L 0 0 2` | n must be at least 1 |
| `0RA` | `NONHALT_FAR L 11 00000000000 2` | n must be at most 10 |
| `0RA` | `NONHALT_FAR L 1 00 2` | the table must have n·k = 1 digit |
| `0RA` | `NONHALT_FAR L 1 0 0` | e must be at least 1 |
| `0RA` | `NONHALT_FAR L 1 0 102011` | e must be at most 102,010 |
| `1RB---` | `NONHALT_FAR L 1 00 6` | it halts after 1 step, though the shortcut a = {⊥} accepts it |
| `0RB` | `NONHALT_FAR L 1 0 2` | it halts after 1 step, though rule 2 only for states that own instructions accepts it |
| `1RB---` | `NONHALT_FAR R 1 00 4` | it halts after 1 step, though rule 1 only for b = 0 accepts it |
| `0RB---_1LA---` | `NONHALT_FAR R 1 00 5` | it halts after 3 steps, though rule 4 only for b = 0 accepts it |
| `1RB---_0LB---` | `NONHALT_FAR L 1 00 5` | it halts after 2 steps, though rule 4 reading w before b accepts it |
| `0RB---_1LA---` | `NONHALT_FAR R 2 0111 10` | it halts after 3 steps, though rule 4 reading only w from (i, t) accepts it, with the true edge count |
| `0RB---_1LA---` | `NONHALT_FAR R 2 0111 9` | it halts after 3 steps, though rule 4 applied once per instance, in one pass, accepts it |
| `0RB---_1LA---` | `NONHALT_FAR R 2 0101 9` | it halts after 3 steps, though rule 3 moving the automaton by the symbol read accepts it |
| `0RA` | `NONHALT_FAR L 2 01 2` | R has 3 edges, as the rules hold at state 1 too, which is never reached from 0, and 2 is the count of a build at the reachable states only |
| the root (empty text) | `NONHALT_FAR L 1 0 2` | the root halts after 0 steps, and (0, A) –0→ ⊥ puts (0, A) in a |
| the root (empty text) | `NONHALT_FAR L 1 0 1` | R has 2 edges, though a checker that gives the empty machine no states accepts it |

With side L and the table `0100`, the test vector `1RB0LD_1LC1RA_0RB0LC_---1LA` gives R these 21 edges,
(0, A) –0→ (1, B), (0, A) –1→ ⊥, (1, A) –0→ (0, B), (1, A) –1→ (0, B) and (1, B), (0, B) –0→ (1, A),
(0, B) –1→ (1, A), (1, B) –0→ (0, B) and (1, B), (1, B) –1→ (0, A), (0, C) –0→ (0, B), (0, C) –1→ (1, A),
(1, C) –0→ (0, B), (1, C) –1→ (0, B), (0, D) –0→ ⊥, (0, D) –1→ (0, A) and (1, A), (1, D) –0→ ⊥, (1, D) –1→ ⊥, and
⊥ –0→ ⊥, ⊥ –1→ ⊥. So a = {⊥, (0, D), (1, D)}, and the 0-paths from (0, A) reach (1, B), (0, B) and (1, A) only.
`1LB1RC_0RA0LB_1RA---` is the mirror image of `1RB1LC_0LA0RB_1LA---` (not a tree machine, but a text a checker
reads), so its side L certificate is the other's side R one. `0RB0LA_1LA1RC_1RB---`, `1RB1LC_0LA0RB_1LA---`,
`0RB---0LA_1LA2RC---_2RB------` and `0RB0LA---_1RC------_2LA---1RB` are four of the eight BBi(5) counters that rung 0,
n-gram CPS and RWL leave UNKNOWN, and the last valid row is one of the three 2-state, 6-symbol parents they leave in
BBi(9) 4×8.

A machine can have valid certificates at several n and on both sides, and a checker accepts each of them. In its
legacy order, the one a summary.json without `decider_order` (section 5) records, the producer tries finite automata
reduction when its first rung, n-gram CPS and RWL leave a machine UNKNOWN, before it runs the machine longer. A
summary.json with `decider_order` names another order, and then the producer tries finite automata reduction in that
place instead. It tries n from 1 to 10, side L before side R at each n, and for each the canonical tables
with n states depth first, and it writes the first certificate that works. Each digit it tries at one position of a
table is one search node. It spends at most 1,000,000 search nodes on a machine, counted across every n and both
sides, and a machine it cannot close within them runs longer. Its search, run on its own, gives `0RA` the
certificate `NONHALT_FAR L 1 0 2`, `1RA---` `NONHALT_FAR L 1 00 4`, `0RB0LA_1LA1RB` `NONHALT_FAR L 1 00 6`, the test
vector `NONHALT_FAR L 2 0100 21`, `1RB2RA1LA_2LA2RB---` `NONHALT_FAR L 2 010011 18`, `1RB0LB---_2LA---0RA`
`NONHALT_FAR L 4 012232113333 31` and `1RB---------------_2LB3LA0RB4RB5LB3RB` `NONHALT_FAR R 2 010000111111 36`. The
eight BBi(5) counters reach finite automata reduction, and the producer gives `0RB0LA_1LA1RC_1RB---`
`NONHALT_FAR L 2 0100 14`, `0RB0LA_1RC---_1LA1RB` `NONHALT_FAR L 2 0100 14`, `1RB---_1LC1RA_0RA0LC`
`NONHALT_FAR L 2 0100 14`, `1RB1LC_0LA0RB_1LA---` `NONHALT_FAR R 2 0100 14`, `0RB---0LA_1LA2RC---_2RB------`
`NONHALT_FAR L 3 012011010 30`, `0RB0LA---_1RC------_2LA---1RB` `NONHALT_FAR L 3 012002022 30`,
`1RB------_2LC---1RA_0RA0LC---` `NONHALT_FAR L 3 012002022 30` and `1RB2LC---_0LA---0RB_2LA------`
`NONHALT_FAR R 3 012011010 30`.

**Valid NONHALT_CPSH certificates.**

| machine | certificate |
|---|---|
| `0RB0LA---_1RC------_2LA---1RB` | `NONHALT_CPSH 3 6 123` and `NONHALT_CPSH 2 2 40` and `NONHALT_CPSH 3 3 85` and `NONHALT_CPSH 3 12 265` and `NONHALT_CPSH 5 12 593` |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 3 6 80` and `NONHALT_CPSH 2 2 34` and `NONHALT_CPSH 3 3 46` and `NONHALT_CPSH 3 12 128` and `NONHALT_CPSH 5 12 199` |
| `1RB2LC---_0LA---0RB_2LA------` | `NONHALT_CPSH 3 6 126` and `NONHALT_CPSH 5 12 608` |
| `1RB------_2LC---1RA_0RA0LC---` | `NONHALT_CPSH 3 6 140` |
| `0RB---0LA_1LA2RC---_2RB------` | `NONHALT_CPSH 3 6 127` |
| `1RB3RA4LB------------_2LA6LB5RB3LB---6LB0RB` | `NONHALT_CPSH 3 6 141` and `NONHALT_CPSH 2 2 52` |
| `1RB3LA4LA0LA1RA_1LC------2RB4RA_---2RA---------` | `NONHALT_CPSH 3 12 458` and `NONHALT_CPSH 3 8 395` |
| `0RB------_1LC---0LE_2RD---1LD_2LE0RD0LA_1LB------` | `NONHALT_CPSH 3 12 296` and `NONHALT_CPSH 4 6 223` |
| `1RB3LC------------_2LA---1LC------0RC_4LB5LA---0RB5LA---` | `NONHALT_CPSH 5 12 756` and `NONHALT_CPSH 4 12 636` |
| `1RB1LA4LB2RB3LB_2LA3LB0RA0LB---` | `NONHALT_CPSH 5 12 19857` |
| `1RB0LC------_0LA------0RF_2LD---------_2LE---------_3LA---------_0RB---0RF---` | `NONHALT_CPSH 3 6 98` and `NONHALT_CPSH 3 1 44` |
| `1RB------_0RC---0LG_1LB1RD---_2RE------_1RF------_2RC------_---0LB---` | `NONHALT_CPSH 3 6 98` and `NONHALT_CPSH 2 2 37` |

**Invalid NONHALT_CPSH certificates.**

| machine | certificate | why |
|---|---|---|
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 3 6 79` | C has 80 members, not 79 |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 3 6 81` | C has 80 members, not 81 |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 3 12 80` | with H = 12, C has 128 members, not the 80 it has with H = 6 |
| `1RB1LA4LB2RB3LB_2LA3LB0RA0LB---` | `NONHALT_CPSH 5 12 19856` | C has 19,857 members, not 19,856 |
| `1RB1LA4LB2RB3LB_2LA3LB0RA0LB---` | `NONHALT_CPSH 3 6 19857` | with n = 3 and H = 6, C reaches an undefined pair, though n = 5 and H = 12 close |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 0 6 80` | n must be at least 1 |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 6 6 80` | n must be at most 5 |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 3 0 80` | H must be at least 1 |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 3 13 80` | H must be at most 12 |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 3 6 0` | c must be at least 1 |
| `1RB------_2LB2LA0RB` | `NONHALT_CPSH 3 6 20001` | c must be at most 20,000 |
| `0RB---_0RC---_1LD---_0LA---` | `NONHALT_CPSH 3 6 10` | section 6's trap machine halts after 6 steps, and C reaches an undefined pair |
| the root (empty text) | `NONHALT_CPSH 1 1 1` | the root halts after 0 steps, and the start member's pair (A, (0, ())) is undefined |
| `1RB2LB---_2LA2RB1LB` | `NONHALT_CPSH 3 6 26` | it halts after 37 steps, though expanding each member once stops at 26 members |
| `1RB2LA1RA_1LB1LA1RC_---2LA2RB` | `NONHALT_CPSH 3 6 61` | a late halter of BBi(8)'s 3×3 cell, which halts after 11,597,631 steps, though expanding each member once stops at 61 members |
| `1RB1RB_1LA---` | `NONHALT_CPSH 3 6 15` | it halts after 3 steps, though using the symbol's number modulo k as its base closes with 15 members |
| `1RB1LB_1LA---` | `NONHALT_CPSH 3 6 11` | the BB(2) champion halts after 5 steps, though using the symbol's number modulo k as its base closes with 11 members |
| `1RB1LA_1LA---` | `NONHALT_CPSH 3 6 4` | it halts after 4 steps, though reading every 0 of section 6 as the first symbol written closes with 4 members |

A machine can have valid certificates at several n and H, and a checker accepts each of them. Four machines of the
valid table, `0RB0LA---_1RC------_2LA---1RB`, `1RB2LC---_0LA---0RB_2LA------`, `1RB------_2LC---1RA_0RA0LC---` and
`0RB---0LA_1LA2RC---_2RB------`, are the four machines of the cell (3, 3) at D = 5 that finite automata reduction
decides in `z5_3x3`, and `1RB------_2LB2LA0RB` is the parent holdout of `x5_3x3` that RWL decides. The other seven are
BBi(9) holdouts, one from each of the cells 2×7, 3×5, 5×3, 3×6, 2×5, 6×4 and 7×3, in the table's order. The 2×5
holdout `1RB1LA4LB2RB3LB_2LA3LB0RA0LB---` is the largest control. At n = 5 and H = 12 its closure meets 347 symbols of
M_H, the blank included, so symbol numbers do not fit in a byte, and C has 19,857 members, 143 below the limit. No
other (n, H) with n from 1 to 5 and H from 1 to 12 closes it within 20,000 members.

In its legacy order, the one a summary.json without `decider_order` (section 5) records, the producer tries
NONHALT_CPSH when its first rung, n-gram CPS, RWL and finite automata reduction leave a machine UNKNOWN, before it
runs the machine longer. A summary.json with `decider_order` names another order, and then the producer tries
NONHALT_CPSH in that place instead. It tries the (n, H) of `cpsh_tries` in order, each with C capped at
`cpsh_limit` members, and it writes the first certificate that closes. Producer 0.6.0 tries (3, 6), then (3, 12),
then (5, 12), each capped at 20,000 members. Its tries, run on their own, give the first five machines of the valid
table and the 2×7, 6×4 and 7×3 holdouts their certificates with (n, H) = (3, 6), the 3×5 and 5×3 holdouts theirs with
(3, 12), and the 3×6 and 2×5 holdouts theirs with (5, 12), each with the c of the matching certificate in the table.

**Corridor counts.** Walk with B = (0, 1, 3, 5, 16) for depths 0 to 4. The cells (4, 1), (2, 5), (3, 3) and (2, 2)
at D = 4 then have 40, 42, 2,256 and 132 machines. With B = (0, 1, 3, 5, 16, 37), the cell (5, 1) at D = 5 has 96.
These bounds are the most steps any halter at each depth runs in the whole tree, so the counts are exact.

**Census counts.** The cells (9, 1), (9, 10) and (2, 10) at D = 9 have census counts 2,560, 2,560 and 19,506.

**The 2×10 control at D = 10.** The cell (2, 10) at D = 10 is the smallest cell of BBi(10) within reach. Its corridor
has 1, 4, 24, 78, 396, 1,734, 8,292, 37,584, 176,574, 795,492 and 3,575,136 machines at depths 0 to 10, so
`cell_machines` is 3,575,136. None of them is late, and producer 0.5.0 leaves 0 holdouts and 0 parent holdouts. Its
best halter is `1RB0LB------------------------_2LA---3RA4LA5RA6LA7RA8LA9RA---`, which halts after 89 steps, and its
`halter_digest` is `2f8306c19cece9d5`. A correct checker passes it with `census: null` and `census_match: null`. Its
corridor counts at depths 0 to 8 equal the census nodes summed over the corridor shapes, and at depth 9 the pred sum.
The sums are exact because no machine of the cell is late at the real caps. With the caps 4,000,000 steps for an
ancestor at depths 0 to 7 and 60 steps from depth 8, 12 cell machines are late, each through an ancestor at depth 9,
since no halter at depth 8 runs more than 55 steps. With the caps 3 and 20 all 3,575,136 are late. Past depth 9 the
known-machines registry's reaches are the independent lower bound on a cell's best halter, checked by the tracker and
not by the checker.

**Digests.** h(`a`) = `ca978112ca1bbdca`. The digest of no lines is `0000000000000000`. The digest of the lines `a`
and `b` is `08bb6928ca551714` in either order.

**The smallest cell, (1, 1) at D = 1.** The corridor is the root (halts after 0 steps), `0RA` (the claim
`0RA<TAB>NONHALT_TRANSLATED<TAB>R<TAB>1<TAB>2`) and `0RB` (halts after 1 step). Its `halter_digest` is
`b51b47683164cd9e`, its `claims_digest` is `2c5371185238a315` and its `top_halters` is
`[{"machine": "0RB", "steps": 1}]`.

**Amendments.** Fixture `a5_3x3` is fixture `x5_3x3` (format 2) amended by producer 0.4.0. Its U has 21 machines,
1 at depth 4 and 20 at depth 5. The amendment proves 17 of them, all NONHALT_RWL, 1 at depth 4 and 16 at depth 5, so
`amended` is 17 and `amend_digest` is `284aa25f3562df2f`. It leaves 4 holdouts and 0 parent holdouts. Fixture
`b5_3x3` is fixture `d5_3x3` (format 1) amended the same way. Its U has 140 machines, 14 at depth 4 and 126 at depth
5. The amendment proves 136 of them, NONHALT_CPS 13 at depth 4 and 106 at depth 5 and NONHALT_RWL 1 at depth 4 and 16
at depth 5, so `amended` is 136 and `amend_digest` is `80d563c0067b74ab`. It too leaves 4 holdouts and 0 parent
holdouts. In both, the holdout lists equal `y5_3x3`'s, every line of `amend.tsv` equals `y5_3x3`'s claim for its
text, and with no parent holdouts left the census rule holds, with the census count 35,848 and 35,848 cell machines,
none of them late.

Fixture `g5_3x3` is fixture `y5_3x3` (format 3) amended by producer 0.5.0. Its U has 4 machines, 0 at depth 4 and 4
at depth 5. The amendment proves all 4, NONHALT_FAR at depth 5, so `amended` is 4 and `amend_digest` is
`46c032d54afa7598`. It leaves 0 holdouts and 0 parent holdouts. Fixture `h5_3x3` is fixture `d5_3x3` (format 1)
amended the same way. Its U has 140 machines, 14 at depth 4 and 126 at depth 5. The amendment proves all 140,
NONHALT_CPS 13 at depth 4 and 106 at depth 5, NONHALT_RWL 1 at depth 4 and 16 at depth 5 and NONHALT_FAR 4 at depth 5,
so `amended` is 140 and `amend_digest` is `c79596955175ea43`. It too leaves 0 holdouts and 0 parent holdouts. In both,
the holdout lists equal `z5_3x3`'s, which are empty, every line of `amend.tsv` equals `z5_3x3`'s claim for its text,
and with no parent holdouts left the census rule holds, with the census count 35,848 and 35,848 cell machines, none of
them late.

**History n-gram CPS fixtures.** Fixtures `p5_3x3` and `q5_3x3` are the cell (3, 3) at D = 5 made by producer 0.6.0
with finite automata reduction switched off. Each has 35,848 cell machines, none of them late, 11,224 claims, 0
holdouts and 0 parent holdouts, and the `halter_digest` `53360f3d608bdd11` and the `top_halters` of `z5_3x3`. Their
corridor counts are `z5_3x3`'s, but with NONHALT_FAR 0 at every depth and NONHALT_CPSH 4 at depth 5. Every claim
equals `z5_3x3`'s for its text but those of the four machines that `z5_3x3` decides by NONHALT_FAR, which here are
`NONHALT_CPSH 3 6 123` for `0RB0LA---_1RC------_2LA---1RB`, `NONHALT_CPSH 3 6 126` for
`1RB2LC---_0LA---0RB_2LA------`, `NONHALT_CPSH 3 6 140` for `1RB------_2LC---1RA_0RA0LC---` and
`NONHALT_CPSH 3 6 127` for `0RB---0LA_1LA2RC---_2RB------`. So `p5_3x3` and `q5_3x3` share the `claims_digest`
`05cc358c70dca773`. Fixture `s5_3x3` is the same run as `p5_3x3` with history n-gram CPS switched off too. It has the
same cell machines, claims count, `halter_digest` and `top_halters`, 4 holdouts and 0 parent holdouts. Its holdout
list is `r5_3x3`'s, and every claim equals `r5_3x3`'s for its text, the four machines UNKNOWN, so its `claims_digest`
is `r5_3x3`'s, `7c316136fa6ab2a1`.

Fixture `t5_3x3` is fixture `s5_3x3` (format 5) amended by producer 0.6.0 with finite automata reduction switched
off, so its `amend.json` has no `far_max_n` and has the `cpsh_tries` `"3:6,3:12,5:12"`. Its U has 4 machines, 0 at
depth 4 and 4 at depth 5. The amendment proves all 4, NONHALT_CPSH at depth 5, so `amended` is 4 and `amend_digest`
is `d6525be49e55ecbf`. It leaves 0 holdouts and 0 parent holdouts. Fixture `u5_3x3` is fixture `y5_3x3` (format 3)
amended the same way, with the same U, the same lines and the same `amend_digest`. The producer tried history n-gram
CPS alone on `t5_3x3`'s U, since its base was made by producer 0.6.0, and the whole ladder on `u5_3x3`'s, since its
base was made by producer 0.3.0. In both, the holdout lists equal `p5_3x3`'s, which are empty, every line of
`amend.tsv` equals `p5_3x3`'s claim for its text, and with no parent holdouts left the census rule holds, with the
census count 35,848 and 35,848 cell machines, none of them late.

The table of normal-form maps below gives, for each machine, the map of section 13 or `no map`. Its N column is the
map's bound B_d, the most steps step 2 may run, and not the N of a `{bbi: N}` list.

**Normal-form maps.**

| machine | N | map | why |
|---|---|---|---|
| `1RB------_2LC---1RA_0RA0LC---` | 33 | `1RB------_2LC---1RA_0RA0LC---` | a 1RB-first holdout is its own map |
| `1RB2LC---_0LA---0RB_2LA------` | 33 | `1RB2LC---_0LA---0RB_2LA------` | a 1RB-first holdout is its own map |
| `0RB0LA---_1RC------_2LA---1RB` | 33 | `1RB------_2LC---1RA_0RA0LC---` | A1 and C0 target A, so A0 stays and runs again |
| `0RB0LA---_1RC------_2LA---1RB` | 5 | `1RB------_2LC------_0RA0LC---` | C2 has not run after 5 steps from s, so the map leaves it out |
| `0RB---0LA_1LA2RC---_2RB------` | 33 | `1RB2LC---_0LA---0RB_2LA------` | the first move from s is L, so the map mirrors |
| `0RB---_1LA---` | 3 | `1RB---_0LA---` | A0 runs again on the way to the halt |
| `0RB---_1LA---` | 1 | `1RB---` | A0 has not run again after 1 step from s, so the map leaves it out |
| `0RA` | 1 | no map | the prefix enters A twice |
| `0RB_0RC_0LA` | 5 | no map | the prefix enters A again |
| `1RA---` | 1 | no map | the map would start `1RA` |
| `0RB1LC_1LC1LA_1RB---` | 16 | `1RB1RC_1LA---_---1RB` | A0 stays since B1 targets A, but it never runs again, so the map leaves it out |
| `0RB------_1LC------_2RC2RB0LC` | 33 | `1RB------_2LB2LA0RB` | nothing targets A, so A0 drops |
| `0RB------_1LC------_2RC2RB0LC` | 4 | `1RB------_2LB2LA---` | C2 has not run after 4 steps from s, so the map leaves it out |
| `0RB---_0RC---_1LD---_1RC---` | 5 | `1RB---_1LA---` | A0 drops, and then B0 |
| `0RB---_1LA1RC` | 5 | no map | an instruction into C, which owns nothing |
| `0RB---_1LC0RB_0LD---_1LE---_1RF0LF_1LB1RA` | 2,655 | `1RB0LA_0RC---_1RD---_1LE0RE_1RA1LF_0LA---` | F1 targets A, so A0 stays |
| `0RB---_1LC0RB_0LD---_1LE---_1RF0LF_1LB1RA` | 18 | `1RB0LA_0RC---_1RD---_1LE0RE_---1LF_0LA---` | F0 has not run after 18 steps from s, so the map leaves it out |
| `0RB---_1LC0RB_0LD---_1LE---_0RE0LF_1RF1LB` | 2,655 | `1RB0LA_0RC---_1RD---_0LD0RE_1LE1RA` | nothing targets A, so A0 drops |
| `0RB---_1LC0RB_0LD---_1LE---_0RE0LF_1RF1LB` | 9 | `1RB---_0RC---_1RD---_0LD0RE_1LE1RA` | B1 has not run after 9 steps from s, so the map leaves it out |
| `1RB---_0RC0RB_0RD1LF_1LE---_0LE1RA_1LB---` | 2,655 | `1RB---_0RC0RB_0RD1LF_1LE---_0LE1RA_1LB---` | a 1RB-first survivor is its own map |

The steps in the why column are counted from s, as step 2 of section 13 counts them. The first four machines of the
table are the holdouts of `y5_3x3`, and the two 0RB-first ones map to the two 1RB-first ones. `0RB---_1LA---` halts
after 3 steps, so it is never in V, and its map is only a function here. Row 12 is a holdout of `x5_3x3` whose map is
that fixture's parent holdout `1RB------_2LB2LA0RB`, one instruction shorter. Its twin `0RB------_1RC------_2LC2LB0RC`
maps to the same text without mirroring. Rows 16 to 20 hold the three six-state survivors of
`experiments/bbi/results/mxdys_s6_d9/survivors_6state.txt`, with the bound 2,655, the `max_halt_steps` at depth 9 of
the cell (6, 2). The first maps to the 1RB form that `experiments/bbi/notes.md` gives for it. The second maps to the 1RB
form given there less its row F, whose pair the map drops, so its map has eight instructions.

Two of the rows worked through. A trace step reads "state@position reads r, instruction, next state@position", with
positions from 0 at the start.

- `0RB0LA---_1RC------_2LA---1RB`. The prefix is the one step A0 = `0RB`, so p = 1 and s = B. A1 and C0 target A,
  so step 1b drops nothing. From B@1 on a blank tape, B@1 reads 0, `1RC`, C@2. C@2 reads 0, `2LA`, A@1. A@1 reads
  1, `0LA`, A@0. A@0 reads 0, `0RB`, B@1. B@1 reads 0, `1RC`, C@2. C@2 reads 2, `1RB`, B@3. The pairs are first
  executed in the order B0, C0, A1, A0, C2, so every pair has run after 6 steps. B, C and A were first entered in that
  order and become A, B and C. The first move is R, so nothing mirrors.
- `0RB---0LA_1LA2RC---_2RB------`. Again p = 1 and s = B. B@1 reads 0, `1LA`, A@0. A@0 reads 0, `0RB`, B@1. B@1
  reads 1, `2RC`, C@2. C@2 reads 0, `2RB`, B@3. B@3 reads 0, `1LA`, A@2. A@2 reads 2, `0LA`, A@1. The pairs are
  first executed in the order B0, A0, B1, C0, A2, and B, A and C become A, B and C. The first move is L, so every L
  and R swap.

**Imports.** Fixture `m5_3x3` is `y5_3x3` with the `check.json` of the full check and an import of the registry
`checker/fixtures/lists/lists.yaml`. Its V is the four holdouts at depth 5 and no parents, and the map's bound is
B_5 = 33 for each of them. The bounds of the depths below are B_3 = 5 and B_4 = 16. Lists `fx-bb3x3`, `fx-cell` and
`fx-bbi5` cover the cell with `decides: true` and all speak our language, and `fx-off` covers it with `decides: false`
and is left out. fx-bb3x3's kept lines are two of kind 2 (`1RB------_2LC---1RA_0RA0LC---`, a holdout of ours, and
`1RB1LA_1LB1LB` over the certified `1RB---_1LB1LB`) and one of kind 3 (`1RB1LB_1LA---`, which halts after 5 steps
with B_3 = 5), and its fourth line has six instructions and is not kept. fx-bbi5's one line is kind 2, a holdout of
ours. No list has a stranger. The import has 3 lines, `import_digest` `3b783303fee43fd8`, decided `fx-bb3x3` 2 and
`fx-cell` 1 and `fx-bbi5` 0 (all holdouts, no parents), `maker_holdouts` 0 and 0, and leaves the holdout
`0RB0LA---_1RC------_2LA---1RB`, which every list leaves open (fx-cell lists it, and fx-bb3x3 and fx-bbi5 list its
map).

Why each line is there. `0RB---0LA_1LA2RC---_2RB------` maps to `1RB2LC---_0LA---0RB_2LA------`, which no kept line
of fx-bb3x3 equals, contains or extends, so fx-bb3x3, first in registry order, decides both of them. The prefixes of
that map in step 2's order are `1RB---`, `1RB---_0LA---`, `1RB2LC---_0LA------` and
`1RB2LC---_0LA------_2LA------`, and none is a line. `1RB------_2LC---1RA_0RA0LC---` is a line of fx-bb3x3, and
fx-cell decides it, as a text of its `made_from` file that it does not list. `0RB0LA---_1RC------_2LA---1RB` is
fx-cell's line, and its map `1RB------_2LC---1RA_0RA0LC---` is a line of fx-bb3x3 and of fx-bbi5, so nothing decides
it.

**Proven values.** The registry `checker/fixtures/lists/lists_proven.yaml` is the fixture registry with one more entry
at its end, `fx-proven`, with the domain `{bbi: 5}`, the empty file `data/fx_off.txt`, `entries: 0`, `decides: true`
and `proven: 1`. An import of `m5_3x3` from it has 4 lines, every one `NONHALT_PROVEN` naming `fx-proven`, with
`import_digest` `de790c7198fd7c3a`, `never_halts` and `decided` 4 and 0 for fx-proven and 0 and 0 for every other
list, and `holdouts` 0 and `parent_holdouts` 0. Each of the four maps has 5 instructions, so it lies in the domain,
and the prefix is one step for the two 0RB-first holdouts and none for the others, so B_5 − p is 32 or 33, above 1.
fx-proven is last in registry order and still named, since a proven value is named before a list. The holdout
`0RB0LA---_1RC------_2LA---1RB`, which every list of the import above leaves open, would never halt by the
fixture's made-up value of 1. With a registry of one empty `{bbi: 4}` list, fx-four, with `decides: true`, an import
of `x5_3x3` gives `DECIDED_LIST` lines for the parent holdout `1RB------_2LB2LA0RB` and for the holdout of the
table's row 12 and its twin, whose A0 drops, and a hand-written line naming fx-four for a five-pair holdout such as
`1RB------_2LC---1RA_0RA0LC---` fails, since its pairs after step 1b, 5, exceed 4. With `proven: 0` on that entry the
same three lines are `NONHALT_PROVEN`, and such a line for a five-pair holdout fails, since its map has 5
instructions, more than 4.

## 11. Fixtures

`checker/fixtures/` holds producer output for small cells, `d1_1x1`, `d4_3x3`, `d4_4x1`, `d5_3x3` and `d9_9x1`
(each name gives D and the cell), with the census at `census.tsv` beside this file. `i1_1x1`, `i4_3x3`, `i5_3x3`
and `i9_9x1` hold the same cells with `claims.idx`, at split depths 1, 2, 3 and 5. These nine are in format 1.
`c5_3x3` and `x5_3x3` are in format 2, made by producer 0.2.0. They hold the cell (3, 3) at D = 5, `c5_3x3` with a
plain `claims.tsv` and `x5_3x3` with `claims.idx` at split depth 3, and each holds NONHALT_CPS claims. `r5_3x3` and
`y5_3x3` are in format 3, made by producer 0.3.0. They hold the same cell, `r5_3x3` with a plain `claims.tsv` and
`y5_3x3` with `claims.idx` at split depth 3, and each holds NONHALT_RWL claims. `a5_3x3` and `b5_3x3` are amended
cells (section 12), made by producer 0.4.0 from copies of `x5_3x3` (format 2, with `claims.idx`) and of `d5_3x3`
(format 1, with a plain `claims.tsv`). So `a5_3x3`'s amendment adds NONHALT_RWL lines to a format 2 cell, and
`b5_3x3`'s adds NONHALT_CPS and NONHALT_RWL lines to a format 1 cell. Each holds its base's `summary.json` and
claims files, the `check.json` that checker 1.3's full check wrote before the amendment (so it has no
`holdout_lists`), the amendment's `amend.json` and plain `amend.tsv`, and the amended holdout lists, which equal
`y5_3x3`'s.

`f5_3x3` and `z5_3x3` are in format 4, made by producer 0.5.0. They hold the cell (3, 3) at D = 5, `f5_3x3` with a
plain `claims.tsv` and `z5_3x3` with `claims.idx` at split depth 3, and each holds four NONHALT_FAR claims at depth 5
and no holdouts. `g5_3x3` and `h5_3x3` are amended cells made by producer 0.5.0 from copies of `y5_3x3` (format 3,
with `claims.idx`) and of `d5_3x3` (format 1, with a plain `claims.tsv`). So `g5_3x3`'s amendment adds NONHALT_FAR
lines to a format 3 cell, and `h5_3x3`'s adds NONHALT_CPS, NONHALT_RWL and NONHALT_FAR lines to a format 1 cell. Each
holds its base's `summary.json` and claims files, the `check.json` that checker 1.4's full check wrote before the
amendment, the amendment's `amend.json` and plain `amend.tsv`, and the amended holdout lists, which equal `z5_3x3`'s
and are empty.

`p5_3x3` and `q5_3x3` are in format 5, made by producer 0.6.0 with finite automata reduction switched off. They hold
the cell (3, 3) at D = 5, `p5_3x3` with a plain `claims.tsv` and `q5_3x3` with `claims.idx` at split depth 3. So the
four machines that `z5_3x3` decides by NONHALT_FAR carry NONHALT_CPSH claims here, and each fixture has no holdouts.
`s5_3x3` is the same run as `p5_3x3` with finite automata reduction and history n-gram CPS both switched off, in
format 5 with a plain `claims.tsv`, and its four holdouts are those four machines. `t5_3x3` and `u5_3x3` are amended
cells made by producer 0.6.0 with finite automata reduction switched off, from copies of `s5_3x3` (format 5, with a
plain `claims.tsv`) and of `y5_3x3` (format 3, with `claims.idx`). So each amendment adds NONHALT_CPSH lines for
those four machines. Each holds its base's `summary.json` and claims files, the `check.json` that checker 1.10's full
check wrote before the amendment, the amendment's `amend.json` and plain `amend.tsv`, and the amended holdout lists.

A correct checker passes all of them, and passes `a5_3x3`, `b5_3x3`, `g5_3x3`, `h5_3x3`, `t5_3x3` and `u5_3x3` with
`--amend` too. Its full check of those six skips the holdout lists. If one fails, the producer may be at fault, so
report the failure rather than change the checker to agree.

`m5_3x3` holds an import (section 13). It is a copy of `y5_3x3` with the `check.json` that checker 1.4's full check
wrote and an import of the registry `checker/fixtures/lists/lists.yaml` that the importer made, with `importer`
`bbi9 imports 2.0`. The registry's hand-made list files are in `checker/fixtures/lists/data`. Section 10 gives the
import's numbers. A correct checker passes `m5_3x3`, and passes it with
`--import --lists checker/fixtures/lists/lists.yaml --data checker/fixtures/lists` too. If it fails, report the failure
rather than change the checker to agree.

## 12. Amendments

An amendment reruns only a cell's holdouts. A later producer gives each UNKNOWN machine of the cell to its deciders
and writes the certificates they find, and the holdout lists shrink to the machines it leaves. The amendment check
verifies those certificates and the shorter lists. Everything else rests on the cell's full check (section 9), which
must already have passed.

### The files

A cell directory may hold an amendment. The producer writes `amend.json`, the amended claims `amend.tsv` and new
holdout lists, and the amendment check writes `amend_check.json`. `amend.tsv` may be `amend.tsv.gz` instead, the
gzip of the same bytes, read as `claims.tsv.gz` is (section 5), so it may hold several gzip members. If both exist, a
checker reads `amend.tsv`.

A cell has at most one amendment. A newer amendment replaces the older one, and a full rerun of the cell removes it.
Every amendment is made against the UNKNOWN machines of the cell's full run, never against an earlier amendment. So
a newer amendment's `amend.tsv` again has a line for each of those machines that it proves, and there is never a
chain of amendments to check.

The base set U is the set of texts of the UNKNOWN claims in the cell's claims file (section 5), at every depth. An
amendment never changes `summary.json` or the claims file, which still describe the full run. The depth of a text is
its machine's number of defined pairs (section 1).

### amend.tsv

There is one line for each machine of U that the amendment proves, and there are no other lines. A line has the
syntax of a claims line (section 5), and it may use the certificates that amend.json's `claims_format` allows, as
summary.json's `format` does for the claims file. No line is UNKNOWN, and no text is on two lines. The lines are
sorted in byte order, and every line ends with a newline. An amendment that proves nothing has an empty `amend.tsv`.

### amend.json

A JSON object. A checker uses these keys and ignores any others, and each of these keys is required.

- `format` is `"bbi9-amend/1"`.
- `cell` is `[S, K]` and `depth` is D, as in summary.json.
- `base_summary_sha256` is the SHA-256 hex of the bytes of the `summary.json` that the amendment was made from.
- `claims_format` is `"bbi9-cell/2"`, `"bbi9-cell/3"`, `"bbi9-cell/4"` or `"bbi9-cell/5"`, and it is not older than
  summary.json's `format` (the formats go from oldest to newest in the order 1, 2, 3, 4, 5). It is the cell format of
  section 5 whose certificates the lines of `amend.tsv` may use. Producer 0.4.0 writes `"bbi9-cell/3"`, producer
  0.5.0 writes `"bbi9-cell/4"`, and producer 0.6.0 writes `"bbi9-cell/5"`.
- `corridor` is a list of D + 1 objects. Entry d describes depth d and has the keys
  - `depth`, which is d
  - `NONHALT_CYCLER`, `NONHALT_TRANSLATED` and `NONHALT_CPS`, how many lines of `amend.tsv` at depth d have each
    verdict
  - `NONHALT_RWL`, how many have that verdict, when `claims_format` is `"bbi9-cell/3"`, `"bbi9-cell/4"` or
    `"bbi9-cell/5"`. An entry of a `"bbi9-cell/2"` amendment does not have this key.
  - `NONHALT_FAR`, how many have that verdict, when `claims_format` is `"bbi9-cell/4"` or `"bbi9-cell/5"`. An entry
    of a `"bbi9-cell/2"` or `"bbi9-cell/3"` amendment does not have this key.
  - `NONHALT_CPSH`, how many have that verdict, when `claims_format` is `"bbi9-cell/5"`. An entry of a
    `"bbi9-cell/2"`, `"bbi9-cell/3"` or `"bbi9-cell/4"` amendment does not have this key.
  - `UNKNOWN`, how many machines of U at depth d no line of `amend.tsv` names
- `holdouts` and `parent_holdouts` count the machines of U that no line of `amend.tsv` names, at depth D and at
  depths below D.
- `amended` is the number of lines of `amend.tsv`, and `amend_digest` is the digest (section 7) of those lines.

The keys `producer`, `caps`, `tc_windows`, `threads` and `seconds` are for people to read. `caps` and `tc_windows` are
summary.json's, which the producer used. amend.json may also carry, for people to read, the keys of section 5 that
record the search settings, `tc_records` and the keys of the deciders, with the same meanings. Producer 0.6.0 writes
`tc_records` from the base summary.json and each decider's keys for the settings it was given, leaving out the keys
of a decider it was given switched off. A checker never uses these keys.

### The holdout lists of an amended cell

With an amendment, the two holdout lists of section 5 hold the texts of U less the texts of `amend.tsv`, at depth D
and at depths below D, sorted in byte order as before. The cell's counts after the amendment are summary.json's with
each amended machine moved from UNKNOWN to the verdict of its line.

### The full check of an amended cell

Step 4 of section 9 compares both holdout lists with the UNKNOWN texts of the claims. A full check skips that one
comparison only when `amend.json` exists, is a JSON object, and its `base_summary_sha256` is the SHA-256 hex of the
bytes of summary.json. It then records `"holdout_lists": "amendment"` in check.json and says so in the line it
prints, and the amendment check makes the comparison instead. Otherwise the full check compares the lists as section
9 says and records `"holdout_lists": "checked"`, so lists left by an amendment of another summary.json fail it.
Everything else in the full check is unchanged. It never reads `amend.tsv` and never judges the amendment.

A check.json whose `holdout_lists` is `"amendment"` counts for nothing without a passing amendment check of the same
summary.json.

### The amendment check

The inputs are the cell directory and the census file. The check passes only when none of the steps below fails.
Each failure adds a message. A step that needs something an earlier failure left unread, such as amend.json's keys
after step 2 fails, is skipped.

1. Read summary.json and check.json. Fail if either is missing or is not a JSON object, if check.json's `pass` is not
   true, or if its `summary_sha256` is not the SHA-256 hex of the bytes of summary.json. An amendment rests on the
   full check, so a cell without a passing one cannot be amended. check.json's `holdout_lists` may be either value or
   missing. The amendment check never repeats the full check.
2. Read amend.json. Fail if it is missing or is not a JSON object, if one of the keys a checker uses is missing, if
   `format` is not `"bbi9-amend/1"`, if `claims_format` is not `"bbi9-cell/2"`, `"bbi9-cell/3"`, `"bbi9-cell/4"` or
   `"bbi9-cell/5"` or is older than summary.json's `format`, or if `cell` or `depth` differs from summary.json's. Fail
   if `corridor` is not a list of D + 1 objects, entry d with `depth` d and the count keys above, `NONHALT_RWL` among
   them exactly when `claims_format` is `"bbi9-cell/3"`, `"bbi9-cell/4"` or `"bbi9-cell/5"`, `NONHALT_FAR` among them
   exactly when it is `"bbi9-cell/4"` or `"bbi9-cell/5"`, and `NONHALT_CPSH` among them exactly when it is
   `"bbi9-cell/5"`. Fail if `base_summary_sha256` is not the SHA-256 hex of the bytes of summary.json.
3. Read every line of the claims file by the rules of section 5. That is `claims.tsv` if it exists, and otherwise
   `claims.tsv.gz`, all its gzip members in order. Fail if neither exists, or if `claims.idx` exists and so does
   `claims.tsv`. Count the lines and digest them (section 7, each line without its newline). Fail unless the count
   equals summary.json's `claims` and the digest equals its `claims_digest`, which shows that these are the lines the
   full check checked. U is the set of texts of the UNKNOWN lines. Fail unless, at every depth d, the number of
   UNKNOWN lines equals entry d's `UNKNOWN` in summary.json's `corridor`. The checker takes U from the claims file
   alone, never from the producer's lists or from amend.json. With `claims.idx` it may split this scan by gzip
   member, and the count and digest check what it read.
   When the cell has neither `claims.tsv` nor `claims.tsv.gz`, this step runs instead. Fail unless check.json has
   `unknown_digest` (section 9). U is the union of the texts of the cell's two lists of section 5 and the texts of the
   lines of `amend.tsv`. Fail if a text is in two of those three files or does not parse. Fail unless the digest of U
   (section 7, each text without a newline) equals `unknown_digest` and, at every depth d, the number of texts of U at
   depth d equals entry d's `UNKNOWN` in summary.json's `corridor`.
4. Read `amend.tsv`, or `amend.tsv.gz` when there is no `amend.tsv`. Fail if neither exists. Fail on each line that
   does not end with a newline, does not parse as a claims line (section 5), is UNKNOWN, has a text that is not in U
   or that an earlier line has, or does not come after the line before it in byte order. Fail on each line whose
   certificate is not valid by section 6, with the limits of step 3 of section 9 and with `claims_format` in place of
   summary.json's `format`. So when `claims_format` is `"bbi9-cell/2"`, every NONHALT_RWL line fails, when it is
   `"bbi9-cell/2"` or `"bbi9-cell/3"`, every NONHALT_FAR line fails, and when it is `"bbi9-cell/2"`, `"bbi9-cell/3"`
   or `"bbi9-cell/4"`, every NONHALT_CPSH line fails.
5. Count the lines of `amend.tsv` at each depth by verdict, and the machines of U at each depth that no line names.
   Fail unless amend.json's `corridor` entry d holds these numbers in `NONHALT_CYCLER`, `NONHALT_TRANSLATED`,
   `NONHALT_CPS`, `NONHALT_RWL`, `NONHALT_FAR`, `NONHALT_CPSH` and `UNKNOWN`. A `"bbi9-cell/2"` entry has no
   `NONHALT_RWL`, and its NONHALT_RWL count is taken as 0. A `"bbi9-cell/2"` or `"bbi9-cell/3"` entry has no
   `NONHALT_FAR`, and its NONHALT_FAR count is taken as 0. A `"bbi9-cell/2"`, `"bbi9-cell/3"` or `"bbi9-cell/4"`
   entry has no `NONHALT_CPSH`, and its NONHALT_CPSH count is taken as 0. Fail unless `holdouts` and
   `parent_holdouts` equal the numbers of machines of U that no line names at depth D and at depths below D,
   `amended` equals the number of lines, and `amend_digest` equals their digest (section 7, each line without its
   newline).
6. Fail unless the holdout list `BBi{D}_{S}x{K}_holdouts_unofficial.txt` is exactly the texts of U at depth D that no
   line of `amend.tsv` names, sorted in byte order, each followed by a newline, and the parent holdout list
   `BBi{D}_{S}x{K}_parent_holdouts_unofficial.txt` is the same for the depths below D. A missing list fails. When no
   text is left, the list is an empty file.
7. Apply the census rule (section 8) with the parent holdouts that the amendment leaves. When none are left and
   D ≤ 9, read the census count of (S, K, D) from the census file, and fail unless summary.json's `cell_machines` less
   its `late_cell_machines` equals it. When some are left, the comparison is skipped. At D ≥ 10 it is skipped the
   same way, since there is no census count (section 8).

Then write `amend_check.json` into the cell directory, print one line starting with `PASS` or `FAIL`, and exit with
0 on a pass, 1 on a fail and 2 on bad usage. `amend_check.json` has the keys `format` (`"bbi9-amend-check/1"`),
`checker` (name and version), `cell` and `depth` (summary.json's), `pass`, `failures` (the first 50 messages),
`holdouts`, `parent_holdouts`, `amended`, `amend_digest`, `census` (the census count, read whether or not the
comparison is made, and null at D ≥ 10), `census_match` (true, false, or null when skipped), `seconds`,
`summary_sha256` and `amend_sha256`, the SHA-256 hex of the bytes of `summary.json` and of `amend.json`. `holdouts`,
`parent_holdouts`, `amended` and `amend_digest` are the checker's own values. On a fail, a value the checker could
not compute is null. The amendment check never writes check.json, and the full check never writes
`amend_check.json`.

The tracker trusts an amendment check only while it passes, its `summary_sha256` and `amend_sha256` match the
current `summary.json` and `amend.json`, and check.json passes for that `summary.json`. The cell's holdouts, parent
holdouts and census match are then amend_check.json's. A cell with `amend.json` and no such amendment check counts
as unchecked, whatever its check.json says.

The command line is `python bbi9check.py CELL_DIR --amend --census CENSUS_TSV [--jobs N]`. `--jobs` spreads the
claims scan (over the gzip members when `claims.idx` exists) and the certificate checks over N processes, and it
changes no result except `seconds`. `--amend` with `--plain` is bad usage.

### Why this is enough

The full check showed that the claims cover exactly the corridor's unhalted machines and that every claim but the
UNKNOWN ones is valid. check.json binds that check to summary.json by `summary_sha256`. Step 2 binds the amendment
to the same summary.json, and step 3 binds the claims file to it by its count and digest. The amendment check then
shows that each newly proved machine was one of the UNKNOWN machines and has a valid certificate, and that the lists
hold the rest. So every corridor machine is a checked halter, a checked non-halter or a listed holdout, as after a
full run, and the census rule applies as it does there.

Without the claims file, `unknown_digest` and the per-depth UNKNOWN counts, bound to summary.json by check.json's
`summary_sha256`, fix U up to a digest collision, the trust the claims digest already carries.

### Producing and reproducing

The producer reads the cell, the depth, `caps` and `tc_windows` from summary.json, and decides each machine of U
alone, with the deciders its own full run would use and those settings. A non-halting verdict gives a line of
`amend.tsv`, and an UNKNOWN verdict leaves the machine in the lists. A HALT verdict for a machine of U means the
settings differ from the base run's, so the producer stops with an error and writes nothing. It takes U from the
holdout lists and the texts of the cell's current amendment, which is cheap. It counts `amend.tsv` or `amend.tsv.gz`
as the current amendment only when `amend.json` exists and its `base_summary_sha256` is the SHA-256 hex of the bytes
of summary.json, and otherwise ignores them as left over from another amendment. A producer that took the wrong U
fails step 4, 5 or 6 of the amendment check, so this needs no trust.

Producer 0.6.0 also reads `tc_records` from summary.json, 4,096 when it has none, and it takes the deciders' settings
from its own command line. When it amends a base made by producer 0.5.0 or later, it does not run the machines of U
step by step again, and of the four deciders of section 5 it tries on each of them only those that are switched on
and whose settings the base does not record as the same. The base run already tried the others on that machine with
those settings and left it UNKNOWN. It may also keep verbatim the lines of an earlier amendment of the same base by
producer 0.5.0 or later whose lines match its `amend_digest`, and then try what is new only on the machines that
amendment left. The checker checks every amended line the same way, whatever the producer tried or kept.

The tree depends on no verdict but HALT, and the producer's verdict for a machine depends only on the machine and
those settings. So a full rerun with the same producer gives the same holdout lists, and for each amended machine
the same line. A machine the base run proved may get another certificate in a full rerun, so an amended cell's
counts may split the non-halting verdicts differently from a full rerun's.

An amendment's lines reproduce with the producer its own RUNS.md row names, run on the cell's full run, whose claims
reproduce with the producer that the full run's row names (section 5). The claims file may be deleted after a passing full check and regenerated by the producer the RUNS.md row names, whose output is deterministic. The control numbers of the six amended
fixtures are in section 10, and the fixtures themselves in section 11.

### Backfilling unknown_digest

`python bbi9check.py CELL_DIR --unknown-digest` adds `unknown_digest` to a check.json that passes and lacks it, with no
census and no claims scan. It rests on the passing check having compared the holdout lists (section 9 step 4), or on
the amendment check having compared them (steps 4 to 6), so the lists, and the lines of `amend.tsv` for an amended
cell, are U. The command refuses unless check.json passes and its `summary_sha256` is that of summary.json. For an
amended cell it also refuses unless `amend_check.json` passes and binds the same summary.json and amend.json, and for
an unamended cell unless check.json's `holdout_lists` is `"checked"` or missing. It refuses when a text is in two
files or does not parse, when the count of U at depth D or below D differs from the recorded one, or when check.json
already has another `unknown_digest`. It prints `ADDED`, `KEPT` or `FAIL`, and it exits with 1 on `FAIL`. A full
re-check gives the same key.

## 13. Imports from other people's lists

An import marks the holdouts of a cell that other people's holdout lists decide, each line naming the list. A list's
maker posted the machines they left open in some domain, so a holdout of ours whose form a covering list leaves out
was decided by that maker, as a halter or as a non-halter. For such a `DECIDED_LIST` machine nothing more is known.
An entry may also register the domain's proven value, and a holdout that has run past it gets the verdict
`NONHALT_PROVEN`, which says that it never halts, by that registered value. An import changes no claim,
count or list of sections 5 and 12. It adds one credited line for each such holdout and two shorter holdout lists
beside our own, and the import check verifies every line from the cell, the registry and the list files alone.

### The registry

The registry is a YAML file, `experiments/bbi/lists.yaml` in this repository, that holds a sequence of mappings, one
for each list. A checker reads it with PyYAML's `yaml.safe_load`, the one library beyond the standard library that the
import check uses. An empty file is a registry with no entries. A checker uses these keys of an entry and ignores any
others.

- `id` names the list in the import's files, and no two entries have the same `id`.
- `label` is what the community calls the domain, such as `BB(3,3)` or `BBi(5)`, and `credit` names the maker and a
  date.
- `domain` is what the list covers, in one of three forms.
  - `{states: S, symbols: K}` is a BB(S,K) holdout list. It covers the cell (S′, K′) at any depth when S′ ≤ S and
    K′ ≤ K.
  - `{bbi: N}` holds the machines of N instructions that its maker left open, and their undecided machines of fewer
    instructions. It covers every cell at depth N and above.
  - `{bbi: N, cell: SxK}`, with the cell written like `3x3`, is a list of one of our cells, made from our holdout
    file of that cell. It covers that cell at depth N.

  A domain is a mapping with exactly the keys of one form, `states` and `symbols`, or `bbi`, or `bbi` and `cell`. S,
  K and N are whole numbers, S and K from 1 to 10 and N from 1 to 9, and a YAML true or false is not a whole number.
  Lists for N from 10 up are not registered yet.
  The cell is a string SxK, with S and K from 1 to 10 written in decimal without a leading zero, such as `3x3` or
  `10x2`. The first two forms are domain lists, and the third is a cell list. In this section N is always the N of a
  `{bbi: N}` domain, and the map's step bound is written B_d.
- `file` is the list file's name relative to the directory `--data DIR`. By default that directory is the directory
  two levels above the directory that holds the registry file, so for `experiments/bbi/lists.yaml` it is the
  repository root. A name ending in `.gz` is a gzip file, and the bytes read from it are the decompressed contents of
  all its members in order.
- `sha256` is the SHA-256 hex of the list file's bytes as stored. Capitals are allowed, and it is compared in
  lowercase.
- `entries` is the number of non-blank lines of the list file.
- `decides` is true or false, and a missing `decides` means false. A list decides our holdouts only when it is true.
- `complete` is a short statement of what the file is, such as "the maker's full TNF-1RB holdout list, nothing pruned
  by equivalence". Every entry with `decides: true` has one.
- `made_from`, which every cell list with `decides: true` has, is the SHA-256 hex of the bytes of our holdout file of
  its cell that the maker ran on. Like `sha256` it may have capitals, and it is compared in lowercase.
- `proven`, which a domain list may have, is the entry's proven value P, a whole number from 0 up, the most steps any
  halting machine of the domain takes before it reads an undefined pair, in the count of section 1, and the domain's
  value is proven to be P. For a classic value that counts the halting transition as a step, P is one less, as
  `experiments/bbi/KNOWN.md` writes its rows. An entry with `proven` is a complete holdout list that is empty
  (`entries: 0`, `decides: true`), since a proven value leaves nothing open, and its `complete` says so, though like
  any other list it decides nothing unless `decides` is true. A YAML true
  or false is not a whole number. A cell list never has `proven`, since a proven value is for a domain list.

A list file is read as the list intake reads it. It is UTF-8 text, and a byte-order mark at its start is ignored.
CRLF, LF and a bare CR each end a line, as in Python's universal newlines. Whitespace around a line is ignored and
blank lines are skipped. A line is then a machine, or an index number (decimal digits) and a machine separated by
whitespace, and the index is dropped. A file that is not UTF-8, or a line of any other form, makes the import check
fail at step 3.

`entry_sha256` of an entry is the SHA-256 hex of the UTF-8 bytes of the Python expression
`json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, where entry is the whole mapping that
`yaml.safe_load` gives for it, every key included. A change to any key of the entry changes it. Some mappings have
no such JSON, for example one with an unquoted YAML date such as `2026-11-01`, which `yaml.safe_load` reads as a
date. Such an entry has no `entry_sha256`, and when it has `decides: true` and covers the cell the import check fails
at step 3 and names it, rather than stopping with an error.

`complete` affirms three things that no check can see. The file is the maker's whole list for its domain, with
nothing removed except by deciding. Every undefined pair is written `---`, and no pair is filled in by convention.
For a `{bbi: N}` list, the maker's undecided machines of fewer than N instructions are listed too, or there are none.
Step 3 refuses a pair outside a `{states: S, symbols: K}` list's domain, but a pair inside the domain that no run of
its line can reach, such as one of a state that nothing targets or one reading a symbol that nothing writes, is not
checked. For such a pair the import rests on the second of these, that no pair is filled in by convention. A list of
class representatives never has `decides: true`, because a holdout that is not a representative would count as
decided. The registry records the statement beside the credit, and an import rests on it.

### Pairs, lines and shapes

A line of a domain list is compared by its set of defined pairs, never by its bytes. Its rows, separated by `_`, are
the states A, B, C and so on in order, and each row is a run of three-character slots for the symbols 0, 1, 2 and so
on. A slot is `---` for an undefined pair, or a digit w, then `L` or `R`, then a letter t from A to J, for the
instruction (w, m, t) of section 1. A line parses when it has this form, with at most 10 rows and at most 10 slots in
a row. Rows need not have the same number of slots. A cell list's lines are our own texts and are compared as texts.

Two machines are equal when their sets of pairs are equal. Rows and columns that own nothing do not matter, so
`1RB1LA_1LA---_------` equals `1RB1LA_1LA---`, and a BB(6) list's line in six rows equals a text of ours with three.
A line's depth is its number of defined pairs. Its shape is (s, k), where s counts the states that own a pair and k
is 1 plus the largest symbol it writes, as in section 2. It is in the cell's corridor when its depth d is at most D
and its shape is in the corridor at depth d (section 4).

A domain list's kept lines are the sets of pairs of its lines with at most D instructions. Two lines with the same
pairs are one kept line. A longer line can equal no machine of the cell and is not kept.

A subset of a line's pairs is written as a section 2 text, in the line's own letters, when the states that own its
pairs are A to the s-th letter, s their number. A subset owned by other states is never a claims text. A claims text
is the text of a line of the cell's claims file (section 5). It is open when it is in V, the base set defined under
The files below, and certified otherwise, by its claim or, in an amended cell, by the amendment's line for it.

### The normal-form map

Our tree is plain Tree Normal Form (section 3), so a machine's first instruction may write 0, as in `0RB---_1LA---`.
Community lists use TNF with a 1RB start. The map m takes a machine M of our tree, with text t, to the text m(t) of
the same machine in the community's form, or says that M has no map. The map's bound is B_d, the `max_halt_steps` of
corridor entry d of summary.json, where d is the depth of t. It is the bound the full check already uses, at most
10,000,000.

A machine with an instruction into a state that owns no pair has no map. For every other machine these steps run in
order, whatever its first instruction.

- **Step 1.** Run M from the start. While the current pair is defined and its instruction writes 0, take the step.
  The tape stays all 0s, and the head is on a 0. Stop at the first round whose instruction writes a non-zero symbol,
  in state s after p steps. If the run reads an undefined pair first, M has no map. If it enters some state twice in
  this prefix, M has no map. The start counts as the first entry of A, so `0RA` enters A twice. When the first
  instruction writes a non-zero symbol, p = 0 and s = A.
- **Step 1b.** The prefix pairs are the p pairs (q, 0) that step 1 executed. Drop a prefix pair (q, 0) from M while
  no remaining pair of M targets q, again and again until nothing more drops. The other pairs of a state whose 0-pair
  drops stay. They can then never run, so step 2 leaves them out. M′ is the pairs of M that remain.
- **Step 2.** From the configuration after p steps, which is the blank tape in state s, run M′ for at most B_d steps.
  Record the order in which pairs are first executed and the order in which states are first entered, s first. Stop as
  soon as every pair of M′ has been executed once, and otherwise stop at the bound. The pairs that ran are U, in the
  order of first use, and the pairs of M′ that did not run are its unused pairs. If the run reads an undefined pair,
  M halts and has no map. If no pair ran, which happens only when B_d is 0, M has no map.
- **Step 3.** Relabel. Each state gets the letter of its place in the order of first entry, so s becomes A. Symbols
  keep their digits. If the first move from s is L, swap every L and R.
- **Step 4.** m(t) is the text of the relabelled table of U, written as section 2 writes a text. A map whose first
  instruction is not `1RB` does not exist, and then M has no map. In the tree the only would-be map this rules out is
  `1RA---`, the map of `1RA---` itself and of 0RB-first machines such as `0RB---_1RB---`, whose run after the prefix
  stays in s forever.

For a machine whose first instruction writes a non-zero symbol, p = 0, s = A and nothing drops. Its states were first
entered in the order of their letters on the path that built it in the tree, and its first move is R (section 3), so
its map, when it has one, is t less its unused pairs, and t itself when every pair ran.

m(t) has the depth |U|, the depth of t less the dropped pairs and the unused ones, so it may be a shorter machine than
t. The rules below also use |M′|, the number of pairs of M′ used or not, and p, the number of steps of the prefix.
Where they speak of the maker's node they use m(t)'s depth, and where they speak of ours they use t's. The
prefixes of m(t) are the sets of its first j pairs in step 2's order, in m(t)'s letters, for j from 1 to m(t)'s depth
less 1. Every line of a domain list must start with `1RB`, and so must every map. That is what a TNF-1RB list
promises, and it rules out a list in some other labelling, which would match nothing and so decide everything.

**Why the map is sound.** Let U = U_0 ⊂ U_1 ⊂ ... ⊂ U_j be the sets of pairs that M's run from s has used after
step 2, after its next first use of a pair, and so on, with U_j the pairs it ever uses. Each U_i, relabelled by first
entry from s, is a node of the community's tree, because each of its pairs is reached in first-use order from the
TNF-1RB start. The labelling of U_0 is a prefix of each later one, so U_0 in U_j's letters is m(t). m(t)'s run is M's
run after the prefix, and M halts exactly when U_j halts, since M never reads a pair outside U_j. For a complete list
over a domain that holds every U_i, the maker listed m(t), a node above it or some U_i, or decided U_j. If the maker
listed one of those, a kept line equals m(t), is a prefix of it or is a proper superset of it, and the equality,
prefix and superset checks below refuse to decide M. If the maker decided U_j, M is decided. An
unused pair that the run from s might reach after B_d steps is the case of a later U_i. U_0 might halt on that very
pair after the bound, and then the maker expanded U_0, which is the case the superset rule already catches. For a
proven value P over a domain that holds U_0, the full check ran M for B_d steps from the start without a halt, so
U_0 ran for B_d − p steps from s. If B_d − p > P, U_0 has made more steps than any halting machine of the domain, so
U_0 never halts, so M never reads a pair outside U_0, so M never halts, whatever its unused pairs. A holdout with no
map is never decided by a domain list and stays in the counts. Step 1b is safe because a prefix state that no pair
targets can never be entered again after the prefix, so its 0-pair can never run again. The run of M′ from s is the
run of M from s.

**Speaking our language.** Before a domain list decides anything in a cell, each of its kept lines in the cell's
corridor is classified by our claims. The line's candidates are the texts of its subsets, the whole line included,
that are claims texts. A line has at most 2^D − 1 non-empty subsets, 511 at D = 9, so a checker may collect the
candidates of every line of every list first and then mark them in one scan of the claims file. The kinds are tested
in this order.

1. **Under one of ours left open.** Some claims text in V is a proper subset of the line. The maker expanded a
   machine we left open, so the line is one of the maker's undecided machines that our tree never reached.
2. **Settled by us.** Otherwise the line's own text is in V, or a claims text not in V is a subset of the line or
   equal to it, so its claim or the amendment's line for it certifies it. A line equal to a text of V is ours. A
   machine that never reads an undefined pair stays that way when pairs are added, so a line over a certified text
   never halts, by our certificate.
3. **A halter of ours.** Otherwise the line halts after at most B_d steps from the start, d its depth. We expanded it,
   the maker left it open, and every machine of ours below it is covered by the prefix rule below.
4. **A stranger.** Otherwise. The list and our tree disagree about this machine, and the list does not speak our
   language in the cell.

A domain list speaks our language in the cell when none of its kept lines in the corridor is of kind 4. Kind 1 is
tested first on purpose. A line that halts within B_d may still sit under a parent holdout of ours that the maker
found halting past our bound, and then its own children are machines of the cell that nobody has enumerated for us.
Kind 1 catches it, and kind 3 alone would not. A line equal to a text of V is not of kind 1. It is a machine both of
us left open, it is already in the after-lists counts as ours, and counting it again would count it twice. It is
kind 2.

The kind 1 lines are the maker holdouts. `maker_holdouts` counts them over all the domain lists that speak, once per
set of pairs, so a machine that two makers both list counts once, at depth D and below D by the line's depth.
A domain list that does not speak adds nothing to `maker_holdouts`. `maker_holdouts_by_list` counts each list's own
kind 1 lines the same way, and it is 0 and 0 for a cell list and for a list that does not speak. A machine that
another list decides is still counted, which overcounts and is the safe side. No line is run except for a kind 3
test, which is one run of at most B_d steps.

**Which machines a list decides.** Take a list that covers the cell, has `decides: true` and speaks our language in
the cell, and a machine t of V of depth d, with the bound B_d and, when t has a map, the prefix of p steps, m(t) and
M′. A domain list with no lines always speaks, since it has no line of kind 4. A cell list speaks by the rule under
**Cell lists** below, whatever its number of lines. The list gives t one of two verdicts, or none.

- A domain list with `proven` P gives t the verdict `NONHALT_PROVEN` when t has a map, m(t) lies in the list's
  domain, and B_d − p > P. For a `{bbi: N}` list, m(t) lies in the domain when its depth is at most N. For a
  `{states: S, symbols: K}` list it always does, since the list covers the cell and the pairs of m(t) are pairs of t.
- A domain list, with `proven` or without, gives t the verdict `DECIDED_LIST` when t has a map, every machine of the
  chain U_0 ⊂ ... ⊂ U_j lies in the list's domain, no kept line of the list equals m(t) or one of its prefixes, and
  no kept line has a set of pairs that is a proper superset of m(t)'s. A `{states: S, symbols: K}` list holds
  everything its maker left open in the whole domain, and the chain lies in it whenever the list covers the cell, so
  it may decide t at every depth. For a `{bbi: N}` list the chain lies in the domain when |M′| ≤ N, since every U_i
  is a subset of M′. So a `{bbi: N}` list may decide any machine of V with |M′| ≤ N, for example a parent
  holdout of depth at most N, a parent holdout of depth d from N + 1 to D − 1 whose prefix drops at least d − N
  pairs, and a depth-D holdout whose prefix drops at least D − N pairs.
- A cell list gives t the verdict `DECIDED_LIST` when t is a text of the cell's current depth-D holdout list
  `BBi{D}_{S}x{K}_holdouts_unofficial.txt` and not a line of the list. So it never decides a parent holdout, and never
  a text that a later run added.

A list decides t when it gives t either verdict.

**Prefixes.** The maker's tree node for our machine may be a proper ancestor of m(t). If the list holds a prefix of
m(t), the maker never expanded it, and m(t)'s absence says nothing.

**Supersets.** A kept line whose pairs are a proper superset of m(t)'s means that the maker expanded m(t), that is,
found it halting past our bound. Such a machine is not decided and stays in the after-lists counts. Its children under
the maker are kind 1 lines anyway.

**Cell lists.** A cell list was made from one version of our depth-D holdout list, which `made_from` pins by digest.
Its lines are our own texts, 0RB-first ones included, so no map, no 1RB rule and no kinds apply. It speaks our
language in the cell when `made_from`, in lowercase, is the SHA-256 hex of the bytes of the cell's current depth-D
holdout list and every line is a text of that list. A machine with no map can be decided by a cell list, never by a
domain list.

**The first list.** A machine's line names the first list in registry order that gives it `NONHALT_PROVEN`, with that
verdict, or, when none does, the first that gives it `DECIDED_LIST`. A proven value is the stronger fact and is never
hidden behind a list. So the import is a function of the registry and the list files.

### The files

A cell directory may hold an import, beside an amendment or without one. The importer writes `import.json`,
`import.tsv` and the two after-lists files, and the import check writes `import_check.json`. A cell has at most one
import. A newer import replaces the older one, and a full rerun or a new amendment of the cell removes it, since its
base changed.

The base set V is the set of texts of the cell's holdouts and parent holdouts, the two holdout lists of section 5 or,
in an amended cell, of section 12. Without an amendment V is the set of UNKNOWN texts of the claims file, and with one
it is that set less the texts of `amend.tsv`.

**import.tsv.** There is one line for each machine of V that some list decides, and there are no other lines. A line
is `text<TAB>NONHALT_PROVEN<TAB>id` or `text<TAB>DECIDED_LIST<TAB>id`, where the verdict and id, the registry `id` of a
list, are those that the first-list rule above names for the machine. The lines are sorted in byte order, every line
ends with a newline, and no text is on two lines. An import that decides nothing has an empty `import.tsv`. The file
may be `import.tsv.gz` instead, the gzip of the same bytes, read as `claims.tsv.gz` is (section 5), so it may hold
several gzip members. If both exist, a checker reads `import.tsv`.

The two verdicts say different things on purpose. A `DECIDED_LIST` machine may halt or never halt, since the maker may
have found it halting past our bound, so a page says "decided", never "never halts", for these machines. A
`NONHALT_PROVEN` machine never halts, by the domain's proven value.

**import.json.** A JSON object. A checker uses these keys and ignores any others, and each of these keys is required.

- `format` is `"bbi9-import/2"`.
- `cell` is `[S, K]` and `depth` is D, as in summary.json.
- `base_summary_sha256` is the SHA-256 hex of the bytes of the summary.json the import was made from, and
  `base_amend_sha256` that of its amend.json, or null when the cell has no amendment.
- `lists` is a list with one object for each registry entry that has `decides: true` and whose domain covers the
  cell, in registry order, whether or not the list decided anything. Each object has exactly the keys `id`, `sha256`
  (in lowercase), `entry_sha256`, `credit` and `label` of the entry, and `speaks`, which is true when the list speaks
  our language in the cell and false when it does not. A list that does not speak decides nothing.
- `decided` maps every id of `lists` to `{"holdouts": h, "parent_holdouts": p}`, the numbers of lines of import.tsv
  that name that id at depth D and at depths below D, with either verdict.
- `never_halts` maps every id of `lists` to `{"holdouts": h, "parent_holdouts": p}`, the numbers of lines of
  import.tsv with the verdict `NONHALT_PROVEN` that name that id at depth D and at depths below D.
- `maker_holdouts` is `{"holdouts": h, "parent_holdouts": p}`, the kind 1 lines of the domain lists that speak,
  counted once per set of pairs, at depth D and below D. `maker_holdouts_by_list` maps every id of `lists` to the same
  counts for that list alone, which are 0 and 0 for a cell list and for a list that does not speak.
- `strangers` maps every id of `lists` to the number of that list's kept lines in the corridor that are of kind 4,
  which is 0 for a cell list.
- `holdouts` and `parent_holdouts` count the machines of V that no line of import.tsv names, at depth D and below D.
- `imported` is the number of lines of import.tsv, and `import_digest` is the digest (section 7) of those lines, each
  without its newline.

`decided`, `never_halts`, `maker_holdouts_by_list` and `strangers` have exactly the ids of `lists` as keys, and every
count object is exactly `{"holdouts": h, "parent_holdouts": p}`, with no other keys.

The keys `importer`, `seconds`, `no_map` (how many machines of V have no map) and `kinds_by_list` (for each domain list
of `lists`, how many of its kept lines in the corridor are of each kind, as `[k1, k2, k3, k4]`) are for people to read.

**The after-lists files.** `BBi{D}_{S}x{K}_holdouts_after_lists_unofficial.txt` holds the texts of V at depth D that
no line of import.tsv names, and `BBi{D}_{S}x{K}_parent_holdouts_after_lists_unofficial.txt` those at depths below D.
Both are sorted in byte order, one text per line, each line ending with a newline, and a list with no machines is an
empty file. Our own two holdout lists stay as they are.

### The import check

The inputs are the cell directory, the census file, the registry and the directory of list files. The command line is
`python bbi9check.py CELL_DIR --import --census CENSUS_TSV --lists LISTS_YAML [--data DIR] [--jobs N]`. `--lists`
names the registry, and `--data` the directory that its `file` names are relative to. By default that is the
directory two levels above the directory that holds the registry file, so for `experiments/bbi/lists.yaml` it is the
repository root. A `--lists` file that is missing or that `yaml.safe_load` cannot read is a failure at step 3, with
exit 1, not bad usage. `--census` must name a file, as for the other checks, or the command is bad usage, and the
import check does not otherwise use it. `--jobs` spreads the work over that many processes, and it changes no result
except `seconds`. `--import` with `--amend` or `--plain`, `--import` without `--lists`, and `--lists` or `--data`
without `--import` are bad usage.

The check passes only when none of the steps below fails. Each failure adds a message. A step that needs something an
earlier failure left unread, such as import.json's keys after step 2 fails, is skipped. A checker may do the work in
another order, for example reading the registry and the list files before the claims file, so that one scan of the
claims file serves steps 1 and 4.

1. Read summary.json and check.json, and fail as step 1 of the amendment check does (section 12). If amend.json
   exists, fail unless amend_check.json exists, is a JSON object, passes, and has `summary_sha256` and
   `amend_sha256` equal to the SHA-256 hex of the bytes of summary.json and of amend.json. Read every line of the
   claims file, and fail unless it is bound to summary.json as step 3 of the amendment check binds it, by its count,
   its digest and its UNKNOWN lines at each depth. V is the set of texts of the UNKNOWN lines. When the cell has
   neither `claims.tsv` nor `claims.tsv.gz` and no kept line of a domain list in `lists` lies in the cell's corridor,
   step 4 looks nothing up among the claims, and this step takes U as step 3 of the amendment check does without the
   claims file, failing as it fails, from the cell's two lists of section 5 and, when amend.json exists, the texts of
   the lines of `amend.tsv`. V is then the set of texts of U. Otherwise a missing claims file fails, so an import of a
   cell whose claims were deleted needs them regenerated first when some list line lies in its corridor. With an
   amendment, read `amend.tsv`, or `amend.tsv.gz` when there is no `amend.tsv`. Fail if neither exists, if the number
   of its lines is not amend.json's `amended`, or if their digest (section 7) is not its `amend_digest`, and take the
   texts of its lines out of V. Fail unless the two holdout lists of section 5 are exactly the texts of V at depth D
   and at depths below D, sorted in byte order, each followed by a newline, by recomputing them this way. A missing
   list fails. The checker takes V from these files, never from the lists it is handed.
2. Read import.json. Fail if it is missing or is not a JSON object, if a key a checker uses is missing, if `format`
   is not `"bbi9-import/2"`, or if `cell` or `depth` differs from summary.json's. Fail if `base_summary_sha256` is
   not the SHA-256 hex of the bytes of summary.json, or if `base_amend_sha256` is not the SHA-256 hex of the bytes of
   amend.json, or null when there is no amend.json.
3. Read the registry with PyYAML's `yaml.safe_load`, the one thing outside the standard library in the whole Python
   checker.
   Fail if the file is missing or `yaml.safe_load` cannot read it, if it is not a sequence of mappings, if an entry's
   `decides` is present and neither true nor false, if an entry's `proven` is present and is not a whole number from 0
   up, if an entry has `proven` and `entries` other than 0, if a cell list has `proven` (a proven value is for a
   domain list), or if an entry with `decides: true` lacks one of `id`, `label`, `credit`, `domain`, `file`, `sha256`,
   `entries` and `complete`, has a `complete` that is empty or not a string, has a domain of none of the three forms,
   shares its `id` with another such entry, or is a cell list without `made_from`. Fail, naming the entry, if one
   that has `decides: true` and covers the cell has no JSON for its `entry_sha256`. Fail unless `lists` holds exactly
   the entries with `decides: true` that cover the cell, in registry order, each an object with exactly the entry's
   `id`, `credit`, `label` and `sha256` in lowercase, its `entry_sha256` and `speaks`. For each of these lists, read
   its file below `--data`, gunzipped when its name ends in `.gz`. Fail if the file is missing, if its SHA-256 hex is
   not the entry's `sha256`, if it has a line of a form that the reading rules above do not allow, or if its number of
   non-blank lines is not `entries`.
   For a domain list, fail on each line that does not parse, whose first instruction, at (A, 0), is not `1RB`, that
   has a `Z` or targets a letter past its rows plus one (a line of r rows may target the first r + 1 letters), that
   targets a state at or past S or writes a symbol at or past K in a `{states: S, symbols: K}` list, or that has more
   than N instructions in a `{bbi: N}` list. In a `{states: S, symbols: K}` list, also fail on each line that defines
   a pair reading a symbol at or past K (a slot other than `---` after the K-th slot of some row) or a pair of a
   state at or past S (a slot other than `---` in a row after the S-th). A slot or a row of nothing but `---` owns
   nothing and passes. Keep each domain list's kept lines, and each cell list's lines as texts.
   Fail unless `strangers` maps each id of `lists`, and no other key, to that list's number of kind 4 lines in step
   4, 0 for a cell list.
4. Classify each kept line of each domain list that is in the cell's corridor by the four kinds above, with the
   claims lines that step 1 bound to summary.json for the candidates and one run of at most B_d steps for a kind 3
   test. A kind 4 line makes the list not speak our language in this cell. A cell list speaks when its `made_from`, in
   lowercase, is the SHA-256 hex of the bytes of the cell's depth-D holdout list and every line is a text of that
   list. Fail unless each list's `speaks` is this result. Fail unless `maker_holdouts` and `maker_holdouts_by_list` are
   the kind 1 counts above, with every id of `lists` and no other key in `maker_holdouts_by_list`, and 0 and 0 for a
   cell list and for a list that does not speak.
5. Read `import.tsv`, or `import.tsv.gz` when there is no `import.tsv`. Fail if neither exists. Fail on each line
   that does not end with a newline, does not have exactly three fields separated by TAB, has a verdict other than
   `DECIDED_LIST` and `NONHALT_PROVEN`, names an id that is not in `lists` or one whose `speaks`, as step 4 computes
   it, is false, has a text that is not in V or that an earlier line has, or does not come after the line before it
   in byte order. Fail on each line that gives `NONHALT_PROVEN` and names a cell list or a list without `proven`. For
   a cell list, fail unless the text is a text of the cell's depth-D holdout list and not a line of the list, so a
   parent holdout fails. For a domain list, compute m(text) with the bound B_d, d the text's depth, with p and |M′|,
   and fail if the machine has no map or its map does not start `1RB`. For the verdict `NONHALT_PROVEN`, fail unless
   m(text) lies in the list's domain, which for a `{bbi: N}` list means at most N instructions, and unless
   B_d − p > P for the list's proven value P. For the verdict `DECIDED_LIST`, fail if the list is a `{bbi: N}` list and
   |M′| > N, if a kept line of the list equals m(text) or one of its prefixes, or if a kept line's set of pairs is a
   proper superset of m(text)'s. Fail if a list earlier in registry order that speaks would give the machine the
   line's verdict, and fail a `DECIDED_LIST` line if any list that speaks would give the machine `NONHALT_PROVEN`,
   since the line must name what the first-list rule names.
6. Count. Fail unless `decided` maps every id of `lists`, and no other key, to the numbers of lines that name it at
   depth D and at depths below D, unless `never_halts` maps every id of `lists`, and no other key, to the numbers of
   lines with the verdict `NONHALT_PROVEN` that name it at depth D and at depths below D, unless `holdouts` and
   `parent_holdouts` are the numbers of machines of V that no line names at depth D and at depths below D, unless
   `imported` is the number of lines, and unless `import_digest` is their digest (section 7, each line without its
   newline).
7. Fail unless the two after-lists files are exactly the texts of V that no line of import.tsv names, at depth D and
   at depths below D, sorted in byte order, each followed by a newline. A missing file fails, and when no text is
   left the file is empty.

Then write `import_check.json` into the cell directory, print one line starting with `PASS` or `FAIL`, and exit with
0 on a pass, 1 on a fail and 2 on bad usage. `import_check.json` has the keys `format` (`"bbi9-import-check/1"`),
`checker` (name and version), `cell` and `depth` (summary.json's), `pass`, `failures` (the first 50 messages),
`holdouts`, `parent_holdouts`, `maker_holdouts` (an object with the keys `holdouts` and `parent_holdouts`),
`imported`, `import_digest`, `lists` (one object `{"id", "sha256", "speaks"}` for each entry with `decides: true` that
covers the cell, in registry order), `seconds`, `summary_sha256`, `amend_sha256` and `import_sha256`, the SHA-256 hex
of the bytes of summary.json, of amend.json (null when there is none) and of import.json. Every value is the
checker's own, and on a fail a value that a failure left uncomputed is null. The import check never writes check.json
or amend_check.json, and the other two checks never write `import_check.json`.

The tracker trusts an import check only while it passes, its `summary_sha256`, `amend_sha256` and `import_sha256`
match the current summary.json, amend.json and import.json (`amend_sha256` is null exactly when there is no
amend.json), check.json is trusted for the same summary.json (section 9), and amend_check.json is trusted for the same
files when amend.json exists (section 12). import.json's `lists` must also carry `entry_sha256` for each entry, and
the sequence of its pairs `(id, entry_sha256)` must equal that of the registry's current entries with `decides: true`
that cover the cell, in registry order. So turning `decides` off, adding a list, reordering those lists, which
can change the list that must name a machine in step 5, or changing a list's `domain`, `made_from`, `complete` or
`proven` hides the import at once, before it is made again. A cell with import.json and no such trusted check counts
as having no import, never as unchecked, because an import is a layer on top of the cell.

### Why this is enough

Step 1 fixes V as the machines that our checked run and amendment left. Step 3 fixes each list to the bytes its maker
posted, by the digest the registry records, and to the TNF-1RB form. Its line checks also refuse a halt written as an
instruction, as `1RZ` or as `1RH` with H past the line's rows plus one, which would make a line one instruction
longer than the machine it lists. A `{bbi: N}` line of more than N instructions is refused for the same reason, since
at depth N it would not be kept and the machine it lists would count as decided. A `{states: S, symbols: K}` line
that defines a pair reading a symbol at or past K or a pair of a state at or past S is refused too. No run reaches
such a pair, so the line is a machine of the domain with a pair added, and a listed prefix of a machine's map hidden
in it would let that machine count as decided. Step 4 shows that the list and our tree agree on every machine both
could hold, which is what makes absence from the list mean something, and it counts the maker's undecided machines
that our tree never reached. Step 5 shows that each `DECIDED_LIST` machine is a TNF-1RB node (it has a map) that the
maker's enumeration reached (no prefix of it is listed) and left out of their list. For each `NONHALT_PROVEN` line it
shows that m(t) lies in the entry's domain and ran B_d − p steps from s, more than the entry's proven value. What the
check cannot see is whether the file is the maker's whole list, with no pair filled in by convention, which `complete`
asserts and the page states, and whether the entry's proven value is right. `complete` and `proven` are taken on
trust. A wrong `proven` makes every `NONHALT_PROVEN` line of its entry unsound, which is why it is a registry key
beside the credit, where anyone can see it and its source. The cell's own numbers are untouched, and the after-lists
numbers say which machines no one has left open. An import that leaves out a machine some list decides still passes,
since that machine then stays in the after-lists counts, which is the safe side.
