#!/usr/bin/env python3

"""YouTube Probe API - FastAPI service for YouTube search and transcription."""

import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Request/Response models
class TranscriptRequest(BaseModel):
    video: str = Field(..., description="YouTube URL or video ID")
    fallback: bool = Field(True, description="Use SoundBridge fallback if API fails")

class JobResponse(BaseModel):
    job_id: str
    status: str
    transcript: Optional[str] = None
    error: Optional[str] = None

# Lifespan manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # Startup
    logger.info("YouTube Probe API starting...")
    from api.jobs import cleanup_old_jobs
    cleanup_old_jobs()
    yield
    # Shutdown
    logger.info("YouTube Probe API shutting down...")
    from api.jobs import log_unfinished_jobs
    unfinished = log_unfinished_jobs()
    if unfinished:
        logger.info(f"Unfinished jobs: {unfinished}")

app = FastAPI(
    title="YouTube Probe API",
    description="Search YouTube videos and fetch transcripts with fallback to local transcription.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "YouTube Probe API"}

@app.get("/search")
def search(
    q: str,
    max_results: int = 10,
    order: str = "relevance",
    published_after: Optional[str] = None,
):
    """Search YouTube videos using official YouTube Data API v3.

    Requires YOUTUBE_API_KEY environment variable.

    Args:
        q: Search query string
        max_results: Maximum results (1-50, default 10)
        order: Sort order - relevance, date, rating, viewCount (default: relevance)
        published_after: ISO 8601 timestamp to filter videos published after this date
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    if max_results < 1 or max_results > 50:
        raise HTTPException(status_code=400, detail="max_results must be between 1 and 50")

    try:
        from api.youtube import search_videos
        results = search_videos(
            q,
            max_results=max_results,
            order=order,
            published_after=published_after,
        )

        if results is None:
            return {
                "query": q,
                "count": 0,
                "results": [],
                "message": "Search unavailable: YOUTUBE_API_KEY not configured",
            }

        return {"query": q, "count": len(results), "results": results}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

@app.post("/transcript", response_model=JobResponse)
def submit_transcript(
    request: TranscriptRequest,
    background_tasks: BackgroundTasks,
):
    """Submit a transcription job for a YouTube video.

    Returns a job_id immediately. Transcription happens in background.
    Poll GET /job/{job_id} for results.
    """
    from api.jobs import create_job
    from api.transcript import process_transcript_job

    try:
        job_id = create_job(request.video, fallback=request.fallback)
        background_tasks.add_task(process_transcript_job, job_id, request.video, request.fallback)

        return JobResponse(
            job_id=job_id,
            status="pending",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job")

@app.get("/job/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    """Get transcription job status and result."""
    from api.jobs import get_job as fetch_job

    job = fetch_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Filter job dict to only include fields in JobResponse
    return JobResponse(
        job_id=job_id,
        status=job["status"],
        transcript=job.get("transcript"),
        error=job.get("error"),
    )

@app.get("/")
def root():
    """Root endpoint with API info."""
    return {
        "name": "YouTube Probe API",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "search": "GET /search?q={query}&max_results={n}&order={relevance|date|rating|viewCount}&published_after={ISO8601}",
            "transcript": "POST /transcript",
            "job": "GET /job/{job_id}",
        },
        "docs": "/docs",
    }
