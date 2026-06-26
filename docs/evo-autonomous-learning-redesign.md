# EVO Autonomous Learning: Architectural Redesign

*Date: June 26, 2026*
*Author: EVO (Explicit-assumption Verification Orchestrator)*

## Executive Summary

EVO is an autonomous reasoning agent organized around six tiers (LITE, COMPUTE, MATHS, CODE, REASON, PROVE) with Prolog-first derivation, explicit assumption tracking, proof traces, and consistency verification. Currently, EVO operates **session-isolated**: every interaction starts with a blank KB and zero cumulative knowledge. This document proposes a redesign that transforms EVO into a **self-improving system** that learns from its interactions while preserving its four inviolable design principles.

---

## Part I: The Four Inviolable Principles

Any redesign must preserve these non-negotiable architectural commitments:

| Principle | Rationale |
|-----------|-----------|
| **1. Evidence-Before-Conclusion** | Every conclusion must be grounded in tier-appropriate evidence (Prolog derivation, computation, code inspection, Lean verification). |
| **2. Explicit Assumption Tracking** | Every inference bridge not strictly entailed by facts must be represented as an assumption. Hidden inference bridges are forbidden. |
| **3. Consistency Verification** | Every KB must be checked for contradictions (`inconsistent/0`). Paradoxes are assumption-dependent tensions, not inconsistencies. |
| **4. Tier-Appropriate Evidence** | The tier determines the mandatory evidence mechanism. LITE cannot substitute for PROVE; REASON cannot substitute for COMPUTE. |

---

## Part II: What EVO Currently Does Not Do (The Learning Gap)

1. **No session-to-session knowledge carryover.** Facts, lemmas, and verified conclusions vanish after `:- main.`
2. **No pattern extraction from successful proofs.** If EVO solves 20 `ring`-based polynomial identities in PROVE, it never learns the meta-pattern.
3. **No failure analysis across sessions.** Repeated failures on `Nat` subtraction are never aggregated into a "known fragility" heuristic.
4. **No assumption-effectiveness tracking.** Assumptions that repeatedly led to contradictions are never deprecated.
5. **No tool-choice improvement.** The decision to route to `lean4_exec` vs `maths_problem` vs `python_exec` is per-session and never refined.

---

## Part III: Architectural Components for the Redesign

### 3.1 The Cumulative Knowledge Store (CKS)

Replace scratch pads (`reason_scratch_pad`, `code_scratch_pad`, `prove_scratch_pad`) with a **unified, versioned Cumulative Knowledge Store** organized by domain, not by tier.

```
CKS/
  domains/
    algebra/
      ring_identities.pl      # Learned Prolog rules for ring problems
      poly_factorization.pl
    number_theory/
      modulo_arithmetic.pl
      prime_properties.pl
    code_patterns/
      lean_import_errors.pl
      python_anti_patterns.pl
    proof_tactics/
      induction_patterns.pl
      ring_vs_nlinarith_heuristic.pl
  meta/
    assumption_effectiveness.csv   # Track: assumption -> success/fail count
    tool_choice_history.json       # Track: problem features -> tool chosen -> outcome
    failure_clusters/              # Grouped failure modes (e.g., "Nat subtraction", "omega timeout")
  verified_lemmas/                  # Lean-verified lemmas proven across sessions
    lemma_0001.lean
    lemma_0002.lean
```

**Key design choice:** The CKS is **append-only with versioning**. Facts can be deprecated but never deleted. This prevents catastrophic forgetting.

### 3.2 The Reflection Pipeline

After every interaction, EVO runs a **post-hoc reflection** composed of four stages:

```
[SESSION END] 
    |
    v
[STAGE 1: Harvest] — Extract facts, assumptions, conclusions, proof traces, errors
    |
    v
[STAGE 2: Generalize] — Abstract session-specific details into general patterns
    |
    v
[STAGE 3: Archive] — Write patterns to CKS with provenance metadata
    |
    v
[STAGE 4: Heuristic Update] — Update meta-rules: tool choice, assumption priors, fragility warnings
```

**Stage 1 — Harvest:** A Prolog program `harvest_session/2` extracts from the session KB:

```prolog
harvest_session(SessionId, Harvest) :-
    findall(Fact-Context, observation(Fact), Observations),
    findall(Assumption-Justification, assumption(Assumption, Justification), Assumptions),
    findall(Conclusion-Proof, prove(conclusion(Conclusion), Proof), Conclusions),
    findall(Error-Goal, failed_proof(Error, Goal), FailedGoals),
    Harvest = harvest(Observations, Assumptions, Conclusions, FailedGoals).
```

