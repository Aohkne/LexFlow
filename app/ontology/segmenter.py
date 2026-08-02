"""Tách một Khoản thành các ĐƠN VỊ NGUYÊN TỬ đánh số, để LLM chọn ID thay vì chép chuỗi.

Đây là tầng "ngăn từ gốc" của cơ chế chống bịa: `char_span` được tính từ chính phép
tách của ta, nên LLM **không thể bịa provenance** — nó chỉ được chọn trong một tập
đóng. Khác với việc bắt LLM chép nguyên văn (giai đoạn 1): ở đó ta phát hiện bịa
SAU khi đã xảy ra, ở đây bịa là bất khả thi.

Ba mức tách:
0. **Gom dòng nối tiếp một câu.** `clean_text` giữ mỗi dòng nguồn một dòng, mà nguồn
   là HTML: mỗi viện dẫn được đặt trong thẻ `<a>` nên nằm trên dòng riêng. Một câu
   như *"a) Điều 9a và khoản 4 Điều 11 đã được sửa đổi… theo Thông tư số
   23/2019/TT-NHNN có hiệu lực đến hết ngày…"* về tới đây đã vỡ thành **7 dòng**. Coi
   `\n` là ranh giới cứng thì menu bày ra 5 "đơn vị", 4 trong đó là mảnh câu không có
   vị ngữ — mô hình buộc phải chọn giữa các mảnh không cái nào đứng vững một mình.
   Nên: dòng nào mà dòng TRƯỚC nó chưa kết thúc câu (không tận cùng bằng `.`/`;`/`:`)
   thì nối lại, và chỉ nối trong cùng một Điểm để không gộp nhầm hai Điểm.
1. Theo dòng logic đã gom — parser vẫn giữ cấu trúc (điểm a/b/c, chapeau).
2. Trong mỗi dòng, tách tiếp theo `;` — luật VN dùng dấu chấm phẩy rất dày để ngăn
   các điều kiện song song (thấy rõ ở điểm b, g, h của ND52 Điều 22). Chapeau tách
   thêm ở `:` khi đó là câu dẫn nhập ("...các điều kiện sau đây:").

MỌI offset tương đối với `dieu.text` — một gốc duy nhất cho cả cây lẫn đơn vị, khớp
`start`/`end` mà parser đã đặt cho node. Tiêu đề Điều cũng là một đơn vị (uid 0) để
chủ ngữ kế thừa có chỗ neo hợp lệ thay vì phải bịa.
"""
from __future__ import annotations

import re

from app.ontology.schema import DieuNode, KhoanNode, Unit

# Mảnh ngắn hơn ngưỡng này là vụn (đuôi câu, dấu lạc) → gộp vào đơn vị liền trước.
_MIN_UNIT = 15

_SEMI_RE = re.compile(r";")
_LEAD_IN_RE = re.compile(r":\s*$")
# Ranh giới câu: chấm + khoảng trắng + chữ HOA. Chữ số phía sau thì không cắt, nên
# số thập phân ("1.000") và số hiệu ("52/2024") an toàn.
_SENT_RE = re.compile(r"\.\s+(?=[A-ZĐÀ-Ỹ])")
# Dòng ngắn hơn ngưỡng này thì không cần tách câu (tránh vụn hoá vô ích).
_SENT_SPLIT_MIN = 200
# Vùng đầu dòng chứa marker ("1. ", "15a. ", "đ) ") — không cắt câu trong vùng này.
_MARKER_ZONE = 6
# Ký tự kết thúc một mệnh đề. Dòng không tận cùng bằng một trong số này thì câu còn
# chạy tiếp sang dòng sau — `\n` ở đó là dấu vết thẻ <a> của HTML, không phải ranh
# giới ngữ nghĩa. Đo trên 16 fixture: 90/267 chỗ xuống dòng là kiểu này.
_CAU_KET = ".;:"


