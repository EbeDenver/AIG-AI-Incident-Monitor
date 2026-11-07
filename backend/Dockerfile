# ==============================================================================
# AI Incident Monitor — Production Dockerfile for Google Cloud Run
# ==============================================================================

FROM python:3.13-slim AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install project build dependencies
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ==============================================================================
# Runner stage
# ==============================================================================
FROM python:3.13-slim AS runner

WORKDIR /app

# Install runtime PostgreSQL client library
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy application code, migrations, and canonical governance data
COPY --chown=appuser:appgroup alembic.ini ./
COPY --chown=appuser:appgroup alembic/ ./alembic/
COPY --chown=appuser:appgroup frameworks/ ./frameworks/
COPY --chown=appuser:appgroup src/ ./src/

# Install application package in editable/link mode
RUN pip install --no-cache-dir -e .

# Prepare data directory for local/scratch caching
RUN mkdir -p /app/.data && chown -R appuser:appgroup /app/.data

USER appuser

# Cloud Run defaults to container port 8080
ENV PORT=8080
ENV REPO_ROOT=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/api/v1/public/categories || exit 1

# Launch FastAPI app factory via Uvicorn
CMD ["sh", "-c", "uvicorn ai_incident_monitor.ui.app:create_app --factory --host 0.0.0.0 --port ${PORT} --workers 2"]
