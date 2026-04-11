# Agent Memory System — Built on ClawBox

**Author:** Benny Jiang
**Date:** 2026-04-10
**Status:** Design

---

## 1. Motivation

AI coding agents (Claude Code, Cursor, Codex, etc.) lose context between sessions. Built-in memory systems are project-path-scoped — memories don't follow you across machines, checkouts, or tools.

Benny previously built a global memory system using Meta's Manifold (internal object storage). It worked, but had limitations:
- **Keyword-based retrieval**: MEMORY.md index with manual keywords — fragile, requires maintenance
- **No search**: Can't ask "what did I learn about auth?" — must scan keywords or read files
- **Corporate-locked**: Manifold is Meta-internal, not portable

**ClawBox solves all three:**
- **Semantic search**: Ask "what do I know about auth migration?" and get the right memory file
- **Self-hostable**: Runs anywhere — laptop, office server, cloud
- **Open source**: Anyone can use it, not locked to one company

## 2. Architecture

```
┌─────────────────────────────────────────────┐
│              AI Agent (Claude, etc.)         │
│                                             │
│  CLAUDE.md instructions tell agent:         │
│  • Load memory index on session start       │
│  • Search memories semantically when needed │
│  • Write memories on learning/compaction    │
│  • Use folders for organization             │
└──────────────┬──────────────────────────────┘
               │ agentbox CLI / HTTP API
               ▼
┌─────────────────────────────────────────────┐
│              ClawBox Server                  │
│                                             │
│  /memory/what/       — Projects & tasks     │
│  /memory/how/        — Agent reflections    │
│  /memory/sessions/   — Session records      │
│  /memory/artifacts/  — Reusable content     │
│                                             │
│  Semantic Search ←── Gemini embeddings      │
│  Folder System   ←── Virtual paths          │
│  File Sharing    ←── Share links            │
└─────────────────────────────────────────────┘
```

**Key difference from Manifold version:** No MEMORY.md keyword index needed. The agent just searches ClawBox semantically to find relevant memories. This eliminates the maintenance burden and makes retrieval more accurate.

## 3. Storage Layout

All memories stored in ClawBox under the `/memory/` folder tree:

```
/memory/
  what/                              # Projects & Tasks
    auth-migration.md
    clawbox-mvp.md

  how/                               # Agent Reflections
    tools.md                         # Tool usage patterns
    approaches.md                    # Problem-solving strategies

  sessions/                          # Session Records
    2026-04-10_agent-memory-design.md

  artifacts/                         # Raw reusable content
    auth/
      migration-script.sql
    clawbox/
      deploy-checklist.md
```

No separate local cache or sync protocol needed — ClawBox IS the persistent store. The agent reads/writes directly via the API.

## 4. Memory Operations

### 4.1 Read: Semantic Retrieval

**Old way (Manifold):**
```
1. Load MEMORY.md index into context
2. Match keywords against conversation
3. Read the matching file
```

**New way (ClawBox):**
```
1. Agent searches: agentbox search "auth migration progress"
2. ClawBox returns ranked results with relevance scores
3. Agent reads the top-matching memory file
```

The semantic search replaces the entire keyword index system. No MEMORY.md to maintain. The agent just asks ClawBox "what do I know about X?" and gets the answer.

### 4.2 Write: Memory Creation & Updates

On every write, update the relevant dimension:

| Dimension | Folder | What to write |
|-----------|--------|---------------|
| **What** | `/memory/what/` | Project objectives, progress, code paths, blockers |
| **How** | `/memory/how/` | Tool patterns, problem-solving reflections |
| **Sessions** | `/memory/sessions/` | Faithful session record for resumability |
| **Artifacts** | `/memory/artifacts/` | Reusable queries, scripts, docs |

**Write triggers:**
1. On compaction (forced — context about to be lost)
2. User says "save/update memory"
3. Proactively when the agent learns something significant

**Write procedure:**
1. Search ClawBox for existing memory on the topic
2. If found → download, update, re-upload
3. If not found → create new file, upload to appropriate folder

### 4.3 Session Lifecycle

**Session start:**
```bash
# Agent checks what memories exist
agentbox list --folder /memory/ --recursive

# If relevant to current work, search for context
agentbox search "the topic we're working on"
```

**During session:**
- Agent searches memory when context would help
- Agent writes memories when learning something new

**Session end / compaction:**
- Write session record to `/memory/sessions/`
- Update project file in `/memory/what/`
- Reflect on approaches in `/memory/how/`

