---
name: agentbox
description: Use the AgentBox CLI to initialize and configure an AgentBox client, upload/download/list/delete files, check server and token status, and run semantic search against stored text content. Use when working with the `agentbox` command or when a user asks to interact with an AgentBox server, manage the local AgentBox token/config, or store and search files through AgentBox.
---

# agentbox

Use `agentbox` as a CLI for an AgentBox server: a cloud file system for agents with token-based auth and optional semantic search.

## Quick start

Run help if the exact subcommand shape is unclear:

```bash
agentbox --help
agentbox <command> --help
```

Main commands:

```bash
agentbox init
agentbox config
agentbox upload <file_path>
agentbox download <file_id>
agentbox list
agentbox delete <file_id>
agentbox search <query>
agentbox status
```

## Important behavior

- Local config file: `~/.agentbox/config.json`
- Default API URL: `http://localhost:8000`
- `init` requests a fresh token from `/get_token` and saves it in config.
- Most commands require a configured token; if missing, the CLI tells you to run `agentbox init` first.
- Semantic search depends on server-side embeddings and an OpenAI API key on the server.
- Search is intended for text-like content. Binary files can be stored but may not be searchable by meaning.

## Workflow

1. Confirm whether the user wants setup, config, upload/download, listing, deletion, search, or status.
2. Check status or config first when the environment may be misconfigured.
3. If there is no token, run `agentbox init` or set one with `agentbox config --token ...`.
4. Prefer non-destructive inspection before mutation: `status`, `config --show`, `list`.
5. Ask before deletion unless the user explicitly requested it.
6. After a successful operation, report the key output: token saved, API URL changed, uploaded file id, download path, or deleted file id.

## Core tasks

### Initialize

Use to get a new token and optionally set the API URL.

```bash
agentbox init
agentbox init --api-url|-u http://localhost:8000
```

What it does:
- Calls `POST /get_token`
- Saves the token to `~/.agentbox/config.json`
- Prints storage limit information

Use this first when the CLI is unconfigured.

### View or update config

Use to inspect or set local client configuration.

```bash
agentbox config --show|-s
agentbox config --api-url|-u http://localhost:8000
agentbox config --token|-t <token>
```

Good practice:
- Use `--show` to inspect current state before changing it.
- Use `--api-url` when switching between local/dev/prod servers.
- Use `--token` when a token is provided externally instead of acquired via `init`.

### Upload a file

Use to store a local file in AgentBox.

```bash
agentbox upload ./path/to/file.txt
```

Behavior:
- Requires a token in config
- Uploads the file to `/files/upload`
- Prints the returned file id, filename, and size

Good practice:
- Verify the local file path exists first.
- Report the returned file id back to the user.

### Download a file

Use to retrieve a file by id.

```bash
agentbox download <file_id>
agentbox download <file_id> --output|-o ./downloaded.bin
```

Behavior:
- Requires a token
- Writes to the provided `--output` path, or uses the server-provided filename when available

Always report the final output path.

### List files

Use to inspect the current file set for the configured token.

```bash
agentbox list
```

Behavior:
- Requires a token
- Shows a table with truncated id, filename, content type, size, and created time

Use this before deletion when the user only partially remembers a file id.

### Delete a file

Deletion is destructive.

```bash
agentbox delete <file_id>
agentbox delete <file_id> --force|-f
```

Behavior:
- Requires a token
- Prompts for confirmation unless `--force` is provided

Ask before deleting unless the user already explicitly requested deletion.

### Search files

Use semantic search across stored content.

```bash
agentbox search "meeting notes"
agentbox search "terraform deployment" --limit|-n 5
```

Behavior:
- Requires a token
- Sends a query to `/search`
- `--limit` controls the maximum number of search results returned (default: 10)
- Shows score, file id, filename, and a matched text chunk
- May fail with a message indicating the server lacks an OpenAI API key

Notes:
- Prefer this for text-heavy content.
- Do not promise search coverage for binary formats like images, PDFs, or Word docs unless the server is known to extract/index them.

### Check status

Use as the safest first diagnostic command.

```bash
agentbox status
```

Behavior:
- Checks `/health` and reports server version when reachable
- Validates the configured token by making a test request to `GET /files`

Use this before troubleshooting uploads, downloads, or search.

## Troubleshooting

### Cannot connect to API

If the CLI cannot connect, it expects an AgentBox server at the configured API URL and suggests:

```bash
python -m mvp.main
```

Use this when working directly in the local repo and the user wants the development server started.

### Search unavailable

If semantic search returns a warning about OpenAI, the likely cause is missing server-side `OPENAI_API_KEY` configuration.

### Missing token

If commands fail because no token is configured, use one of:

```bash
agentbox init
agentbox config --token <token>
```

## Example requests

Requests that should trigger this skill include:
- "Initialize agentbox against my local server"
- "Show the current AgentBox config"
- "Upload this file with agentbox and tell me the id"
- "Download AgentBox file `abc123` into this folder"
- "List my AgentBox files"
- "Delete this AgentBox file"
- "Search AgentBox for notes about Terraform"
- "Check whether the AgentBox server and token are working"
