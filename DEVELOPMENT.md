# Development

## Local Setup

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

AgentBox uses Alembic for schema changes. `Base.metadata.create_all()` is not used
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

## Existing Local Databases

If you already created tables locally before Alembic was added, run:

```bash
alembic upgrade head
```

The initial bootstrap migration is written to reconcile the current local schema:
it creates missing tables on a fresh database and adds `files.embedding_status`
when upgrading an existing local database in place.
