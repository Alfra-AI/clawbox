# Quick Drop - Ephemeral File Sharing

## Problem
AirDrop doesn't work cross-platform. Sometimes you just want to send a file to someone (or yourself on another device) without it living in cloud storage forever.

## Concept
Upload a file, get a short link. The file auto-deletes after download or expiry. No account needed.

## Key Design Decisions

### Link Format
- `https://clawbox.ink/d/<code>` — short 6-character alphanumeric code
- Easy to type on another device, share via chat, or display as QR code
- Example: `clawbox.ink/d/x7Km9p`

### Expiry Rules
- Default: expires after **first download** OR **24 hours**, whichever comes first
- Options at upload time:
  - `burn_after_read: true` (default) — deleted after first download
  - `expires_in: 3600` — custom TTL in seconds (max 7 days)
  - `max_downloads: 5` — allow multiple downloads before expiry

### Storage
- Files stored in S3 with lifecycle policy as safety net
- Separate S3 prefix (`drops/`) from persistent files
- No embeddings generated (not searchable)
- **No token required** to upload or download — friction-free

### Size Limits
- Max 100 MB per drop (larger than the 10 MB token quota since it's ephemeral)
- Rate limit: 10 drops per hour per IP

## Schema

```sql
CREATE TABLE drops (
    id UUID PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    burn_after_read BOOLEAN DEFAULT true,
    max_downloads INTEGER DEFAULT 1,
    download_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT now(),
    created_by_ip VARCHAR(45)  -- for rate limiting
);
CREATE INDEX ix_drops_code ON drops (code);
CREATE INDEX ix_drops_expires_at ON drops (expires_at);
```

## API

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/drop` | POST | None | Upload a file, returns `{code, url, expires_at}` |
| `/d/<code>` | GET | None | Download page (shows filename, size, download button) |
| `/d/<code>/download` | GET | None | Direct file download |

## Web UI
- New "Quick Drop" tab/section on the homepage
- Drag & drop zone (separate from persistent upload)
- After upload: shows the short link + QR code + "Copy Link" button
- Download page: clean, minimal — filename, size, big download button

## Cleanup
- Background task (or cron) deletes expired drops every 5 minutes
- S3 lifecycle policy as backup (delete objects in `drops/` older than 8 days)

## Future
- Optional password protection
- End-to-end encryption (encrypt in browser, key in URL fragment)
- Drop history for logged-in users
