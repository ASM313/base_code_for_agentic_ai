FROM python:3.11.11-slim-bookworm

WORKDIR /app

ARG APP_ENV=production

ENV APP_ENV=${APP_ENV} \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# ---------------------------------------------------------
# Install uv
# ---------------------------------------------------------
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ---------------------------------------------------------
# Upgrade Python packaging tools
# ---------------------------------------------------------
RUN python -m pip install --no-cache-dir --upgrade \
    pip \
    "setuptools>=78.1.1" \
    "wheel>=0.46.2"

# ---------------------------------------------------------
# System dependencies
# ---------------------------------------------------------
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# Install Python dependencies
# ---------------------------------------------------------
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

# ---------------------------------------------------------
# Copy application
# ---------------------------------------------------------
COPY . .

# ---------------------------------------------------------
# Fix entrypoint permissions / Windows CRLF
# ---------------------------------------------------------
RUN sed -i 's/\r$//' /app/scripts/docker-entrypoint.sh \
    && chmod +x /app/scripts/docker-entrypoint.sh

# ---------------------------------------------------------
# Create non-root user
# ---------------------------------------------------------
RUN useradd \
        --create-home \
        appuser \
    && mkdir -p /app/logs /app/uploads \
    && chown -R appuser:appuser /app

USER appuser

# ---------------------------------------------------------
# Application
# ---------------------------------------------------------
EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

CMD ["/app/.venv/bin/uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]