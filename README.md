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

EVO operates in two modes, chosen automatically based on task complexity:

| Mode | When | Mechanism |
|------|------|-----------|
| **inline** | Single-file fixes, small changes | GitHub API writes + CI |
| **codespace** | Multi-file refactors, debugging | gh codespace + terminal |

### Workflow

1. **K1 Inspect:** EVO reads the target repo/issue via github_public
2. **K2 Ledger:** EVO maps code facts into a Prolog KB
3. **K3 Change:** EVO writes files to a feature branch (evo/<slug>-<timestamp>)
4. **K4 Verify:** EVO runs tests via CI (inline) or pytest/npm test in a Codespace
5. **K5 Answer:** EVO creates a PR with the verified changes

### Branch convention

evo/<task-slug>-<YYYYMMDD-HHMMSS>

Example: evo/fix-auth-bug-20260608-143022

## CI

The ci.yml workflow is triggered via workflow_dispatch and should detect the
project type and run the appropriate test suite.

## Codespaces

Pre-configured with common dev tools. EVO spins up a Codespace via
gh codespace create, runs tests interactively, and tears down when done.
Defaults to the 2-core machine (free tier: ~660 hrs/month).

## Security

- EVO writes are scoped to branches prefixed with evo/
- Main branch protection prevents direct pushes
- All changes go through PR review
