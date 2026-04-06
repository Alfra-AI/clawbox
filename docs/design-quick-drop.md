# Qdrop - Ephemeral Text & File Sharing

## Problem
AirDrop doesn't work cross-platform. Sometimes you just want to send a file or text to someone (or yourself on another device) without it living in cloud storage forever.

## Concept
Share text and/or files, get a 4-digit PIN. Receiver enters the PIN to get everything. Expires in 10 minutes. No account needed.

## Status: Implemented & Deployed

**Domain:** www.qdrop.cc
**Branch:** feature/self-hosting (also feature/quick-drop)

### What's Built
- [x] 4-digit numeric PIN (easy to type/say aloud)
- [x] Text sharing (auto-copies to recipient's clipboard)
- [x] Multi-file sharing (up to 200 MB total)
- [x] 10-minute expiry with countdown
- [x] Dedicated UI at /drop (and served at www.qdrop.cc root)
- [x] Send and Receive on one page (no tabs)
- [x] Code shown as fullscreen overlay after sharing
- [x] Mobile-friendly responsive design
- [x] PIN input with auto-advance and paste support
- [x] Auto-download for single file drops
- [x] Host-based routing (qdrop.cc → drop page, clawbox.ink → main app)
- [x] SSL certificate for qdrop.cc on ALB
- [x] DNS configured (www.qdrop.cc → ALB)

### Known Limitations
- **iOS photo conversion:** iOS converts HEIC to JPEG on web upload. This is a system-level limitation affecting all browsers on iOS. Workaround: upload from Files app instead of Photos to preserve original format.
- **iOS photo saving:** Downloads go to Files app, not Photos library. No web API to save directly to Photos. Workaround: display images inline so users can long-press → "Add to Photos".
- **Root domain:** qdrop.cc (without www) doesn't work — NameSilo doesn't support CNAME on root domain. Only www.qdrop.cc works.

### TODO
- [ ] Display received images inline (preview) instead of auto-download — enables long-press → Save to Photos on iOS
- [ ] QR code display alongside PIN code
- [ ] Rate limiting (prevent abuse)
- [ ] Cleanup cron for expired sessions (currently cleaned on next request)
- [ ] End-to-end encryption (encrypt in browser, key in URL fragment)
- [ ] Password-protected drops

## Architecture

### Schema

```sql
CREATE TABLE drop_sessions (
    id UUID PRIMARY KEY,
    code VARCHAR(4) NOT NULL UNIQUE,
    text_content TEXT,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE drop_files (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES drop_sessions(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);
```

### API

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /drop` | POST | None | Create drop (text + files), returns 4-digit code |
| `GET /drop/{code}` | GET | None | Get drop contents (text + file list) |
| `GET /drop/{code}/file/{id}` | GET | None | Download a specific file |

### Limits
- 200 MB total files per session
- 100K characters text per session
- 10-minute expiry
- 4-digit PIN (10,000 combinations — sufficient for 10-min window)

### Files
- `mvp/routes/drops.py` — API routes
- `mvp/models.py` — DropSession, DropFile models
- `mvp/static/drop.html` — Qdrop UI
- `mvp/main.py` — host-based routing for qdrop.cc
- `alembic/versions/20260329_0005_add_drops_table.py` — migration
