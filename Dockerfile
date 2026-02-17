FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
RUN chmod a+rx /usr/local/bin/yt-dlp

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir pyproject.toml

WORKDIR /app
COPY . .

# Expose port
EXPOSE 8743

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8743"]
