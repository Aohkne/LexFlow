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
from app.ontology.tac_dong import _DICH_RE as _KHOA_RE

#: Nhãn chunk `"Điều 8"` hoặc `"Điều 8 Khoản 7"` — đúng dạng `_khoan_label` của
#: `app/ingestion/pipeline.py` sinh ra cho chunk KHÔNG gộp nhiều khoản. Khoản phải là MỘT
#: khoản thật (`\d+[a-zđ]?`) — không `\S+` (review round 2, F1): `\S+` khớp cả "1-6" của một
#: nhãn GỘP nhiều khoản và mint một khoá `#khoan_1-3` KHÔNG TỒN TẠI, khiến chunk (21.8% số
#: chunk thật) rớt khỏi mọi cạnh tác động và bị đọc nhầm là nguyên vẹn. Cắt cửa sổ ký tự
#: "(phần 2)" (điều không chẻ khoản được) vẫn không giải được thành MỘT khoá — nằm ngoài
#: regex này lẫn regex gộp bên dưới, `khoa_tu_chunk_id` trả `None` cho dạng đó.
_NHAN_RE = re.compile(r"^Điều\s+(\d+[a-zđ]?)(?:\s+Khoản\s+(\d+[a-zđ]?))?$")

#: Nhãn GỘP nhiều khoản liền kề — `_khoan_label` chỉ sinh dạng `"{đầu}-{cuối}"` với hai số
#: khoản thuần chữ số (`_KHOAN_RE` của pipeline.py chỉ bắt `^\d+\.`, không có hậu tố chữ).
#: Khớp dạng này thì KHÔNG mint khoá khoản (không biết chính xác khoản nào trong dải bị
#: tác động) — chỉ lấy phần điều, để `dinh_tuyen` dò tiếp bằng `_canh_deeper_ap_duoc` (khoá
#: điều là khoá THẬT, chunk chắc chắn là một phần của điều đó — review round 2, F1).
_NHAN_GOP_KHOAN_RE = re.compile(r"^Điều\s+(\d+[a-zđ]?)\s+Khoản\s+\d+-\d+$")

# `_KHOA_RE` = `app.ontology.tac_dong._DICH_RE` — cùng bóc một khoá overlay
# `{so_hieu}#than/dieu_N[#khoan_M[#diem_x]]` thành các phần, tái dùng thay vì khai lại
# byte-for-byte (review round 1, minor 1).


def khoa_tu_chunk_id(chunk_id: str, so_hieu_theo_doc: dict[str, str]) -> str | None:
    """Chunk-id `"{doc_id}::{label}"` → khoá overlay `"{so_hieu}#than/dieu_N[#khoan_M]"`.

    Trả `None` khi `doc_id` không có trong bảng (văn bản lạ) hoặc `label` không khớp dạng
    "Điều N" / "Điều N Khoản M" / "Điều N Khoản M-K" (gộp) — KHÔNG bịa khoá cho những trường
    hợp không chắc.

    Nhãn GỘP nhiều khoản (`_NHAN_GOP_KHOAN_RE`, vd `"Điều 8 Khoản 1-6"`) không cho ra một khoá
    khoản — không khoản nào trong dải "1-6" là MỘT khoản thật để mint `#khoan_1-6` (khoá đó
    không tồn tại trong overlay, không cạnh nào trỏ tới). Rơi về khoá CẤP ĐIỀU thay: khoá đó
    thật (chunk chắc chắn nằm trong điều này) và đủ để `dinh_tuyen` dò tiếp cạnh sâu hơn bên
    trong điều qua `_canh_deeper_ap_duoc` (review round 2, F1).
    """
    doc_id, sep, nhan = chunk_id.partition("::")
    if not sep:
        return None
    so_hieu = so_hieu_theo_doc.get(doc_id)
    if so_hieu is None:
        return None
    m = _NHAN_RE.match(nhan)
    if m:
        dieu, khoan = m.group(1), m.group(2)
    else:
        m_gop = _NHAN_GOP_KHOAN_RE.match(nhan)
        if not m_gop:
            return None
        dieu, khoan = m_gop.group(1), None
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
    #: Cạnh đã QUYẾT ĐỊNH nhánh này (None ở nhánh nguyên vẹn). Người gọi cần biết chính xác
    #: cạnh nào để tra lời văn mới mà không phải mô phỏng lại luật chọn cạnh ở đây.
    canh: CanhTacDong | None = None


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


