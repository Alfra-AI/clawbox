# Auto-Organize - AI-Powered File Organization

## Problem
Users upload files into flat folders or the root. Over time, files pile up with no structure. Manually organizing is tedious.

## Concept
When auto-organize is enabled, each uploaded file is automatically placed into the right folder based on its content, filename, and existing folder structure. Uses an LLM to decide placement.

## How It Works

### On File Upload (auto-organize enabled)
1. Extract text from the file (reuse existing extractors)
2. Get the first ~500 chars of content + filename + content type
3. Fetch the user's existing folder structure (list of folders)
4. Ask the LLM: "Given this file and these existing folders, where should it go? You may suggest a new folder."
5. Set the file's `folder` to the LLM's answer
6. If the folder doesn't exist yet, it's created implicitly (virtual folders)

### LLM Prompt Design
```
You organize files into folders. Given:
- Filename: {filename}
- Type: {content_type}
- Content preview: {first_500_chars}
- Existing folders: {folder_list}

Return ONLY the folder path (e.g., /reports/finance/).
Rules:
- Use existing folders when they fit
- Create new folders only when no existing folder is appropriate
- Keep folder names short and lowercase
- Max 2 levels deep
```

### Configuration
- Per-token setting: `auto_organize: bool` (default false)
- Stored in tokens table or a new `token_settings` table
- Toggle via API: `PATCH /settings {"auto_organize": true}`
- Toggle via web UI: checkbox in the token/settings card

## Schema Change

```sql
ALTER TABLE tokens ADD COLUMN auto_organize BOOLEAN DEFAULT false;
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `PATCH /settings` | PATCH | Update token settings (auto_organize, etc.) |
| `GET /settings` | GET | Get current token settings |
| `POST /files/organize` | POST | Manually trigger organize on all files in root |

## Web UI
- Toggle switch in the settings/token card: "Auto-organize uploads"
- When enabled, uploaded files show their auto-assigned folder with a small "AI" badge
- "Organize" button to reorganize existing unorganized files

## Cost Considerations
- Uses GPT-4o-mini for classification (~$0.15/1M input tokens) — negligible cost
- Only processes the first 500 chars, not the full file
- Caches folder suggestions for identical content types + similar filenames

## Edge Cases
- Empty file → stays in root
- LLM returns invalid path → fallback to root, log warning
- No OpenAI key → auto-organize silently disabled
- User moves a file manually after auto-organize → respect the manual move

## Future
- Smart rename (suggest better filenames)
- Duplicate detection (flag files with very similar embeddings)
- Auto-tagging (add metadata tags alongside folder placement)
