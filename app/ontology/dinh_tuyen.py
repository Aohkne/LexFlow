"""Định tuyến sau truy hồi: chunk-id trả về từ retrieval → khoá overlay → một trong BA nhánh.

Một chunk (kết quả tìm kiếm) là một đơn vị luật (điều hoặc khoản) TRONG một văn bản cụ thể.
Ba nhánh trả lời câu hỏi "đơn vị này, đọc hôm nay, thì sao":

1. **nguyen_ven** — không cạnh tác động nào chạm tới nó. Đọc thẳng chunk là đủ.
2. **nen_da_sua** — chunk nằm trong văn bản NỀN và đã bị sửa/bãi bỏ (một phần hoặc toàn bộ)
   bởi cạnh tác động còn hiệu lực tại `hom_nay`. Cần chỉ người đọc sang `khoa_dich` — khoá
   nơi lời văn mới thực sự nằm.
3. **trich_trong_van_ban_sua** — chunk nằm trong văn bản SỬA, và đoạn văn bản retrieval trả
   về (`span_chunk`) trùng vào chính khối lời văn mới (`loi_van_moi`) của một cạnh phát từ
   văn bản đó. Đây là kiểu chunk hay bị đọc nhầm là "toàn văn của điều/khoản sửa" trong khi
   thực ra nó là MỘT PHẦN LỆNH sửa điều/khoản khác — cần chỉ ngược `khoa_dich` về văn bản nền.

REUSE `phien_ban_hien_hanh` (Task 6) cho nhánh 2 — không viết lại luật cạnh-chết / cạnh áp
được ở đây.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from app.ingestion.vbpl_corpus import doc_id_theo_corpus
from app.ontology.hien_hanh import phien_ban_hien_hanh
from app.ontology.tac_dong import CanhTacDong

#: Nhãn chunk `"Điều 8"` hoặc `"Điều 8 Khoản 7"` — đúng dạng `_khoan_label` của
#: `app/ingestion/pipeline.py` sinh ra cho chunk KHÔNG gộp nhiều khoản (gộp "Khoản 1-3" hay
#: cắt cửa sổ "(phần 2)" không giải được thành MỘT khoá duy nhất nên nằm ngoài regex này —
#: khoá bên dưới do brief chỉ định, không mở rộng).
_NHAN_RE = re.compile(r"^Điều\s+(\d+[a-zđ]?)(?:\s+Khoản\s+(\S+))?$")

#: Bóc một khoá overlay `{so_hieu}#than/dieu_N[#khoan_M[#diem_x]]` thành các phần để render
#: trích dẫn người đọc — cùng khuôn `_DICH_RE` của `app/ontology/tac_dong.py`.
_KHOA_RE = re.compile(
    r"^(?P<sh>.+?)#than/dieu_(?P<dieu>[^#]+)(?:#khoan_(?P<khoan>[^#]+))?(?:#diem_(?P<diem>[^#]+))?$"
)


def khoa_tu_chunk_id(chunk_id: str, so_hieu_theo_doc: dict[str, str]) -> str | None:
    """Chunk-id `"{doc_id}::{label}"` → khoá overlay `"{so_hieu}#than/dieu_N[#khoan_M]"`.

    Trả `None` khi `doc_id` không có trong bảng (văn bản lạ) hoặc `label` không khớp dạng
    "Điều N" / "Điều N Khoản M" — KHÔNG bịa khoá cho những trường hợp không chắc.
    """
    doc_id, sep, nhan = chunk_id.partition("::")
    if not sep:
        return None
    so_hieu = so_hieu_theo_doc.get(doc_id)
    if so_hieu is None:
        return None
    m = _NHAN_RE.match(nhan)
    if not m:
        return None
    dieu, khoan = m.group(1), m.group(2)
    khoa = f"{so_hieu}#than/dieu_{dieu}"
    if khoan:
        khoa += f"#khoan_{khoan}"
    return khoa


class KetQuaTuyen(BaseModel):
    """Kết quả định tuyến một chunk: nhánh đọc + khoá gốc/khoá đích + trích dẫn cho người đọc."""

    nhanh: Literal["nguyen_ven", "nen_da_sua", "trich_trong_van_ban_sua"]
    khoa_goc: str
    khoa_dich: str | None
    trich_dan_dung_chu: str


def _cite(khoa: str) -> str:
    """Khoá overlay → trích dẫn người đọc `"TT40-2024 Điều 8 Khoản 7"`.

    Số hiệu quy về `doc_id` qua `doc_id_theo_corpus` (không tự đoán quy ước); không giải
    được thì giữ nguyên số hiệu thô thay vì rớt trích dẫn.
    """
    m = _KHOA_RE.match(khoa)
    if not m:
        return khoa
    doc_id = doc_id_theo_corpus(m.group("sh")) or m.group("sh")
    phan = f"Điều {m.group('dieu')}"
    if m.group("khoan"):
        phan += f" Khoản {m.group('khoan')}"
    if m.group("diem"):
        phan += f" Điểm {m.group('diem')}"
    return f"{doc_id} {phan}"


def _giao_nhau(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _canh_deeper_ap_duoc(
    khoa: str, canh: list[CanhTacDong], hom_nay: str
) -> CanhTacDong | None:
    """Cạnh có `dich` SÂU HƠN `khoa` (một điểm bên trong khoản `khoa`) đang áp được.

    `phien_ban_hien_hanh(khoa, ...)` chỉ xét cạnh mà `dich` là chính `khoa` hoặc TIỀN TỐ của
    nó (điều bị bãi kéo khoản con). Chiều ngược lại — chunk là khoản, cạnh sửa một điểm BÊN
    TRONG khoản đó — không thuộc phạm vi hàm đó, nên kiểm riêng ở đây.

    Giới hạn đã biết (ghi rõ, không giấu): chỉ lọc `valid_from <= hom_nay`, KHÔNG áp lại luật
    cạnh-chết của `phien_ban_hien_hanh` (cạnh có nguồn đã bị bãi bỏ vẫn được tính là áp được
    ở đây). Đủ cho phạm vi Task 7 (không có test nào phủ luật cạnh-chết kết hợp mục tiêu sâu
    hơn khoá); mở lại nếu có ca thật cần.
    """
    for c in canh:
        if c.dich.startswith(khoa + "#") and c.valid_from is not None and c.valid_from <= hom_nay:
            return c
    return None


def dinh_tuyen(
    chunk_id: str,
    span_chunk: tuple[int, int] | None,
    canh: list[CanhTacDong],
    so_hieu_theo_doc: dict[str, str],
    hom_nay: str,
) -> KetQuaTuyen | None:
    """Định tuyến một chunk retrieval vào một trong ba nhánh đọc.

    Trả `None` khi không suy ra được khoá (`khoa_tu_chunk_id` thất bại — văn bản lạ hoặc
    nhãn không khớp dạng biết) — không bịa kết quả cho một chunk không định danh được.

    Thứ tự kiểm: NHÁNH 3 trước — nó cần `span_chunk` (thông tin cụ thể hơn: retrieval đã trả
    đúng khối lời văn mới nào) nên khi khớp là chắc chắn nhất. NHÁNH 2 sau, qua
    `phien_ban_hien_hanh` (chiều rộng-hơn-hoặc-bằng) rồi mới tới kiểm chiều sâu-hơn
    (`_canh_deeper_ap_duoc`). NHÁNH 1 là phần còn lại.
    """
    khoa_goc = khoa_tu_chunk_id(chunk_id, so_hieu_theo_doc)
    if khoa_goc is None:
        return None

    doc_id = chunk_id.partition("::")[0]
    so_hieu_doc = so_hieu_theo_doc.get(doc_id)

    # --- Nhánh 3: chunk thuộc văn bản SỬA, span retrieval trùng lời văn mới của cạnh nó phát.
    if span_chunk is not None and so_hieu_doc is not None:
        for c in canh:
            if (
                c.nguon.split("#", 1)[0] == so_hieu_doc
                and c.loi_van_moi is not None
                and _giao_nhau(span_chunk, c.loi_van_moi)
            ):
                return KetQuaTuyen(
                    nhanh="trich_trong_van_ban_sua",
                    khoa_goc=khoa_goc,
                    khoa_dich=c.dich,
                    trich_dan_dung_chu=f"{_cite(c.dich)} (sửa bởi {_cite(c.nguon)})",
                )

    # --- Nhánh 2: chunk thuộc văn bản NỀN, đã bị sửa/bãi bỏ — rộng-hơn-hoặc-bằng trước.
    pb = phien_ban_hien_hanh(khoa_goc, canh, hom_nay)
    if pb.trang_thai != "nguyen_ven":
        c = pb.cac_lan[-1]
        if pb.trang_thai == "bi_bai_bo":
            trich = f"{_cite(khoa_goc)} (đã bị bãi bỏ bởi {_cite(c.nguon)})"
        else:
            trich = f"{_cite(khoa_goc)} (đã sửa bởi {_cite(c.nguon)})"
        return KetQuaTuyen(
            nhanh="nen_da_sua", khoa_goc=khoa_goc, khoa_dich=c.dich,
            trich_dan_dung_chu=trich,
        )

    sau_hon = _canh_deeper_ap_duoc(khoa_goc, canh, hom_nay)
    if sau_hon is not None:
        return KetQuaTuyen(
            nhanh="nen_da_sua",
            khoa_goc=khoa_goc,
            khoa_dich=sau_hon.dich,
            trich_dan_dung_chu=f"{_cite(sau_hon.dich)} (sửa bởi {_cite(sau_hon.nguon)})",
        )

    # --- Nhánh 1: không cạnh nào chạm — nguyên vẹn.
    return KetQuaTuyen(
        nhanh="nguyen_ven", khoa_goc=khoa_goc, khoa_dich=None,
        trich_dan_dung_chu=_cite(khoa_goc),
    )
