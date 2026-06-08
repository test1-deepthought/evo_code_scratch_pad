#!/usr/bin/env python3
"""Tests for utility modules."""

from utils.math_ops import factorial, is_palindrome


def test_factorial():
    assert factorial(0) == 1
    assert factorial(1) == 1
    assert factorial(5) == 120
    assert factorial(10) == 3628800


def test_factorial_negative():
    try:
        factorial(-1)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_is_palindrome():
    assert is_palindrome("racecar") == True
    assert is_palindrome("A man a plan a canal Panama") == True
    assert is_palindrome("hello") == False
    assert is_palindrome("") == True


def test_is_palindrome_case_sensitivity():
    assert is_palindrome("RaceCar") == True
    assert is_palindrome("Noon") == True
    assert is_palindrome("EVO") == False


if __name__ == "__main__":
    test_factorial()
    test_factorial_negative()
    test_is_palindrome()
    test_is_palindrome_case_sensitivity()
    print("All utility tests passed!")
