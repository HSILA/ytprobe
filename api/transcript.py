#!/usr/bin/env python3

"""Transcript fetching with SoundBridge MLX-Audio service fallback."""

import os
import logging
import time
import tempfile
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)

# SoundBridge service URL (default: localhost:8742)
SOUNDBRIDGE_URL = os.getenv("SOUNDBRIDGE_URL", "http://localhost:8742")


def get_transcript_from_api(video_id: str, languages=("en",)) -> str:
    """Fetch transcript using youtube-transcript-api.

    Args:
        video_id: YouTube video ID
        languages: List of language codes to try

    Returns:
        Plain text transcript

    Raises:
        NoTranscriptFound: No transcript available
        TranscriptsDisabled: Transcripts disabled for video
        VideoUnavailable: Video is not available
    """
    logger.info(f"Fetching transcript from API for {video_id}")

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=languages)
        text = " ".join([segment.text for segment in transcript])
        logger.info(f"API transcript fetched: {len(text)} characters")
        return text
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
        logger.info(f"API transcript not available: {type(e).__name__}")
        raise


def download_audio(video_url: str, output_path: str) -> str:
    """Download audio from YouTube using yt-dlp.

    Args:
        video_url: Full YouTube video URL
        output_path: Output file path

    Returns:
        Path to downloaded audio file

    Raises:
        RuntimeError: If download fails
    """
    logger.info(f"Downloading audio from {video_url}")

    try:
        import yt_dlp
    except ImportError as e:
        logger.error(f"yt-dlp not installed: {e}")
        raise ImportError(
            "Install with: uv pip install yt-dlp"
        ) from e

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        logger.info(f"Audio downloaded to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Audio download failed: {e}")
        raise RuntimeError(f"Failed to download audio: {e}") from e


def transcribe_with_soundbridge(audio_path: str, poll_interval: int = 5) -> str:
    """Send audio to SoundBridge service for transcription.

    Args:
        audio_path: Path to audio file
        poll_interval: Seconds between status checks (default: 5)

    Returns:
        Transcribed text

    Raises:
        RuntimeError: If transcription fails or times out
    """
    logger.info(f"Sending audio to SoundBridge: {audio_path}")

    # Upload file
    with open(audio_path, "rb") as f:
        try:
            response = requests.post(
                f"{SOUNDBRIDGE_URL}/transcribe",
                files={"file": f},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"SoundBridge upload failed: {e}")
            raise RuntimeError(f"SoundBridge service unavailable: {e}") from e

    data = response.json()
    job_id = data.get("job_id")
    if not job_id:
        raise RuntimeError("SoundBridge did not return job_id")

    logger.info(f"SoundBridge job submitted: {job_id}")

    # Poll for result
    max_attempts = 120  # 10 minutes with 5s intervals
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f"{SOUNDBRIDGE_URL}/job/{job_id}",
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Poll attempt {attempt + 1} failed: {e}")
            time.sleep(poll_interval)
            continue

        data = response.json()
        status = data.get("status")

        if status == "completed":
            transcript = data.get("transcript")
            if not transcript:
                raise RuntimeError("SoundBridge completed with empty transcript")
            logger.info(f"SoundBridge transcription complete: {len(transcript)} characters")
            return transcript
        elif status == "failed":
            error = data.get("error", "Unknown error")
            raise RuntimeError(f"SoundBridge transcription failed: {error}")
        elif status in ("pending", "processing"):
            logger.debug(f"SoundBridge status: {status} (attempt {attempt + 1})")
        else:
            logger.warning(f"Unknown SoundBridge status: {status}")

        time.sleep(poll_interval)

    raise RuntimeError(f"SoundBridge transcription timed out after {max_attempts * poll_interval}s")


def get_transcript(video_id: str, fallback: bool = True) -> str:
    """Get transcript with SoundBridge fallback.

    Args:
        video_id: YouTube video ID
        fallback: If True, use SoundBridge when API fails

    Returns:
        Plain text transcript

    Raises:
        ValueError: If video_id is invalid
        NoTranscriptFound: If no transcript available and fallback=False
        RuntimeError: If transcription fails
    """
    if not video_id or len(video_id) != 11:
        raise ValueError(f"Invalid video_id: {video_id}")

    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Try YouTube transcript API first
    try:
        return get_transcript_from_api(video_id)
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
        if not fallback:
            raise

    # Fallback to SoundBridge
    if not fallback:
        raise NoTranscriptFound(f"No transcript available for {video_id}")

    logger.info(f"Using SoundBridge fallback for {video_id}")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, f"{video_id}.mp3")
        download_audio(video_url, audio_path)
        return transcribe_with_soundbridge(audio_path)


def process_transcript_job(job_id: str, video: str, fallback: bool = True):
    """Process transcript job in background.

    Args:
        job_id: Job identifier
        video: YouTube URL or video ID
        fallback: Use SoundBridge fallback if API fails
    """
    from urllib.parse import urlparse, parse_qs

    logger.info(f"Processing transcript job {job_id} for {video}")

    # Extract video_id from URL if needed
    if "/" in video or "?" in video:
        u = urlparse(video)
        qs = parse_qs(u.query)
        if "v" in qs:
            video_id = qs["v"][0]
        elif u.path and u.netloc == "youtu.be":
            video_id = u.path.strip("/").split("/")[0]
        else:
            raise ValueError(f"Invalid video URL: {video}")
    else:
        video_id = video

    # Update job status using jobs module (lazy import to avoid circular)
    from api.jobs import update_job

    update_job(job_id, status="processing")

    try:
        transcript = get_transcript(video_id, fallback=fallback)
        update_job(job_id, status="completed", transcript=transcript)
    except Exception as e:
        logger.error(f"Transcription job {job_id} failed: {e}")
        update_job(job_id, status="failed", error=str(e))


def check_soundbridge_health() -> bool:
    """Check if SoundBridge service is healthy.

    Returns:
        True if SoundBridge is healthy, False otherwise
    """
    try:
        response = requests.get(f"{SOUNDBRIDGE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False
