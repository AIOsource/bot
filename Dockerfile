FROM python:3.11-slim

LABEL version="2.0.0"
LABEL description="PRSBOT — Infrastructure Event Monitor"

WORKDIR /app

# Install system dependencies
# curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy application code
COPY *.py ./
COPY config/ ./config/

# Create data directory and set permissions
RUN mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set timezone
ENV TZ=Europe/Moscow
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite+aiosqlite:///data/prsbot.db

# Run the bot
CMD ["python", "main.py"]