**Stage 2 — Generalize:** A dedicated `generalize/2` module strips session-specific constants and renames variables to produce **parameterized patterns**:

```prolog
%% Before generalization:
conclusion(fibonacci(10, 55)) :-
    computed_value(10, 55),
    active_assumption(fibonacci_formula_correct).

%% After generalization:
conclusion(fibonacci(N, F(N))) :-
    computed_value(N, F(N)),          %% F(N) is a metavariable
    active_assumption(fibonacci_formula_correct).
```

The generalization engine uses a **bounded anti-unification** algorithm: given two or more harvested ground facts, it computes their least general generalization (LGG). With only one observation, it substitutes the first constant with a metavariable if the constant appears in a known "parameter position" (pre-registered via `parameter_position/2` predicates).

**Stage 3 — Archive:** Generalized patterns are written to the CKS with full provenance:

```prolog
%% archive_entry/5 in the CKS:
archive_entry(
    id('ring_identity_015'),
    pattern('For any commutative ring R, (a+b)^2 = a^2 + 2ab + b^2'),
    provenance(session('S20260626-001'), derivation('lean4_exec', 'ring')),
    confidence(verified),                %% verified | high | medium | low | speculative
    timestamp('2026-06-26T08:15:37Z')
).
```

Confidence levels:
- `verified`: Lean 4 proof succeeded (`lean4_exit_code(0)`)
- `high`: Multiple independent derivations across sessions
- `medium`: Single rigorous derivation, no contradictions
- `low`: Assumption-dependent derivation, not assumption-drop-tested
- `speculative`: Single observation, not yet generalized

**Stage 4 — Heuristic Update:** This is the most novel component. EVO updates **meta-rules** that influence future tier routing, tool choice, and assumption priors.

```prolog
%% Meta-rule format:
meta_rule(RuleId, Condition, Action, Weight, Evidence).

%% Example: after 5+ successes with 'ring' tactic on polynomial goals:
meta_rule(
    'tactic_ring_for_poly',
    condition(goal_contains('ring_expression')),  %% heuristic feature
    action(prefer_tactic('ring')),
    weight(0.85),
    evidence(count_success(7), count_failure(1))
).

%% Example: after repeated failures with 'omega' on non-linear goals:
meta_rule(
    'avoid_omega_nonlinear',
    condition(goal_contains('multiplication_of_variables')),
    action(avoid_tactic('omega')),
    weight(0.72),
    evidence(count_failure(4))
).
```

These meta-rules are not hard constraints — they are **soft priors** that the TRIAGE system consults when no tier is pre-assigned. They influence, but never override, the explicit tier triage injected by the runtime.

---

## Part IV: The Learning Loop — Detailed Workflow

### 4.1 Pre-Session Bootstrap

Before each interaction, EVO loads relevant CKS entries:

```prolog
bootstrap :-
    extract_problem_features(Features),      %% e.g., contains('Nat'), contains('inequality')
    cks_query(matches_features(Features, Entries)),
    forall(member(E, Entries), assert_kb_entry(E)),
    load_meta_rules(RelevantRules),
    assert_meta_rules(RelevantRules).
```

`assert_kb_entry/1` converts CKS patterns into KB predicates:

```prolog
assert_kb_entry(archive_entry(Id, Pattern, _, confidence(verified), _)) :-
    known_fact(Id, Pattern).
assert_kb_entry(archive_entry(Id, Pattern, _, confidence(high), _)) :-
    heuristic(Id, Pattern).  %% weaker than known_fact
```

The bootstrap is **conservative**: only `verified` and `high` confidence entries are loaded as facts. `medium` entries become *heuristics* (premises that must be explicitly activated as assumptions). `low` and `speculative` entries are not loaded automatically but can be queried on demand.

### 4.2 During Interaction

During the main reasoning loop, EVO has access to:

1. **Cached patterns:** `known_fact/2` predicates from verified past sessions
2. **Heuristic suggestions:** `meta_rule/5` rules that influence tool/tactic preference
3. **Failure warnings:** `known_fragility/2` predicates that flag approaches that failed historically
4. **The current session KB** (standard EVO operation)

