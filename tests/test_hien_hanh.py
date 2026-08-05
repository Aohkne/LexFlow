from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.ingestion.vbpl_corpus import tho_theo_so_hieu
from app.ontology.hien_hanh import DonViOverlay, dung_overlay, phien_ban_hien_hanh
from app.ontology.tac_dong import CanhTacDong


def _c(nguon, dich, thao_tac="sua_doi"):
    return CanhTacDong(nguon=nguon, dich=dich, thao_tac=thao_tac, menh_lenh="x")


def test_dung_overlay_dedup_va_gan_doc_id():
    canh = [
        _c("41/2025/TT-NHNN#than/dieu_1", "40/2024/TT-NHNN#than/dieu_8#khoan_1"),
        _c("41/2025/TT-NHNN#than/dieu_1", "40/2024/TT-NHNN#than/dieu_8#khoan_2"),
        _c("22/2026/TT-NHNN#than/dieu_6", "41/2025/TT-NHNN#than/dieu_16", "bai_bo"),
    ]
    nodes: dict[str, DonViOverlay] = {n.khoa: n for n in dung_overlay(canh)}
    assert len(nodes) == 5  # 2 nguon + 3 dich, dieu_1 khong nhan doi
    assert nodes["40/2024/TT-NHNN#than/dieu_8#khoan_1"].doc_id == "TT40-2024"
    assert nodes["41/2025/TT-NHNN#than/dieu_1"].vai == "nguon_lenh"


def test_vua_nguon_vua_dich_thi_la_dich():
    """TT41 D16 phat lenh sua TT40 NHUNG chinh no bi TT22 bai — vai 'bi tac dong' thang."""
    canh = [
        _c("41/2025/TT-NHNN#than/dieu_16", "40/2024/TT-NHNN#than/dieu_41"),
        _c("22/2026/TT-NHNN#than/dieu_6", "41/2025/TT-NHNN#than/dieu_16", "bai_bo"),
    ]
    nodes: dict[str, DonViOverlay] = {n.khoa: n for n in dung_overlay(canh)}
    assert nodes["41/2025/TT-NHNN#than/dieu_16"].vai == "dich_bi_tac_dong"


# --- phien_ban_hien_hanh ---------------------------------------------------------
# `_ctd` thay vì `_c` — module đã có `_c` cho các test overlay phía trên, chữ ký khác.


def _ctd(nguon, dich, thao_tac, vf):
    return CanhTacDong(nguon=nguon, dich=dich, thao_tac=thao_tac, menh_lenh="x",
                       valid_from=vf)


_TT41_SUA = _ctd("41/2025/TT-NHNN#than/dieu_16", "40/2024/TT-NHNN#than/dieu_41",
                 "sua_doi", "2025-11-05")
_TT22_BAI = _ctd("22/2026/TT-NHNN#than/dieu_6", "41/2025/TT-NHNN#than/dieu_16",
                 "bai_bo", "2026-05-19")


def test_nguyen_ven_khi_khong_canh_nao_cham():
    pb = phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_1", [_TT41_SUA], "2026-08-05")
    assert pb.trang_thai == "nguyen_ven" and pb.cac_lan == []


def test_canh_chet_khong_duoc_ap():
    """Sau 19/05/2026, sửa đổi của TT41 Đ16 vào TT40 Đ41 KHÔNG còn áp (TT22 đã bãi Đ16)."""
    pb = phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_41", [_TT41_SUA, _TT22_BAI],
                             "2026-08-05")
    assert pb.trang_thai == "nguyen_ven"
    # còn TRƯỚC ngày TT22 hiệu lực thì cạnh sống:
    pb_cu = phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_41", [_TT41_SUA, _TT22_BAI],
                                "2026-01-01")
    assert pb_cu.trang_thai == "da_sua" and len(pb_cu.cac_lan) == 1


def test_bai_ca_dieu_thi_khoan_con_chet_nhung_khong_nuot_so_dai():
    bai = _ctd("S#than/dieu_1", "40/2024/TT-NHNN#than/dieu_1", "bai_bo", "2025-01-01")
    assert phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_1#khoan_2", [bai],
                               "2026-08-05").trang_thai == "bi_bai_bo"
    assert phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_11", [bai],
                               "2026-08-05").trang_thai == "nguyen_ven"  # dieu_1 ≠ dieu_11


def test_canh_tuong_lai_chua_ap():
    assert phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_41", [_TT41_SUA],
                               "2025-01-01").trang_thai == "nguyen_ven"


