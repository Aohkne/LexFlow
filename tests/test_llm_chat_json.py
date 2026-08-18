"""chat_json phải sống sót khi model trả JSON hoàn chỉnh kèm ĐUÔI RÁC.

Ca thật (judge PAYFAC Đ21, 16/08): response kết thúc `...}]}` rồi model thoái
hoá, in thêm các mảnh lặp (`luật]"}]}` · `]}"]}`). json.loads vỡ vì Extra data
→ cả lô verdict thành "LLM bỏ sót" trong im lặng.
"""
from types import SimpleNamespace

from app.core import llm


def _gia_lap_resp(monkeypatch, text: str) -> None:
    fake = SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda **_k: SimpleNamespace(text=text)))
    monkeypatch.setattr(llm, "get_client", lambda: fake)


def test_duoi_rac_sau_json_hop_le_van_parse_duoc(monkeypatch):
    _gia_lap_resp(monkeypatch, '{"phan_quyet": [{"cu_id": "A"}]}\nluật]"}]}\n]}"]}')
    assert llm.chat_json("x") == {"phan_quyet": [{"cu_id": "A"}]}


def test_json_sach_khong_doi_hanh_vi(monkeypatch):
    _gia_lap_resp(monkeypatch, '{"a": 1}')
    assert llm.chat_json("x") == {"a": 1}


def test_xuong_dong_that_trong_chuoi_van_parse_duoc(monkeypatch):
    # Ca thật (judge PAYFAC Đ23, 17/08): model quote văn bản luật có xuống dòng
    # THẬT trong string — JSON strict cấm control char, cả phiếu mất trắng và
    # temp 0 nên retry lặp y hệt. strict=False phải cứu được.
    _gia_lap_resp(monkeypatch, '{"quote_luat": "quy định tại\nĐiều 12"}')
    assert llm.chat_json("x") == {"quote_luat": "quy định tại\nĐiều 12"}


def test_embed_chia_lo_100(monkeypatch):
    # API BatchEmbedContents chỉ nhận ≤100/request (400 khi vượt, lộ 18/08 khi
    # từ vựng hypernym quá 100 mục) — _embed phải tự chia lô và nối kết quả.
    lo: list[int] = []

    def _gia_embed(**k):
        lo.append(len(k["contents"]))
        return SimpleNamespace(embeddings=[
            SimpleNamespace(values=[0.0]) for _ in k["contents"]])

    fake = SimpleNamespace(models=SimpleNamespace(embed_content=_gia_embed))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    ra = llm._embed([f"t{i}" for i in range(250)], "RETRIEVAL_DOCUMENT")
    assert lo == [100, 100, 50]
    assert len(ra) == 250


def test_cut_giua_chung_van_tra_raw(monkeypatch):
    # JSON đứt giữa chừng (không phải đuôi rác) — raw_decode cũng vỡ → giữ _raw
    _gia_lap_resp(monkeypatch, '{"phan_quyet": [{"cu_id": "A", "verd')
    ra = llm.chat_json("x")
    assert "_raw" in ra
