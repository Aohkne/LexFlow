"""Lược đồ vbpl.vn → cạnh quan hệ theo TẬP ĐÓNG 13 mã của KG v0.5 §6.

vbpl.vn (Cơ sở dữ liệu quốc gia về pháp luật) đã mô hình hoá sẵn đúng thứ v0.5 §6 đặc tả:
`luoc_do.outgoing` / `luoc_do.incoming`, mỗi nhóm mang một **nhãn tiếng Việt** trùng với
một trong hai cột "nhãn đầu chủ động / nhãn đầu bị động" của bảng 13 quan hệ.

**Chiều mũi tên là thứ `outgoing`/`incoming` nói ra, không phải thứ nhãn nói ra:**

    outgoing  ⇒  văn bản đang xem là ĐẦU NGUỒN   (current → listed)
    incoming  ⇒  văn bản đang xem là ĐẦU ĐÍCH    (listed → current)

Quy tắc này đồng nhất cho cả 13 mã, kể cả cặp #8 bất quy tắc (*căn cứ ban hành* ⟷ *áp dụng*)
nơi hai nhãn không chung gốc từ. Đo trên `data/raw/vbpl/sample.json` (trang ND 52/2024):

    outgoing  "Căn cứ ban hành"     → 10 Luật    ⇒ ND52 -[:CAN_CU]-> Luật
    incoming  "Văn bản áp dụng"     → 20 Thông tư ⇒ TT   -[:CAN_CU]-> ND52

Chính nhóm thứ hai chứa **TT 15/2024, 17/2024, 18/2024, 40/2024** — bốn văn bản mà corpus
đang gán `HUONG_DAN → ND52`. Chúng KHÔNG nằm ở nhóm *"Văn bản quy định chi tiết, hướng dẫn
thi hành"* (nhóm đó chỉ có TT 34/2024). Nói cách khác, quan hệ đúng là **`CAN_CU`**, và
`HUONG_DAN` là một loại tự đặt đã gộp nhầm hai thứ khác nhau.

Bảng nhãn ở đây **suy ra từ `REL_TYPES`**, không gõ tay: một mã bị thêm/sửa ở
`app/core/schemas.py` thì bảng này đi theo, không thể trôi khỏi tập đóng.

Nhãn lạ ⇒ **báo ra**, không đoán và cũng không bỏ im lặng: vbpl có thể dùng những nhãn mà
18 fixture hiện tại chưa gặp, và đoán bừa một mã là cách `HUONG_DAN` đã sinh ra.
"""
from __future__ import annotations

import re
import unicodedata

from app.core.schemas import REL_TYPES, Relationship

#: "Nghị định số 101/2012/NĐ-CP …" → "101/2012/NĐ-CP"; cũng bắt "14/2022/QH15" (không gạch nối).
SO_HIEU_RE = re.compile(r"\b\d+[a-zA-Z]?/\d{4}/[A-ZĐ]+[A-ZĐ\d]*(?:-[A-ZĐ\d]+)*\b")

_KHOANG = re.compile(r"\s+")
_TIEN_TO = re.compile(r"^văn\s*bản\s+", re.IGNORECASE)


def chuan_hoa_nhan(s: str) -> str:
    """Nhãn lược đồ → dạng so khớp. Bỏ tiền tố "Văn bản", dấu phẩy, hoa/thường, khoảng trắng.

    Bỏ dấu phẩy vì v0.5 và vbpl viết khác nhau ở đúng chỗ đó ("sửa đổi bổ sung" vs "sửa đổi,
    bổ sung"). An toàn: `test_quan_he_13` canh rằng sau khi chuẩn hoá, 26 nhãn của 13 mã vẫn
    **phân biệt được từng cái**, nên phép bỏ dấu phẩy không gộp nhầm hai quan hệ.
    """
    s = unicodedata.normalize("NFC", s).replace(",", " ")
    return _KHOANG.sub(" ", _TIEN_TO.sub("", s).strip()).casefold()


def _dung_bang() -> dict[str, str]:
    """{nhãn đã chuẩn hoá → mã}, dựng từ CẢ HAI nhãn của mỗi mã trong `REL_TYPES`."""
    bang: dict[str, str] = {}
    for ma, cap in REL_TYPES.items():
        for nhan in cap:
            bang[chuan_hoa_nhan(nhan)] = ma
    return bang


#: Tra cứu nhãn (chủ động lẫn bị động) → mã. Xem `_dung_bang`.
MA_THEO_NHAN: dict[str, str] = _dung_bang()


def so_hieu_tu_tieu_de(tieu_de: str) -> str | None:
    """Trích số hiệu từ tiêu đề vbpl. `None` khi không có — không bịa khoá."""
    m = SO_HIEU_RE.search(tieu_de or "")
    return m.group(0) if m else None


def doc_luoc_do(sample: dict) -> tuple[list[Relationship], list[str]]:
    """Một bản ghi vbpl → (cạnh theo 13 mã v0.5, cảnh báo).

    Cạnh khoá bằng **số hiệu** (`52/2024/NĐ-CP`) chứ không phải `doc_id` (`ND52-2024`):
    số hiệu là khoá v0.5 dùng, và nó có sẵn trong dữ liệu vbpl. Quy về `doc_id` là việc của
    bước nạp, sau khi có trường bắc cầu `so_hieu` trên `DocumentMeta`.

    Cảnh báo (không ném lỗi) cho: nhãn lạ, và mục không đọc được số hiệu. Cả hai đều là
    "chưa quy được về khoá", không phải "dữ liệu hỏng" — bỏ im lặng mới là hỏng.
    """
    canh: list[Relationship] = []
    canh_bao: list[str] = []

    goc = so_hieu_tu_tieu_de(sample.get("thuoc_tinh", {}).get("so_hieu", "")) or (
        sample.get("thuoc_tinh", {}).get("so_hieu") or ""
    ).strip()
    if not goc:
        return [], ["không đọc được số hiệu của chính văn bản đang xem"]

    for chieu in ("outgoing", "incoming"):
        for nhan, ds in (sample.get("luoc_do", {}).get(chieu) or {}).items():
            ma = MA_THEO_NHAN.get(chuan_hoa_nhan(nhan))
            if ma is None:
                canh_bao.append(
                    f"{chieu}: nhãn {nhan!r} không thuộc 13 quan hệ v0.5 — bỏ qua "
                    f"{len(ds)} văn bản, cần người ánh xạ"
                )
                continue
            for x in ds:
                tieu_de = x.get("title", "") if isinstance(x, dict) else str(x)
                kia = so_hieu_tu_tieu_de(tieu_de)
                if not kia:
                    canh_bao.append(
                        f"{chieu}/{nhan}: không đọc được số hiệu từ {tieu_de[:70]!r}"
                    )
                    continue
                # ĐÂY là chỗ chiều mũi tên được quyết: theo outgoing/incoming, không theo nhãn.
                src, tgt = (goc, kia) if chieu == "outgoing" else (kia, goc)
                canh.append(
                    Relationship(
                        source_doc=src,
                        target_doc=tgt,
                        rel_type=ma,
                        note=tieu_de[:200] or None,
                    )
                )
    return canh, canh_bao
