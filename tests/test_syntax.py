#!/usr/bin/env python3
"""Validate Python syntax of all project scripts."""
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCRIPTS = [
    "configs/lora_config.py",
    "scripts/prepare_dataset.py",
    "scripts/train.py",
    "scripts/generate.py",
]


def test_all_scripts_syntax():
    """Check that every .py file parses without SyntaxError."""
    errors = []
    for rel in SCRIPTS:
        path = PROJECT_ROOT / rel
        if not path.exists():
            # Try alternate location (GitHub Actions checkout)
            alt = Path(rel)
            if alt.exists():
                path = alt
        if not path.exists():
            errors.append(f"MISSING: {rel}")
            continue
        source = path.read_text()
        try:
            ast.parse(source, filename=rel)
        except SyntaxError as e:
            errors.append(f"SYNTAX ERROR in {rel}: {e}")
    assert not errors, "\n".join(errors)


def test_no_bare_excepts():
    """Flag bare `except:` clauses that catch BaseException."""
    for rel in SCRIPTS:
        path = PROJECT_ROOT / rel
        if not path.exists():
            path = Path(rel)
        if not path.exists():
            continue
        source = path.read_text()
        # Simple check: lines with 'except:' (no exception named)
        for i, line in enumerate(source.split("\n"), 1):
            stripped = line.strip()
            if stripped == "except:":
                print(f"  WARNING: {rel}:{i} bare 'except:' clause")
