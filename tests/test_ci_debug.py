#!/usr/bin/env python3
"""Minimal CI debug script - just test imports and basic operations."""
import os, sys, tempfile, hashlib, time

print(f"Python version: {sys.version}")
print(f"Working dir: {os.getcwd()}")
print(f"Script dir: {os.path.dirname(os.path.abspath(__file__))}")

# Test temp directory
tmpdir = tempfile.gettempdir()
print(f"Temp dir: {tmpdir}")
print(f"Temp dir exists: {os.path.exists(tmpdir)}")
print(f"Temp dir writable: {os.access(tmpdir, os.W_OK)}")

# Test import from pr1_mind
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from pr1_mind.shared_kb import SharedKB, _esc
    print(f"Import shared_kb: OK")
    from pr1_mind.mind_kb_adapter import MindKBAdapter
    print(f"Import mind_kb_adapter: OK")
    from pr1_mind.evo_kb_adapter import EvoKBAdapter
    print(f"Import evo_kb_adapter: OK")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)

# Test basic KB creation
try:
    tag = f"debug_{os.urandom(4).hex()}"
    kb = SharedKB(storage_tag=tag)
    print(f"KB created at: {kb.path}")
    print(f"KB file exists: {os.path.exists(kb.path)}")
    
    # Test propose
    kb.propose_strategy("s1", "Test problem", "Test strategy", priority=3)
    print(f"Strategy proposed")
    
    with open(kb.path) as f:
        content = f.read()
    assert "propose_strategy(s1" in content
    print("KB content verified: propose_strategy present")
    
    # Test trace
    kb.write_trace(1, "TEST", "test_goal", "derived", "test detail")
    print("Trace written")
    
    # Test critique
    kb.write_critique("s1", "test gap", "low", "test suggestion")
    print("Critique written")
    
    # Cleanup
    os.unlink(kb.path)
    print("Cleanup OK")
    
except Exception as e:
    print(f"TEST ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll CI debug tests passed!")
sys.exit(0)
