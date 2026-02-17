# YouTube Probe API

FastAPI service for YouTube video search and transcript extraction.

## What it does

- **Search**: Query YouTube videos using the official YouTube Data API v3
- **Transcript**: Get video transcripts with automatic fallback to local transcription

## How it works

1. **Search**: Calls YouTube Data API v3 to search for videos
2. **Transcript flow**:
   - Try YouTube transcript API first (fast, ~1 second)
   - If unavailable, fallback to SoundBridge service
   - SoundBridge downloads audio and transcribes using Parakeet model

## Dependencies

- **SoundBridge service**: Runs natively on Apple Silicon (M1/M2/M3/M4)
  - Address: `http://localhost:8742`
  - Model: Parakeet (MLX-Audio)
  - Required only for transcript fallback

## Endpoints

| Method | Path | Description |
|--------|-------|-------------|
| GET | `/health` | Health check |
| GET | `/search?q={query}` | Search YouTube videos |
| POST | `/transcript` | Submit transcription job |
| GET | `/job/{job_id}` | Get job status/result |

## Usage

```bash
# Run API
uv run uvicorn main:app --host 0.0.0.0 --port 8743

# Submit transcript
curl -X POST http://localhost:8743/transcript \
  -H "Content-Type: application/json" \
  -d '{"video": "https://youtube.com/watch?v=VIDEO_ID"}'

# Check job status
curl http://localhost:8743/job/{job_id}
```

## Environment

See `.env.example`:
- `YOUTUBE_API_KEY`: Required for search endpoint
- `SOUNDBRIDGE_URL`: Optional, defaults to `http://localhost:8742`

## Docker

```bash
docker build -t ytprobe .
docker run -p 8743:8743 --env-file .env ytprobe
```
