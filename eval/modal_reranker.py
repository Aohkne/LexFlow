"""Host một cross-encoder reranker open (mặc định ViRanker, tuned tiếng Việt) trên Modal, expose
endpoint CÙNG SHAPE Jina/Cohere để `eval/thu_rerank.py` cắm vào không phải sửa mã.

CHỈ ĐỂ THÍ NGHIỆM (T114) — so ViRanker/bge với Jina/Cohere trước khi quyết có đáng host reranker
cho production không. KHÔNG phải dịch vụ của đường sản phẩm. Scale-to-zero sau 5 phút rảnh.

Vì sao Modal chứ không API: ViRanker (`namdp-ptit/ViRanker`) và `BAAI/bge-reranker-v2-m3` là các
reranker mạnh nhất cho tiếng Việt/pháp lý, không nhà cung cấp API nào phục vụ — phải tự host GPU,
mà máy user yếu nên đẩy lên cloud.

--- Deploy (một lần, ở máy user) ---
  pip install modal                     # hoặc: uv tool install modal
  modal setup                           # đăng nhập tài khoản Modal
  modal secret create lexflow-rerank RERANK_TOKEN=<chuỗi-bí-mật-tự-đặt>
  modal deploy eval/modal_reranker.py
  # → in ra URL kiểu https://<workspace>--lexflow-reranker-web.modal.run

--- Trỏ thí nghiệm vào Modal (.env) ---
  RERANK_URL=https://<workspace>--lexflow-reranker-web.modal.run/rerank
  RERANK_MODEL=viranker                 # nhãn tự do, chỉ để tách file cache
  RERANK_API_KEY=<chuỗi-bí-mật-tự-đặt>  # đúng RERANK_TOKEN ở trên
  # rồi: uv run python -u eval/thu_rerank.py --bo eval/bo_sbv.jsonl

Đổi sang bge-reranker-v2-m3: đặt biến MODEL_ID trong cùng secret (thêm MODEL_ID=BAAI/bge-reranker-v2-m3)
hoặc sửa mặc định dưới đây rồi deploy lại.
"""
import os

import modal

# AITeamVN/Vietnamese_Reranker = bge-reranker-v2-m3 fine-tune thêm 1.1M triplet tiếng Việt (Acc@1
# 0.79 vs bge-m3 0.57 trên Zalo-legal eval). Ứng viên KT2b — ViRanker (VN-general) đã thua Cohere,
# cái này cùng base bge-reranker-v2-m3 + train VN nhiều hơn. Đổi qua MODEL_ID trong secret nếu cần.
_MODEL_MAC_DINH = "AITeamVN/Vietnamese_Reranker"

app = modal.App("lexflow-reranker")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "sentence-transformers>=3.0", "torch", "fastapi[standard]",
        "tiktoken", "sentencepiece", "protobuf",  # tokenizer bge-m3/AITeamVN cần khi convert slow→fast
    )
)


@app.function(
    image=image,
    gpu="T4",  # đủ cho rerank 20 cặp câu ngắn; rẻ nhất
    scaledown_window=300,  # rảnh 5 phút → scale về 0, không tính tiền GPU idle
    secrets=[modal.Secret.from_name("lexflow-rerank")],
)
@modal.asgi_app()
def web():
    import torch
    from fastapi import FastAPI, Header, HTTPException
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_id = os.environ.get("MODEL_ID", _MODEL_MAC_DINH)
    token = os.environ.get("RERANK_TOKEN", "")
    max_len = int(os.environ.get("MAX_LENGTH", "512"))
    # Dùng thẳng transformers (đúng cách model card khuyến nghị) thay vì sentence-transformers
    # CrossEncoder: bản ST mới gọi AutoProcessor, fail trên các repo reranker chỉ có tokenizer
    # (AITeamVN/Vietnamese_Reranker). Path này chạy cho mọi reranker sequence-classification
    # single-logit: bge-reranker-v2-m3, ViRanker, AITeamVN. Nạp một lần mỗi container.
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id).to("cuda").eval()

    api = FastAPI()

    @api.post("/rerank")
    def rerank(body: dict, authorization: str = Header(default="")):
        # Endpoint công khai trên Internet → chặn bằng token để không ai đốt GPU của user.
        if token and authorization != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="token sai")
        query = body["query"]
        docs = body["documents"]
        top_n = int(body.get("top_n", len(docs)))
        pairs = [[query, d] for d in docs]
        with torch.no_grad():
            enc = tok(pairs, padding=True, truncation=True, max_length=max_len, return_tensors="pt").to("cuda")
            scores = model(**enc).logits.view(-1).float().cpu().tolist()  # single-logit/pair
        order = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)[:top_n]
        # Trả đúng shape Jina/Cohere: results[].index (+ relevance_score) đã xếp giảm dần.
        return {"results": [{"index": i, "relevance_score": float(scores[i])} for i in order]}

    return api
