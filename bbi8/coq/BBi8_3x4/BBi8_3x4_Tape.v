(** * BBi(8) holdouts #7 and #8: from the tape to the map h *)
(** Credit and how this was made: see README.md in the bbi8 folder. *)

(** The bounce. Both machines keep a binary word on the tape and bounce off its
    right end. Read the word as a number V (bit 0 next to the blank cell on the
    right) and put y = V + 1. Each bounce replaces y by h(y), and the word grows
    by two cells when h(y) no longer fits ([bounce]). The machine could only halt
    when the word is all ones, that is when y is a power of 2, and the invariant
    [Inv] of BBi8_3x4_Arith.v rules that out ([counter_nonhalt]).

    A word of length L with value V is the list of its L binary digits, bit 0
    first, written with the symbol [d1] for the digit 1 and [d0] for the digit 0.
    For #7, [d1] is 2 and [d0] is 1. For #8, [d1] is 3 and [d0] is 2. In
    [l <* xs] the first element of [xs] is the cell next to the head.

    The machine-independent part comes first: binary words as lists of
    booleans, increment ([incw]), and adding [2^(j+1) - 1] from bit j down
    ([addlow]). Then [Section Bounce] proves the bounce for any machine with the
    three local tape lemmas [carry], [overflow] and [sweepA]. *)

From Coq Require Import Lists.List. Import ListNotations.
From Coq Require Import Arith Lia.
From BusyCoq Require Import Individual34.
Require Import BusyCoq.BBi8_3x4.BBi8_3x4_Arith.
Set Default Goal Selector "!".

Local Open Scope nat_scope.

(** ** Bits of a number *)

Definition bit (V : nat) : bool := V mod 2 =? 1.

(** The [L] lowest binary digits of [V], bit 0 first. *)
Fixpoint tobits (L V : nat) : list bool :=
  match L with
  | O => []
  | S L' => bit V :: tobits L' (V / 2)
  end.

Definition b2n (b : bool) : nat := if b then 1 else 0.

Lemma divmod2 : forall a q r, r < 2 -> a = 2 * q + r -> a / 2 = q /\ a mod 2 = r.
Proof.
  intros a q r Hr E.
  pose proof (Nat.div_mod_eq a 2) as D.
  pose proof (Nat.mod_upper_bound a 2 ltac:(lia)) as B.
  split; lia.
Qed.

Lemma tobits_cons : forall b M W, b :: tobits M W = tobits (S M) (2 * W + b2n b).
Proof.
  intros b M W. cbn [tobits].
  assert (Hb : b2n b < 2) by (destruct b; simpl; lia).
  destruct (divmod2 (2 * W + b2n b) W (b2n b) Hb eq_refl) as [E1 E2].
  unfold bit. rewrite E1, E2.
  destruct b; reflexivity.
Qed.

(** ** Adding one at the low end of a word *)

(** Binary increment, bit 0 first. A word of ones grows by two cells, a one
    and a zero, as the machine's word does when a carry runs off its top. *)
Fixpoint incw (bs : list bool) : list bool :=
  match bs with
  | [] => [true; false]
  | false :: bs' => true :: bs'
  | true :: bs' => false :: incw bs'
  end.

Lemma inc_fit : forall M W, W + 1 < 2 ^ M -> incw (tobits M W) = tobits M (W + 1).
Proof.
  induction M as [|M IH]; intros W H.
  - simpl in H. lia.
  - change (2 ^ S M) with (2 * 2 ^ M) in H.
    cbn [tobits]. unfold bit.
    pose proof (Nat.div_mod_eq W 2) as D.
    pose proof (Nat.mod_upper_bound W 2 ltac:(lia)) as B.
    destruct (Nat.eq_dec (W mod 2) 0) as [E|E].
    + destruct (divmod2 (W + 1) (W / 2) 1 ltac:(lia) ltac:(lia)) as [E1 E2].
      rewrite E, E1, E2. reflexivity.
    + assert (E' : W mod 2 = 1) by lia.
      destruct (divmod2 (W + 1) (W / 2 + 1) 0 ltac:(lia) ltac:(lia)) as [E1 E2].
      rewrite E', E1, E2.
      change (1 =? 1) with true. change (0 =? 1) with false.
      cbn [incw]. f_equal. apply IH. lia.
Qed.

Lemma inc_full : forall M W, W + 1 = 2 ^ M -> incw (tobits M W) = tobits (M + 2) (W + 1).
Proof.
  induction M as [|M IH]; intros W H.
  - simpl in H. assert (W = 0) as -> by lia. reflexivity.
  - change (2 ^ S M) with (2 * 2 ^ M) in H.
    change (S M + 2) with (S (M + 2)).
    cbn [tobits]. unfold bit.
    pose proof (Nat.div_mod_eq W 2) as D.
    pose proof (Nat.mod_upper_bound W 2 ltac:(lia)) as B.
    assert (E : W mod 2 = 1) by lia.
    destruct (divmod2 (W + 1) (W / 2 + 1) 0 ltac:(lia) ltac:(lia)) as [E1 E2].
    rewrite E, E1, E2.
    change (1 =? 1) with true. change (0 =? 1) with false.
    cbn [incw]. f_equal. apply IH. lia.
Qed.

(** ** Adding [2^(j+1) - 1] from bit j down, on lists *)

(** The head is on the lowest cell of [hi], and [lo] lists the cells to its
    right, nearest first. Add one at the head, step right, repeat. *)
Fixpoint addlow (lo hi : list bool) : list bool :=
  match lo with
  | [] => incw hi
  | b :: lo' => addlow lo' (b :: incw hi)
  end.

(** The value of [lo], read with its first element as the highest digit. *)
Fixpoint valr (lo : list bool) : nat :=
  match lo with
  | [] => 0
  | b :: lo' => b2n b * 2 ^ length lo' + valr lo'
  end.

Lemma valr_lt : forall lo, valr lo < 2 ^ length lo.
Proof.
  induction lo as [|b lo IH].
  - simpl. lia.
  - cbn [valr length]. change (2 ^ S (length lo)) with (2 * 2 ^ length lo).
    destruct b; cbn [b2n]; lia.
Qed.

(** The word length after a value [v] is written over a word of length [N]. *)
Definition grow (N v : nat) : nat := if v <? 2 ^ N then N else N + 2.

Lemma grow_lo : forall N v, v < 2 ^ N -> grow N v = N.
Proof.
  intros N v H. unfold grow.
  assert (E : (v <? 2 ^ N) = true) by (apply Nat.ltb_lt; exact H).
  rewrite E. reflexivity.
Qed.

Lemma grow_hi : forall N v, 2 ^ N <= v -> grow N v = N + 2.
Proof.
  intros N v H. unfold grow.
  destruct (v <? 2 ^ N) eqn:E; [|reflexivity].
  apply Nat.ltb_lt in E. lia.
Qed.

Lemma grow_if : forall L y, 1 <= y -> grow L (y - 1) = if y <=? 2 ^ L then L else L + 2.
Proof.
  intros L y Hy. unfold grow.
  destruct (y - 1 <? 2 ^ L) eqn:E1; destruct (y <=? 2 ^ L) eqn:E2; try reflexivity.
  - apply Nat.ltb_lt in E1.
    assert (H : (y <=? 2 ^ L) = true) by (apply Nat.leb_le; lia).
    congruence.
  - apply Nat.leb_le in E2.
    assert (H : (y - 1 <? 2 ^ L) = true) by (apply Nat.ltb_lt; lia).
    congruence.
Qed.

(** The head on bit j adds [2^(j+1) - 1] to the word, and the word grows by two
    cells if the sum does not fit. *)
Lemma addlow_spec : forall lo M W, W < 2 ^ M ->
  addlow lo (tobits M W) =
  tobits (grow (M + length lo) (W * 2 ^ length lo + valr lo + 2 ^ (length lo + 1) - 1))
         (W * 2 ^ length lo + valr lo + 2 ^ (length lo + 1) - 1).
Proof.
  induction lo as [|b lo IH]; intros M W HW.
  - cbn [addlow length valr].
    replace (W * 2 ^ 0 + 0 + 2 ^ (0 + 1) - 1) with (W + 1) by (simpl; lia).
    replace (M + 0) with M by lia.
    destruct (Nat.lt_ge_cases (W + 1) (2 ^ M)) as [H|H].
    + rewrite (inc_fit M W H), (grow_lo M (W + 1) H). reflexivity.
    + assert (E : W + 1 = 2 ^ M) by lia.
      rewrite (inc_full M W E), (grow_hi M (W + 1) H). reflexivity.
  - cbn [addlow length valr].
    pose proof (valr_lt lo) as Hv.
    pose proof (pow2_pos (length lo)) as HP.
    assert (Hb : b2n b <= 1) by (destruct b; simpl; lia).
    set (j := length lo) in *.
    set (vr := valr lo) in *.
    assert (EV : forall W', W' = 2 * (W + 1) + b2n b ->
      W' * 2 ^ j + vr + 2 ^ (j + 1) - 1 =
      W * 2 ^ S j + (b2n b * 2 ^ j + vr) + 2 ^ (S j + 1) - 1).
    { intros W' ->. change (2 ^ S j) with (2 * 2 ^ j).
      change (2 ^ (S j + 1)) with (2 * 2 ^ (j + 1)).
      rewrite (pow2_add j 1). change (2 ^ 1) with 2.
      nia. }
    destruct (Nat.lt_ge_cases (W + 1) (2 ^ M)) as [H|H].
    + rewrite (inc_fit M W H), (tobits_cons b M (W + 1)).
      assert (HW' : 2 * (W + 1) + b2n b < 2 ^ S M).
      { change (2 ^ S M) with (2 * 2 ^ M). lia. }
      rewrite (IH (S M) _ HW').
      rewrite (EV _ eq_refl).
      replace (S M + j) with (M + S j) by lia.
      reflexivity.
    + assert (E : W + 1 = 2 ^ M) by lia.
      rewrite (inc_full M W E), (tobits_cons b (M + 2) (W + 1)).
      pose proof (pow2_pos M) as HQ.
      assert (HW' : 2 * (W + 1) + b2n b < 2 ^ S (M + 2)).
      { change (2 ^ S (M + 2)) with (2 * 2 ^ (M + 2)).
        rewrite (pow2_add M 2). change (2 ^ 2) with 4. lia. }
      rewrite (IH (S (M + 2)) _ HW').
      rewrite (EV _ eq_refl).
      set (X := W * 2 ^ S j + (b2n b * 2 ^ j + vr) + 2 ^ (S j + 1) - 1).
      assert (Hlo : 2 ^ (M + S j) <= X).
      { unfold X. rewrite (pow2_add M (S j)).
        change (2 ^ S j) with (2 * 2 ^ j).
        change (2 ^ (S j + 1)) with (2 * 2 ^ (j + 1)).
        rewrite (pow2_add j 1). change (2 ^ 1) with 2.
        rewrite <- E. nia. }
      assert (Hhi : X < 2 ^ (S (M + 2) + j)).
      { unfold X. rewrite (pow2_add (S (M + 2)) j).
        change (2 ^ S (M + 2)) with (2 * 2 ^ (M + 2)).
        rewrite (pow2_add M 2). change (2 ^ 2) with 4.
        change (2 ^ S j) with (2 * 2 ^ j).
        change (2 ^ (S j + 1)) with (2 * 2 ^ (j + 1)).
        rewrite (pow2_add j 1). change (2 ^ 1) with 2.
        rewrite <- E. nia. }
      rewrite (grow_lo _ _ Hhi), (grow_hi _ _ Hlo).
      replace (S (M + 2) + j) with (M + S j + 2) by lia.
      reflexivity.
Qed.

(** ** The words of the bounce *)

(** If [V + 1 = 2^n * (2o + 1)] then digits 0 to n-1 of [V] are 1, digit n is
    0, and the digits above are those of [o]. *)
Lemma tobits_low_ones : forall n M o,
  tobits (n + S M) (2 ^ n - 1 + 2 ^ (n + 1) * o) = List.repeat true n ++ false :: tobits M o.
Proof.
  induction n as [|n IH]; intros M o.
  - change (0 + S M) with (S M). cbn [tobits List.repeat app].
    replace (2 ^ 0 - 1 + 2 ^ (0 + 1) * o) with (2 * o + 0) by (simpl; lia).
    destruct (divmod2 (2 * o + 0) o 0 ltac:(lia) eq_refl) as [E1 E2].
    unfold bit. rewrite E1, E2. reflexivity.
  - change (S n + S M) with (S (n + S M)). cbn [tobits List.repeat app].
    assert (Hv : 2 ^ S n - 1 + 2 ^ (S n + 1) * o = 2 * (2 ^ n - 1 + 2 ^ (n + 1) * o) + 1).
    { change (2 ^ S n) with (2 * 2 ^ n).
      change (2 ^ (S n + 1)) with (2 * 2 ^ (n + 1)).
      pose proof (pow2_pos n). nia. }
    rewrite Hv.
    destruct (divmod2 (2 * (2 ^ n - 1 + 2 ^ (n + 1) * o) + 1)
                (2 ^ n - 1 + 2 ^ (n + 1) * o) 1 ltac:(lia) eq_refl) as [E1 E2].
    unfold bit. rewrite E1, E2. change (1 =? 1) with true.
    f_equal. apply IH.
Qed.

Lemma valr_ones : forall n, valr (List.repeat true n) = 2 ^ n - 1.
Proof.
  induction n as [|n IH]; [reflexivity|].
  cbn [List.repeat valr]. rewrite IH, List.repeat_length. cbn [b2n].
  change (2 ^ S n) with (2 * 2 ^ n). pose proof (pow2_pos n). lia.
Qed.

Lemma len_lo : forall n, length (false :: List.repeat true n) = S n.
Proof. intros n. cbn [length]. rewrite List.repeat_length. reflexivity. Qed.

Lemma valr_lo : forall n, valr (false :: List.repeat true n) = 2 ^ n - 1.
Proof. intros n. cbn [valr b2n]. rewrite valr_ones. lia. Qed.

(** ** Words as symbols *)

Definition sb (d1 d0 : Sym) (b : bool) : Sym := if b then d1 else d0.

(** The word of length L and value V. *)
Definition word (d1 d0 : Sym) (L V : nat) : list Sym := List.map (sb d1 d0) (tobits L V).

(** The bounce configuration K(L, V): state C on the blank cell just right of
    the word, blank everywhere else. *)
Definition Kw (d1 d0 : Sym) (L V : nat) : Q * tape :=
  const S0 <* word d1 d0 L V {{C}}> const S0.

Lemma map_repeat_sb : forall (d1 d0 : Sym) b k,
  List.map (sb d1 d0) (List.repeat b k) = [sb d1 d0 b]^^k.
Proof.
  intros d1 d0 b k. induction k as [|k IH]; [reflexivity|].
  cbn [List.repeat List.map lpow app]. rewrite IH. reflexivity.
Qed.

Lemma map_ones : forall (d1 d0 : Sym) k, List.map (sb d1 d0) (List.repeat true k) = [d1]^^k.
Proof. intros. exact (map_repeat_sb d1 d0 true k). Qed.

Lemma map_zeros : forall (d1 d0 : Sym) k, List.map (sb d1 d0) (List.repeat false k) = [d0]^^k.
Proof. intros. exact (map_repeat_sb d1 d0 false k). Qed.

Lemma split_ones : forall hi : list bool, exists k rest,
  hi = List.repeat true k ++ rest /\ (rest = [] \/ exists rest', rest = false :: rest').
Proof.
  induction hi as [|b hi IH].
  - exists 0, (@nil bool). split; [reflexivity | left; reflexivity].
  - destruct b.
    + destruct IH as (k & rest & E & H). exists (S k), rest. split; [| exact H].
      rewrite E. reflexivity.
    + exists 0, (false :: hi). split; [reflexivity | right; exists hi; reflexivity].
Qed.

Lemma incw_ones : forall k rest,
  incw (List.repeat true k ++ rest) = List.repeat false k ++ incw rest.
Proof.
  induction k as [|k IH]; intros rest; [reflexivity|].
  cbn [List.repeat app incw]. rewrite IH. reflexivity.
Qed.

(** ** The bounce, for any machine with the three local tape lemmas *)

Section Bounce.

Variable tm : TM.
Variables d1 d0 : Sym.

(** Carry. The head is on bit j in state C, bits j to q-1 hold [d1] and bit q
    holds [d0]. They become [d0] and [d1], and the head ends on bit j-1. As
    numbers, the word grows by 2^j. *)
Hypothesis carry : forall k l r,
  l <* [d0] <* [d1]^^k <{{C}} r -[ tm ]->+ l <* [d1] <* [d0]^^k {{C}}> r.

(** Overflow. Bits j to L-1 hold [d1] and everything above is blank. They
    become [d0], bit L becomes [d1] and bit L+1 becomes [d0]. The word grows
    by 2^j and gains two cells. *)
Hypothesis overflow : forall k r,
  const S0 <* [d1]^^k <{{C}} r -[ tm ]->+ const S0 <* [d1; d0] <* [d0]^^k {{C}}> r.

(** The first n+2 steps of a bounce: C0, the A-sweep over the n low cells
    holding [d1], and A reading [d0] at bit n. The head ends on bit n+1 in
    state C. *)
Hypothesis sweepA : forall n l,
  l <* [d0] <* [d1]^^n {{C}}> const S0 -[ tm ]->+ l <{{C}} [d0] *> [d1]^^n *> const S0.

(** Carry or overflow, on lists: the head on the lowest cell of [hi] adds one
    there and steps right. *)
Lemma add_one : forall hi r,
  const S0 <* List.map (sb d1 d0) hi <{{C}} r -[ tm ]->+
  const S0 <* List.map (sb d1 d0) (incw hi) {{C}}> r.
Proof.
  intros hi r.
  destruct (split_ones hi) as (k & rest & -> & [-> | (rest' & ->)]).
  - rewrite incw_ones, List.app_nil_r, List.map_app, map_ones, map_zeros, Str_app_assoc.
    change (List.map (sb d1 d0) (incw [])) with [d1; d0].
    apply overflow.
  - rewrite incw_ones, !List.map_app, map_ones, map_zeros, !Str_app_assoc.
    change (List.map (sb d1 d0) (false :: rest')) with ([d0] ++ List.map (sb d1 d0) rest').
    change (List.map (sb d1 d0) (incw (false :: rest')))
      with ([d1] ++ List.map (sb d1 d0) rest').
    rewrite !Str_app_assoc.
    apply carry.
Qed.

(** Repeated carries from bit j down to bit 0 add [2^(j+1) - 1]. *)
Lemma add_down : forall lo hi,
  const S0 <* List.map (sb d1 d0) hi <{{C}} List.map (sb d1 d0) lo *> const S0 -[ tm ]->+
  const S0 <* List.map (sb d1 d0) (addlow lo hi) {{C}}> const S0.
Proof.
  induction lo as [|b lo IH]; intros hi.
  - exact (add_one hi (const S0)).
  - eapply progress_trans.
    + exact (add_one hi (List.map (sb d1 d0) (b :: lo) *> const S0)).
    + exact (IH (b :: incw hi)).
Qed.

(** The bounce. If the word of length L and value V is not all ones, the
    machine goes on to the word of value [h (V + 1) - 1], two cells longer when
    that value does not fit. *)
Lemma bounce : forall L V, V + 1 < 2 ^ L ->
  Kw d1 d0 L V -[ tm ]->+
  Kw d1 d0 (if h (V + 1) <=? 2 ^ L then L else L + 2) (h (V + 1) - 1).
Proof.
  intros L V HV.
  pose proof (nu_lt L (V + 1) ltac:(lia) HV) as Hn.
  destruct (nu_spec (V + 1) ltac:(lia)) as [o Ho].
  set (n := nu (V + 1)) in *.
  set (M := L - n - 1).
  assert (HL : L = n + S M) by (unfold M; lia).
  assert (HVo : V = 2 ^ n - 1 + 2 ^ (n + 1) * o).
  { rewrite (pow2_add n 1). change (2 ^ 1) with 2. pose proof (pow2_pos n). nia. }
  assert (Ho2 : o < 2 ^ M).
  { rewrite HL in HV. rewrite (pow2_add n (S M)) in HV.
    change (2 ^ S M) with (2 * 2 ^ M) in HV.
    rewrite Ho in HV. pose proof (pow2_pos n). nia. }
  assert (EK : Kw d1 d0 L V =
    (const S0 <* List.map (sb d1 d0) (tobits M o)) <* [d0] <* [d1]^^n {{C}}> const S0).
  { unfold Kw, word. rewrite HL, HVo, tobits_low_ones, List.map_app, map_ones.
    change (List.map (sb d1 d0) (false :: tobits M o))
      with ([d0] ++ List.map (sb d1 d0) (tobits M o)).
    rewrite !Str_app_assoc. reflexivity. }
  assert (EA :
    (const S0 <* List.map (sb d1 d0) (tobits M o)) <{{C}} [d0] *> [d1]^^n *> const S0 =
    const S0 <* List.map (sb d1 d0) (tobits M o) <{{C}}
      List.map (sb d1 d0) (false :: List.repeat true n) *> const S0).
  { change (List.map (sb d1 d0) (false :: List.repeat true n))
      with ([d0] ++ List.map (sb d1 d0) (List.repeat true n)).
    rewrite map_ones, Str_app_assoc. reflexivity. }
  assert (EF : addlow (false :: List.repeat true n) (tobits M o) =
               tobits (if h (V + 1) <=? 2 ^ L then L else L + 2) (h (V + 1) - 1)).
  { rewrite (addlow_spec _ M o Ho2), len_lo, valr_lo.
    assert (EX : o * 2 ^ S n + (2 ^ n - 1) + 2 ^ (S n + 1) - 1 = h (V + 1) - 1).
    { unfold h. change (nu (V + 1)) with n. rewrite HVo.
      change (2 ^ S n) with (2 * 2 ^ n).
      change (2 ^ (S n + 1)) with (2 * 2 ^ (n + 1)).
      rewrite (pow2_add n 1), (pow2_add n 2).
      change (2 ^ 1) with 2. change (2 ^ 2) with 4.
      pose proof (pow2_pos n). nia. }
    rewrite EX.
    replace (M + S n) with L by lia.
    assert (Hh : 1 <= h (V + 1)) by (pose proof (h_gt (V + 1) ltac:(lia)); lia).
    rewrite (grow_if L (h (V + 1)) Hh).
    reflexivity. }
  rewrite EK.
  eapply progress_trans.
  - apply sweepA.
  - rewrite EA. unfold Kw, word. rewrite <- EF. apply add_down.
Qed.

(** A machine with the three local lemmas that reaches the word of length 2
    and value 1 from the blank tape never halts: its bounces follow the orbit
    of 2 under h, and [Inv] keeps the word from filling up. *)
Theorem counter_nonhalt : c0 -[ tm ]->* Kw d1 d0 2 1 -> ~ halts tm c0.
Proof.
  intros Hstart.
  apply multistep_nonhalt with (c' := Kw d1 d0 2 1); [exact Hstart|].
  apply (progress_nonhalt_cond tm (nat * nat) (2, 1)
           (fun p => Kw d1 d0 (fst p) (snd p)) (fun p => Inv (fst p) (snd p))).
  - intros [len V] I.
    exists ((if h (V + 1) <=? 2 ^ len then len else len + 2), h (V + 1) - 1).
    split.
    + exact (bounce len V (Inv_not_full len V I)).
    + exact (Inv_next len V I).
  - exact Inv_start.
Qed.

End Bounce.
