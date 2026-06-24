#!/bin/bash
# Apply all network resilience patches to the evo-ai repo
# Run this from the evo-ai repo root directory

set -e

echo "=== EVO Network Resilience Deployment ==="
echo ""

# Copy the core module
if [ -f "mind/network_resilience.py" ]; then
    echo "SKIP: mind/network_resilience.py already exists"
else
    cp deploy/mind/network_resilience.py mind/network_resilience.py
    echo "OK: Created mind/network_resilience.py"
fi

# Apply patches
echo ""
echo "Applying patches..."
for patch in deploy/patches/*.patch; do
    name=$(basename "$patch")
    if patch -p1 --dry-run < "$patch" > /dev/null 2>&1; then
        patch -p1 < "$patch"
        echo "OK: $name"
    else
        echo "WARN: $name could not be applied (already patched?)"
    fi
Done

echo ""
echo "=== Verification ==="
python -c "from mind.network_resilience import resilient_call, urlopen_retry, check_endpoint_health; print('OK: mind/network_resilience imports resolve')"

echo ""
echo "Deployment complete."
echo "See deploy/README.md for environment variable documentation."
