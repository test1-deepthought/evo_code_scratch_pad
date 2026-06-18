#!/usr/bin/env python3
"""Mathematical operations utility."""


def factorial(n: int) -> int:
    """Compute factorial of n recursively."""
    if n < 0:
        raise ValueError("Negative input not allowed")
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def is_palindrome(s: str) -> bool:
    """Check if string is a palindrome (case-insensitive)."""
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]
