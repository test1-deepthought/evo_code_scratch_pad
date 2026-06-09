#!/usr/bin/env python3
"""CI debug - test KB creation."""
import os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pr1_mind.shared_kb import SharedKB, _esc

# Test 1: gettempdir
tmpdir = tempfile.gettempdir()
print(f"tmpdir={tmpdir}")
print(f"exists={os.path.exists(tmpdir)}")
print(f"writable={os.access(tmpdir, os.W_OK)}")

# Test 2: Create KB
tag = f"debug_{os.urandom(4).hex()}"
kb = SharedKB(storage_tag=tag)
print(f"kb.path={kb.path}")
print(f"kb exists={os.path.exists(kb.path)}")

# Test 3: Content
with open(kb.path) as f:
    c = f.read()
print(f"content length={len(c)}")
print("propose_strategy/4" in c)
print("next_strategy(" in c)

# Test 4: Propose
kb.propose_strategy("s1", "test", "desc", 3)
with open(kb.path) as f:
    c = f.read()
print(f"after propose: 'propose_strategy(s1' in content={('propose_strategy(s1' in c)}")

# Cleanup
os.unlink(kb.path)
print("CLEANUP OK")

# Test 5: Make tag with f-string
tag2 = f"test_{os.urandom(4).hex()}"
print(f"tag2={tag2}")

print("\nALL OK")
sys.exit(0)
