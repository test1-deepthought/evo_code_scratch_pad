%% ============================================================
%% ARC-AGI-3 Prolog Reasoning Rules v4
%% Adaptive maze reasoning for PrologReasoning6.
%% Key improvements over v3:
%%   - Handles PLAYER_UNKNOWN gracefully
%%   - Improved BFS with visited-set optimization
%%   - Lower priority for portal-seeking (no modifier needed)
%% ============================================================

:- dynamic max_tile_x/1.
:- dynamic max_tile_y/1.
:- dynamic tile_size/1.
:- dynamic wall/2.
:- dynamic player/2.
:- dynamic explored/2.
:- dynamic portal/3.
:- dynamic modifier/3.
:- dynamic had_modifier/1.
:- dynamic step_pickup/2.
:- dynamic level/1.
:- dynamic action_taken/3.
:- dynamic known_floor/1.

action(up, 1).
action(down, 2).
action(left, 3).
action(right, 4).
action(interact, 5).
action(click, 6).

valid_move(TX, TY, up, TX, NY) :-
    NY is TY - 1, NY >= 0, max_tile_y(H), NY =< H.
valid_move(TX, TY, down, TX, NY) :-
    NY is TY + 1, max_tile_y(H), NY =< H.
valid_move(TX, TY, left, NX, TY) :-
    NX is TX - 1, NX >= 0, max_tile_x(W), NX =< W.
valid_move(TX, TY, right, NX, TY) :-
    NX is TX + 1, max_tile_x(W), NX =< W.

can_move(TX, TY, Dir, NX, NY) :-
    valid_move(TX, TY, Dir, NX, NY),
    \+ wall(NX, NY).

action_for(up, 1).
action_for(down, 2).
action_for(left, 3).
action_for(right, 4).

adjacent(TX, TY, NX, NY) :-
    (NX is TX + 1, NY is TY ; NX is TX - 1, NY is TY
    ; NX is TX, NY is TY + 1 ; NX is TX, NY is TY - 1).

bfs_path(SX, SY, EX, EY, Path) :-
    bfs_queue([(SX, SY, [(SX,SY)])], EX, EY, [SX-SY], Path).

bfs_queue([(EX, EY, Path)|_], EX, EY, _, Path).

bfs_queue([(CX, CY, CurrPath)|Rest], EX, EY, Visited, Result) :-
    findall((NX, NY, NewPath), (
        valid_move(CX, CY, _, NX, NY),
        \+ member(NX-NY, Visited),
        \+ wall(NX, NY),
        append(CurrPath, [(NX,NY)], NewPath)
    ), Neighbors),
    append(Rest, Neighbors, NewQueue),
    bfs_queue(NewQueue, EX, EY, [CX-CY|Visited], Result).

bfs_path(_, _, _, _, []).

nearest_unexplored(PX, PY, TX, TY, Dist) :-
    findall(D-Tx-Ty, (
        max_tile_x(W), max_tile_y(H),
        between(0, W, Tx), between(0, H, Ty),
        \+ wall(Tx, Ty),
        \+ explored(Tx, Ty),
        D is abs(Tx - PX) + abs(Ty - PY)
    ), Candidates),
    Candidates \= [],
    sort(Candidates, [(D-TX-TY)|_]),
    Dist = D.

nearest_portal(PX, PY, TX, TY, Dist) :-
    findall(D-Tx-Ty, (
        portal(Tx, Ty, _),
        D is abs(Tx - PX) + abs(Ty - PY)
    ), Candidates),
    Candidates \= [],
    sort(Candidates, [(D-TX-TY)|_]),
    Dist = D.

nearest_explored(PX, PY, TX, TY, Dist) :-
    findall(D-Tx-Ty, (
        explored(Tx, Ty),
        (Tx \= PX ; Ty \= PY),
        D is abs(Tx - PX) + abs(Ty - PY)
    ), Candidates),
    Candidates \= [],
    sort(Candidates, [(D-TX-TY)|_]),
    Dist = D.

have_modifier :- had_modifier(_), !.

first_step_dir(PX, PY, NX, NY, DirNum) :-
    (NX > PX -> action_for(right, DirNum)
    ; NX < PX -> action_for(left, DirNum)
    ; NY > PY -> action_for(down, DirNum)
    ; NY < PY -> action_for(up, DirNum)).

next_action(PX, PY, 5) :- portal(PX, PY, _).

next_action(PX, PY, 5) :-
    have_modifier,
    portal(NX, NY, _),
    adjacent(PX, PY, NX, NY).

next_action(PX, PY, DirNum) :-
    have_modifier,
    nearest_portal(PX, PY, TX, TY, _),
    bfs_path(PX, PY, TX, TY, Path),
    Path \= [],
    Path = [(PX,PY), (NX,NY)|_],
    first_step_dir(PX, PY, NX, NY, DirNum).

next_action(PX, PY, 5) :-
    modifier(NX, NY, _),
    adjacent(PX, PY, NX, NY).

next_action(PX, PY, DirNum) :-
    nearest_unexplored(PX, PY, TX, TY, _),
    bfs_path(PX, PY, TX, TY, Path),
    Path \= [],
    Path = [(PX,PY), (NX,NY)|_],
    first_step_dir(PX, PY, NX, NY, DirNum).

next_action(PX, PY, DirNum) :-
    nearest_portal(PX, PY, TX, TY, _),
    bfs_path(PX, PY, TX, TY, Path),
    Path \= [],
    Path = [(PX,PY), (NX,NY)|_],
    first_step_dir(PX, PY, NX, NY, DirNum).

next_action(PX, PY, DirNum) :-
    nearest_explored(PX, PY, TX, TY, _),
    bfs_path(PX, PY, TX, TY, Path),
    Path \= [],
    Path = [(PX,PY), (NX,NY)|_],
    first_step_dir(PX, PY, NX, NY, DirNum).

next_action(PX, PY, DirNum) :-
    can_move(PX, PY, Dir, NX, NY),
    action_for(Dir, DirNum).

next_action(_, _, 1).

main :-
    (player(PX, PY) ->
        (next_action(PX, PY, DirNum) ->
            format('NEXT_ACTION:~d~n', [DirNum])
        ;   format('NEXT_ACTION:~d~n', [1]))
    ;   format('PLAYER_UNKNOWN~n', [])),
    halt.
