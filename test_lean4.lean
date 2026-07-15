import Mathlib

-- Test 1: basic arithmetic
example : 2 + 2 = 4 := by
  norm_num

-- Test 2: quantifier with simp
example : ∀ n : ℕ, n + 0 = n := by
  intro n
  simp

-- Test 3: simple inequality
example : 3 ≤ 5 := by
  omega

-- Test 4: logical connective
example (P Q : Prop) (hP : P) (hQ : Q) : P ∧ Q := by
  constructor
  · exact hP
  · exact hQ
