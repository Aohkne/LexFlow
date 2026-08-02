"""Parser Điều → Khoản → Điểm GIỮ NGUYÊN offset ký tự.

Khác `app/ingestion/extract.py` (chỉ tách tới mức Điều, không giữ vị trí): ở
đây mỗi nút ghi `[start, end)` vào chuỗi đã làm sạch, để bước sau neo được
bằng chứng của LLM về đúng ký tự gốc (ý tưởng `char_span` của GraphCompliance).

Ba cái bẫy đã kiểm chứng trên ND52-2024 (xem docs/ONTOLOGY-POC.md):

1. Điểm của Điều 22 khoản 2 là ``a) b) c) d) đ) e) g) h)``. Trong Python
   ``[a-z]\\)`` KHÔNG khớp ``đ)`` → điểm đ bị nuốt im lặng thành dòng nối của
   điểm d. Mọi regex marker ở đây dựng từ bảng 23 chữ tường minh (KG v0.5 §5),
   không bao giờ tính bằng ``ord()``.
2. Câu bao trùm (chapeau) không nằm trên dòng đánh số: dòng "2. Điều kiện
   cung ứng..." chỉ là tiêu đề, Subject + Action ở dòng kế tiếp. Nên một Khoản
   = dòng đánh số + mọi dòng không-marker theo sau.
3. Text nguồn (snapshot luatvietnam) lẫn rác biên tập: dòng "Phân tích" và
   khối bình luận chèn giữa chapeau và điểm a).
"""
from __future__ import annotations

import re

from app.ingestion.extract import _NOISE_LINES
from app.ontology.schema import DiemNode, DieuNode, KhoanNode, TietSpan

# Bảng chữ cái dùng đánh số trong văn bản QPPL Việt Nam — 23 chữ (KG v0.5 §5).
# `đ` là chữ duy nhất thêm vào so với ASCII; không có f j w z; sau `e` là `g`.
VI_LETTERS = "a b c d đ e g h i k l m n o p q r s t u v x y".split()

# 1-based: a→1 ... đ→5. `so_hau_to = 0` nghĩa là không có hậu tố (KG v0.5 §5).
_LETTER_ORDER = {ch: i + 1 for i, ch in enumerate(VI_LETTERS)}

# Lớp ký tự cho regex — dựng TỪ bảng trên, không hardcode "a-z".
_LC = "".join(VI_LETTERS)

# Số La Mã dùng đánh dấu TIẾT — "(i) (ii) (iii)..." bên trong một Điểm. Bảng tường
# minh, cùng kỷ luật với VI_LETTERS: không suy ra bằng thuật toán chuyển số La Mã.
# Dài nhất đứng trước để regex alternation khớp "iii" chứ không dừng ở "ii".
ROMAN = ["viii", "vii", "iii", "vi", "iv", "ix", "ii", "i", "v", "x"]
ROMAN_ORDER = {r: i + 1 for i, r in enumerate(
    ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]
)}
_ROMAN_ALT = "|".join(ROMAN)

_DIEU_RE = re.compile(rf"^Điều\s+(\d+)([{_LC}])?\s*\.\s*(.*)$")
_KHOAN_RE = re.compile(rf"^(\d{{1,3}})([{_LC}])?\s*\.\s+(.*)$")
_DIEM_RE = re.compile(rf"^([{_LC}])\)\s*(.*)$")
_CHUONG_RE = re.compile(r"^(Chương|Mục|Phần|Phụ lục)\s+[IVXLC\d]")
# Tiết "(i) ..." bên trong một Điểm. KHÔNG được cấp địa chỉ node (xem TietSpan) —
# nhận diện ở đây chỉ để giữ quan hệ logic giữa các tiết.
_TIET_RE = re.compile(rf"^\(\s*({_ROMAN_ALT})\s*\)\s*(.*)$", re.I)
# Từ nối ở ĐUÔI tiết cho biết quan hệ với tiết kế tiếp.
_HOAC_RE = re.compile(r"(?:;|,)?\s*hoặc\s*$", re.I)
_VA_RE = re.compile(r"(?:;|,)?\s*và\s*$", re.I)

# Rác biên tập của luatvietnam (nút "Phân tích" mở khối chú giải của biên tập
# viên, không phải chữ của luật). Giữ bộ lọc riêng ở đây — sửa _NOISE_LINES
# trong extract.py sẽ đổi hành vi đường ingest đang chạy.
_EXTRA_NOISE = {"Phân tích", "VB song ngữ", "Xem thêm tất cả", "Lược đồ"}
_NOISE = _NOISE_LINES | _EXTRA_NOISE

