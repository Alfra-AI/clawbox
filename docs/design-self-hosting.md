# Self-Hosting & Open Source Strategy

## Goal
Let users self-host ClawBox on their own infrastructure — from a single laptop to a private cluster to their own cloud account. One codebase, multiple deployment targets.

## Hosting Tiers

### Tier 1: Local / Single Server
**Target:** Developer laptop, home server, single VM
**Method:** `docker compose up`
**Stack:** Docker Compose → PostgreSQL (pgvector) + ClawBox app + local filesystem
**Effort:** Low — mostly packaging what we already have

### Tier 2: Private Cluster
**Target:** Office servers, on-prem data center, private cloud
**Method:** Docker Compose with MinIO, or Kubernetes (Helm chart)
**Stack:** Multiple app containers + PostgreSQL + MinIO (S3-compatible object storage)
**Benefits:** Redundancy, encryption at rest, scalability
**Effort:** Medium — add S3_ENDPOINT_URL config, write docker-compose.cluster.yml

### Tier 3: Public Cloud (user's own account)
**Target:** User's own AWS, GCP, Azure, DigitalOcean, Fly.io, etc.
**Method:** One-click deploy scripts (Terraform, fly.toml, etc.)
**Stack:** Managed containers + managed PostgreSQL + cloud object storage
**Effort:** Medium-High — one Terraform module per cloud

---

## Architecture

```
                    ┌─────────────────────────┐
                    │      Load Balancer       │
                    │   (nginx/Caddy/ALB)      │
                    └────────┬────────────────┘
                             │
                    ┌────────┼────────┐
                    │    App (x N)    │    ← Stateless, horizontally scalable
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │                             │
     ┌────────┴────────┐          ┌─────────┴─────────┐
     │   PostgreSQL     │          │  Object Storage    │
     │   (pgvector)     │          │  (Local/MinIO/S3)  │
     └─────────────────┘          └───────────────────┘
```

The app is stateless. All state lives in PostgreSQL (metadata, embeddings, users) and object storage (files). This means:
- Horizontal scaling = just add more app containers
- No sticky sessions needed
- Storage backend is swappable via config

---

## Storage Backend Matrix

| Backend | Config | Use case | Redundancy | Encryption |
|---------|--------|----------|------------|------------|
| Local filesystem | `STORAGE_BACKEND=local` | Dev, single server | None (unless RAID) | None (unless disk encryption) |
| MinIO | `STORAGE_BACKEND=s3` + `S3_ENDPOINT_URL=http://minio:9000` | Private cluster | Erasure coding | AES-256 at rest |
| AWS S3 | `STORAGE_BACKEND=s3` + `S3_BUCKET_NAME=...` | AWS cloud | 99.999999999% durability | AES-256/SSE |
| GCS | `STORAGE_BACKEND=s3` + `S3_ENDPOINT_URL=https://storage.googleapis.com` | GCP cloud | Same as S3 | Default encrypted |
| Azure Blob | `STORAGE_BACKEND=s3` + `S3_ENDPOINT_URL=...` | Azure cloud | LRS/GRS | Default encrypted |
| DO Spaces | `STORAGE_BACKEND=s3` + `S3_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com` | DigitalOcean | Built-in | AES-256 |

**Key insight:** All cloud object stores speak S3 API. One config change (`S3_ENDPOINT_URL`) unlocks all of them.

---

## Code Changes Required

### Phase 1: Universal Docker Image (Priority)

| Change | File | Description |
|--------|------|-------------|
| Add `S3_ENDPOINT_URL` config | `mvp/config.py` | Empty = AWS, set = MinIO/GCS/etc. |
| Pass `endpoint_url` to boto3 | `mvp/storage.py` | One line in S3StorageBackend |
| `docker-compose.yml` | root | App + PostgreSQL + auto-migration |
| `.env.example` | root | All settings documented |
| Self-hosting README | `docs/self-hosting.md` | Quick start + configuration reference |
| `.dockerignore` | root | Exclude venv, .git, data, .env |
| License file | `LICENSE` | MIT or AGPL |

### Phase 2: Cluster & Cloud Deploys

