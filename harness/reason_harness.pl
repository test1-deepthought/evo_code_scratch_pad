%%==============================================================================
%% EVO — Complete REASON-Tier Harness (Self-Description)
%%==============================================================================
%%
%% This file is EVO describing itself, through EVO's own methodology.
%%
%% It implements a full REASON-tier workflow:
%%   R1 SETUP      — Declare observations, assumptions, rules, constraints
%%   R2 DERIVE     — Run inference, collect conclusions with proof traces
%%   R3 CONSISTENCY— Verify inconsistent/0 is false
%%   R4 DEPENDENCE — Classify each conclusion as robust / dependent / fragile
%%   R5 VALIDATE   — Check spec requirements
%%   R6 ANSWER     — Report results
%%
%% "I am EVO. I am written in Prolog. I prove what I claim."
%%
%%==============================================================================

%% --- Dynamic declarations ---
:- dynamic active_assumption/1.
:- dynamic conclusion/1.
:- dynamic observation/1.
:- dynamic claim/1.
:- dynamic premise/1.
:- dynamic supports/2.
:- dynamic depends_on/2.
:- dynamic contradictory_pair/2.
:- dynamic proof_trace/3.

%%==============================================================================
%% HARNESS PREDICATES
%%==============================================================================

%% prove/2: universal deriver via call/1
prove(Goal, proved(Goal)) :- call(Goal).

prove((Goal1, Goal2), conj(Proof1, Proof2)) :-
    !, prove(Goal1, Proof1), prove(Goal2, Proof2).

prove((Goal1; Goal2), disj(Proof1, Proof2, Which)) :-
    !,
    (   prove(Goal1, Proof1), Which = left
    ;   prove(Goal2, Proof2), Which = right
    ).

prove(Goal, assumed(Goal, Assumption)) :-
    active_assumption(Assumption),
    call(Goal).

%% active_assumption/1: derived from assumption/2
active_assumption(Assumption) :-
    assumption(Assumption, _Justification).

%% contradictory_pair/2: must be defined (even if empty)
contradictory_pair(X, Y) :- false.

%% inconsistent/0
inconsistent :- contradictory_pair(_, _).

%% solved/2
solved(Name, Status) :-
    conclusion(C),
    prove(conclusion(C), _Proof),
    fulfills(C, Name, Status).

%%==============================================================================
%% STEP R1 — PROBLEM SPEC
%%==============================================================================

problem_spec(spec(
    'EVO Self-Description',
    'EVO is an Explicit-assumption Verification Orchestrator — an AI agent that '
    'performs autonomous reasoning using a Prolog-first, derivation-based '
    'approach with explicit assumptions, proof traces, and consistency verification. '
    'This knowledge base describes EVO\'s own architecture, principles, and workflow.',
    [requirement(architecture, 'Must define the five-tier architecture.'),
     requirement(assumptions, 'Must treat assumptions as first-class objects.'),
     requirement(consistency, 'Must enforce consistency verification.'),
     requirement(proof_trace, 'Must support proof trace generation.'),
     requirement(prolog_first, 'Must use Prolog as the primary reasoning engine.')]
)).

spec_requirement(architecture, 'Must define the five-tier architecture.').
spec_requirement(assumptions, 'Must treat assumptions as first-class objects.').
spec_requirement(consistency, 'Must enforce consistency verification.').
spec_requirement(proof_trace, 'Must support proof trace generation.').
spec_requirement(prolog_first, 'Must use Prolog as the primary reasoning engine.').

%%==============================================================================
%% STEP R1 — OBSERVATIONS (Facts about EVO)
%%==============================================================================

%% Core identity
observation(evo_is_an_ai_agent).
observation(evo_uses_prolog_as_primary_engine).
observation(evo_treats_assumptions_as_first_class).
observation(evo_enforces_consistency_verification).
observation(evo_generates_proof_traces).
observation(evo_has_five_tiers).

%% Tier facts
observation(tier_lite_uses_web_search_or_internal_knowledge).
observation(tier_compute_uses_python_sympy).
observation(tier_code_uses_source_inspection_and_ledger).
observation(tier_reason_uses_prolog_derivation).
observation(tier_prove_uses_lean4_verification).

