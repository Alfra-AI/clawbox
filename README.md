# AgentBox

A minimal cloud file system for agents with semantic search capabilities.

## Features

- **File Storage**: Upload, download, list, and delete files
- **Token-Based Auth**: Zero-friction onboarding with free 10 MB quota
- **Semantic Search**: Search files by meaning using vector embeddings

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for PostgreSQL with pgvector)
- OpenAI API key (for semantic search)

### Setup

1. Start PostgreSQL with pgvector:
```bash
docker-compose up -d
```

Wait until the container is healthy before starting the app.

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

4. Run the server:
```bash
python -m agentbox.main
```

The API will be available at `http://localhost:8000`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/get_token` | POST | Get a free token with 10 MB quota |
| `/files/upload` | POST | Upload a file |
| `/files/{id}` | GET | Download a file |
| `/files` | GET | List files for the token |
| `/files/{id}` | DELETE | Delete a file |
| `/search` | POST | Semantic search across files |
| `/health` | GET | Health check |

All endpoints (except `/get_token` and `/health`) require `Authorization: Bearer <token>`.

## Usage Example

```bash
# Get a token
TOKEN=$(curl -s -X POST http://localhost:8000/get_token | jq -r .token)

# Upload a file
curl -X POST http://localhost:8000/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.txt"

# List files
curl http://localhost:8000/files \
  -H "Authorization: Bearer $TOKEN"

# Search files
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query"}'
```

## Agent Integrations

If you want to connect AgentBox to an external coding or task agent, see
[`agent-integration/SKILL.md`](agent-integration/SKILL.md).

This file provides a reusable skill definition covering:

- File upload, download, listing, and deletion workflows
- Semantic search usage and troubleshooting

## Development

API documentation is available at `http://localhost:8000/docs` when the server is running.