#: Số đơn vị đích tối đa liệt kê trong MỘT câu trích dẫn. Một khối lời văn mới có thể là lời
#: văn của rất nhiều đơn vị cùng lúc (đo trên `data/overlay/lop_phu.json`: tối đa 6); ngưỡng 8
#: để câu trích còn đọc được. Vượt ngưỡng thì cắt **kèm lời báo** — cắt trong im lặng là đúng
#: cái khuyết tật hàm này sinh ra để chặn.
_TOI_DA_KE_DICH = 8

_SO_RE = re.compile(r"^(\d*)(.*)$")


def _tach_khoa(khoa: str) -> tuple[str, str, str | None, str | None] | None:
    """Khoá overlay → (`doc_id` hiển thị, số điều, khoản, điểm). Không giải được ⇒ None."""
    m = _KHOA_RE.match(khoa)
    if not m:
        return None
    return (
        doc_id_theo_corpus(m.group("sh")) or m.group("sh"),
        m.group("dieu"),
        m.group("khoan"),
        m.group("diem"),
    )


def _tu_nhien(v: str | None) -> tuple:
    """Khoá sắp TỰ NHIÊN cho số điều/khoản: `"10"` sau `"9"`, `"5a"` sau `"5"`."""
    if not v:
        return (0, 0, "")
    so, hau = _SO_RE.match(v).groups()
    return (1, int(so) if so else 0, hau)


def _sap(khoa: str) -> tuple:
    """Thứ tự TẤT ĐỊNH giữa các khoá overlay — dùng cả để chọn cạnh chủ lẫn để in danh sách."""
    p = _tach_khoa(khoa)
    if p is None:
        return (1, khoa, (0, 0, ""), (0, 0, ""), "")
    doc_id, dieu, khoan, diem = p
    return (0, doc_id, _tu_nhien(dieu), _tu_nhien(khoan), diem or "")


def _cite_nhieu(khoas: list[str]) -> str:
    """Nhiều khoá overlay → MỘT trích dẫn kể ĐỦ, gom theo (văn bản, điều).

    Nhánh 3 khớp theo span, mà một span thường là lời văn mới của NHIỀU đơn vị: đo trên
    artefact thật có 46 cặp cạnh cùng văn bản sửa giao span và 17 nhóm (văn bản, lời văn) trùng
    khít — `80/2016/NĐ-CP` (1071, 2386) là lời văn của khoản 4, 5, 6, 7 **và** 8 Điều 4
    `101/2012/NĐ-CP`; `16/2019/NĐ-CP` (7121, 7445) chạm cả `10/2010/NĐ-CP` lẫn `57/2016/NĐ-CP`.
    Nói tên MỘT đích rồi im về phần còn lại là trích dẫn tự tin mà thiếu — với sản phẩm pháp lý
    đó tệ hơn không trích.
    """
    rieng = sorted(dict.fromkeys(khoas), key=_sap)
    du = len(rieng) - _TOI_DA_KE_DICH
    if du > 0:
        rieng = rieng[:_TOI_DA_KE_DICH]

    nhom: dict[tuple[str, str], list[str]] = {}
    for k in rieng:
        p = _tach_khoa(k)
        if p is None:
            nhom.setdefault((k, ""), [])  # khoá lạ: giữ nguyên chữ thô, không bịa
            continue
        doc_id, dieu, khoan, diem = p
        phan = ""
        if khoan:
            phan = f"Khoản {khoan}" + (f" Điểm {diem}" if diem else "")
        nhom.setdefault((doc_id, dieu), []).append(phan)

    manh: list[str] = []
    for (doc_id, dieu), phan in nhom.items():
        if not dieu:
            manh.append(doc_id)
            continue
        dau = f"{doc_id} Điều {dieu}"
        con = [p for p in phan if p]
        if not con or len(con) < len(phan):
            # Có cạnh trỏ TRỌN điều ⇒ nói cấp điều là đã bao trùm các khoản còn lại, không giấu.
            manh.append(dau)
        elif all(" Điểm " not in p for p in con):
            manh.append(f"{dau} Khoản " + ", ".join(p[len("Khoản "):] for p in con))
        else:
            manh.append(f"{dau} " + ", ".join(con))

    ra = " và ".join(manh)
    if du > 0:
        ra += f" và {du} đơn vị khác (đã rút gọn)"
    return ra


