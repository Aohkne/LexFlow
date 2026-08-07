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

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.ingestion.vbpl_corpus import duong_dan_toan_van, file_da_chuyen_khuon
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
) -> tuple[list[CanhTacDong], list[str]]:
    """MỘT điều của văn bản sửa → (danh sách cạnh tác động, cảnh báo cấp điều).

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
       giữa hai khối nghĩa là gộp có thể vơ luôn phần không phải lời văn mới). Một khối
       CHỒNG LẤN ranh của mệnh lệnh mà không nằm trọn trong đó (cắt ngang biên khoản) bị
       loại khỏi gộp và cũng phát cảnh báo riêng — im lặng bỏ qua nó cũng là một kiểu đoán.
    4. Mệnh lệnh `sua_doi`/`bo_sung` mà KHÔNG có khối trích nào ⇒ cạnh vẫn tạo,
       `loi_van_moi=None` + cảnh báo trên CHÍNH cạnh đó (`CanhTacDong.canh_bao`) — thiếu
       lời văn mới là khuyết tật đáng thấy ở tầng trên, không phải lý do vứt cạnh (một cạnh
       có cảnh báo còn dò được, một cạnh biến mất thì không).
    5. Text đưa vào `parse_citations` là phần NGOÀI khối trích của mệnh lệnh — che bằng
       `trong_trich_dan` của parser trên toàn bộ `full` rồi mới cắt theo khoản: viện dẫn BÊN
       TRONG lời văn mới nói về văn bản NỀN, không phải đích của lệnh đang xét.

    Mệnh lệnh không đọc được động từ mở đầu (`thao_tac_tu_cau` trả `None`) thì bị BỎ QUA,
    không tạo cạnh, không cảnh báo — không phải mọi câu trong thân điều là một mệnh lệnh
    (chapeau, câu mô tả...), nên im lặng ở bước này là đúng, không phải mất tích.

    Mệnh lệnh CÓ đọc được động từ nhưng KHÔNG giải được đích nào (`dich_tu_menh_lenh` trả
    rỗng) thì KHÔNG bị bỏ qua trong im lặng: không có cạnh nào được tạo (không có gì hợp lệ
    để gán vào `CanhTacDong.dich`), nhưng mọi cảnh báo đã tính cho mệnh lệnh đó — cả cảnh
    báo Quy tắc 3/4 lẫn cảnh báo "không giải được đích" của `dich_tu_menh_lenh` — đều được
    gộp vào danh sách cảnh báo TRẢ VỀ Ở CẤP ĐIỀU (phần tử thứ hai của tuple), mỗi cảnh báo
    có tiền tố `nguon` + đoạn mệnh lệnh rút gọn để người đọc biết cảnh báo này thuộc về đâu
    mà tra. "Giải không được thì BÁO chứ không đoán" (bất biến của dự án) áp dụng ở đây
    đúng nghĩa: một mệnh lệnh chết không được phép biến mất không dấu vết.
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
    canh_bao_dieu: list[str] = []
    for nguon, u_start, u_end, la_khoan in don_vi:
        than_menh_lenh = full_ngoai_trich[u_start:u_end]
        if la_khoan:
            than_menh_lenh = _SO_KHOAN_DAU.sub("", than_menh_lenh, count=1)

        thao_tac = thao_tac_tu_cau(than_menh_lenh)
        if thao_tac is None:
            continue

        span_start = char_start + u_start - d
        span_end = char_start + u_end - d
        khoi: list[tuple[int, int]] = []
        for a, b in khoi_trich:
            if a >= span_start and b <= span_end:
                khoi.append((a, b))
            elif a < span_end and b > span_start:
                # Chồng lấn nhưng không nằm trọn — cắt ngang ranh mệnh lệnh. Loại khỏi
                # gộp (Quy tắc 3 chỉ gộp khối NẰM TRỌN) và nói ra, không âm thầm bỏ.
                canh_bao_dieu.append(
                    f"{nguon}: khối trích cắt ngang ranh mệnh lệnh — trích [{a},{b}) "
                    f"chồng lấn nhưng không nằm trọn trong span [{span_start},{span_end})"
                )
        khoi.sort()

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
            # Đọc được động từ nhưng không giải được đích: KHÔNG có cạnh để neo cảnh báo
            # (CanhTacDong.dich bắt buộc có giá trị) — đẩy lên cảnh báo cấp điều thay vì
            # để chúng biến mất cùng với mệnh lệnh bị bỏ qua.
            dia_chi = f"{nguon} ({menh_lenh_hien_thi[:80]!r})"
            canh_bao_dieu.extend(f"{dia_chi}: {msg}" for msg in canh_bao + canh_bao_dich)
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
    return ra, canh_bao_dieu


# --- Đối chứng hai chiều với `dieu_khoan_bi_tac_dong` --------------------------

#: Bóc (số hiệu, điều, cấp, số) từ một khoá đích do `to_node_ids` sinh: luôn
#: `{so_hieu}#than/dieu_{n}` rồi có thể thêm `#khoan_{n}` rồi `#diem_{n}` — không bao giờ có
#: `diem` mà thiếu `khoan` phía trước trong CHUỖI, nhưng cấp so khớp lấy theo mức SÂU NHẤT có
#: mặt (diem > khoan > điều), vì đó là đơn vị đích thật của cạnh.
_DICH_RE = re.compile(
    r"^(?P<sh>.+?)#than/dieu_(?P<dieu>[^#]+)(?:#khoan_(?P<khoan>[^#]+))?(?:#diem_(?P<diem>[^#]+))?$"
)

#: Bóc số điều từ `dieu_khoan_bi_tac_dong[].dieu` — mục cấp điều viết "Điều 8. <tiêu đề>",
#: mục cấp dưới viết bare "Điều 8". `[^\s.]+` dừng ở dấu chấm hoặc khoảng trắng đầu tiên nên
#: ăn được cả hai dạng mà không cần biết trước đang đọc dạng nào.
_MUC_DIEU_RE = re.compile(r"^Điều\s+([^\s.]+)")

#: Một khoá node `...#than/dieu_N[#khoan_..][#diem_..]` bên trong một chuỗi tự do (cảnh báo cấp
#: điều cũng nhúng `nguon` theo đúng khuôn này) — dùng để đếm "điều lệnh" ở `main` mà không phải
#: chạy lại `canh_tu_dieu`. Chỉ lấy tới hết số điều: `[^#\s"'()]+` sau `dieu_` chặn ở dấu `#`
#: kế tiếp (nếu có `#khoan_`/`#diem_`) nên luôn quy về đúng cấp ĐIỀU.
_DIEU_ID_RE = re.compile(r"[^\s\"'()]+#than/dieu_[^#\s\"'()]+")


def _dich_thanh_bo_ba(dich: str) -> tuple[str, str, str | None, str | None] | None:
    m = _DICH_RE.match(dich)
    if not m:
        return None
    if m.group("diem") is not None:
        return m.group("sh"), m.group("dieu"), "diem", m.group("diem")
    if m.group("khoan") is not None:
        return m.group("sh"), m.group("dieu"), "khoan", m.group("khoan")
    return m.group("sh"), m.group("dieu"), None, None


def _muc_thanh_bo_ba(muc: dict) -> tuple[str, str | None, str | None] | None:
    m = _MUC_DIEU_RE.match((muc.get("dieu") or "").strip())
    if not m:
        return None
    cap = muc.get("cap")
    if cap not in ("khoan", "diem"):
        cap = None  # cấp "dieu"/"khac"/vắng mặt đều coi là mục Ở CẤP ĐIỀU (so bằng số điều)
    so = muc.get("so") if cap else None
    return m.group(1), cap, so


def _khop(dieu_c: str, cap_c: str | None, so_c: str | None,
          dieu_m: str, cap_m: str | None, so_m: str | None) -> bool:
    """Một cạnh và một mục nguồn có nói về CÙNG một chỗ trong văn bản nền không.

    Mục cấp điều (`cap_m is None`) chỉ đòi khớp số điều — không quan tâm cạnh trỏ vào khoản
    nào bên trong. Mục cấp dưới điều đòi khớp đúng (điều, cấp, số); một cạnh trỏ NGUYÊN điều
    (`cap_c is None`, ví dụ bãi bỏ cả điều) vẫn được coi là khớp mọi mục cấp dưới của điều đó
    — bãi bỏ cả điều kéo theo mọi khoản/điểm bên trong, nên không thể coi là lệch.
    """
    if dieu_c != dieu_m:
        return False
    if cap_m is None:
        return True
    return cap_c is None or (cap_c == cap_m and so_c == so_m)


def doi_chung(canh: list[CanhTacDong], muc: list[dict], so_hieu_nen: str) -> list[str]:
    """Cạnh tác động mình sinh ra so HAI CHIỀU với `dieu_khoan_bi_tac_dong` của văn bản nền.

    Lệch KHÔNG phải lỗi dừng: đây là công cụ soi, không phải bộ kiểm hợp lệ. Cả hai chiều đều
    in kèm địa chỉ (khoá node đầy đủ / chuỗi "Điều N" nguyên văn) để người đọc tra thẳng vào
    nguồn mà không cần lần lại qua code.
    """
    canh_dich = [
        (c, *bo_ba)
        for c in canh
        if (bo_ba := _dich_thanh_bo_ba(c.dich)) is not None and bo_ba[0] == so_hieu_nen
    ]
    canh_dich = [(c, dieu, cap, so) for c, _sh, dieu, cap, so in canh_dich]

    muc_dich = [
        (m, *bo_ba) for m in muc if (bo_ba := _muc_thanh_bo_ba(m)) is not None
    ]

    lech: list[str] = []
    for c, dieu_c, cap_c, so_c in canh_dich:
        if not any(
            _khop(dieu_c, cap_c, so_c, dieu_m, cap_m, so_m)
            for _, dieu_m, cap_m, so_m in muc_dich
        ):
            lech.append(f"[+] {c.dich} không có trong dieu_khoan_bi_tac_dong")
    for m, dieu_m, cap_m, so_m in muc_dich:
        if not any(
            _khop(dieu_c, cap_c, so_c, dieu_m, cap_m, so_m)
            for _, dieu_c, cap_c, so_c in canh_dich
        ):
            lech.append(f"[-] {m['dieu']} nguồn ghi {m['phan_loai']} mà không có cạnh")
    return lech


# --- Quét cả thư mục ------------------------------------------------------------


def _dau_tien(text: str) -> str:
    return (text or "").split("\n", 1)[0].strip()


def doc_tac_dong(thu_muc: Path) -> tuple[list[CanhTacDong], list[str]]:
    """Mọi văn bản CÓ TOÀN VĂN trong `thu_muc` → cạnh tác động + cảnh báo gộp.

    **`char_start` không cần bù trừ gì thêm ở tầng gọi** — đây là phát hiện phải xác nhận
    bằng thăm dò trước khi viết hàm này (chữ ký `canh_tu_dieu` nhìn thoáng qua như đòi trừ
    `len(nhan_dieu) + 2`, nhưng đó là phép bù NỘI BỘ của nó cho tiền tố nó tự thêm). `articles[]`
    của corpus lưu `char_start` là vị trí của CHÍNH `text` (không kèm "Điều N. ") trong
    `noi_dung` của bản ghi thô — đúng quy ước `canh_tu_dieu` đợi nhận. Đo trên TT41/2025 Điều 1:
    `loi_van_moi=(1087,1309)` và `noi_dung[1087] == '"'` — đúng ký tự mở ngoặc kép của khối
    trích đầu tiên, không lệch một ký tự nào.

    Văn bản sửa = có ≥1 điều mà `thao_tac_tu_cau` đọc được động từ mệnh lệnh ở DÒNG ĐẦU thân
    điều (đa số điều lệnh không chẻ khoản viết ngay động từ ở dòng đầu). Đây chỉ là bộ lọc
    Ở CẤP VĂN BẢN — một khi văn bản đã vào diện "sửa", MỌI điều của nó đều được đưa qua
    `canh_tu_dieu`, kể cả điều có tiêu đề không phải mệnh lệnh (ca TT22 Điều 6 "Điều khoản thi
    hành": khoản 1 là hiệu lực thi hành, khoản 2 mới là "Bãi bỏ Điều 16, 17, 18..." — lọc ở
    mức điều sẽ làm rớt đúng cạnh khoá cứng của nghiệm thu này).

    `mac_dinh_nen` (số hiệu nền khi tiêu đề MỘT điều không tự nêu, ca TT41 Đ8 "Bãi bỏ khoản 4
    Điều 24" không nói khoản 4 Điều 24 của văn bản nào) lấy từ bản ghi thô, quan hệ lược đồ
    `luoc_do.outgoing["Văn bản được sửa đổi bổ sung"]`, mục ĐẦU TIÊN. Văn bản sửa nhiều nền
    cùng lúc (TT30/2016 → TT19/2016 + TT22/2015 + TT39/2014) luôn tự nêu số hiệu nền trong
    CHÍNH tiêu đề từng điều, nên fallback này chỉ thật sự được dùng ở các văn bản một-nền —
    đúng lúc nó cần đúng.
    """
    ra: list[CanhTacDong] = []
    canh_bao: list[str] = []
    for p in file_da_chuyen_khuon(thu_muc):
        try:
            corpus = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            canh_bao.append(f"{p.name}: không đọc được JSON corpus")
            continue

        dieu_list = corpus.get("articles") or []
        if not dieu_list:
            continue  # văn bản 0 điều (VBHN không có toàn văn) — bỏ sạch, không phải lỗi

        so_hieu_sua = corpus.get("so_hieu")
        if not so_hieu_sua:
            canh_bao.append(f"{p.name}: thiếu so_hieu — bỏ qua cả văn bản")
            continue

        la_van_ban_sua = any(
            thao_tac_tu_cau(_dau_tien(a.get("text") or "")) is not None for a in dieu_list
        )
        if not la_van_ban_sua:
            continue

        p_tho = duong_dan_toan_van(p)
        if not p_tho.exists():
            canh_bao.append(f"{so_hieu_sua}: thiếu bản ghi thô {p_tho.name!r} — bỏ qua")
            continue
        try:
            tho = json.loads(p_tho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            canh_bao.append(f"{so_hieu_sua}: bản ghi thô {p_tho.name!r} không đọc được JSON")
            continue

        mac_dinh_nen = so_hieu_sua
        muc_tieu = (
            (tho.get("luoc_do") or {}).get("outgoing") or {}
        ).get("Văn bản được sửa đổi bổ sung") or []
        if muc_tieu:
            sh, _cb = so_hieu_tu_tieu_de(muc_tieu[0].get("title") or "")
            if sh:
                mac_dinh_nen = sh

        valid_from = corpus.get("valid_from")
        khoi_toan_bo = [
            (t["char_start"], t["char_end"])
            for t in corpus.get("trich_dan") or []
            if isinstance(t.get("char_start"), int) and isinstance(t.get("char_end"), int)
        ]

        for a in dieu_list:
            nhan = a.get("article")
            cs, ce = a.get("char_start"), a.get("char_end")
            if not nhan or not isinstance(cs, int) or not isinstance(ce, int):
                canh_bao.append(
                    f"{so_hieu_sua}: điều {nhan!r} thiếu char_start/char_end — bỏ qua"
                )
                continue
            khoi = [(a0, b0) for a0, b0 in khoi_toan_bo if a0 >= cs and b0 <= ce]
            canh, canh_bao_dieu = canh_tu_dieu(
                nhan, a.get("text") or "", cs, so_hieu_sua, mac_dinh_nen, khoi, valid_from
            )
            ra.extend(canh)
            canh_bao.extend(f"{so_hieu_sua}: {w}" for w in canh_bao_dieu)
    return ra, canh_bao


def main() -> None:
    thu_muc = Path("data/raw/vbpl")
    canh, canh_bao = doc_tac_dong(thu_muc)

    theo_nguon: dict[str, list[CanhTacDong]] = {}
    for c in canh:
        theo_nguon.setdefault(c.nguon.split("#", 1)[0], []).append(c)

    cb_theo_nguon: dict[str, int] = {}
    dieu_lenh: dict[str, set[str]] = {}
    for c in canh:
        for did in _DIEU_ID_RE.findall(c.nguon):
            dieu_lenh.setdefault(did.split("#", 1)[0], set()).add(did)
    for w in canh_bao:
        sh_prefix, _, phan_con_lai = w.partition(": ")
        cb_theo_nguon[sh_prefix] = cb_theo_nguon.get(sh_prefix, 0) + 1
        for did in _DIEU_ID_RE.findall(phan_con_lai):
            dieu_lenh.setdefault(sh_prefix, set()).add(did)

    tat_ca_nguon = sorted(set(theo_nguon) | set(cb_theo_nguon))
    print(f"{'văn bản sửa':<22} {'điều lệnh':>9} {'cạnh':>6} {'cảnh báo':>8}")
    for sh in tat_ca_nguon:
        print(
            f"{sh:<22} {len(dieu_lenh.get(sh, ())):>9} "
            f"{len(theo_nguon.get(sh, [])):>6} {cb_theo_nguon.get(sh, 0):>8}"
        )

    dong_doi_chung: list[str] = []
    for p in file_da_chuyen_khuon(thu_muc):
        corpus = json.loads(p.read_text(encoding="utf-8"))
        so_hieu = corpus.get("so_hieu")
        if not so_hieu:
            continue
        p_tho = duong_dan_toan_van(p)
        if not p_tho.exists():
            continue
        tho = json.loads(p_tho.read_text(encoding="utf-8"))
        muc = tho.get("dieu_khoan_bi_tac_dong") or []
        if not muc:
            continue
        lech = doi_chung(canh, muc, so_hieu)
        dong_doi_chung.append(f"=== {so_hieu} ({len(muc)} mục nguồn, {len(lech)} lệch) ===")
        dong_doi_chung.extend(lech)

    # Cảnh báo cấp điều (`canh_bao_dieu` gộp lên từ `canh_tu_dieu` — mệnh lệnh đọc được động
    # từ nhưng không giải được đích, khối trích cắt ngang ranh...) trước đây chỉ ĐẾM ra console
    # (`cb_theo_nguon`) — chữ thật của từng cảnh báo biến mất, không ai tra lại được (review
    # round 2, F4). Ghi nguyên văn vào cuối `doi_chung.txt` thay vì một file riêng: cùng là sản
    # phẩm "soi" của `main()`, không phải bộ kiểm hợp lệ.
    if canh_bao:
        dong_doi_chung.append("")
        dong_doi_chung.append("--- cảnh báo cấp điều ---")
        dong_doi_chung.extend(canh_bao)

    out_dir = Path("eval/overlay")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "canh_tac_dong.jsonl").write_text(
        "".join(c.model_dump_json() + "\n" for c in canh), encoding="utf-8"
    )
    (out_dir / "doi_chung.txt").write_text(
        "".join(line + "\n" for line in dong_doi_chung), encoding="utf-8"
    )
    print(f"\nghi {len(canh)} cạnh -> {out_dir / 'canh_tac_dong.jsonl'}")
    print(f"ghi đối chứng -> {out_dir / 'doi_chung.txt'}")


if __name__ == "__main__":
    main()
