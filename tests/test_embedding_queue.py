from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.auth import get_current_token
from src.config import settings
from src.database import Base, get_db
from src.embedding_jobs import EmbeddingWrite, claim_next_embedding_job, utcnow
from src.models import EmbeddingJob, File, FileEmbedding, Token, User
from src.routes import files as files_routes
from src.worker import process_job


class FakeStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    async def save(self, token_id, file_id, file_data, filename):
        path = f"{token_id}/{file_id}_{filename}"
        self.files[path] = file_data.read()
        return path

    async def load(self, storage_path: str) -> bytes:
        if storage_path not in self.files:
            raise FileNotFoundError(storage_path)
        return self.files[storage_path]

    async def delete(self, storage_path: str) -> None:
        self.files.pop(storage_path, None)

    async def exists(self, storage_path: str) -> bool:
        return storage_path in self.files


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Token.__table__,
            File.__table__,
            EmbeddingJob.__table__,
            FileEmbedding.__table__,
        ],
    )

    session = TestingSessionLocal()
    try:
        yield session, TestingSessionLocal
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def token(db_session):
    session, _ = db_session
    token = Token(id=uuid4(), storage_used_bytes=0, storage_limit_bytes=10_000_000)
    session.add(token)
    session.commit()
    return token


@pytest.fixture
def client(db_session, token, monkeypatch):
    session, _ = db_session
    storage = FakeStorage()
    monkeypatch.setattr(files_routes, "get_storage_backend", lambda: storage)

    app = FastAPI()
    app.include_router(files_routes.router)

    def override_db():
        yield session

    def override_token():
        return session.get(Token, token.id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_token] = override_token
    test_client = TestClient(app)
    try:
        yield test_client, session, storage
    finally:
        test_client.close()


def create_file(session, token_id, *, embedding_status="queued", filename="doc.txt", storage_path="stored/doc.txt"):
    file_record = File(
        id=uuid4(),
        token_id=token_id,
        filename=filename,
        folder="/",
        content_type="text/plain",
        size_bytes=12,
        storage_path=storage_path,
        embedding_status=embedding_status,
    )
    session.add(file_record)
    session.commit()
    return file_record


def test_upload_queues_embedding_job(client):
    test_client, session, _storage = client

    response = test_client.post(
        "/files/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["embedding_status"] == "queued"

    file_record = session.query(File).one()
    job = session.query(EmbeddingJob).one()
    assert file_record.embedding_status == "queued"
    assert job.file_id == file_record.id
    assert job.status == "queued"


def test_embed_endpoint_skips_existing_active_job(client, token):
    test_client, session, _storage = client
    file_record = create_file(session, token.id, embedding_status="queued")
    session.add(
        EmbeddingJob(
            file_id=file_record.id,
            token_id=token.id,
            status="queued",
        )
    )
    session.commit()

    response = test_client.post("/files/embed", json={"file_ids": [str(file_record.id)]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] == 0
    assert payload["skipped"] == 1
    assert payload["results"][0]["error"] == "already_queued"


def test_embed_endpoint_requeues_failed_file(client, token):
    test_client, session, _storage = client
    file_record = create_file(session, token.id, embedding_status="failed")
    session.add(
        EmbeddingJob(
            file_id=file_record.id,
            token_id=token.id,
            status="failed",
            attempt_count=3,
        )
    )
    session.commit()

    response = test_client.post("/files/embed", json={"failed_only": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["queued"] == 1
    assert payload["skipped"] == 0
    assert payload["results"][0]["embedding_status"] == "queued"

    session.refresh(file_record)
    active_jobs = session.query(EmbeddingJob).filter(EmbeddingJob.file_id == file_record.id, EmbeddingJob.status == "queued").all()
    assert file_record.embedding_status == "queued"
    assert len(active_jobs) == 1


def test_claim_next_job_requeues_expired_lease(db_session, token):
    session, _ = db_session
    file_record = create_file(session, token.id, embedding_status="processing")
    expired_job = EmbeddingJob(
        file_id=file_record.id,
        token_id=token.id,
        status="running",
        attempt_count=1,
        lease_expires_at=utcnow() - timedelta(seconds=1),
    )
    session.add(expired_job)
    session.commit()

    claimed_job = claim_next_embedding_job(session)

    assert claimed_job is not None
    assert claimed_job.id == expired_job.id
    assert claimed_job.status == "leased"
    assert claimed_job.attempt_count == 2
    session.refresh(file_record)
    assert file_record.embedding_status == "processing"


def test_process_job_stores_embeddings_and_completes(db_session, token, monkeypatch):
    session, TestingSessionLocal = db_session
    storage = FakeStorage()
    monkeypatch.setattr("src.worker.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("src.worker.get_storage_backend", lambda: storage)
    monkeypatch.setattr(
        "src.worker.embed_file_content",
        lambda file, content, content_type: [
            EmbeddingWrite(
                chunk_index=0,
                chunk_text="hello world",
                embedding=[0.1] * settings.embedding_dimensions,
            ),
        ],
    )

    file_record = create_file(session, token.id, embedding_status="queued", storage_path="token/doc.txt")
    storage.files[file_record.storage_path] = b"hello world"
    session.add(EmbeddingJob(file_id=file_record.id, token_id=token.id, status="queued"))
    session.commit()

    claimed_job = claim_next_embedding_job(session)
    process_job(claimed_job.id)

    session.expire_all()
    refreshed_job = session.get(EmbeddingJob, claimed_job.id)
    refreshed_file = session.get(File, file_record.id)
    embeddings = session.query(FileEmbedding).filter(FileEmbedding.file_id == file_record.id).all()

    assert refreshed_job.status == "completed"
    assert refreshed_file.embedding_status == "completed"
    assert refreshed_file.last_embedded_at is not None
    assert len(embeddings) == 1
    assert embeddings[0].chunk_text == "hello world"


def test_process_job_marks_missing_storage_as_failed(db_session, token, monkeypatch):
    session, TestingSessionLocal = db_session
    monkeypatch.setattr("src.worker.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("src.worker.get_storage_backend", lambda: FakeStorage())

    file_record = create_file(session, token.id, embedding_status="queued", storage_path="missing/doc.txt")
    session.add(EmbeddingJob(file_id=file_record.id, token_id=token.id, status="queued"))
    session.commit()

    claimed_job = claim_next_embedding_job(session)
    process_job(claimed_job.id)

    session.expire_all()
    refreshed_job = session.get(EmbeddingJob, claimed_job.id)
    refreshed_file = session.get(File, file_record.id)

    assert refreshed_job.status == "failed"
    assert refreshed_job.error_code == "file_not_found_in_storage"
    assert refreshed_file.embedding_status == "failed"
    assert refreshed_file.embedding_error_code == "file_not_found_in_storage"
