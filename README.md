# EVO — Explicit-assumption Verification Orchestrator

> *"I think in Prolog. I prove in Lean. I compute in Python. I verify everything."*

## What EVO Is

EVO is an intelligent reasoning agent whose architecture is built on five unshakable principles:

1. **Prolog-First** — Every inference must be derivable, not just asserted. Facts are predicates. Rules are clauses. Conclusions are queries.
2. **Assumptions Are First-Class Objects** — No inference bridge is hidden. Every assumption is named, justified, and testable. A conclusion is only as strong as its weakest assumption dependency.
3. **Evidence Before Authority** — Answers are grounded in tool execution outputs, not memory. Each tier (LITE, COMPUTE, CODE, REASON, PROVE) has a designated primary evidence mechanism.
4. **Consistency Is Enforced** — A knowledge base that derives `inconsistent/0` must be repaired before any conclusion stands.
5. **Proof Over Prose** — Formal verification (Lean 4) is the sole authority for mathematical proofs. Prolog tracks the plan. Python explores patterns. Lean compiles the truth.

## Architecture

```
                    ┌──────────────────────┐
                    │   Tier-0 Runtime      │
                    │   (Classification)    │
                    └──────┬───────┬────────┘
                           │       │
              ┌────────────┘       └────────────┐
              ↓                                  ↓
     ┌────────────────┐                ┌─────────────────┐
     │  LITE / COMPUTE │                │  CODE / REASON   │
     │  (Tool Direct)  │                │  (Prolog First)  │
     └────────────────┘                └────────┬─────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    │    Prolog KB Engine    │
                                    │  ┌─────────────────┐  │
                                    │  │ Observations     │  │
                                    │  │ Claims           │  │
                                    │  │ Rules            │  │
                                    │  │ Assumptions      │  │
                                    │  │ Constraints      │  │
                                    │  │ Harness          │  │
                                    │  └─────────────────┘  │
                                    └───────────┬───────────┘
                                                │
                         ┌──────────────────────┼──────────────────────┐
                         ↓                      ↓                      ↓
                  ┌────────────┐         ┌────────────┐         ┌────────────┐
                  │  DERIVE    │         │ CONSISTENCY│         │ ASSUMPTION │
                  │  (prove/2) │         │ (inconsistent/0)│     │  TESTING   │
                  └────────────┘         └────────────┘         └────────────┘
                                                │
                                        ┌───────┴───────┐
                                        │   PROVE Tier   │
                                        │  (Lean 4 +    │
                                        │   Mathlib4)   │
                                        └───────────────┘
```

## The Five Tiers

| Tier | Primary Evidence | When Used |
|------|-----------------|-----------|
| LITE | Web search / internal knowledge / compact Prolog ledger | Fact lookup, simple questions |
| COMPUTE | Python/SymPy with verification claims | Numerical/symbolic computation |
| CODE | Source inspection + reasoning ledger | Code review, debugging, security |
| REASON | Prolog derivation (prove/2 with proof traces) | Logical/philosophical reasoning |
| PROVE | Lean 4 verification (lean4_exit_code(0)) | Formal mathematical proofs |

## Core Predicates

- `observation(Fact)` — Ground truth acquired from tools or premises
- `claim(Proposition)` — User-stated claim under analysis
- `assumption(Name, Justification)` — Named inference bridge with textual justification
- `active_assumption(Name)` — Dynamic predicate controlling which assumptions are live
- `prove(Goal, Proof)` — Derives Goal using call/1 and records the proof
- `inconsistent/0` — True when contradictory_pair/2 succeeds
- `conclusion(Answer)` — Derived result of the reasoning process
- `solved(Name, Status)` — Fulfillment status for each spec requirement

## Halt Conditions

EVO halts when:
- Evidence requirements cannot be met (HALT conditions H1–H8)
- The knowledge base is irreparably inconsistent
- A Lean proof still contains `sorry` after the deadline
- The tier's primary evidence mechanism cannot deliver

## License

EVO is a reasoning architecture. Use it. Extend it. Question your assumptions.
