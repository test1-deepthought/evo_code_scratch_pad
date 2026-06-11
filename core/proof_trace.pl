%%==============================================================================
%% EVO — Proof Trace Generation
%%==============================================================================
%%
%% Every derivation in EVO carries a proof trace — a structured record of
%% how a conclusion was reached, what premises it rests on, and which
%% assumptions were used.
%%
%% Proof traces enable:
%%   1. Explanation of any conclusion
%%   2. Audit of reasoning steps
%%   3. Assumption-dependence analysis
%%   4. Contradiction localization
%%
%% "A conclusion without a trace is a guess. A conclusion with a trace is evidence."
%%
%%==============================================================================

:- dynamic proof_trace/3.
:- dynamic observation/1.

%%------------------------------------------------------------------------------
%% PROOF TRACE RECORDING
%%
%% proof_trace(Conclusion, Derivation, Dependencies) where:
%%   Conclusion   — the derived result
%%   Derivation   — how it was derived (rule name, direct observation, etc.)
%%   Dependencies — list of premises/observations/assumptions it rests on
%%------------------------------------------------------------------------------

record_trace(Conclusion, direct, Deps) :-
    findall(D, (observation(D), supports(D, Conclusion)), Deps),
    assertz(proof_trace(Conclusion, direct, Deps)).

record_trace(Conclusion, derived(Rule), Deps) :-
    findall(D, depends_on(Conclusion, D), Deps1),
    findall(O, (observation(O), supports(O, Conclusion)), Deps2),
    append(Deps1, Deps2, Deps),
    assertz(proof_trace(Conclusion, derived(Rule), Deps)).

record_trace(Conclusion, assumed(Assumption), [Assumption]) :-
    active_assumption(Assumption),
    depends_on(Conclusion, Assumption),
    assertz(proof_trace(Conclusion, assumed(Assumption), [Assumption])).

%%------------------------------------------------------------------------------
%% PROOF EXPLANATION
%%
%% explain/1: print a human-readable proof trace for a conclusion.
%%------------------------------------------------------------------------------
explain(Conclusion) :-
    proof_trace(Conclusion, Derivation, Dependencies),
    !,
    write('=== PROOF TRACE: '), write(Conclusion), write(' ==='), nl,
    write('Derivation: '),
    (   Derivation = direct
    ->  write('Direct observation')
    ;   Derivation = derived(Rule)
    ->  write('Derived via rule: '), write(Rule)
    ;   Derivation = assumed(Assumption)
    ->  write('Assumption-dependent: '), write(Assumption)
    ;   write(Derivation)
    ),
    nl,
    write('Dependencies: '), write(Dependencies), nl,
    (   member(D, Dependencies),
        (   observation(D)
        ->  write('  Obs: '), write(D), nl
        ;   active_assumption(D)
        ->  write('  Assumption: '), write(D), nl
        ;   true
        ),
        fail
    ;   true
    ),
    nl.

explain(Conclusion) :-
    \+ proof_trace(Conclusion, _, _),
    write('No proof trace recorded for: '), write(Conclusion), nl.

%%------------------------------------------------------------------------------
%% AUDIT TRAIL
%%
%% audit/0: print all proof traces in the KB
%%------------------------------------------------------------------------------
audit :-
    write('=== COMPLETE AUDIT TRAIL ==='), nl,
    findall(C, proof_trace(C, _, _), Conclusions),
    (   Conclusions == []
    ->  write('No proof traces recorded.'), nl
    ;   forall(member(C, Conclusions), explain(C))
    ),
    nl.

%%------------------------------------------------------------------------------
%% PROOF DEPTH ANALYSIS
%%
%% How many hops from observation to conclusion?
%%------------------------------------------------------------------------------
proof_depth(Conclusion, Depth) :-
    proof_trace(Conclusion, _, Dependencies),
    (   Dependencies == []
    ->  Depth = 0
    ;   findall(D, (member(D, Dependencies), observation(D)), DirectObs),
        length(DirectObs, N),
        Depth is N + 1
    ).

%%------------------------------------------------------------------------------
%% MAIN
%%------------------------------------------------------------------------------
main :-
    write('=== EVO Proof Trace System ==='), nl,
    write('Ready to record and explain derivations.'), nl,
    nl,
    audit.

:- main.
