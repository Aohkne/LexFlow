"""LexFlow — Hoa Tiêu Pháp Lý. FastAPI backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, chat, graph
from app.core.config import settings

app = FastAPI(
    title="LexFlow — Hoa Tiêu Pháp Lý",
    description="Trợ lý pháp lý tra cứu quy định ngân hàng (Advanced RAG + Knowledge Graph)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
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
