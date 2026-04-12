# Self-Hosting ClawBox

## Quick Start (Docker Compose)

Use this flow when you want a local ClawBox server with PostgreSQL and local file
storage.

### Prerequisites

- Docker and Docker Compose

### Steps

```bash
git clone https://github.com/Alfra-AI/clawbox.git
cd clawbox
cp .env.example .env
# Edit .env if you want optional features such as search or Google login
docker compose up -d
docker compose exec app alembic upgrade head
```

ClawBox is then available at **http://localhost:8000**.

If you want to use the CLI against your local server:

```bash
clawbox config --api-url http://localhost:8000
clawbox init
```

### What's included

- PostgreSQL with pgvector
- ClawBox app container
- Local filesystem storage

### Notes

- `docker compose up` does not run Alembic automatically in the current setup.
- Re-run `docker compose exec app alembic upgrade head` after pulling schema changes.
- Add `GOOGLE_API_KEY` to `.env` if you want semantic search and embeddings.

---

## Cluster Setup (with MinIO)

Use this flow when you want S3-compatible object storage through MinIO.

```bash
docker compose -f docker-compose.cluster.yml up -d
docker compose -f docker-compose.cluster.yml exec app alembic upgrade head
```

This stack adds MinIO for file storage. The MinIO console is available at
`http://localhost:9001`.

---

## Cloud Deploy

ClawBox works with any managed PostgreSQL database plus S3-compatible object
storage.

### Required environment

```text
DATABASE_URL=postgresql://user:pass@your-db-host:5432/clawbox
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://your-s3-endpoint
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=your-bucket
GOOGLE_API_KEY=your-gemini-key
```

Leave `S3_ENDPOINT_URL` empty for AWS S3.

| Provider | S3 endpoint |
|----------|-------------|
| AWS S3 | (leave empty) |
| MinIO | `http://minio:9000` |
| GCS | `https://storage.googleapis.com` |
| DigitalOcean Spaces | `https://{region}.digitaloceanspaces.com` |
| Cloudflare R2 | `https://{account_id}.r2.cloudflarestorage.com` |

Apply migrations before serving traffic:

```bash
alembic upgrade head
```

---

## Bare Metal

### Prerequisites

- Python 3.10+
- PostgreSQL with pgvector

### Steps

```bash
git clone https://github.com/Alfra-AI/clawbox.git
cd clawbox
python -m venv venv
source venv/bin/activate
pip install .
cp .env.example .env
# Edit .env with your database and API settings
alembic upgrade head
python -m mvp.main
```

---

## Configuration Notes

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://clawbox:clawbox@localhost:5432/clawbox` | PostgreSQL connection string |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `LOCAL_STORAGE_PATH` | `./data` | Path for local file storage |
| `S3_ENDPOINT_URL` | (empty) | S3-compatible endpoint |
| `S3_BUCKET_NAME` | (empty) | Bucket name when using `s3` |
| `GOOGLE_API_KEY` | (empty) | Enables Gemini-based search and embeddings |
| `GOOGLE_CLIENT_ID` | (empty) | Enables Google login |
| `GOOGLE_CLIENT_SECRET` | (empty) | Google OAuth secret |
| `SESSION_SECRET_KEY` | `change-me-to-a-random-string` | Session signing key |
| `APP_URL` | `http://localhost:8000` | Public base URL |
