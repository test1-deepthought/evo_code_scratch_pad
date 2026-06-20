#!/usr/bin/env python3
"""Count tilings of an AxB area into T loops using correct recurrence."""

from functools import lru_cache

@lru_cache(maxsize=None)
def g(A, B, T):
    """Number of guillotine tilings of AxB into T loops."""
    if A < 2 or B < 2:
        return 1 if T == 0 else 0
    if T == 0:
        return 0
    if T == 1:
        return 1 if (A == 2 or B == 2) else 0
    
    total = 0
    if A >= 4 and B >= 4 and T >= 2:
        total += g(A - 2, B - 2, T - 1)
    
    for C in range(2, B - 1):
        Left, Right = C, B - C
        if not ((Left == 2 or Left >= 4) and (Right == 2 or Right >= 4)):
            continue
        for TL in range(1, T):
            total += g(A, Left, TL) * g(A, Right, T - TL)
    
    for R in range(2, A - 1):
        Top, Bot = R, A - R
        if not ((Top == 2 or Top >= 4) and (Bot == 2 or Bot >= 4)):
            continue
        for TT in range(1, T):
            total += g(Top, B, TT) * g(Bot, B, T - TT)
    
    return total

# Test small cases
for A in range(2, 7):
    for B in range(2, 7):
        for T in range(1, 6):
            c = g(A, B, T)
            if c > 0:
                print(f"g({A},{B},{T}) = {c}")

print()
print(f"g(10,10,5) = {g(10,10,5)}")