# --- Trên dữ liệu THẬT (05/08) ---------------------------------------------------

_GOC = Path("data/raw/vbpl")
_CAN = ("41/2025/TT-NHNN", "40/2024/TT-NHNN", "22/2026/TT-NHNN")
_CANH_TAC_DONG_JSONL = Path("eval/overlay/canh_tac_dong.jsonl")


def _thieu(*so_hieu: str) -> bool:
    bang = tho_theo_so_hieu(_GOC)
    return any(s not in bang for s in so_hieu)


@pytest.mark.skipif(
    _thieu(*_CAN) or not _CANH_TAC_DONG_JSONL.exists(),
    reason="chưa crawl đủ bản ghi vbpl hoặc thiếu eval/overlay/canh_tac_dong.jsonl",
)
def test_phien_ban_hien_hanh_tren_du_lieu_that():
    """Ca thật, đo trên corpus 05/08 (KHÔNG phải giả định của brief — xem ghi chú dưới).

    `canh_tac_dong.jsonl` thật có BA cạnh chạm `40/2024/TT-NHNN#than/dieu_41`, không phải
    hai như ví dụ đơn vị ở trên:
    - TT41 Đ16 -sua_doi-> TT40 Đ41 (valid_from 2025-11-05)
    - TT22 Đ6 khoản 2 -bai_bo-> TT41 Đ16 (valid_from 2026-05-19)
    - TT22 Đ1 -sua_doi-> TT40 Đ41, TRỰC TIẾP (valid_from 2026-05-19) — TT22 tự viết lại
      Điều 41 thay vì chỉ dựa vào bản TT41 đã sửa, rồi mới bãi bỏ TT41 Đ16 vì đã dư thừa.

    Vì vậy trạng thái hôm nay của TT40 Đ41 là `da_sua` (do cạnh TT22 Đ1 còn sống), KHÔNG
    phải `nguyen_ven` — đây là số đo được, không sửa code cho khớp một dự đoán sai. Luật
    cạnh-chết vẫn được kiểm chứng đúng chỗ nó có tác dụng: cạnh TT41 Đ16 (đã bị TT22 Đ6
    bãi) bị loại khỏi `cac_lan`, chỉ còn đúng 1 cạnh sống — của TT22 Đ1.

    Đếm tổng số đơn vị (khoá) `da_sua`/`bi_bai_bo` trên MỌI khoá đích xuất hiện trong
    `canh_tac_dong.jsonl` — số đo được (không phải đoán) để ghi vào WORKLOG.
    """
    canh = [
        CanhTacDong.model_validate_json(line)
        for line in _CANH_TAC_DONG_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    hom_nay = date.today().isoformat()

    pb = phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_41", canh, hom_nay)
    assert pb.trang_thai == "da_sua"
    # Luật cạnh-chết đã loại cạnh TT41 Đ16 (điều phát lệnh đã bị TT22 bãi bỏ) — chỉ còn
    # đúng cạnh TT22 Đ1 (trực tiếp, chưa từng bị ai bãi).
    assert len(pb.cac_lan) == 1
    assert pb.cac_lan[0].nguon.startswith("22/2026/TT-NHNN#than/dieu_1")

    # TRƯỚC ngày TT22 hiệu lực (2026-05-19), cạnh TT41 Đ16 còn sống — đúng ca chết-vì-thời-
    # gian mà brief mô tả, chỉ khác là quan sát ở "trước/sau" thay vì "có/không".
    pb_cu = phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_41", canh, "2026-01-01")
    assert pb_cu.trang_thai == "da_sua"
    assert len(pb_cu.cac_lan) == 1
    assert pb_cu.cac_lan[0].nguon.startswith("41/2025/TT-NHNN#than/dieu_16")

    dich_khoa = sorted({c.dich for c in canh})
    dem: dict[str, int] = {"nguyen_ven": 0, "da_sua": 0, "bi_bai_bo": 0}
    for khoa in dich_khoa:
        dem[phien_ban_hien_hanh(khoa, canh, hom_nay).trang_thai] += 1

    print(
        f"\n[phien_ban_hien_hanh @ {hom_nay}] {len(dich_khoa)} khoá đích: "
        f"nguyen_ven={dem['nguyen_ven']} da_sua={dem['da_sua']} bi_bai_bo={dem['bi_bai_bo']}"
    )
    assert dem["da_sua"] + dem["bi_bai_bo"] > 0
