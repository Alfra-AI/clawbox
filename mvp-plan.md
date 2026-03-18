# AgentBox MVP Implementation Plan (v0)

## Overview

A minimal cloud file system for agents with three core pillars: file storage, frictionless token-based auth, and semantic search.

---

## API Surface (v0)

| Endpoint          | Method | Description                        |
| ----------------- | ------ | ---------------------------------- |
| `/get_token`      | POST   | Get a free token with 10 MB quota  |
| `/files/upload`   | POST   | Upload a file                      |
| `/files/{id}`     | GET    | Download a file                    |
| `/files`          | GET    | List files for the token           |
| `/files/{id}`     | DELETE | Delete a file                      |
| `/search`         | POST   | Semantic search across files       |

All endpoints (except `get_token`) require `Authorization: Bearer <token>`.


## Tech Stack

### v0.0 — Local Development

- **API Server**: FastAPI (Python)
- **File Storage**: Local filesystem (files stored in a data directory, namespaced per token)
- **Database**: Local PostgreSQL with pgvector extension (metadata, tokens, and vector search)
- **Embeddings**: OpenAI Embeddings API

### v0 — Cloud Deployment

- **API Server**: FastAPI on AWS (EC2/ECS)
- **File Storage**: AWS S3
- **Database**: PostgreSQL on AWS RDS with pgvector extension
- **Embeddings**: OpenAI Embeddings API

---

## 1. File Storage (Upload & Download)

Storage backend is abstracted so the same API works locally (filesystem) and in production (S3).

### Core Operations

- **Upload** — store a file with a name and optional metadata
- **Download** — retrieve a file by ID or path
- **List** — enumerate files under a token/account
- **Delete** — remove a file

### File Metadata

Each file tracks at minimum:
- File ID (unique identifier)
- Filename / path
- Content type (MIME)
- Size (bytes)
- Created / updated timestamps

### Storage Backend

- **v0.0 (local)**: Files stored on local filesystem under `./data/{token_id}/`
- **v0 (cloud)**: AWS S3 with files namespaced per token; presigned URLs for direct upload/download
- Storage backend selected via configuration, API contract stays the same

---

## 2. Token-Based Account Management

Zero-friction onboarding — no signup, no email, no OAuth.

### `get_token` API

- Any agent calls `get_token` and receives a unique token
- Token grants **10 MB** of free storage
- No authentication required to obtain a token
- Token is the sole credential for all subsequent API calls

### Token Properties

- Unique, unguessable (e.g., UUID v4 or similar)
- Tracks: total storage used, storage limit, created timestamp
- Stateless validation via DB lookup on each request

### Future Expansion

- Official account registration (email/OAuth) for larger storage quotas
- Token upgrade path — link an anonymous token to a registered account
- Paid tiers with configurable limits

### Abuse Prevention

- Rate limit `get_token` calls (e.g., per IP)
- Basic rate limiting on all API endpoints per token
- Monitor for token farming patterns

---

## 3. Semantic Search

Enable agents to search stored files by meaning, not just filename.

### Vector Database

- PostgreSQL with pgvector extension (local in v0.0, RDS in v0)
- On file upload, extract text content and generate embeddings
- Store embeddings indexed by file ID and token

### Search API

- **`search(query, token)`** — returns ranked list of files matching the semantic query
- Results include file metadata + relevance score
- Scoped to the caller's token (agents only search their own files)

### Supported File Types (v0)

- Plain text, Markdown, JSON, CSV
- Future: PDF, images (via OCR/captioning), code files

---

## v0.0 Implementation Details

### Project Structure

```
mvp/
├── __init__.py          # Package init, version
├── main.py              # FastAPI app entry point
├── config.py            # Settings (env vars via pydantic-settings)
├── database.py          # SQLAlchemy engine, session, init_db()
├── models.py            # Token, File, FileEmbedding models
├── auth.py              # Bearer token authentication dependency
├── storage.py           # StorageBackend ABC + LocalStorageBackend
├── embeddings.py        # OpenAI embeddings, chunking, vector search
└── routes/
    ├── tokens.py        # POST /get_token
    ├── files.py         # CRUD /files/*
    └── search.py        # POST /search
```

### Database Schema

**tokens**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| storage_used_bytes | BIGINT | Current usage |
| storage_limit_bytes | BIGINT | Quota (default 10MB) |
| created_at | TIMESTAMP | Creation time |

**files**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| token_id | UUID | Foreign key to tokens |
| filename | VARCHAR(255) | Original filename |
| content_type | VARCHAR(100) | MIME type |
| size_bytes | BIGINT | File size |
| storage_path | VARCHAR(512) | Path in storage backend |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

**file_embeddings**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| file_id | UUID | Foreign key to files |
| chunk_index | INT | Chunk position in file |
| chunk_text | TEXT | Original text chunk |
| embedding | VECTOR(1536) | OpenAI embedding |
| created_at | TIMESTAMP | Creation time |

### Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | postgresql://agentbox:agentbox@localhost:5432/agentbox | PostgreSQL connection |
| STORAGE_BACKEND | local | "local" or "s3" |
| LOCAL_STORAGE_PATH | ./data | Local file storage directory |
| DEFAULT_STORAGE_LIMIT_BYTES | 10485760 | 10 MB default quota |
| OPENAI_API_KEY | (required for search) | OpenAI API key |
| EMBEDDING_MODEL | text-embedding-3-small | OpenAI embedding model |
| HOST | 0.0.0.0 | Server host |
| PORT | 8000 | Server port |

### Dependencies

- **fastapi** - Web framework
- **uvicorn** - ASGI server
- **sqlalchemy** - ORM
- **psycopg2-binary** - PostgreSQL driver
- **pgvector** - Vector extension for SQLAlchemy
- **openai** - Embeddings API
- **pydantic-settings** - Configuration management
- **python-multipart** - File upload support

---

