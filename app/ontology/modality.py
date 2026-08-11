"""Từ điển tình thái (deontic) tiếng Việt + kiểm tra thêm/bớt so với văn bản gốc.

Vì sao cần: neo `char_span` chỉ chứng minh chuỗi CÓ trong luật, không chứng minh
phần diễn giải của mô hình giữ nguyên NGHĨA. Lỗi thật đã gặp ở giai đoạn 1: Gemini
viết "**phải** đáp ứng đầy đủ" trong khi luật viết "cấp Giấy phép **khi** đáp ứng
đầy đủ" — biến điều kiện được cấp phép thành nghĩa vụ. Câu vẫn xuôi nên đọc lướt
không thấy; chỉ so tập dấu hiệu tình thái mới bắt được.

Nguyên tắc: tập dấu hiệu tình thái trong câu mô hình viết phải là TẬP CON của tập
trong đoạn luật đã neo. Thêm nghĩa vụ/cấm đoán ⇒ lỗi cứng.
"""
from __future__ import annotations

import difflib
import re
from collections import Counter

from pydantic import BaseModel

# Nhóm dấu hiệu. Thứ tự trong mỗi nhóm không quan trọng — việc khớp dài-nhất-trước
# được xử lý khi dựng regex bên dưới.
MODALITY: dict[str, list[str]] = {
    "nghia_vu": ["phải", "có trách nhiệm", "có nghĩa vụ", "buộc phải", "bắt buộc"],
    "cam": ["không được phép", "không được", "nghiêm cấm", "cấm"],
    "cho_phep": ["được phép", "có quyền", "được"],
    "dieu_kien": ["trong trường hợp", "với điều kiện", "trừ trường hợp", "khi", "nếu"],
    "dinh_luong": [
        "tối thiểu", "tối đa", "ít nhất", "nhiều nhất", "không quá",
        "chậm nhất", "trong thời hạn", "trở lên", "trở xuống",
    ],
    "chi_duoc": ["chỉ được phép", "chỉ được"],
    "mien_tru": ["không bắt buộc", "được miễn", "không phải"],
}

# Thêm dấu hiệu thuộc các nhóm này = bịa ra ràng buộc pháp lý → chặn cứng.
_HARD_GROUPS = {"nghia_vu", "cam"}
# Mất dấu hiệu thuộc nhóm này = biến có-điều-kiện thành vô-điều-kiện → cảnh báo.
_SOFT_LOSS_GROUPS = {"dieu_kien"}

_PHRASE_GROUP = {p: g for g, ps in MODALITY.items() for p in ps}

# BẪY CHÍNH: "được" là chuỗi con của "không được". Nếu khớp ngắn trước thì mọi câu
# CẤM sẽ bị đọc thành CHO PHÉP. Sắp giảm dần theo độ dài để khớp dài nhất thắng.
_MODALITY_RE = re.compile(
    r"(?<![\wÀ-ỹ])(" + "|".join(re.escape(p) for p in sorted(_PHRASE_GROUP, key=len, reverse=True)) + r")(?![\wÀ-ỹ])"
)

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
_WORD_RE = re.compile(r"[\wÀ-ỹ]+|[^\s\wÀ-ỹ]")

# Đoạn `replace` dài là dấu hiệu difflib đang gióng hai đoạn KHÁC NHAU, không phải một
# phép thay từ tình thái. Đảo cực là phát biểu về việc TRÁO MỘT TỪ, nên hai vế phải
# ngắn. Đo được trên corpus: flip thật là 1↔1 từ (`'khi' → 'phải'`); báo nhầm duy nhất
# là 29↔6 từ — nhãn tóm tắt cả một danh sách liệt kê thành một mệnh đề (ND52 Đ26 k1).
_FLIP_MAX_TU = 6


