#!/usr/bin/env python3
"""
Fine-tune a code LLM on Lean4 theorem generation using QLoRA.

Usage:
    python scripts/train.py \
        --train_file ./data/mathlib4_theorems_train.jsonl \
        --eval_file ./data/mathlib4_theorems_val.jsonl \
        --output_dir ./outputs/lean4-theorem-generator \
        --base_model deepseek-ai/deepseek-coder-1.3b-instruct \
        --num_epochs 3 \
        --batch_size 4
"""
import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import torch
import transformers
from datasets import Dataset, DatasetDict, load_dataset
from peft import (
    LoraConfig,
    get_peft_model,
    get_peft_model_state_dict,
    prepare_model_for_kbit_training,
    set_peft_model_state_dict,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    HfArgumentParser,
    Trainer,
    TrainingArguments,
    set_seed,
)
from tqdm import tqdm

from configs.lora_config import LoRATrainingConfig, InferenceConfig


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------

def get_chat_template(tokenizer):
    """Determine the chat template from tokenizer or apply a default one."""
    if tokenizer.chat_template is not None:
        return tokenizer.chat_template
    # For models without a chat template, provide a default
    return None


def format_with_template(example: Dict, config: LoRATrainingConfig, tokenizer) -> str:
    """
    Format a dataset example according to the model's expected format.
    """
    prompt = example.get('prompt', '')
    completion = example.get('completion', '')

    # Try to use chat template if available
    chat_template = get_chat_template(tokenizer)
    if chat_template is not None:
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": completion},
        ]
        return tokenizer.apply_chat_template(messages, tokenize=False)

    # Default: simple concatenation
    return prompt + '\n' + completion


def tokenize_function(
    examples: Dict[str, List],
    tokenizer,
    config: LoRATrainingConfig,
) -> Dict:
    """Tokenize and prepare examples for causal LM training."""
    texts = []
    for i in range(len(examples.get('prompt', []))):
        ex = {k: examples[k][i] for k in examples}
        text = format_with_template(ex, config, tokenizer)
        texts.append(text)

    # Tokenize
    tokenized = tokenizer(
        texts,
        truncation=True,
        max_length=config.max_seq_length,
        padding=False,
        return_tensors=None,
    )

    # Create labels (same as input_ids for causal LM)
    tokenized['labels'] = tokenized['input_ids'].copy()
    return tokenized


# ---------------------------------------------------------------------------
# Model setup
# ---------------------------------------------------------------------------

def create_quantized_model(
    model_name: str,
    config: LoRATrainingConfig,
) -> Tuple[AutoModelForCausalLM, AutoTokenizer]:
    """Load model with 4-bit quantization and prepare for LoRA fine-tuning."""
    compute_dtype = getattr(torch, config.bnb_4bit_compute_dtype)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=config.use_4bit,
        bnb_4bit_quant_type=config.bnb_4bit_quant_type,
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=config.use_nested_quant,
    )

    print(f"[*] Loading base model: {model_name}")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=compute_dtype,
    )
    model.config.use_cache = False  # Required for gradient checkpointing
    model.config.pretraining_tp = 1

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        padding_side="right",
    )

    # Set pad token if not set
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # Prepare model for k-bit training
    model = prepare_model_for_kbit_training(model)

    return model, tokenizer


def setup_lora_model(
    model: AutoModelForCausalLM,
    config: LoRATrainingConfig,
) -> AutoModelForCausalLM:
    """Apply LoRA adapters to the model."""
    # Determine target modules based on model architecture
    target_modules = config.lora_target_modules
    if target_modules is None:
        # Common patterns for code models
        target_modules = find_all_linear_names(model)

    print(f"[*] LoRA target modules: {target_modules}")

    lora_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        target_modules=target_modules,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


