# EVO Network Resilience Deployment

This directory contains the complete set of changes to make the evo-ai
codebase resilient against network errors. Each file is a drop-in replacement
for the corresponding file in the original evo-ai repository.

## Quick Start

1. Copy all files into the evo-ai repo root
2. Create the `mind/network_resilience.py` file (the core module)
3. Update the files in `tools/` as shown
4. Update `config.py` with the new settings
5. Run the existing test suite to verify

## Files

| Source File | Target | Description |
|---|---|---|
| `mind/network_resilience.py` | `mind/network_resilience.py` | NEW — Core resilience module |
| `patches/0002-web_search-resilience.patch` | `tools/web_search.py` | Retry+circuit-breaker for Brave/LangSearch/DDG |
| `patches/0003-web_browse-resilience.patch` | `tools/web_browse.py` | Retry on Playwright navigation timeout |
| `patches/0004-github_public-resilience.patch` | `tools/github_public.py` | Retry+rate-limiter for GitHub API |
| `patches/0005-python_executor-resilience.patch` | `tools/python_executor.py` | Timeout hardening |
| `patches/0006-code_scratch_pad-resilience.patch` | `tools/code_scratch_pad.py` | Retry for CI dispatch/query calls |
| `patches/0007-config-network-timeouts.patch` | `config.py` | New timeout env vars |

## Applying Patches

```bash
# From the evo-ai repo root:
patch -p1 < patches/0002-web_search-resilience.patch
patch -p1 < patches/0003-web_browse-resilience.patch
patch -p1 < patches/0004-github_public-resilience.patch
patch -p1 < patches/0005-python_executor-resilience.patch
patch -p1 < patches/0006-code_scratch_pad-resilience.patch
patch -p1 < patches/0007-config-network-timeouts.patch
```

## Verifying

```bash
# Check imports resolve
python -c "from mind.network_resilience import resilient_call, urlopen_retry"

# Run existing tests
python -m pytest test_evo_gates.py test_evo_prompt.py -v
```

## Environment Variables (new)

| Variable | Default | Description |
|---|---|---|
| `EVO_NETWORK_TIMEOUT` | 30 | Default HTTP timeout (s) |
| `EVO_GITHUB_TIMEOUT` | 15 | GitHub API timeout (s) |
| `EVO_BRAVE_TIMEOUT` | 30 | Brave Search timeout (s) |
| `EVO_LANGSEARCH_TIMEOUT` | 15 | LangSearch timeout (s) |
| `EVO_BROWSE_TIMEOUT` | 60 | Playwright browse timeout (s) |
| `EVO_MAX_RETRIES` | 3 | Max retry attempts |
| `EVO_BASE_DELAY` | 1.0 | Initial retry delay (s) |
| `EVO_MAX_DELAY` | 30.0 | Maximum retry delay (s) |
| `EVO_BACKOFF_MULT` | 2.0 | Exponential backoff multiplier |
