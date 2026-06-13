#!/usr/bin/env python3
"""
Generate Lean4 Mathlib theorems using a fine-tuned model.

Usage:
    # Interactive mode
    python scripts/generate.py --model_path ./outputs/lean4-theorem-generator/final

    # One-shot mode
    python scripts/generate.py --model_path ./outputs/lean4-theorem-generator/final \\
        --prompt "A theorem about the sum of two even numbers being even"

    # Batch mode from file
    python scripts/generate.py --model_path ./outputs/lean4-theorem-generator/final \\
        --input_file prompts.jsonl --output_file generations.jsonl
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import torch
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    GenerationConfig,
)

from configs.lora_config import InferenceConfig


# ---------------------------------------------------------------------------
# System prompt for theorem generation
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Lean 4 theorem prover working with Mathlib. \
Given a natural language description, generate the corresponding Lean 4 theorem \
statement with its type signature. Output only the Lean code."""

USER_TEMPLATE = """<|system|>
{SYSTEM_PROMPT}
<|user|>
Write a Lean 4 theorem for: {description}
<|assistant|>
```lean4
"""

USER_TEMPLATE_SIMPLE = """Write a Lean 4 theorem that: {description}

```lean4
"""


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_model(
    model_path: str,
    use_4bit: bool = True,
    device: str = "auto",
) -> tuple:
    """Load the fine-tuned model and tokenizer."""
    print(f"[*] Loading model from {model_path}")

    compute_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

    bnb_config = None
    if use_4bit and torch.cuda.is_available():
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=False,
        )

    # Try loading with PEFT first (fine-tuned adapter)
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True
        )

        # Load base model
        base_model_name = _get_base_model_name(model_path)
        if base_model_name:
            print(f"[*] Loading base model: {base_model_name}")
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                quantization_config=bnb_config,
                device_map=device,
                trust_remote_code=True,
                torch_dtype=compute_dtype,
            )
            model = PeftModel.from_pretrained(base_model, model_path)
        else:
            # Load directly (might be merged)
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                quantization_config=bnb_config,
                device_map=device,
                trust_remote_code=True,
                torch_dtype=compute_dtype,
            )
    except Exception as e:
        print(f"[!] Could not load as PEFT model: {e}")
        print("[*] Trying direct loading...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=bnb_config,
            device_map=device,
            trust_remote_code=True,
            torch_dtype=compute_dtype,
        )

    # Ensure pad token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model.eval()
    print("[*] Model loaded successfully.")
    return model, tokenizer


def _get_base_model_name(model_path: str) -> Optional[str]:
    """Try to read the base model name from the adapter config."""
    try:
        adapter_config_path = Path(model_path) / 'adapter_config.json'
        if adapter_config_path.exists():
            with open(adapter_config_path) as f:
                config = json.load(f)
            return config.get('base_model_name_or_path')
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_theorem(
    model,
    tokenizer,
    description: str,
    config: InferenceConfig = None,
) -> str:
    """
    Generate a Lean4 theorem from a natural language description.

    Args:
        model: The (PEFT) model.
        tokenizer: The tokenizer.
        description: Natural language description of the theorem.
        config: Generation configuration.

    Returns:
        Generated Lean4 theorem code.
    """
    if config is None:
        config = InferenceConfig()

    # Format the prompt
    prompt = USER_TEMPLATE_SIMPLE.format(description=description)

    # Tokenize
    inputs = tokenizer(
        prompt,
        return_tensors='pt',
        truncation=True,
        max_length=config.max_new_tokens * 2,
    ).to(model.device)

    # Generation config
    gen_config = GenerationConfig(
        max_new_tokens=config.max_new_tokens,
        temperature=config.temperature,
        top_p=config.top_p,
        top_k=config.top_k,
        repetition_penalty=config.repetition_penalty,
        do_sample=config.do_sample,
        num_return_sequences=config.num_return_sequences,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    # Generate
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            generation_config=gen_config,
        )

    # Decode
    generated = tokenizer.decode(
        output_ids[0][inputs['input_ids'].shape[1]:],
        skip_special_tokens=True,
    )

    # Clean up the output
    generated = generated.strip()
    # Remove trailing ``` if present
    if generated.endswith('```'):
        generated = generated[:-3].strip()
    # Remove leading ```lean4 if present
    if generated.startswith('```lean4'):
        generated = generated[8:].strip()
    elif generated.startswith('```'):
        generated = generated[3:].strip()

    return generated


