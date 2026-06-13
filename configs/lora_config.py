"""
LoRA / QLoRA configuration for Lean4 Theorem Generator fine-tuning.
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class LoRATrainingConfig:
    # --- Model ---
    base_model_name: str = "deepseek-ai/deepseek-coder-1.3b-instruct"
    # Alternatives: "codellama/CodeLlama-7b-hf", "mistralai/Mistral-7B-v0.1",
    #              "microsoft/Phi-3-mini-4k-instruct", "Qwen/Qwen2.5-Coder-1.5B"

    # --- QLoRA 4-bit quantization ---
    use_4bit: bool = True
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"
    use_nested_quant: bool = False

    # --- LoRA hyperparameters ---
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: Optional[List[str]] = None
    # Default: all linear layers (q, k, v, o, gate, up, down)
    # Auto-detected from model config if None.

    # --- Training ---
    output_dir: str = "./outputs/lean4-theorem-generator"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    per_device_eval_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    gradient_checkpointing: bool = True
    max_grad_norm: float = 0.3
    learning_rate: float = 2e-4
    weight_decay: float = 0.001
    optim: str = "paged_adamw_8bit"
    lr_scheduler_type: str = "cosine"
    warmup_ratio: float = 0.03
    group_by_length: bool = True
    packing: bool = False

    # --- Dataset ---
    max_seq_length: int = 2048
    dataset_source: str = "mathlib4"  # "mathlib4" or "hf" or "local"

    # --- Logging / saving ---
    logging_steps: int = 10
    save_steps: int = 200
    eval_steps: int = 200
    save_total_limit: int = 3
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False

    # --- Misc ---
    seed: int = 42
    report_to: str = "tensorboard"  # "wandb" or "none"
    fp16: bool = False
    bf16: bool = True  # Use bf16 if supported
    tf32: bool = True  # Use tf32 on Ampere+ GPUs

    # --- Data files ---
    train_file: str = "./data/mathlib4_theorems_train.jsonl"
    eval_file: str = "./data/mathlib4_theorems_eval.jsonl"
    test_file: str = "./data/mathlib4_theorems_test.jsonl"


@dataclass
class InferenceConfig:
    model_path: str = "./outputs/lean4-theorem-generator/final"
    max_new_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repetition_penalty: float = 1.1
    num_return_sequences: int = 1
    do_sample: bool = True
