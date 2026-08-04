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


# --- Câu bao trùm của một Điểm quyết phép nối các tiết ------------------------
#
# Đo trên 18 fixture trước khi viết: cả corpus chỉ có **5 Điểm có tiết**, 2 đã giải
# được bằng liên từ hiện ("hoặc"), 3 còn `unknown`. Trong 3 cái đó chỉ **1** mang cụm
# chapeau — TT18 Đ9 k3 điểm c, *"phải đảm bảo **các nguyên tắc sau**:"*. Nên luật này
# mua đúng một ca hôm nay; nó đáng viết vì tất định và vì cụm đó lặp lại khắp VBQPPL,
# không vì số lượng.
#
# Cái bắt buộc phải đo là **cụm "sau" trong corpus có ĐỦ BA CỰC TRÁI NGƯỢC NHAU**:
#
#   ALL       "phải đảm bảo các nguyên tắc sau:"  ·  "đáp ứng tối thiểu các yêu cầu sau:"
#   ANY       "đáp ứng ít nhất MỘT TRONG các tiêu chí sau:"
#   loại trừ  "KHÔNG ÁP DỤNG đối với các trường hợp sau:"  ·  "TRỪ các quy định sau đây"
#   định nghĩa "(sau đây GỌI LÀ …)" — 15+ lần, dạng ĐÔNG NHẤT trong corpus
#
# Một regex lỏng sẽ bắt nhầm chính cái dạng đông nhất, và tệ hơn là đọc `any` thành
# `all` — đảo nghĩa pháp lý. Ba chốt chặn: cụm phải nằm ở **ĐUÔI** chapeau (một mình
# điều này đã loại hết `(sau đây gọi là …)` vì chúng nằm giữa câu); "một trong" hạ
# xuống `any`; loại trừ và định nghĩa trả `unknown` chứ không đoán.
_CHAPEAU_DS = re.compile(
    r"(?:các|những)\s+[^.;:\n]{0,40}?(?:sau đây|như sau|sau)\s*:?\s*$", re.IGNORECASE
)
_CHAPEAU_ANY = re.compile(r"một trong|ít nhất một", re.IGNORECASE)
# "(?<!bù )" giữ "Hệ thống bù trừ điện tử" khỏi bị đọc thành mệnh đề loại trừ.
_CHAPEAU_TRU = re.compile(
    r"không áp dụng|(?<!bù )trừ\s+(?:các|những|trường hợp|quy định)", re.IGNORECASE
)
_CHAPEAU_DINH_NGHIA = re.compile(r"được hiểu|gọi là|gọi tắt", re.IGNORECASE)


def chapeau_cua_diem(diem: DiemNode) -> str:
    """Phần chữ của Điểm nằm TRƯỚC tiết đầu tiên. Rỗng nếu Điểm không có tiết."""
    if not diem.tiet:
        return ""
    return diem.text[: diem.tiet[0].start - diem.start]


def chapeau_logic(chapeau: str) -> tuple[str, str | None]:
    """Câu bao trùm → (all | any | unknown, cụm đã khớp).

    Chỉ đọc dấu hiệu HIỆN trong chữ luật, cùng hạng với việc đọc "hoặc"/"và" — không
    suy diễn. Không khớp thì trả `unknown`, không đoán.
    """
    t = " ".join(chapeau.split())
    m = _CHAPEAU_DS.search(t)
    if not m:
        return "unknown", None
    # Danh sách định nghĩa hay danh sách NGOẠI LỆ không phải phép nối các yêu cầu —
    # gán `all`/`any` cho chúng là trả lời một câu hỏi khác với câu đang hỏi.
    if _CHAPEAU_DINH_NGHIA.search(t) or _CHAPEAU_TRU.search(t):
        return "unknown", None
    return ("any" if _CHAPEAU_ANY.search(t) else "all"), m.group(0)


def tiet_logic(diem: DiemNode) -> str:
    """Các tiết của một Điểm kết hợp theo phép gì: all | any | unknown.

    Liên từ hiện trên chính tiết THẮNG câu bao trùm: nó nói về đúng hai tiết đang xét,
    còn chapeau nói về cả danh sách. Chapeau chỉ là đường lui khi tiết im lặng.
    """
    conns = {t.connector for t in diem.tiet}
    if "hoac" in conns:
        return "any"
    if "va" in conns:
        return "all"
    return chapeau_logic(chapeau_cua_diem(diem))[0]