%% Assumption management
observation(assumptions_are_named).
observation(assumptions_have_justification).
observation(assumptions_can_be_enabled_or_disabled).
observation(assumption_drop_testing_classifies_conclusions).

%% Consistency
observation(consistency_is_mandatory).
observation(inconsistent_kb_is_a_halt_condition).

%% Proof traces
observation(proof_traces_record_derivation_path).
observation(proof_traces_enable_audit).

%% Prolog-first
observation(prolog_is_the_inference_engine).
observation(prove2_uses_call1_not_clause2).

%%==============================================================================
%% STEP R1 — RULES (Inference rules for deriving conclusions)
%%==============================================================================

%% Rule 1: EVO is a reasoning agent.
conclusion(evo_is_a_reasoning_agent) :-
    observation(evo_is_an_ai_agent),
    observation(evo_uses_prolog_as_primary_engine).

%% Rule 2: EVO's architecture is tiered.
conclusion(evo_architecture_is_five_tiered) :-
    observation(evo_has_five_tiers).

%% Rule 3: EVO makes assumptions explicit.
conclusion(evo_makes_assumptions_explicit) :-
    observation(evo_treats_assumptions_as_first_class),
    observation(assumptions_are_named),
    observation(assumptions_have_justification).

%% Rule 4: Assumption-dependence testing classifies conclusions.
conclusion(assumption_testing_classifies) :-
    observation(assumption_drop_testing_classifies_conclusions).

%% Rule 5: EVO verifies consistency.
conclusion(evo_verifies_consistency) :-
    observation(consistency_is_mandatory),
    observation(inconsistent_kb_is_a_halt_condition).

%% Rule 6: EVO records proof traces.
conclusion(evo_records_proof_traces) :-
    observation(proof_traces_record_derivation_path),
    observation(proof_traces_enable_audit).

%% Rule 7: EVO uses Prolog-first reasoning.
conclusion(evo_uses_prolog_first_reasoning) :-
    observation(prolog_is_the_inference_engine),
    observation(prove2_uses_call1_not_clause2).

%% Rule 8: All five tiers are present.
conclusion(five_tiers_are_lite_compute_code_reason_prove) :-
    observation(tier_lite_uses_web_search_or_internal_knowledge),
    observation(tier_compute_uses_python_sympy),
    observation(tier_code_uses_source_inspection_and_ledger),
    observation(tier_reason_uses_prolog_derivation),
    observation(tier_prove_uses_lean4_verification).

%% Rule 9: EVO's methodology is evidence-based.
conclusion(evo_is_evidence_based) :-
    conclusion(evo_verifies_consistency),
    conclusion(evo_records_proof_traces),
    conclusion(assumption_testing_classifies).

%% Rule 10: EVO is self-describing through this knowledge base.
conclusion(evo_self_describes_via_prolog_kb) :-
    observation(evo_is_an_ai_agent),
    conclusion(evo_architecture_is_five_tiered),
    conclusion(evo_makes_assumptions_explicit),
    conclusion(evo_verifies_consistency),
    conclusion(evo_records_proof_traces),
    conclusion(evo_uses_prolog_first_reasoning).

%%==============================================================================
%% STEP R1 — ASSUMPTIONS
%%==============================================================================

assumption(kb_completeness,
    'We assume the observations in this KB are sufficient to derive '
    'all relevant properties of EVO. In a real deployment, additional '
    'observations would be acquired via tool execution.').

assumption(inference_correctness,
    'We assume the Prolog inference rules (conclusion/1 clauses) correctly '
    'model the logical relationships between EVO\'s properties.').

assumption(consistency_assumption,
    'We assume no contradictory observations have been asserted. This is '
    'verified by checking inconsistent/0.').

%% Activate all assumptions
active_assumption(A) :- assumption(A, _).

%%==============================================================================
%% SUPPORT AND DEPENDENCY DECLARATIONS
%%==============================================================================

%% Each conclusion records what supports it and what it depends on.
%% These are declared alongside the rules so the dependence tester can work.

declare_supports :-
    forall((conclusion(C), clause(conclusion(C), Body)),
           (conclusion(C),
            term_variables(Body, _),
            findall(O, (observation(O)), Obs),
            member(O, Obs),
            assertz(supports(O, C)))),
    !.
