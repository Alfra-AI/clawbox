# AgentBox MVP (v0.0)

Local development setup for AgentBox - a minimal cloud file system for agents.

## Prerequisites

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
# Get a token
TOKEN=$(curl -s -X POST http://localhost:8000/get_token | jq -r .token)

# Upload a file
curl -X POST http://localhost:8000/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@yourfile.txt"

# List files
curl http://localhost:8000/files -H "Authorization: Bearer $TOKEN"

# Search (requires OPENAI_API_KEY in .env)
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query"}'
```

## API Docs

Interactive docs at `http://localhost:8000/docs`