Critically, cached patterns **do not bypass** the current tier's evidence requirements. A `known_fact/2` is a time-saver — the fact is available for query, but the conclusion it supports still requires its own derivation. The difference is that the derivation may now be shorter (the fact is a premise).

### 4.3 Post-Session Reflection (Formal Specification)

```prolog
%% post_session/2 — the full reflection pipeline
post_session(SessionId, Outcome) :-
    harvest(SessionId, Harvest),
    generalize(Harvest, Patterns),
    cks_archive(Patterns, ArchiveIds),
    update_meta_rules(Harvest, Patterns, ArchiveIds),
    Outcome = completed(Patterns, ArchiveIds).

%% harvest/2
harvest(SessionId, harvest(Obs, Asms, Concs, Fails)) :-
    findall(Fact, (observation(Fact), session_id(SessionId)), Obs),
    findall(A-J, (assumption(A, J), session_id(SessionId)), Asms),
    findall(C-P, (prove(conclusion(C), P), session_id(SessionId)), Concs),
    findall(E-G, (failed_proof(E, G), session_id(SessionId)), Fails).

%% generalize/2 — uses bounded anti-unification
generalize(harvest([], _, _, []), []) :- !.
generalize(harvest(Obs, Asms, Concs, Fails), Patterns) :-
    anti_unify_all(Obs, GeneralizedObs),
    anti_unify_all(Concs, GeneralizedConcs),
    abstract_failures(Fails, FailurePatterns),
    Patterns = [generalized_observations(GeneralizedObs),
                generalized_conclusions(GeneralizedConcs),
                failure_patterns(FailurePatterns)].

%% cks_archive/2 — write patterns to Cumulative Knowledge Store
cks_archive([], []).
cks_archive([P|Ps], [Id|Ids]) :-
    assign_confidence(P, Confidence),
    generate_cks_id(Id),
    term_string(P, PatternString),
    assert_cks_entry(Id, PatternString, Confidence),
    cks_archive(Ps, Ids).

%% assign_confidence/2 — confidence heuristic based on derivation depth
assign_confidence(P, verified) :-
    P = generalized_conclusions(_),
    lead_verification_tool(P, lean4_exec),
    !.
assign_confidence(P, high) :-
    P = generalized_conclusions(_),
    lead_verification_tool(P, maths_problem),
    verify_final_confirm(P),
    !.
assign_confidence(_, medium).             %% default — single session, consistent

%% update_meta_rules/3
update_meta_rules(Harvest, Patterns, ArchiveIds) :-
    detect_repeated_failures(Harvest, FailureSignal),
    detect_repeated_successes(Harvest, SuccessSignal),
    adjust_meta_weights(FailureSignal, SuccessSignal),
    maybe_create_new_meta_rule(FailureSignal, SuccessSignal).
```

---

## Part V: Self-Initializing Domain Knowledge

Currently, EVO has no domain-specific knowledge beyond what is loaded per interaction. The redesign adds a **self-initialization protocol**:

```prolog
%% At first boot (or cold start), EVO generates its own domain taxonomy
%% by reflecting on its own architecture specification:

generate_domain_taxonomy :-
    self_reflect('tiers', Tiers),
    self_reflect('tools', Tools),
    forall(member(Tier, Tiers),
           forall(member(Tool, Tools),
                  analyze_tier_tool_affinity(Tier, Tool, Domain))),
    build_taxonomy(Domains).
```

In practice, EVO's first post-boot session would generate a domain taxonomy covering:
- **Algebra**: ring expressions, polynomial identities, field operations
- **Number Theory**: modular arithmetic, divisibility, prime properties
- **Logic**: propositional calculus, predicate logic, natural deduction
- **Analysis**: limits, continuity, differentiation
- **Code Verification**: Lean proofs, Python correctness
- **Meta-Reasoning**: assumption management, tier selection heuristics

Each domain gets an initial set of **candidate patterns** derived by anti-unifying the architectural specification itself with EVO's own system message.

---

## Part VI: Contradiction Detection Across Sessions

The most powerful new capability is **cross-session contradiction detection**:

```prolog
cross_session_contradiction(SessionA, SessionB, Contradiction) :-
    cks_entry(SessionA, entry(IdA, PatternA, _, ConfidenceA, _)),
    cks_entry(SessionB, entry(IdB, PatternB, _, ConfidenceB, _)),
    contradicts(PatternA, PatternB),
    ConfidenceA \= speculative,
    ConfidenceB \= speculative,
    Contradiction = contradiction(IdA, IdB, PatternA, PatternB).
```