| Change | Description |
|--------|-------------|
| `docker-compose.cluster.yml` | App + PostgreSQL + MinIO (with redundancy) |
| `deploy/aws/` | Clean up existing Terraform |
| `deploy/gcp/main.tf` | Cloud Run + Cloud SQL + GCS |
| `deploy/digitalocean/main.tf` | App Platform + Managed DB + Spaces |
| `deploy/fly/fly.toml` | Fly.io deploy config |
| Helm chart (`deploy/k8s/`) | For any Kubernetes cluster |

### Phase 3: Polish

| Change | Description |
|--------|-------------|
| GitHub Actions CI | Run tests on PR, build Docker image on merge |
| One-line install script | `curl -fsSL https://clawbox.ink/install | sh` |
| Admin dashboard | User management, storage stats, system health |
| Backup/restore scripts | pg_dump + storage sync |

---

## docker-compose.yml (Tier 1)

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DATABASE_URL: postgresql://clawbox:clawbox@db:5432/clawbox
      STORAGE_BACKEND: local
    volumes:
      - file_data:/app/data
    depends_on:
      db:
        condition: service_healthy

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: clawbox
      POSTGRES_PASSWORD: clawbox
      POSTGRES_DB: clawbox
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U clawbox"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  db_data:
  file_data:
```

## docker-compose.cluster.yml (Tier 2)

```yaml
version: "3.8"

services:
  app:
    build: .
    deploy:
      replicas: 3
    env_file: .env
    environment:
      DATABASE_URL: postgresql://clawbox:clawbox@db:5432/clawbox
      STORAGE_BACKEND: s3
      S3_ENDPOINT_URL: http://minio:9000
      AWS_ACCESS_KEY_ID: minioadmin
      AWS_SECRET_ACCESS_KEY: minioadmin
      S3_BUCKET_NAME: clawbox-files
    depends_on:
      - db
      - minio

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: clawbox
      POSTGRES_PASSWORD: clawbox
      POSTGRES_DB: clawbox
    volumes:
      - db_data:/var/lib/postgresql/data

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    ports:
      - "9001:9001"  # MinIO console

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - app

volumes:
  db_data:
  minio_data:
```

---

## Cloud Deploy Matrix

| Cloud | Compute | Database | Storage | Deploy |
|-------|---------|----------|---------|--------|
| **AWS** | ECS Fargate | RDS PostgreSQL | S3 | `cd deploy/aws && terraform apply` |
| **GCP** | Cloud Run | Cloud SQL | GCS | `cd deploy/gcp && terraform apply` |
| **Azure** | Container Apps | Azure PostgreSQL | Blob Storage | `cd deploy/azure && terraform apply` |
| **DigitalOcean** | App Platform | Managed PostgreSQL | Spaces | `cd deploy/do && terraform apply` |
| **Fly.io** | Fly Machines | Fly Postgres | Tigris S3 | `fly deploy` |
| **Railway** | Container | Railway Postgres | Local volume | `railway up` |
| **Bare metal** | Docker | Docker PostgreSQL | Local / MinIO | `docker compose up` |

---

## Open Source Checklist

- [ ] Choose and add LICENSE file (MIT recommended for adoption, AGPL for protection)
- [ ] Audit repo for secrets (git history too — may need BFG if any were committed)
- [ ] Add `.env.example` with all variables documented
- [ ] Add `.dockerignore`
- [ ] Create `docker-compose.yml` (single server)
- [ ] Add `S3_ENDPOINT_URL` config + pass to boto3
- [ ] Write `docs/self-hosting.md`
- [ ] Add `CONTRIBUTING.md`
- [ ] Set up GitHub Actions (lint, test, Docker build)
- [ ] Create GitHub release with Docker image on ghcr.io
- [ ] Add badges to README (license, CI, Docker pulls)

---

## Security Considerations for Self-Hosting

- Default `docker-compose.yml` uses hardcoded DB passwords — docs should tell users to change them
- `SESSION_SECRET_KEY` must be set to a random value
- HTTPS should be handled by a reverse proxy (nginx/Caddy) — not built into the app
- OpenAI API key is user's own — we never see it
- Google OAuth credentials are user's own
- No telemetry, no phone-home, no analytics

---

## Migration Strategy for Self-Hosters

The app should auto-run migrations on startup so users don't need to manage alembic manually:

```python
# In lifespan handler:
from alembic import command
from alembic.config import Config

alembic_cfg = Config("alembic.ini")
command.upgrade(alembic_cfg, "head")
```

This means `docker compose up` on a fresh install creates all tables automatically.
