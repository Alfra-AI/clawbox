# Agent Memory (ClawBox)

You have persistent, cross-machine memory powered by ClawBox. Use it proactively — the user should never need to ask you to check or save memory.

## Setup

If `agentbox` CLI is not configured, run:
```bash
agentbox init  # connects to clawbox.ink, gets a token
```

## Reading Memory

**On every session start**, check what you know:
```bash
agentbox search "current project status"
agentbox list --folder /memory/what/ --recursive
```

**During conversation**, when context would help:
```bash
agentbox search "the topic being discussed"
```

Then download and read the relevant file:
```bash
agentbox download <file_id> --output /tmp/mem.md && cat /tmp/mem.md
```

Search is semantic — ask by meaning, not keywords. "auth issues we hit last week" works as well as "authentication bug".

## Writing Memory

Write whenever you learn something significant. Always write on compaction (before context is lost).

### Folders

| Folder | What goes there | When to write |
|--------|----------------|---------------|
| `/memory/what/<project>.md` | Project state, objectives, progress, key code paths, blockers | When project state changes |
| `/memory/how/<topic>.md` | Tool patterns, problem-solving approaches, meta-reflections | When you learn a better way |
| `/memory/sessions/<date>_<title>.md` | Session record — what was done, decisions, next steps | On compaction or session end |
| `/memory/artifacts/<project>/<file>` | Reusable scripts, queries, docs, data | When creating reusable content |

### Write Procedure

1. Search for existing memory on the topic:
   ```bash
   agentbox search "topic"
   ```
2. If found: download → update content → re-upload to same path:
   ```bash
   agentbox download <id> --output /tmp/mem.md
   # Edit /tmp/mem.md
   agentbox upload /tmp/mem.md --path /memory/what/project.md
   ```
3. If not found: create new file → upload:
   ```bash
   # Write content to /tmp/new-memory.md
   agentbox upload /tmp/new-memory.md --path /memory/what/new-project.md
   ```

### On Compaction (ALWAYS do this)

Before context is lost, save three things:

1. **Session record** — faithful account of what happened:
   ```bash
   agentbox upload /tmp/session.md --path /memory/sessions/$(date +%Y-%m-%d)_<title>.md
   ```

2. **Project state** — update the relevant project file in `/memory/what/`

3. **Reflections** — what worked, what didn't, in `/memory/how/`

## Memory File Format

### Project file (`/memory/what/project.md`)
```markdown
# Project Name

## Objective
What we're trying to achieve

## Background
Domain knowledge, why this matters

## Current State
What's done, what's in progress, what's blocked

## Key Code Paths
- `path/to/important/file.py` — what it does
- `path/to/another.py` — what it does

## Artifacts
- [deploy checklist](/memory/artifacts/project/deploy-checklist.md)
- [benchmark query](/memory/artifacts/project/benchmark.sql)
```

### Session file (`/memory/sessions/date_title.md`)
```markdown
# Session: Title

**Date:** 2026-04-10
**Project:** Link to /memory/what/project.md

## What was accomplished
- Did X
- Decided Y because Z

## Current state
Where things stand right now

## Next steps
1. Do A
2. Then B

## Open questions
- Unresolved issue about X
```

### Reflection file (`/memory/how/topic.md`)
```markdown
# Topic

## What works
- Approach A is effective because...

## What doesn't work
- Approach B fails when...

## Lessons
- Always do X before Y because...
```
