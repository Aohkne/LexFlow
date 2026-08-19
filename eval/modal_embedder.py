"""Host một embedding model open (mặc định `minhquan6203/paraphrase-vietnamese-law`, chuyên luật VN)
trên Modal, expose endpoint `/embed` để `eval/vlqa_*` re-embed corpus VLQA vào bảng riêng và so recall
với `gemini-embedding-001`.

CHỈ ĐỂ THÍ NGHIỆM (T118 · KT5) — trả lời "embedding chuyên luật có nâng recall (11% gold ngoài top-20)
không?". KHÔNG phải dịch vụ đường sản phẩm. Scale-to-zero sau 5 phút rảnh.

Vì sao Modal: model là sentence-transformers (HuggingFace), máy user yếu + ràng buộc không tải HF local
→ đẩy GPU cloud. `paraphrase-vietnamese-law` = embedding bài báo SBV-LawGraph dùng (768-dim, max 300 token).

--- Deploy (một lần, ở máy user) ---
  uv tool install modal ; modal setup
  # dùng lại secret đã tạo cho reranker (RERANK_TOKEN); chưa có thì:
  #   modal secret create lexflow-rerank RERANK_TOKEN=<chuỗi-bí-mật-tự-đặt>
  modal deploy eval/modal_embedder.py
  # → in URL kiểu https://<workspace>--lexflow-embedder-web.modal.run

--- Gọi ---
  POST {URL}/embed   {"texts": ["...", "..."]}   header Authorization: Bearer <RERANK_TOKEN>
  → {"embeddings": [[...768...], ...], "dim": 768, "max_seq_length": 300}

Đổi model: đặt EMBED_MODEL_ID trong cùng secret (vd BAAI/bge-m3) hoặc sửa mặc định dưới rồi deploy lại.
"""
import os

import modal

_MODEL_MAC_DINH = "minhquan6203/paraphrase-vietnamese-law"

app = modal.App("lexflow-embedder")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("sentence-transformers>=3.0", "torch", "fastapi[standard]")
)


@app.function(
    image=image,
    gpu="T4",  # 0.3B model, batch encode — T4 dư
    scaledown_window=300,  # rảnh 5 phút → scale 0, không tính GPU idle
    secrets=[modal.Secret.from_name("lexflow-rerank")],
    timeout=600,
)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, Header, HTTPException
    from sentence_transformers import SentenceTransformer

    model_id = os.environ.get("EMBED_MODEL_ID", _MODEL_MAC_DINH)
    token = os.environ.get("RERANK_TOKEN", "")
    model = SentenceTransformer(model_id)  # nạp một lần mỗi container

    api = FastAPI()

    @api.post("/embed")
    def embed(body: dict, authorization: str = Header(default="")):
        # Endpoint công khai → chặn bằng token để không ai đốt GPU của user.
        if token and authorization != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="token sai")
        texts = body["texts"]
        bs = int(body.get("batch_size", 64))
        # normalize → cosine ≡ L2 (index LanceDB dùng L2). Model tuned CosineSimilarityLoss nên chuẩn hoá.
        vecs = model.encode(texts, batch_size=bs, normalize_embeddings=True, convert_to_numpy=True)
        return {
            "embeddings": [v.tolist() for v in vecs],
            "dim": int(vecs.shape[1]),
            "max_seq_length": int(model.max_seq_length),
        }

    return api
