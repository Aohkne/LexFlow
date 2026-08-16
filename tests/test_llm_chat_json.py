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


def test_cut_giua_chung_van_tra_raw(monkeypatch):
    # JSON đứt giữa chừng (không phải đuôi rác) — raw_decode cũng vỡ → giữ _raw
    _gia_lap_resp(monkeypatch, '{"phan_quyet": [{"cu_id": "A", "verd')
    ra = llm.chat_json("x")
    assert "_raw" in ra
