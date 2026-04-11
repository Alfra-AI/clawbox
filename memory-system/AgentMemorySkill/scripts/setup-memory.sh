#!/bin/bash
# Set up AgentBox memory system
# Creates the memory folder structure and verifies connectivity

set -e

# Check if agentbox CLI is available
if ! command -v agentbox &> /dev/null; then
    echo "agentbox CLI not found. Installing..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
    if [ -f "$REPO_ROOT/pyproject.toml" ]; then
        pip install "$REPO_ROOT"
    else
        echo "Error: Cannot find agentbox repo. Install manually: pip install ."
        exit 1
    fi
fi

# Check if initialized
if ! agentbox status &> /dev/null; then
    echo "Initializing agentbox..."
    agentbox init
fi

echo "AgentBox memory system is ready!"
echo ""
echo "Memory folders:"
echo "  /memory/what/      — project state and objectives"
echo "  /memory/how/       — tool patterns and reflections"
echo "  /memory/sessions/  — session records"
echo "  /memory/artifacts/ — reusable scripts and docs"
echo ""
echo "Usage:"
echo "  agentbox memory save what my-project 'Project description...'"
echo "  agentbox memory search 'what do I know about auth?'"
echo "  agentbox memory list"
