"""Nạp văn bản vbpl đã kiểm vào `data/corpus.real.json` — có vết, lặp được, không lặng lẽ.

Chạy:
    uv run python -m app.ingestion.nap_corpus            # data/raw/vbpl → data/corpus.real.json
    uv run python -m app.ingestion.nap_corpus --kho      # chỉ in việc sẽ làm, không ghi file

Ba quy tắc, mỗi quy tắc trả lời một ca đã gặp thật:

1. **Văn bản đã có trong corpus: thay `articles`, GIỮ `valid_from`/`valid_to` của corpus khi
   hai bên lệch** (kèm cảnh báo). Thuộc tính vbpl đã sai ít nhất một lần: trang ND52/2024 ghi
   `ngay_co_hieu_luc: 01/07/2027 — Chưa có hiệu lực`, trong khi chính Điều 37 của nó viết
   *"có hiệu lực thi hành từ ngày 01 tháng 7 năm 2024"*. Chữ trong luật thắng metadata.
2. **Văn bản mới: nhận ngày của vbpl, trừ khi `GHI_DE_CO_CAN_CU` nói khác** — và mỗi mục ghi
   đè phải mang câu trích từ toàn văn làm căn cứ, không có căn cứ thì không có mục.
3. **Cạnh mới chỉ vào khi CẢ HAI đầu nằm trong corpus.** Cạnh nửa vời đẩy xuống Neo4j sẽ bị
   `MATCH…MATCH` bỏ **im lặng** (bài học `push_corpus`); đầu mút chưa crawl là việc của tầng
   bắc cầu (`bac_cau.py`), không phải của file corpus.

Vì sao `TT22 -BAI_BO-> TT41` KHÔNG có trong `CANH_MOI` dù lược đồ vbpl ghi TT41 là *"Văn bản
bị bãi bỏ"* của TT22: toàn văn TT22 không có câu bãi bỏ nào, và chính vbpl gắn TT41
*"Hết hiệu lực một phần"* (không phải toàn bộ). Hai nguồn của vbpl mâu thuẫn nhau thì không
nguồn nào đủ làm căn cứ; thêm cạnh là phán định pháp lý, để người quyết.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.schemas import CorpusDocument
from app.ingestion.vbpl_corpus import KetQuaDoc, doc_thu_muc

_CORPUS = Path("data/corpus.real.json")
_VBPL = Path("data/raw/vbpl")

#: Ghi đè CÓ CĂN CỨ cho văn bản MỚI — `can_cu` là bắt buộc và phải trích được từ toàn văn.
GHI_DE_CO_CAN_CU: dict[str, dict[str, str]] = {
    "ND80-2016": {
        "valid_to": "2024-07-01",
        "can_cu": (
            "ND 52/2024 Điều 37: 'Nghị định này thay thế cho … Nghị định số 80/2016/NĐ-CP' — "
            "vbpl vẫn gắn ND80 'Còn hiệu lực', nhưng chữ trong luật thắng metadata"
        ),
    },
}

#: Cạnh mới, mỗi cạnh kèm `note` nêu bằng chứng. Đúng nếp `relationships` đang có.
CANH_MOI: list[dict] = [
    {
        "source_doc": "ND52-2024", "target_doc": "ND80-2016",
        "rel_type": "THAY_THE", "valid_from": "2024-07-01",
        "note": "ND 52/2024 Điều 37: 'Nghị định này thay thế cho … Nghị định số 80/2016/NĐ-CP'",
    },
    {
        "source_doc": "ND52-2024", "target_doc": "ND16-2019",
        "rel_type": "BAI_BO", "valid_from": "2024-07-01",
        "note": (
            "ND 52/2024 Điều 37: 'bãi bỏ Điều 3 của Nghị định số 16/2019/NĐ-CP' — bãi bỏ "
            "MỘT PHẦN, ND16 còn hiệu lực các điều khác (vbpl: 'Hết hiệu lực một phần')"
        ),
        "anchors": [{
            "source_article": "Điều 37", "target_article": "Điều 3",
            "detail": "Bãi bỏ Điều 3 (phần sửa đổi, bổ sung ND 101/2012)",
        }],
    },
    {
        "source_doc": "ND80-2016", "target_doc": "ND101-2012",
        "rel_type": "SUA_DOI_BO_SUNG", "valid_from": "2016-07-01",
        "note": "Sửa đổi, bổ sung một số điều của ND 101/2012 (tiêu đề + lược đồ vbpl)",
    },
    {
        "source_doc": "ND16-2019", "target_doc": "ND101-2012",
        "rel_type": "SUA_DOI_BO_SUNG", "valid_from": "2019-03-20",
        "note": (
            "Điều 3 sửa đổi, bổ sung, bãi bỏ một số điều của ND 101/2012; chính Điều 3 này "
            "bị ND 52/2024 bãi bỏ từ 2024-07-01"
        ),
        "anchors": [{"source_article": "Điều 3", "target_article": None,
                     "detail": "Sửa đổi, bổ sung, bãi bỏ một số điều của ND 101/2012"}],
    },
    {
        "source_doc": "TT41-2025", "target_doc": "TT40-2024",
        "rel_type": "SUA_DOI_BO_SUNG", "valid_from": "2025-11-05",
        "note": "27 điều, mỗi điều sửa đúng một điều của TT 40/2024 (Đ1→Đ8 … Đ25 thay Phụ lục)",
    },
    {
        "source_doc": "TT22-2026", "target_doc": "TT40-2024",
        "rel_type": "SUA_DOI_BO_SUNG", "valid_from": "2026-05-19",
        "note": "Sửa đổi, bổ sung một số điều của TT 40/2024 (tiêu đề + lược đồ vbpl)",
    },
    {
        "source_doc": "TT22-2026", "target_doc": "ND52-2024",
        "rel_type": "CAN_CU", "valid_from": "2026-05-19",
        "note": "Căn cứ ban hành (lược đồ vbpl)",
    },
    {
        "source_doc": "TT41-2025", "target_doc": "ND52-2024",
        "rel_type": "CAN_CU", "valid_from": "2025-11-05",
        "note": "Căn cứ ban hành (lược đồ vbpl)",
    },
    {
        "source_doc": "TT66-2025", "target_doc": "ND52-2024",
        "rel_type": "CAN_CU", "valid_from": "2026-02-15",
        "note": (
            "Căn cứ ban hành (lược đồ vbpl). Quan hệ chính của TT66 — sửa TT 34/2024 — "
            "KHÔNG vào corpus: TT34 chưa có toàn văn, tầng bắc cầu giữ cạnh đó"
        ),
    },
]


def tron_van_ban(corpus: dict, vb: CorpusDocument) -> list[str]:
    """Thay (giữ ngày corpus khi lệch) hoặc thêm một văn bản. → nhật ký việc đã làm."""
    docs = corpus["documents"]
    moi = vb.model_dump()
    for i, cu in enumerate(docs):
        if cu["doc_id"] != vb.doc_id:
            continue
        nhat_ky = [f"thay {vb.doc_id}: {len(cu['articles'])} → {len(moi['articles'])} điều"]
        for truong in ("valid_from", "valid_to"):
            if cu.get(truong) != moi.get(truong):
                nhat_ky.append(
                    f"  {vb.doc_id}.{truong}: vbpl {moi.get(truong)!r} ≠ corpus "
                    f"{cu.get(truong)!r} — GIỮ corpus (quy tắc 1: chữ trong luật thắng metadata)"
                )
                moi[truong] = cu.get(truong)
        moi["source"] = cu.get("source") or moi["source"]
        docs[i] = moi
        return nhat_ky
    docs.append(moi)
    return [f"thêm {vb.doc_id}: {len(moi['articles'])} điều"]


def tron_canh(corpus: dict, canh: dict) -> list[str]:
    """Thêm một cạnh nếu đủ hai đầu và chưa có. → nhật ký (kể cả lý do KHÔNG thêm)."""
    co = {d["doc_id"] for d in corpus["documents"]}
    thieu = {canh["source_doc"], canh["target_doc"]} - co
    ten = f"{canh['source_doc']} -{canh['rel_type']}-> {canh['target_doc']}"
    if thieu:
        return [f"BỎ cạnh {ten}: {', '.join(sorted(thieu))} chưa có trong corpus (quy tắc 3)"]
    khoa = (canh["source_doc"], canh["target_doc"], canh["rel_type"])
    rels = corpus["relationships"]
    if any((r.get("source_doc"), r.get("target_doc"), r.get("rel_type")) == khoa for r in rels):
        return []
    rels.append(canh)
    return [f"cạnh mới {ten}"]


def nap(corpus: dict, ket_qua: list[KetQuaDoc]) -> list[str]:
    """Trộn toàn bộ kết quả đọc + `CANH_MOI` vào corpus (sửa tại chỗ). → nhật ký."""
    nhat_ky: list[str] = []
    for kq in ket_qua:
        if kq.van_ban is None:
            ly_do = kq.canh_bao[-1] if kq.canh_bao else "không có văn bản"
            nhat_ky.append(f"bỏ qua {kq.so_hieu or kq.duong_dan}: {ly_do}")
            continue
        vb = kq.van_ban
        gd = GHI_DE_CO_CAN_CU.get(vb.doc_id)
        if gd:
            doi = {k: v for k, v in gd.items() if k != "can_cu"}
            vb = vb.model_copy(update=doi)
            nhat_ky.append(f"ghi đè {vb.doc_id} {doi} — {gd['can_cu']}")
        nhat_ky += tron_van_ban(corpus, vb)
    for canh in CANH_MOI:
        nhat_ky += tron_canh(corpus, canh)
    return nhat_ky


def main() -> int:
    ap = argparse.ArgumentParser(description="Nạp bản crawl vbpl vào corpus.real.json")
    ap.add_argument("--goc", default=str(_VBPL))
    ap.add_argument("--file", default=str(_CORPUS))
    ap.add_argument("--kho", action="store_true", help="chỉ in, không ghi")
    args = ap.parse_args()

    duong = Path(args.file)
    corpus = json.loads(duong.read_text(encoding="utf-8"))
    ket_qua = doc_thu_muc(Path(args.goc))
    for kq in ket_qua:
        for c in kq.canh_bao:
            print(f"[{kq.so_hieu or '?'}] {c}")

    nhat_ky = nap(corpus, ket_qua)
    for dong in nhat_ky:
        print(dong)
    print(f"\n→ {len(corpus['documents'])} văn bản · "
          f"{sum(len(d['articles']) for d in corpus['documents'])} điều · "
          f"{len(corpus['relationships'])} quan hệ")
    if args.kho:
        print("(--kho: chưa ghi gì)")
        return 0
    # KHÔNG qua shell redirect: PowerShell đổi encoding và làm lệch mọi char_span.
    duong.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"đã ghi {duong}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
