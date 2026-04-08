# Mount — ClawBox as a Local Folder

## Problem
Users want to interact with ClawBox files using native OS tools (Finder, Explorer, terminal) without going through the web UI or CLI commands.

## Concept
Mount ClawBox as a local folder. `~/clawbox` behaves like a normal directory — all file operations transparently map to API calls.

```bash
agentbox mount ~/clawbox
# Now use it like any folder
cp report.pdf ~/clawbox/docs/
open ~/clawbox/docs/report.pdf
ls ~/clawbox/
```

## Operation Mapping

| FS Operation | API Call |
|-------------|----------|
| `ls dir/` | `GET /files?folder=/dir/` |
| `cp file dir/` | `POST /files/upload` with path |
| `open file` | `GET /files/{id}` (download + cache) |
| `rm file` | `DELETE /files/{id}` |
| `mv a b` | `PATCH /files/{id}` with new path |
| `mkdir dir/` | Implicit (created on first file upload) |

## Approach A: FUSE (fusepy)

Python FUSE adapter that maps filesystem operations to ClawBox API calls.

**Pros:**
- Same language as CLI, ships as part of `agentbox` package
- Full control over behavior
- ~200 lines of FUSE adapter code

**Cons:**
- macOS requires macFUSE (kernel extension) — Apple has been restricting these
- No Windows support without WinFsp
- Must handle caching, retries, error mapping ourselves

**Dependencies:**
- `fusepy` (Python)
- macFUSE (macOS) or native FUSE (Linux)

## Approach B: rclone Backend

Write an rclone remote backend for ClawBox. Users mount via rclone.

```bash
rclone config  # add clawbox remote
rclone mount clawbox: ~/clawbox
```

**Pros:**
- rclone handles caching, retries, VFS layer, cross-platform
- Well-tested mounting infrastructure
- Users may already have rclone installed
- Works on macOS, Linux, Windows

**Cons:**
- Backend must be written in Go (rclone's language)
- Or use rclone's HTTP/WebDAV backend with a WebDAV adapter on our side
- Extra dependency for users

## Approach C: WebDAV Server

Add a WebDAV endpoint to the ClawBox API. Users mount via native OS support.

```bash
# macOS — mount via Finder: Go → Connect to Server
# URL: https://clawbox.ink/webdav/

# Linux
mount -t davfs https://clawbox.ink/webdav/ ~/clawbox
```

**Pros:**
- No client-side dependencies (OS-native WebDAV support)
- Works on macOS, Linux, Windows out of the box
- Single implementation on the server side

**Cons:**
- WebDAV protocol is complex (PROPFIND, PROPPATCH, LOCK, etc.)
- macOS Finder WebDAV is notoriously buggy/slow
- Need to implement enough of the spec to satisfy OS clients

## Recommendation

**WebDAV** is the most user-friendly (zero client install), but the protocol is complex.

**rclone with HTTP backend** is the most practical — we add a few API endpoints that match rclone's expected format, and rclone does the rest.

**FUSE** gives the most control but has the worst platform story (macFUSE restrictions).

For MVP: start with **rclone HTTP backend** or **WebDAV**. Defer FUSE unless there's strong demand.

## Caching Strategy (applies to all approaches)

- **Read cache:** Store downloaded files in `~/.agentbox/cache/` with TTL (5 min default)
- **Write-through:** Uploads happen immediately (no local buffering)
- **Cache invalidation:** On `ls`, check file `updated_at` against cache timestamp
- **Max cache size:** Configurable, default 500 MB, LRU eviction

## Effort Estimate

| Approach | Effort |
|----------|--------|
| FUSE (fusepy) | Medium (2-3 days) |
| rclone backend | Medium-High (3-4 days, Go required) |
| WebDAV server | High (4-5 days, protocol complexity) |

## Future
- Selective sync (only mount specific folders)
- Offline mode (queue uploads when disconnected)
- Real-time sync (WebSocket for file change notifications)
