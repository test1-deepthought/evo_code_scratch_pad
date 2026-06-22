"""
NOVA Configuration — extracted and extended from evo-ai config.py

Extracts: DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, SWIPL_PATH,
LEAN_PROJECT_DIR, GITHUB_TOKEN, BFS_PROVER, DEEPSEEK_PROVER settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- DeepSeek LLM (primary reasoning engine) ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_REASONING_EFFORT = os.getenv("DEEPSEEK_REASONING_EFFORT", "high").strip().lower()
DEEPSEEK_THINKING_MODE = os.getenv("DEEPSEEK_THINKING_MODE", "enabled").strip().lower()
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8192"))

# --- Prolog Reasoner (SWI-Prolog) ---
SWIPL_PATH = os.getenv("SWIPL_PATH", "swipl")

# --- Lean 4 Integration ---
LEAN_PROJECT_DIR = os.getenv("LEAN_PROJECT_DIR", "").strip() or os.path.join(os.path.expanduser("~"), "lean4-sandbox")
LEAN_TIMEOUT_SECONDS = int(os.getenv("LEAN_TIMEOUT_SECONDS", "120"))

# --- GitHub ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# --- Proof Specialists ---
DEEPSEEK_PROVER_API_KEY = os.getenv("DEEPSEEK_PROVER_API_KEY", "")
DEEPSEEK_PROVER_BASE_URL = os.getenv("DEEPSEEK_PROVER_BASE_URL", "https://api.novita.ai/openai")
DEEPSEEK_PROVER_MODEL = os.getenv("DEEPSEEK_PROVER_MODEL", "deepseek/deepseek-prover-v2-671b")
BFS_PROVER_MODEL = os.getenv("BFS_PROVER_MODEL", "ByteDance-Seed/BFS-Prover-V2-32B")
BFS_PROVER_API_KEY = os.getenv("BFS_PROVER_API_KEY", os.getenv("HF_TOKEN", ""))

# --- Web Search ---
LANGSEARCH_API_KEY = os.getenv("LANGSEARCH_API_KEY", "")

# --- NOVA-specific configuration ---
NOVA_KNOWLEDGE_GRAPH_PATH = os.getenv("NOVA_KNOWLEDGE_GRAPH_PATH", "nova_knowledge_graph.json")
NOVA_PROOF_LIBRARY_PATH = os.getenv("NOVA_PROOF_LIBRARY_PATH", "nova_proof_library.json")
NOVA_MAX_AGENTS = int(os.getenv("NOVA_MAX_AGENTS", "5"))
NOVA_DEFAULT_CONFIDENCE_THRESHOLD = float(os.getenv("NOVA_DEFAULT_CONFIDENCE_THRESHOLD", "0.7"))
NOVA_VERIFICATION_BUDGET = int(os.getenv("NOVA_VERIFICATION_BUDGET", "100"))
NOVA_LEARNED_PATTERNS_MAX = int(os.getenv("NOVA_LEARNED_PATTERNS_MAX", "5000"))