def find_all_linear_names(model: AutoModelForCausalLM) -> List[str]:
    """Find all linear layer names in the model (common LoRA targets)."""
    cls = torch.nn.Linear
    lora_module_names = set()
    for name, module in model.named_modules():
        if isinstance(module, cls):
            names = name.split('.')
            lora_module_names.add(names[0] if len(names) == 1 else names[-1])

    # Remove common non-target names
    if 'lm_head' in lora_module_names:
        lora_module_names.remove('lm_head')
    if 'embed_tokens' in lora_module_names:
        lora_module_names.remove('embed_tokens')

    return list(lora_module_names)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(config: LoRATrainingConfig):
    """Run the full training pipeline."""
    set_seed(config.seed)

    # 1. Load tokenizer and model
    model, tokenizer = create_quantized_model(
        config.base_model_name, config
    )

    # 2. Load dataset
    print(f"[*] Loading dataset from {config.train_file}")
    data_files = {
        'train': config.train_file,
        'eval': config.eval_file,
    }
    raw_datasets = load_dataset('json', data_files=data_files, split={
        'train': 'train',
        'eval': 'eval',
    })

    # Tokenize
    tokenized_datasets = raw_datasets.map(
        lambda examples: tokenize_function(examples, tokenizer, config),
        batched=True,
        remove_columns=raw_datasets['train'].column_names,
        desc="Tokenizing dataset",
    )

    # 3. Setup LoRA
    model = setup_lora_model(model, config)

    # 4. Enable gradient checkpointing
    if config.gradient_checkpointing:
        model.config.use_cache = False
        model.enable_input_require_grads()

    # 5. Data collator
    collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )

    # 6. Training arguments
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        per_device_eval_batch_size=config.per_device_eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        gradient_checkpointing=config.gradient_checkpointing,
        max_grad_norm=config.max_grad_norm,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        optim=config.optim,
        lr_scheduler_type=config.lr_scheduler_type,
        warmup_ratio=config.warmup_ratio,
        group_by_length=config.group_by_length,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        eval_steps=config.eval_steps,
        save_total_limit=config.save_total_limit,
        load_best_model_at_end=config.load_best_model_at_end,
        metric_for_best_model=config.metric_for_best_model,
        greater_is_better=config.greater_is_better,
        seed=config.seed,
        fp16=config.fp16,
        bf16=config.bf16,
        tf32=config.tf32,
        report_to=config.report_to,
        remove_unused_columns=False,
        ddp_find_unused_parameters=False if torch.cuda.device_count() > 1 else None,
        evaluation_strategy="steps",
    )

    # 7. Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets['train'],
        eval_dataset=tokenized_datasets['eval'],
        tokenizer=tokenizer,
        data_collator=collator,
    )

    # 8. Train
    print("[*] Starting training...")
    trainer.train()

    # 9. Save final model
    final_dir = os.path.join(config.output_dir, 'final')
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)
    print(f"[*] Final model saved to {final_dir}")

    # Save training config alongside model
    config_path = os.path.join(final_dir, 'training_config.json')
    with open(config_path, 'w') as f:
        json.dump(vars(config), f, indent=2, default=str)

    return trainer


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Fine-tune code LLM on Lean4 theorems using QLoRA.',
    )

    # Dataset
    parser.add_argument('--train_file', type=str,
                        default='./data/mathlib4_theorems_train.jsonl')
    parser.add_argument('--eval_file', type=str,
                        default='./data/mathlib4_theorems_val.jsonl')

    # Model
    parser.add_argument('--base_model', type=str,
                        default='deepseek-ai/deepseek-coder-1.3b-instruct',
                        help='HuggingFace base model name or path.')

    # Output
    parser.add_argument('--output_dir', type=str,
                        default='./outputs/lean4-theorem-generator')

    # Training hyperparameters
    parser.add_argument('--num_epochs', type=int, default=3)
    parser.add_argument('--batch_size', type=int, default=4)
    parser.add_argument('--gradient_accumulation_steps', type=int, default=4)
    parser.add_argument('--learning_rate', type=float, default=2e-4)
    parser.add_argument('--max_seq_length', type=int, default=2048)
    parser.add_argument('--lora_r', type=int, default=16)
    parser.add_argument('--lora_alpha', type=int, default=32)
    parser.add_argument('--lora_dropout', type=float, default=0.05)

    # Precision
    parser.add_argument('--use_4bit', action='store_true', default=True)
    parser.add_argument('--bf16', action='store_true', default=True)
    parser.add_argument('--no_bf16', dest='bf16', action='store_false')

    # Logging
    parser.add_argument('--logging_steps', type=int, default=10)
    parser.add_argument('--save_steps', type=int, default=200)
    parser.add_argument('--report_to', type=str, default='tensorboard',
                        choices=['tensorboard', 'wandb', 'none'])

    # Misc
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--resume_from_checkpoint', type=str, default=None,
                        help='Path to a checkpoint to resume from.')

    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # Build config from args
    config = LoRATrainingConfig(
        base_model_name=args.base_model,
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        max_seq_length=args.max_seq_length,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        use_4bit=args.use_4bit,
        bf16=args.bf16,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        report_to=args.report_to,
        seed=args.seed,
        train_file=args.train_file,
        eval_file=args.eval_file,
    )

    print("=" * 60)
    print("Lean4 Theorem Generator — QLoRA Fine-Tuning")
    print("=" * 60)
    print(f"Base model: {config.base_model_name}")
    print(f"LoRA rank: {config.lora_r}, alpha: {config.lora_alpha}")
    print(f"Training epochs: {config.num_train_epochs}")
    print(f"Batch size (per device): {config.per_device_train_batch_size}")
    print(f"Gradient accumulation: {config.gradient_accumulation_steps}")
    print(f"Effective batch size: {config.per_device_train_batch_size * config.gradient_accumulation_steps}")
    print(f"Max sequence length: {config.max_seq_length}")
    print(f"Output directory: {config.output_dir}")
    print("=" * 60)

    train(config)


if __name__ == '__main__':
    main()