class Delta(BaseModel):
    """Chênh lệch tình thái giữa câu mô hình viết và đoạn luật đã neo."""

    added: dict[str, list[str]] = {}  # nhóm → dấu hiệu bị THÊM
    lost: dict[str, list[str]] = {}  # nhóm → dấu hiệu bị MẤT
    added_numbers: list[str] = []
    flips: list[tuple[str, str]] = []  # (chữ trong luật, chữ mô hình thay vào)
    # Nguồn nêu điều kiện ("khi/nếu"), mô hình bỏ mất và phát biểu như nghĩa vụ.
    condition_to_obligation: bool = False
    # Nhóm ràng buộc mà diễn giải khẳng định NHƯNG nguồn KHÔNG hề có. Đây mới là
    # "bịa ra ràng buộc"; thêm số lần xuất hiện của một nhóm đã có sẵn thì không —
    # đó thường chỉ là phân phối lệnh cấm ra từng vế, hoặc thay từ đồng nghĩa.
    invented_groups: list[str] = []

    @property
    def hard_error(self) -> bool:
        """Bịa nhóm ràng buộc, bịa số, đảo cực, hoặc biến điều kiện → nghĩa vụ."""
        return (
            bool(self.invented_groups)
            or bool(self.added_numbers)
            or bool(self.flips)
            or self.condition_to_obligation
        )

    @property
    def soft_warning(self) -> bool:
        return bool(set(self.lost) & _SOFT_LOSS_GROUPS) or bool(set(self.added) - _HARD_GROUPS)

    def describe(self) -> list[str]:
        out = []
        if self.condition_to_obligation:
            out.append(
                "[LỖI] luật nêu ĐIỀU KIỆN nhưng diễn giải phát biểu như NGHĨA VỤ "
                "(mất 'khi/nếu', thêm 'phải/không được')"
            )
        for src, dst in self.flips:
            out.append(f"[LỖI] đảo cực tình thái: {src!r} → {dst!r}")
        for group in self.invented_groups:
            out.append(
                f"[LỖI] bịa ràng buộc nhóm {group}: nguồn không có dấu hiệu nào thuộc nhóm này"
            )
        for group, phrases in sorted(self.added.items()):
            if group in self.invented_groups:
                continue  # đã báo ở trên
            out.append(f"[cảnh báo] thêm dấu hiệu {group}: {', '.join(phrases)}")
        if self.added_numbers:
            out.append(f"[LỖI] bịa số không có trong nguồn: {', '.join(self.added_numbers)}")
        for group, phrases in sorted(self.lost.items()):
            if group in _SOFT_LOSS_GROUPS:
                out.append(f"[cảnh báo] mất dấu hiệu {group}: {', '.join(phrases)}")
        return out


def find_markers(text: str) -> Counter[str]:
    """Đếm dấu hiệu tình thái, khớp dài-nhất-trước và theo biên từ."""
    return Counter(m.group(1) for m in _MODALITY_RE.finditer(text.lower()))


def _norm_num(s: str) -> str:
    return s.replace(".", "").replace(",", "").lstrip("0") or "0"


def find_numbers(text: str) -> Counter[str]:
    return Counter(_norm_num(m.group()) for m in _NUM_RE.finditer(text))


def groups_in(text: str) -> set[str]:
    """Các NHÓM tình thái có mặt trong đoạn (không quan tâm số lần)."""
    return {_PHRASE_GROUP[m.group(1)] for m in _MODALITY_RE.finditer(text.lower())}


def _groups_in(text: str) -> set[str]:
    return {_PHRASE_GROUP[m.group(1)] for m in _MODALITY_RE.finditer(text)}


