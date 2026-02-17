#!/usr/bin/env python3

"""Tests for YouTube Probe API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    import os
    os.environ.setdefault("YOUTUBE_API_KEY", "test_key")
    os.environ.setdefault("SOUNDBRIDGE_URL", "http://localhost:8742")


class TestHealth:
    """Health endpoint tests."""

    def test_health_endpoint(self):
        """Health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "YouTube Probe API"

    def test_root_endpoint(self):
        """Root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "YouTube Probe API"
        assert "endpoints" in data
        assert "docs" in data


class TestSearch:
    """Search endpoint tests."""

    def test_search_missing_query(self, mock_env):
        """Search without query parameter returns 422 (validation error)."""
        response = client.get("/search")
        assert response.status_code == 422

    def test_search_empty_query(self, mock_env):
        """Search with empty query returns 400."""
        response = client.get("/search?q=")
        assert response.status_code == 400

    def test_search_invalid_max_results(self, mock_env):
        """Search with invalid max_results returns 400."""
        response = client.get("/search?q=test&max_results=0")
        assert response.status_code == 400

    def test_search_without_api_key(self, mock_env):
        """Search without API key returns empty results."""
        import os
        old_key = os.environ.pop("YOUTUBE_API_KEY", None)
        response = client.get("/search?q=coffee")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        if old_key:
            os.environ["YOUTUBE_API_KEY"] = old_key

    def test_search_success(self, mock_env):
        """Search with valid query returns structured response."""
        response = client.get("/search?q=test&max_results=5")
        assert response.status_code == 200
        data = response.json()
        # Verify response structure (may be empty if no API key)
        assert "query" in data
        assert "count" in data
        assert "results" in data
        assert data["query"] == "test"


class TestTranscript:
    """Transcript endpoint tests."""

    def test_transcript_missing_video(self, mock_env):
        """Transcript without video field returns 422 (validation error)."""
        response = client.post("/transcript", json={})
        assert response.status_code == 422

    def test_transcript_submit(self, mock_env):
        """Submit transcript job returns job_id."""
        with patch("api.transcript.process_transcript_job"):
            response = client.post(
                "/transcript",
                json={"video": "https://youtube.com/watch?v=test123"}
            )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_transcript_submit_with_fallback_disabled(self, mock_env):
        """Submit transcript with fallback=False."""
        with patch("api.transcript.process_transcript_job"):
            response = client.post(
                "/transcript",
                json={"video": "test123", "fallback": False}
            )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data


class TestJob:
    """Job endpoint tests."""

    def test_job_not_found(self):
        """Get non-existent job returns 404."""
        response = client.get("/job/nonexistent-job-id")
        assert response.status_code == 404

    def test_job_pending(self, mock_env):
        """Get pending job returns pending status."""
        from api.jobs import create_job
        job_id = create_job("test123", fallback=True)

        response = client.get(f"/job/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "pending"
        assert data["transcript"] is None

    def test_job_completed(self, mock_env):
        """Get completed job returns transcript."""
        from api.jobs import create_job, update_job
        job_id = create_job("test123")
        update_job(job_id, status="completed", transcript="test transcript")

        response = client.get(f"/job/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert data["transcript"] == "test transcript"

    def test_job_failed(self, mock_env):
        """Get failed job returns error."""
        from api.jobs import create_job, update_job
        job_id = create_job("test123")
        update_job(job_id, status="failed", error="test error")

        response = client.get(f"/job/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "test error"


class TestJobsModule:
    """Jobs module tests."""

    def test_create_job(self):
        """Job creation returns valid job_id."""
        from api.jobs import create_job, get_job, get_job_count

        initial_count = get_job_count()
        job_id = create_job("test_video")
        assert len(job_id) == 36  # UUID length
        assert get_job_count() == initial_count + 1

        job = get_job(job_id)
        assert job is not None
        assert job["video"] == "test_video"
        assert job["status"] == "pending"
        assert job["transcript"] is None
        assert job["error"] is None

    def test_get_job_not_found(self):
        """Get non-existent job returns None."""
        from api.jobs import get_job
        assert get_job("nonexistent") is None

    def test_update_job_status(self):
        """Update job status works."""
        from api.jobs import create_job, update_job, get_job

        job_id = create_job("test_video")
        update_job(job_id, status="processing")

        job = get_job(job_id)
        assert job["status"] == "processing"

    def test_update_job_transcript(self):
        """Update job with transcript works."""
        from api.jobs import create_job, update_job, get_job

        job_id = create_job("test_video")
        transcript = "This is a test transcript"
        update_job(job_id, status="completed", transcript=transcript)

        job = get_job(job_id)
        assert job["status"] == "completed"
        assert job["transcript"] == transcript

    def test_update_job_error(self):
        """Update job with error works."""
        from api.jobs import create_job, update_job, get_job

        job_id = create_job("test_video")
        error = "Test error message"
        update_job(job_id, status="failed", error=error)

        job = get_job(job_id)
        assert job["status"] == "failed"
        assert job["error"] == error

    def test_update_job_nonexistent(self):
        """Update non-existent job returns False."""
        from api.jobs import update_job
        result = update_job("nonexistent", status="processing")
        assert result is False

    def test_cleanup_old_jobs(self):
        """Cleanup removes old jobs."""
        from api.jobs import create_job, update_job, get_job_count, cleanup_old_jobs
        from datetime import timedelta

        # Create a completed job (should be removed)
        job_id = create_job("old_video")
        update_job(job_id, status="completed", transcript="old transcript")

        # Mock the job's updated_at to be old
        from api.jobs import _jobs
        _jobs[job_id]["updated_at"] = _jobs[job_id]["updated_at"] - timedelta(minutes=10)

        count = cleanup_old_jobs()
        assert count == 1
        assert job_id not in _jobs

    def test_log_unfinished_jobs(self):
        """Log unfinished jobs returns correct list."""
        from api.jobs import create_job, update_job, log_unfinished_jobs

        # Create jobs in different states
        job1 = create_job("video1")
        job2 = create_job("video2")
        job3 = create_job("video3")

        update_job(job1, status="processing")
        update_job(job2, status="completed")
        update_job(job3, status="failed")

        unfinished = log_unfinished_jobs()
        assert job1 in unfinished
        assert job2 not in unfinished
        assert job3 not in unfinished


@pytest.fixture(autouse=True)
def cleanup_jobs():
    """Clean up jobs after each test."""
    yield
    from api.jobs import _jobs
    _jobs.clear()
