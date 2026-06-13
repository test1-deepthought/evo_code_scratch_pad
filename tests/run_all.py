#!/usr/bin/env python3
"""Run all test modules and report results."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

test_modules = [
    "test_syntax",
    "test_config",
    "test_sample_prompts",
    "test_dataset_logic",
    "test_generation_logic",
]

# Add repo root to sys.path
sys.path.insert(0, str(HERE.parent))

passed = 0
failed = 0

for mod_name in test_modules:
    mod_path = HERE / f"{mod_name}.py"
    if not mod_path.exists():
        print(f"[SKIP] {mod_name}: file not found")
        continue
    print(f"\n{'='*60}")
    print(f"  {mod_name}")
    print(f"{'='*60}")
    import importlib.util
    spec = importlib.util.spec_from_file_location(mod_name, mod_path)
    if spec is None:
        print(f"  [FAIL] Could not load spec for {mod_name}")
        failed += 1
        continue
    mod = importlib.util.module_from_spec(spec)
    # Find all test_* functions
    import types
    # We'll exec the module manually to capture test functions
    try:
        with open(mod_path) as f:
            code = f.read()
        exec(compile(code, mod_path.name, 'exec'), mod.__dict__)
        test_fns = [name for name in dir(mod) if name.startswith("test_")]
        mod_passed = 0
        mod_failed = 0
        for fn_name in test_fns:
            fn = getattr(mod, fn_name)
            if not callable(fn):
                continue
            try:
                fn()
                mod_passed += 1
            except Exception as e:
                print(f"  [FAIL] {fn_name}: {e}")
                mod_failed += 1
        print(f"  Results: {mod_passed} passed, {mod_failed} failed")
        passed += mod_passed
        failed += mod_failed
    except Exception as e:
        print(f"  [FAIL] Could not execute {mod_name}: {e}")
        failed += 1

print(f"\n{'='*60}")
print(f"  TOTAL: {passed} passed, {failed} failed")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