def _giao_nhau(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _canh_deeper_ap_duoc(
    khoa: str, canh: list[CanhTacDong], hom_nay: str
) -> CanhTacDong | None:
    """Cạnh có `dich` SÂU HƠN `khoa` (một điểm bên trong khoản `khoa`) đang áp được.

    `phien_ban_hien_hanh(khoa, ...)` chỉ xét cạnh mà `dich` là chính `khoa` hoặc TIỀN TỐ của
    nó (điều bị bãi kéo khoản con). Chiều ngược lại — chunk là khoản, cạnh sửa một điểm BÊN
    TRONG khoản đó — không thuộc phạm vi hàm đó, nên lọc ứng cử riêng ở đây; nhưng luật
    cạnh-chết (một cạnh chết nếu chính điều/khoản đã PHÁT ra nó bị bãi bỏ) vẫn phải là luật
    THẬT của `phien_ban_hien_hanh`, không viết lại: gọi `phien_ban_hien_hanh(c.nguon, canh,
    hom_nay)` cho từng ứng cử — nếu trạng thái của NGUỒN cạnh đó là `bi_bai_bo` tại `hom_nay`
    thì cạnh không còn áp được, dù `valid_from` riêng của nó vẫn `<= hom_nay` (review round 1,
    important fix — route công khai thay vì mô phỏng lại luật cạnh-chết).

    Nhiều cạnh sâu-hơn cùng còn sống (hiếm nhưng có thể) → lấy cạnh có `valid_from` MỚI NHẤT,
    nhất quán với cách `phien_ban_hien_hanh` sắp `cac_lan` và lấy `[-1]`.
    """
    ung_cu = [
        c for c in canh
        if c.dich.startswith(khoa + "#")
        and c.valid_from is not None
        and c.valid_from <= hom_nay
        and phien_ban_hien_hanh(c.nguon, canh, hom_nay).trang_thai != "bi_bai_bo"
    ]
    if not ung_cu:
        return None
    ung_cu.sort(key=lambda c: c.valid_from)
    return ung_cu[-1]


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
    #
    # Khớp span KHÔNG đủ để nói "sửa bởi" ở thì hiện tại (review round 2, F2): cạnh có thể đã
    # CHẾT (luật cạnh-chết của `phien_ban_hien_hanh` — chính nguồn phát ra nó đã bị bãi bỏ) dù
    # đoạn văn bản vẫn nằm đó và span vẫn khớp. Cổng qua `phien_ban_hien_hanh(c.dich, ...)`:
    # cạnh còn ÁP ĐƯỢC hôm nay khi và chỉ khi nó có mặt trong `cac_lan` (route công khai, không
    # tự chấm valid_from/cạnh-chết ở đây). Chunk vẫn LÀ một trích dẫn (span vẫn khớp lời văn nó
    # mang) nên vẫn về nhánh `trich_trong_van_ban_sua` — chỉ câu trích dẫn phải nói thật là sửa
    # đổi đó không còn hiệu lực, kèm ai đã bãi bỏ nó (suy từ `phien_ban_hien_hanh(c.nguon, ...)`,
    # cùng cách `_canh_deeper_ap_duoc` đã làm cho nhánh 2).
    # Gom TẤT CẢ cạnh khớp span, không lấy cạnh đầu tiên (fix wave 06/08, CRITICAL 1): một khối
    # lời văn mới thường là lời văn của nhiều đơn vị, đôi khi ở nhiều VĂN BẢN NỀN khác nhau —
    # xem `_cite_nhieu`. Lấy cạnh đầu rồi phát biểu như sự thật là giấu phần còn lại.
    if span_chunk is not None and so_hieu_doc is not None:
        khop = [
            c for c in canh
            if c.nguon.split("#", 1)[0] == so_hieu_doc
            and c.loi_van_moi is not None
            and _giao_nhau(span_chunk, c.loi_van_moi)
        ]
        if khop:
            khop.sort(key=lambda c: (_sap(c.dich), _sap(c.nguon), c.thao_tac, c.valid_from or ""))
            # Cổng cạnh-chết giữ nguyên, chỉ áp cho TỪNG cạnh khớp: chỉ kể những cạnh còn áp
            # được hôm nay. Không cạnh nào còn áp ⇒ vẫn phải nói về chúng, nhưng ở thì quá khứ.
            con_ap = [c for c in khop if c in phien_ban_hien_hanh(c.dich, canh, hom_nay).cac_lan]
            ke = con_ap or khop
            chu = ke[0]  # cạnh CHỦ: nhỏ nhất theo `_sap` ⇒ tất định giữa các lần chạy
            if con_ap:
                trich = (
                    f"{_cite_nhieu([c.dich for c in ke])} "
                    f"(sửa bởi {_cite_nhieu([c.nguon for c in ke])})"
                )
            else:
                # Các cạnh chết có thể chết vì những lý do KHÁC nhau (nguồn bị bãi bỏ bởi văn
                # bản khác nhau, hoặc chưa tới ngày áp) — gom theo lý do rồi mới gộp câu chữ,
                # không quy hết về lý do của một cạnh.
                theo_ly_do: dict[str, list[CanhTacDong]] = {}
                for c in ke:
                    pb_nguon = phien_ban_hien_hanh(c.nguon, canh, hom_nay)
                    boi = (
                        _cite(pb_nguon.cac_lan[-1].nguon)
                        if pb_nguon.trang_thai == "bi_bai_bo" and pb_nguon.cac_lan
                        else ""
                    )
                    theo_ly_do.setdefault(boi, []).append(c)
                manh = []
                for boi, cs in theo_ly_do.items():
                    dich_s = _cite_nhieu([c.dich for c in cs])
                    nguon_s = _cite_nhieu([c.nguon for c in cs])
                    if boi:
                        manh.append(
                            f"{dich_s} (từng được sửa bởi {nguon_s} — đã bị bãi bỏ bởi "
                            f"{boi}, không còn áp dụng)"
                        )
                    else:
                        # Chưa gặp trong dữ liệu thật (vd valid_from còn ở tương lai) — vẫn
                        # nói thẳng "không áp dụng" thay vì im lặng giữ nguyên "sửa bởi".
                        manh.append(f"{dich_s} (từng được sửa bởi {nguon_s}, hiện không áp dụng)")
                trich = "; ".join(manh)
            return KetQuaTuyen(
                nhanh="trich_trong_van_ban_sua",
                khoa_goc=khoa_goc,
                khoa_dich=chu.dich,
                trich_dan_dung_chu=trich,
                canh=chu,
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
            trich_dan_dung_chu=trich, canh=c,
        )

    sau_hon = _canh_deeper_ap_duoc(khoa_goc, canh, hom_nay)
    if sau_hon is not None:
        # Cùng chữ với nhánh rộng-hơn-hoặc-bằng ở trên (review round 2, F3): `sau_hon` có thể
        # là `bai_bo` (vd bãi điểm c bên trong một khoản) — "sửa bởi" cho một lệnh XOÁ là nói
        # sai thao tác, dù "route" (nen_da_sua) vẫn đúng.
        if sau_hon.thao_tac == "bai_bo":
            trich = f"{_cite(sau_hon.dich)} (đã bị bãi bỏ bởi {_cite(sau_hon.nguon)})"
        else:
            trich = f"{_cite(sau_hon.dich)} (sửa bởi {_cite(sau_hon.nguon)})"
        return KetQuaTuyen(
            nhanh="nen_da_sua", khoa_goc=khoa_goc, khoa_dich=sau_hon.dich,
            trich_dan_dung_chu=trich, canh=sau_hon,
        )

    # --- Nhánh 1: không cạnh nào chạm — nguyên vẹn.
    return KetQuaTuyen(
        nhanh="nguyen_ven", khoa_goc=khoa_goc, khoa_dich=None,
        trich_dan_dung_chu=_cite(khoa_goc),
    )
