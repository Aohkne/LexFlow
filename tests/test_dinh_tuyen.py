from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.pipeline import build_chunks, load_corpus
from app.ontology.dinh_tuyen import dinh_tuyen, khoa_tu_chunk_id
from app.ontology.tac_dong import CanhTacDong

_SH = {"TT40-2024": "40/2024/TT-NHNN", "TT41-2025": "41/2025/TT-NHNN"}
_CANH = [CanhTacDong(nguon="41/2025/TT-NHNN#than/dieu_1#khoan_1",
                     dich="40/2024/TT-NHNN#than/dieu_8#khoan_7",
                     thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(1000, 1500),
                     valid_from="2025-11-05")]


def test_khoa_tu_chunk_id():
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 Khoản 7", _SH) == \
        "40/2024/TT-NHNN#than/dieu_8#khoan_7"
    assert khoa_tu_chunk_id("TT40-2024::Điều 8", _SH) == "40/2024/TT-NHNN#than/dieu_8"
    assert khoa_tu_chunk_id("LA-J::Điều 1", _SH) is None  # doc lạ → không bịa


def test_ba_nhanh():
    v = dinh_tuyen("TT40-2024::Điều 1", None, _CANH, _SH, "2026-08-05")
    assert v.nhanh == "nguyen_ven"
    v = dinh_tuyen("TT40-2024::Điều 8 Khoản 7", None, _CANH, _SH, "2026-08-05")
    assert v.nhanh == "nen_da_sua" and v.khoa_dich == "40/2024/TT-NHNN#than/dieu_8#khoan_7"
    v = dinh_tuyen("TT41-2025::Điều 1 Khoản 1", (900, 1200), _CANH, _SH, "2026-08-05")
    assert v.nhanh == "trich_trong_van_ban_sua"
    assert "TT40-2024" in v.trich_dan_dung_chu and "sửa bởi" in v.trich_dan_dung_chu


# --- Review round 1, important: nhánh 2 "sâu hơn khoá" phải dùng ĐÚNG luật cạnh-chết của
# `phien_ban_hien_hanh` (qua route công khai `phien_ban_hien_hanh(nguon, ...)`), không tự
# lọc valid_from một mình — cạnh A sửa N#Điều5#Khoản2 (sâu hơn chunk "Điều 5") do S1#Điều9
# phát ra; cạnh B bãi bỏ chính S1#Điều9 từ 2026-01-01. Sau ngày đó, cạnh A phải coi là chết.
_SH_SAU_HON = {"ND": "N"}
_CANH_SAU_HON = [
    CanhTacDong(nguon="S1#than/dieu_9", dich="N#than/dieu_5#khoan_2",
                thao_tac="sua_doi", menh_lenh="x", valid_from="2025-01-01"),
    CanhTacDong(nguon="S2#than/dieu_1", dich="S1#than/dieu_9",
                thao_tac="bai_bo", menh_lenh="x", valid_from="2026-01-01"),
]


def test_nhanh_2_sau_hon_khoa_chet_theo_nguon_bi_bai_bo():
    v_sau = dinh_tuyen("ND::Điều 5", None, _CANH_SAU_HON, _SH_SAU_HON, "2026-08-05")
    assert v_sau.nhanh == "nguyen_ven"  # cạnh A chết: nguồn S1#Điều9 đã bị B bãi bỏ

    v_truoc = dinh_tuyen("ND::Điều 5", None, _CANH_SAU_HON, _SH_SAU_HON, "2025-06-01")
    assert v_truoc.nhanh == "nen_da_sua"  # trước ngày B áp, cạnh A còn sống
    assert v_truoc.khoa_dich == "N#than/dieu_5#khoan_2"


# --- Review round 2, F1: nhãn GỘP nhiều khoản không được mint khoá khoản bịa -------------
#
# `"Điều 8 Khoản 1-6"` không phải một khoản thật — không cho ra `#khoan_1-6` mà rơi về khoá
# CẤP ĐIỀU `#than/dieu_8`, để `_canh_deeper_ap_duoc` (nhánh 2, chiều sâu hơn) dò tiếp được
# cạnh sửa/bãi một khoản/điểm BÊN TRONG điều đó. Dùng dữ liệu THẬT (data/corpus.real.json +
# eval/overlay/canh_tac_dong.jsonl) vì hai ca này (điểm a khoản 5 sửa bởi TT41, khoản 4 bãi
# bỏ bởi TT41) chỉ xảy ra ở corpus thật, không đáng dựng lại bằng fixture giả.


