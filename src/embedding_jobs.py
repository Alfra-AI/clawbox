"""Embedding queue state transitions and worker coordination."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.config import settings
from src.models import EmbeddingJob, File, FileEmbedding

FILE_STATUS_NOT_APPLICABLE = "not_applicable"
FILE_STATUS_QUEUED = "queued"
FILE_STATUS_PROCESSING = "processing"
FILE_STATUS_COMPLETED = "completed"
FILE_STATUS_FAILED = "failed"

FILE_ACTIVE_STATUSES: Sequence[str] = (FILE_STATUS_QUEUED, FILE_STATUS_PROCESSING)
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_LEASED = "leased"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_ACTIVE_STATUSES: Sequence[str] = (JOB_STATUS_QUEUED, JOB_STATUS_LEASED, JOB_STATUS_RUNNING)


@dataclass
class EmbeddingWrite:
    """Stored embedding row payload."""

    chunk_index: int
    chunk_text: str
    embedding: list[float]


class EmbeddingJobError(Exception):
    """Normalized worker failure."""

    def __init__(self, code: str, detail: str | None = None, retryable: bool = True):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code
        self.retryable = retryable


def utcnow() -> datetime:
    """Return a timezone-naive UTC timestamp."""
    return datetime.now(UTC).replace(tzinfo=None)


def job_lease_deadline(now: datetime | None = None) -> datetime:
    """Calculate the current job lease expiry."""
    now = now or utcnow()
    return now + timedelta(seconds=settings.embedding_job_lease_seconds)


def reset_expired_jobs(db: Session, now: datetime | None = None) -> int:
    """Return expired active jobs to the queue."""
    now = now or utcnow()
    expired_jobs = (
        db.query(EmbeddingJob)
        .filter(
            EmbeddingJob.status.in_((JOB_STATUS_LEASED, JOB_STATUS_RUNNING)),
            EmbeddingJob.lease_expires_at.is_not(None),
            EmbeddingJob.lease_expires_at < now,
        )
        .all()
    )
    for job in expired_jobs:
        job.status = JOB_STATUS_QUEUED
        job.lease_expires_at = None
        job.error_code = None
        job.error_detail = None
        job.file.embedding_status = FILE_STATUS_QUEUED
    return len(expired_jobs)


def get_active_job_for_file(db: Session, file_id) -> EmbeddingJob | None:
    """Fetch the active job for a file, if any."""
    return (
        db.query(EmbeddingJob)
        .filter(EmbeddingJob.file_id == file_id, EmbeddingJob.status.in_(JOB_ACTIVE_STATUSES))
        .order_by(EmbeddingJob.created_at.desc())
        .first()
    )


def enqueue_embedding_job(
    db: Session,
    file: File,
    requested_by: str = "system",
    priority: int = 100,
) -> tuple[EmbeddingJob | None, bool]:
    """Ensure there is an active job for the file."""
    if file.embedding_status == FILE_STATUS_NOT_APPLICABLE:
        return None, False

    now = utcnow()
    active_job = get_active_job_for_file(db, file.id)
    if active_job and active_job.status in (JOB_STATUS_LEASED, JOB_STATUS_RUNNING):
        if active_job.lease_expires_at and active_job.lease_expires_at < now:
            active_job.status = JOB_STATUS_QUEUED
            active_job.lease_expires_at = None
            active_job.error_code = None
            active_job.error_detail = None
            file.embedding_status = FILE_STATUS_QUEUED
            file.embedding_error_code = None
            db.flush()
            return active_job, False
        return active_job, False
    if active_job:
        return active_job, False

    job = EmbeddingJob(
        file_id=file.id,
        token_id=file.token_id,
        status=JOB_STATUS_QUEUED,
        max_attempts=settings.embedding_job_max_attempts,
        priority=priority,
        requested_by=requested_by,
    )
    file.embedding_status = FILE_STATUS_QUEUED
    file.embedding_error_code = None
    db.add(job)
    db.flush()
    return job, True


def claim_next_embedding_job(db: Session) -> EmbeddingJob | None:
    """Lease the next queued job."""
    now = utcnow()
    reset_expired_jobs(db, now=now)
    db.flush()

    job = (
        db.query(EmbeddingJob)
        .filter(EmbeddingJob.status == JOB_STATUS_QUEUED)
        .order_by(EmbeddingJob.priority.asc(), EmbeddingJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if job is None:
        db.commit()
        return None

    job.status = JOB_STATUS_LEASED
    job.attempt_count += 1
    job.lease_expires_at = job_lease_deadline(now)
    if job.started_at is None:
        job.started_at = now
    job.error_code = None
    job.error_detail = None
    job.file.embedding_status = FILE_STATUS_PROCESSING
    job.file.embedding_error_code = None
    db.commit()
    db.refresh(job)
    return job


def mark_job_running(db: Session, job: EmbeddingJob) -> EmbeddingJob:
    """Mark a leased job as running."""
    job.status = JOB_STATUS_RUNNING
    job.file.embedding_status = FILE_STATUS_PROCESSING
    db.commit()
    db.refresh(job)
    return job


def complete_embedding_job(db: Session, job: EmbeddingJob, writes: Iterable[EmbeddingWrite]) -> None:
    """Replace a file's embeddings and mark the job complete."""
    now = utcnow()
    db.query(FileEmbedding).filter(FileEmbedding.file_id == job.file_id).delete()
    for write in writes:
        db.add(
            FileEmbedding(
                file_id=job.file_id,
                chunk_index=write.chunk_index,
                chunk_text=write.chunk_text,
                embedding=write.embedding,
            )
        )

    job.status = JOB_STATUS_COMPLETED
    job.completed_at = now
    job.lease_expires_at = None
    job.error_code = None
    job.error_detail = None
    job.file.embedding_status = FILE_STATUS_COMPLETED
    job.file.embedding_error_code = None
    job.file.last_embedded_at = now
    db.commit()


def fail_embedding_job(db: Session, job: EmbeddingJob, exc: EmbeddingJobError) -> None:
    """Retry or fail a job based on the normalized error."""
    should_retry = exc.retryable and job.attempt_count < job.max_attempts
    job.error_code = exc.code
    job.error_detail = exc.detail
    job.file.embedding_error_code = exc.code

    if should_retry:
        job.status = JOB_STATUS_QUEUED
        job.lease_expires_at = None
        job.file.embedding_status = FILE_STATUS_QUEUED
    else:
        job.status = JOB_STATUS_FAILED
        job.completed_at = utcnow()
        job.lease_expires_at = None
        job.file.embedding_status = FILE_STATUS_FAILED
    db.commit()


def get_embeddable_files_for_selector(
    db: Session,
    token_id,
    file_ids: Sequence | None = None,
    failed_only: bool = False,
    pending_only: bool = False,
) -> list[File]:
    """Fetch files targeted by the embed endpoint."""
    query = db.query(File).filter(File.token_id == token_id)
    if failed_only:
        return query.filter(File.embedding_status == FILE_STATUS_FAILED).all()
    if pending_only:
        return query.filter(
            or_(
                File.embedding_status.in_(FILE_ACTIVE_STATUSES),
                File.embedding_status == "pending",
            )
        ).all()
    return query.filter(File.id.in_(file_ids or [])).all()
