%%==============================================================================
%% EVO — First-Class Assumption Management
%%==============================================================================
%%
%% Assumptions are the defining architectural feature of EVO.
%%
%% Unlike conventional knowledge bases where assumptions are invisible
%% background commitments, EVO makes every assumption EXPLICIT, NAMED,
%% JUSTIFIED, and TESTABLE.
%%
%% "A conclusion is only as strong as its weakest assumption dependency."
%%
%%==============================================================================

:- dynamic active_assumption/1.
:- dynamic assumption/2.
:- dynamic depends_on/2.

%%------------------------------------------------------------------------------
%% DECLARING ASSUMPTIONS
%%
%% Every assumption has:
%%   - A unique name (atom)
%%   - A textual justification explaining WHY this bridge is needed
%%------------------------------------------------------------------------------
%% assumption/2 is declared by the KB builder, e.g.:
%%   assumption(algebra_is_correct, 'We assume basic algebraic identities hold
%%                                   because the domain is a field.').

%%------------------------------------------------------------------------------
%% ACTIVATING / DEACTIVATING ASSUMPTIONS
%%
%% Active assumptions participate in inference.
%% Inactive assumptions are suspended — conclusions that depend on them
%% become unavailable, revealing what the KB can prove WITHOUT the assumption.
%%------------------------------------------------------------------------------
activate_assumption(Name) :-
    assumption(Name, _),
    (   active_assumption(Name)
    ->  true
    ;   assertz(active_assumption(Name))
    ).

deactivate_assumption(Name) :-
    retractall(active_assumption(Name)).

toggle_assumption(Name) :-
    (   active_assumption(Name)
    ->  deactivate_assumption(Name)
    ;   activate_assumption(Name)
    ).

activate_all :-
    assumption(Name, _),
    activate_assumption(Name),
    fail.
activate_all.

deactivate_all :-
    retractall(active_assumption(_)).

%%------------------------------------------------------------------------------
%% ASSUMPTION-DEPENDENCE TESTING
%%
%% For each conclusion, determine whether it survives removal of each
%% active assumption.  This is the core of EVO's robustness analysis.
%%
%% Classification:
%%   ROBUST                — survives removal of ALL assumptions
%%   ASSUMPTION-DEPENDENT(A) — depends on assumption A (fails without it)
%%   FRAGILE               — depends on multiple assumptions
%%------------------------------------------------------------------------------

%% dependence_classify/2: classify a single conclusion
dependence_classify(Conclusion, robust) :-
    conclusion(Conclusion),
    findall(A, depends_on(Conclusion, A), Deps),
    (   Deps == []
    ->  true
    ;   \+ (   member(A, Deps),
               active_assumption(A),
               \+ prove_without(conclusion(Conclusion), A)
           )
    ).

dependence_classify(Conclusion, dependent(A)) :-
    conclusion(Conclusion),
    depends_on(Conclusion, A),
    active_assumption(A),
    \+ prove_without(conclusion(Conclusion), A).

dependence_classify(Conclusion, fragile) :-
    conclusion(Conclusion),
    findall(A, (depends_on(Conclusion, A), active_assumption(A)), Deps),
    length(Deps, N),
    N >= 2,
    \+ dependence_classify(Conclusion, robust),
    \+ dependence_classify(Conclusion, dependent(_)).

%% prove_without/2: test whether Goal succeeds without Assumption active
prove_without(Goal, Assumption) :-
    deactivate_assumption(Assumption),
    (   call(Goal)
    ->  reactivate(Assumption)
    ;   reactivate(Assumption),
        fail
    ).

reactivate(Assumption) :-
    assumption(Assumption, _),
    assertz(active_assumption(Assumption)).

%% dependence_report/1: generate full classification report
dependence_report(Reports) :-
    findall(C-Cls,
            (conclusion(C), dependence_classify(C, Cls)),
            Reports).

%% dependence_report_text/0: print human-readable report
dependence_report_text :-
    dependence_report(Reports),
    write('=== ASSUMPTION DEPENDENCE REPORT ==='), nl,
    forall(member(C-Cls, Reports),
           (write('  '), write(C),
            (   Cls = robust
            ->  write('  [ROBUST]')
            ;   Cls = dependent(A)
            ->  write('  [DEPENDENT on '), write(A), write(']')
            ;   Cls = fragile
            ->  write('  [FRAGILE]')
            ),
            nl)),
    nl.

%%------------------------------------------------------------------------------
%% ASSUMPTION QUERIES
%%------------------------------------------------------------------------------
list_all_assumptions(Assumptions) :-
    findall(Name-Just, assumption(Name, Just), Assumptions).

list_active_assumptions(Active) :-
    findall(Name, active_assumption(Name), Active).

%%------------------------------------------------------------------------------
%% CONSISTENCY — Assumptions cannot contradict observations
%%------------------------------------------------------------------------------
inconsistent :-
    active_assumption(A1),
    active_assumption(A2),
    A1 \= A2,
    contradictory_pair(A1, A2).

%%------------------------------------------------------------------------------
%% MAIN — Diagnostic
%%------------------------------------------------------------------------------
main :-
    write('=== EVO Assumption Manager ==='), nl,
    list_all_assumptions(All),
    write('Total assumptions declared: '), length(All, N), write(N), nl,
    list_active_assumptions(Active),
    write('Active assumptions: '), write(Active), nl,
    (   Active == []
    ->  write('WARNING: No assumptions active — inference may be empty.'), nl
    ;   true
    ),
    dependence_report_text,
    (   inconsistent
    ->  write('WARNING: contradictory assumptions detected.'), nl
    ;   write('No assumption contradictions detected.'), nl
    ),
    nl.

:- main.
