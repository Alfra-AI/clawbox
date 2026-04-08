#!/bin/bash
# AgentBox CLI setup script
# Installs the agentbox CLI tool and initializes with a token

set -e

# Check if agentbox is already installed
if command -v agentbox &> /dev/null; then
    echo "agentbox CLI is already installed."
    agentbox status 2>/dev/null || true
    exit 0
fi

# Find the repo root (look for pyproject.toml)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
    echo "Error: Cannot find pyproject.toml. Run this from the agentbox repo."
    exit 1
fi

echo "Installing agentbox CLI..."
pip install "$REPO_ROOT"

echo ""
echo "Initializing agentbox..."
agentbox init

echo ""
echo "Setup complete! Try: agentbox status"
