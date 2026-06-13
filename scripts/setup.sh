#!/usr/bin/env bash
# Setup script for Lean4 Theorem Generator fine-tuning pipeline.
# Usage: bash scripts/setup.sh

set -euo pipefail

echo "============================================"
echo " Lean4 Theorem Generator — Setup"
echo "============================================"

# Check Python version
echo "[*] Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "    Python $python_version detected"
major=$(echo "$python_version" | cut -d. -f1)
minor=$(echo "$python_version" | cut -d. -f2)
if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 10 ]); then
    echo "[!] WARNING: Python 3.10+ is recommended. Found $python_version"
fi

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv .venv
    echo "    ✅ Created .venv/"
else
    echo "[*] Virtual environment already exists."
fi

# Activate
echo "[*] Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "[*] Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "[*] Installing Python dependencies..."
pip install -r requirements.txt --quiet
echo "    ✅ Dependencies installed"

# Create data directory
mkdir -p data
echo "    ✅ data/ directory created"

# Create outputs directory
mkdir -p outputs
echo "    ✅ outputs/ directory created"

# Check for Mathlib4
if [ ! -d "../mathlib4" ] && [ ! -d "./mathlib4" ]; then
    echo ""
    echo "[!] NOTE: Mathlib4 not found locally."
    echo "    To prepare the training dataset, clone:"
    echo "      git clone https://github.com/leanprover-community/mathlib4.git"
    echo ""
    echo "    Optional: Use a pre-built dataset or a small sample to test."
fi

# Check CUDA
echo ""
echo "[*] Checking CUDA availability..."
if python3 -c "import torch; print('    ✅ CUDA available:', torch.cuda.is_available(), '| Devices:', torch.cuda.device_count())" 2>/dev/null; then
    :
else
    echo "    ℹ️  torch not yet installed or no CUDA — will be available after activation"
fi

echo ""
echo "============================================"
echo " Setup complete!"
echo "============================================"
echo ""
echo "Activate the environment:"
echo "    source .venv/bin/activate"
echo ""
echo "Quick start:"
echo "    1. Prepare dataset:  python scripts/prepare_dataset.py --mathlib_path /path/to/mathlib4"
echo "    2. Train:            python scripts/train.py"
echo "    3. Generate:         python scripts/generate.py --model_path ./outputs/lean4-theorem-generator/final"
echo ""