def test_nhan_gop_khoan_khong_bia_khoa_khoan():
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 Khoản 1-6", _SH) == "40/2024/TT-NHNN#than/dieu_8"
    assert khoa_tu_chunk_id("TT40-2024::Điều 24 Khoản 1-4", _SH) == "40/2024/TT-NHNN#than/dieu_24"
    # Cắt cửa sổ ký tự vẫn ngoài phạm vi — không bịa khoá cho dạng đó.
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 (phần 2)", _SH) is None


@pytest.mark.skipif(
    not Path("data/corpus.real.json").exists()
    or not Path("eval/overlay/canh_tac_dong.jsonl").exists(),
    reason="thiếu data/corpus.real.json hoặc eval/overlay/canh_tac_dong.jsonl",
)
def test_nhan_gop_khoan_route_nen_da_sua_tren_corpus_that():
    docs, _rels = load_corpus(Path("data/corpus.real.json"))
    so_hieu_theo_doc = {d.doc_id: d.so_hieu for d in docs}
    canh = [
        CanhTacDong.model_validate_json(line)
        for line in Path("eval/overlay/canh_tac_dong.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # TT40 Đ8 Khoản 1-6 gộp — chứa khoản 5 (điểm a bị SỬA bởi TT41 Đ1 Khoản 1) — trước khi
    # sửa "\S+" -> "\d+[a-zđ]?" chunk này rớt khỏi mọi cạnh (mint "#khoan_1-6" không tồn tại).
    v = dinh_tuyen("TT40-2024::Điều 8 Khoản 1-6", None, canh, so_hieu_theo_doc, "2026-08-05")
    assert v is not None and v.nhanh == "nen_da_sua"

    # TT40 Đ24 Khoản 1-4 gộp — chứa khoản 4 (bị BÃI BỎ bởi TT41 Đ8) — cùng lỗi, khác điều/thao
    # tác (kèm F3: câu trích phải nói "bãi bỏ", không "sửa bởi").
    v = dinh_tuyen("TT40-2024::Điều 24 Khoản 1-4", None, canh, so_hieu_theo_doc, "2026-08-05")
    assert v is not None and v.nhanh == "nen_da_sua"
    assert v.khoa_dich == "40/2024/TT-NHNN#than/dieu_24#khoan_4"
    assert "đã bị bãi bỏ bởi" in v.trich_dan_dung_chu
    assert "TT41-2025" in v.trich_dan_dung_chu


# --- Review round 2, F3: nhánh 2 chiều-sâu-hơn phải nói ĐÚNG thao tác (bãi bỏ ≠ sửa) -----

_CANH_SAU_HON_BAI_BO = [
    CanhTacDong(nguon="S1#than/dieu_9#khoan_2", dich="N#than/dieu_5#khoan_3#diem_c",
                thao_tac="bai_bo", menh_lenh="x", valid_from="2025-01-01"),
]


def test_nhanh_2_sau_hon_bai_bo_khong_noi_sua_boi():
    v = dinh_tuyen("ND::Điều 5", None, _CANH_SAU_HON_BAI_BO, _SH_SAU_HON, "2026-08-05")
    assert v.nhanh == "nen_da_sua"
    assert "đã bị bãi bỏ bởi" in v.trich_dan_dung_chu
    assert "sửa bởi" not in v.trich_dan_dung_chu


# --- Review round 2, F2: nhánh 3 (trích trong văn bản sửa) phải gate qua hiệu lực hôm nay --
#
# TT41-2025 Đ16 sửa TT40 Đ41 (valid_from 2025-11-05); chính Đ16 đó bị TT22-2026 Đ6 Khoản 2
# bãi bỏ từ 2026-05-19 (luật cạnh-chết). Span vẫn khớp `loi_van_moi` của cạnh TT41 Đ16 →
# TT40 Đ41 dù cạnh đó có còn áp được hay không — chỉ câu trích dẫn phải đổi theo hôm_nay.

_SH_NHANH3 = {"S": "S", "T": "T", "U": "U"}
_CANH_NHANH3 = [
    CanhTacDong(nguon="T#than/dieu_16", dich="S#than/dieu_41",
                thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(100, 200),
                valid_from="2025-11-05"),
    CanhTacDong(nguon="U#than/dieu_6#khoan_2", dich="T#than/dieu_16",
                thao_tac="bai_bo", menh_lenh="y", valid_from="2026-05-19"),
]


def test_nhanh_3_gate_hieu_luc_hom_nay():
    # Trước ngày TT22 bãi Đ16 TT41 áp được: cạnh còn sống, câu trích "sửa bởi" bình thường.
    v_truoc = dinh_tuyen("T::Điều 16", (120, 180), _CANH_NHANH3, _SH_NHANH3, "2026-01-01")
    assert v_truoc.nhanh == "trich_trong_van_ban_sua"
    assert v_truoc.trich_dan_dung_chu == "S Điều 41 (sửa bởi T Điều 16)"

    # Sau ngày đó: cạnh chết theo luật cạnh-chết dù span vẫn khớp — câu trích phải nói rõ
    # đã hết hiệu lực và chỉ ra ai bãi bỏ.
    v_sau = dinh_tuyen("T::Điều 16", (120, 180), _CANH_NHANH3, _SH_NHANH3, "2026-08-05")
    assert v_sau.nhanh == "trich_trong_van_ban_sua"
    assert "không còn áp dụng" in v_sau.trich_dan_dung_chu
    assert "đã bị bãi bỏ bởi U Điều 6 Khoản 2" in v_sau.trich_dan_dung_chu
    assert "từng được sửa bởi T Điều 16" in v_sau.trich_dan_dung_chu


# --- Bộ câu hỏi gắn nhãn TAY trên dữ liệu THẬT (Task 8) --------------------------------
#
# `eval/overlay/cau_hoi_nhan.jsonl` gắn nhãn bằng cách ĐỌC từng chunk + cạnh liên quan
# (không chạy `dinh_tuyen` trước rồi chép lại — xem `ghi_chu` của từng dòng để thấy lý lẽ
# pháp lý/toạ độ span). `hom_nay` CỐ ĐỊNH "2026-08-05" cho toàn bộ file nhãn — sau
# `valid_from` lớn nhất trong `canh_tac_dong.jsonl` (2026-05-19) nên mọi cạnh đều đã áp.

_CORPUS_REAL = Path("data/corpus.real.json")
_CANH_TAC_DONG_JSONL = Path("eval/overlay/canh_tac_dong.jsonl")
_CAU_HOI_NHAN_JSONL = Path("eval/overlay/cau_hoi_nhan.jsonl")
_HOM_NAY = "2026-08-05"


@pytest.mark.skipif(
    not (_CORPUS_REAL.exists() and _CANH_TAC_DONG_JSONL.exists() and _CAU_HOI_NHAN_JSONL.exists()),
    reason="thiếu data/corpus.real.json, eval/overlay/canh_tac_dong.jsonl hoặc "
    "eval/overlay/cau_hoi_nhan.jsonl",
)
def test_bo_cau_hoi_nhan_khop_100_phan_tram():
    docs, _rels = load_corpus(_CORPUS_REAL)
    so_hieu_theo_doc = {d.doc_id: d.so_hieu for d in docs}
    chunk_theo_id = {c["id"]: c for c in build_chunks(docs)}

    canh = [
        CanhTacDong.model_validate_json(line)
        for line in _CANH_TAC_DONG_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    hang = [
        json.loads(line)
        for line in _CAU_HOI_NHAN_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(hang) >= 10

    nhanh_thay = {"nguyen_ven", "nen_da_sua", "trich_trong_van_ban_sua"}
    assert {h["nhanh_dung"] for h in hang} == nhanh_thay  # phủ đủ cả 3 nhánh

    sai: list[str] = []
    for h in hang:
        # Chunk phải thật sự có trong corpus — nhãn không được trỏ vào một id bịa.
        assert h["chunk_id"] in chunk_theo_id, f"chunk lạ: {h['chunk_id']}"

        span = tuple(h["span"]) if h["span"] is not None else None
        v = dinh_tuyen(h["chunk_id"], span, canh, so_hieu_theo_doc, _HOM_NAY)
        assert v is not None, f"không định tuyến được: {h['chunk_id']}"
        if v.nhanh != h["nhanh_dung"]:
            sai.append(f"{h['chunk_id']}: nhãn={h['nhanh_dung']!r} nhưng dinh_tuyen={v.nhanh!r}")

        # Trường tuỳ chọn (review round 2, F5): dòng nào có ghi kỳ vọng một đoạn trong câu
        # trích dẫn thì phải kiểm luôn — không chỉ đúng NHÁNH mà còn đúng CHỮ người đọc thấy.
        trich_dan_chua = h.get("trich_dan_chua")
        if trich_dan_chua is not None and trich_dan_chua not in v.trich_dan_dung_chu:
            sai.append(
                f"{h['chunk_id']}: trích dẫn thiếu {trich_dan_chua!r} — "
                f"thực tế={v.trich_dan_dung_chu!r}"
            )

    assert not sai, "\n".join(sai)
    print(f"\n[cau_hoi_nhan] {len(hang)}/{len(hang)} khớp nhãn tại hôm_nay={_HOM_NAY}")
