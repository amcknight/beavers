(** * BBi(8) holdouts #7 and #8: the arithmetic of the map h *)
(** Credit and how this was made: see README.md in the bbi8 folder. *)

(** Both machines follow the orbit of 2 under the map

      h(y) = y - 1 + 2^(nu(y) + 2),

    where [nu y] is the number of trailing zeros of [y] in binary, and they can
    only halt on a power of 2 (see BBi8_3x4_Tape.v). This file shows that the
    orbit of 2 contains no power of 2 from 4 up.

    - Three facts about h: [h_gt], [h_odd], [h_double].
    - Self-similarity ([selfsim]): from [Q * 2^m] the orbit's next multiple of
      [2^m] is [(h Q + 2m) * 2^m].
    - The ladder ([ladder]): the orbit of 2 passes every rung
      [(2m - 1) * 2^m], [m >= 2].
    - Slow zeros ([slow_zeros]): every number on the orbit of 2 that is a
      multiple of [2^m] is at least the rung [(2m - 1) * 2^m]. The orbit gains
      trailing zeros too slowly to reach a power of 2 ([no_pow2], [no_pow4]).
    - The invariant [Inv] of the bounce configurations, used by the tape file.

    Standard library only. *)

From Coq Require Import Arith Lia.

(** ** Powers of 2 *)

Lemma pow2_pos : forall n, 1 <= 2 ^ n.
Proof.
  induction n as [|n IH].
  - simpl. lia.
  - change (2 ^ S n) with (2 * 2 ^ n). lia.
Qed.

Lemma pow2_add : forall a b, 2 ^ (a + b) = 2 ^ a * 2 ^ b.
Proof.
  induction a as [|a IH]; intros b.
  - change (2 ^ (0 + b)) with (2 ^ b). change (2 ^ 0) with 1. lia.
  - change (2 ^ (S a + b)) with (2 * 2 ^ (a + b)).
    change (2 ^ S a) with (2 * 2 ^ a).
    rewrite IH. rewrite Nat.mul_assoc. reflexivity.
Qed.

Lemma pow2_le_mono : forall a b, a <= b -> 2 ^ a <= 2 ^ b.
Proof.
  intros a b H.
  replace b with ((b - a) + a) by lia.
  rewrite pow2_add.
  pose proof (pow2_pos (b - a)). nia.
Qed.

(** [2^a] divides [2^b] when [a <= b]. *)
Lemma pow2_mod : forall a b, a <= b -> 2 ^ b mod 2 ^ a = 0.
Proof.
  intros a b H.
  replace b with ((b - a) + a) by lia.
  rewrite pow2_add.
  apply Nat.Div0.mod_mul.
Qed.

Lemma pow4 : forall k, 4 ^ k = 2 ^ (2 * k).
Proof.
  induction k as [|k IH].
  - reflexivity.
  - replace (2 * S k) with (S (S (2 * k))) by lia.
    change (4 ^ S k) with (4 * 4 ^ k).
    change (2 ^ S (S (2 * k))) with (2 * (2 * 2 ^ (2 * k))).
    rewrite IH. lia.
Qed.

(** If [2P] divides [w] then [P] divides [w]. *)
Lemma mod_halve : forall w P, 1 <= P -> w mod (2 * P) = 0 -> w mod P = 0.
Proof.
  intros w P HP H.
  pose proof (Nat.div_mod_eq w (2 * P)) as E.
  rewrite H, Nat.add_0_r in E.
  set (X := w / (2 * P)) in E.
  rewrite E.
  replace (2 * P * X) with ((2 * X) * P) by nia.
  apply Nat.Div0.mod_mul.
Qed.

(** An odd multiple of [P] is not a multiple of [2P]. *)
Lemma odd_mul_mod : forall a P, 1 <= P -> ((2 * a + 1) * P) mod (2 * P) = P.
Proof.
  intros a P HP.
  replace ((2 * a + 1) * P) with (P + a * (2 * P)) by nia.
  rewrite Nat.Div0.mod_add.
  apply Nat.mod_small. lia.
Qed.

Lemma mul_ge_r : forall a b, 1 <= a -> b <= a * b.
Proof.
  intros a b Ha. destruct a as [|a]; [lia|].
  simpl. lia.
Qed.

Lemma mul_le_r : forall a b c, a <= b -> a * c <= b * c.
Proof.
  intros a b c H.
  replace b with (a + (b - a)) by lia.
  rewrite Nat.mul_add_distr_r. lia.
Qed.

(** ** The 2-adic valuation and the map h *)

(** [nu_fuel f y] is the number of trailing zero bits of [y] when [y <= f]. *)
Fixpoint nu_fuel (fuel y : nat) : nat :=
  match fuel with
  | O => 0
  | S f => if y mod 2 =? 0 then (if y =? 0 then 0 else S (nu_fuel f (y / 2))) else 0
  end.

Definition nu (y : nat) : nat := nu_fuel y y.

Definition h (y : nat) : nat := y - 1 + 2 ^ (nu y + 2).

Lemma nu_fuel_eq : forall f g y, y <= f -> y <= g -> nu_fuel f y = nu_fuel g y.
Proof.
  induction f as [|f IH]; intros g y Hf Hg.
  - assert (y = 0) as -> by lia. destruct g; reflexivity.
  - destruct g as [|g].
    + assert (y = 0) as -> by lia. reflexivity.
    + cbn [nu_fuel].
      destruct (y mod 2 =? 0); [|reflexivity].
      destruct (y =? 0) eqn:Z; [reflexivity|].
      assert (Hy : y <> 0) by (intro E; rewrite E in Z; simpl in Z; discriminate Z).
      f_equal.
      pose proof (Nat.div_lt y 2 ltac:(lia) ltac:(lia)).
      apply IH; lia.
Qed.

Lemma nu_eq : forall y,
  nu y = if y mod 2 =? 0 then (if y =? 0 then 0 else S (nu (y / 2))) else 0.
Proof.
  intros [|y].
  - reflexivity.
  - unfold nu at 1. cbn [nu_fuel].
    destruct (S y mod 2 =? 0); [|reflexivity].
    destruct (S y =? 0); [reflexivity|].
    f_equal. unfold nu. apply nu_fuel_eq.
    + pose proof (Nat.div_lt (S y) 2 ltac:(lia) ltac:(lia)). lia.
    + lia.
Qed.

Lemma nu_even : forall y, 1 <= y -> y mod 2 = 0 -> nu y = S (nu (y / 2)).
Proof.
  intros y Hy E. rewrite (nu_eq y), E.
  destruct (y =? 0) eqn:Z.
  - apply Nat.eqb_eq in Z. lia.
  - reflexivity.
Qed.

Lemma nu_odd : forall y, y mod 2 = 1 -> nu y = 0.
Proof. intros y E. rewrite (nu_eq y), E. reflexivity. Qed.

Lemma odd_mod : forall y, Nat.Odd y -> y mod 2 = 1.
Proof.
  intros y [m Hm]. subst y.
  replace (2 * m + 1) with (1 + m * 2) by lia.
  rewrite Nat.Div0.mod_add. reflexivity.
Qed.

Lemma nu_double : forall y, 1 <= y -> nu (2 * y) = S (nu y).
Proof.
  intros y Hy.
  assert (M : (2 * y) mod 2 = 0).
  { rewrite Nat.mul_comm. apply Nat.Div0.mod_mul. }
  assert (D : 2 * y / 2 = y).
  { rewrite Nat.mul_comm. apply Nat.div_mul. lia. }
  rewrite (nu_even (2 * y) ltac:(lia) M), D. reflexivity.
Qed.

(** [y = 2^(nu y) * odd]. *)
Lemma nu_spec_aux : forall n y, y <= n -> 1 <= y -> exists o, y = 2 ^ nu y * (2 * o + 1).
Proof.
  induction n as [|n IH]; intros y Hn Hy.
  - lia.
  - pose proof (Nat.div_mod_eq y 2) as D.
    pose proof (Nat.mod_upper_bound y 2 ltac:(lia)) as B.
    destruct (Nat.eq_dec (y mod 2) 0) as [E|E].
    + rewrite (nu_even y Hy E).
      destruct (IH (y / 2) ltac:(lia) ltac:(lia)) as [o Ho].
      exists o. change (2 ^ S (nu (y / 2))) with (2 * 2 ^ nu (y / 2)).
      rewrite E, Nat.add_0_r in D. rewrite Ho in D. nia.
    + assert (E1 : y mod 2 = 1) by lia.
      rewrite (nu_odd y E1). exists (y / 2). change (2 ^ 0) with 1. lia.
Qed.

Lemma nu_spec : forall y, 1 <= y -> exists o, y = 2 ^ nu y * (2 * o + 1).
Proof. intros y Hy. exact (nu_spec_aux y y (le_n y) Hy). Qed.

Lemma nu_lt : forall L y, 1 <= y -> y < 2 ^ L -> nu y < L.
Proof.
  intros L y Hy HL.
  destruct (Nat.le_gt_cases L (nu y)) as [H|H]; [|exact H].
  exfalso. destruct (nu_spec y Hy) as [o Ho].
  pose proof (pow2_le_mono _ _ H). nia.
Qed.

(** ** Three facts about h *)

(** [h y >= y + 3], so every orbit is strictly increasing. *)
Lemma h_gt : forall y, 1 <= y -> y + 3 <= h y.
Proof.
  intros y Hy. unfold h.
  assert (4 <= 2 ^ (nu y + 2)).
  { rewrite pow2_add. change (2 ^ 2) with 4. pose proof (pow2_pos (nu y)). lia. }
  lia.
Qed.

(** [h y = y + 3] for odd [y]. *)
Lemma h_odd : forall y, Nat.Odd y -> h y = y + 3.
Proof.
  intros y Hy. unfold h. rewrite (nu_odd y (odd_mod y Hy)).
  change (2 ^ (0 + 2)) with 4.
  destruct Hy as [m Hm]. lia.
Qed.

(** [h (2y) = 2 h(y) + 1]. *)
Lemma h_double : forall y, 1 <= y -> h (2 * y) = 2 * h y + 1.
Proof.
  intros y Hy. unfold h. rewrite (nu_double y Hy).
  change (2 ^ (S (nu y) + 2)) with (2 * 2 ^ (nu y + 2)).
  lia.
Qed.

(** One step from a value below [2^L] stays at most [4 * 2^L]. *)
Lemma step_bound : forall L y, 1 <= y -> y < 2 ^ L -> h y <= 4 * 2 ^ L.
Proof.
  intros L y Hy HL. unfold h.
  pose proof (nu_lt L y Hy HL) as Hn.
  assert (H2 : 2 * 2 ^ nu y <= 2 ^ L).
  { change (2 * 2 ^ nu y) with (2 ^ S (nu y)). apply pow2_le_mono. lia. }
  rewrite pow2_add. change (2 ^ 2) with 4. lia.
Qed.

(** ** Orbits *)

(** [reach y z]: [z] is on the orbit of [y]. *)
Definition reach (y z : nat) : Prop := exists k, Nat.iter k h y = z.

(** [gap d y z]: no number on the orbit of [y] strictly between [y] and [z] is a
    multiple of [d]. *)
Definition gap (d y z : nat) : Prop :=
  forall w, reach y w -> y < w -> w < z -> w mod d <> 0.

Lemma iter_0 : forall y, Nat.iter 0 h y = y.
Proof. reflexivity. Qed.

Lemma iter_1 : forall y, Nat.iter 1 h y = h y.
Proof. reflexivity. Qed.

Lemma iter_S : forall k y, Nat.iter (S k) h y = h (Nat.iter k h y).
Proof. reflexivity. Qed.

Lemma iter_add : forall a b y, Nat.iter (a + b) h y = Nat.iter a h (Nat.iter b h y).
Proof. intros. apply Nat.iter_add. Qed.

Lemma iter_ge : forall k y, 1 <= y -> y + 3 * k <= Nat.iter k h y.
Proof.
  induction k as [|k IH]; intros y Hy.
  - rewrite iter_0. lia.
  - rewrite iter_S. specialize (IH y Hy).
    pose proof (h_gt (Nat.iter k h y) ltac:(lia)). lia.
Qed.

Lemma iter_le_mono : forall y a b, 1 <= y -> a <= b -> Nat.iter a h y <= Nat.iter b h y.
Proof.
  intros y a b Hy Hab.
  replace b with ((b - a) + a) by lia.
  rewrite iter_add.
  pose proof (iter_ge a y Hy).
  pose proof (iter_ge (b - a) (Nat.iter a h y) ltac:(lia)).
  lia.
Qed.

Lemma iter_lt_mono : forall y a b, 1 <= y -> a < b -> Nat.iter a h y < Nat.iter b h y.
Proof.
  intros y a b Hy Hab.
  replace b with ((b - a) + a) by lia.
  rewrite iter_add.
  pose proof (iter_ge a y Hy).
  pose proof (iter_ge (b - a) (Nat.iter a h y) ltac:(lia)).
  lia.
Qed.

Lemma reach_h : forall y, reach y (h y).
Proof. intros y. unfold reach. exists 1. reflexivity. Qed.

Lemma reach_trans : forall x y z, reach x y -> reach y z -> reach x z.
Proof.
  intros x y z [a Ha] [b Hb]. unfold reach. exists (b + a).
  rewrite iter_add, Ha. exact Hb.
Qed.

Lemma reach_ge : forall y z, 1 <= y -> reach y z -> y <= z.
Proof.
  intros y z Hy [k Hk]. rewrite <- Hk.
  pose proof (iter_ge k y Hy). lia.
Qed.

(** The orbit is totally ordered: from a later point the orbit goes on. *)
Lemma reach_cmp : forall x y z, 1 <= x -> reach x y -> reach x z -> y <= z -> reach y z.
Proof.
  intros x y z Hx [a Ha] [b Hb] Hyz.
  destruct (Nat.le_gt_cases a b) as [Hab | Hab].
  - unfold reach. exists (b - a). rewrite <- Ha, <- Hb, <- iter_add.
    replace (b - a + a) with b by lia. reflexivity.
  - exfalso. pose proof (iter_lt_mono x b a Hx Hab). lia.
Qed.

(** ** Self-similarity *)

(** From [Q * 2^m] the orbit reaches [(h Q + 2m) * 2^m], and it meets no
    multiple of [2^m] strictly in between. The induction on m uses that one
    step at level m+1 is two steps at level m, through [h_double] and [h_odd]. *)
Theorem selfsim : forall m Q, 1 <= Q ->
  reach (Q * 2 ^ m) ((h Q + 2 * m) * 2 ^ m) /\
  gap (2 ^ m) (Q * 2 ^ m) ((h Q + 2 * m) * 2 ^ m).
Proof.
  induction m as [|m IH]; intros Q HQ.
  - rewrite !Nat.pow_0_r, !Nat.mul_1_r, Nat.mul_0_r, Nat.add_0_r.
    split.
    + apply reach_h.
    + intros w [k Hk] Hlo Hhi _.
      destruct k as [|k].
      * rewrite iter_0 in Hk. lia.
      * pose proof (iter_le_mono Q 1 (S k) HQ ltac:(lia)) as Hle.
        rewrite Hk, iter_1 in Hle. lia.
  - change (2 ^ S m) with (2 * 2 ^ m).
    pose proof (pow2_pos m) as HP.
    destruct (IH (2 * Q) ltac:(lia)) as [R1 G1].
    rewrite (h_double Q HQ) in R1, G1.
    assert (HQ1 : Nat.Odd (2 * h Q + 1 + 2 * m)) by (exists (h Q + m); lia).
    destruct (IH (2 * h Q + 1 + 2 * m) ltac:(lia)) as [R2 G2].
    rewrite (h_odd _ HQ1) in R2, G2.
    replace (Q * (2 * 2 ^ m)) with (2 * Q * 2 ^ m) by nia.
    replace ((h Q + 2 * S m) * (2 * 2 ^ m))
      with ((2 * h Q + 1 + 2 * m + 3 + 2 * m) * 2 ^ m) by nia.
    split.
    + exact (reach_trans _ _ _ R1 R2).
    + intros w Hw Hlo Hhi Hmod.
      pose proof (mod_halve w (2 ^ m) HP Hmod) as Hmod'.
      destruct (Nat.lt_trichotomy w ((2 * h Q + 1 + 2 * m) * 2 ^ m)) as [Hlt | [Heq | Hgt]].
      * exact (G1 w Hw Hlo Hlt Hmod').
      * rewrite Heq in Hmod.
        replace (2 * h Q + 1 + 2 * m) with (2 * (h Q + m) + 1) in Hmod by lia.
        rewrite odd_mul_mod in Hmod by lia. lia.
      * assert (Hpos : 1 <= 2 * Q * 2 ^ m).
        { pose proof (mul_ge_r (2 * Q) (2 ^ m) ltac:(lia)). lia. }
        assert (Hle : (2 * h Q + 1 + 2 * m) * 2 ^ m <= w) by lia.
        pose proof (reach_cmp (2 * Q * 2 ^ m) ((2 * h Q + 1 + 2 * m) * 2 ^ m) w
                      Hpos R1 Hw Hle) as Hw1.
        exact (G2 w Hw1 Hgt Hhi Hmod').
Qed.

(** ** The ladder *)

(** The rungs [(2m - 1) * 2^m]: 12, 40, 112, 288, ... *)
Definition rung (m : nat) : nat := (2 * m - 1) * 2 ^ m.

(** Self-similarity with the odd number [Q = 2m - 1]: the next multiple of [2^m]
    after the rung for m is the rung for m+1. *)
Lemma rung_step : forall m, 2 <= m ->
  reach (rung m) (rung (S m)) /\ gap (2 ^ m) (rung m) (rung (S m)).
Proof.
  intros m Hm.
  assert (HQ : Nat.Odd (2 * m - 1)) by (exists (m - 1); lia).
  destruct (selfsim m (2 * m - 1) ltac:(lia)) as [R G].
  rewrite (h_odd _ HQ) in R, G.
  replace ((2 * m - 1 + 3 + 2 * m) * 2 ^ m) with (rung (S m)) in R, G.
  - split; [exact R | exact G].
  - unfold rung. change (2 ^ S m) with (2 * 2 ^ m).
    replace (2 * S m - 1) with (2 * m + 1) by lia.
    replace (2 * m - 1 + 3 + 2 * m) with (2 * (2 * m + 1)) by lia.
    ring.
Qed.

(** The orbit of 2 contains every rung. It begins 2, 9, 12. *)
Theorem ladder : forall m, 2 <= m -> reach 2 (rung m).
Proof.
  induction m as [|m IH]; intros Hm.
  - lia.
  - destruct (Nat.eq_dec m 1) as [->|Hm1].
    + unfold reach. exists 2. reflexivity.
    + exact (reach_trans _ _ _ (IH ltac:(lia)) (proj1 (rung_step m ltac:(lia)))).
Qed.

(** ** Slow zeros *)

Lemma slow_zeros_rung : forall m, 2 <= m ->
  forall z, reach 2 z -> z mod 2 ^ m = 0 -> rung m <= z.
Proof.
  induction m as [|m IH]; intros Hm z Hz Hmod.
  - lia.
  - destruct (Nat.eq_dec m 1) as [->|Hm1].
    + (* m + 1 = 2: below 12 the orbit of 2 is 2 and 9, and neither is a multiple of 4 *)
      assert (B : rung 2 = 12) by reflexivity. rewrite B.
      destruct Hz as [i Hi].
      destruct i as [|[|i]].
      * rewrite iter_0 in Hi. subst z.
        assert (A : 2 mod 2 ^ 2 = 2) by reflexivity. lia.
      * rewrite iter_1 in Hi.
        assert (A9 : h 2 = 9) by reflexivity.
        rewrite A9 in Hi. subst z.
        assert (A : 9 mod 2 ^ 2 = 1) by reflexivity. lia.
      * pose proof (iter_le_mono 2 2 (S (S i)) ltac:(lia) ltac:(lia)) as Hle.
        rewrite Hi in Hle.
        assert (A : Nat.iter 2 h 2 = 12) by reflexivity. lia.
    + (* m + 1 >= 3: a multiple of 2^(m+1) is a multiple of 2^m, so it is at least
         the rung for m. It is not that rung, whose odd part is 2m - 1, and by
         self-similarity no multiple of 2^m lies between the two rungs. *)
      assert (Hm2 : 2 <= m) by lia.
      pose proof (pow2_pos m) as HP.
      change (2 ^ S m) with (2 * 2 ^ m) in Hmod.
      pose proof (mod_halve z (2 ^ m) HP Hmod) as Hmod'.
      pose proof (IH Hm2 z Hz Hmod') as Hge.
      destruct (Nat.lt_trichotomy z (rung (S m))) as [Hlt | [Heq | Hgt]]; [| lia | lia].
      exfalso.
      destruct (Nat.eq_dec z (rung m)) as [Heq | Hne].
      * rewrite Heq in Hmod. unfold rung in Hmod.
        replace (2 * m - 1) with (2 * (m - 1) + 1) in Hmod by lia.
        rewrite odd_mul_mod in Hmod by exact HP. lia.
      * destruct (rung_step m Hm2) as [_ G].
        assert (Hlt' : rung m < z) by lia.
        assert (Hle : rung m <= z) by lia.
        assert (H2 : 1 <= 2) by lia.
        pose proof (reach_cmp 2 (rung m) z H2 (ladder m Hm2) Hz Hle) as Rz.
        exact (G z Rz Hlt' Hlt Hmod').
Qed.

(** Every number on the orbit of 2 that is a multiple of [2^m] ([m >= 2]) is at
    least [(2m - 1) * 2^m]. *)
Theorem slow_zeros : forall z m, reach 2 z -> 2 <= m -> z mod 2 ^ m = 0 ->
  (2 * m - 1) * 2 ^ m <= z.
Proof. intros z m Hz Hm Hmod. exact (slow_zeros_rung m Hm z Hz Hmod). Qed.

(** The orbit of 2 contains no power of 2 from 4 up. *)
Theorem no_pow2 : forall z k, reach 2 z -> 2 <= k -> z <> 2 ^ k.
Proof.
  intros z k Hz Hk E.
  assert (Hmod : z mod 2 ^ k = 0) by (rewrite E; exact (pow2_mod k k (le_n k))).
  pose proof (slow_zeros z k Hz Hk Hmod) as H.
  rewrite E in H.
  pose proof (mul_le_r 3 (2 * k - 1) (2 ^ k) ltac:(lia)) as H3.
  pose proof (pow2_pos k). lia.
Qed.

(** The orbit of 2 contains no power of 4. *)
Theorem no_pow4 : forall z k, reach 2 z -> z <> 4 ^ k.
Proof.
  intros z [|k] Hz E.
  - pose proof (reach_ge 2 z ltac:(lia) Hz). simpl in E. lia.
  - rewrite pow4 in E. exact (no_pow2 z (2 * S k) Hz ltac:(lia) E).
Qed.

(** ** The invariant of the bounce configurations *)

(** [Inv L V]: the word has length [L >= 2], its value [V] fits, and [V + 1] is
    on the orbit of 2. *)
Definition Inv (L V : nat) : Prop :=
  2 <= L /\ V < 2 ^ L /\ reach 2 (V + 1).

Lemma Inv_start : Inv 2 1.
Proof.
  unfold Inv. split; [| split].
  - lia.
  - simpl. lia.
  - unfold reach. exists 0. reflexivity.
Qed.

(** The word is never all ones, so the machine never meets its halting case. *)
Lemma Inv_not_full : forall L V, Inv L V -> V + 1 < 2 ^ L.
Proof.
  intros L V (HL & HV & HR).
  destruct (Nat.eq_dec (V + 1) (2 ^ L)) as [E|E]; [|lia].
  exfalso. exact (no_pow2 (V + 1) L HR HL E).
Qed.

Lemma Inv_next : forall L V, Inv L V ->
  Inv (if h (V + 1) <=? 2 ^ L then L else L + 2) (h (V + 1) - 1).
Proof.
  intros L V I.
  pose proof (Inv_not_full L V I) as HF.
  destruct I as (HL & HV & HR).
  pose proof (h_gt (V + 1) ltac:(lia)) as Hh.
  assert (HR' : reach 2 (h (V + 1) - 1 + 1)).
  { replace (h (V + 1) - 1 + 1) with (h (V + 1)) by lia.
    exact (reach_trans _ _ _ HR (reach_h (V + 1))). }
  destruct (h (V + 1) <=? 2 ^ L) eqn:Hc.
  - apply Nat.leb_le in Hc.
    change (Inv L (h (V + 1) - 1)). unfold Inv.
    split; [exact HL | split; [lia | exact HR']].
  - assert (Hc' : 2 ^ L < h (V + 1)).
    { destruct (Nat.le_gt_cases (h (V + 1)) (2 ^ L)) as [H|H]; [|exact H].
      assert (H' : (h (V + 1) <=? 2 ^ L) = true) by (apply Nat.leb_le; exact H).
      congruence. }
    pose proof (step_bound L (V + 1) ltac:(lia) HF) as Hb.
    change (Inv (L + 2) (h (V + 1) - 1)). unfold Inv.
    split; [lia | split; [| exact HR']].
    rewrite pow2_add. change (2 ^ 2) with 4. lia.
Qed.
