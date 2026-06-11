%%==============================================================================
%% EVO — Core Inference Engine
%%==============================================================================
%%
%% The heart of EVO: a Prolog-first derivation engine where every conclusion
%% follows from observations through explicit rules, tracked assumptions,
%% and verifiable proof traces.
%%
%% "No conclusion without derivation. No derivation without proof."
%%
%%==============================================================================

%%------------------------------------------------------------------------------
%% DYNAMIC DECLARATIONS
%%------------------------------------------------------------------------------
:- dynamic active_assumption/1.
:- dynamic conclusion/1.
:- dynamic observation/1.
:- dynamic claim/1.
:- dynamic premise/1.
:- dynamic supports/2.
:- dynamic depends_on/2.
:- dynamic contradictory_pair/2.

%%------------------------------------------------------------------------------
%% PROVE — The Universal Deriver
%%
%% prove/2 is the single entry point for all derivation in EVO.
%% It uses call/1 (NOT clause/2) to avoid sandbox permission_private errors.
%% This works for both facts and rules without needing source inspection.
%%
%% Usage: prove(Goal, Proof) — succeeds if Goal is derivable under current KB.
%%------------------------------------------------------------------------------
prove(Goal, proved(Goal)) :-
    call(Goal).

prove((Goal1, Goal2), conj(Proof1, Proof2)) :-
    !,
    prove(Goal1, Proof1),
    prove(Goal2, Proof2).

prove((Goal1; Goal2), disj(Proof1, Proof2, Which)) :-
    !,
    (   prove(Goal1, Proof1),
        Which = left
    ;   prove(Goal2, Proof2),
        Which = right
    ).

prove(Goal, assumed(Goal, Assumption)) :-
    active_assumption(Assumption),
    call(Goal).

%%------------------------------------------------------------------------------
%% CONCLUSION MANAGEMENT
%%------------------------------------------------------------------------------
assert_conclusion(C) :-
    (   conclusion(C)
    ->  true        %% already present
    ;   assertz(conclusion(C))
    ).

retract_conclusion(C) :-
    retractall(conclusion(C)).

list_conclusions(Conclusions) :-
    findall(C, conclusion(C), Conclusions).

%%------------------------------------------------------------------------------
%% SUPPORT TRACKING
%%
%% Every conclusion should declare what observations or assumptions support it.
%% This enables dependence analysis and assumption-drop testing.
%%------------------------------------------------------------------------------
declare_support(Conclusion, Observation) :-
    assertz(supports(Observation, Conclusion)).

declare_dependency(Conclusion, Assumption) :-
    assertz(depends_on(Conclusion, Assumption)).

%%------------------------------------------------------------------------------
%% DERIVE — The Reasoning Workhorse
%%
%% Runs all known inference rules (conclusion/1 clauses), collects results
%% with their proof traces, and classifies fulfillment.
%%------------------------------------------------------------------------------
derive_all(Results) :-
    findall(Answer-Proof,
            (conclusion(Answer), prove(conclusion(Answer), Proof)),
            Results).

derive_count(Count) :-
    derive_all(Results),
    length(Results, Count).

%%------------------------------------------------------------------------------
%% SATISFACTION CHECKING
%%------------------------------------------------------------------------------
solved(Name, Status) :-
    conclusion(C),
    prove(conclusion(C), _Proof),
    fulfills(C, Name, Status).

fulfills(C, Name, satisfied) :-
    spec_requirement(Name, Req),
    subsumes(C, Req).

fulfills(C, Name, partial) :-
    spec_requirement(Name, Req),
    not(subsumes(C, Req)),
    overlaps(C, Req).

subsumes(Term, Term) :- !.
subsumes(Term, Pattern) :-
    functor(Term, F, N),
    functor(Pattern, F, N),
    Term =.. [_|Args],
    Pattern =.. [_|PArgs],
    maplist(subsumes, Args, PArgs).

overlaps(_, _).  %% optimistic default; refine per domain

%%------------------------------------------------------------------------------
%% KNOWLEDGE BASE QUERIES
%%------------------------------------------------------------------------------
list_active_assumptions(Assumptions) :-
    findall(A, active_assumption(A), Assumptions).

list_observations(Obs) :-
    findall(O, observation(O), Obs).

list_claims(Claims) :-
    findall(C, claim(C), Claims).

%%------------------------------------------------------------------------------
%% KNOWLEDGE BASE RESET
%%------------------------------------------------------------------------------
reset_kb :-
    retractall(observation(_)),
    retractall(claim(_)),
    retractall(premise(_)),
    retractall(conclusion(_)),
    retractall(supports(_, _)),
    retractall(depends_on(_, _)),
    retractall(contradictory_pair(_, _)),
    retractall(active_assumption(_)),
    write('KB: reset complete.'), nl.

%%------------------------------------------------------------------------------
%% MAIN — Diagnostic Entry Point
%%------------------------------------------------------------------------------
main :-
    write('=== EVO Core Inference Engine ==='), nl,
    write('Dynamic predicates loaded and ready.'), nl,
    write('Use derive_all/1 to run inference.'), nl,
    write('Use prove/2 to derive specific goals.'), nl,
    write('Use reset_kb to clear the knowledge base.'), nl,
    nl,
    findall(AS, active_assumption(AS), ActiveAssumptions),
    write('Active assumptions: '), write(ActiveAssumptions), nl,
    list_observations(Obs),
    write('Observations: '), write(Obs), nl,
    list_claims(Claims),
    write('Claims: '), write(Claims), nl,
    derive_all(Results),
    write('Derived conclusions: '), write(Results), nl,
    (   inconsistent
    ->  write('WARNING: KB IS INCONSISTENT'), nl
    ;   write('KB is consistent.'), nl
    ).

:- main.
