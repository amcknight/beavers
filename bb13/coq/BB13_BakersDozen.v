(** * The Baker's Dozen, a 13-state machine, halts (main theorem [halt]); its score is in BB13_BakersDozen_bound.v *)

(** The Baker's Dozen = M12 with L0 = 1RL (was 0LH), K0 = 0LM (was the halt) and a new state M = (0LG, ---).

    This file is built on Jeff Ketchersid's Coq development for M12 (BB12/verify_m12/multifile/BB12_M12.v in
    github.com/jeff87654/busy-beaver; M12 was found and proved by Argon, a Google Gemini model run by Jeff).  Blocks
    marked "copied unchanged" are his text, byte for byte; they are replayed here against the Baker's Dozen's table, which
    agrees with M12's on every slot those proofs read.  New here: the table, the rules G (halt), D1, RST (restart,
    via RST_entry, RST_sweep, RST_restart, STARTUP) and START, the residues of W and of the Kc/Kd maps modulo 81,
    and the four-round run.

    The run (configurations as in BB12_M12.v; Cd p b d = 0^inf (10)^p 1^(b+2) I> (10)^d 0^inf):
      c0 -->* Cd 7 3 5                                                   (START, 260 steps)
      Cd 7 3 d -->+ Cd 7 3 (round2 d)            when d mod 3 = 2        (Kd_loop, Kc_full_all, D1, RST)
      d1 = round2 5,  d2 = round2 d1,  d3 = round2 d2,  d4 = round2 d3
      d1 = 32 (mod 81), d2 = 14 (mod 27), d3 = 8 (mod 9), d4 = 0 (mod 3)  (W_mod81 and the Kc/Kd residues)
      Cd 7 3 d4 -->* Cd (fst pb4) (snd pb4) 0 -->+ c_halt _ _            (Kd_loop, G_HALT: M reads a 1) *)

From BB8 Require Import Individual132.
From Coq Require Import Lia PeanoNat List Wf_nat.
Import ListNotations.
Set Default Goal Selector "!".

(* machine: 1RB1RA_1RI1RC_0LD1LG_0RE1LD_1LK1RF_1RG0RA_1RA0LH_1LG1LH_1RE0LJ_1LH1LI_0LM0LL_1RL1LK_0LG--- *)
Definition tm : TM := fun '(q, s) =>
  match q, s with
  | A, 0 => Some (1, TM.R, B)  | A, 1 => Some (1, TM.R, A)
  | B, 0 => Some (1, TM.R, I)  | B, 1 => Some (1, TM.R, C)
  | C, 0 => Some (0, TM.L, D)  | C, 1 => Some (1, TM.L, G)
  | D, 0 => Some (0, TM.R, E)  | D, 1 => Some (1, TM.L, D)
  | E, 0 => Some (1, TM.L, K)  | E, 1 => Some (1, TM.R, F)
  | F, 0 => Some (1, TM.R, G)  | F, 1 => Some (0, TM.R, A)
  | G, 0 => Some (1, TM.R, A)  | G, 1 => Some (0, TM.L, H)
  | H, 0 => Some (1, TM.L, G)  | H, 1 => Some (1, TM.L, H)
  | I, 0 => Some (1, TM.R, E)  | I, 1 => Some (0, TM.L, J)
  | J, 0 => Some (1, TM.L, H)  | J, 1 => Some (1, TM.L, I)
  | K, 0 => Some (0, TM.L, M)  | K, 1 => Some (0, TM.L, L)
  | L, 0 => Some (1, TM.R, L)  | L, 1 => Some (1, TM.L, K)
  | M, 0 => Some (0, TM.L, G)  | M, 1 => None
  end.

(* ---- copied unchanged from BB12_M12.v (Jeff Ketchersid): the step notations, align_lpow, align_lpow_const,
        align_tape, norm_nat, finish_norm, lpow_double ---- *)
