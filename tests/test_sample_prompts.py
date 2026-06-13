#!/usr/bin/env python3
"""Validate the sample prompts JSONL file."""
import json
from pathlib import Path


def _load_jsonl(path: Path):
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def test_jsonl_valid():
    path = Path(__file__).resolve().parent.parent / "sample_prompts.jsonl"
    if not path.exists():
        path = Path("sample_prompts.jsonl")
    assert path.exists(), f"{path} not found"
    records = _load_jsonl(path)
    assert len(records) >= 10, f"Expected >=10 prompts, got {len(records)}"
    for i, rec in enumerate(records):
        assert "prompt" in rec, f"Record {i} missing 'prompt'"
        assert "difficulty" in rec, f"Record {i} missing 'difficulty'"
        assert rec["difficulty"] in ("easy", "medium", "hard"), \
            f"Record {i} invalid difficulty: {rec['difficulty']}"
        assert isinstance(rec["prompt"], str) and len(rec["prompt"]) > 5
    print(f"  {len(records)} prompts: all valid")


def test_difficulty_distribution():
    path = Path(__file__).resolve().parent.parent / "sample_prompts.jsonl"
    if not path.exists():
        path = Path("sample_prompts.jsonl")
    records = _load_jsonl(path)
    counts = {"easy": 0, "medium": 0, "hard": 0}
    for rec in records:
        counts[rec["difficulty"]] += 1
    print(f"  Difficulty distribution: {counts}")
    assert counts["easy"] >= 1
    assert counts["medium"] >= 1
    assert counts["hard"] >= 1
