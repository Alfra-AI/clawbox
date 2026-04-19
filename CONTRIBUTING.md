# Contributing to ClawBox

Thanks for your interest in contributing to ClawBox! Whether you're fixing a bug, adding a feature, improving docs, or writing tests, your help is welcome.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Issues](#reporting-issues)
- [Good First Contributions](#good-first-contributions)
- [License](#license)

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/clawbox.git
   cd clawbox
   ```
3. **Add the upstream remote** so you can stay in sync:
   ```bash
   git remote add upstream https://github.com/Alfra-AI/clawbox.git
   ```

---

## Development Setup

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- A Google API key (for Gemini embeddings; optional for non-search work)

### Quick Setup

1. **Start PostgreSQL** with pgvector:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db
   ```
   Wait until the container is healthy before proceeding.

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e ".[server,dev]"
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env — at minimum set DATABASE_URL and optionally GOOGLE_API_KEY
   ```

4. **Apply database migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Run the server:**
   ```bash
   python -m src.main
   ```

   The API is available at `http://localhost:8000`.

For the full development guide, see [DEVELOPMENT.md](DEVELOPMENT.md).

---

## Project Structure

```
clawbox/
├── src/                    # Main application package
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # Settings (loaded from environment)
│   ├── models.py           # SQLAlchemy models
│   ├── database.py         # DB connection and pgvector setup
│   ├── storage.py          # Storage backend abstraction (local/S3)
│   ├── embeddings.py       # Gemini embeddings and text extraction
│   ├── auth.py             # Bearer token authentication
│   ├── oauth.py            # Google OAuth setup
│   ├── cli.py              # CLI tool (typer)
│   ├── routes/             # API route handlers
│   │   ├── files.py        # File CRUD, folders, sharing
│   │   ├── search.py       # Semantic search
│   │   ├── tokens.py       # Token management
│   │   ├── oauth.py        # OAuth flow
│   │   └── drops.py        # File drop feature
│   └── static/             # Web UI (HTML/JS)
├── alembic/                # Database migrations
│   └── versions/           # Migration files
├── docs/                   # Documentation
├── skills/clawbox/         # AI agent skill definition
├── terraform/              # AWS infrastructure (Terraform)
├── docker-compose.yml      # Single-server Docker setup
├── docker-compose.dev.yml  # Dev override (exposes DB locally)
├── docker-compose.cluster.yml  # Multi-node setup with MinIO
└── pyproject.toml          # Package config and dependencies
```

### Key architectural decisions

- **FastAPI + async** throughout. Route handlers and storage operations use `async`/`await`.
- **Pluggable storage.** The `storage.py` module abstracts over local filesystem and any S3-compatible service (AWS S3, MinIO, GCS, R2, etc.).
- **pgvector for embeddings.** Semantic search uses PostgreSQL's pgvector extension rather than a separate vector database.
- **Alembic for migrations.** Schema changes go through Alembic, never `Base.metadata.create_all()`.

---

## Making Changes

### Branch naming

Create a feature branch from `main`:

```bash
git checkout main
git pull upstream main
git checkout -b <type>/<short-description>
```

Use a descriptive prefix:

| Prefix     | Use for                          |
|------------|----------------------------------|
| `feat/`    | New features                     |
| `fix/`     | Bug fixes                        |
| `docs/`    | Documentation changes            |
| `test/`    | Adding or updating tests         |
| `refactor/`| Code refactoring (no behavior change) |
| `chore/`   | Build, CI, dependency updates    |

### Commit messages

Write clear, concise commit messages:

```
feat: add folder size endpoint

Adds GET /files/folders/{path}/size that returns the total size
of all files in a folder and its subfolders.
```

- Use the imperative mood ("add", not "added" or "adds").
- First line: `<type>: <short summary>` (under 72 characters).
- Optional body: explain **why**, not just what.

---

## Database Migrations

ClawBox uses [Alembic](https://alembic.sqlalchemy.org/) for all schema changes.

### Creating a migration

After modifying models in `src/models.py`:

```bash
alembic revision --autogenerate -m "describe your change"
```

**Always review the generated migration file** before committing. Autogenerate doesn't catch everything (e.g., data migrations, index changes on existing columns).

### Migration guidelines

- **One migration per logical change.** Don't bundle unrelated schema changes.
- **Name migrations clearly.** Use the format `YYYYMMDD_NNNN_description.py`.
- **Test both directions.** Make sure `upgrade()` and `downgrade()` work:
  ```bash
  alembic upgrade head
  alembic downgrade -1
  alembic upgrade head
  ```
- **Never edit a migration that has been merged to `main`.** Create a new migration instead.

### Pulling migration changes

If you have local-only migrations applied, downgrade before pulling:

```bash
alembic downgrade -1          # Revert each local-only migration
git pull upstream main
alembic upgrade head
```

See [DEVELOPMENT.md](DEVELOPMENT.md#pulling-migration-changes-from-remote) for details.

---

## Testing

### Running tests

```bash
pip install -e ".[server,dev]"
pytest
```

### Writing tests

We use [pytest](https://docs.pytest.org/) with [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) for async tests and [httpx](https://www.python-httpx.org/) for the test client.

Guidelines:

- Place tests in a `tests/` directory, mirroring the source structure (e.g., `tests/test_files.py` for `src/routes/files.py`).
- Name test files `test_<module>.py` and test functions `test_<behavior>`.
- Use FastAPI's `TestClient` (via httpx) for API route tests.
- Test both success and error paths.
- Keep tests focused: one assertion per behavior, not one mega-test.

Example:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
```

---

## Code Style

### General guidelines

- **Python 3.10+** — use modern syntax (type hints, `match` statements, `|` union types where appropriate).
- **Async by default** — use `async def` for route handlers and I/O-bound operations.
- **Keep functions focused** — if a function does multiple unrelated things, split it.
- **Type hints** — add type annotations to function signatures. Use Pydantic models for request/response schemas.
- **No wildcard imports** — always import specific names.

### File organization

- **Routes** go in `src/routes/`. Each route module should use an `APIRouter`.
- **Models** go in `src/models.py`.
- **Business logic** should live in dedicated modules (like `embeddings.py`, `storage.py`), not inline in route handlers.
- **Configuration** is centralized in `src/config.py` via Pydantic Settings.

### Environment and secrets

- Never commit secrets, API keys, or credentials.
- All configuration comes from environment variables (defined in `src/config.py`).
- Update `.env.example` when adding new environment variables.

---

## Submitting a Pull Request

1. **Make sure your branch is up to date:**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests** (if applicable) and verify the server starts:
   ```bash
   pytest
   python -m src.main
   ```

3. **Push your branch:**
   ```bash
   git push origin <your-branch>
   ```

4. **Open a pull request** against `main` on GitHub.

### PR guidelines

- **Title:** Use the same `<type>: <description>` format as commits.
- **Description:** Explain what changed and why. Include screenshots for UI changes.
- **Keep PRs focused.** One logical change per PR. Large refactors should be discussed in an issue first.
- **Link related issues** using `Closes #123` or `Fixes #123` in the description.
- **Be responsive to review feedback.** We aim to review PRs promptly; please address comments in a timely manner.

### What to expect

- A maintainer will review your PR and may request changes.
- CI checks (when available) must pass before merging.
- PRs are squash-merged to keep `main` history clean.

---

## Reporting Issues

Found a bug or have a feature request? [Open an issue](https://github.com/Alfra-AI/clawbox/issues/new) with:

### Bug reports

- **Title:** Short description of the problem.
- **Steps to reproduce:** Minimal steps to trigger the bug.
- **Expected behavior:** What you expected to happen.
- **Actual behavior:** What actually happened (include error messages, logs, or screenshots).
- **Environment:** OS, Python version, Docker version, deployment method (Docker/local).

### Feature requests

- **Problem:** What problem does this solve? Who benefits?
- **Proposed solution:** How do you envision this working?
- **Alternatives considered:** What other approaches did you think about?

---

## Good First Contributions

Looking for a place to start? Here are some areas where help is especially welcome:

- **Tests** — The test suite is in its early stages. Adding tests for existing endpoints is a great way to learn the codebase.
- **Documentation** — Improve inline docs, add examples to the API reference, or clarify setup instructions.
- **Error handling** — Improve error messages and HTTP status codes in API responses.
- **CLI improvements** — Extend the `clawbox` CLI with new commands or better output formatting.

Look for issues labeled `good first issue` on GitHub.

---

## License

By contributing to ClawBox, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

---

Thank you for helping make ClawBox better!
