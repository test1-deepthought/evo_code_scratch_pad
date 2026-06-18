#!/usr/bin/env python3
"""Refactored utility: consolidate all math ops."""
from utils.math_ops import factorial, is_palindrome

def main():
    for n in range(10):
        print(f"factorial({n}) = {factorial(n)}")
    print(f"is_palindrome(12321) = {is_palindrome(12321)}")

if __name__ == "__main__":
    main()
