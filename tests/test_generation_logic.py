#!/usr/bin/env python3
"""Test the generation logic (prompt formatting, output cleaning) in isolation.

These tests replicate the core formatting logic from generate.py
without needing torch or a model.
"""
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Replicate core logic from generate.py
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Lean 4 theorem prover working with Mathlib. \
Given a natural language description, generate the corresponding Lean 4 theorem \
statement with its type signature. Output only the Lean code."""

USER_TEMPLATE_SIMPLE = """Write a Lean 4 theorem that: {description}

```lean4
"""


def format_simple_prompt(description: str) -> str:
    return USER_TEMPLATE_SIMPLE.format(description=description)


def clean_output(raw: str) -> str:
    """Extract Lean code from model output (remove markdown fences)."""
    # Remove ```lean4 ... ``` blocks
    pattern = re.compile(r"```lean4\s*\n(.*?)\n```", re.DOTALL)
    m = pattern.search(raw)
    if m:
        return m.group(1).strip()
    # Try plain ``` ... ```
    pattern2 = re.compile(r"```\s*\n(.*?)\n```", re.DOTALL)
    m2 = pattern2.search(raw)
    if m2:
        return m2.group(1).strip()
    # No fences — return as-is (trimmed)
    return raw.strip()


def truncate_to_signature(lean_code: str) -> str:
    """If the model output includes proof, truncate after the signature."""
    lines = lean_code.split("\n")
    sig_lines = []
    for line in lines:
        sig_lines.append(line)
        if line.rstrip().endswith(":=") or ":=" in line:
            break
    return "\n".join(sig_lines).strip()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_format_simple_prompt():
    prompt = format_simple_prompt("The sum of two evens is even")
    assert "sum of two evens" in prompt
    assert "```lean4" in prompt
    print(f"  Prompt template: OK")


def test_clean_output_lean4_fence():
    raw = """Some preamble.
```lean4
theorem even_add (ha : Even a) (hb : Even b) : Even (a + b) :=
```
Postamble."""
    cleaned = clean_output(raw)
    assert cleaned.startswith("theorem even_add")
    assert cleaned.endswith("(a + b) :=")
    print(f"  Lean4 fence cleanup: OK")


def test_clean_output_plain_fence():
    raw = """```
theorem add_comm (a b : ℕ) : a + b = b + a :=
```"""
    cleaned = clean_output(raw)
    assert cleaned.startswith("theorem")
    print(f"  Plain fence cleanup: OK")


def test_clean_output_no_fence():
    raw = "theorem foo (x : ℕ) : x = x :="
    cleaned = clean_output(raw)
    assert cleaned == raw.strip()
    print(f"  No fence: OK")


def test_truncate_to_signature():
    code = """theorem even_add (ha : Even a) (hb : Even b) : Even (a + b) :=
by
  rcases ha with ⟨k, hk⟩
  use k"""
    truncated = truncate_to_signature(code)
    assert truncated == "theorem even_add (ha : Even a) (hb : Even b) : Even (a + b) :="
    # Should end with :=
    assert truncated.endswith(":=")
    print(f"  Truncation: OK")


def test_truncate_no_proof():
    code = "theorem foo : True"
    truncated = truncate_to_signature(code)
    assert truncated == code
    print(f"  No proof to truncate: OK")


def test_truncate_inline_proof():
    code = "theorem trivial : True := by trivial"
    truncated = truncate_to_signature(code)
    assert ":=" in truncated
    assert "trivial" in truncated
    print(f"  Inline proof truncation: OK")