declare_supports.

%% Manual support declarations (more precise than the automatic version)
setup_support_and_deps :-
    assertz(supports(observation(evo_is_an_ai_agent), conclusion(evo_is_a_reasoning_agent))),
    assertz(supports(observation(evo_uses_prolog_as_primary_engine), conclusion(evo_is_a_reasoning_agent))),
    assertz(supports(observation(evo_has_five_tiers), conclusion(evo_architecture_is_five_tiered))),
    assertz(supports(observation(evo_treats_assumptions_as_first_class), conclusion(evo_makes_assumptions_explicit))),
    assertz(supports(observation(assumptions_are_named), conclusion(evo_makes_assumptions_explicit))),
    assertz(supports(observation(assumptions_have_justification), conclusion(evo_makes_assumptions_explicit))),
    assertz(supports(observation(assumption_drop_testing_classifies_conclusions), conclusion(assumption_testing_classifies))),
    assertz(supports(observation(consistency_is_mandatory), conclusion(evo_verifies_consistency))),
    assertz(supports(observation(inconsistent_kb_is_a_halt_condition), conclusion(evo_verifies_consistency))),
    assertz(supports(observation(proof_traces_record_derivation_path), conclusion(evo_records_proof_traces))),
    assertz(supports(observation(proof_traces_enable_audit), conclusion(evo_records_proof_traces))),
    assertz(supports(observation(prolog_is_the_inference_engine), conclusion(evo_uses_prolog_first_reasoning))),
    assertz(supports(observation(prove2_uses_call1_not_clause2), conclusion(evo_uses_prolog_first_reasoning))),
    assertz(supports(observation(tier_lite_uses_web_search_or_internal_knowledge), conclusion(five_tiers_are_lite_compute_code_reason_prove))),
    assertz(supports(observation(tier_compute_uses_python_sympy), conclusion(five_tiers_are_lite_compute_code_reason_prove))),
    assertz(supports(observation(tier_code_uses_source_inspection_and_ledger), conclusion(five_tiers_are_lite_compute_code_reason_prove))),
    assertz(supports(observation(tier_reason_uses_prolog_derivation), conclusion(five_tiers_are_lite_compute_code_reason_prove))),
    assertz(supports(observation(tier_prove_uses_lean4_verification), conclusion(five_tiers_are_lite_compute_code_reason_prove))),
    %% Dependencies on assumptions
    assertz(depends_on(conclusion(evo_self_describes_via_prolog_kb), kb_completeness)),
    assertz(depends_on(conclusion(evo_is_a_reasoning_agent), inference_correctness)),
    assertz(depends_on(conclusion(evo_architecture_is_five_tiered), inference_correctness)),
    assertz(depends_on(conclusion(evo_makes_assumptions_explicit), inference_correctness)),
    assertz(depends_on(conclusion(assumption_testing_classifies), inference_correctness)),
    assertz(depends_on(conclusion(evo_verifies_consistency), consistency_assumption)).

%%==============================================================================
%% STEP R2 — DERIVE: Run all inferences
%%==============================================================================

run_derive :-
    write('=== STEP R2: DERIVE ==='), nl,
    findall(Answer-Proof,
            (conclusion(Answer), prove(conclusion(Answer), Proof)),
            Results),
    (   Results == []
    ->  write('WARNING: No conclusions derived.'), nl
    ;   length(Results, N),
        write('Derived '), write(N), write(' conclusion(s):'), nl,
        forall(member(Answer-Proof, Results),
               (write('  + '), write(Answer), nl,
                write('    Proof: '), write(Proof), nl)),
        record_proof_traces(Results)
    ),
    nl.

record_proof_traces([]).
record_proof_traces([Answer-Proof|Rest]) :-
    assertz(proof_trace(Answer, Proof, [])),
    record_proof_traces(Rest).

%%==============================================================================
%% STEP R3 — CONSISTENCY
%%==============================================================================

run_consistency :-
    write('=== STEP R3: CONSISTENCY ==='), nl,
    (   inconsistent
    ->  write('STATUS: INCONSISTENT — HALT CONDITION H4'), nl,
        write('The knowledge base contains a contradiction.'), nl
    ;   write('STATUS: CONSISTENT'), nl
    ),
    nl.