# --- Guard "áp dụng khi" — tất định, không hỏi LLM (xem GuardApDung) ------------
#
# Ba dạng được nhận, rút ra từ ĐO trên 18 fixture chứ không từ suy đoán văn phạm:
#
#   A  "đối với khách hàng LÀ cá nhân"          → ("khách hàng", "cá nhân")      8 ca
#   B  "Đối với tài khoản thanh toán CỦA cá nhân:" → ("tài khoản thanh toán", "cá nhân")  4 ca
#   C  "Đối với thẻ trả trước,"  (danh ngữ trần)  → ("thẻ", "thẻ trả trước")     3 ca
#
# Dạng C **chỉ** được nhận khi cụm MỞ ĐẦU đơn vị (tức nó phủ cả đơn vị), ngắn, và
# không mở đầu bằng từ cho biết đây không phải tên một loại. Nới lỏng vế đó ra thì
# mẫu nền bắt 36 ca mà phần lớn là rác — đã đo: `thuoc_tinh='các'`, `'phát'`, `'trường'`.

_GUARD_TRIGGER = re.compile(r"(?:^|[\s(;])(đối với|trường hợp)\s+", re.IGNORECASE)
# Cụm chứa viện dẫn là ĐỊA CHỈ, không phải loại đối tượng: "đối với các trường hợp
# quy định tại Điều 5" nói về phạm vi, không nói về thuộc tính của ai.
_GUARD_VIEN_DAN = re.compile(
    r"quy định tại|Điều\s+\d|khoản\s+\d|điểm\s+[a-zđ]\b|Thông tư|Nghị định|Mẫu số",
    re.IGNORECASE,
)
# Mở đầu bằng những từ này thì cụm là một TÌNH HUỐNG hoặc một tập hợp chung, không
# phải tên một loại đối tượng ("đối với CÁC tài liệu", "trường hợp PHÁT HIỆN…").
_GUARD_KHONG_PHAI_LOAI = re.compile(
    r"^(các|mọi|những|việc|từng|này|có|không|phát hiện|sử dụng|đề nghị|thay đổi"
    r"|từ chối|đóng|cung ứng|được|thỏa thuận|hồ sơ|văn bản)\b",
    re.IGNORECASE,
)
_GUARD_LA = re.compile(r"^(.{2,32}?)\s+là\s+(.{2,52}?)$", re.IGNORECASE)
_GUARD_CUA = re.compile(r"^(.{2,32}?)\s+của\s+(.{2,32}?)$", re.IGNORECASE)
# Cụm chứa những thứ này thì đã sang mệnh đề khác, tách ra là cắt nhầm câu.
_GUARD_XAU = re.compile(r"\bhoặc\b|\bvà\b|\bđối với\b|[()]", re.IGNORECASE)
# `)` là dấu KẾT của cụm, ngang hàng `;:,.` — guard hay nằm trong ngoặc đơn gắn vào một
# danh ngữ: *"…của chủ tài khoản thanh toán (đối với khách hàng là cá nhân), người đại
# diện hợp pháp (đối với khách hàng là tổ chức)…"*. Không dừng ở `)` thì cụm nuốt luôn
# dấu đóng ngoặc, `_GUARD_XAU` thấy `[()]` và loại — ba ca thật bị đẩy sang `guard_ngoai_mau`
# dù mẫu A khớp hoàn hảo sau khi cắt đúng.
_GUARD_CUM = re.compile(r"(.+?)([;:,.)]|$)", re.DOTALL)
_SO_THU_TU = re.compile(rf"^\s*(\d{{1,3}}[{_LC}]?\s*\.|[{_LC}]\s*\)|\(\s*({_ROMAN_ALT})\s*\))\s*", re.I)


