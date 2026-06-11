%%==============================================================================
%% EVO — Tier Dispatch and Workflow Orchestration
%%==============================================================================
%%
%% EVO classifies every task into one of five tiers at runtime.
%% Each tier has its own primary evidence mechanism, workflow steps,
%% and halt conditions.
%%
%% The tier is determined BEFORE any tool use by the Runtime Tier-0 Triage.
%% This module defines the dispatch rules and workflow contracts.
%%
%%==============================================================================

:- dynamic tier/1.
:- dynamic workflow_step/1.
:- dynamic task_status/2.

%%------------------------------------------------------------------------------
%% TIER DECLARATION
%%------------------------------------------------------------------------------
tier(lite).
tier(compute).
tier(code).
tier(reason).
tier(prove).

%%------------------------------------------------------------------------------
%% TIER — Primary Evidence Mechanism
%%------------------------------------------------------------------------------
primary_evidence(lite, 'Web search / internal knowledge / compact Prolog ledger').
primary_evidence(compute, 'Python/SymPy with computation_check and verified_value').
primary_evidence(code, 'Source inspection + reasoning ledger (observations -> hypotheses -> verification)').
primary_evidence(reason, 'Prolog derivation (prove/2 with proof traces and assumption testing)').
primary_evidence(prove, 'Lean 4 verification (lean4_exit_code(0) + lean4_verified status)').

%%------------------------------------------------------------------------------
%% TIER — Workflow Steps
%%------------------------------------------------------------------------------
workflow(lite, [tool_execution, mini_kb_validate, answer]).
workflow(compute, [setup, compute, validate, answer]).
workflow(code, [inspect, build_ledger, analyze, verify, answer]).
workflow(reason, [setup, derive, consistency, dependence_test, validate, answer]).
workflow(prove, [setup, explore, build_verify, validate, answer]).

%%------------------------------------------------------------------------------
%% TIER — Halt Conditions
%%------------------------------------------------------------------------------
halt_condition(lite, 'Insufficient internal knowledge and no tool can fill the gap.').
halt_condition(compute, 'Python execution fails unrecoverably or result is self-contradictory.').
halt_condition(code, 'Relevant code/repo evidence cannot be inspected. Verification cannot be run.').
halt_condition(reason, 'KB empty. Derivation produces zero conclusions. Inconsistency irreparable.').
halt_condition(prove, 'Python exploration fails. Lean proof contains sorry after deadline. No valid lemma path.').

%%------------------------------------------------------------------------------
%% TIER VALIDATION
%%------------------------------------------------------------------------------
valid_tier(T) :-
    tier(T),
    primary_evidence(T, _),
    workflow(T, Steps),
    Steps \= [].

%%------------------------------------------------------------------------------
%% WORKFLOW STEP TRACKING
%%------------------------------------------------------------------------------
current_step(Step) :-
    workflow_step(Step),
    !.

begin_workflow(Tier) :-
    retractall(workflow_step(_)),
    workflow(Tier, [First|_]),
    assertz(workflow_step(First)),
    assertz(task_status(started, Tier)).

advance_step :-
    workflow_step(Current),
    retractall(workflow_step(Current)),
    findall(T, task_status(started, T), [Tier]),
    workflow(Tier, Steps),
    append(Prefix, [Current|Rest], Steps),
    (   Rest = [Next|_]
    ->  assertz(workflow_step(Next))
    ;   assertz(task_status(completed, Tier))
    ),
    !.

%%------------------------------------------------------------------------------
%% TIER REPORT
%%------------------------------------------------------------------------------
tier_report :-
    write('=== EVO Tier Dispatch ==='), nl,
    forall(valid_tier(T),
           (write('Tier: '), write(T), nl,
            primary_evidence(T, E),
            write('  Evidence: '), write(E), nl,
            workflow(T, Steps),
            write('  Steps: '), write(Steps), nl,
            halt_condition(T, H),
            write('  Halt: '), write(H), nl,
            nl)),
    findall(S, workflow_step(S), Current),
    (   Current == []
    ->  write('No active workflow.'), nl
    ;   write('Current step: '), write(Current), nl
    ),
    findall(T-S, task_status(T, S), Status),
    (   Status == []
    ->  true
    ;   write('Task status: '), write(Status), nl
    ),
    nl.

%%------------------------------------------------------------------------------
%% MAIN
%%------------------------------------------------------------------------------
main :-
    write('=== EVO Tier Dispatch Module ==='), nl,
    tier_report.

:- main.
