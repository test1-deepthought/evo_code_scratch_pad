#!/usr/bin/env python3
"""
Prepare a fine-tuning dataset of Lean4 Mathlib theorems.

Extracts theorem/lemma declarations with their docstrings from Mathlib4 source,
formats them as (prompt, completion) pairs for supervised fine-tuning.

Usage:
    python scripts/prepare_dataset.py \
        --mathlib_path /path/to/mathlib4 \
        --output_dir ./data \
        --max_examples 50000 \
        --val_split 0.05 \
        --test_split 0.05
"""
import argparse
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm


# ---------------------------------------------------------------------------
# Regex patterns for Lean4 theorem/lemma declarations
# ---------------------------------------------------------------------------

# A theorem or lemma header, capturing optional docstring and the full declaration.
# Matches patterns like:
#   /-- Docstring -/
#   theorem name (binders) : type :=
#   lemma name (binders) : type :=
#   theorem name (binders) : type where
#   lemma name (binders) : type where
#
# Docstrings can be multi-line: /-- ... -/
# We capture: (docstring_or_none, full_header)

RE_DOCSTRING = r'\/-\s*(.*?)\s*-\/'  # non-greedy, includes newlines via re.DOTALL

# Header patterns for theorem-like declarations
THEOREM_KW = r'(?:theorem|lemma|deftheorem|example)\s+'
# Name (identifier, possibly with `.` for namespace)
NAME_PART = r'[a-zA-Z_][a-zA-Z0-9_\u2032\']*'
QUALIFIED_NAME = rf'{NAME_PART}(?:\s*\.\s*{NAME_PART})*'
# Binders (anything up to : or := or :where or :where)
BINDERS = r'(?:[^:=\n]|\([^)]*\)|\{[^}]*\}|\[[^\]]*\])*?'
# Header pattern (excluding docstring)
HEADER_PATTERN = re.compile(
    rf'({THEOREM_KW}{QUALIFIED_NAME}\s*{BINDERS}\s*:\s*[^:=]*(?::=' +
    r'|\bwhere\b))',
    re.DOTALL,
)

