---
name: agentbox
description: Use the AgentBox CLI to upload, download, organize, search, and share files on ClawBox (clawbox.ink) or a self-hosted AgentBox server. Trigger this skill when users mention agentbox, clawbox, cloud file storage, uploading files to the cloud, semantic file search, file sharing links, organizing files into folders, or managing tokens and storage quotas. Also use when code imports or references the agentbox CLI tool.
---

# agentbox

CLI for ClawBox / AgentBox — a cloud file system for agents with token-based auth, semantic search, folders, and file sharing.

## Setup

```bash
git clone https://github.com/Tanggy123/agentbox.git
cd agentbox
pip install .
```

Then initialize with a token:

```bash
agentbox init                                    # Uses clawbox.ink (hosted)
agentbox init --api-url http://localhost:8000     # Self-hosted
```

This creates `~/.agentbox/config.json` with your token and API URL. All subsequent commands use this config automatically.

## Quick start

```bash
agentbox --help
agentbox <command> --help
```

Commands:

```bash
agentbox init              # Get a token (or sign in with Google on the web)
agentbox config            # View/update local config
agentbox upload <file>     # Upload a file (with optional folder path)
agentbox download <id>     # Download a file by ID
agentbox list              # List files (with optional folder filter)
agentbox delete <id>       # Delete a file
agentbox search <query>    # Semantic search across files
agentbox embed <id>        # Generate embeddings for specific files
agentbox status            # Check server health and token validity
```

## Important behavior

- Config file: `~/.agentbox/config.json`
- Default API URL: `https://clawbox.ink` (override with `--api-url` on init)
- `init` requests a fresh token from `/get_token` and saves it in config
- Most commands require a configured token; if missing, run `agentbox init`
- Semantic search requires a Google API key (Gemini) configured on the server
- Supported search formats: text, JSON, XML, PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), CSV

## Workflow

1. Confirm whether the user wants setup, upload/download, listing, search, sharing, or status.
2. Check status or config first when the environment may be misconfigured.
3. If there is no token, run `agentbox init` or set one with `agentbox config --token ...`.
4. Prefer non-destructive inspection before mutation: `status`, `config --show`, `list`.
5. Ask before deletion unless the user explicitly requested it.
6. After a successful operation, report the key output: token, file id, download path, share link, etc.

## Core tasks

### Initialize

Get a new token and optionally set the API URL.

```bash
agentbox init
agentbox init --api-url https://clawbox.ink
agentbox init --api-url http://localhost:8000   # For local/self-hosted
```

### View or update config

```bash
agentbox config --show
agentbox config --api-url http://localhost:8000
agentbox config --token <token>
```

### Upload a file

```bash
agentbox upload ./report.pdf
agentbox upload ./report.pdf --path /docs/report.pdf   # Upload into a folder
```

The `--path` flag organizes the file into a virtual folder. Without it, files go to the root `/`.

### Download a file

```bash
agentbox download <file_id>
agentbox download <file_id> --output ./downloaded.pdf
```

### List files

```bash
agentbox list                          # All files
agentbox list --folder /docs/          # Files in /docs/ only
agentbox list --folder /docs/ --recursive  # Include subfolders
```

Output shows file path, type, size, embedding status, and creation date.

### Delete a file

```bash
agentbox delete <file_id>
agentbox delete <file_id> --force      # Skip confirmation
```

Ask before deleting unless the user already explicitly requested it.

### Search files

Semantic search across all stored files using vector embeddings.

```bash
agentbox search "quarterly revenue"
agentbox search "deployment notes" --limit 5
```

Searches text content of: plain text, Markdown, JSON, XML, PDF, Word, Excel, PowerPoint, and CSV files. Returns relevance score, file path, and matched text chunk.

### Embed files

Generate or retry embeddings for specific files.

```bash
agentbox embed <file_id>               # Embed a specific file
agentbox embed --failed                # Retry all files that failed embedding
```

### Check status

```bash
agentbox status
```

Checks server health and token validity. Use as the first diagnostic command.

## Self-hosting

For self-hosted instances, point the CLI at your server:

```bash
agentbox init --api-url http://your-server:8000
```

Self-hosting options:
- `docker compose up` — single server with PostgreSQL
- `docker compose -f docker-compose.cluster.yml up` — cluster with MinIO
- Any cloud with managed PostgreSQL + S3-compatible storage

## Troubleshooting

### Cannot connect to API

The CLI expects a server at the configured API URL. For local development:

```bash
python -m mvp.main
```

### Search unavailable

Search requires a Google API key (Gemini) configured on the server. Check with the server admin.

### Missing token

```bash
agentbox init
agentbox config --token <token>
```

## Example requests

Requests that should trigger this skill:
- "Initialize agentbox against my local server"
- "Upload this file to clawbox"
- "Upload report.pdf to the /docs folder on agentbox"
- "List my files in the /reports folder"
- "Search agentbox for meeting notes about the Q1 review"
- "Download agentbox file abc123"
- "Delete this file from agentbox"
- "Check if the agentbox server is running"
- "Retry failed embeddings on agentbox"
- "Set up agentbox to point to my self-hosted server"