def _split_line(line: str, base: int, allow_colon: bool) -> list[tuple[int, int]]:
    """Tách một dòng thành các span [start, end) đã cộng `base`, bỏ khoảng trắng rìa."""
    cuts = [m.end() for m in _SEMI_RE.finditer(line)]
    if len(line) >= _SENT_SPLIT_MIN:
        # Bỏ qua vùng marker đầu dòng ("1. ", "a) "): dấu chấm của số khoản cũng
        # khớp mẫu ranh giới câu, cắt ở đó sẽ tạo đơn vị rác chỉ chứa số.
        cuts += [m.start() + 1 for m in _SENT_RE.finditer(line) if m.start() >= _MARKER_ZONE]
    if allow_colon:
        # Chỉ ngắt ở ":" khi phần còn lại của dòng là câu dẫn nhập ("...sau đây:").
        cuts += [m.end() for m in re.finditer(r":", line) if _LEAD_IN_RE.search(line[m.start():])]

    spans: list[tuple[int, int]] = []
    bounds = sorted({0, *cuts, len(line)})
    for a, b in zip(bounds, bounds[1:]):
        piece = line[a:b]
        if not piece.strip():
            continue
        lead = len(piece) - len(piece.lstrip())
        trail = len(piece) - len(piece.rstrip())
        spans.append((base + a + lead, base + b - trail))
    return spans


def segment(dieu: DieuNode, khoan: KhoanNode) -> list[Unit]:
    """(Điều, Khoản) → đơn vị nguyên tử. uid 0 = tiêu đề Điều, 1..n = nội dung Khoản.

    Bất biến (test canh): `dieu.text[u.start:u.end] == u.text` với mọi đơn vị; các
    đơn vị của Khoản không chồng lấn và sắp tăng dần.
    """
    text = dieu.text
    head_line = text.split("\n", 1)[0]
    units = [Unit(uid=0, kind="tieu_de", source_diem=None, start=0, end=len(head_line),
                  text=head_line)]

    diem_ranges = [(d.start, d.end, d.so_hien_thi) for d in khoan.diem]

    # Mức 0 — gom dòng nối tiếp một câu. Phải làm TRƯỚC mọi phép tách khác: tách trên
    # dòng vật lý là tách trên dấu vết của HTML, không phải trên cấu trúc câu.
    dong: list[list] = []  # [start, end, label]
    pos = khoan.start
    for line in khoan.text.split("\n"):
        start = pos
        pos += len(line) + 1
        if not line.strip():
            continue
        a = start + len(line) - len(line.lstrip())
        b = start + len(line.rstrip())
        label = next((lb for x, y, lb in diem_ranges if x <= a < y), None)
        # Nối chỉ khi CÙNG Điểm — nếu không sẽ nuốt điểm b vào đuôi điểm a khi điểm a
        # tình cờ không có dấu kết. Điều kiện thứ hai: câu trước thật sự còn dang dở.
        if dong and dong[-1][2] == label and text[dong[-1][1] - 1] not in _CAU_KET:
            dong[-1][1] = b
        else:
            dong.append([a, b, label])

    raw: list[tuple[int, int, str | None]] = []
    for a, b, label in dong:
        for x, y in _split_line(text[a:b], a, allow_colon=label is None):
            raw.append((x, y, label))

    # Gộp mảnh vụn vào đơn vị liền trước cùng điểm, tránh đơn vị vô nghĩa trong menu.
    merged: list[list] = []
    for a, b, label in raw:
        if merged and (b - a) < _MIN_UNIT and merged[-1][2] == label:
            merged[-1][1] = b
        else:
            merged.append([a, b, label])
    # Mảnh vụn đứng ĐẦU không có đơn vị trước để gộp → gộp về phía sau.
    while len(merged) > 1 and (merged[0][1] - merged[0][0]) < _MIN_UNIT and merged[0][2] == merged[1][2]:
        merged[1][0] = merged[0][0]
        merged.pop(0)

    units += [
        Unit(
            uid=i,
            kind="diem" if label else "chapeau",
            source_diem=label,
            start=a,
            end=b,
            text=text[a:b],
        )
        for i, (a, b, label) in enumerate(merged, start=1)
    ]
    return units


def render_menu(units: list[Unit]) -> str:
    """Danh sách đơn vị đánh số để nhúng vào prompt."""
    tags = {"tieu_de": "tiêu đề Điều", "chapeau": "câu bao trùm"}
    return "\n".join(
        f"[{u.uid}] ({tags.get(u.kind) or f'điểm {u.source_diem}'}) {u.text}" for u in units
    )


def hull(units: list[Unit], uids: list[int]) -> tuple[int, int] | None:
    """Bao lồi các đơn vị được chọn → span [start, end). None nếu có uid không hợp lệ."""
    by_uid = {u.uid: u for u in units}
    if not uids or any(i not in by_uid for i in uids):
        return None
    chosen = [by_uid[i] for i in uids]
    return min(u.start for u in chosen), max(u.end for u in chosen)
