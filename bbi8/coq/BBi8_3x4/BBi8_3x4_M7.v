(** * BBi(8) holdout #7 1RB1LC2LA---_2RC---------_0LA2RC3LC1RC never halts *)
(** Credit and how this was made: see README.md in the bbi8 folder. *)

(** The word of the bounce uses the symbol 2 for the digit 1 and the symbol 1
    for the digit 0. The C-sweeps use 3 as their temporary symbol. This file
    proves the three local tape lemmas that BBi8_3x4_Tape.v asks for (carry,
    overflow and the A-sweep), the start, and the theorem. *)

From BusyCoq Require Import Individual34.
Require Import BusyCoq.BBi8_3x4.BBi8_3x4_Tape.
From Coq Require Import String.
Set Default Goal Selector "!".

Definition tm := Eval compute in (TM_from_str "1RB1LC2LA---_2RC---------_0LA2RC3LC1RC").

Notation "c -->* c'" := (c -[ tm ]->* c') (at level 40).
Notation "c -->+ c'" := (c -[ tm ]->+ c') (at level 40).

Notation K := (Kw 2 1).

(** C2 is 3LC. *)
Lemma sweep_C2 : forall n l r,
  l <* [2]^^n <{{C}} r -->* l <{{C}} [3]^^n *> r.
Proof. es. Qed.

(** C3 is 1RC. *)
Lemma sweep_C3 : forall n l r,
  l {{C}}> [3]^^n *> r -->* l <* [1]^^n {{C}}> r.
Proof. es. Qed.

(** A2 is 2LA. *)
Lemma sweep_A2 : forall n l r,
  l <* [2]^^n <{{A}} r -->* l <{{A}} [2]^^n *> r.
Proof. es. Qed.

(** Carry. The head is on bit j, bits j to q-1 hold 2 (digit 1) and bit q holds
    1 (digit 0). Afterwards bits j to q-1 hold 1, bit q holds 2, and the head is
    on bit j-1. C1 is 2RC. *)
Lemma carry : forall k l r,
  l <* [1] <* [2]^^k <{{C}} r -->+ l <* [2] <* [1]^^k {{C}}> r.
Proof.
  intros.
  follow sweep_C2.
  eapply progress_intro; [prove_step | simpl_tape].
  follow sweep_C3.
  finish.
Qed.

(** Overflow. Bits j to L-1 hold 2 and everything above is blank. Afterwards
    bits j to L-1 hold 1, bit L holds 2, bit L+1 holds 1, and the head is on
    bit j-1. Between the sweeps the machine runs C0, A0 and B0. *)
Lemma overflow : forall k r,
  const 0 <* [2]^^k <{{C}} r -->+ const 0 <* [2; 1] <* [1]^^k {{C}}> r.
Proof.
  intros.
  follow sweep_C2.
  eapply progress_intro; [prove_step | simpl_tape].
  execute.
  follow sweep_C3.
  finish.
Qed.

(** The A-sweep. From the bounce position, C0, then A over bits 0 to n-1
    holding 2, then A1 (1LC) on bit n leaves the head on bit n+1 in state C. *)
Lemma sweepA : forall n l,
  l <* [1] <* [2]^^n {{C}}> const 0 -->+ l <{{C}} [1] *> [2]^^n *> const 0.
Proof.
  intros.
  eapply progress_intro; [prove_step | simpl_tape].
  follow sweep_A2.
  execute.
Qed.

(** The start: two steps reach the word of length 2 and value 1. *)
Lemma start : c0 -->* K 2 1.
Proof. unfold Kw, word. solve [execute | es]. Qed.

(** Sanity checks on the reading of the word: h(2) = 9 needs a longer word,
    h(9) = 12 does not. *)
Example bounce_2_1 : K 2 1 -->+ K 4 8.
Proof. unfold Kw, word. solve [start_progress | es]. Qed.

Example bounce_4_8 : K 4 8 -->+ K 4 11.
Proof. unfold Kw, word. solve [start_progress | es]. Qed.

Theorem nonhalt : ~ halts tm c0.
Proof. exact (counter_nonhalt tm 2 1 carry overflow sweepA start). Qed.