# Mảnh vỡ do hyperlink cắt dòng: dòng chỉ có dấu câu nối đuôi dòng trước.
_ORPHAN_PUNCT = ";,.:"


def letter_to_so_hau_to(ch: str | None) -> int:
    """Chữ cái → `so_hau_to` 1-based. Tra bảng, KHÔNG dùng ord()."""
    if not ch:
        return 0
    try:
        return _LETTER_ORDER[ch]
    except KeyError:  # pragma: no cover - chỉ xảy ra khi regex sai
        raise ValueError(f"{ch!r} không thuộc bảng 23 chữ đánh số VN") from None


def is_marker(line: str) -> bool:
    """Dòng có phải là marker cấu trúc (Điều / Chương / Khoản / Điểm)?"""
    return bool(
        _DIEU_RE.match(line)
        or _CHUONG_RE.match(line)
        or _KHOAN_RE.match(line)
        or _DIEM_RE.match(line)
    )


def clean_text(raw: str) -> str:
    """Text thô → text sạch, mỗi dòng một đoạn.

    Bỏ dòng rác; bỏ luôn khối chú giải (mọi dòng sau một dòng rác cho tới
    marker cấu trúc kế tiếp); nối mảnh vỡ hyperlink chỉ chứa dấu câu.
    """
    out: list[str] = []
    skipping = False
    for raw_line in raw.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line in _NOISE:
            skipping = True
            continue
        if is_marker(line):
            skipping = False
        elif skipping:
            continue
        if out and line[0] in _ORPHAN_PUNCT:
            out[-1] += line
            continue
        out.append(line)
    return "\n".join(out)


def slice_dieu(text: str, so_goc: int, so_hau_to: int = 0) -> str:
    """Cắt khối một Điều ra khỏi văn bản đã sạch (dùng cho --from-html)."""
    lines = text.split("\n")
    start = end = None
    for i, line in enumerate(lines):
        m = _DIEU_RE.match(line)
        if not m:
            continue
        if start is None:
            if int(m.group(1)) == so_goc and letter_to_so_hau_to(m.group(2)) == so_hau_to:
                start = i
        else:
            end = i
            break
    if start is None:
        raise ValueError(f"Không tìm thấy Điều {so_goc} trong văn bản")
    return "\n".join(lines[start:end])


def _line_offsets(text: str) -> list[tuple[str, int, int]]:
    """[(dòng, start, end)] — offset tuyệt đối trong `text`."""
    out: list[tuple[str, int, int]] = []
    pos = 0
    for line in text.split("\n"):
        out.append((line, pos, pos + len(line)))
        pos += len(line) + 1  # +1 cho ký tự \n
    return out


def _split_tiet(
    lines: list[tuple[str, int, int]], dieu_text: str
) -> list[TietSpan]:
    """Các dòng của một Điểm → danh sách tiết `(i)/(ii)` kèm từ nối.

    Từ nối đọc ở ĐUÔI mỗi tiết ("...tạo lập; hoặc"). Chỉ có ';' trần thì để
    `unknown`: tiếng Việt pháp lý dùng ';' cho cả liệt kê lẫn lựa chọn, đoán bừa
    sẽ biến phép TUYỂN thành phép HỘI — đúng loại lỗi đổi nghĩa mà cả pipeline
    này sinh ra để chặn.
    """
    groups: list[tuple[str, list[tuple[str, int, int]]]] = []
    for line, start, end in lines:
        m = _TIET_RE.match(line)
        if m:
            groups.append((m.group(1).lower(), [(line, start, end)]))
        elif groups:
            groups[-1][1].append((line, start, end))

    out: list[TietSpan] = []
    for marker, grp in groups:
        a, b = grp[0][1], grp[-1][2]
        tail = dieu_text[a:b].rstrip()
        if _HOAC_RE.search(tail):
            conn = "hoac"
        elif _VA_RE.search(tail):
            conn = "va"
        else:
            conn = "unknown"
        out.append(
            TietSpan(marker=marker, start=a, end=b, text=dieu_text[a:b], connector=conn)
        )
    return out


