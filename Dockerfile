FROM python:3.13.2-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev \
    && pip install uv \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project || uv sync --no-install-project

COPY . .
RUN uv sync --frozen || uv sync
RUN chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
