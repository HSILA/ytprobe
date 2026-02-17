#!/usr/bin/env python3

"""Stateless job management for async transcription.

Jobs are removed from memory when completed (stateless design).
Only running/failed jobs are tracked to minimize memory usage.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# In-memory job store (stateless: completed jobs are removed)
_jobs: Dict[str, dict] = {}


def create_job(video: str, fallback: bool = True) -> str:
    """Create a new transcription job."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "pending",
        "video": video,
        "fallback": fallback,
        "transcript": None,
        "error": None,
        "created_at": datetime.now(),
    }
    logger.info(f"Created job {job_id} for video {video}")
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    """Get job by ID. Returns None if not found."""
    return _jobs.get(job_id)


def update_job(
    job_id: str,
    status: str = None,
    transcript: Optional[str] = None,
    error: Optional[str] = None,
) -> bool:
    """Update job status and/or result. Returns True if job exists, False otherwise."""
    if job_id not in _jobs:
        return False

    job = _jobs[job_id]

    if status:
        job["status"] = status
    if transcript is not None:
        job["transcript"] = transcript
    if error is not None:
        job["error"] = error

    job["updated_at"] = datetime.now()

    logger.info(f"Updated job {job_id}: status={status}, error={error}")

    # Note: Jobs are NOT removed on completion to allow clients to retrieve results
    # They will be cleaned up by cleanup_old_jobs after RETENTION_MINUTES

    return True

# Keep completed jobs for this many minutes to allow client retrieval
RETENTION_MINUTES = 5


def cleanup_old_jobs() -> int:
    """Remove old jobs to free memory. Returns number of jobs cleaned.

    Completed/failed jobs are removed after RETENTION_MINUTES.
    Pending/processing jobs older than 1 hour are also removed.
    """
    now = datetime.now()
    to_delete = []

    for job_id, job in _jobs.items():
        status = job.get("status", "pending")
        updated = job.get("updated_at", job.get("created_at", now))
        age = now - updated

        if status in ("completed", "failed"):
            # Remove after RETENTION_MINUTES
            if age > timedelta(minutes=RETENTION_MINUTES):
                to_delete.append(job_id)
        else:
            # Remove pending/processing jobs after 1 hour (stale jobs)
            if age > timedelta(hours=1):
                to_delete.append(job_id)

    for job_id in to_delete:
        del _jobs[job_id]
        logger.warning(f"Cleaned up job {job_id} (status={_jobs.get(job_id, {}).get('status', 'unknown')})")

    return len(to_delete)


def get_job_count() -> int:
    """Get current number of jobs in memory."""
    return len(_jobs)


def log_unfinished_jobs() -> list:
    """Return list of unfinished job IDs for logging on shutdown."""
    unfinished = [
        job_id for job_id, job in _jobs.items() if job["status"] in ("pending", "processing")
    ]
    return unfinished
