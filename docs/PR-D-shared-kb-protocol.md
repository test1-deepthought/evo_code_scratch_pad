# Shared KB Protocol (Pattern D) — Implementation Guide

## What This PR Implements

This PR introduces **Pattern D: Shared Knowledge Base Protocol** — a file-based multi-agent communication system where two agents (Mind + EvoAgent) coordinate through a Prolog-backed shared knowledge base on disk. No server, no IPC, no shared memory needed.

## Architecture

```
+---------------------+     File System      +---------------------+
|     Mind Agent      |     +----------+      |    EvoAgent         |
| (mind_kb_adapter.py) |<---| shared   |--->| (evo_kb_adapter.py) |
| - classify & propose|     |  kb.pl   |     | - claim strategies  |
| - read traces       |     | (Prolog) |     | - write trace turns |
| - write critiques   |     +----------+     | - check critiques   |
| - trigger backtracks|                       | - report completion |
+---------------------+                       +---------------------+
```

## Files Changed

| File | Purpose |
|------|---------|
| `pr1_mind/__init__.py` | Package init |
| `pr1_mind/shared_kb.py` | Core: Prolog-backed KB engine with dynamic predicates |
| `pr1_mind/mind_kb_adapter.py` | Mind agent: classifies problems, proposes strategies, critiques traces |
| `pr1_mind/evo_kb_adapter.py` | EvoAgent adapter: claims strategies, writes traces, checks for critiques |
| `tests/__init__.py` | Tests package init |
| `tests/test_pr1.py` | Main test file: 7 tests covering init, strategy layer, and critic loop |
| `tests/test_shared_kb.py` | pytest-compatible version of the same tests |
| `tests/run_pr1_tests.py` | Standalone test runner (no pytest dependency) |
| `tests/run_tests.py` | Additional standalone test runner |
| `.github/workflows/ci.yml` | CI workflow (workflow_dispatch) running test_pr1.py |

## Prolog Schema

The shared KB uses these dynamic predicates written to a `.pl` file:

| Predicate | Arity | Purpose |
|-----------|-------|---------|
| `propose_strategy` | 4 | Strategy proposal: id, problem, description, priority |
| `active_strategy` | 1 | Currently active strategy id |
| `strategy_result` | 3 | Outcome: id, status (in_progress/succeeded/failed), detail |
| `strategy_log` | 4 | Audit log: id, event, timestamp, detail |
| `trace` | 5 | Trace turn: turn_number, layer, goal, status, detail |
| `critique_gap` | 4 | Critique: strategy_id, gap_description, severity, suggestion |
| `verified` | 2 | Verification record: name, sha256 hash |

## Protocol Lifecycle

```
Mind                    KB File                     EvoAgent
  |                       |                           |
  |-- propose_strategy ->|                           |
  |-- propose_strategy ->|                           |
  |                       |<-- claim_strategy (highest priority) --|
  |                       |-- write trace turns ------------------>|
  |<-- read traces -------|                           |
  |-- write critique ---->|                           |
  |                       |<-- check for critiques ---|
  |                       |<-- report result ---------|
  |<-- read result -------|                           |
```

## Key Design Decisions

### 1. File-based Prolog KB
- **Why:** No server, no IPC, no shared memory. Two agents running independently can coordinate through a single `.pl` file.
- **Trade-off:** Requires file system access; polling-based communication (no push notifications).

### 2. Keyword-based Problem Classification
The Mind agent scans problem text for math keywords ("prove", "find all", "prime", "inequality", "geometry", "polynomial") and generates ranked strategies. Lower priority numbers = higher priority.

### 3. Dynamic Predicate Schema
All predicates are declared `:- dynamic` so facts can be appended incrementally. The KB file is append-only for writes; `retractall` rewrites the file for cleanup.

### 4. Self-Contained Tests
Each test creates a unique tag (`os.urandom(4).hex()`), uses a temp file in `/tmp/`, and cleans up with `try/finally`. No cross-test contamination.

### 5. CI via workflow_dispatch
CI is manually triggered (not on push) so that the test suite runs against the exact branch ref being tested. The `ref: ${{ github.event.ref || github.ref }}` pattern ensures the correct branch is checked out.

## Running the Tests

```bash
# Standalone (recommended)
python3 tests/test_pr1.py

# Or using the explicit runner
python3 tests/run_pr1_tests.py

# Or with pytest (if installed)
pip install pytest
pytest tests/test_shared_kb.py -v
```

## How It Was Tested

The branch `test-pr-1-artificial-mind-20260608-160751` demonstrated the full protocol:

1. **Init KB** — creates header with all dynamic predicates
2. **Propose Strategy** — Mind generates ranked strategies for "Find all primes p such that p^2 + 2 is also prime"
3. **Claim Strategy** — EvoAgent selects highest-priority unclaimed strategy
4. **Execute & Trace** — EvoAgent writes trace turns (REASON layer, COMPUTE layer, PROVE layer)
5. **Check Critique** — EvoAgent reads Mind's critique and handles high-severity gaps
6. **Complete** — EvoAgent reports success or backtracks on failure

The demo problem answer is **p = 3** (since 3\u00b2 + 2 = 11, which is prime).

## Learnings from the Original Test Branch

1. **Namespace conflicts**: The package was renamed from `mind/` to `pr1_mind` to avoid Python sandbox namespace conflicts.
2. **Import paths**: Tests need `sys.path.insert(0, _repo_root)` because Python adds `tests/` to sys.path, not the repo root.
3. **CI ref handling**: `workflow_dispatch` doesn't populate `GITHUB_REF` the same way push events do; the explicit `ref:` parameter is critical.
4. **Test isolation**: Random tags and try/finally cleanup prevent cross-test contamination.
5. **Dual-mode tests**: The test files work both with pytest and standalone — the `if __name__ == '__main__'` pattern makes them self-contained.
