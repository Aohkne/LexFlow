# Backend image — dùng chung cho service `api` và `worker` (khác CMD).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Cài dependencies trước để tận dụng layer cache
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY eval ./eval
COPY data/corpus.sample.json ./data/corpus.sample.json

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# LanceDB nằm ở volume /app/data/lancedb (LANCEDB_PATH=data/lancedb)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
