# evo_code_scratch_pad

**EVO CODE Tier persistent workspace.** This repository is the scratch pad for
[EVO](https://github.com/machinelearning2014/artificial_mind)
(Explicit-assumption Verification Orchestrator) CODE-tier tasks.

## Purpose

When EVO executes a CODE-tier workflow (K1 inspect -> K2 ledger -> K3 change ->
K4 verify -> K5 answer), this repo serves as the persistent evidence store.
Every file change, test result, and PR is an auditable artifact -- not ephemeral
tool output.

## How EVO Uses This Repo

The persistent scratch-pad workflow and the server sandbox are deliberately
separate:

| Mode | When | Mechanism |
|------|------|-----------|
| **scratch pad** | Explicit persistent publication | GitHub API writes + CI |
| **server sandbox** | Ephemeral CODE verification | User-authorized Codespace + nested Docker |

### Workflow

1. **K1 Inspect:** EVO reads the target repo/issue via github_public
2. **K2 Ledger:** EVO maps code facts into a Prolog KB
3. **K3 Change:** EVO writes files to a feature branch (evo/<slug>-<timestamp>)
4. **K4 Verify:** EVO runs the scratch branch through GitHub Actions CI
5. **K5 Answer:** EVO creates a PR with the verified changes

### Branch convention

evo/<task-slug>-<YYYYMMDD-HHMMSS>

Example: evo/fix-auth-bug-20260608-143022

## CI

The ci.yml workflow is triggered via workflow_dispatch and should detect the
project type and run the appropriate test suite.

## Codespaces

This repository is also the clean template for EVO's separately authorized
Codespaces sandbox. Its dev-container enables the official Docker-in-Docker and
SSH features. EVO copies the isolated Railway session workspace into a fresh
user-authorized Codespace, runs the requested command in a hardened nested
container, and deletes the Codespace afterward.

The nested container uses `--network none` unless network access was explicitly
authorized. The persistent `code_scratch_pad` tool does not create Codespaces
and never reuses EVO's server-owned GitHub credential for sandbox execution.

## Security

- EVO writes are scoped to branches prefixed with evo/
- Main branch protection prevents direct pushes
- All changes go through PR review

---

# Historical Operational Learnings: Running Tests & Triggering CI

This section captures hands-on experience accumulated across **22 CI workflow runs, 8+
feature branches, and 4 open PRs** in this repository.

## 1. CI Must Be Triggered Explicitly

The CI workflow (`.github/workflows/ci.yml`) is configured as **`workflow_dispatch` only**
--- it does NOT trigger on push, pull_request, or any other event. Every CI run must be
initiated explicitly.

**How EVO dispatches CI (inline mode):**

After writing files via the GitHub API, `code_scratch_pad stage=test` calls:

```
POST /repos/test1-deepthought/evo_code_scratch_pad/actions/workflows/ci.yml/dispatches
{"ref": "evo/<branch-name>"}
```

Then polls `GET /repos/.../actions/runs?branch=<branch>&event=workflow_dispatch` up to
300 seconds until the run completes.

**Manual dispatch via GitHub UI:**
1. Navigate to https://github.com/test1-deepthought/evo_code_scratch_pad/actions
2. Select the "CI" workflow
3. Click "Run workflow" -> select branch -> "Run workflow"

**Manual dispatch via curl:**
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/test1-deepthought/evo_code_scratch_pad/actions/workflows/ci.yml/dispatches \
  -d '{"ref":"evo/fix-ci-test-pr1-20260609-011420"}'
```

## 2. Main Branch CI Is a Trap

The current `main` branch CI runs `python3 tests/test_pr1.py`, but that file only exists
on the `evo/fix-ci-test-pr1-20260609-011420` feature branch --- it has **not** been merged
to main. Dispatching CI on **main** will fail with a file-not-found error.

**The fix branch** (`evo/fix-ci-test-pr1`) uses a more robust CI with graceful fallbacks:
1. Tries `pytest tests/ -v` (if pytest is installed)
2. Falls back to `python3 tests/run_pr1_tests.py`
3. Falls back to `python3 tests/test_pr1.py`
4. Finally prints "No test file found" if nothing exists

**Lesson:** Until the feature branch is merged, dispatch CI only on branches that have
the `tests/` directory. Once merged, update the main CI to include the fallback chain.

## 3. Historical Inline/Codespace Comparison

The comparison below describes the retired scratch-pad Codespace mode. Current
Codespaces execution uses the separate user-authorized nested-container sandbox
described above.

| Aspect | Inline Mode | Codespace Mode |
|--------|-------------|----------------|
| Mechanism | GitHub API writes + workflow_dispatch CI | gh codespace create + terminal |
| Test feedback | CI logs (polled) | Interactive terminal |
| Reliability | **Proven across 22/22 runs** | Intermittent `gh` CLI issues (PR #5) |
| Speed | ~10-15s total | 30-60s spin-up + teardown |
| Cost | Free (GitHub Actions) | Free tier (~660 hrs/month) |

The codespace mode had `gh` CLI `--json` flag compatibility issues documented in PR #5.
When codespace creation fails, the tool falls back to inline mode --- a critical safety net.

## 4. Import Paths Are Tricky for Nested Modules

The `pr1_mind/` module lives at the repo root, but tests live in `tests/`. Python's
default `sys.path` behavior means `from pr1_mind.shared_kb import ...` fails with
`ModuleNotFoundError` when running `python3 tests/test_pr1.py`.

**The fix** --- add the repo root to `sys.path` at the top of the test file:

```python
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
```

This pattern is proven and should be replicated in any new test file under `tests/`.

## 5. Both pytest and Standalone Work

The test file (`tests/test_pr1.py`) is designed to work **both** with pytest (for nice
fixture management and detailed reporting) and standalone (for environments where pytest
isn't installed):

- **With pytest:** `pip install pytest && pytest tests/test_pr1.py -v`
- **Standalone:** `python3 tests/test_pr1.py`

The CI's fallback chain (see Learning #2) handles both paths gracefully.

## 6. CI Run History

| Statistic | Value |
|-----------|-------|
| Total workflow runs | 22 |
| Status | All 22 completed successfully |
| Branches tested | `evo/fix-ci-test-pr1-20260609-011420`, `evo/test-code-tier-scratch-pad-*`, and others |
| CI runtime (typical) | ~10-15 seconds |
| Open PRs | 4 (#3, #4, #5, #6) |

## 7. Test Pattern: Self-Contained with Fixtures

Each test creates its own `SharedKB` with a random tag (`uuid.uuid4().hex`) to prevent
cross-test contamination, and cleans up with `_cleanup(kb)` which deletes the temp `.pl`
file. The `Fixtures` class provides static methods usable by both pytest and standalone
modes.

**Key pattern to follow for new tests:**
```python
class Fixtures:
    @staticmethod
    def shared_kb():
        tag = uuid.uuid4().hex
        kb = SharedKB(tag=tag)
        kb.clean()
        return kb

    @staticmethod
    def cleanup(kb):
        kb.clean()
```

---

*Last updated: 2026-06-09 | 22 CI runs | 4 open PRs*