def khoan_de_trich(dieu: DieuNode) -> list[KhoanNode]:
    """Danh sách Khoản dùng để trích. Điều không chẻ Khoản → một khoản ẢO.

    Đo trên corpus: 25/267 điều (9.4%) không có khoản đánh số nào — thân điều là
    một đoạn liền. Không chỉ điều định nghĩa: Điều 9 "Mở và sử dụng tài khoản
    thanh toán", Điều 38 "Trách nhiệm thi hành" của ND52 cũng vậy. Trước khi có
    hàm này, vòng lặp `for k in dieu.khoan` chạy 0 lần và **cả điều bị bỏ qua
    không một lời báo** — đúng kiểu lỗi im lặng mà pipeline này sinh ra để chặn.

    Khoản ảo mang `id` của chính Điều (không bịa ra "khoản 1" không tồn tại) và
    `so_hien_thi = ""` để phân biệt với khoản thật.
    """
    if dieu.khoan:
        return dieu.khoan
    head = dieu.text.split("\n", 1)[0]
    start = min(len(head) + 1, dieu.end)
    if start >= dieu.end:
        return []
    return [
        KhoanNode(
            id=dieu.id,
            so_hien_thi="",
            so_goc=0,
            so_hau_to=0,
            start=start,
            end=dieu.end,
            text=dieu.text[start : dieu.end],
        )
    ]


def tiet_logic(diem: DiemNode) -> str:
    """Các tiết của một Điểm kết hợp theo phép gì: all | any | unknown."""
    conns = {t.connector for t in diem.tiet}
    if "hoac" in conns:
        return "any"
    if "va" in conns:
        return "all"
    return "unknown"


def parse_dieu(dieu_text: str, so_hieu: str) -> DieuNode:
    """Parse text của MỘT Điều thành cây, offset tính từ 0 trong `dieu_text`.

    `so_hieu` là số hiệu văn bản, ví dụ "52/2024/NĐ-CP".
    """
    lines = _line_offsets(dieu_text)
    if not lines:
        raise ValueError("Văn bản rỗng")

    head = _DIEU_RE.match(lines[0][0])
    if not head:
        raise ValueError(f"Dòng đầu không phải tiêu đề Điều: {lines[0][0][:60]!r}")

    so_goc = int(head.group(1))
    so_hau_to = letter_to_so_hau_to(head.group(2))
    so_hien_thi = f"{so_goc}{head.group(2) or ''}"
    dieu_id = f"{so_hieu}#than/dieu_{so_hien_thi}"

    # Gom dòng theo Khoản, rồi theo Điểm bên trong Khoản.
    khoan_groups: list[tuple[re.Match[str], list[tuple[str, int, int]]]] = []
    for line, start, end in lines[1:]:
        m = _KHOAN_RE.match(line)
        if m:
            khoan_groups.append((m, [(line, start, end)]))
        elif khoan_groups:
            khoan_groups[-1][1].append((line, start, end))

    khoan_nodes: list[KhoanNode] = []
    for m, group in khoan_groups:
        k_hau_to = letter_to_so_hau_to(m.group(2))
        k_hien_thi = f"{m.group(1)}{m.group(2) or ''}"
        k_id = f"{dieu_id}#khoan_{k_hien_thi}"
        k_start, k_end = group[0][1], group[-1][2]

        diem_groups: list[tuple[re.Match[str], list[tuple[str, int, int]]]] = []
        for line, start, end in group[1:]:
            dm = _DIEM_RE.match(line)
            if dm:
                diem_groups.append((dm, [(line, start, end)]))
            elif diem_groups:
                diem_groups[-1][1].append((line, start, end))

        diem_nodes = [
            DiemNode(
                id=f"{k_id}#diem_{dm.group(1)}",
                so_hien_thi=dm.group(1),
                so_goc=0,  # Điểm không có phần số, chỉ có chữ
                so_hau_to=letter_to_so_hau_to(dm.group(1)),
                start=dg[0][1],
                end=dg[-1][2],
                text=dieu_text[dg[0][1] : dg[-1][2]],
                tiet=_split_tiet(dg, dieu_text),
            )
            for dm, dg in diem_groups
        ]

        khoan_nodes.append(
            KhoanNode(
                id=k_id,
                so_hien_thi=k_hien_thi,
                so_goc=int(m.group(1)),
                so_hau_to=k_hau_to,
                start=k_start,
                end=k_end,
                text=dieu_text[k_start:k_end],
                diem=diem_nodes,
            )
        )

    return DieuNode(
        id=dieu_id,
        so_hien_thi=so_hien_thi,
        so_goc=so_goc,
        so_hau_to=so_hau_to,
        start=0,
        end=lines[-1][2],
        text=dieu_text[: lines[-1][2]],
        tieu_de=head.group(3).strip(),
        khoan=khoan_nodes,
    )
