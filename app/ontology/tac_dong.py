"""Mệnh lệnh tác động trong văn bản sửa đổi → cạnh con↔con của lớp phủ.

Vì sao đọc ĐỘNG TỪ MỞ ĐẦU chứ không tìm từ khoá trong cả câu: câu lệnh luật luôn mở đầu
bằng động từ ("Sửa đổi…", "Bãi bỏ…", "Bổ sung…"), còn giữa câu có thể nhắc thao tác khác
("…đã được sửa đổi bởi…" là mô tả, không phải lệnh). IGNORECASE bắt buộc: mệnh đề đứng
đầu khoản viết hoa — grep thường đã một lần bỏ sót câu bãi bỏ của TT22 (05/08).

Thứ tự khớp có chủ đích: `thay_cum_tu`/`thay_phu_luc` trước `sua_doi` — "Thay thế cụm từ"
cũng bắt đầu bằng "Thay thế"; `bo_sung` sau `sua_doi` — "Sửa đổi, bổ sung" là một thao tác
ghi đè lời văn, chỉ khi đứng một mình "Bổ sung" mới là thêm mới.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.ingestion.vbpl_luoc_do import so_hieu_tu_tieu_de
from app.ontology.citation import parse_citations, to_node_ids
from app.ontology.parser import parse_dieu, trong_trich_dan

# Tiền tố đánh số một khoản-lệnh ("1. ", "2a. ") — chỉ để BÓC ra trước khi đọc động từ mở
# đầu / tìm viện dẫn, không dùng để định danh (đã có `KhoanNode.so_hien_thi` của parser.py
# cho việc đó). Không cần bảng 23 chữ đầy đủ ở đây: `\S` đủ rộng để nuốt hậu tố chữ bất kỳ
# mà không đổi kết quả — cái ta cần chỉ là bỏ được tiền tố, không phải xác thực nó.
_SO_KHOAN_DAU = re.compile(r"^\d{1,3}\S?\s*\.\s*")

_BANG_THAO_TAC: list[tuple[str, str]] = [
    (r"thay\s*thế\s+cụm\s+từ", "thay_cum_tu"),
    (r"thay\s*thế\s+(?:một\s+số\s+)?phụ\s+lục", "thay_phu_luc"),
    (r"bãi\s+bỏ", "bai_bo"),
    (r"sửa\s+đổi", "sua_doi"),
    (r"bổ\s+sung", "bo_sung"),
]


class CanhTacDong(BaseModel):
    """Một mệnh lệnh tác động: đơn vị NGUỒN (văn bản sửa) chạm đơn vị ĐÍCH (văn bản nền)."""

    nguon: str
    dich: str
    thao_tac: Literal["sua_doi", "bo_sung", "bai_bo", "thay_phu_luc", "thay_cum_tu"]
    #: span trong `noi_dung` của văn bản SỬA — xuất xứ lời văn mới; bãi bỏ thì None.
    loi_van_moi: tuple[int, int] | None = None
    valid_from: str | None = None
    menh_lenh: str
    canh_bao: list[str] = Field(default_factory=list)


def thao_tac_tu_cau(cau: str) -> str | None:
    dau = cau.strip()
    for mau, ma in _BANG_THAO_TAC:
        if re.match(mau, dau, re.IGNORECASE):
            return ma
    return None


def so_hieu_nen(tieu_de_dieu: str, mac_dinh: str) -> str:
    """Văn bản nền của MỘT điều lệnh. ND16 là lý do hàm này tồn tại: năm điều, năm nghị
    định nền khác nhau — lấy theo văn bản thì gán nhầm cả năm."""
    sh, _ = so_hieu_tu_tieu_de(tieu_de_dieu)
    return sh or mac_dinh


def dich_tu_menh_lenh(
    menh_lenh: str, so_hieu_nen: str, ctx_dieu: str | None
) -> tuple[list[str], list[str]]:
    """Câu lệnh → khoá node đích trong không gian văn bản NỀN.

    Dùng lại citation.py nguyên vẹn — nó đã thuộc 23 ca tiết của corpus. Không giải được
    thì BÁO chứ không đoán: một khoá sai trỏ vào node thật khác là kiểu hỏng im lặng nhất.
    """
    refs = parse_citations(menh_lenh)
    ra: list[str] = []
    for r in refs:
        for khoa in to_node_ids(r, ctx_so_hieu=so_hieu_nen, ctx_dieu=ctx_dieu):
            if khoa not in ra:
                ra.append(khoa)
    if ra:
        return ra, []
    return [], [f"không giải được đích từ mệnh lệnh: {menh_lenh[:80]!r}"]


def canh_tu_dieu(
    nhan_dieu: str,
    text_dieu: str,
    char_start: int,
    so_hieu_sua: str,
    mac_dinh_nen: str,
    khoi_trich: list[tuple[int, int]],
    valid_from: str | None,
) -> list[CanhTacDong]:
    """MỘT điều của văn bản sửa → danh sách cạnh tác động, gắn khối trích dẫn.

    `char_start` là vị trí của `text_dieu` trong `noi_dung` (văn bản sửa); `khoi_trich`
    là các span `trich_dan` cũng ở toạ độ `noi_dung`. Năm quy tắc thiết kế:

    1. **Điều không chẻ khoản** (TT41 Đ8 "Bãi bỏ khoản 4 Điều 24"): `parse_dieu` không tách
       được khoản nào (`dieu.khoan == []`) ⇒ cả thân điều là MỘT mệnh lệnh, `nguon` là khoá
       của chính Điều — không bịa một "khoản 1" không tồn tại.
    2. **Điều chẻ khoản**: mỗi khoản là một mệnh lệnh riêng; `ctx_dieu` cho `dich_tu_menh_lenh`
       lấy từ tiêu đề điều lệnh (`dieu.tieu_de`, qua `parse_citations` — ref nội bộ đầu tiên
       có `.dieu`), để mệnh lệnh như "Bãi bỏ điểm c khoản 7." (không tự nêu Điều) vẫn giải
       được đích đúng Điều mà tiêu đề đã nói.
    3. **Khối trích thuộc mệnh lệnh nào**: khối `[a,b)` gắn vào khoản-lệnh có khoảng
       `noi_dung` `[char_start + u.start - d, char_start + u.end - d)` CHỨA nó, với
       `d = len(nhan_dieu) + 2` bù cho tiền tố `f"{nhan_dieu}. "` đưa vào `parse_dieu` (để
       nó thấy dòng tiêu đề "Điều N. ..." hợp lệ). Nhiều khối trong cùng một mệnh lệnh ⇒
       gộp thành span `(min_start, max_end)`, kèm cảnh báo nếu chúng không liền kề (khe hở
       giữa hai khối nghĩa là gộp có thể vơ luôn phần không phải lời văn mới).
    4. Mệnh lệnh `sua_doi`/`bo_sung` mà KHÔNG có khối trích nào ⇒ cạnh vẫn tạo,
       `loi_van_moi=None` + cảnh báo — thiếu lời văn mới là khuyết tật đáng thấy ở tầng
       trên, không phải lý do vứt cạnh (một cạnh có cảnh báo còn dò được, một cạnh biến mất
       thì không).
    5. Text đưa vào `parse_citations` là phần NGOÀI khối trích của mệnh lệnh — che bằng
       `trong_trich_dan` của parser trên toàn bộ `full` rồi mới cắt theo khoản: viện dẫn BÊN
       TRONG lời văn mới nói về văn bản NỀN, không phải đích của lệnh đang xét.

    Mệnh lệnh không đọc được động từ mở đầu (`thao_tac_tu_cau` trả `None`) thì bị BỎ QUA,
    không tạo cạnh. Mệnh lệnh không giải được đích nào (`dich_tu_menh_lenh` trả rỗng) cũng
    bị bỏ qua — `CanhTacDong.dich` bắt buộc phải có giá trị, không có gì để gán thì không
    có cạnh để tạo; cảnh báo tương ứng vì vậy không có nơi neo và bị mất, đây là lựa chọn có
    ý thức trong phạm vi hàm này (tầng gọi hàm nếu cần đếm "mệnh lệnh chết" phải tự log riêng).
    """
    full = f"{nhan_dieu}. {text_dieu}"
    d = len(nhan_dieu) + 2
    dieu = parse_dieu(full, so_hieu_sua)
    sh_nen = so_hieu_nen(dieu.tieu_de, mac_dinh_nen)

    mat_na = trong_trich_dan(full)
    full_ngoai_trich = "".join(" " if mat_na[i] else c for i, c in enumerate(full))

    ctx_dieu: str | None = None
    for ref in parse_citations(dieu.tieu_de):
        if ref.noi_bo and ref.dieu:
            ctx_dieu = ref.dieu[0]
            break

    # (nguon, u_start, u_end trong `full`, có phải khoản thật hay thân điều nguyên khối)
    if dieu.khoan:
        don_vi = [
            (f"{dieu.id}#khoan_{k.so_hien_thi}", k.start, k.end, True) for k in dieu.khoan
        ]
    else:
        don_vi = [(dieu.id, d, len(full), False)]

    ra: list[CanhTacDong] = []
    for nguon, u_start, u_end, la_khoan in don_vi:
        than_menh_lenh = full_ngoai_trich[u_start:u_end]
        if la_khoan:
            than_menh_lenh = _SO_KHOAN_DAU.sub("", than_menh_lenh, count=1)

        thao_tac = thao_tac_tu_cau(than_menh_lenh)
        if thao_tac is None:
            continue

        span_start = char_start + u_start - d
        span_end = char_start + u_end - d
        khoi = sorted(
            (a, b) for a, b in khoi_trich if a >= span_start and b <= span_end
        )

        canh_bao: list[str] = []
        loi_van_moi: tuple[int, int] | None = None
        if khoi:
            loi_van_moi = (khoi[0][0], khoi[-1][1])
            for (_, truoc_end), (sau_start, _) in zip(khoi, khoi[1:]):
                if sau_start != truoc_end:
                    canh_bao.append(
                        f"nhiều khối trích không liền kề trong cùng mệnh lệnh {nguon!r} — "
                        f"gộp thành span {loi_van_moi}"
                    )
                    break
        elif thao_tac in ("sua_doi", "bo_sung"):
            canh_bao.append(
                f"mệnh lệnh {thao_tac!r} không có khối trích dẫn — thiếu lời văn mới"
            )

        menh_lenh_hien_thi = full[u_start:u_end]
        if la_khoan:
            menh_lenh_hien_thi = _SO_KHOAN_DAU.sub("", menh_lenh_hien_thi, count=1)
        menh_lenh_hien_thi = menh_lenh_hien_thi.strip()

        dich_list, canh_bao_dich = dich_tu_menh_lenh(than_menh_lenh, sh_nen, ctx_dieu)
        if not dich_list:
            continue

        for dich in dich_list:
            ra.append(
                CanhTacDong(
                    nguon=nguon,
                    dich=dich,
                    thao_tac=thao_tac,  # type: ignore[arg-type]
                    loi_van_moi=loi_van_moi,
                    valid_from=valid_from,
                    menh_lenh=menh_lenh_hien_thi,
                    canh_bao=canh_bao + canh_bao_dich,
                )
            )
    return ra
