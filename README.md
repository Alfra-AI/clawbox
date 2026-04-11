<p align="center">
  <h1 align="center">ClawBox</h1>
  <p align="center">
    Open-source cloud file system for AI agents<br>
    Semantic search &bull; Folders &bull; File sharing &bull; Self-hostable
  </p>
  <p align="center">
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
    <a href="https://clawbox.ink"><img src="https://img.shields.io/badge/demo-clawbox.ink-00d4ff.svg" alt="Live Demo"></a>
    <a href="docs/self-hosting.md"><img src="https://img.shields.io/badge/self--host-docker%20compose-green.svg" alt="Self-Host"></a>
  </p>
  <p align="center">
    <a href="https://clawbox.ink">Live Demo</a> &bull;
    <a href="docs/self-hosting.md">Self-Host Guide</a>
  </p>
</p>

---

## What is ClawBox?

ClawBox is an open-source file storage platform built for AI agents. Upload files, search by meaning, organize into folders, and share with anyone &mdash; all via API or CLI.

**For agents:** Store files, search by meaning, organize into folders &mdash; all via API.

**For humans:** Upload files, get a share link, search across documents. Like a smarter Dropbox with an API-first design.

### Key Features

| Feature | Description |
|---------|-------------|
| **Semantic Search** | Search files by meaning, not keywords. Powered by Gemini embeddings. |
| **Multimodal** | Index text, PDF, Word, Excel, PowerPoint, CSV, images, audio, video. |
| **Virtual Folders** | Organize files with paths like `/docs/reports/q1.pdf`. |
| **File Sharing** | Generate share links &mdash; anyone with the link can download. |
| **Google Login** | Sign in with Google for 10 GB storage (1 GB free without login). |
| **Self-Hostable** | `docker compose up` &mdash; runs on your laptop, office server, or cloud. |

---

## Quick Start

### Option 1: Docker (recommended)

```bash
git clone https://github.com/Alfra-AI/agentbox.git
cd agentbox
cp .env.example .env       # Edit to add your Google API key for search
docker compose up
```

ClawBox is running at **http://localhost:8000**.

### Option 2: Use the hosted version

No setup needed &mdash; just visit **[clawbox.ink](https://clawbox.ink)**.

### Option 3: CLI

```bash
pip install .
agentbox init                    # Get a token
agentbox upload report.pdf       # Upload
agentbox search "quarterly revenue"  # Semantic search
```

---

## API

All endpoints (except public ones) require `Authorization: Bearer <token>`.

### Core

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /get_token` | POST | No | Get a free token (1 GB storage) |
| `POST /files/upload` | POST | Yes | Upload a file (with optional `path` for folders) |
| `GET /files` | GET | Yes | List files (filter by `folder`, `recursive`) |
| `GET /files/{id}` | GET | Yes | Download a file |
| `PATCH /files/{id}` | PATCH | Yes | Move/rename a file |
| `DELETE /files/{id}` | DELETE | Yes | Delete a file |
| `POST /search` | POST | Yes | Semantic search across files |
| `POST /files/embed` | POST | Yes | Generate/retry embeddings |

### Sharing

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /files/{id}/share` | POST | Yes | Create a share link |
| `GET /s/{code}` | GET | No | Download via share link |

### Auth

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /auth/google` | GET | Start Google OAuth login |
| `GET /auth/me` | GET | Get current user info |

---

## Supported File Formats

| Format | Search Support |
|--------|---------------|
| Text, Markdown, JSON, XML, CSV | Full text extraction |
| PDF | pdfplumber |
| Word (.docx) | python-docx |
| Excel (.xlsx) | openpyxl |
| PowerPoint (.pptx) | python-pptx |
| Images (PNG, JPEG, GIF, WebP) | Gemini multimodal + captioning |
| Audio, Video | Gemini multimodal embedding |

---

## Self-Hosting

### Single Server

```bash
docker compose up
```

### With MinIO (S3-Compatible Storage)

```bash
docker compose -f docker-compose.cluster.yml up
```

### Any Cloud

ClawBox works with any S3-compatible storage. Set `S3_ENDPOINT_URL`:

| Provider | S3_ENDPOINT_URL |
|----------|-----------------|
| AWS S3 | (leave empty) |
| MinIO | `http://minio:9000` |
| GCS | `https://storage.googleapis.com` |
| DigitalOcean Spaces | `https://{region}.digitaloceanspaces.com` |
| Cloudflare R2 | `https://{account_id}.r2.cloudflarestorage.com` |

See [Self-Hosting Guide](docs/self-hosting.md) for details.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `S3_ENDPOINT_URL` | (empty) | S3-compatible endpoint |
| `GOOGLE_API_KEY` | (empty) | Gemini API key (enables search) |
| `GOOGLE_CLIENT_ID` | (empty) | Google OAuth (enables login) |
| `SESSION_SECRET_KEY` | `change-me` | Session signing (change in prod) |
| `APP_URL` | `http://localhost:8000` | Public URL for share links |

See [.env.example](.env.example) for all options.

---

## Architecture

```
┌─────────────────────────┐
│     Web UI / CLI        │
└────────┬────────────────┘
         │ HTTP API
┌────────┴────────────────┐
│     FastAPI Server      │
│  (stateless, scalable)  │
└────────┬────────────────┘
         │
    ┌────┴────┐
    │         │
┌───┴───┐ ┌──┴──────────┐
│ PostgreSQL │ │ Object Storage │
│ (pgvector) │ │ (Local/S3/MinIO)│
└────────┘ └─────────────┘
```

- **PostgreSQL + pgvector** &mdash; metadata, users, embeddings, search
- **Object storage** &mdash; file content (local filesystem, S3, MinIO, GCS, etc.)
- **Gemini** &mdash; embeddings + multimodal indexing (optional)

---

## Project Structure

```
mvp/
├── main.py           # FastAPI app, routing, middleware
├── config.py         # Settings from environment
├── models.py         # SQLAlchemy models
├── auth.py           # Bearer token authentication
├── storage.py        # Storage backend (local/S3)
├── embeddings.py     # Gemini embeddings + text extraction
├── database.py       # Database connection
├── cli.py            # CLI tool (agentbox command)
├── routes/
│   ├── tokens.py     # Token management + settings
│   ├── files.py      # File CRUD + sharing + folders
│   ├── search.py     # Semantic search
│   └── oauth.py      # Google OAuth
└── static/
    └── index.html    # Web UI
```

---

## Contributing

Contributions are welcome! Please open an issue or submit a PR.

```bash
git clone https://github.com/Alfra-AI/agentbox.git
cd agentbox
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
docker compose up -d  # Start PostgreSQL
python -m mvp.main    # Start dev server
```

---

## License

[MIT](LICENSE)