# Combined: docstring + header
FULL_PATTERN = re.compile(
    rf'(?:{RE_DOCSTRING}\s*)?{THEOREM_KW}{QUALIFIED_NAME}\s*{BINDERS}\s*:\s*[^:=]*(?:=|\bwhere\b)',
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Lean 4 theorem prover working with Mathlib. \
Given a natural language description, generate the corresponding Lean 4 theorem \
statement with its type signature. Output only the Lean code."""

PROMPT_TEMPLATE = """<|system|>
{SYSTEM_PROMPT}
<|user|>
Write a Lean 4 theorem for: {description}
<|assistant|>
```lean4
{theorem_code}
```"""

PROMPT_TEMPLATE_SIMPLE = """Write a Lean 4 theorem that: {description}

```lean4
{theorem_code}
```"""


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def find_lean_files(mathlib_path: Path) -> List[Path]:
    """Recursively find all .lean files under mathlib_path, excluding tests."""
    lean_files = []
    for root, dirs, files in os.walk(mathlib_path):
        # Skip test directories and cache
        dirs[:] = [d for d in dirs if d not in ('test', 'tests', '.cache', 'build')]
        for f in files:
            if f.endswith('.lean') and not f.endswith('_test.lean'):
                lean_files.append(Path(root) / f)
    return lean_files


def extract_theorems_from_file(filepath: Path) -> List[Dict[str, str]]:
    """
    Extract (docstring, theorem_header) pairs from a single .lean file.
    Returns list of dicts with keys: docstring, header, full_decl, source_file
    """
    try:
        content = filepath.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        return []

    results = []
    # Find all matches with optional preceding docstring
    for match in FULL_PATTERN.finditer(content):
        full_match = match.group(0)
        header = full_match.strip()

        # Extract docstring if present (captured as group 1)
        doc_match = re.match(rf'\/-\s*(.*?)\s*-\/\s*({THEOREM_KW})', full_match, re.DOTALL)
        docstring = ""
        if doc_match:
            docstring = doc_match.group(1).strip()
            # Normalize whitespace
            docstring = re.sub(r'\s+', ' ', docstring)

        # Clean up the header
        header = header.replace('\n', ' ').strip()
        # Collapse multiple spaces
        header = re.sub(r'\s+', ' ', header)

        # Compute a relative source path
        rel_path = str(filepath)

        results.append({
            'docstring': docstring,
            'header': header,
            'source_file': rel_path,
        })

    return results


def extract_signature(header: str) -> str:
    """
    Given a theorem header like:
      theorem foo (x : Nat) : x + 0 = x :=
    Return just the type signature:
      theorem foo (x : Nat) : x + 0 = x
    (dropping trailing `:=` or `where`)
    """
    sig = header.rstrip()
    if sig.endswith(':='):
        sig = sig[:-2].strip()
    elif sig.endswith('where'):
        sig = sig[:-5].strip()
    elif sig.endswith(':='):
        sig = sig[:-2].strip()
    elif sig.endswith('where'):
        sig = sig[:-5].strip()
    # Also handle := with trailing spaces
    sig = re.sub(r'\s*:=\s*$', '', sig)
    sig = re.sub(r'\s*where\s*$', '', sig)
    return sig.strip()


def format_example(
    docstring: str,
    header: str,
    prompt_version: str = 'simple',
) -> Dict[str, str]:
    """
    Format a (docstring, theorem header) pair into a training example.
    The prompt is the docstring (or a derived description).
    The completion is the theorem signature.
    """
    description = docstring if docstring else extract_signature(header)

    if prompt_version == 'full':
        prompt = PROMPT_TEMPLATE.format(
            SYSTEM_PROMPT=SYSTEM_PROMPT,
            description=description,
            theorem_code=header,
        )
        # The completion is the assistant response
        completion = f"```lean4\n{header}\n```"
    else:
        # Simple format: just the prompt text + completion
        prompt = PROMPT_TEMPLATE_SIMPLE.format(
            description=description,
            theorem_code='',  # completion will be appended
        ).rstrip()
        # Remove trailing ``` from prompt since completion adds it
        prompt = prompt.rstrip('`').rstrip()
        completion = f"```lean4\n{header}\n```"

    return {
        'prompt': prompt,
        'completion': completion,
        'text': prompt + '\n' + completion,
        'description': description,
        'signature': extract_signature(header),
        'source': header,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_dataset(
    mathlib_path: Path,
    output_dir: Path,
    max_examples: int = 50000,
    val_split: float = 0.05,
    test_split: float = 0.05,
    prompt_version: str = 'simple',
    min_description_len: int = 10,
    seed: int = 42,
):
    """Main dataset construction pipeline."""
    random.seed(seed)

    print(f"[*] Searching for .lean files in {mathlib_path} ...")
    lean_files = find_lean_files(mathlib_path)
    print(f"[*] Found {len(lean_files)} .lean files.")

    # Extract theorems
    all_theorems: List[Dict] = []
    for fpath in tqdm(lean_files, desc="Extracting theorems"):
        theorems = extract_theorems_from_file(fpath)
        all_theorems.extend(theorems)

    print(f"[*] Extracted {len(all_theorems)} theorem declarations total.")

    # Filter: require a docstring (description) of minimum length
    filtered = [
        t for t in all_theorems
        if len(t['docstring']) >= min_description_len
    ]
    print(f"[*] After filtering (min_description_len={min_description_len}): {len(filtered)} examples")

    # Limit
    if max_examples and len(filtered) > max_examples:
        filtered = random.sample(filtered, max_examples)
        print(f"[*] Sampled down to {max_examples} examples.")

    # Shuffle
    random.shuffle(filtered)

    # Format into training examples
    examples = [
        format_example(t['docstring'], t['header'], prompt_version)
        for t in tqdm(filtered, desc="Formatting examples")
    ]

    # Split
    n = len(examples)
    n_val = int(n * val_split)
    n_test = int(n * test_split)
    n_train = n - n_val - n_test

    train = examples[:n_train]
    val = examples[n_train:n_train + n_val]
    test = examples[n_train + n_val:]

    print(f"[*] Split: {len(train)} train / {len(val)} val / {len(test)} test")

    # Write
    output_dir.mkdir(parents=True, exist_ok=True)

    splits = {
        'train': train,
        'val': val,
        'test': test,
    }
    for split_name, split_data in splits.items():
        fpath = output_dir / f'mathlib4_theorems_{split_name}.jsonl'
        with open(fpath, 'w', encoding='utf-8') as f:
            for ex in split_data:
                f.write(json.dumps(ex, ensure_ascii=False) + '\n')
        print(f"    Wrote {len(split_data)} examples to {fpath}")

    # Write a stats file
    stats = {
        'total_raw_theorems': len(all_theorems),
        'total_filtered': len(filtered),
        'total_examples': len(examples),
        'train': len(train),
        'val': len(val),
        'test': len(test),
        'prompt_version': prompt_version,
        'min_description_len': min_description_len,
        'source': str(mathlib_path),
    }
    stats_path = output_dir / 'dataset_stats.json'
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"[*] Stats written to {stats_path}")

    # Print a few examples
    print("\n[*] Sample examples:")
    for i, ex in enumerate(examples[:3]):
        print(f"\n--- Example {i+1} ---")
        print(f"Prompt: {ex['prompt'][:200]}...")
        print(f"Completion: {ex['completion'][:200]}...")

    return examples


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Prepare Lean4 theorem dataset for fine-tuning.',
    )
    parser.add_argument(
        '--mathlib_path',
        type=str,
        required=True,
        help='Path to mathlib4 repository clone.',
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        default='./data',
        help='Output directory for dataset files.',
    )
    parser.add_argument(
        '--max_examples',
        type=int,
        default=50000,
        help='Maximum number of examples to include (sampled randomly).',
    )
    parser.add_argument(
        '--val_split',
        type=float,
        default=0.05,
        help='Fraction of examples for validation.',
    )
    parser.add_argument(
        '--test_split',
        type=float,
        default=0.05,
        help='Fraction of examples for test.',
    )
    parser.add_argument(
        '--prompt_version',
        type=str,
        default='simple',
        choices=['simple', 'full'],
        help='Prompt template version.',
    )
    parser.add_argument(
        '--min_description_len',
        type=int,
        default=10,
        help='Minimum docstring length to include.',
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed.',
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    build_dataset(
        mathlib_path=Path(args.mathlib_path),
        output_dir=Path(args.output_dir),
        max_examples=args.max_examples,
        val_split=args.val_split,
        test_split=args.test_split,
        prompt_version=args.prompt_version,
        min_description_len=args.min_description_len,
        seed=args.seed,
    )


if __name__ == '__main__':
    main()
