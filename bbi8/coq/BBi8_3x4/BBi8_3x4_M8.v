(** * BBi(8) holdout #8 1RB---2LC3LA_2LC---------_0LA2RC3RC1LC never halts *)
(** Credit and how this was made: see README.md in the bbi8 folder. *)

(** #8 is #7 with the symbols relabelled 1 -> 2, 2 -> 3, 3 -> 1, except for A0
    and B0. The word of the bounce uses the symbol 3 for the digit 1 and the
    symbol 2 for the digit 0. The C-sweeps use 1 as their temporary symbol. This
    file proves the three local tape lemmas that BBi8_3x4_Tape.v asks for, the
    start, and the theorem. *)

From BusyCoq Require Import Individual34.
Require Import BusyCoq.BBi8_3x4.BBi8_3x4_Tape.
From Coq Require Import String.
Set Default Goal Selector "!".

Definition tm := Eval compute in (TM_from_str "1RB---2LC3LA_2LC---------_0LA2RC3RC1LC").

Notation "c -->* c'" := (c -[ tm ]->* c') (at level 40).
Notation "c -->+ c'" := (c -[ tm ]->+ c') (at level 40).

Notation K := (Kw 3 2).

(** C3 is 1LC. *)
Lemma sweep_C3 : forall n l r,
  l <* [3]^^n <{{C}} r -->* l <{{C}} [1]^^n *> r.
Proof. es. Qed.

(** C1 is 2RC. *)
Lemma sweep_C1 : forall n l r,
  l {{C}}> [1]^^n *> r -->* l <* [2]^^n {{C}}> r.
Proof. es. Qed.

(** A3 is 3LA. *)
Lemma sweep_A3 : forall n l r,
  l <* [3]^^n <{{A}} r -->* l <{{A}} [3]^^n *> r.
Proof. es. Qed.

(** Carry. C2 is 3RC. *)
Lemma carry : forall k l r,
  l <* [2] <* [3]^^k <{{C}} r -->+ l <* [3] <* [2]^^k {{C}}> r.
Proof.
  intros.
  follow sweep_C3.
  eapply progress_intro; [prove_step | simpl_tape].
  follow sweep_C1.
  finish.
Qed.

(** Overflow. Between the sweeps the machine runs C0, A0, B0 (2LC), C1 and C2,
    five steps where #7 takes three. *)
Lemma overflow : forall k r,
  const 0 <* [3]^^k <{{C}} r -->+ const 0 <* [3; 2] <* [2]^^k {{C}}> r.
Proof.
  intros.
  follow sweep_C3.
  eapply progress_intro; [prove_step | simpl_tape].
  execute.
  follow sweep_C1.
  finish.
Qed.

(** The A-sweep. A2 is 2LC. *)
Lemma sweepA : forall n l,
  l <* [2] <* [3]^^n {{C}}> const 0 -->+ l <{{C}} [2] *> [3]^^n *> const 0.
Proof.
  intros.
  eapply progress_intro; [prove_step | simpl_tape].
  follow sweep_A3.
  execute.
Qed.

(** The start: four steps reach the word of length 2 and value 1. *)
Lemma start : c0 -->* K 2 1.
Proof. unfold Kw, word. solve [execute | es]. Qed.

(** Sanity checks on the reading of the word. *)
Example bounce_2_1 : K 2 1 -->+ K 4 8.
Proof. unfold Kw, word. solve [start_progress | es]. Qed.

Example bounce_4_8 : K 4 8 -->+ K 4 11.
Proof. unfold Kw, word. solve [start_progress | es]. Qed.

Theorem nonhalt : ~ halts tm c0.
Proof. exact (counter_nonhalt tm 3 2 carry overflow sweepA start). Qed.
