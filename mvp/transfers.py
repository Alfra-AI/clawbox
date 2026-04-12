"""Transfer state management for background uploads/downloads.

State files are stored as JSON in ~/.agentbox/transfers/{file_id}.json.
Any CLI invocation can read/write these — no daemon or socket needed.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


TRANSFERS_DIR = Path.home() / ".agentbox" / "transfers"


def _ensure_dir():
    TRANSFERS_DIR.mkdir(parents=True, exist_ok=True)


def _state_path(file_id: str) -> Path:
    return TRANSFERS_DIR / f"{file_id}.json"


def _log_path(file_id: str) -> Path:
    return TRANSFERS_DIR / f"{file_id}.log"


def create_transfer(
    file_id: str,
    direction: str,  # "upload" or "download"
    file_path: str,
    filename: str,
    size_bytes: int,
    worker_pid: Optional[int] = None,
    upload_id: Optional[str] = None,
    part_urls: Optional[list] = None,
    virtual_path: Optional[str] = None,
    total_parts: int = 0,
) -> dict:
    """Create a new transfer state file."""
    _ensure_dir()
    state = {
        "file_id": file_id,
        "direction": direction,
        "file_path": file_path,
        "filename": filename,
        "size_bytes": size_bytes,
        "status": "uploading" if direction == "upload" else "downloading",
        "bytes_transferred": 0,
        "total_parts": total_parts,
        "completed_parts": 0,
        "completed_etags": [],
        "upload_id": upload_id,
        "part_urls": part_urls,
        "virtual_path": virtual_path,
        "error": None,
        "worker_pid": worker_pid,
        "started_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    _write_state(file_id, state)
    return state


def update_transfer(file_id: str, **fields) -> Optional[dict]:
    """Atomically update fields in a transfer state file."""
    state = get_transfer(file_id)
    if state is None:
        return None
    state.update(fields)
    state["updated_at"] = datetime.utcnow().isoformat()
    _write_state(file_id, state)
    return state


def get_transfer(file_id: str) -> Optional[dict]:
    """Read a transfer state file."""
    path = _state_path(file_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def list_transfers(direction: Optional[str] = None, status: Optional[str] = None) -> list:
    """List all transfer state files, optionally filtered."""
    _ensure_dir()
    transfers = []
    for p in TRANSFERS_DIR.glob("*.json"):
        try:
            state = json.loads(p.read_text())
            if direction and state.get("direction") != direction:
                continue
            if status and state.get("status") != status:
                continue
            transfers.append(state)
        except (json.JSONDecodeError, OSError):
            continue
    transfers.sort(key=lambda t: t.get("started_at", ""), reverse=True)
    return transfers


def cleanup_transfers(max_age_hours: int = 24):
    """Remove transfer state files older than max_age_hours that are completed or failed."""
    _ensure_dir()
    now = datetime.utcnow()
    for p in TRANSFERS_DIR.glob("*.json"):
        try:
            state = json.loads(p.read_text())
            if state.get("status") not in ("ready", "downloaded", "completed", "failed"):
                continue
            updated = datetime.fromisoformat(state.get("updated_at", "2000-01-01"))
            if (now - updated).total_seconds() > max_age_hours * 3600:
                p.unlink(missing_ok=True)
                # Also clean up log file
                log = _log_path(state["file_id"])
                log.unlink(missing_ok=True)
        except (json.JSONDecodeError, OSError, ValueError):
            continue


def is_worker_alive(pid: int) -> bool:
    """Check if a worker process is still running."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _write_state(file_id: str, state: dict):
    """Write state atomically (write to temp, then rename)."""
    _ensure_dir()
    path = _state_path(file_id)
    fd, tmp = tempfile.mkstemp(dir=TRANSFERS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
