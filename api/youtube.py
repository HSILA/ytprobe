#!/usr/bin/env python3

"""YouTube Data API v3 integration for video search."""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def search_videos(
    query: str,
    max_results: int = 10,
    api_key: Optional[str] = None,
) -> Optional[List[Dict]]:
    """Search YouTube videos using Data API v3.

    Args:
        query: Search query string
        max_results: Maximum number of results (default: 10)
        api_key: YouTube Data API key (uses env var if not provided)

    Returns:
        List of video dicts with keys: videoId, title, url, channelTitle,
        publishedAt, description, duration
        Returns None if API key is not configured or on error.

    Raises:
        ValueError: If max_results < 1 or > 50
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

    logger.info(f"Searching YouTube: query='{query}', max_results={max_results}")

    try:
        youtube = build("youtube", "v3", developerKey=key)
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results,
            order="relevance",
        )
        response = request.execute()

        # Extract video IDs and snippet data
        video_ids = []
        snippet_data = {}
        for item in response.get("items", []):
            video_id = (item.get("id") or {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
                snippet_data[video_id] = item.get("snippet", {})

        # Get duration from videos endpoint (1 quota unit)
        duration_data = {}
        if video_ids:
            videos_request = youtube.videos().list(
                part="contentDetails",
                id=",".join(video_ids),
            )
            videos_response = videos_request.execute()
            for item in videos_response.get("items", []):
                video_id = item.get("id")
                if video_id:
                    duration_data[video_id] = item.get("contentDetails", {}).get("duration")

        # Build final items
        items = []
        for video_id, snippet in snippet_data.items():
            items.append(
                {
                    "videoId": video_id,
                    "title": snippet.get("title"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "channelTitle": snippet.get("channelTitle"),
                    "publishedAt": snippet.get("publishedAt"),
                    "description": snippet.get("description"),
                    "duration": duration_data.get(video_id),
                }
            )

        logger.info(f"Found {len(items)} videos for query: {query}")
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
