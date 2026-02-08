FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY config/ ./config/

# Create data directory for SQLite
RUN mkdir -p /app/data

# Set timezone
ENV TZ=Europe/Moscow
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite+aiosqlite:///data/prsbot.db

# Run the bot
CMD ["python", "main.py"]
