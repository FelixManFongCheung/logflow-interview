FROM python:3.13-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv
COPY . .
RUN uv sync --frozen || uv sync

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
