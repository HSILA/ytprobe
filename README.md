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

## API Specification

### Endpoints

| Method | Path | Description |
|--------|-------|-------------|
| GET | `/health` | Health check |
| GET | `/search?q={query}&max_results={n}` | Search YouTube videos |
| POST | `/transcript` | Submit transcription job |
| GET | `/job/{job_id}` | Get job status/result |

### /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "YouTube Probe API"
}
```

### /search

Search YouTube videos using Data API v3.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| q | string | Yes | - | Search query |
| max_results | integer | No | 10 | Max results (1-50) |

**Response:**
```json
{
  "query": "coffee tutorial",
  "count": 10,
  "results": [
    {
      "videoId": "abc123",
      "title": "Video Title",
      "url": "https://www.youtube.com/watch?v=abc123",
      "channelTitle": "Channel Name",
      "publishedAt": "2024-01-15T10:30:00Z",
      "description": "Video description text...",
      "duration": "PT10M30S"
    }
  ]
}
```

### /transcript

Submit a transcription job for a YouTube video.

**Request Body:**
```json
{
  "video": "https://youtube.com/watch?v=VIDEO_ID",
  "fallback": true
}
```

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| video | string | Yes | - | YouTube URL or video ID |
| fallback | boolean | No | true | Use SoundBridge fallback if API fails |

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-4466554400000",
  "status": "pending",
  "transcript": null,
  "error": null
}
```

### /job/{job_id}

Get transcription job status and result.

**Job Statuses:**
| Status | Description |
|--------|-------------|
| pending | Job queued, waiting to process |
| processing | Currently transcribing |
| completed | Transcribed, transcript available |
| failed | Transcription failed, error message available |

**Response (pending/processing):**
```json
{
  "job_id": "...",
  "status": "processing",
  "transcript": null,
  "error": null
}
```

**Response (completed):**
```json
{
  "job_id": "...",
  "status": "completed",
  "transcript": "Transcribed text content...",
  "error": null
}
```

**Response (failed):**
```json
{
  "job_id": "...",
  "status": "failed",
  "transcript": null,
  "error": "Video unavailable"
}
```

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

## Testing

```bash
# Install test dependencies
uv pip install -e ".[dev]"

# Run all tests
uv run pytest

# Run specific test class
uv run pytest tests/test_api.py::TestHealth

# Run with coverage
uv run pytest --cov=api --cov=main
```

## Docker

### Build and Run

```bash
# Build the image
docker build -t ytprobe .

# Run the container (exposes port 8743 on 0.0.0.0)
docker run -p 8743:8743 --env-file .env ytprobe

# Run in background
docker run -d --name ytprobe -p 8743:8743 --env-file .env ytprobe
```

### Network Access

The container exposes port `8743` on `0.0.0.0`, allowing other services and clients to connect via:

- **Localhost**: `http://localhost:8743`
- **Local IP**: Find your Mac's IP, e.g. `http://192.168.1.5:8743`
- **Docker network**: From other containers, use service name: `http://ytprobe:8743`

**Get your local IP:**
```bash
# macOS/Linux
ipconfig getifaddr en0 | awk '/inet/ {print $2}'

# Or use hostname -I
hostname -I
```

**Example: Connecting from another machine:**
```bash
# If your Mac IP is 192.168.1.5
curl http://192.168.1.5:8743/health
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
services:
  ytprobe:
    build: .
    ports:
      - "8743:8743"
    env_file:
      - .env
    network_mode: "host"  # For SoundBridge access from host
```