## 5. Advantages over Manifold Version

| Aspect | Manifold Version | ClawBox Version |
|--------|-----------------|-----------------|
| **Retrieval** | Keyword matching in MEMORY.md index | Semantic search — "what do I know about X?" |
| **Index maintenance** | Manual — must update MEMORY.md on every write | None — search replaces the index |
| **Sync protocol** | Complex 4-step sync with etag detection | None — single source of truth, direct API |
| **Local cache** | Required for performance | Not needed — API calls are fast enough |
| **Cross-machine** | Requires Manifold access (corporate VPN) | Works anywhere — self-hostable |
| **Sharing** | Not supported | Share memories via links |
| **Setup** | Install Manifold CLI + CLAUDE.md | `pip install agentbox && agentbox init` |
| **Search quality** | Exact keyword match only | Fuzzy, meaning-based (Gemini embeddings) |

## 6. Implementation Plan

### Phase 1: CLAUDE.md Instructions (Day 1)

Write a `CLAUDE.md` snippet that any agent can include:

```markdown
## Memory System

You have a persistent memory system powered by ClawBox.

### Reading memories
- Search: `agentbox search "topic"` — finds relevant memories by meaning
- Browse: `agentbox list --folder /memory/what/` — see all project memories
- Read: `agentbox download <file_id> --output /tmp/memory.md` — load full content

### Writing memories
- Upload: `agentbox upload memory.md --path /memory/what/project-name.md`
- On every significant learning, write to the appropriate folder
- On compaction, write session record + update project files
```

### Phase 2: Memory Skill (Day 2)

Package as a Claude Code skill (`AgentMemorySkill/SKILL.md`) that:
- Auto-triggers on session start (loads recent memories)
- Auto-triggers on compaction (saves session state)
- Provides `/memory` command for manual interaction
- Includes reference docs for the memory structure

### Phase 3: Memory CLI Commands (Day 3)

Add convenience commands to the `agentbox` CLI:

```bash
agentbox memory search "auth migration"     # Semantic search in /memory/
agentbox memory save what project.md        # Upload to /memory/what/
agentbox memory save session today.md       # Upload to /memory/sessions/
agentbox memory list                        # List all memories
agentbox memory recall "last session"       # Search + display
```

### Phase 4: Memory API Endpoints (Optional)

Dedicated endpoints for memory operations:

```
POST /memory/save    — Save a memory (auto-organizes by content)
GET  /memory/recall  — Semantic search across memories
GET  /memory/browse  — List memories by folder
```

The auto-organize feature could classify memories into what/how/sessions automatically using LLM.

## 7. CLAUDE.md Template

The full instruction set for agents:

```markdown
## Agent Memory (ClawBox)

You have persistent, cross-machine memory via ClawBox. Use it proactively.

### Setup (one-time)
agentbox init  # Gets token, connects to clawbox.ink

### Reading (do this on session start + when relevant)
- `agentbox search "topic"` — semantic search across all memories
- `agentbox list --folder /memory/what/ --recursive` — browse project memories
- `agentbox download <id>` — read a specific memory file

### Writing (do this on learning + compaction)
Write to the appropriate folder:
- `/memory/what/<project>.md` — project state, objectives, progress
- `/memory/how/<topic>.md` — tool patterns, approaches, reflections
- `/memory/sessions/<date>_<title>.md` — session record for resumability
- `/memory/artifacts/<project>/<file>` — reusable scripts, queries, docs

Procedure:
1. Search for existing memory on the topic
2. If found: download → update → re-upload (same path)
3. If not found: create new file → upload to appropriate folder

### On compaction (ALWAYS do this)
Before context is lost, save:
1. Session record in /memory/sessions/
2. Updated project state in /memory/what/
3. Reflections in /memory/how/
```

## 8. Design Decisions

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| No local cache | Direct API | Local cache + sync | Eliminates sync complexity. API latency (~100ms) is acceptable for memory ops. |
| No MEMORY.md index | Semantic search | Keyword index | Search is more accurate and requires zero maintenance |
| Same ClawBox token | Shared with files | Separate memory token | Memories are just files — no need for separate auth |
| Folder-based organization | `/memory/what/how/sessions/` | Flat with tags | Folders match the Manifold design, easy to browse |
| agentbox CLI | Reuse existing | Custom memory CLI | Already installed, already has search/upload/download |
