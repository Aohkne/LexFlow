"""`push_corpus` xoá cạnh `THUOC` — đường ingest phải nối lại lớp phủ ngay sau đó.

`push_corpus` mở đầu bằng `MATCH (d:Document) DETACH DELETE d`, và `DETACH` xoá **mọi** cạnh
chạm các node đó, kể cả `THUOC` phát từ `(:DonVi)`. Node `DonVi` và cạnh `TAC_DONG` thì không
bị xoá (chúng không mang nhãn `Document`), nên đồ thị sau đó **trông vẫn có lớp phủ**: đủ nút,
đủ cạnh tác động, chỉ mất sạch đường nối về văn bản. Không lỗi, không cảnh báo.

Docstring của `push_overlay` đã ghi rõ "phải chạy lại SAU MỖI `push_corpus`" và để đó cho
người chạy nhớ. Ca này biến lời nhắc thành ràng buộc kiểm được.
"""
from __future__ import annotations

from app.core.schemas import CorpusDocument
from app.ingestion import pipeline


def _docs() -> list[CorpusDocument]:
    return [
        CorpusDocument.model_validate(
            {
                "doc_id": "TT40-2024",
                "title": "Thông tư 40/2024/TT-NHNN",
                "doc_type": "Thông tư",
                "source": "external",
                "valid_from": "2024-07-17",
                "so_hieu": "40/2024/TT-NHNN",
                "articles": [{"article": "Điều 1", "text": "Nội dung."}],
            }
        )
    ]


def _gia_lap_neo4j(monkeypatch) -> list[str]:
    """Ghi lại THỨ TỰ các bước chạm Neo4j, không gọi Aura thật."""
    thu_tu: list[str] = []
    # `neo4j_enabled` là property chỉ-đọc suy từ hai trường này — đặt thẳng vào trường để ca
    # test không phụ thuộc `.env` của máy đang chạy.
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "neo4j+s://test")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "test")
    monkeypatch.setattr(pipeline, "write_lancedb", lambda rows: len(rows))
    monkeypatch.setattr(
        "app.knowledge.graph.push_corpus",
        lambda *a, **k: thu_tu.append("push_corpus"),
    )
    monkeypatch.setattr(
        "app.knowledge.graph.push_overlay",
        lambda goi: (thu_tu.append("push_overlay"), (255, 178))[1],
    )
    return thu_tu


def test_ingest_noi_lai_lop_phu_sau_khi_nap_corpus(monkeypatch):
    thu_tu = _gia_lap_neo4j(monkeypatch)
    pipeline.ingest_docs(_docs(), [])
    assert thu_tu == ["push_corpus", "push_overlay"], (
        "thiếu push_overlay ⇒ 255 cạnh THUOC bị xoá mà không ai biết"
    )


def test_thieu_artefact_thi_canh_bao_chu_khong_ngat_ingest(monkeypatch, tmp_path, capsys):
    """Artefact thiếu không được làm hỏng lượt ingest — nhưng phải kêu."""
    thu_tu = _gia_lap_neo4j(monkeypatch)
    monkeypatch.setattr(pipeline, "_DUONG_DAN_LOP_PHU", tmp_path / "khong-co.json")

    pipeline.ingest_docs(_docs(), [])

    assert thu_tu == ["push_corpus"], "không có artefact thì không gọi push_overlay được"
    assert "lớp phủ" in capsys.readouterr().out
