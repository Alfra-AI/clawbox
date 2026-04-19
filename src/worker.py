"""Embedding queue worker."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from src.config import settings
from src.database import SessionLocal, ensure_pgvector_extension
from src.embedding_jobs import (
    EmbeddingJobError,
    claim_next_embedding_job,
    complete_embedding_job,
    fail_embedding_job,
    mark_job_running,
)
from src.embeddings import embed_file_content
from src.models import EmbeddingJob
from src.storage import get_storage_backend

logger = logging.getLogger(__name__)


def process_job(job_id) -> None:
    """Process a single claimed job."""
    db = SessionLocal()
    try:
        job = db.query(EmbeddingJob).filter(EmbeddingJob.id == job_id).first()
        if job is None:
            return

        mark_job_running(db, job)
        file = job.file
        storage = get_storage_backend()

        try:
            content = asyncio.run(storage.load(file.storage_path))
        except FileNotFoundError as exc:
            fail_embedding_job(
                db,
                job,
                EmbeddingJobError(
                    "file_not_found_in_storage",
                    f"Storage path missing for {file.filename}",
                    retryable=False,
                ),
            )
            return

        try:
            writes = embed_file_content(file, content, file.content_type)
            complete_embedding_job(db, job, writes)
        except EmbeddingJobError as exc:
            fail_embedding_job(db, job, exc)
        except Exception as exc:  # pragma: no cover - last-resort safety net
            logger.exception("Unhandled embedding worker error for job %s", job_id)
            db.rollback()
            job = db.query(EmbeddingJob).filter(EmbeddingJob.id == job_id).first()
            if job is None:
                return
            fail_embedding_job(
                db,
                job,
                EmbeddingJobError("internal_error", str(exc) or "Internal worker error"),
            )
    finally:
        db.close()


def run_worker(once: bool = False) -> None:
    """Run the embedding worker loop."""
    ensure_pgvector_extension()
    while True:
        db = SessionLocal()
        try:
            job = claim_next_embedding_job(db)
        finally:
            db.close()

        if job is None:
            if once:
                return
            time.sleep(settings.embedding_worker_poll_seconds)
            continue

        process_job(job.id)
        if once:
            return


def main() -> None:
    """CLI entrypoint for the worker."""
    parser = argparse.ArgumentParser(description="Process queued embedding jobs.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