def modality_flips(claim: str, source: str) -> list[tuple[str, str]]:
    """Bắt ĐẢO CỰC tình thái theo vị trí, thứ phép đếm tập con bỏ lọt.

    Lỗi thật đã gặp: luật viết "cấp Giấy phép **khi** đáp ứng đầy đủ", mô hình viết
    "**phải** đáp ứng đầy đủ". Đếm không bắt được vì đoạn nguồn tình cờ có sẵn 2 chữ
    "phải" ở chỗ khác ("không phải là ngân hàng", "phải đảm bảo duy trì") nên hiệu
    bằng 0. Phải canh theo vị trí: đoạn nào bị THAY, nhóm tình thái hai bên khác nhau
    thì đó là đổi nghĩa pháp lý.
    """
    a = _WORD_RE.findall(source.lower())
    b = _WORD_RE.findall(claim.lower())
    out: list[tuple[int, str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag != "replace":
            continue
        if max(i2 - i1, j2 - j1) > _FLIP_MAX_TU:
            # Không phải tráo từ tình thái mà là hai đoạn khác hẳn nhau bị gióng vào
            # nhau — thường gặp khi nhãn tóm tắt một danh sách liệt kê dài.
            continue
        src, dst = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        gs, gc = _groups_in(src), _groups_in(dst)
        if gs and gc and gs != gc:
            out.append((i2 - i1 + j2 - j1, src, dst))
    # Đoạn thay càng ngắn thì càng chắc là đổi đúng một từ tình thái → báo trước.
    return [(s, d) for _, s, d in sorted(out)]


def _hard_deu_co_can_cu(claim: str, source: str) -> bool:
    """Mọi dấu hiệu ràng buộc CỨNG trong `claim` đều có mặt trong nguồn KÈM NGỮ CẢNH.

    Phép đếm theo nhóm không phân biệt được hai tình huống rất khác nhau, vì cả hai đều
    có nhóm ràng buộc ở cả hai bên:

    - luật *"cấp Giấy phép **khi** đáp ứng đầy đủ"* → nhãn *"**phải** đáp ứng đầy đủ"*:
      cùng một cụm nội dung, tình thái bị đổi. Cặp `"phải đáp"` KHÔNG có trong nguồn.
    - luật *"các hành vi **không được** thực hiện khi mở và sử dụng…"* → nhãn *"hành vi
      **không được** thực hiện"*: mô hình CHÉP lại lệnh cấm rồi bỏ phần đuôi danh ngữ.
      Cặp `"không được thực"` CÓ nguyên văn trong nguồn.

    Trường hợp sau không phải "biến điều kiện thành nghĩa vụ" — chữ "khi" bị mất nằm
    trong danh ngữ (*"hành vi … khi mở và sử dụng"*), không chi phối toán tử tình thái.
    Xét cặp (dấu hiệu + từ liền sau) tách được đúng hai tình huống này; xét riêng dấu
    hiệu thì không, vì cả hai bên đều có nó.
    """
    src = source.lower()
    for m in _MODALITY_RE.finditer(claim.lower()):
        if _PHRASE_GROUP[m.group(1)] not in _HARD_GROUPS:
            continue
        sau = _WORD_RE.search(claim.lower(), m.end())
        cap = f"{m.group(1)} {sau.group()}" if sau else m.group(1)
        if cap not in src:
            return False
    return True


def modality_delta(claim: str, source: str) -> Delta:
    """So câu mô hình viết (`claim`) với đoạn luật đã neo (`source`)."""
    c, s = find_markers(claim), find_markers(source)
    added: dict[str, list[str]] = {}
    lost: dict[str, list[str]] = {}
    for phrase in (c - s):
        added.setdefault(_PHRASE_GROUP[phrase], []).append(phrase)
    for phrase in (s - c):
        lost.setdefault(_PHRASE_GROUP[phrase], []).append(phrase)

    added_numbers = sorted(find_numbers(claim) - find_numbers(source))

    claim_groups = {_PHRASE_GROUP[p] for p in c}
    source_groups = {_PHRASE_GROUP[p] for p in s}
    # Chỉ tính là BỊA khi nguồn không có dấu hiệu nào thuộc nhóm đó. Đếm theo số
    # lần xuất hiện gây báo nhầm: mô hình phân phối một lệnh cấm ra nhiều vế
    # ("không được X; không được phép Y, Z" → "không được X, không được Y, không
    # được Z") sẽ ra "thêm 2 lệnh cấm" dù nguồn đã cấm sẵn.
    invented = sorted((claim_groups - source_groups) & _HARD_GROUPS)

    # "Điều kiện → nghĩa vụ": phép đếm tập con bỏ lọt biến đổi này khi đoạn nguồn
    # tình cờ đã có sẵn chữ "phải" ở chỗ khác (case thật: "không phải là ngân hàng"
    # và "phải đảm bảo duy trì" nằm cùng câu bao trùm với "khi đáp ứng đầy đủ").
    # Điều kiện đủ: dấu hiệu điều kiện của luật BIẾN MẤT, diễn giải phát biểu nghĩa
    # vụ, VÀ diễn giải không còn dấu hiệu điều kiện nào. Vế cuối tránh báo nhầm khi
    # mô hình chỉ thay từ đồng nghĩa ("trong trường hợp" → "khi").
    # Vế cuối (`_hard_deu_co_can_cu`) chặn chế độ báo nhầm đo được ở TT17 Điều 16 khoản
    # 1 điểm c: mô hình CHÉP nguyên lệnh cấm của luật rồi bỏ phần đuôi danh ngữ có chữ
    # "khi" — không hề biến điều kiện thành nghĩa vụ. Ba vế đầu không tách được nó khỏi
    # case gốc vì cả hai đều "mất dieu_kien + có ràng buộc cứng + claim hết dieu_kien".
    cond_to_obl = (
        bool(lost.get("dieu_kien"))
        and bool(claim_groups & _HARD_GROUPS)
        and "dieu_kien" not in claim_groups
        and not _hard_deu_co_can_cu(claim, source)
    )
    return Delta(
        added={k: sorted(v) for k, v in added.items()},
        lost={k: sorted(v) for k, v in lost.items()},
        added_numbers=added_numbers,
        flips=modality_flips(claim, source),
        condition_to_obligation=cond_to_obl,
        invented_groups=invented,
    )


# `invented_groups` và `added_numbers` là cáo buộc VẮNG MẶT — "nguồn KHÔNG hề có X".
# Vắng mặt phải được kiểm trên TOÀN BỘ bằng chứng mô hình đã trích dẫn (bao lồi các đơn
# vị nó chọn), không phải trên lát cắt mà `quote` thu hẹp lại: không thể kết tội bịa một
# cụm nằm NGUYÊN VĂN bên trong chính bằng chứng đó. Hai cáo buộc này ĐƠN ĐIỆU theo độ
# rộng nguồn — nới nguồn ra thì tập phát hiện chỉ co lại, nên phép nới là an toàn một chiều.
#
# `flips` và `condition_to_obligation` cố ý KHÔNG được nới. Chúng là cáo buộc BIẾN ĐỔI
# một đoạn cụ thể, và `condition_to_obligation` còn NGƯỢC ĐƠN ĐIỆU: đoạn nguồn càng rộng
# thì "mất dấu hiệu điều kiện" càng dễ đúng một cách vô nghĩa, vì một Điểm dài luôn có
# 'khi/nếu' ở mệnh đề khác mà bản tóm tắt không nhắc tới. Đo được: TT17 Điều 16 khoản 2
# điểm c nới ra bao lồi thì hết `invented_groups` nhưng LẠI nổ `condition_to_obligation`
# do "khi có yêu cầu từ cơ quan có thẩm quyền" nằm ở mệnh đề mà nhãn không tóm. Nới cả
# gói là đổi một báo nhầm này lấy một báo nhầm khác.


def relax_absence(delta: Delta, claim: str, evidence: str) -> tuple[Delta, list[str]]:
    """Bỏ cáo buộc VẮNG MẶT không đứng vững trước toàn bộ bằng chứng đã trích dẫn.

    `delta` được đo trên lát cắt hẹp (`quote` đã thu hẹp); `evidence` là bao lồi các
    đơn vị mô hình đã chọn. Trả `(delta đã nới, ghi chú hạ mức)`. Ghi chú KHÔNG được
    bỏ đi: một cáo buộc bị hạ mức nghĩa là `quote` thu hẹp sai chỗ — nhãn mô tả chữ
    nằm ngoài span, nên `text` của bản ghi KHÔNG chứa đoạn mà nhãn đang nói tới.
    """
    if not (delta.invented_groups or delta.added_numbers):
        return delta, []
    wide = modality_delta(claim, evidence)
    out = delta.model_copy(deep=True)
    notes: list[str] = []
    bo_nhom = sorted(set(delta.invented_groups) - set(wide.invented_groups))
    bo_so = sorted(set(delta.added_numbers) - set(wide.added_numbers))
    if bo_nhom:
        out.invented_groups = list(wide.invented_groups)
        notes.append(
            f"hạ mức 'bịa ràng buộc nhóm {', '.join(bo_nhom)}': cụm này CÓ trong các đơn "
            "vị đã chọn, chỉ nằm ngoài đoạn mà 'quote' thu hẹp vào"
        )
    if bo_so:
        out.added_numbers = list(wide.added_numbers)
        notes.append(
            f"hạ mức 'bịa số {', '.join(bo_so)}': số này CÓ trong các đơn vị đã chọn, "
            "chỉ nằm ngoài đoạn mà 'quote' thu hẹp vào"
        )
    if notes:
        notes.append(
            "⇒ 'quote' thu hẹp sai chỗ: `text` của trường này KHÔNG chứa đoạn mà nhãn "
            "đang mô tả — cần người duyệt xác nhận phạm vi"
        )
    return out, notes


# Viện dẫn tương đối mà văn bản QPPL dùng để tự trỏ về chính nó. Chỉ dựng cho `Điều`
# và `khoản`: `điểm` đánh bằng chữ cái nên không sinh ra số để mà tranh cãi, còn
# "Thông tư này"/"Nghị định này" thì corpus chưa có case nào mô hình khai triển ra số
# hiệu — dựng trước là thiết kế không có dữ liệu.
_TU_TRO = {
    "dieu": (re.compile(r"Điều\s+này", re.I), "Điều"),
    "khoan": (re.compile(r"khoản\s+này", re.I), "khoản"),
}


def relax_dereference(
    delta: Delta, claim: str, source: str, *, so_dieu: int = 0, so_khoan: int = 0
) -> tuple[Delta, list[str]]:
    """Bỏ cáo buộc "bịa số" khi số đó chỉ là mô hình KHAI TRIỂN một viện dẫn tương đối.

    Case thật: luật viết *"Quy định tại khoản 1 **Điều này** không áp dụng…"*, mô hình
    viết *"Quy định tại khoản 1 **Điều 26**"*. Suy ra đúng — nó **là** Điều 26 — nhưng
    số 26 không có trong đoạn được viện dẫn nên guard đọc thành bịa số.

    Ba điều kiện phải đủ cả, và cả ba đều kiểm được TẤT ĐỊNH:

    1. đoạn luật đã neo thật sự chứa cụm tự trỏ (`"Điều này"` / `"khoản này"`);
    2. số bị tố cáo **khớp đúng** số Điều/Khoản đang xét;
    3. trong nhãn, số đó đứng **ngay sau** đúng từ đó (`"Điều 26"`, không phải một số 26
       lạc ở chỗ khác).

    Vế 3 là vế chống lọt: thiếu nó thì một nhãn viết *"áp dụng cho 26 tổ chức"* trong
    một Khoản của Điều 26 cũng được tha, mà đó mới đúng là bịa số.

    KHÔNG mở rộng thành "mọi số suy ra được đều tha": `citation.py` đã giải viện dẫn
    tương đối thành khoá node ở `references` một cách tất định rồi, nên nhãn chép thêm
    số vào **không mang thêm thông tin** — phép nới này chỉ để bản ghi khỏi bị đánh dấu
    không dùng được, không phải để khuyến khích mô hình tự suy.
    """
    if not delta.added_numbers:
        return delta, []
    ngu_canh = {"dieu": so_dieu, "khoan": so_khoan}
    con_lai, bo = [], []
    for n in delta.added_numbers:
        cua = next(
            (
                tu
                for key, (re_tu_tro, tu) in _TU_TRO.items()
                if ngu_canh[key] > 0
                and n == str(ngu_canh[key])
                and re_tu_tro.search(source)
                and re.search(rf"{tu}\s+0*{re.escape(n)}(?!\d)", claim, re.I)
            ),
            None,
        )
        (bo if cua else con_lai).append((n, cua) if cua else n)
    if not bo:
        return delta, []
    out = delta.model_copy(deep=True)
    out.added_numbers = con_lai
    return out, [
        f"hạ mức 'bịa số {n}': mô hình khai triển viện dẫn tương đối {tu.lower()} này → "
        f"{tu} {n}, khớp đúng đơn vị đang xét. Khoá node đã có sẵn ở `references` "
        f"(giải tất định), nhãn không cần mang số này"
        for n, tu in bo
    ]


def explain(claim: str, source: str, max_ops: int = 4) -> str:
    """Diff mức TỪ, in gọn kiểu `khi → phải`.

    Thay cho báo "not_grounded" chung chung: chỉ đích danh chữ bị đổi để người rà
    soát nhìn một cái là thấy.
    """
    a = _WORD_RE.findall(source.lower())
    b = _WORD_RE.findall(claim.lower())
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        src, dst = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if tag == "replace":
            parts.append(f"{src!r} → {dst!r}")
        elif tag == "delete":
            parts.append(f"mất {src!r}")
        else:
            parts.append(f"thêm {dst!r}")
        if len(parts) >= max_ops:
            parts.append("…")
            break
    return "; ".join(parts) if parts else "(không khác biệt ở mức từ)"


# --- Gán nhãn tình thái cho ActorCU (POC GraphCompliance) ----------------------

#: Thứ tự ưu tiên khi một đoạn chứa nhiều nhóm: nhóm khắt khe hơn thắng.
#: "cam" trước "chi_duoc": câu cấm thường kèm vế cho phép có điều kiện.
_UU_TIEN = ("cam", "chi_duoc", "mien_tru", "nghia_vu", "cho_phep")


def gan_modality(text: str) -> str:
    """Nhãn tình thái của MỘT trường đã neo — tất định, chỉ từ điển.

    "không phải là" bị loại: đó là phủ định danh xưng ("không phải là ngân hàng"),
    không phải miễn trừ nghĩa vụ. Kiểm từ liền sau, cùng cách `_hard_deu_co_can_cu`
    xét cặp (dấu hiệu + từ liền sau).
    """
    low = text.lower()
    groups: set[str] = set()
    for m in _MODALITY_RE.finditer(low):
        g = _PHRASE_GROUP[m.group(1)]
        if g == "mien_tru" and m.group(1) == "không phải":
            sau = _WORD_RE.search(low, m.end())
            if sau and sau.group() == "là":
                continue
        groups.add(g)
    return next((g for g in _UU_TIEN if g in groups), "khong_ro")
