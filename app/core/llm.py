"""Wrapper cho Google Gemini (google-genai SDK): chat, reasoning, embedding.

Toàn bộ tính toán chạy trên API → không cần model cục bộ (hợp máy yếu).
"""
from __future__ import annotations

import json
from functools import lru_cache

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

# gemini-embedding-001 hỗ trợ Matryoshka (MRL): cắt còn 768 chiều cho nhẹ.
EMBED_DIM = 768


@lru_cache
def get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("Chưa cấu hình GEMINI_API_KEY trong .env")
    return genai.Client(api_key=settings.gemini_api_key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def chat(prompt: str, *, system: str | None = None, reasoning: bool = False) -> str:
    """Sinh câu trả lời văn bản. `reasoning=True` dùng model mạnh hơn."""
    client = get_client()
    model = settings.gemini_reasoning_model if reasoning else settings.gemini_chat_model
    cfg = types.GenerateContentConfig(system_instruction=system) if system else None
    resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
    return (resp.text or "").strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def chat_json(prompt: str, *, system: str | None = None, reasoning: bool = True) -> dict:
    """Sinh JSON có cấu trúc (cho conflict detector, mapping...)."""
    client = get_client()
    model = settings.gemini_reasoning_model if reasoning else settings.gemini_chat_model
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
    )
    resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
    text = (resp.text or "{}").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    client = get_client()
    resp = client.models.embed_content(
        model=settings.gemini_embed_model,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type, output_dimensionality=EMBED_DIM
        ),
    )
    return [list(e.values) for e in resp.embeddings]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embedding cho văn bản đưa vào index."""
    if not texts:
        return []
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    """Embedding cho câu truy vấn."""
    return _embed([text], "RETRIEVAL_QUERY")[0]
