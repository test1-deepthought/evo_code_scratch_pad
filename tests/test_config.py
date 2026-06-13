#!/usr/bin/env python3
"""Unit tests for LoRA / inference configuration dataclasses."""
import sys
import importlib.util
from pathlib import Path


def _import_config():
    """Import configs.lora_config via sys.path manipulation."""
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "configs.lora_config",
        root / "configs" / "lora_config.py",
    )
    if spec is None:
        # Try relative path
        spec = importlib.util.spec_from_file_location(
            "configs.lora_config",
            Path("configs/lora_config.py"),
        )
    if spec is None:
        raise ImportError("Cannot find configs/lora_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_training_config_defaults():
    mod = _import_config()
    cfg = mod.LoRATrainingConfig()
    assert cfg.base_model_name == "deepseek-ai/deepseek-coder-1.3b-instruct"
    assert cfg.use_4bit is True
    assert cfg.lora_r == 16
    assert cfg.lora_alpha == 32
    assert cfg.lora_dropout == 0.05
    assert cfg.num_train_epochs == 3
    assert cfg.learning_rate == 2e-4
    assert cfg.max_seq_length == 2048
    assert cfg.optim == "paged_adamw_8bit"
    assert cfg.bf16 is True
    print(f"  LoRATrainingConfig: {len(cfg.__dataclass_fields__)} fields OK")


def test_inference_config_defaults():
    mod = _import_config()
    cfg = mod.InferenceConfig()
    assert cfg.model_path == "./outputs/lean4-theorem-generator/final"
    assert cfg.max_new_tokens == 512
    assert cfg.temperature == 0.7
    assert cfg.top_p == 0.9
    assert cfg.top_k == 40
    assert cfg.repetition_penalty == 1.1
    assert cfg.num_return_sequences == 1
    assert cfg.do_sample is True
    print(f"  InferenceConfig: {len(cfg.__dataclass_fields__)} fields OK")


def test_training_config_override():
    mod = _import_config()
    cfg = mod.LoRATrainingConfig(
        base_model_name="codellama/CodeLlama-7b-hf",
        lora_r=32,
        num_train_epochs=5,
    )
    assert cfg.base_model_name == "codellama/CodeLlama-7b-hf"
    assert cfg.lora_r == 32
    assert cfg.num_train_epochs == 5
    # Unchanged defaults
    assert cfg.learning_rate == 2e-4
    print("  Override test: OK")