def batch_generate(
    model,
    tokenizer,
    prompts: List[Dict],
    config: InferenceConfig = None,
    output_file: Optional[str] = None,
) -> List[Dict]:
    """Generate theorems for a batch of prompts."""
    results = []
    for i, item in enumerate(prompts):
        desc = item.get('prompt', item.get('description', ''))
        print(f"[{i+1}/{len(prompts)}] Generating for: {desc[:80]}...")

        try:
            theorem = generate_theorem(model, tokenizer, desc, config)
            results.append({
                'prompt': desc,
                'generated_theorem': theorem,
                'status': 'success',
                'timestamp': time.time(),
            })
            print(f"    Result: {theorem[:100]}...")
        except Exception as e:
            print(f"    [!] Error: {e}")
            results.append({
                'prompt': desc,
                'generated_theorem': None,
                'status': 'error',
                'error': str(e),
                'timestamp': time.time(),
            })

        # Save incrementally
        if output_file and (i + 1) % 5 == 0:
            _save_results(results, output_file)

    if output_file:
        _save_results(results, output_file)
        print(f"[*] Saved {len(results)} results to {output_file}")

    return results


def _save_results(results: List[Dict], output_file: str):
    """Save generation results to JSONL file."""
    with open(output_file, 'w') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


# ---------------------------------------------------------------------------
# Interactive REPL
# ---------------------------------------------------------------------------

def interactive_mode(model, tokenizer, config: InferenceConfig):
    """Run an interactive theorem generation session."""
    print("\n" + "=" * 60)
    print("  Lean4 Theorem Generator — Interactive Mode")
    print("=" * 60)
    print("  Describe a theorem in natural language and I'll generate the Lean4 code.")
    print("  Type 'quit' to exit, 'save <filename>' to save last generation.")
    print("-" * 60)

    last_theorem = None

    while True:
        try:
            prompt = input("\n🎯 Describe theorem: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not prompt:
            continue
        if prompt.lower() in ('quit', 'exit', 'q'):
            print("Goodbye!")
            break

        if prompt.lower().startswith('save ') and last_theorem:
            filename = prompt[5:].strip()
            try:
                with open(filename, 'w') as f:
                    f.write(last_theorem)
                print(f"  Saved to {filename}")
            except Exception as e:
                print(f"  Error saving: {e}")
            continue

        if prompt.lower().startswith('save') and not last_theorem:
            print("  No theorem generated yet to save.")
            continue

        print("\n  Generating...")
        theorem = generate_theorem(model, tokenizer, prompt, config)
        last_theorem = theorem

        print("\n" + "-" * 40)
        print("  Generated Theorem:")
        print("-" * 40)
        # Pretty print the Lean code
        for line in theorem.split('\n'):
            print(f"  {line}")
        print("-" * 40)
        print("  [Type 'save filename.lean' to save this theorem]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Generate Lean4 theorems using a fine-tuned LLM.'
    )

    # Model
    parser.add_argument('--model_path', type=str, required=True,
                        help='Path to fine-tuned model (PEFT adapter or merged).')
    parser.add_argument('--no_4bit', dest='use_4bit', action='store_false',
                        help='Disable 4-bit quantization.')

    # Generation config
    parser.add_argument('--max_tokens', type=int, default=512)
    parser.add_argument('--temperature', type=float, default=0.7)
    parser.add_argument('--top_p', type=float, default=0.95)
    parser.add_argument('--top_k', type=int, default=40)
    parser.add_argument('--repetition_penalty', type=float, default=1.1)
    parser.add_argument('--num_samples', type=int, default=1)

    # Mode
    parser.add_argument('--prompt', type=str, default=None,
                        help='Single prompt to generate from.')
    parser.add_argument('--input_file', type=str, default=None,
                        help='JSONL file with prompts.')
    parser.add_argument('--output_file', type=str, default=None,
                        help='Output file for batch generations.')

    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # Build inference config
    inf_config = InferenceConfig(
        max_new_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        repetition_penalty=args.repetition_penalty,
        num_return_sequences=args.num_samples,
    )

    # Load model
    model, tokenizer = load_model(args.model_path, use_4bit=args.use_4bit)

    # Determine mode
    if args.prompt:
        # One-shot mode
        print(f"\n[*] Generating theorem for: {args.prompt}")
        theorem = generate_theorem(model, tokenizer, args.prompt, inf_config)
        print("\n" + "=" * 60)
        print(theorem)
        print("=" * 60)

    elif args.input_file:
        # Batch mode
        print(f"[*] Reading prompts from {args.input_file}")
        with open(args.input_file) as f:
            prompts = [json.loads(line) for line in f if line.strip()]
        output_file = args.output_file or 'generations.jsonl'
        batch_generate(model, tokenizer, prompts, inf_config, output_file)

    else:
        # Interactive mode
        interactive_mode(model, tokenizer, inf_config)


if __name__ == '__main__':
    main()
