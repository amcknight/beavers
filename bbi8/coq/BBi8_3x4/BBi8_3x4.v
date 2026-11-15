(** * BBi(8) holdouts #7 and #8 never halt *)
(** Credit and how this was made: see README.md in the bbi8 folder. *)

(** The two machines are the 3-state 4-symbol holdouts of BBi(8). Each [table]
    lemma pins the transition table written out by hand, so the statement does
    not depend on the parser [TM_from_str].

    Proofs: BBi8_3x4_M7.v and BBi8_3x4_M8.v (the local tape lemmas of each
    machine), BBi8_3x4_Tape.v (the bounce: each bounce maps y = V + 1 to
    h(y) = y - 1 + 2^(nu(y)+2), and the machine can only halt when y is a power
    of 2), BBi8_3x4_Arith.v (self-similarity and slow zeros: the orbit of 2
    under h contains no power of 2 from 4 up). *)

From BusyCoq Require Import Individual34.
Require Import String.
Require BusyCoq.BBi8_3x4.BBi8_3x4_M7 BusyCoq.BBi8_3x4.BBi8_3x4_M8.

Module TM7.
Definition tm := Eval compute in (TM_from_str "1RB1LC2LA---_2RC---------_0LA2RC3LC1RC").

Lemma table : forall q s, tm (q, s) =
  match q, s with
  | A, S0 => Some (S1, R, B) | A, S1 => Some (S1, L, C)
  | A, S2 => Some (S2, L, A) | A, S3 => None
  | B, S0 => Some (S2, R, C) | B, S1 => None
  | B, S2 => None            | B, S3 => None
  | C, S0 => Some (S0, L, A) | C, S1 => Some (S2, R, C)
  | C, S2 => Some (S3, L, C) | C, S3 => Some (S1, R, C)
  end.
Proof. intros [] []; reflexivity. Qed.

Theorem nonhalt: ~halts tm c0.
Proof. exact BusyCoq.BBi8_3x4.BBi8_3x4_M7.nonhalt. Qed.
End TM7.

Module TM8.
Definition tm := Eval compute in (TM_from_str "1RB---2LC3LA_2LC---------_0LA2RC3RC1LC").

Lemma table : forall q s, tm (q, s) =
  match q, s with
  | A, S0 => Some (S1, R, B) | A, S1 => None
  | A, S2 => Some (S2, L, C) | A, S3 => Some (S3, L, A)
  | B, S0 => Some (S2, L, C) | B, S1 => None
  | B, S2 => None            | B, S3 => None
  | C, S0 => Some (S0, L, A) | C, S1 => Some (S2, R, C)
  | C, S2 => Some (S3, R, C) | C, S3 => Some (S1, L, C)
  end.
Proof. intros [] []; reflexivity. Qed.

Theorem nonhalt: ~halts tm c0.
Proof. exact BusyCoq.BBi8_3x4.BBi8_3x4_M8.nonhalt. Qed.
End TM8.

Print Assumptions TM7.nonhalt.
Print Assumptions TM8.nonhalt.
