# evo_code_scratch_pad

**EVO CODE Tier persistent workspace.** This repository is the scratch pad for
[EVO](https://github.com/machinelearning2014/artificial_mind)
(Explicit-assumption Verification Orchestrator) CODE-tier tasks.

## Purpose

When EVO executes a CODE-tier workflow (K1 inspect -> K2 ledger -> K3 change ->
K4 verify -> K5 answer), this repo serves as the persistent evidence store.
Every file change, test result, and PR is an auditable artifact — not ephemeral
tool output.

---

## Operational Learnings

### 1. Tier Classification Is Not Optional

Every task entering EVO passes through a Tier 0 triage that assigns one of five
tiers before any tool is used. **Do not re-classify the task.** If the injected
tier contradicts a user-specified tier, state the mismatch and produce
**INCOMPLETE** — never blend workflows or silently replace tiers.

| Tier | Primary Evidence | Tool |
|------|-----------------|------|
| LITE | Tool output (web search / Python) + minimal Prolog assumption ledger | `web_search`, `python_exec` |
| COMPUTE | Python/SymPy computation with verification claims | `python_exec` |
| CODE | Source inspection + reasoning ledger + test/build results | `github_public`, `web_browse`, Prolog |
| REASON | Prolog derivation with `prove/2` proof traces | `prolog_exec` |
| PROVE | Lean 4 verification (`lean4_exit_code(0)`) | `lean4_exec`, `lean4_probe` |

**Key insight:** A task is *solved* only when its tier-specific evidence
requirement is met. Listing facts without derivation is not REASON.
Computation without verification is not COMPUTE. A proof that does not compile
is not PROVE.

### 2. Assumptions Are First-Class Objects (All Tiers)

Every inference that is not strictly entailed by facts **must** be declared as
an assumption with a textual justification. Hidden inference bridges are
forbidden. This applies even in LITE tier (compact assumption ledger) and
CODE tier (assumption predicates for risk hypotheses).

In REASON tier, every conclusion must be evaluated with respect to:
- Which assumptions are active
- Which assumptions are required
- Whether the conclusion survives assumption removal (STEP R4)

**Anti-pattern:** Declaring `assumption(foo, '...')` but never testing what
happens when `foo` is retracted. Always run assumption-drop testing in REASON.

### 3. The Prolog-First Discipline

Prolog is not decorative — it is the reasoning engine. Key rules:

- **`:- dynamic active_assumption/1.`** must be declared at the top of every
  REASON KB. Without this, STEP R4 assumption-dependence testing will fail with
  *"No permission to modify static procedure"*.

- **Use `call/1`, never `clause/2`.** The sandbox restricts `clause/2` on
  private procedures. `call(Goal)` works for both facts and rules without
  source inspection.

- **Every clause ends with a period.** Missing periods are the #1 syntax error
  in Prolog code submitted to `prolog_exec`.

- **`contradictory_pair/2` must be defined even if empty.** The consistency
  harness queries `inconsistent/0`, which depends on `contradictory_pair/2`.
  If it is not defined, the KB fails before any reasoning occurs.

- **Variables are uppercase, atoms are lowercase.** `conclusion(X)` not
  `conclusion(x)`. String arguments use single quotes.

### 4. CODE Tier: Evidence-First, Prolog-Second

CODE is REASON specialized for code, but evidence acquisition is the first
**and** primary phase. Do not force Prolog before inspecting source files.
The workflow is:

1. **K1 Inspect:** Read source, config, repo metadata, docs, commits.
   Concrete observations tied to file paths and tool outputs.
2. **K2 Ledger:** Convert evidence into structured ledger entries.
   Use Prolog facts when the task has multiple interacting hypotheses,
   attack paths, invariants, or contradictory evidence.
3. **K3 Change:** Write files to a feature branch.
4. **K4 Verify:** Run tests/builds. For non-Python code, map source into
   Prolog predicates as the primary proxy.
5. **K5 Answer:** Present findings with evidence citations.

**Key insight:** For simple CODE tasks (single file fix, small config change),
a structured Reasoning Ledger in the final answer is sufficient. For complex
CODE tasks (security review, multi-file refactor, dependency analysis), use
`prolog_exec` to formalize code relationships as predicates.

### 5. Lean Proof Workflow: Plan Before Code

The PROVE tier has evolved a strict pre-code planning phase that prevents
wasted iterations:

1. **Batch lemma verification:** Use `batch_mathlib_check` to verify ALL
   intended lemma names in one call. Do not check lemmas individually.
2. **Always `import Mathlib`:** Submodule imports cause *"unknown package"*
   errors because paths change between Mathlib versions. `import Mathlib`
   compiles instantly from the Lake/.olean cache.
3. **Never use Lean 3 names.** `nat.prime_def_lt` -> `Nat.prime_def_lt_two`,
   `even_pow` -> `Even.pow`, etc. Always verify with `mathlib_check` or
   `#check` before use.
4. **Syntax trap — `expected token`:** This is a parser-level error, not a
   semantic one. Check missing colons, unbalanced brackets, malformed theorem
   headers. The most common cause: missing `:` after theorem binders or
   missing `:=` before the proof body.
5. **Set-restricted integral ambiguity:** When Lean reports *"expected ';' or
   line break"* near an integral expression, the cause is almost always
   parser ambiguity between `let...in` and Mathlib's `integrate x in S, ...`
   notation. **Always parenthesize integral expressions in let-bindings.**

### 6. Uniqueness Claims Require Proof

If a solution is claimed to be *unique*, *the only*, or *singular*, the
conclusion `conclusion(unique_solution(X))` requires either:
- `exhaustive_search(all_checked, count(N))`, or
- `completeness_proof(early_stop_preserves_all)`

Without such proof:
- Classify as `candidate_solution(uniqueness_unproven)`
- State *"Found a solution"* not *"Found the only solution"*
- *"Found first"* does not equal *"proved only"*

This applies to tool outputs claiming uniqueness, derivations finding one
solution, and any claim of exhaustiveness without proof.

### 7. Paradox vs. Inconsistency

A paradox is an **assumption-dependent tension**, not a logical inconsistency.
- A paradox exists only if Prolog derives it under explicit assumptions.
- If the paradox disappears when assumptions are disabled, report it as
  **ASSUMPTION-DEPENDENT**.
- Do not conflate a derived tension under specific assumptions with a global
  inconsistency in the KB.

### 8. Tool Selection Priority

Always try `internal_knowledge` first before calling external tools. Only
escalate when internal knowledge cannot supply the required fact (e.g., live
data, exact computation, formal proof, current repository state).

For non-Python code in CODE tier, do not rely on Python as a general proxy.
Its import/library coverage is limited. Use Prolog as the primary proxy by
mapping inspected code into facts and rules.

### 9. Lean-Eval Preflight Is the Final Authority

For Lean-Eval submission workspaces, the ultimate verification is the pinned
GitHub Actions Lean-Eval Preflight workflow. Local structural checks and
unrelated full-repo CI are **not** sufficient for SOLVED status. Use
`solve_lean_eval_problem` for the end-to-end staged workflow, which
coordinates problem setup, candidate writing, and CI verification.

### 10. Common Failure Modes (Check Before Running)

| Failure | Cause | Fix |
|---------|-------|-----|
| Prolog: `permission_private` | Using `clause/2` on restricted predicate | Replace with `call/1` |
| Prolog: `permission_static` | Asserting/retracting non-dynamic predicate | Add `:- dynamic` declaration |
| Prolog: `discontiguous` warning | Predicate clauses separated | Add `:- discontiguous` or regroup |
| Prolog: infinite loop | Recursive rule before base case | Reorder: base case first |
| Prolog: `format/3` arity error | Args not wrapped in list | `format('~w~n', [Val])` not `format('~w~n', Val)` |
| Lean: `unknown identifier` | Wrong lemma name | Verify with `mathlib_check` |
| Lean: `expected token` | Parser/grammar error | Check colons, brackets, `:=` |
| Lean: `expected ';' or line break` | Integral notation in let-binding | Parenthesize integral expression |
| Lean: submodule import fails | `import Mathlib.Data.X` | Use `import Mathlib` only |
| Uniqueness: unproven | Claiming "the only solution" | Add exhaustive search or qualify |

---

## How EVO Uses This Repo

EVO operates in two modes, chosen automatically based on task complexity:

| Mode | When | Mechanism |
|------|------|-----------|
| **inline** | Single-file fixes, small changes | GitHub API writes + CI |
| **codespace** | Multi-file refactors, debugging | gh codespace + terminal |

### Workflow

1. **K1 Inspect:** EVO reads the target repo/issue via github_public
2. **K2 Ledger:** EVO maps code facts into a Prolog KB (for complex tasks)
3. **K3 Change:** EVO writes files to a feature branch (evo/<slug>-<timestamp>)
4. **K4 Verify:** EVO runs tests via CI (inline) or pytest/npm test in a Codespace
5. **K5 Answer:** EVO creates a PR with the verified changes

### Branch convention

evo/<task-slug>-<YYYYMMDD-HHMMSS>

Example: evo/fix-auth-bug-20260608-143022

### CI

The ci.yml workflow is triggered via workflow_dispatch and should detect the
project type and run the appropriate test suite.

### Codespaces

Pre-configured with common dev tools. EVO spins up a Codespace via
gh codespace create, runs tests interactively, and tears down when done.
Defaults to the 2-core machine (free tier: ~660 hrs/month).

### Security

- EVO writes are scoped to branches prefixed with evo/
- Main branch protection prevents direct pushes
- All changes go through PR review
