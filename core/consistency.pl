%%==============================================================================
%% EVO — Consistency Verification
%%==============================================================================
%%
%% Consistency is not optional.  A knowledge base that derives inconsistent/0
%% is a knowledge base that proves everything — and therefore nothing.
%%
%% EVO enforces consistency through:
%%   1. Explicit contradictory_pair/2 declarations
%%   2. Automatic detection of direct conflicts
%%   3. Repair strategies when inconsistency is found
%%
%% "A single contradiction collapses the entire KB. Find it. Fix it. Prove it."
%%
%%==============================================================================

:- dynamic contradictory_pair/2.
:- dynamic observation/1.
:- dynamic claim/1.
:- dynamic premise/1.

%%------------------------------------------------------------------------------
%% INCONSISTENCY DETECTION
%%
%% inconsistent/0 succeeds when the KB contains a logical contradiction.
%% This is a HALT condition in REASON/CODE/PROVE tiers.
%%------------------------------------------------------------------------------
inconsistent :-
    contradictory_pair(X, Y),
    are_contradictory(X, Y).

%% By default, contradictory_pair/2 is empty (false).
%% KB builders must declare actual contradictions, e.g.:
%%   contradictory_pair(observation(sky_is_blue), observation(sky_is_red)).
%%   are_contradictory(X, Y) :- X \= Y.  %% any two distinct observations?

%%------------------------------------------------------------------------------
%% ARE_CONTRADICTORY — The General Contradiction Relation
%%
%% Override this for domain-specific contradiction logic.
%% Default: two things are contradictory if they are declared as such.
%%------------------------------------------------------------------------------
are_contradictory(X, Y) :-
    contradictory_pair(X, Y).

are_contradictory(X, Y) :-
    contradictory_pair(Y, X).

%%------------------------------------------------------------------------------
%% DIRECT CONFLICT DETECTION
%%
%% Beyond declared contradictions, EVO can detect structural conflicts:
%%   - An observation and its negation (via negated/1 declarations)
%%   - Mutually exclusive claims
%%------------------------------------------------------------------------------

%% negated/1: declare that two facts are logical negations
:- dynamic negated/1.

negated_form(positive(Fact), negative(Fact)).
negated_form(negative(Fact), positive(Fact)).

contradiction_via_negation :-
    observation(positive(Fact)),
    observation(negative(Fact)).

contradiction_via_negation :-
    claim(positive(Fact)),
    claim(negative(Fact)).

contradiction_via_negation :-
    premise(positive(Fact)),
    premise(negative(Fact)).

%%------------------------------------------------------------------------------
%% CONSISTENCY REPORT
%%------------------------------------------------------------------------------
consistency_status(consistent) :-
    \+ inconsistent,
    \+ contradiction_via_negation.

consistency_status(inconsistent) :-
    inconsistent.

consistency_status(inconsistent) :-
    contradiction_via_negation.

consistency_report :-
    write('=== CONSISTENCY REPORT ==='), nl,
    (   consistency_status(consistent)
    ->  write('STATUS: CONSISTENT'), nl
    ;   write('STATUS: INCONSISTENT'), nl,
        (   inconsistent
        ->  contradictory_pair(X, Y),
            write('  Contradiction: '), write(X), write(' vs '), write(Y), nl,
            fail
        ;   true
        ),
        (   contradiction_via_negation
        ->  write('  Negation conflict detected.'), nl
        ;   true
        )
    ),
    nl.

%%------------------------------------------------------------------------------
%% REPAIR STRATEGIES
%%
%% When inconsistency is detected, EVO can attempt repair:
%%   1. Remove the offending observation
%%   2. Deactivate a contradictory assumption
%%   3. Narrow a claim's scope
%%------------------------------------------------------------------------------

%% repair/0: attempt automatic repair
repair :-
    consistency_status(inconsistent),
    write('Attempting repair...'), nl,
    (   contradictory_pair(X, Y)
    ->  retractall(observation(X)),
        retractall(observation(Y)),
        write('  Removed observations: '), write(X), write(', '), write(Y), nl,
        fail
    ;   true
    ),
    (   contradiction_via_negation
    ->  retractall(observation(positive(_))),
        retractall(observation(negative(_))),
        write('  Removed negated observations.'), nl,
        fail
    ;   true
    ),
    (   consistency_status(consistent)
    ->  write('Repair successful. KB is now consistent.'), nl
    ;   write('Repair incomplete — manual intervention required.'), nl
    ).

%%------------------------------------------------------------------------------
%% MAIN
%%------------------------------------------------------------------------------
main :-
    write('=== EVO Consistency Verifier ==='), nl,
    consistency_report,
    (   consistency_status(inconsistent)
    ->  write('HALT CONDITION H4: KB is inconsistent.'), nl,
        write('Run repair/0 to attempt automatic repair.'), nl
    ;   write('All clear. Proceed with inference.'), nl
    ),
    nl.

:- main.
