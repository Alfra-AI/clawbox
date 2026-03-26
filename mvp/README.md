# AgentBox MVP (v0.0)

A minimal cloud file system for agents with semantic search capabilities.

## Features

- **File Storage**: Upload, download, delete any file format
- **Token-based Auth**: Free tokens with 10MB storage quota
- **Semantic Search**: Search text files by meaning (requires OpenAI API key)
- **Web UI**: Browser-based interface for file management

### Supported File Formats

| Operation | Supported Formats |
|-----------|-------------------|
| Upload/Download | All formats (binary storage) |
| Semantic Search | `text/*`, `application/json`, `application/xml`, `application/pdf`, `.docx` |

> **Note**: Images and other binary formats can be stored but are NOT indexed for semantic search.

## Local Development

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ with pgvector extension
- OpenAI API key (optional, for semantic search)

## Setup

### 1. PostgreSQL Setup (via Homebrew)

```bash
# Install PostgreSQL if not already installed
brew install postgresql@14

# Initialize database (if first time)
initdb --locale=en_US.UTF-8 -E UTF-8 /usr/local/var/postgresql@14

# Start PostgreSQL
brew services start postgresql@14

# Create database and user
psql -U $USER -d postgres -c "CREATE USER agentbox WITH PASSWORD 'agentbox' CREATEDB;"
psql -U $USER -d postgres -c "CREATE DATABASE agentbox OWNER agentbox;"

# Install pgvector extension
psql -U $USER -d agentbox -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 2. Python Environment

```bash
# From the project root (agentbox/)
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### 3. Configuration

```bash
cp .env.example .env
# Edit .env to add your OpenAI API key (optional, for semantic search)
```

### 4. Run the Server

```bash
python -m mvp.main
```

Server runs at `http://localhost:8000`

**Production:** `https://clawbox.ink`

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/get_token` | POST | No | Get a free token (10 MB quota) |
| `/files/upload` | POST | Bearer | Upload a file |
| `/files/{id}` | GET | Bearer | Download a file |
| `/files` | GET | Bearer | List files |
| `/files/{id}` | DELETE | Bearer | Delete a file |
| `/search` | POST | Bearer | Semantic search (requires OpenAI key) |
| `/health` | GET | No | Health check |

## Quick Test

```bash
# Use production API
API_URL="https://clawbox.ink"
# Or for local development:
# API_URL="http://localhost:8000"

# Get a token
TOKEN=$(curl -s -X POST $API_URL/get_token | jq -r .token)

# Upload a file
curl -X POST $API_URL/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@yourfile.txt"

# List files
curl $API_URL/files -H "Authorization: Bearer $TOKEN"

# Search
curl -X POST $API_URL/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query"}'
```

## API Docs

- **Production:** `https://clawbox.ink/docs`
- **Local:** `http://localhost:8000/docs`

## Cloud Deployment (AWS)

The `terraform/` directory contains infrastructure-as-code for deploying to AWS.

### Architecture

- **ECS Fargate**: Serverless container hosting
- **RDS PostgreSQL**: Managed database with pgvector
- **S3**: File storage
- **ALB**: Load balancer

### Deploy

```bash
cd terraform

# Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# Deploy
terraform init
terraform plan
terraform apply

# Build and push Docker image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t agentbox ..
docker tag agentbox:latest <ecr-repo-url>:latest
docker push <ecr-repo-url>:latest

# Force ECS to pull new image
aws ecs update-service --cluster agentbox-prod-cluster --service agentbox-prod --force-new-deployment
```

### Production URL

**https://clawbox.ink**