def tach_guard(text: str, base: int = 0) -> tuple[tuple[str, str, str, int, int] | None, str]:
    """Text của MỘT đơn vị → (guard, cảnh báo).

    `guard` = `(thuoc_tinh, gia_tri, raw_text, start, end)` với offset đã cộng `base`
    để neo về `dieu.text`; `None` khi không có guard.
    `cảnh báo` = chuỗi rỗng, hoặc `"guard_ngoai_mau: …"` khi cụm TRÔNG như một guard mà
    không tách sạch được — cố ý **không đoán**, nhưng cũng không im lặng.

    Guard tại mỗi nút cố ý PHẲNG, MỘT CẤP: không guard lồng guard, không `else`, không
    thứ tự ưu tiên. Muốn biết hiệu lực đầy đủ của một tiết thì hợp dọc đường đi bằng
    `hop_guard()`.

    Chỉ nhận khi đơn vị có **ĐÚNG MỘT** guard sạch. Bản đầu trả cụm *đầu tiên*, và đó là
    một lỗi im lặng đã sống trong dữ liệu: TT17 Đ16 k1 điểm a có tiết (i) *"đối với khách
    hàng là cá nhân"* và tiết (ii) *"đối với khách hàng là tổ chức"*; đọc trên toàn văn
    Điểm thì cụm đầu thắng, Điểm nhận guard `cá nhân`, rồi `hop_guard` (AND dọc đường đi)
    cho tiết (ii) một guard **`cá nhân ∧ tổ chức` — bất khả thi**, không đối tượng nào
    thoả. Hai trên hai ca có guard ở cả hai tầng đều hỏng như vậy. Nhiều cụm khác nhau
    trong một đơn vị nghĩa là chúng gắn vào những danh ngữ khác nhau, không phải một guard
    phủ cả nút — chọn hộ là phán định.
    """
    m0 = _SO_THU_TU.match(text)
    moc = m0.end() if m0 else 0
    ngoai_mau: list[str] = []
    sach: list[tuple[str, str, str, int, int]] = []

    for m in _GUARD_TRIGGER.finditer(text):
        mc = _GUARD_CUM.match(text[m.end() :])
        if not mc:
            continue
        cum, ket = mc.group(1).strip(), mc.group(2)
        raw = text[m.start(1) : m.end() + len(mc.group(1).rstrip())]
        span = (base + m.start(1), base + m.end() + len(mc.group(1).rstrip()))

        if not cum or _GUARD_VIEN_DAN.search(cum):
            continue  # địa chỉ, không phải loại — bỏ hẳn, không cảnh báo

        la = _GUARD_LA.match(cum)
        if (
            la
            and not _GUARD_XAU.search(la.group(1))
            and not _GUARD_XAU.search(la.group(2))
            and la.group(1).strip().lower() not in {"trường hợp", "đối với"}
        ):
            sach.append((la.group(1).strip(), la.group(2).strip(), raw, *span))
            continue

        cua = _GUARD_CUA.match(cum)
        # Giữ `ket == ":"`: hình dạng `X của Y:` mở đầu một DANH SÁCH yêu cầu, tức đúng vị
        # trí một guard. Bỏ điều kiện này chỉ mua thêm đúng một ca trên toàn corpus —
        # ND52 Đ3 k9 *"…đứng tên mở tài khoản đối với tài khoản của tổ chức."* — mà đó là
        # một khoản ĐỊNH NGHĨA, nơi guard vô nghĩa vì không có nghĩa vụ nào để chặn.
        if cua and ket == ":" and not _GUARD_XAU.search(cum):
            sach.append((cua.group(1).strip(), cua.group(2).strip(), raw, *span))
            continue

        if (
            m.start(1) <= moc + 1
            and len(cum.split()) <= 4
            and not _GUARD_KHONG_PHAI_LOAI.match(cum)
            and not _GUARD_XAU.search(cum)
        ):
            sach.append((cum.split()[0], cum, raw, *span))
            continue

        # Trông như tên một loại mà không tách được ⇒ nói ra. Cụm dài hoặc mở đầu bằng
        # từ chỉ tình huống thì bỏ im lặng: cảnh báo cho cả 48 ca khớp trigger sẽ dìm
        # chết hàng đợi duyệt (hiện toàn corpus có 82 cảnh báo).
        if len(cum.split()) <= 6 and not _GUARD_KHONG_PHAI_LOAI.match(cum):
            ngoai_mau.append(cum[:60])

    # Cùng một guard lặp lại không phải mâu thuẫn — chỉ đếm các cặp KHÁC nhau.
    khac: list[tuple[str, str, str, int, int]] = []
    for g in sach:
        if (g[0], g[1]) not in [(x[0], x[1]) for x in khac]:
            khac.append(g)

    if len(khac) == 1:
        return khac[0], ""
    if len(khac) >= 2:
        ds = "; ".join(f"({a!r}, {b!r})" for a, b, *_ in khac[:3])
        return None, (
            f"guard_nhieu_cum: đơn vị này có {len(khac)} guard KHÁC nhau {ds} — chúng gắn "
            "vào những danh ngữ khác nhau chứ không phải một guard phủ cả nút, nên máy "
            "không chọn hộ. Nếu đây là chỗ phân nhánh thì guard thuộc về từng tiết/điểm con."
        )
    return None, (
        f"guard_ngoai_mau: khớp 'đối với/trường hợp' nhưng không tách được "
        f"(thuộc tính, giá trị): {'; '.join(repr(x) for x in ngoai_mau[:3])}"
        if ngoai_mau
        else ""
    )


def hop_guard(*guards) -> list:
    """Guard hiệu lực của một nút = AND của mọi guard dọc đường đi Điểm → tiết.

    Điểm *"đối với khách hàng là cá nhân"* chứa tiết *"trường hợp mở bằng eKYC"* ⇒ tiết
    áp dụng khi **cá nhân ∧ eKYC**. Phép hợp là AND thuần: không có `else`, không thứ tự
    ưu tiên, không guard lồng guard — mỗi nút một guard phẳng.

    Trả danh sách guard đã bỏ `None`, giữ nguyên thứ tự từ ngoài vào trong.
    """
    return [g for g in guards if g is not None]


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
