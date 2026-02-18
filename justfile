# YouTube Probe API - Just commands
# Run `just --list` to see all available commands

# Default: list all commands
default:
    @just --list

# ============================================
# Docker commands
# ============================================

# Build Docker image
build:
    docker build -t ytprobe .

# Run container in foreground
run:
    docker run --rm -p 8743:8743 --env-file .env ytprobe

# Run container in background (detached)
run-d:
    docker run -d --name ytprobe -p 8743:8743 --env-file .env ytprobe

# Run container with auto-restart (starts on boot, restarts on failure)
run-auto:
    docker run -d --name ytprobe --restart unless-stopped -p 8743:8743 --env-file .env ytprobe

# Stop container
stop:
    docker stop ytprobe 2>/dev/null || true

# Restart container
restart:
    docker restart ytprobe

# Tail container logs
logs:
    docker logs -f ytprobe

# Remove container
rm: stop
    docker rm ytprobe 2>/dev/null || true

# Remove dangling images
prune:
    docker image prune -f

# Full refresh: stop, remove, build, run in background
refresh: rm prune build
    docker run -d --name ytprobe -p 8743:8743 --env-file .env ytprobe

# Full refresh with auto-restart
refresh-auto: rm prune build
    docker run -d --name ytprobe --restart unless-stopped -p 8743:8743 --env-file .env ytprobe

# ============================================
# Development commands
# ============================================

# Run API locally with uvicorn (no Docker)
dev:
    uv run uvicorn main:app --host 0.0.0.0 --port 8743 --reload

# Run all tests
test:
    uv run pytest -v

# Run tests with coverage
test-cov:
    uv run pytest --cov=api --cov=main --cov-report=term-missing

# Install dependencies
install:
    uv sync

# Install dev dependencies
install-dev:
    uv pip install -e ".[dev]"

# ============================================
# Quick API checks
# ============================================

# Health check
health:
    curl -s http://localhost:8743/health | python3 -m json.tool

# Test search endpoint
search query="test":
    curl -s "http://localhost:8743/search?q={{query}}&max_results=3" | python3 -m json.tool

# Submit transcript job
transcript video:
    curl -s -X POST http://localhost:8743/transcript \
        -H "Content-Type: application/json" \
        -d '{"video": "{{video}}"}' | python3 -m json.tool

# Get job status
job job_id:
    curl -s "http://localhost:8743/job/{{job_id}}" | python3 -m json.tool

# ============================================
# Utilities
# ============================================

# Clean up Python cache files
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true

# Get local IP address for network access
ip:
    @ipconfig getifaddr en0 2>/dev/null || echo "Run: ipconfig getifaddr en0"

# ============================================
# Setup
# ============================================

# Initial project setup
setup:
    @if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; else echo ".env already exists"; fi
    uv sync
    @echo "\nSetup complete! Edit .env with your API keys, then run:"
    @echo "  just dev       # Run locally"
    @echo "  just run-auto  # Run in Docker with auto-restart"
