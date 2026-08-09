"""LexFlow — Hoa Tiêu Pháp Lý. FastAPI backend."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, chat, documents, graph, reviews
from app.core import tracing
from app.core.config import settings


# Uvicorn chỉ gắn handler cho `uvicorn.*`. Không cấu hình gốc thì mọi `logger.info` của
# `app.*` rơi vào hư không, và `logger.warning` chỉ thoát ra nhờ `logging.lastResort` — tức
# đúng những dòng ta cần đọc trong Cloud Run logs thì không có. `basicConfig` là no-op nếu
# root đã có handler, nên nó nhường cho cấu hình bên ngoài mà không giành.
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)
# Đặt mức thẳng trên namespace `app`, không dựa vào mức của root: `basicConfig` là no-op khi
# root đã có handler (pytest gắn sẵn một cái), và khi đó root vẫn ở WARNING — tức dòng log
# boot lại mất hút, đúng chỗ vừa vá xong.
logging.getLogger("app").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def _bao_lop_phu() -> None:
    """Nói ra ngay lúc boot là lớp phủ có nạp được không.

    Nạp luôn ở đây (thay vì đợi lượt hỏi đầu tiên) vì hai lẽ: dòng log này chỉ có thật khi đã
    thử nạp, và lượt chat đầu tiên khỏi phải trả giá parse artefact. Không nạp được thì vẫn
    chạy tiếp — fail-open là quyết định có chủ đích, cái thiếu lâu nay chỉ là tiếng nói.
    """
    from app.knowledge.lop_phu import tinh_trang

    tt = tinh_trang()
    if not tt["bat"]:
        logger.info("lớp phủ: TẮT theo cấu hình (overlay_router=false)")
    elif tt["nap"]:
        logger.info("lớp phủ: %d cạnh, sinh %s", tt["so_canh"], tt["sinh_luc"])
    else:
        logger.warning(
            "lớp phủ: KHÔNG nạp được %s — badge hiệu lực sẽ vắng mặt trên toàn sản phẩm",
            tt["duong_dan"],
        )


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _bao_lop_phu()
    yield
    tracing.shutdown()  # flush trace Langfuse trước khi Cloud Run tắt instance


app = FastAPI(
    title="LexFlow — Hoa Tiêu Pháp Lý",
    description="Trợ lý pháp lý tra cứu quy định ngân hàng (Advanced RAG + Knowledge Graph)",
    version="0.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # FRONTEND_ORIGIN nhận nhiều origin cách nhau dấu phẩy (localhost + Vercel)
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(graph.router)
app.include_router(reviews.router)


@app.get("/")
def root() -> dict:
    return {"app": "LexFlow", "docs": "/docs"}
