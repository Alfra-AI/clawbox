---
name: agent-memory
version: 1.0.0
description: Persistent cross-machine memory for AI agents using ClawBox semantic search. Use this skill on session start to load context, during conversation when past knowledge would help, and on compaction to save learnings. Triggers on "remember", "what do I know about", "save this", "memory", "recall", "what did we do last time", "continue where we left off", "update memory", or any context that benefits from past session knowledge.
---

# Agent Memory

Persistent, semantic memory for AI agents. Memories are stored in ClawBox and retrieved by meaning — not keywords.

## How It Works

Memories are files stored in ClawBox under `/memory/`, organized by type:
- `/memory/what/` — project state, objectives, progress
- `/memory/how/` — tool patterns, problem-solving approaches
- `/memory/sessions/` — session records for resumability
- `/memory/artifacts/` — reusable scripts, queries, docs

Retrieval uses ClawBox's semantic search — ask "what do I know about auth?" and get ranked results by meaning.

## Prerequisites

The `agentbox` CLI must be installed and initialized:
```bash
pip install .  # from the agentbox repo
agentbox init  # gets a token
```

Check with `agentbox status`. If not configured, run the setup script:
```bash
bash AgentMemorySkill/scripts/setup-memory.sh
```

## Session Start

On every session start, proactively load relevant context:

```bash
# See what projects are tracked
agentbox list --folder /memory/what/

# Search for context relevant to current work
agentbox search "topic the user is working on"
```

Download and read any relevant memory files to inform your responses.

## During Conversation

When past context would help, search memory:

```bash
agentbox search "the specific topic"
```

Download the top result and read it. Memory search is semantic — natural language queries work well.

## Writing Memory

Write when you learn something significant. **Always** write on compaction.

### Write procedure
1. Search if a memory on this topic already exists
2. If exists: download → update → re-upload to same path
3. If new: create file → upload to appropriate folder

Use the memory CLI commands:
```bash
agentbox memory save what project-name "content here"
agentbox memory save session "session title" "content here"
agentbox memory save how topic-name "content here"
```

Or upload files directly:
```bash
agentbox upload /tmp/memory-file.md --path /memory/what/project.md
```

### On compaction (CRITICAL — do this before context is lost)
1. Save session record → `/memory/sessions/<date>_<title>.md`
2. Update project state → `/memory/what/<project>.md`
3. Save reflections → `/memory/how/<topic>.md`

For detailed memory file formats, read `AgentMemorySkill/references/memory-format.md`.
For the full CLAUDE.md snippet to add to any project, read `AgentMemorySkill/references/claude-md-snippet.md`.
