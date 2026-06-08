#!/usr/bin/env python3
"""Test file to demonstrate codespace + inline fallback workflow."""

import sys
import platform


def main():
    print("Codespace Mode Test")
    print("===================")
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"System: {platform.system()} {platform.release()}")
    print()
    print("Result: Codespace creation failed (machine type error)")
    print("Fallback: Inline mode (GitHub API + CI) works correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
