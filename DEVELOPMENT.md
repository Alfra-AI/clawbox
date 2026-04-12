# Development

## Local Setup

1. Start PostgreSQL with pgvector:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db
```

The dev override publishes PostgreSQL on `localhost:5432` for local tools such
as Alembic and `psql`. Override the host port with `POSTGRES_PORT` if needed.

Wait until the container is healthy before starting the app.

2. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env and add your Google API key
```

4. Apply database migrations:
```bash
alembic upgrade head
```

5. Run the server:
```bash
python -m mvp.main
```

The API will be available at `http://localhost:8000`.

## Database Migrations

ClawBox uses Alembic for schema changes. `Base.metadata.create_all()` is not used
to evolve existing databases.

Apply migrations:

```bash
alembic upgrade head
```

Create a new migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe change"
```

Review the generated migration before committing it.

### Pulling migration changes from remote

If you have local-only (uncommitted) migrations applied to your database, **downgrade
out of them before pulling** new migration files that may reorganize the history:

```bash
# 1. Revert your local-only migration(s)
alembic downgrade -1   # repeat for each local-only migration

# 2. Pull the latest code
git pull

# 3. Apply the updated migration chain
alembic upgrade head
```

If you skip step 1, `git pull` may delete or rename migration files that your database
still references. Alembic cannot resolve an orphaned revision and will refuse to run
any command — the only recovery is manually updating the `alembic_version` table.

## Existing Local Databases

If you already created tables locally before Alembic was added, run:

```bash
alembic upgrade head
```

The initial bootstrap migration is written to reconcile the current local schema:
it creates missing tables on a fresh database and adds `files.embedding_status`
when upgrading an existing local database in place.
