FROM python:3.10-slim

# Install system packages
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ffmpeg \
    wget \
    bash \
    nodejs \
    npm \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install -U yt-dlp

# Copy project files
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1

# Expose port for Flask health check
EXPOSE 5000

# Start services
CMD ["bash", "-c", "flask run --host=0.0.0.0 --port=5000 & python3 main.py"]