Notation "c --> c'" := (c -[ tm ]-> c')   (at level 40).
Notation "c -->* c'" := (c -[ tm ]->* c') (at level 40).
Notation "c -->+ c'" := (c -[ tm ]->+ c') (at level 40).

Lemma align_lpow : forall (x : Sym) xs ys n,
  (x::xs)^^n *> x >> ys = x >> (xs ++ [x])^^n *> ys.
Proof.
  induction n.
  - reflexivity.
  - simpl. repeat rewrite Str_app_assoc. rewrite IHn. reflexivity.
Qed.

Lemma align_lpow_const : forall (x : Sym) xs n,
  (x::xs)^^n *> const x = x >> (xs ++ [x])^^n *> const x.
Proof. intros. rewrite const_unfold at 1. apply align_lpow. Qed.

Ltac align_tape := repeat ((rewrite align_lpow || rewrite align_lpow_const); simpl app).
Ltac norm_nat := repeat progress (rewrite ?Nat.add_succ_r, ?Nat.add_0_r; simpl).
Ltac finish_norm := apply evstep_refl'; norm_nat; align_tape; try reflexivity; lia_refl.

Lemma lpow_double : forall {T} (xs : list T) m, xs^^(2 * m) = (xs ++ xs)^^m.
Proof.
  induction m. - reflexivity.
  - replace (2 * S m)%nat with (S (S (2 * m))) by lia. cbn [lpow]. rewrite IHm, app_assoc. reflexivity.
Qed.
(* ---- end of copied block ---- *)

(** ** Basic shift lemmas *)

(* ---- copied unchanged from BB12_M12.v: cr_AR_1_1, cr_DL_1_1, cr_HL_1_1, cr_HL_01_01, cr_IL_11_10, cr_KL_11_10
        (cr_KL_11_10 reads K1 = 0LL and L1 = 1LK, which the Baker's Dozen shares with M12) ---- *)
Lemma cr_AR_1_1 : forall n l r, l {{A}}> [1]^^n *> r -->* [1]^^n *> l {{A}}> r.
Proof. induction n; intros. - finish. - execute. follow IHn. finish_norm. Qed.

Lemma cr_DL_1_1 : forall n l r, [1]^^n *> l <{{D}} r -->* l <{{D}} [1]^^n *> r.
Proof. induction n; intros. - finish. - execute. follow IHn. finish_norm. Qed.

Lemma cr_HL_1_1 : forall n l r, [1]^^n *> l <{{H}} r -->* l <{{H}} [1]^^n *> r.
Proof. induction n; intros. - finish. - execute. follow IHn. finish_norm. Qed.

Lemma cr_HL_01_01 : forall n l r, [0; 1]^^n *> l <{{H}} r -->* l <{{H}} [0; 1]^^n *> r.
Proof. induction n; intros. - finish. - execute. follow IHn. finish_norm. Qed.

Lemma cr_IL_11_10 : forall n l r, [1; 1]^^n *> l <{{I}} r -->* l <{{I}} [1; 0]^^n *> r.
Proof. induction n; intros. - finish. - execute. follow IHn. finish_norm. Qed.

Lemma cr_KL_11_10 : forall n l r, [1; 1]^^n *> l <{{K}} r -->* l <{{K}} [1; 0]^^n *> r.
Proof. induction n; intros. - finish. - execute. follow IHn. finish_norm. Qed.
(* ---- end of copied block ---- *)

(** ** Configurations and inner cascade rules *)

(* ---- copied unchanged from BB12_M12.v: configurations Ca, Ch, Ce, Cd, blk and the cascade rules CA_SH,
        CA_SH_iter, CA_EXIT, CA_CH, CH_0, CH_S_aux, CH_S, E_EVEN ---- *)
Definition Ca (j b : nat) (z : side) : Q * tape :=
  ([1]^^b *> [0; 1]^^j *> const 0) {{A}}> (0 >> z).

Definition Ch (j b : nat) (z : side) : Q * tape :=
  ([0; 1]^^j *> const 0) <{{H}} (1 >> [1]^^b *> 0 >> z).

Definition Ce (p a c d : nat) : Q * tape :=
  ([1]^^(a + 2) *> [0; 1]^^p *> const 0) {{I}}> ([1; 0]^^c *> 0 >> [1; 0]^^d *> const 0).

Definition Cd (p b d : nat) : Q * tape :=
  ([1]^^(b + 2) *> [0; 1]^^p *> const 0) {{I}}> ([1; 0]^^d *> const 0).

Definition blk (a : nat) (z : side) : side :=
  1 >> [1]^^a *> 0 >> z.

Lemma CA_SH : forall j b z,
  Ca j b (1 >> 0 >> z) -->+ Ca (S j) b z.
Proof.
  intros j b z. unfold Ca.
  start_progress.
  follow cr_DL_1_1.
  align_tape.
  execute.
  follow cr_AR_1_1.
  finish_norm.
Qed.

Lemma CA_SH_iter : forall k j b z,
  Ca j b ([1; 0]^^k *> z) -->* Ca (j + k) b z.
Proof.
  induction k; intros j b z.
  - replace (j + 0)%nat with j by lia. finish.
  - simpl.
    eapply evstep_trans; [apply progress_evstep, CA_SH |].
    follow (IHk (S j) b z).
    replace (S j + k)%nat with (j + S k)%nat by lia. finish.
Qed.

Lemma CA_EXIT : forall j b z,
  Ca j b (0 >> z) -->+ ([1]^^(b + 2) *> [0; 1]^^j *> const 0) {{I}}> z.
Proof.
  intros j b z. unfold Ca.
  start_progress.
  finish_norm.
Qed.

Lemma CA_CH : forall j b y,
  Ca j b (1 >> 1 >> y) -->+ Ch j b (1 >> y).
Proof.
  intros j b y. unfold Ca, Ch.
  start_progress.
  follow cr_HL_1_1.
  finish_norm.
Qed.

Lemma CH_0 : forall b z,
  Ch 0 b z -->+ Ca 0 (b + 3) z.
Proof.
  intros b z. unfold Ch, Ca. simpl lpow.
  start_progress.
  follow cr_AR_1_1.
  finish_norm.
Qed.

Lemma CH_S_aux : forall j b z,
  Ch (S j) b z -->+ Ca 0 2 ([1; 0]^^j *> blk (S b) z).
Proof.
  intros j b z. unfold Ch, Ca, blk.
  start_progress.
  follow cr_HL_01_01.
  align_tape.
  execute; finish_norm.
Qed.

Lemma CH_S : forall j b z,
  Ch (S j) b z -->+ Ca j 2 (blk (S b) z).
Proof.
  intros j b z.
  eapply progress_evstep_trans; [apply CH_S_aux |].
  follow (CA_SH_iter j 0 2 (blk (S b) z)).
  finish_norm.
Qed.

Lemma E_EVEN : forall p' k r,
  ([1]^^(2 * k + 2) *> [0; 1]^^(S p') *> const 0) {{I}}> (1 >> 0 >> r) -->+
  Ch p' 1 ([1; 0]^^(S k) *> 0 >> r).
Proof.
  intros p' k r. unfold Ch.
  replace (2 * k + 2)%nat with (1 + (2 * k + 1))%nat by lia.
  rewrite !lpow_add. cbn [lpow Str_app].
  rewrite (lpow_double [1] k). cbn [app].
  start_progress.
  follow cr_IL_11_10.
  execute; finish_norm.
Qed.
(* ---- end of copied block ---- *)

(* ---- copied unchanged from BB12_M12.v: C_REL_aux, D_STEP_aux.  (M12's D_REL_aux is not copied: it reads L0,
        which the Baker's Dozen changes.) ---- *)
Lemma C_REL_aux : forall p' m d,
  Cd (S p') (2 * m + 1) (S d) -->+ Ch p' 3 (0 >> [1; 0]^^m *> 0 >> [1; 0]^^d *> const 0).
Proof.
  intros p' m d. unfold Cd, Ch.
  replace (2 * m + 1 + 2)%nat with (1 + (2 * m + 2))%nat by lia.
  rewrite !lpow_add. cbn [lpow Str_app].
  rewrite (lpow_double [1] m). cbn [app].
  start_progress.
  follow cr_IL_11_10.
  align_tape.
  execute; finish_norm.
Qed.

Lemma D_STEP_aux : forall p a d,
  Ce p a 0 (S (S d)) -->+ Ch p (a + 4) (0 >> [1; 0]^^d *> const 0).
Proof.
  intros p a d. unfold Ce, Ch. norm_nat.
  start_progress.
  follow cr_HL_1_1.
  finish_norm.
Qed.
(* ---- end of copied block ---- *)

(** ** Halting step at d = 0 *)

(* ---- copied unchanged from BB12_M12.v: c_end, HALT_step.  In the Baker's Dozen, c_end is not a halting configuration
        (K0 = 0LM); the halt is one step later, in rule G below. ---- *)
Definition c_end (p m : nat) : Q * tape :=
  ([0; 1]^^p *> const 0) <{{K}} ([1; 0]^^(m + 2) *> 1 >> const 0).

Lemma HALT_step : forall p m,
  Cd p (2 * m + 1) 0 -->+ c_end p m.
Proof.
  intros p m. unfold Cd, c_end.
  replace (2 * m + 1 + 2)%nat with (1 + (2 * m + 2))%nat by lia.
  rewrite !lpow_add. cbn [lpow Str_app].
  rewrite (lpow_double [1] m). cbn [app].
  start_progress.
  follow cr_KL_11_10.
  align_tape.
  execute; finish_norm.
Qed.
(* ---- end of copied block ---- *)

(** ** New rules of the Baker's Dozen: G (halt), D1, RST (restart) *)

(** G: the halting configuration, one step after [c_end] (K0 = 0LM), with M reading a 1 (M1 undefined). *)
Definition c_halt (p m : nat) : Q * tape :=
  (1 >> [0; 1]^^p *> const 0) <{{M}} (0 >> [1; 0]^^(m + 2) *> 1 >> const 0).

Lemma c_halt_halted : forall p m, halted tm (c_halt p m).
Proof. intros. unfold c_halt. simpl. reflexivity. Qed.

(** G: from [Cd (p+1) (2m+1) 0], M12's HALT_step (I0, E0, the K sweep) reaches [c_end], then K0 = 0LM moves onto
    the 1 of the top (10) pair and M1 halts.  p >= 1 is needed (with p = 0, M reads a 0 and the run continues). *)
Lemma G_HALT : forall p m,
  Cd (S p) (2 * m + 1) 0 -->+ c_halt p m.
Proof.
  intros p m.
  eapply progress_evstep_trans; [apply HALT_step |].
  unfold c_end, c_halt. cbn [lpow Str_app app].
  execute.
Qed.

(** D1: [Ce p a 0 1] becomes [Ce p (a + 6) 0 0] in 6 steps (I0 E1 F0 G0 A0 B0). *)
Lemma D1 : forall p a,
  Ce p a 0 1 -->+ Ce p (a + 6) 0 0.
Proof.
  intros p a. unfold Ce. cbn [lpow Str_app app].
  replace (a + 6 + 2)%nat with (6 + (a + 2))%nat by lia.
  rewrite (lpow_add _ 6 (a + 2)).
  start_progress; finish_norm.
Qed.

(** RST: the restart.  [Xk q n] is the sweep configuration 0^inf (10)^q 1 <K (10)^n 1 0^inf. *)
Definition Xk (q n : nat) : Q * tape :=
  (1 >> [0; 1]^^q *> const 0) <{{K}} ([1; 0]^^n *> 1 >> const 0).

(** RST_entry: I0, E0, then the K sweep (cr_KL_11_10) over the 2k + 3 ones. *)
Lemma RST_entry : forall p k,
  Ce p (2 * k) 0 0 -->+ Xk p (S k).
Proof.
  intros p k. unfold Ce, Xk.
  replace (2 * k + 2)%nat with (1 + (2 * k + 1))%nat by lia.
  rewrite !lpow_add. cbn [lpow Str_app].
  rewrite (lpow_double [1] k). cbn [app].
  start_progress.
  follow cr_KL_11_10.
  finish_norm.
Qed.

(** RST_sweep_step: 6 steps (K1 L0 L0 L1 K1 L1); L0 = 1RL turns one (10) pair on the left into one more (10) on
    the right. *)
Lemma RST_sweep_step : forall q n,
  Xk (S q) n -->+ Xk q (S n).
Proof.
  intros q n. unfold Xk. cbn [lpow Str_app app].
  rewrite align_lpow. cbn [app].
  start_progress; finish_norm.
Qed.

Lemma RST_sweep : forall q n,
  Xk q n -->* Xk 0 (n + q).
Proof.
  induction q as [| q IHq]; intros n.
  - replace (n + 0)%nat with n by lia. finish.
  - eapply evstep_trans; [apply progress_evstep, RST_sweep_step |].
    follow (IHq (S n)).
    replace (S n + q)%nat with (n + S q)%nat by lia. finish.
Qed.

(** RST_restart: 11 steps; K0 = 0LM and M0 = 0LG restart the machine at the left end. *)
Lemma RST_restart : forall n,
  Xk 0 n -->+ Cd 0 1 (S (S n)).
Proof.
  intros n. unfold Xk, Cd. cbn [lpow Str_app app].
  rewrite align_lpow. cbn [app]. rewrite align_lpow_const. cbn [app].
  start_progress; finish_norm.
Qed.

(** STARTUP: 168 literal steps that consume four counter pairs and never read the other D. *)
Lemma STARTUP : forall D,
  Cd 0 1 (4 + D) -->* Cd 7 3 D.
Proof.
  intros D. unfold Cd.
  rewrite lpow_add. cbn [lpow Str_app app].
  do 168 step. finish_norm.
Qed.

(** RST: the whole tape becomes the new counter.  p + k >= 1 gives the four pairs STARTUP consumes. *)
Lemma RST : forall p k,
  1 <= p + k ->
  Ce p (2 * k) 0 0 -->+ Cd 7 3 (p + k - 1).
Proof.
  intros p k Hpk.
  eapply progress_evstep_trans; [apply RST_entry |].
  follow (RST_sweep p (S k)).
  eapply evstep_trans; [apply progress_evstep, RST_restart |].
  replace (S (S (S k + p))) with (4 + (p + k - 1))%nat by lia.
  apply STARTUP.
Qed.

(** ** START (new): 260 steps from the blank tape *)

Lemma START : c0 -->* Cd 7 3 5.
Proof.
  unfold Cd. cbn [lpow Str_app].
  do 260 step. finish_norm.
Qed.

(** ** Exact hierarchy functions W, Kc, Kd_step *)

Local Open Scope nat_scope.

(* ---- copied unchanged from BB12_M12.v: iter, iter_S', iter_add, W, W_0, W_S, BLK_iter_aux, CH_CA, CE_EVEN,
        C_REL, D_STEP (the rules KC, CREL, DSTEP).  (M12's D_REL is not copied: it uses D_REL_aux.) ---- *)
Fixpoint iter {X : Type} (n : nat) (g : X -> X) (x : X) : X :=
  match n with
  | O => x
  | S n' => g (iter n' g x)
  end.

Lemma iter_S' : forall {X : Type} n (g : X -> X) x, iter (S n) g x = iter n g (g x).
Proof. induction n; intros; simpl. - reflexivity. - rewrite <- IHn. reflexivity. Qed.

Lemma iter_add : forall {X : Type} a b (g : X -> X) x, iter (a + b) g x = iter a g (iter b g x).
Proof. induction a; intros; simpl. - reflexivity. - rewrite IHa. reflexivity. Qed.

Fixpoint W (j : nat) (b : nat) : nat :=
  match j with
  | O => b + 3
  | S j' => iter (S b) (W j') 2
  end.

Lemma W_0 : forall b, W 0 b = b + 3.
Proof. reflexivity. Qed.

Lemma W_S : forall j b, W (S j) b = iter (S b) (W j) 2.
Proof. reflexivity. Qed.

Lemma BLK_iter_aux : forall j,
  (forall b z, Ch j b z -->+ Ca j (W j b) z) ->
  forall a b z, Ca j b (blk a z) -->+ Ca (S j) (iter a (W j) b) z.
Proof.
  intros j HCh a. induction a as [| a IHa]; intros b z.
  - apply CA_SH.
  - eapply progress_evstep_trans; [apply CA_CH |].
    eapply evstep_trans; [apply progress_evstep, HCh |].
    rewrite iter_S'.
    apply progress_evstep, IHa.
Qed.

Lemma CH_CA : forall j b z,
  Ch j b z -->+ Ca j (W j b) z.
Proof.
  induction j as [| j IHj]; intros b z.
  - apply CH_0.
  - eapply progress_evstep_trans; [apply CH_S |].
    apply progress_evstep.
    apply (BLK_iter_aux j IHj (S b) 2 z).
Qed.

Lemma CE_EVEN : forall p' k c d,
  Ce (S p') (2 * k) (S c) d -->+ Ce (p' + S k) (W p' 1) c d.
Proof.
  intros p' k c d. unfold Ce.
  cbn [lpow Str_app].
  eapply progress_evstep_trans; [apply E_EVEN |].
  eapply evstep_trans; [apply progress_evstep, CH_CA |].
  follow (CA_SH_iter (S k) p' (W p' 1) (0 >> [1; 0]^^c *> 0 >> [1; 0]^^d *> const 0)%sym).
  eapply evstep_trans; [apply progress_evstep, CA_EXIT |].
  finish_norm.
Qed.

Lemma C_REL : forall p' m d,
  Cd (S p') (2 * m + 1) (S d) -->+ Ce p' (W p' 3) m d.
Proof.
  intros p' m d. unfold Ce.
  eapply progress_evstep_trans; [apply C_REL_aux |].
  eapply evstep_trans; [apply progress_evstep, CH_CA |].
  eapply evstep_trans; [apply progress_evstep, CA_EXIT |].
  finish_norm.
Qed.

Lemma D_STEP : forall p a d,
  Ce p a 0 (S (S d)) -->+ Cd p (W p (a + 4)) d.
Proof.
  intros p a d. unfold Cd.
  eapply progress_evstep_trans; [apply D_STEP_aux |].
  eapply evstep_trans; [apply progress_evstep, CH_CA |].
  eapply evstep_trans; [apply progress_evstep, CA_EXIT |].
  finish_norm.
Qed.
(* ---- end of copied block ---- *)

(** ** Growth, parity, and mod-6 invariants *)

(* ---- copied unchanged from BB12_M12.v: absmod, mods, iter_lin3, iter_par_nat, W_grow, W_par, iter_W0, W_1,
        W_1_mod6, W_S_mod6, W_S_1_mod6 ---- *)
Ltac absmod x k :=
  let q := fresh "q" in let r := fresh "r" in
  let H1 := fresh "Hdm" in let H2 := fresh "Hmb" in
  pose proof (Nat.div_mod_eq x k) as H1;
  assert (H2 : x mod k < k) by (apply Nat.mod_upper_bound; discriminate);
  set (q := x / k) in *; set (r := x mod k) in *; clearbody q r.
Ltac mods :=
  repeat match goal with
  | H : context[?x mod ?k] |- _ => absmod x k
  | |- context[?x mod ?k] => absmod x k
  | H : context[?x / ?k] |- _ => absmod x k
  | |- context[?x / ?k] => absmod x k
  end.

Lemma iter_lin3 : forall g, (forall a, a + 3 <= g a) -> forall n x, x + 3 * n <= iter n g x.
Proof.
  intros g Hg. induction n; intros; simpl. - lia.
  - specialize (IHn x). specialize (Hg (iter n g x)). lia.
Qed.

Lemma iter_par_nat : forall g, (forall y, g y mod 2 = (y + 1) mod 2) ->
  forall n x, iter n g x mod 2 = (x + n) mod 2.
Proof.
  intros g Hg. induction n; intros x; cbn [iter].
  - f_equal; lia.
  - rewrite Hg. pose proof (IHn x). mods; lia.
Qed.

Lemma W_grow : forall j b, b + 3 <= W j b.
Proof.
  induction j as [| j IHj]; intros b.
  - rewrite W_0. lia.
  - rewrite W_S.
    pose proof (iter_lin3 (W j) IHj (S b) 2). lia.
Qed.

Lemma W_par : forall j b, W j b mod 2 = (b + 1) mod 2.
Proof.
  induction j as [| j IHj]; intros b.
  - rewrite W_0. mods; lia.
  - rewrite W_S. rewrite (iter_par_nat (W j) IHj). mods; lia.
Qed.

Lemma iter_W0 : forall n x, iter n (W 0) x = x + 3 * n.
Proof.
  induction n as [| n IHn]; intros x; cbn [iter].
  - lia.
  - rewrite W_0, IHn. lia.
Qed.

Lemma W_1 : forall b, W 1 b = 3 * b + 5.
Proof.
  intros b. rewrite W_S, iter_W0. lia.
Qed.

Lemma W_1_mod6 : forall b,
  W 1 b mod 6 = (if b mod 2 =? 0 then 5 else 2).
Proof.
  intros b. rewrite W_1.
  destruct (b mod 2 =? 0) eqn:Heq;
    [apply Nat.eqb_eq in Heq | apply Nat.eqb_neq in Heq];
    mods; lia.
Qed.

Lemma W_S_mod6 : forall j b,
  W (S j) b mod 6 = (if b mod 2 =? 0 then 5 else 2).
Proof.
  induction j as [| j IHj]; intros b.
  - apply W_1_mod6.
  - change (W (S (S j)) b) with (iter (S b) (W (S j)) 2).
    cbn [iter].
    rewrite (IHj (iter b (W (S j)) 2)).
    rewrite (iter_par_nat (W (S j)) (W_par (S j)) b 2).
    replace ((2 + b) mod 2) with (b mod 2) by (mods; lia).
    reflexivity.
Qed.

Lemma W_S_1_mod6 : forall j, W (S j) 1 mod 6 = 2.
Proof.
  intros j. rewrite W_S_mod6. reflexivity.
Qed.
(* ---- end of copied block ---- *)

(** ** New: W modulo 81 (the 3-adic fact the halting argument needs) *)

(** [W 2 y = (3^(y+3) - 5) / 2]: W_1 is b -> 3b + 5, and 2x + 5 is multiplied by 3 at each application. *)
Lemma iter_W1_pow : forall n, 2 * iter n (W 1) 2 + 5 = 3 ^ (n + 2).
Proof.
  induction n as [| n IHn]; cbn [iter].
  - reflexivity.
  - rewrite W_1. replace (S n + 2) with (S (n + 2)) by lia. rewrite Nat.pow_succ_r'. lia.
Qed.

Lemma W2_pow : forall y, 2 * W 2 y + 5 = 3 ^ (y + 3).
Proof.
  intros y. rewrite W_S. replace (y + 3) with (S y + 2) by lia. apply iter_W1_pow.
Qed.

(** Fact (A) of the paper proof: for j >= 2, 2 W j b + 5 is a power of 3, 3^(y+3) with y >= b. *)
Lemma W_pow3 : forall j b, exists y, b <= y /\ 2 * W (S (S j)) b + 5 = 3 ^ (y + 3).
Proof.
  induction j as [| j IHj]; intros b.
  - exists b. split; [lia | apply W2_pow].
  - rewrite W_S. cbn [iter].
    destruct (IHj (iter b (W (S (S j))) 2)) as [y [Hy Hpow]].
    exists y. split; [| exact Hpow].
    pose proof (iter_lin3 (W (S (S j))) (W_grow (S (S j))) b 2). lia.
Qed.

Lemma W2_mod81 : forall y, 1 <= y -> W 2 y mod 81 = 38.
Proof.
  intros y Hy. pose proof (W2_pow y) as H.
  replace (y + 3) with (4 + (y - 1)) in H by lia.
  rewrite Nat.pow_add_r in H. change (3 ^ 4) with 81 in H.
  set (t := 3 ^ (y - 1)) in *. clearbody t.
  mods; lia.
Qed.

(** For every level j >= 3 and every argument b, W j b = 38 (mod 81). *)
Lemma W_mod81 : forall j b, W (S (S (S j))) b mod 81 = 38.
Proof.
  induction j as [| j IHj]; intros b.
  - rewrite W_S. cbn [iter]. apply W2_mod81.
    pose proof (iter_lin3 (W 2) (W_grow 2) b 2). lia.
  - rewrite W_S. cbn [iter]. apply IHj.
Qed.

Opaque W.

(* ---- copied unchanged from BB12_M12.v: Kc, Kc_step, Kc_props, Kc_mod6, Kc_loop, Kc_loop_mod6, Kc_full,
        Kc_full_all, Kd_step, Kd_step_all, Kd_iter, Kd_loop (they use only CE_EVEN, C_REL, D_STEP) ---- *)
Definition Kc (pa : nat * nat) : nat * nat :=
  let '(p, a) := pa in
  (p + a / 2, W (p - 1) 1).

Lemma Kc_step : forall c d pa,
  1 <= fst pa -> snd pa mod 2 = 0 ->
  Ce (fst pa) (snd pa) (S c) d -->+ Ce (fst (Kc pa)) (snd (Kc pa)) c d.
Proof.
  intros c d [p a] Hp Hev. cbn [fst snd Kc] in *.
  destruct p as [| p']; [lia |].
  replace (S p' - 1) with p' by lia.
  assert (Ha : a = 2 * (a / 2)) by (mods; lia).
  replace (S p' + a / 2) with (p' + S (a / 2)) by lia.
  rewrite Ha at 1.
  apply CE_EVEN.
Qed.

Lemma Kc_props : forall pa,
  1 <= fst pa -> 2 <= snd pa -> snd pa mod 2 = 0 ->
  fst pa + 1 <= fst (Kc pa) /\
  2 <= snd (Kc pa) /\
  snd (Kc pa) mod 2 = 0.
Proof.
  intros [p a] Hp Ha Hev. cbn [fst snd Kc] in *.
  pose proof (W_grow (p - 1) 1).
  pose proof (W_par (p - 1) 1).
  split; [| split]; mods; lia.
Qed.

Lemma Kc_mod6 : forall pa,
  2 <= fst pa -> snd (Kc pa) mod 6 = 2.
Proof.
  intros [p a] Hp. cbn [fst snd Kc] in *.
  destruct p as [| [| p']]; [lia | lia |].
  replace (S (S p') - 1) with (S p') by lia.
  apply W_S_1_mod6.
Qed.

Lemma Kc_loop : forall c d pa,
  1 <= fst pa -> 2 <= snd pa -> snd pa mod 2 = 0 ->
  Ce (fst pa) (snd pa) c d -->* Ce (fst (iter c Kc pa)) (snd (iter c Kc pa)) 0 d /\
  fst pa + c <= fst (iter c Kc pa) /\
  2 <= snd (iter c Kc pa) /\
  snd (iter c Kc pa) mod 2 = 0.
Proof.
  induction c as [| c IHc]; intros d pa Hp Ha Hev.
  - cbn [iter]. split; [finish | split; [lia | split; [lia | exact Hev]]].
  - rewrite iter_S'.
    destruct (Kc_props pa Hp Ha Hev) as [Hp1 [Ha1 Hm1]].
    destruct (IHc d (Kc pa) ltac:(lia) Ha1 Hm1) as [Hrun [Hp2 [Ha2 Hm2]]].
    split; [| split; [| split]].
    + eapply evstep_trans; [apply progress_evstep, (Kc_step c d pa Hp Hev) | exact Hrun].
    + lia.
    + exact Ha2.
    + exact Hm2.
Qed.

Lemma Kc_loop_mod6 : forall c pa,
  2 <= fst pa -> 2 <= snd pa -> snd pa mod 2 = 0 ->
  snd (iter (S c) Kc pa) mod 6 = 2.
Proof.
  intros c pa Hp Ha Hev.
  replace (S c) with (1 + c) by lia.
  rewrite iter_add. cbn [iter].
  destruct (Kc_loop c 0 pa ltac:(lia) Ha Hev) as [_ [Hp' _]].
  apply Kc_mod6. lia.
Qed.

Definition Kc_full (pb : nat * nat) : nat * nat :=
  let '(p, b) := pb in
  iter (b / 2) Kc (p - 1, W (p - 1) 3).

Lemma Kc_full_all : forall d pb,
  3 <= fst pb -> 3 <= snd pb -> snd pb mod 2 = 1 ->
  Cd (fst pb) (snd pb) (S d) -->+ Ce (fst (Kc_full pb)) (snd (Kc_full pb)) 0 d /\
  fst pb <= fst (Kc_full pb) /\
  2 <= snd (Kc_full pb) /\
  snd (Kc_full pb) mod 2 = 0 /\
  snd (Kc_full pb) mod 6 = 2.
Proof.
  intros d [p b] Hp Hb Hodd. cbn [fst snd Kc_full] in *.
  destruct p as [| p']; [lia |].
  replace (S p' - 1) with p' by lia.
  assert (Hb_eq : b = 2 * (b / 2) + 1) by (mods; lia).
  assert (Hb_ge : 1 <= b / 2) by (mods; lia).
  pose proof (W_grow p' 3) as Hw3_grow.
  pose proof (W_par p' 3) as Hw3_par.
  assert (Hw3_ev : W p' 3 mod 2 = 0) by (mods; lia).
  destruct (Kc_loop (b / 2) d (p', W p' 3) ltac:(cbn; lia) ltac:(cbn; lia) Hw3_ev)
    as [Hrun [Hp1 [Ha1 Hm1]]].
  assert (Hm6 : snd (iter (b / 2) Kc (p', W p' 3)) mod 6 = 2).
  { replace (b / 2) with (S (b / 2 - 1)) by lia.
    apply Kc_loop_mod6; cbn [fst snd]; [lia | lia | exact Hw3_ev]. }
  cbn [fst snd] in *.
  split; [| split; [| split; [| split]]].
  - rewrite Hb_eq at 1.
    eapply progress_evstep_trans; [apply C_REL | exact Hrun].
  - lia.
  - exact Ha1.
  - exact Hm1.
  - exact Hm6.
Qed.

Definition Kd_step (pb : nat * nat) : nat * nat :=
  let '(p', a') := Kc_full pb in
  (p', W p' (a' + 4)).

Lemma Kd_step_all : forall d pb,
  3 <= fst pb -> 3 <= snd pb -> snd pb mod 2 = 1 ->
  Cd (fst pb) (snd pb) (S (S (S d))) -->+ Cd (fst (Kd_step pb)) (snd (Kd_step pb)) d /\
  fst pb <= fst (Kd_step pb) /\
  3 <= snd (Kd_step pb) /\
  snd (Kd_step pb) mod 2 = 1.
Proof.
  intros d pb Hp Hb Hodd.
  unfold Kd_step.
  destruct (Kc_full_all (S (S d)) pb Hp Hb Hodd) as [Hkc [Hp1 [Ha1 [Hm1 _]]]].
  set (pa' := Kc_full pb) in *.
  destruct pa' as [p' a']. cbn [fst snd] in *.
  pose proof (W_grow p' (a' + 4)) as Hwg.
  pose proof (W_par p' (a' + 4)) as Hwp.
  split; [| split; [| split]].
  - eapply progress_evstep_trans; [exact Hkc | apply progress_evstep, D_STEP].
  - exact Hp1.
  - lia.
  - mods; lia.
Qed.

Definition Kd_iter (m : nat) (pb : nat * nat) : nat * nat :=
  iter m Kd_step pb.

Lemma Kd_loop : forall m r pb,
  3 <= fst pb -> 3 <= snd pb -> snd pb mod 2 = 1 ->
  Cd (fst pb) (snd pb) (3 * m + r) -->* Cd (fst (Kd_iter m pb)) (snd (Kd_iter m pb)) r /\
  fst pb <= fst (Kd_iter m pb) /\
  3 <= snd (Kd_iter m pb) /\
  snd (Kd_iter m pb) mod 2 = 1.
Proof.
  unfold Kd_iter.
  induction m as [| m IHm]; intros r pb Hp Hb Hodd.
  - cbn [iter]. replace (3 * 0 + r) with r by lia.
    split; [finish | split; [lia | split; [exact Hb | exact Hodd]]].
  - rewrite iter_S'.
    replace (3 * S m + r) with (S (S (S (3 * m + r)))) by lia.
    destruct (Kd_step_all (3 * m + r) pb Hp Hb Hodd) as [Hstep [Hp1 [Hb1 Hm1]]].
    destruct (IHm r (Kd_step pb) ltac:(lia) Hb1 Hm1) as [Hrun [Hp2 [Hb2 Hm2]]].
    split; [| split; [| split]].
    + eapply evstep_trans; [apply progress_evstep, Hstep | exact Hrun].
    + lia.
    + exact Hb2.
    + exact Hm2.
Qed.
(* ---- end of copied block ---- *)

(** ** New: residues of the Kc / Kd functions modulo 81 *)

(** At level >= 3 every accumulator Kc produces is W _ 1 = 38 (mod 81) and even, i.e. = 38 (mod 162), so each Kc
    step adds 19 (mod 81) to p. *)
Lemma Kc_res : forall pa,
  4 <= fst pa -> snd pa mod 162 = 38 ->
  4 <= fst (Kc pa) /\ snd (Kc pa) mod 162 = 38 /\ fst (Kc pa) mod 81 = (fst pa + 19) mod 81.
Proof.
  intros [p a] Hp Ha. cbn [fst snd Kc] in *.
  destruct p as [| [| [| [| p']]]]; try lia.
  replace (S (S (S (S p'))) - 1) with (S (S (S p'))) by lia.
  pose proof (W_mod81 p' 1) as H81.
  pose proof (W_par (S (S (S p'))) 1) as H2.
  split; [lia | split]; mods; lia.
Qed.

Lemma Kc_iter_res : forall c pa,
  4 <= fst pa -> snd pa mod 162 = 38 ->
  4 <= fst (iter c Kc pa) /\ snd (iter c Kc pa) mod 162 = 38 /\
  fst (iter c Kc pa) mod 81 = (fst pa + 19 * c) mod 81.
Proof.
  induction c as [| c IHc]; intros pa Hp Ha.
  - cbn [iter]. split; [lia | split; [exact Ha | f_equal; lia]].
  - cbn [iter].
    destruct (IHc pa Hp Ha) as [H1 [H2 H3]].
    destruct (Kc_res (iter c Kc pa) H1 H2) as [H4 [H5 H6]].
    split; [exact H4 | split; [exact H5 |]].
    rewrite H6. clear H4 H5 H6.
    set (x := fst (iter c Kc pa)) in *. clearbody x.
    mods; lia.
Qed.

Lemma Kc_full_res : forall pb,
  5 <= fst pb ->
  4 <= fst (Kc_full pb) /\ snd (Kc_full pb) mod 162 = 38 /\
  fst (Kc_full pb) mod 81 = (fst pb - 1 + 19 * (snd pb / 2)) mod 81.
Proof.
  intros [p b] Hp. cbn [fst snd Kc_full] in *.
  destruct p as [| [| [| [| [| p']]]]]; try lia.
  replace (S (S (S (S (S p')))) - 1) with (S (S (S (S p')))) by lia.
  pose proof (W_mod81 (S p') 3) as H81.
  pose proof (W_par (S (S (S (S p')))) 3) as H2.
  assert (H162 : W (S (S (S (S p')))) 3 mod 162 = 38) by (mods; lia).
  destruct (Kc_iter_res (b / 2) (S (S (S (S p'))), W (S (S (S (S p')))) 3) ltac:(cbn; lia) H162)
    as [Hp1 [Ha1 Hm1]].
  cbn [fst] in Hm1.
  split; [exact Hp1 | split; [exact Ha1 | exact Hm1]].
Qed.

(** A Kd step ends with W p' (a' + 4), at level >= 3 and with an even argument: = 38 (mod 81) and odd. *)
Lemma Kd_step_res : forall pb,
  5 <= fst pb ->
  fst (Kd_step pb) = fst (Kc_full pb) /\ snd (Kd_step pb) mod 162 = 119.
Proof.
  intros pb Hp. unfold Kd_step.
  destruct (Kc_full_res pb Hp) as [Hp1 [Ha1 _]].
  set (pa' := Kc_full pb) in *.
  destruct pa' as [p' a']. cbn [fst snd] in *.
  split; [reflexivity |].
  destruct p' as [| [| [| p'']]]; try lia.
  pose proof (W_mod81 p'' (a' + 4)) as H81.
  pose proof (W_par (S (S (S p''))) (a' + 4)) as H2.
  mods; lia.
Qed.

(** From [Cd 7 3 _], the n-th Kd step (n >= 1) leaves p = 25 + 67 (n - 1) (mod 81). *)
Lemma Kd_iter_res : forall n,
  7 <= fst (Kd_iter (S n) (7, 3)) /\ snd (Kd_iter (S n) (7, 3)) mod 162 = 119 /\
  fst (Kd_iter (S n) (7, 3)) mod 81 = (25 + 67 * n) mod 81.
Proof.
  induction n as [| n IHn].
  - unfold Kd_iter. cbn [iter].
    destruct (Kd_step_all 0 (7, 3) ltac:(cbn; lia) ltac:(cbn; lia) eq_refl) as [_ [Hp _]].
    destruct (Kd_step_res (7, 3) ltac:(cbn; lia)) as [Hf Hs].
    destruct (Kc_full_res (7, 3) ltac:(cbn; lia)) as [_ [_ Hm]].
    cbn [fst snd] in *.
    split; [lia | split; [exact Hs |]].
    rewrite Hf, Hm. reflexivity.
  - destruct IHn as [Hp [Hs Hm]].
    unfold Kd_iter in *. cbn [iter] in *.
    set (pb := Kd_step (iter n Kd_step (7, 3))) in *.
    assert (Hodd : snd pb mod 2 = 1) by (mods; lia).
    destruct (Kd_step_all 0 pb ltac:(lia) ltac:(mods; lia) Hodd) as [_ [Hp1 _]].
    destruct (Kd_step_res pb ltac:(lia)) as [Hf Hs1].
    destruct (Kc_full_res pb ltac:(lia)) as [_ [_ Hm1]].
    split; [lia | split; [exact Hs1 |]].
    rewrite Hf, Hm1. clear Hf Hs1 Hm1 Hp1 Hodd.
    set (P := fst pb) in *. set (Bv := snd pb) in *. clearbody P Bv.
    mods; lia.
Qed.

(** ** New: one round with remainder 2, and its counter modulo 81 *)

(** From [Cd 7 3 d] with d = 3n + 2: n Kd steps (Kd_loop), then C_REL and the KC steps (Kc_full_all) leave
    [Ce p' a' 0 1], D1 gives [Ce p' (a' + 6) 0 0], and RST restarts at [Cd 7 3 (p' + a'/2 + 2)]. *)
Definition round2 (d : nat) : nat :=
  fst (Kc_full (Kd_iter (d / 3) (7, 3))) + snd (Kc_full (Kd_iter (d / 3) (7, 3))) / 2 + 2.

Lemma round2_run : forall d,
  d mod 3 = 2 -> Cd 7 3 d -->+ Cd 7 3 (round2 d).
Proof.
  intros d Hd. unfold round2.
  assert (Hdn : d = 3 * (d / 3) + 2) by (pose proof (Nat.div_mod_eq d 3); lia).
  destruct (Kd_loop (d / 3) 2 (7, 3) ltac:(cbn; lia) ltac:(cbn; lia) eq_refl) as [Hloop [Hp [Hb Hodd]]].
  cbn [fst snd] in Hloop, Hp.
  set (pb := Kd_iter (d / 3) (7, 3)) in *.
  destruct (Kc_full_all 1 pb ltac:(lia) Hb Hodd) as [Hkc [Hp1 [Ha1 [Hev _]]]].
  set (pa := Kc_full pb) in *.
  rewrite Hdn at 1.
  eapply evstep_progress_trans; [exact Hloop |].
  eapply progress_trans; [exact Hkc |].
  eapply progress_trans; [apply D1 |].
  assert (Ha6 : snd pa + 6 = 2 * (snd pa / 2 + 3)) by (mods; lia).
  rewrite Ha6.
  replace (fst pa + snd pa / 2 + 2) with (fst pa + (snd pa / 2 + 3) - 1) by lia.
  apply RST. lia.
Qed.

(** The counter after a round: round2 d = 46 + 67 (d / 3) (mod 81). *)
Lemma round2_res : forall d,
  3 <= d -> 9 <= round2 d /\ round2 d mod 81 = (46 + 67 * (d / 3)) mod 81.
Proof.
  intros d Hd. unfold round2.
  assert (Hn : exists n, d / 3 = S n)
    by (exists (d / 3 - 1); pose proof (Nat.div_mod_eq d 3); pose proof (Nat.mod_upper_bound d 3); lia).
  destruct Hn as [n Hn]. rewrite Hn.
  destruct (Kd_iter_res n) as [Hp [Hs Hm]].
  set (pb := Kd_iter (S n) (7, 3)) in *.
  assert (Hodd : snd pb mod 2 = 1) by (mods; lia).
  destruct (Kc_full_all 0 pb ltac:(lia) ltac:(mods; lia) Hodd) as [_ [Hp1 [Ha1 _]]].
  destruct (Kc_full_res pb ltac:(lia)) as [_ [Ha2 Hm2]].
  set (pa := Kc_full pb) in *.
  clearbody pa pb. destruct pa as [p' a']. destruct pb as [P Bv]. cbn [fst snd] in *.
  split; [lia |].
  mods; lia.
Qed.

(** ** The full run of the Baker's Dozen *)

(** Round 0 starts at [Cd 7 3 5] (START); rounds 0-3 end with remainder 2 and restart; round 4 has remainder 0
    and halts (G). *)
Definition d1 : nat := round2 5.
Definition d2 : nat := round2 d1.
Definition d3 : nat := round2 d2.
Definition d4 : nat := round2 d3.
Definition pb4 : nat * nat := Kd_iter (d4 / 3) (7, 3).

Lemma round2_def : forall d,
  round2 d = fst (Kc_full (Kd_iter (d / 3) (7, 3))) + snd (Kc_full (Kd_iter (d / 3) (7, 3))) / 2 + 2.
Proof. reflexivity. Qed.
Lemma d1_def : d1 = round2 5. Proof. reflexivity. Qed.
Lemma d2_def : d2 = round2 d1. Proof. reflexivity. Qed.
Lemma d3_def : d3 = round2 d2. Proof. reflexivity. Qed.
Lemma d4_def : d4 = round2 d3. Proof. reflexivity. Qed.
Lemma pb4_def : pb4 = Kd_iter (d4 / 3) (7, 3). Proof. reflexivity. Qed.

Opaque Kc Kc_full Kd_step Kd_iter round2 d1 d2 d3 d4 pb4.

(** The counters d1..d4 are f_omega-sized constants: the arithmetic below is done in lemmas over variables and
    then instantiated, so that no tactic tries to unfold or evaluate them. *)
Lemma res_81_27 : forall y x, y mod 81 = 32 -> x mod 81 = (46 + 67 * (y / 3)) mod 81 -> x mod 27 = 14.
Proof. intros y x H1 H2. mods; lia. Qed.

Lemma res_27_9 : forall y x, y mod 27 = 14 -> x mod 81 = (46 + 67 * (y / 3)) mod 81 -> x mod 9 = 8.
Proof. intros y x H1 H2. mods; lia. Qed.

Lemma res_9_3 : forall y x, y mod 9 = 8 -> x mod 81 = (46 + 67 * (y / 3)) mod 81 -> x mod 3 = 0.
Proof. intros y x H1 H2. mods; lia. Qed.

Lemma res_rem2 : forall y, y mod 81 = 32 \/ y mod 27 = 14 \/ y mod 9 = 8 -> y mod 3 = 2.
Proof. intros y H. mods; lia. Qed.

Lemma le_3_9 : forall y, 9 <= y -> 3 <= y.
Proof. intros. lia. Qed.

(** The counters: d1 = 32 (mod 81), d2 = 14 (mod 27), d3 = 8 (mod 9), d4 = 0 (mod 3). *)
Lemma d1_res : 9 <= d1 /\ d1 mod 81 = 32.
Proof.
  rewrite d1_def. destruct (round2_res 5 ltac:(lia)) as [H1 H2].
  split; [exact H1 | rewrite H2; reflexivity].
Qed.

Lemma d2_res : 9 <= d2 /\ d2 mod 27 = 14.
Proof.
  destruct d1_res as [H1 H2].
  rewrite d2_def. destruct (round2_res d1 (le_3_9 d1 H1)) as [H3 H4].
  exact (conj H3 (res_81_27 d1 (round2 d1) H2 H4)).
Qed.

Lemma d3_res : 9 <= d3 /\ d3 mod 9 = 8.
Proof.
  destruct d2_res as [H1 H2].
  rewrite d3_def. destruct (round2_res d2 (le_3_9 d2 H1)) as [H3 H4].
  exact (conj H3 (res_27_9 d2 (round2 d2) H2 H4)).
Qed.

Lemma d4_res : d4 mod 3 = 0.
Proof.
  destruct d3_res as [H1 H2].
  rewrite d4_def. destruct (round2_res d3 (le_3_9 d3 H1)) as [H3 H4].
  exact (res_9_3 d3 (round2 d3) H2 H4).
Qed.

Lemma run_d4 : c0 -->* Cd 7 3 d4.
Proof.
  pose proof (round2_run 5 eq_refl) as R0. rewrite <- d1_def in R0.
  pose proof (round2_run d1 (res_rem2 d1 (or_introl (proj2 d1_res)))) as R1.
  rewrite <- d2_def in R1.
  pose proof (round2_run d2 (res_rem2 d2 (or_intror (or_introl (proj2 d2_res))))) as R2.
  rewrite <- d3_def in R2.
  pose proof (round2_run d3 (res_rem2 d3 (or_intror (or_intror (proj2 d3_res))))) as R3.
  rewrite <- d4_def in R3.
  follow START.
  eapply evstep_trans; [apply progress_evstep, R0 |].
  eapply evstep_trans; [apply progress_evstep, R1 |].
  eapply evstep_trans; [apply progress_evstep, R2 |].
  apply progress_evstep, R3.
Qed.

(** The last round: remainder 0, so the Kd loop ends at [Cd p b 0] and G halts the machine. *)
Lemma Kd_from_7_3 : forall n,
  7 <= fst (Kd_iter n (7, 3)) /\ 3 <= snd (Kd_iter n (7, 3)) /\ snd (Kd_iter n (7, 3)) mod 2 = 1.
Proof.
  intros n.
  destruct (Kd_loop n 0 (7, 3) ltac:(cbn; lia) ltac:(cbn; lia) eq_refl) as [_ [Hp [Hb Hodd]]].
  cbn [fst snd] in Hp.
  split; [exact Hp | split; [exact Hb | exact Hodd]].
Qed.

Lemma run_last_round : forall d,
  c0 -->* Cd 7 3 d -> d mod 3 = 0 ->
  c0 -->* Cd (fst (Kd_iter (d / 3) (7, 3))) (snd (Kd_iter (d / 3) (7, 3))) 0.
Proof.
  intros d Hrun Hd.
  assert (Hdd : d = 3 * (d / 3) + 0) by (pose proof (Nat.div_mod_eq d 3); lia).
  set (n := d / 3) in *. clearbody n. subst d.
  destruct (Kd_loop n 0 (7, 3) ltac:(cbn; lia) ltac:(cbn; lia) eq_refl) as [Hloop _].
  cbn [fst snd] in Hloop.
  follow Hrun. exact Hloop.
Qed.

Lemma run_halt_gen : forall pb,
  c0 -->* Cd (fst pb) (snd pb) 0 -> 1 <= fst pb -> snd pb mod 2 = 1 ->
  c0 -->* c_halt (fst pb - 1) (snd pb / 2).
Proof.
  intros [p b] Hrun Hp Hodd. cbn [fst snd] in *.
  destruct p as [| p']; [lia |].
  replace (S p' - 1) with p' by lia.
  assert (Hb : b = 2 * (b / 2) + 1) by (mods; lia).
  set (m := b / 2) in *. clearbody m. subst b.
  follow Hrun.
  apply progress_evstep, G_HALT.
Qed.

Lemma pb4_props : 7 <= fst pb4 /\ 3 <= snd pb4 /\ snd pb4 mod 2 = 1.
Proof. rewrite pb4_def. apply Kd_from_7_3. Qed.

Lemma run_halt : c0 -->* c_halt (fst pb4 - 1) (snd pb4 / 2).
Proof.
  destruct pb4_props as [Hp [_ Hodd]].
  apply run_halt_gen; [| exact (Nat.le_trans 1 7 _ ltac:(lia) Hp) | exact Hodd].
  rewrite pb4_def.
  exact (run_last_round d4 run_d4 d4_res).
Qed.

Theorem halt : halts tm c0.
Proof.
  destruct (with_counter run_halt) as [n Hn].
  eapply halts_multistep; [| exact Hn].
  apply halted_halts. apply c_halt_halted.
Qed.
