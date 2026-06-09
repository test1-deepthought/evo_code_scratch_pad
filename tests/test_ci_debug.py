#!/usr/bin/env python3
"""Ultra-minimal CI check - prints everything, then tries imports."""
import os, sys

print(f"::debug::Python: {sys.version}")
print(f"::debug::CWD: {os.getcwd()}")
print(f"::debug::Script: {os.path.abspath(__file__)}")
print(f"::debug::Repo root: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")
print(f"::debug::PATH: {sys.path}")

# List dir contents
for d in ['.', 'pr1_mind', 'tests']:
    if os.path.isdir(d):
        print(f"::debug::Contents of {d}: {os.listdir(d)}")
    else:
        print(f"::debug::{d} NOT FOUND (CWD={os.getcwd()})")

# Add to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try import
try:
    from pr1_mind.shared_kb import SharedKB, _esc
    print("::debug::Import shared_kb OK")
    from pr1_mind.mind_kb_adapter import MindKBAdapter
    print("::debug::Import mind_kb_adapter OK")
    from pr1_mind.evo_kb_adapter import EvoKBAdapter
    print("::debug::Import evo_kb_adapter OK")
except Exception as e:
    print(f"::error::IMPORT FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("::notice::All imports passed!")
sys.exit(0)
