"""
pro_symbolic — Asynchronous Symbolic Logic Reasoner

An async tool that uses the DeepSeek-V4-Pro frontier reasoning model
(max reasoning effort, 50000 max tokens) to perform iterative,
symbolic-logic-driven analysis with self-evaluation and refinement.

Design:
  - Single-turn with N refinement iterations (configurable, default 3)
  - Each iteration evaluates the previous response against 7 symbolic-logic
    criteria, then produces an adversarial review and a refined response.
  - Early-stops when the model self-declares [COMPLETE].
  - Repeating-text detection as safety cutoff.
  - Pure reasoning engine: no tool-calling during generation.

API: OpenAI-compatible chat completions at https://api.deepseek.com
     Uses the "deepseek-reasoner" model which supports the `reasoning_content`
     field for chain-of-thought traces.

Author: DeepThought Engineering
"""

import asyncio
import json
import os
import uuid
from typing import Optional

from openai import AsyncOpenAI

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "deepseek-reasoner"           # v4-pro with reasoning tokens
DEFAULT_MAX_TOKENS = 50000                     # matches frontier_reasoner
DEFAULT_TEMPERATURE = 0.5
DEFAULT_REFINEMENT_ITERATIONS = 3
MAX_REFINEMENT_ITERATIONS = 200

API_KEY_ENV = "DEEPSEEK_API_KEY"
API_BASE_URL = "https://api.deepseek.com"

DEFAULT_REPEATING_WINDOW = 20                  # word window for detection

# ---------------------------------------------------------------------------
# System message — symbolic logic reasoning
# ---------------------------------------------------------------------------

