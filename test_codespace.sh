#!/bin/bash
# Test script for codespace
echo "=== Codespace Environment Test ==="
echo "Hostname: $(hostname)"
echo "User: $(whoami)"
echo "Date: $(date)"
echo "Python version: $(python3 --version 2>&1)"
echo "Disk space:"
df -h / | tail -1
echo "=== Test Complete ==="
