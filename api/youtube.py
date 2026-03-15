#!/usr/bin/env python3

"""YouTube Data API v3 integration for video search."""

from datetime import datetime
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def _validate_iso8601(timestamp: str) -> bool:
    """Validate ISO 8601 / RFC 3339 timestamp format."""
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]
    for fmt in formats:
        try:
            datetime.strptime(timestamp, fmt)
            return True
        except ValueError:
            continue
    return False


def search_videos(
    query: str,
    max_results: int = 10,
    order: str = "relevance",
    published_after: Optional[str] = None,
    lang: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional[List[Dict]]:
    """Search YouTube videos using Data API v3.

    Args:
        query: Search query string
        max_results: Maximum number of results (default: 10)
        order: Sort order - relevance, date, rating, viewCount (default: relevance)
        published_after: ISO 8601 timestamp to filter videos published after this date
        lang: Language code (BCP-47 or ISO 639-1) to filter by audio language (e.g., "en", "es")
        api_key: YouTube Data API key (uses env var if not provided)

    Returns:
        List of video dicts with keys: videoId, title, url, channelTitle,
        publishedAt, description, duration
        Returns None if API key is not configured or on error.

    Raises:
        ValueError: If max_results < 1 or > 50 or order is invalid
    """
    if max_results < 1 or max_results > 50:
        raise ValueError("max_results must be between 1 and 50")

    key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:
        logger.warning("YouTube search skipped: no YOUTUBE_API_KEY configured")
        return None

    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        logger.error(f"google-api-python-client not installed: {e}")
        raise ImportError(
            "Install with: uv pip install google-api-python-client"
        ) from e

    valid_orders = ["date", "rating", "relevance", "viewCount"]  # sorted for deterministic error message
    if order not in valid_orders:
        raise ValueError(f"order must be one of: {', '.join(valid_orders)}")

    if published_after and not _validate_iso8601(published_after):
        raise ValueError(
            "published_after must be ISO 8601 format (e.g., 2026-03-01T00:00:00Z)"
        )

    logger.info(f"Searching YouTube: query='{query}', max_results={max_results}, order={order}, published_after={published_after}, lang={lang}")

    try:
        youtube = build("youtube", "v3", developerKey=key)
        search_params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "order": order,
        }
        if published_after:
            search_params["publishedAfter"] = published_after
        if lang:
            search_params["relevanceLanguage"] = lang

        request = youtube.search().list(**search_params)
        response = request.execute()

        # Extract video IDs and snippet data
        video_ids = []
        snippet_data = {}
        for item in response.get("items", []):
            video_id = (item.get("id") or {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
                snippet_data[video_id] = item.get("snippet", {})

        # Get duration and audio language from videos endpoint (1 quota unit)
        duration_data = {}
        audio_lang_data = {}
        if video_ids:
            videos_request = youtube.videos().list(
                part="contentDetails,snippet",
                id=",".join(video_ids),
            )
            videos_response = videos_request.execute()
            for item in videos_response.get("items", []):
                video_id = item.get("id")
                if video_id:
                    duration_data[video_id] = item.get("contentDetails", {}).get("duration")
                    audio_lang_data[video_id] = item.get("snippet", {}).get("defaultAudioLanguage")

        # Build final items, filtering by audio language if specified
        items = []
        for video_id, snippet in snippet_data.items():
            audio_lang = audio_lang_data.get(video_id)

            # Filter by audio language if lang is specified
            if lang:
                # Skip videos without language metadata when language filter is requested
                if not audio_lang:
                    continue
                # Normalize comparison (e.g., "en-US" should match "en")
                if not (audio_lang == lang or audio_lang.startswith(f"{lang}-")):
                    continue

            items.append(
                {
                    "videoId": video_id,
                    "title": snippet.get("title"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "channelTitle": snippet.get("channelTitle"),
                    "publishedAt": snippet.get("publishedAt"),
                    "description": snippet.get("description"),
                    "duration": duration_data.get(video_id),
                    "defaultAudioLanguage": audio_lang,
                }
            )

        logger.info(f"Found {len(items)} videos for query: {query}" + (f" (filtered by lang={lang})" if lang else ""))
        return items

    except Exception as e:
        logger.error(f"YouTube search failed: {e}")
        raise


def get_video_details(video_id: str, api_key: Optional[str] = None) -> Optional[Dict]:
    """Get detailed information about a specific video.

    Args:
        video_id: YouTube video ID
        api_key: YouTube Data API key (uses env var if not provided)

    Returns:
        Dict with video details or None on error.
    """
    key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:
        logger.warning("Video details skipped: no YOUTUBE_API_KEY configured")
        return None

    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        logger.error(f"google-api-python-client not installed: {e}")
        return None

    try:
        youtube = build("youtube", "v3", developerKey=key)
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id,
        )
        response = request.execute()

        items = response.get("items", [])
        if not items:
            logger.warning(f"Video not found: {video_id}")
            return None

        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        return {
            "videoId": video_id,
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            "channelTitle": snippet.get("channelTitle"),
            "publishedAt": snippet.get("publishedAt"),
            "duration": item.get("contentDetails", {}).get("duration"),
            "viewCount": stats.get("viewCount"),
            "likeCount": stats.get("likeCount"),
        }

    except Exception as e:
        logger.error(f"Failed to get video details for {video_id}: {e}")
        return None
