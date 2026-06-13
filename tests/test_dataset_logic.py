#!/usr/bin/env python3
"""Test the dataset preparation logic in isolation.

These tests validate the docstring-extraction and JSONL-formatting
logic that prepare_dataset.py implements, without requiring Mathlib4.
"""
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Replicate the core extraction logic from prepare_dataset.py
# (tested in isolation so we don't import the full script with torch deps)
# ---------------------------------------------------------------------------

DOCSTRING_PATTERN = re.compile(
    r"/-{3,}\s*\n(.*?)\n\./-{3,}\s*\n", re.DOTALL
)


def extract_docstring(lean_code: str) -> str | None:
    """Extract the docstring from a Lean theorem block."""
    m = DOCSTRING_PATTERN.search(lean_code)
    if m:
        return m.group(1).strip()
    return None


def strip_signature(line: str) -> str:
    """Strip `:=` or `where` tail from a theorem/lemma signature."""
    # Remove := ... or where ...
    for marker in [" :=", ":=", " where "]:
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
    return line.strip()


def parse_theorem_block(lean_code: str) -> dict | None:
    """Parse a block containing a theorem/lemma + optional docstring."""
    docstring = extract_docstring(lean_code)
    # Find the theorem/lemma line
    lines = lean_code.split("\n")
    sig_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("theorem ") or stripped.startswith("lemma "):
            sig_lines.append(stripped)
    if not sig_lines:
        return None
    signature = strip_signature(sig_lines[0])
    return {
        "prompt": docstring or "",
        "completion": signature,
        "has_docstring": docstring is not None,
    }


def format_jsonl_entry(prompt: str, completion: str) -> str:
    """Format a prompt-completion pair as a JSONL line."""
    return json.dumps({
        "prompt": prompt.strip(),
        "completion": completion.strip(),
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

SAMPLE_LEAN = r'''/--
The sum of two even natural numbers is even.
-/
theorem even_add (ha : Even a) (hb : Even b) : Even (a + b) :=
by
  rcases ha with ⟨k, hk⟩
  rcases hb with ⟨l, hl⟩
  use k + l
  calc
    a + b = 2 * k + 2 * l : by rw [hk, hl]
    _ = 2 * (k + l) : by ring
'''

SAMPLE_LEAN_NO_DOC = '''theorem add_comm (a b : ℕ) : a + b = b + a := by
  induction a with
  | zero => simp
  | succ a ih => simp [add_succ, ih]
'''


def test_extract_docstring():
    ds = extract_docstring(SAMPLE_LEAN)
    assert ds is not None
    assert "sum of two even natural numbers" in ds
    print(f"  Docstring: {ds[:60]}...")


def test_extract_docstring_none():
    ds = extract_docstring(SAMPLE_LEAN_NO_DOC)
    assert ds is None
    print("  No docstring: correctly None")


def test_strip_signature():
    assert strip_signature("theorem foo (x : ℕ) : x = x :=") == "theorem foo (x : ℕ) : x = x"
    assert strip_signature("theorem bar : 1 + 1 = 2 :=") == "theorem bar : 1 + 1 = 2"
    assert strip_signature("lemma baz (h : P) : Q where") == "lemma baz (h : P) : Q"
    print("  Signature stripping: OK")


def test_parse_theorem_block_with_doc():
    result = parse_theorem_block(SAMPLE_LEAN)
    assert result is not None
    assert result["has_docstring"] is True
    assert "even_add" in result["completion"]
    print(f"  Parsed: {result['completion'][:50]}...")


def test_parse_theorem_block_no_doc():
    result = parse_theorem_block(SAMPLE_LEAN_NO_DOC)
    assert result is not None
    assert result["has_docstring"] is False
    assert result["prompt"] == ""
    print(f"  No-doc parsed: {result['completion'][:50]}...")


def test_jsonl_format():
    line = format_jsonl_entry("Sum of evens is even", "theorem even_add ...")
    obj = json.loads(line)
    assert obj["prompt"] == "Sum of evens is even"
    assert obj["completion"] == "theorem even_add ..."
    print("  JSONL formatting: OK")


def test_empty_prompt_handling():
    line = format_jsonl_entry("", "theorem foo : True")
    assert line  # Should produce valid JSONL even with empty prompt
    obj = json.loads(line)
    assert obj["prompt"] == ""
    print("  Empty prompt handling: OK")