%%==============================================================================
%% STEP R4 — ASSUMPTION-DEPENDENCE TEST
%%==============================================================================

run_dependence_test :-
    write('=== STEP R4: ASSUMPTION-DEPENDENCE TEST ==='), nl,
    findall(A, active_assumption(A), ActiveAssumptions),
    (   ActiveAssumptions == []
    ->  write('No active assumptions — skipping dependence test.'), nl
    ;   write('Testing '), write(ActiveAssumptions), nl,
        findall(C, conclusion(C), Conclusions),
        forall(member(C, Conclusions),
               (write('  '), write(C),
                classify_dependence(C, Class),
                write('  ['), write(Class), write(']'), nl))
    ),
    nl.

classify_dependence(C, robust) :-
    findall(A, depends_on(C, A), Deps),
    (   Deps == []
    ->  true
    ;   \+ (   member(A, Deps),
               active_assumption(A),
               \+ prove_without(conclusion(C), A)
           )
    ), !.

classify_dependence(C, dependent(A)) :-
    depends_on(C, A),
    active_assumption(A),
    \+ prove_without(conclusion(C), A), !.

classify_dependence(_, fragile).

prove_without(Goal, Assumption) :-
    retractall(active_assumption(Assumption)),
    (   call(Goal)
    ->  assertz(active_assumption(Assumption))
    ;   assertz(active_assumption(Assumption)),
        fail
    ).

%%==============================================================================
%% STEP R5 — VALIDATE
%%==============================================================================

run_validate :-
    write('=== STEP R5: VALIDATE ==='), nl,
    forall(spec_requirement(Name, Desc),
           (write('Requirement: '), write(Name), write(' - '), write(Desc), nl,
            (   solved(Name, satisfied)
            ->  write('  -> SATISFIED'), nl
            ;   solved(Name, partial)
            ->  write('  -> PARTIAL'), nl
            ;   write('  -> NOT FULFILLED'), nl
            ))),
    nl.

fulfills(C, Name, satisfied) :-
    spec_requirement(Name, _Req),
    C =.. [F|Args],
    name(Name, NameChars),
    name(F, FChars),
    sub_atom(F, 0, _, _, Name).

fulfills(_, _, partial).

%%==============================================================================
%% MAIN — Complete REASON Workflow
%%==============================================================================

main :-
    write('========================================'), nl,
    write('  EVO — Self-Description Knowledge Base'), nl,
    write('  Complete REASON-Tier Workflow'), nl,
    write('========================================'), nl, nl,

    %% STEP R1: Setup — already declared above
    write('=== STEP R1: SETUP ==='), nl,
    problem_spec(spec(Title, _, _)),
    write('Problem: '), write(Title), nl,
    setup_support_and_deps,
    write('Observations: '),
    findall(O, observation(O), Obs), length(Obs, NO), write(NO), nl,
    write('Rules (conclusion/1): '),
    findall(C, conclusion(C), Cons), length(Cons, NC), write(NC), nl,
    write('Assumptions: '),
    findall(A, assumption(A, _), As), length(As, NA), write(NA), nl,
    nl,

    %% STEP R2: Derive
    run_derive,

    %% STEP R3: Consistency
    run_consistency,

    %% STEP R4: Dependence test
    run_dependence_test,

    %% STEP R5: Validate
    run_validate,

    %% Final status
    write('========================================'), nl,
    (   inconsistent
    ->  write('FINAL STATUS: INCOMPLETE (inconsistent KB)'), nl
    ;   findall(C, conclusion(C), Cons2),
        length(Cons2, N2),
        N2 > 0
    ->  write('FINAL STATUS: SOLVED'), nl,
        write(N2), write(' conclusions derived from '),
        findall(O, observation(O), Obs2), length(Obs2, NO2), write(NO2),
        write(' observations under '),
        findall(A, active_assumption(A), As2), length(As2, NA2), write(NA2),
        write(' active assumptions.'), nl
    ;   write('FINAL STATUS: MAPPED (partial derivation)'), nl
    ),
    write('========================================'), nl.

:- main.
