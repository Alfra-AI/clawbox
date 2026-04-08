# Troubleshooting

## Cannot connect to API

```
Cannot connect to API at https://clawbox.ink
```

- Check if the server is running: `agentbox status`
- For local dev, start the server: `python -m mvp.main`
- Check the configured URL: `agentbox config --show`
- Change the URL: `agentbox config --api-url http://localhost:8000`

## Missing token

```
No token configured. Run 'agentbox init' first.
```

```bash
agentbox init
# Or set manually:
agentbox config --token <token>
```

## Search unavailable

```
Search is not available. OpenAI API key not configured.
```

Search requires a Google API key (Gemini) configured on the server side. This is a server config issue, not a CLI issue. If self-hosting, add `GOOGLE_API_KEY` to your `.env`.

## Upload fails with 413

```
Storage quota exceeded
```

- Anonymous tokens have 10 MB storage
- Sign in with Google at the web UI for 1 GB
- Check current usage: `agentbox status`

## Embedding failed

```
Embedding failed — file stored but not searchable
```

The file was uploaded but text extraction or embedding generation failed. Retry with:

```bash
agentbox embed <file_id>
# Or retry all failed:
agentbox embed --failed
```

## Invalid or expired token

```
Invalid or expired token
```

The token in your config no longer exists on the server. Get a new one:

```bash
agentbox init
```

Note: this creates a new token — you won't have access to files from the old token unless you sign in with the same Google account.
