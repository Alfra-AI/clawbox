---
name: agentbox
version: 1.1.0
description: Use the AgentBox CLI to upload, download, organize, search, and share files on ClawBox (clawbox.ink) or a self-hosted AgentBox server. Trigger this skill when users mention agentbox, clawbox, cloud file storage, uploading files to the cloud, semantic file search, file sharing links, organizing files into folders, or managing tokens and storage quotas. Also use when code imports or references the agentbox CLI tool.
---

# AgentBox

CLI for ClawBox / AgentBox — a cloud file system for agents with token-based auth, semantic search, folders, and file sharing.

## Setup

If the CLI is not installed, run the setup script:

```bash
bash AgentBoxSkill/scripts/setup.sh
```

Or manually:

```bash
git clone https://github.com/Alfra-AI/agentbox.git
cd agentbox
pip install .
agentbox init
```

## Commands

```bash
agentbox init                                 # Get a token from clawbox.ink
agentbox init --login                         # Sign in with Google (opens browser)
agentbox init --api-url http://localhost:8000  # Self-hosted server
agentbox config --show                        # View current config
agentbox upload <file>                        # Upload a file (async embedding)
agentbox upload <file> --path /docs/file.pdf  # Upload into a folder
agentbox download <file_id>                   # Download by ID
agentbox list                                 # List all files
agentbox list --folder /docs/ --recursive     # List folder contents
agentbox search "query"                       # Semantic search
agentbox embed <file_id>                      # Generate embeddings
agentbox embed --failed                       # Retry failed embeddings
agentbox delete <file_id>                     # Delete a file
agentbox status                               # Check server + token health
```

## Workflow

1. Check if `agentbox` is installed. If not, run the setup script.
2. Run `agentbox status` to verify server connection and token.
3. If no token, run `agentbox init`.
4. Prefer non-destructive inspection before mutation: `status`, `config --show`, `list`.
5. Ask before deletion unless the user explicitly requested it.
6. Report key output after each operation: file id, download path, share link, etc.

## Key details

- Config: `~/.agentbox/config.json`
- Default server: `https://clawbox.ink`
- Searchable formats: text, JSON, XML, PDF, Word, Excel, PowerPoint, CSV, images, audio, video
- Storage: 1 GB free (anonymous), 10 GB with Google login
- Large files: use presigned URLs via API (`POST /files/upload-url`) for direct S3 upload
- Folders: virtual paths like `/docs/reports/`, created implicitly on upload

For detailed API reference, read `AgentBoxSkill/references/api.md`.
For self-hosting and deployment, read `AgentBoxSkill/references/self-hosting.md`.
For troubleshooting, read `AgentBoxSkill/references/troubleshooting.md`.
