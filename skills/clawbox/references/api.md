# ClawBox API Reference

## Authentication

All endpoints except `/get_token`, `/health`, `/drop/*`, and `/s/*` require a bearer token:

```
Authorization: Bearer <token-uuid>
```

## Endpoints

### Tokens

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/get_token` | No | Create anonymous token (10 MB quota) |
| GET | `/settings` | Yes | Get token settings |
| PATCH | `/settings` | Yes | Update settings (e.g., auto_organize) |

### Files

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/files/upload` | Yes | Upload file. Form fields: `file` (required), `path` (optional) |
| GET | `/files` | Yes | List files. Query params: `folder`, `recursive` |
| GET | `/files/{id}` | Yes | Download file |
| PATCH | `/files/{id}` | Yes | Move/rename file. Body: `{"path": "/new/path.txt"}` |
| DELETE | `/files/{id}` | Yes | Delete file |
| POST | `/files/embed` | Yes | Queue embeddings. Body: `{"file_ids": [...]}`, `{"failed_only": true}`, or `{"pending_only": true}` |

### Search

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/search` | Yes | Semantic search. Body: `{"query": "...", "limit": 10}` |

### File Sharing

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/files/{id}/share` | Yes | Create share link. Body: `{"expires_in": 3600, "max_downloads": 5}` |
| GET | `/files/{id}/shares` | Yes | List share links for a file |
| DELETE | `/files/{id}/share/{code}` | Yes | Revoke a share link |
| GET | `/s/{code}` | No | Download via share link |

### Quick Drop (Qdrop)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/drop` | No | Create drop. Form: `text` + `files` |
| GET | `/drop/{code}` | No | Get drop info |
| GET | `/drop/{code}/file/{id}` | No | Download file from drop |

### Auth (Google OAuth)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/auth/google` | No | Start Google login flow |
| GET | `/auth/google/callback` | No | OAuth callback |
| GET | `/auth/me` | Yes | Get current user info |
| GET | `/auth/providers` | No | List available auth providers |

### System

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | No | Health check |

## Batch Embed Response

`POST /files/embed` returns:

```json
{
  "processed": 2,
  "queued": 1,
  "skipped": 1,
  "results": [
    {
      "requested_id": "<uuid>",
      "id": "<uuid>",
      "filename": "report.pdf",
      "embedding_status": "queued",
      "error": null
    },
    {
      "requested_id": "<uuid>",
      "id": "<uuid>",
      "filename": "notes.txt",
      "embedding_status": "processing",
      "error": "already_queued"
    }
  ]
}
```

- `processed` — total result entries returned
- `queued` — jobs newly enqueued by this request
- `skipped` — files that were not enqueued (missing, unsupported, or already queued)
- `results[].error` — one of `already_queued`, `file_not_found`, `unsupported_content_type`, or `null` when the job was freshly enqueued

## File Embedding Status

The `embedding_status` field on a file progresses through:

| Status | Meaning |
|--------|---------|
| `not_applicable` | Content type cannot be embedded |
| `queued` | Waiting for the worker to pick it up |
| `processing` | Worker has leased the job and is running it |
| `completed` | Embeddings are stored and the file is searchable |
| `failed` | Retry budget exhausted; requeue with `/files/embed` |

## Supported File Formats for Search

| Format | MIME Type | Extraction |
|--------|-----------|------------|
| Plain text, Markdown | `text/*` | Direct |
| JSON | `application/json` | Direct |
| XML | `application/xml` | Direct |
| PDF | `application/pdf` | pdfplumber |
| Word (.docx) | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx |
| Excel (.xlsx) | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | openpyxl |
| PowerPoint (.pptx) | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | python-pptx |
| CSV | `text/csv` | csv module |
