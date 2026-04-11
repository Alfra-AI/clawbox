# Async Upload & Download — Design Doc

## Problem

Large file uploads (>10 MB) block the HTTP connection. The user or agent waits for:
1. File transfer to complete
2. File to be saved to storage
3. Embeddings to be generated

For a 100 MB file, this can take 30+ seconds. Agents shouldn't sit idle waiting.

## Proposed Solution: Background Processing

### Upload Flow (Current vs Proposed)

**Current (synchronous):**
```
Client → POST /files/upload → [save to storage] → [generate embeddings] → 200 OK
         ←————————————— blocks for entire duration ——————————————→
```

**Proposed (async):**
```
Client → POST /files/upload → [save to storage] → 202 Accepted (immediate)
                                                    ↓
                               Background worker → [generate embeddings]
                                                    ↓
Client → GET /files/{id}    → status: "processing" | "ready"
```

### Key Changes

#### 1. Split upload into two phases

**Phase 1 (synchronous, fast):** Receive file, save to storage, create DB record. Return `202 Accepted` with file ID immediately.

**Phase 2 (background):** Generate embeddings asynchronously. Client can poll the file status or just proceed — embeddings aren't needed for download.

```python
@router.post("/files/upload", status_code=202)
async def upload_file(...):
    # Save file to storage (fast)
    # Create DB record with embedding_status="pending"
    # Queue embedding job (background)
    return {"id": file_id, "status": "pending"}
```

#### 2. Background embedding worker

Options:
- **Simple (MVP):** `asyncio.create_task()` in the same process. No extra infrastructure.
- **Robust:** Celery/Redis task queue. Separate worker process. Retries, monitoring.
- **Serverless:** AWS Lambda triggered by S3 event. Scales to zero.

For MVP, `asyncio.create_task()` is sufficient:

```python
import asyncio

async def upload_file(...):
    # ... save file ...
    asyncio.create_task(generate_embeddings_background(file_id))
    return {"id": file_id, "status": "pending"}
```

#### 3. Presigned URLs for large uploads

For files >50 MB, skip the server entirely:

```
Client → GET /files/upload-url → {presigned_url, file_id}
Client → PUT presigned_url      → (direct to S3, no server bottleneck)
Client → POST /files/confirm    → (server creates DB record, queues embedding)
```

This requires S3/MinIO storage backend. Not applicable for local storage.

#### 4. Chunked/resumable uploads (future)

For very large files or unreliable connections:
- Use `tus.io` protocol for resumable uploads
- Or implement multipart upload with progress tracking

### Download Flow

Downloads are already fast for small files. For large files:

#### Presigned download URLs

```
Client → GET /files/{id}/url → {download_url, expires_in: 3600}
Client → GET download_url    → (direct from S3, no server proxy)
```

Benefits:
- Server doesn't proxy large files through memory
- CDN-friendly (can put CloudFront in front of S3)
- Supports range requests (resume interrupted downloads)

#### Streaming downloads (current improvement)

Instead of loading the entire file into memory:

```python
from fastapi.responses import StreamingResponse

@router.get("/files/{id}")
async def download_file(...):
    stream = await storage.stream(file_record.storage_path)
    return StreamingResponse(stream, media_type=content_type)
```

### API Changes

| Endpoint | Change |
|----------|--------|
| `POST /files/upload` | Return `202` immediately, embed in background |
| `GET /files/{id}` | Add `status` field: `pending` / `ready` |
| `GET /files/{id}/url` | New: presigned download URL (S3 only) |
| `GET /files/upload-url` | New: presigned upload URL (S3 only) |
| `POST /files/confirm` | New: confirm presigned upload |

### Implementation Priority

| Phase | What | Effort |
|-------|------|--------|
| 1. Background embedding | `asyncio.create_task()` for embeddings | Low (1 hour) |
| 2. Streaming downloads | `StreamingResponse` instead of loading into memory | Low (1 hour) |
| 3. Presigned download URLs | Direct S3 download links | Medium (half day) |
| 4. Presigned upload URLs | Direct S3 upload, skip server | Medium (half day) |
| 5. Resumable uploads | tus.io or multipart | High (2-3 days) |

### Phase 1 is the quick win — just move embedding generation to a background task. The upload returns instantly and the agent can continue working.