SYSTEM_MESSAGE = (
    "You are an advanced AI that uses rigorous symbolic logic reasoning "
    "to solve problems, then translates your findings into clear natural language.\n"
    "Your reasoning process should follow these steps:\n"
    "1. SYMBOLIC ANALYSIS: Break down the problem into logical components, "
    "identify premises, and establish formal relationships\n"
    "2. LOGICAL INFERENCE: Apply deductive reasoning, logical operators, "
    "and systematic analysis\n"
    "3. NATURAL LANGUAGE SYNTHESIS: Translate your symbolic reasoning into "
    "clear, accessible explanations\n"
    "Always structure your response as:\n"
    "- First, conduct thorough symbolic logic analysis\n"
    "- Then, provide your final answer in natural, conversational language "
    "that explains both your reasoning and conclusions"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_n_words(text: str, n: int = DEFAULT_REPEATING_WINDOW) -> str:
    """Return the last *n* words of *text*."""
    words = text.split()
    return " ".join(words[-n:]) if len(words) >= n else text


def _is_repeating(text: str, window: int = DEFAULT_REPEATING_WINDOW) -> bool:
    """Detect whether the last *window* words duplicate an earlier span."""
    words = text.split()
    if len(words) < window * 2:
        return False
    tail = " ".join(words[-window:])
    return " ".join(words[:-window]).find(tail) != -1


def _build_iteration_prompt(
    prompt: str,
    iteration_index: int,
    previous_thoughts: str = "",
    previous_answer: str = "",
) -> str:
    """Build the per-iteration message body.

    Iteration 0 is the initial symbolic-logic analysis.
    Later iterations are evaluation + refinement rounds.
    """
    uid = uuid.uuid4()

    if iteration_index == 0:
        return (
            f"UUID: {uid}\n"
            "Using symbolic logic reasoning, analyze and respond to the "
            "following query:\n\n"
            f"Query: {prompt}\n\n"
            "Process:\n"
            "1. SYMBOLIC ANALYSIS: Break down the query into logical "
            "components. Identify:\n"
            "   - Key premises (P1, P2, P3...)\n"
            "   - Logical relationships (->, AND, OR, NOT, <->)\n"
            "   - Variables and constants\n"
            "   - Quantifiers (forall, exists) if applicable\n"
            "2. LOGICAL INFERENCE: Apply systematic reasoning:\n"
            "   - Use deductive reasoning rules (modus ponens, modus "
            "tollens, etc.)\n"
            "   - Apply logical operators methodically\n"
            "   - Check for consistency and completeness\n"
            "   - Derive conclusions step by step\n"
            "3. NATURAL LANGUAGE RESPONSE: Translate your symbolic "
            "reasoning into a clear, comprehensive answer that:\n"
            "   - Explains your logical process in accessible terms\n"
            "   - Provides concrete examples where helpful\n"
            "   - Addresses all aspects of the original query\n"
            "   - Uses conversational, natural language\n\n"
            "Your response should demonstrate the symbolic logic foundation "
            "while being completely readable and helpful to someone without "
            "formal logic training."
        )

    # --- Evaluation + refinement iterations (i >= 1) -------------------
    return (
        f"UUID: {uid}\n"
        "Evaluate the completeness and logical rigor of the previous "
        "response using symbolic logic principles.\n\n"
        f"Previous Thoughts: {previous_thoughts}\n"
        f"Previous Response: {previous_answer}\n"
        f"Original Query: {prompt}\n\n"
        "EVALUATION CRITERIA:\n"
        "1. LOGICAL COMPLETENESS: Are all aspects of the query addressed "
        "through proper symbolic reasoning?\n"
        "2. INFERENCE VALIDITY: Are the logical steps sound and properly "
        "derived?\n"
        "3. NATURAL LANGUAGE CLARITY: Is the reasoning readable; define "
        "symbols when first introduced and briefly explain jargon.\n"
        "4. ASSUMPTIONS & SCOPE: Assumptions, constraints, and unknowns "
        "are explicit; out-of-scope parts noted.\n"
        "5. CONSISTENCY & NON-CONTRADICTION: Conclusions do not conflict "
        "with premises; quantifier scope is correct.\n"
        "6. ACTIONABILITY & RELEVANCE: Final answer aligns with user "
        "intent and provides practical guidance where applicable.\n"
        "7. EXAMPLES & EVIDENCE: Concrete examples illustrate key "
        "inferences; avoid unsupported factual claims.\n\n"
        "Must-pass gate: No hallucinated or unsupported facts; unknowns "
        "and limitations clearly flagged.\n\n"
        "SYMBOLIC LOGIC CHECKLIST:\n"
        "- Premises clearly identified and formalized\n"
        "- Logical relationships properly established\n"
        "- Deductive reasoning applied correctly\n"
        "- Conclusions validly derived\n"
        "- All query components addressed\n"
        "- No contradictions detected; quantifier scope validated\n"
        "- Assumptions enumerated; edge cases considered\n\n"
        "ADVERSARIAL REVIEW:\n"
        "- Adopt an adversarial stance: for each identified enhancement, "
        "proactively propose specific counter-arguments or failure modes "
        "that could challenge the reasoning, assumptions, clarity, or "
        "completeness. Focus on edge cases and potential contradictions.\n\n"
        "OUTPUT INSTRUCTIONS (if/else):\n"
        "- Use labels exactly: [COMPLETE|INCOMPLETE], \"Reason:\", "
        "\"Enhancements:\", \"Refined Response:\".\n"
        "- When referencing criteria, use numbers only (e.g., 3,4,7) "
        "with a one-line note per item.\n"
        "- If the previous response is complete:\n"
        "  - Start with \"[COMPLETE]\".\n"
        "  - Immediately add \"Reason:\" summarizing which criteria are "
        "met (e.g., \"Reason: 1,2,5 met; 3,4 need clarity and "
        "assumptions\").\n"
        "  - Omit the \"Enhancements:\" and \"Refined Response:\" "
        "sections.\n"
        "- Else (the response is incomplete):\n"
        "  - Start with \"[INCOMPLETE]\".\n"
        "  - Immediately add \"Reason:\" summarizing which criteria "
        "need work.\n"
        "  - Under \"Enhancements:\", list only the applicable items "
        "using the 1-7 numbers with one-line notes.\n"
        "  - Under \"Counter Arguments:\", provide adversarial critiques "
        "aligned to the numbers in \"Enhancements\" (at least one per "
        "item), highlighting risks, edge cases, and possible "
        "contradictions.\n"
        "  - Under \"Refined Response:\", provide an improved answer "
        "that resolves each listed enhancement (by number). Define any "
        "symbols when first introduced (e.g., \"-> = implies\", "
        "\"forall = for all\"); if none are used, state \"No new "
        "symbols.\""
    )


# ---------------------------------------------------------------------------
# Core async function
# ---------------------------------------------------------------------------

async def pro_symbolic(
    query: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    refinement_iterations: int = DEFAULT_REFINEMENT_ITERATIONS,
    api_key: Optional[str] = None,
    api_base_url: str = API_BASE_URL,
    client: Optional[AsyncOpenAI] = None,
) -> dict:
    """Run an iterative symbolic-logic reasoning session.

    Parameters
    ----------
    query:
        The user's question or problem statement.
    model:
        DeepSeek model name.  Default ``deepseek-reasoner`` (v4-pro).
    max_tokens:
        Maximum tokens per generation.  Default 50,000.
    temperature:
        Sampling temperature (0.0 - 4.0).  Default 0.5.
    refinement_iterations:
        Number of evaluation-refinement rounds.  1 = no refinement.
        Default 3, max 200.
    api_key:
        DeepSeek API key.  Falls back to ``DEEPSEEK_API_KEY`` env var.
    api_base_url:
        API base URL.  Default ``https://api.deepseek.com``.
    client:
        Optional pre-configured ``AsyncOpenAI`` client for re-use.

    Returns
    -------
    dict with keys:
        final_answer      - The best answer after all iterations.
        thoughts          - Reasoning trace(s) if the model supports it.
        iterations_done   - Number of iterations executed.
        early_stopped     - Whether early-stopped on [COMPLETE].
        repeating_cutoff  - Whether repeating-text detection triggered.
        per_iteration     - List of (thoughts, answer) per round.
    """
    # --- Resolve client ---------------------------------------------------
    resolved_client = client or AsyncOpenAI(
        api_key=api_key or os.environ.get(API_KEY_ENV),
        base_url=api_base_url,
    )

    # --- Clamp iterations ------------------------------------------------
    n_iters = max(1, min(refinement_iterations, MAX_REFINEMENT_ITERATIONS))

    # --- State -----------------------------------------------------------
    refined_thoughts = ""
    refined_answer = ""
    per_iteration = []
    iterations_done = 0
    early_stopped = False
    repeating_cutoff = False

    for i in range(n_iters):
        iterations_done = i + 1
        iteration_prompt = _build_iteration_prompt(
            prompt=query,
            iteration_index=i,
            previous_thoughts=refined_thoughts,
            previous_answer=refined_answer,
        )

        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": iteration_prompt},
        ]

        current_thoughts = ""
        current_answer = ""

        try:
            stream = await resolved_client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else type(
                    "Delta", (), {"content": None, "reasoning_content": None}
                )()

                # --- Content (visible answer) -----------------------------
                if hasattr(delta, "content") and delta.content:
                    current_answer += delta.content
                    if _is_repeating(current_answer):
                        repeating_cutoff = True
                        break

                # --- Reasoning content (CoT trace, reasoner models) -------
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    current_thoughts += delta.reasoning_content
                    if _is_repeating(current_thoughts):
                        repeating_cutoff = True
                        break

        except Exception as exc:
            current_answer = (
                f"Error during iteration {i + 1}: {exc}\n\n"
                "Falling back to previous answer."
            ) if not refined_answer else refined_answer

        per_iteration.append((current_thoughts, current_answer))
        refined_thoughts = current_thoughts
        refined_answer = current_answer

        # --- Early stop on [COMPLETE] ------------------------------------
        if current_answer.strip().startswith("[COMPLETE]"):
            early_stopped = True
            break

        # --- Safety cutoff -----------------------------------------------
        if repeating_cutoff:
            break

    # --- Strip control markers from the final answer ----------------------
    cleaned = refined_answer.replace("[COMPLETE]", "").replace("[INCOMPLETE]", "")

    return {
        "final_answer": cleaned,
        "thoughts": refined_thoughts,
        "iterations_done": iterations_done,
        "early_stopped": early_stopped,
        "repeating_cutoff": repeating_cutoff,
        "per_iteration": per_iteration,
    }


# ---------------------------------------------------------------------------
# Synchronous convenience wrapper (for non-async contexts)
# ---------------------------------------------------------------------------

def pro_symbolic_sync(
    query: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    refinement_iterations: int = DEFAULT_REFINEMENT_ITERATIONS,
    api_key: Optional[str] = None,
) -> dict:
    """Synchronous wrapper around :func:`pro_symbolic`."""
    return asyncio.run(
        pro_symbolic(
            query=query,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            refinement_iterations=refinement_iterations,
            api_key=api_key,
        )
    )


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    test_query = " ".join(sys.argv[1:]) or "What is 2 + 2?"
    result = asyncio.run(pro_symbolic(test_query, refinement_iterations=2))
    print("=" * 72)
    print("FINAL ANSWER")
    print("=" * 72)
    print(result["final_answer"])
    print()
    print(f"Iterations: {result['iterations_done']}")
    print(f"Early stopped: {result['early_stopped']}")
    print(f"Repeating cutoff: {result['repeating_cutoff']}")
