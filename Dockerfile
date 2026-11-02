FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose API port
EXPOSE 8000

# Environment variables
ENV HOST=0.0.0.0
ENV PORT=8000
ENV TRADE_STORE_DB=/app/data/trade_store.db
ENV ENABLE_SCHEDULER=True

VOLUME ["/app/data"]

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Launch application
CMD ["python", "main.py"]
