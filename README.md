# Lean4 Theorem Generator — Fine-Tuned LLM

A complete Python pipeline for fine-tuning a Large Language Model to generate **Lean4 Mathlib-level theorem declarations** from natural language descriptions.

## Overview

```
User Prompt: "A theorem about the sum of two even numbers being even"
        ↓
   Fine-Tuned LLM
        ↓
Lean4 Output:  theorem sum_of_evens (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := ...
```

The system extracts theorem declarations from the [Mathlib4](https://github.com/leanprover-community/mathlib4) repository, where each theorem's **docstring** serves as the natural language prompt and the **theorem signature** serves as the target output. A code LLM is then fine-tuned using **QLoRA** (4-bit quantized LoRA) to learn the mapping from descriptions to Lean4 type signatures.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  prepare_dataset │────▶│    train.py      │────▶│   generate.py   │
│  (extract        │     │  (QLoRA fine-    │     │  (inference /   │
│   theorems from  │     │   tuning)        │     │   generation)   │
│   Mathlib4)      │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
  data/*.jsonl          outputs/*/              Interactive /
  (prompt,              (model checkpoints,      Batch /
  completion) pairs      adapters)              One-shot modes
```

### Pipeline Stages

1. **Data Preparation** (`scripts/prepare_dataset.py`)
   - Scans Mathlib4 source tree for `.lean` files
   - Extracts `theorem`/`lemma` declarations with their preceding docstrings
   - Filters for examples with meaningful descriptions (docstrings ≥ 10 chars)
   - Formats as (prompt, completion) pairs
   - Splits into train/val/test sets
   - Output: `mathlib4_theorems_{train,val,test}.jsonl`

2. **Fine-Tuning** (`scripts/train.py`)
   - Loads base model with **4-bit NF4 quantization** (QLoRA)
   - Applies **LoRA adapters** to all linear layers
   - Trains with causal language modeling objective
   - Uses gradient checkpointing and paged optimizers for memory efficiency
   - Saves best checkpoint + final merged adapter
   - Output: PEFT adapter in `outputs/lean4-theorem-generator/`

3. **Inference** (`scripts/generate.py`)
   - Three modes: **interactive**, **one-shot**, **batch**
   - Loads PEFT adapter on top of base model
   - Generates Lean4 theorem code from natural language descriptions
   - Supports configurable sampling parameters (temperature, top-p, top-k)

## Quick Start

### Prerequisites

- Python 3.10+
- CUDA-capable GPU with ≥ 12GB VRAM (for 1.3B model) or ≥ 24GB (for 7B model)
- [Mathlib4](https://github.com/leanprover-community/mathlib4) repository clone (for dataset generation)

### Installation

```bash
# Clone this repo
git clone https://github.com/test1-deepthought/evo_code_scratch_pad.git
cd evo_code_scratch_pad

# Install dependencies
pip install -r requirements.txt

# (Optional) Clone Mathlib4 for dataset preparation
git clone https://github.com/leanprover-community/mathlib4.git /path/to/mathlib4
```

### 1. Prepare Dataset

```bash
python scripts/prepare_dataset.py \
    --mathlib_path /path/to/mathlib4 \
    --output_dir ./data \
    --max_examples 50000 \
    --val_split 0.05 \
    --test_split 0.05 \
    --min_description_len 20 \
    --prompt_version simple
```

This will produce:
- `data/mathlib4_theorems_train.jsonl` (~45k examples)
- `data/mathlib4_theorems_val.jsonl` (~2.5k examples)
- `data/mathlib4_theorems_test.jsonl` (~2.5k examples)
- `data/dataset_stats.json`

### 2. Fine-Tune

```bash
# Fine-tune DeepSeek-Coder-1.3B (recommended for 12GB GPUs)
python scripts/train.py \
    --base_model deepseek-ai/deepseek-coder-1.3b-instruct \
    --train_file ./data/mathlib4_theorems_train.jsonl \
    --eval_file ./data/mathlib4_theorems_val.jsonl \
    --output_dir ./outputs/lean4-theorem-generator \
    --num_epochs 3 \
    --batch_size 4 \
    --gradient_accumulation_steps 4 \
    --learning_rate 2e-4 \
    --lora_r 16 \
    --max_seq_length 2048 \
    --bf16

# For larger models (7B+, requires 24GB+ VRAM):
python scripts/train.py \
    --base_model codellama/CodeLlama-7b-hf \
    ... (same args)
```

### 3. Generate Theorems

```bash
# Interactive mode
python scripts/generate.py --model_path ./outputs/lean4-theorem-generator/final

# One-shot
python scripts/generate.py \
    --model_path ./outputs/lean4-theorem-generator/final \
    --prompt "If a natural number n is prime and n divides a*b, then n divides a or n divides b"

# Batch from file
python scripts/generate.py \
    --model_path ./outputs/lean4-theorem-generator/final \
    --input_file prompts.jsonl \
    --output_file generations.jsonl
```

## Dataset Format

Each line in the `.jsonl` files is a JSON object:

```json
{
  "prompt": "Write a Lean 4 theorem that: If two integers are congruent mod n, their difference is divisible by n",
  "completion": "```lean4\ntheorem modEq_iff_sub_dvd (a b n : ℤ) : a ≡ b [ZMOD n] ↔ n ∣ a - b :=\n```",
  "text": "Write a Lean 4 theorem that: ... \n```lean4\n...\n```",
  "description": "If two integers are congruent mod n, their difference is divisible by n",
  "signature": "theorem modEq_iff_sub_dvd (a b n : ℤ) : a ≡ b [ZMOD n] ↔ n ∣ a - b"
}
```

## Model Selection Guide

| Model | VRAM | Quality | Speed |
|-------|------|---------|-------|
| `deepseek-ai/deepseek-coder-1.3b-instruct` | ~8GB | Good | Fast |
| `microsoft/Phi-3-mini-4k-instruct` | ~10GB | Good | Fast |
| `Qwen/Qwen2.5-Coder-1.5B` | ~8GB | Good | Fast |
| `codellama/CodeLlama-7b-hf` | ~16GB | Better | Medium |
| `mistralai/Mistral-7B-v0.1` | ~16GB | Better | Medium |
| `deepseek-ai/deepseek-coder-6.7b-instruct` | ~16GB | Best | Medium |
| `codellama/CodeLlama-34b-hf` | ~40GB | Best | Slow |

## Example Generations

**Prompt:** "A theorem that the sum of two even natural numbers is even"

**Generated:**
```lean4
theorem even_add (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by
  rcases ha with ⟨k, hk⟩
  rcases hb with ⟨l, hl⟩
  use k + l
  calc
    a + b = 2 * k + 2 * l := by rw [hk, hl]
    _ = 2 * (k + l) := by ring
```

**Prompt:** "If a prime p divides a product a*b then p divides a or p divides b"

**Generated:**
```lean4
theorem Prime.dvd_or_dvd {p a b : ℕ} (hp : p.Prime) (h : p ∣ a * b) : p ∣ a ∨ p ∣ b :=
  hp.dvd_or_dvd h
```

## Configuration

All training hyperparameters are in `configs/lora_config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lora_r` | 16 | LoRA rank |
| `lora_alpha` | 32 | LoRA scaling |
| `lora_dropout` | 0.05 | Dropout for LoRA layers |
| `learning_rate` | 2e-4 | Peak learning rate |
| `num_train_epochs` | 3 | Number of epochs |
| `max_seq_length` | 2048 | Maximum sequence length |
| `use_4bit` | True | 4-bit quantization |
| `bnb_4bit_quant_type` | "nf4" | NormalFloat4 quantization |

## Evaluation

After fine-tuning, evaluate on the test set:

```bash
python scripts/generate.py \
    --model_path ./outputs/lean4-theorem-generator/final \
    --input_file ./data/mathlib4_theorems_test.jsonl \
    --output_file ./outputs/test_generations.jsonl
```

Key metrics to assess:
- **Exact match** of generated theorem signature vs ground truth
- **Type-correctness** (can the generated theorem be parsed by Lean?)
- **Semantic correctness** (does the theorem accurately capture the description?)

## Limitations

- **Proof generation**: This pipeline primarily generates **theorem signatures** (statements), not full proofs. Extending to proof generation would require a larger model and a different training objective.
- **Mathlib dependency**: Generated theorems may reference types/lemmas not available in the user's Mathlib version.
- **Hallucination**: The LLM may invent non-existent lemmas or incorrect type signatures.
- **Dataset quality**: Depends on the quality and breadth of Mathlib4 docstrings.

## Future Work

- [ ] Add proof generation with step-by-step training
- [ ] Integrate with Lean 4's `#check` for automatic validation
- [ ] Add RAG (Retrieval-Augmented Generation) using Mathlib4 lemma search
- [ ] Support for user-provided custom theorem databases
- [ ] Web UI for interactive theorem generation

## License

MIT
