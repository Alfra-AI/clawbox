# Self-Hosting ClawBox

## Quick Start (Docker Compose)

The fastest way to run ClawBox on your own machine or server.

### Prerequisites
- Docker and Docker Compose

### Steps

```bash
git clone https://github.com/Tanggy123/agentbox.git
cd agentbox
cp .env.example .env    # Edit .env if you want to configure optional features
docker compose up
```

ClawBox is now running at **http://localhost:8000**

### What's included
- PostgreSQL with pgvector (for semantic search)
- ClawBox app with auto-migration
- Local filesystem storage

### Optional features
Edit `.env` to enable:
- **Semantic search:** Add your `OPENAI_API_KEY`
- **Google login:** Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- **Custom domain:** Set `APP_URL` to your domain

---

## Cluster Setup (with MinIO)

For teams or production use with redundant object storage.

```bash
docker compose -f docker-compose.cluster.yml up
```

This adds MinIO (S3-compatible storage) for file redundancy and encryption at rest. MinIO console is available at http://localhost:9001 (login: minioadmin/minioadmin).

---

## Cloud Deploy (your own account)

ClawBox works with any cloud that has managed PostgreSQL and S3-compatible storage.

### AWS

```bash
cd deploy/aws
cp terraform.tfvars.example terraform.tfvars  # Edit with your values
terraform init && terraform apply
```

### Any cloud with S3-compatible storage

Set these environment variables on your container:

```
DATABASE_URL=postgresql://user:pass@your-db-host:5432/clawbox
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://your-s3-endpoint    # Leave empty for AWS S3
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=your-bucket
```

| Cloud | S3 Endpoint |
|-------|-------------|
| AWS S3 | (leave empty) |
| MinIO | `http://minio:9000` |
| GCS | `https://storage.googleapis.com` |
| DigitalOcean Spaces | `https://{region}.digitaloceanspaces.com` |
| Cloudflare R2 | `https://{account_id}.r2.cloudflarestorage.com` |

---

## Bare Metal (no Docker)

### Prerequisites
- Python 3.10+
- PostgreSQL 14+ with pgvector extension

### Steps

```bash
# Install pgvector extension
# On Ubuntu: sudo apt install postgresql-16-pgvector
# On macOS: brew install pgvector

# Clone and install
git clone https://github.com/Tanggy123/agentbox.git
cd agentbox
python -m venv venv
source venv/bin/activate
pip install .

# Configure
cp .env.example .env
# Edit .env with your database URL

# Run
python -m mvp.main
```

---

## HTTPS (Production)

ClawBox does not handle HTTPS directly. Use a reverse proxy:

### Caddy (easiest — auto HTTPS)

```
# Caddyfile
yourdomain.com {
    reverse_proxy localhost:8000
}
```

```bash
caddy run
```

### Nginx

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 100M;
    }
}
```

---

## Configuration Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `postgresql://clawbox:clawbox@localhost:5432/clawbox` | Yes | PostgreSQL connection string |
| `STORAGE_BACKEND` | `local` | No | `local` or `s3` |
| `LOCAL_STORAGE_PATH` | `./data` | No | Path for local file storage |
| `S3_ENDPOINT_URL` | (empty) | No | S3-compatible endpoint (empty = AWS) |
| `AWS_ACCESS_KEY_ID` | (empty) | If s3 | S3 access key |
| `AWS_SECRET_ACCESS_KEY` | (empty) | If s3 | S3 secret key |
| `S3_BUCKET_NAME` | (empty) | If s3 | S3 bucket name |
| `AWS_REGION` | `us-east-1` | No | S3 region |
| `OPENAI_API_KEY` | (empty) | No | Enables semantic search |
| `GOOGLE_CLIENT_ID` | (empty) | No | Enables Google login |
| `GOOGLE_CLIENT_SECRET` | (empty) | No | Google OAuth secret |
| `SESSION_SECRET_KEY` | `change-me...` | Prod | Random string for session signing |
| `APP_URL` | `http://localhost:8000` | Prod | Public URL for callbacks/share links |
| `HOST` | `0.0.0.0` | No | Server bind address |
| `PORT` | `8000` | No | Server port |

---

## Backup & Restore

### Backup

```bash
# Database
docker compose exec db pg_dump -U clawbox clawbox > backup.sql

# Files (local storage)
tar czf files-backup.tar.gz data/

# Files (S3/MinIO)
mc mirror myminio/clawbox-files ./files-backup/
```

### Restore

```bash
# Database
docker compose exec -T db psql -U clawbox clawbox < backup.sql

# Files
tar xzf files-backup.tar.gz
```
