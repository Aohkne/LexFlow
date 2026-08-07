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
# Corpus canonical khởi điểm — sau đó bản chuẩn sống trên Supabase Storage (corpus.json)
COPY data/corpus.real.json ./data/corpus.real.json
# Lớp phủ dưới-văn-bản: BẮT BUỘC có trong image. Runtime không đọc `data/raw/` (gitignored,
# không lên image), nên đây là nguồn duy nhất. Thiếu file này thì `tai_lop_phu()` trả None và
# lớp phủ tắt **trong im lặng** — fail-open nuốt gọn, deploy vẫn xanh mà tính năng không chạy.
COPY data/overlay/lop_phu.json ./data/overlay/lop_phu.json

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Cloud Run truyền $PORT (8080); compose/local mặc định 8000.
# LanceDB local nằm ở volume /app/data/lancedb — không cần khi dùng LanceDB Cloud.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
