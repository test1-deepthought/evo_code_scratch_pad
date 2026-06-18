#!/usr/bin/env python3
"""A simple hello-world test for the CODE tier scratch pad."""


def greet(name: str) -> str:
    """Return a greeting for the given name."""
    return f"Hello, {name}! Welcome to the CODE tier scratch pad."


def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def main() -> None:
    """Run the demo."""
    print(greet("EVO Agent"))
    print(f"2 + 3 = {add(2, 3)}")
    print(f"10 + (-5) = {add(10, -5)}")


if __name__ == "__main__":
    main()
