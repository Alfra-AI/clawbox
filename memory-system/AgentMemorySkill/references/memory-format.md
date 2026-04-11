# Memory File Formats

## Project File (`/memory/what/<project>.md`)

```markdown
# Project Name

## Objective
What we're trying to achieve and why

## Background
Domain knowledge, context, constraints

## Current State
- **Status:** active / paused / completed
- **Last updated:** 2026-04-10
- What's done, in progress, and blocked

## Key Code Paths
- `path/to/file.py` — what it does and why it matters
- `path/to/config.yaml` — important configuration

## Tasks
- [x] Completed task
- [ ] In-progress task
- [ ] Blocked task (blocked by: reason)

## Key Decisions
- Chose X over Y because Z
- Trade-off: accepted A to gain B

## Artifacts
- [Deploy script](/memory/artifacts/project/deploy.sh)
- [Benchmark results](/memory/artifacts/project/benchmark.md)

## Open Questions
- Unresolved issue about X
```

## Session File (`/memory/sessions/<date>_<title>.md`)

The goal: a new agent reading this file should be able to **seamlessly continue** the work.

```markdown
# Session: Descriptive Title

**Date:** 2026-04-10
**Project:** project-name (see /memory/what/project.md)

## Context
What the user was trying to accomplish and why. Enough background for pickup.

## What Was Accomplished
- Implemented feature X
- Fixed bug in Y
- Decided to use approach Z

## Key Decisions
- Chose library A because B
- Deferred feature C until D

## Current State
Where things stand right now. What file is open, what's the next step.

## Next Steps
1. Immediate next action
2. Then this
3. After that

## Artifacts Created
- `/memory/artifacts/project/script.py` — helper for X

## Open Questions / Blockers
- Need to figure out X before proceeding
- Waiting on Y from user
```

## Reflection File (`/memory/how/<topic>.md`)

Agent self-improvement — what works, what doesn't.

```markdown
# Topic Name

## What Works
- Strategy A is effective for problem type X because...
- Tool Y is best when Z

## What Doesn't Work
- Approach A fails when B — use C instead
- Don't do X before Y because...

## Patterns
- When seeing error type A, always check B first
- For performance issues, start with C not D

## Lessons Learned
- Specific insight from experience
- Another insight with context
```

## Artifacts (`/memory/artifacts/<project>/<file>`)

Raw reusable files — not descriptions, the actual content:
- `.sql` — database queries
- `.py` — scripts and utilities
- `.sh` — shell scripts
- `.md` — docs, reports, checklists
- `.json` — config, data snapshots

Keep artifacts small and self-contained. Memory files in `what/` and `sessions/` should **point to** artifacts, not inline them.
