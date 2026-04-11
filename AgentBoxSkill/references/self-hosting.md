# Self-Hosting AgentBox

## Quick Start (Docker Compose)

```bash
git clone https://github.com/Alfra-AI/agentbox.git
cd agentbox
cp .env.example .env
docker compose up
```

Server runs at `http://localhost:8000`.

## Cluster Setup (with MinIO)

For redundant S3-compatible storage:

```bash
docker compose -f docker-compose.cluster.yml up
```

MinIO console at `http://localhost:9001` (minioadmin/minioadmin).

## Cloud Deploy

Set these environment variables on any cloud container service:

```
DATABASE_URL=postgresql://user:pass@db-host:5432/clawbox
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://your-s3-endpoint  # Empty for AWS S3
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=your-bucket
```

### S3-Compatible Endpoints

| Provider | S3_ENDPOINT_URL |
|----------|-----------------|
| AWS S3 | (leave empty) |
| MinIO | `http://minio:9000` |
| GCS | `https://storage.googleapis.com` |
| DigitalOcean Spaces | `https://{region}.digitaloceanspaces.com` |
| Cloudflare R2 | `https://{account_id}.r2.cloudflarestorage.com` |

## Optional Features

| Feature | Env Var | Description |
|---------|---------|-------------|
| Semantic search | `GOOGLE_API_KEY` | Gemini embeddings |
| Google login | `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` | 1 GB storage for logged-in users |
| Session signing | `SESSION_SECRET_KEY` | Random string for production |
| Share links | `APP_URL` | Public URL for share/callback URLs |

## Point CLI at Self-Hosted Server

```bash
agentbox init --api-url http://your-server:8000
```
