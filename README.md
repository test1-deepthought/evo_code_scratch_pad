# Lean4 Theorem Generator — Fine-Tuned LLM

[![CI - Lean4 Theorem Generator](https://github.com/test1-deepthought/evo_code_scratch_pad/actions/workflows/ci.yml/badge.svg?branch=evo/lean4-theorem-generator-finetune-20260613-234316)](https://github.com/test1-deepthought/evo_code_scratch_pad/actions/workflows/ci.yml)

A complete Python pipeline for fine-tuning a Large Language Model to generate **Lean4 Mathlib-level theorem declarations** from natural language descriptions.

## Overview

```
User Prompt: "A theorem about the sum of two even numbers being even"
        v
   Fine-Tuned LLM
        v
Lean4 Output:  theorem sum_of_evens (a b : N) (ha : Even a) (hb : Even b) : Even (a + b) := ...
```

The system extracts theorem declarations from the [Mathlib4](https://github.com/leanprover-community/mathlib4) repository, where each theorem's **docstring** serves as the natural language prompt and the **theorem signature** serves as the target output. A code LLM is then fine-tuned using **QLoRA** (4-bit quantized LoRA) to learn the mapping from descriptions to Lean4 type signatures.

## Architecture

```
+-------------------+     +------------------+     +-----------------+
|  prepare_dataset  |--->|    train.py      |--->|   generate.py   |
|  (extract         |     |  (QLoRA fine-    |     |  (inference /   |
|   theorems from   |     |   tuning)        |     |   generation)   |
|   Mathlib4)       |     |                  |     |                 |
+-------------------+     +------------------+     +-----------------+
        |                        |                        |
        v                        v                        v
  data/*.jsonl          outputs/*/              Interactive /
  (prompt,              (model checkpoints,      Batch /
  completion) pairs      adapters)              One-shot modes
```

### Pipeline Stages

1. **Data Preparation** (`scripts/prepare_dataset.py`)
   - Scans Mathlib4 source tree for `.lean` files
   - Extracts `theorem`/`lemma` declarations with their preceding docstrings
   - Filters for examples with meaningful descriptions (docstrings >= 10 chars)
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
- CUDA-capable GPU with >= 12GB VRAM (for 1.3B model) or >= 24GB (for 7B model)
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

### 2. Fine-Tune

```bash
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

## Test Suite

The test suite validates all pipeline components **without requiring torch, CUDA, or Mathlib4**:

| Test File | What It Tests |
|-----------|---------------|
| `tests/test_syntax.py` | Python AST validation of all .py files |
| `tests/test_config.py` | Config dataclass defaults and overrides |
| `tests/test_sample_prompts.py` | Sample prompts JSONL format |
| `tests/test_dataset_logic.py` | Docstring extraction, signature stripping |
| `tests/test_generation_logic.py` | Prompt formatting, output cleaning |

Run tests: `pip install pytest && python -m pytest tests/ -v`

## Limitations

- **Proof generation**: This pipeline primarily generates **theorem signatures** (statements), not full proofs
- **Mathlib dependency**: Generated theorems may reference types/lemmas not available
- **Hallucination**: The LLM may invent non-existent lemmas or incorrect type signatures

## License

MIT