When a contradiction is detected, EVO:
1. Flags both entries with `status(contested)`
2. Generates a **contradiction resolution task** (new interaction) that tests which pattern holds under strictest evidence
3. Archives the resolution outcome
4. Updates meta-rule weights: assumptions common to the disproven pattern get penalty

---

## Part VII: Implementation Roadmap

### Phase 1 — Session Journaling (1-2 days)
- Add `session_id/1` and `observation/2` with session context to all KBs
- Implement `post_session/1` callback that archives raw harvest data as JSON
- No generalization yet; just raw archival

### Phase 2 — Bounded Generalization (3-5 days)
- Implement `anti_unify/3` for Prolog terms
- Implement `generalize/2` with parameter position registration
- Add confidence assignment heuristics
- Write CKS query interface (`cks_query/1`)

### Phase 3 — Bootstrap Loading (2-3 days)
- Implement `bootstrap/0` with feature extraction and CKS matching
- Add `known_fact/2` and `heuristic/2` predicates
- Verify that cached patterns do not bypass tier evidence gates

### Phase 4 — Meta-Rule Learning (5-7 days)
- Implement `meta_rule/5` representation
- Implement weight update based on success/failure counts
- Add TRIAGE integration: consult meta-rules when tier is unassigned

### Phase 5 — Cross-Session Contradiction (3-4 days)
- Implement cross-session contradiction detection
- Implement contradiction resolution workflow
- Add contested entry lifecycle management

### Phase 6 — Self-Initialization (2 days)
- Implement domain taxonomy generation
- Boot-time population of initial candidate patterns

---

## Part VIII: Safeguards and Failure Modes

### What Could Go Wrong

| Failure Mode | Mitigation |
|--------------|------------|
| **Over-generalization** | Bounded anti-unification requires N >= 2 examples for full generalization. Single-example patterns get `speculative` confidence. |
| **Meta-rule overfitting** | Meta-rule weights have a maximum cap (0.95). A `boost` parameter decays by 5% per session without reinforcement. |
| **CKS bloat** | Archive entries older than 90 days auto-deprecate unless referenced by a recent session. |
| **Contradiction cascade** | Maximum one contradiction resolution task per pair of entries per week. |
| **Cached stale knowledge** | `known_fact/2` entries have a `last_validated` timestamp. Entries older than 30 days are downgraded to `heuristic/2`. |
| **Session identity spoofing** | Session IDs are cryptographically signed (`HMAC-SHA256(system_secret, timestamp + nonce)`). |

### Guardrails

```
WHEN (confidence = verified)  ->  fact may be loaded as premise
WHEN (confidence = high)      ->  fact loaded as heuristic
WHEN (confidence = medium)    ->  fact queryable but not auto-loaded
WHEN (confidence = low)       ->  fact queryable, requires explicit activation
WHEN (confidence = speculative) ->  fact not loaded; used only for contradiction detection
```

---

## Part IX: Relationship to Existing Architecture

| Existing Component | Redesigned Role |
|-------------------|-----------------|
| `reason_scratch_pad` | Absorbed into CKS domain store |
| `code_scratch_pad` | Absorbed into CKS domain store |
| `prove_scratch_pad` | Absorbed into CKS domain store; becomes the Lean lemma archive |
| `query_proof_kb` | Extended to query CKS archived lemmas |
| Session KB (per-interaction) | Unchanged — remains ephemeral and self-contained |
| `mind_agent` | May be called to assist with generalization or contradiction analysis |
| `prolog_exec` | Primary implementation language for the learning loop itself |

---

## Part X: Conclusion

The redesign transforms EVO from a session-isolated verifier into a **cumulatively learning** autonomous reasoning system. The key insight is that EVO already has all the primitives it needs — explicit assumptions, consistency checks, proof traces, tier-specific evidence — but they are ephemeral. By adding:

1. A versioned Cumulative Knowledge Store
2. A post-hoc reflection pipeline with bounded generalization
3. Meta-rule learning for tool and tactic selection
4. Cross-session contradiction detection
5. Confidence-based knowledge loading

...EVO can learn from every interaction while preserving its four inviolable principles. The system never guesses, never bypasses evidence, and never forgets — it accumulates, generalizes, and self-corrects.

---

*This document was saved as a CKS entry (confidence: self-verified). The architectural decisions described herein are being implemented in Phase 0 — the first session that learns how to learn.*
