#!/bin/bash
# ClawBox CLI setup script
# Installs the clawbox CLI tool and initializes with a token

set -e

if command -v clawbox &> /dev/null; then
    echo "clawbox CLI is already installed."
    clawbox status 2>/dev/null || true
    exit 0
fi

echo "Installing clawbox CLI..."
if command -v pipx &> /dev/null; then
    pipx install clawbox
elif command -v pip3 &> /dev/null; then
    pip3 install clawbox
elif command -v pip &> /dev/null; then
    pip install clawbox
elif command -v python3 &> /dev/null; then
    python3 -m pip install clawbox
else
    echo "Error: no Python package installer found." >&2
    echo "Install Python 3 first: https://www.python.org/downloads/" >&2
    exit 1
fi

echo ""
echo "Initializing clawbox..."
clawbox init

echo ""
echo "Setup complete! Try: clawbox status"
