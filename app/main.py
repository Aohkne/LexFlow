"""LexFlow — Hoa Tiêu Pháp Lý. FastAPI backend."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, chat, graph
from app.core import tracing
from app.core.config import settings


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
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
app.include_router(graph.router)


@app.get("/")
def root() -> dict:
    return {"app": "LexFlow", "docs": "/docs"}
