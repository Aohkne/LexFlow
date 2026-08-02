"""Phân loại vai ở mức ĐƠN VỊ (Khoản/Điểm), chạy TRƯỚC bước trích S-O-A-C.

`roles.py` phân loại ở mức **Điều** bằng tiêu đề — đo được 40/278 điều (14.4%)
không phải actor-CU. Nhưng vai của Điều không phải lúc nào cũng là vai của từng
Khoản bên trong nó, và chênh lệch đó gây ra CU rác thật, đã đo được (xem
`docs/ONTOLOGY-CLASSIFY.md` §2).

Ba phép thử, áp theo thứ tự (khung của GraphCompliance, arXiv:2510.26309):

- **Test A — vị trí văn bản.** Đơn vị có mang một cặp chủ-thể + hành-vi tại chỗ
  không? Có ⇒ ứng viên actor-CU (điều kiện trong cùng câu thuộc về CU đó). Không,
  mà đứng thành điều/khoản riêng dưới các tiêu đề "Phạm vi điều chỉnh", "Đối tượng
  áp dụng", "Hiệu lực thi hành" ⇒ sang Test B.
- **Test B — có thể bị vi phạm độc lập không?** Có ⇒ actor-CU. Không và không chặn
  cổng gì ⇒ premise. Không nhưng chặn cổng quy định khác ⇒ meta-CU.
- **Test C — phạm vi ảnh hưởng.** Chặn nhiều actor-CU / cả một chương-mục-văn bản
  ⇒ meta-CU (và `Gate` ghi lại phạm vi đó).

**Ranh giới trung thực:** Test A trong bài viết gốc nói tới quan hệ cú pháp
"cùng một câu". Ở đây không có phân tích cú pháp tiếng Việt; nó được XẤP XỈ bằng
hai tín hiệu đã đo được: (1) luật tiêu đề của `roles.py`, (2) từ điển tình thái
của `modality.py`. Mọi nhánh quyết định đều ghi lại trong `test_path` để người
đọc thấy phép xấp xỉ nào đã dùng, thay vì chỉ nhận một nhãn.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.ontology.citation import parse_citations, to_node_ids
from app.ontology.modality import groups_in
from app.ontology.roles import title_rule
from app.ontology.schema import DieuKienCong, DieuNode, Gate, KhoanNode

UnitType = Literal["premise", "meta_cu", "actor_cu"]
PremiseKind = Literal["dinh_nghia", "pham_vi", "vai_tro"]

# Nhóm tình thái chứng minh đơn vị có ĐẶT RA nghĩa vụ/cấm đoán tại chỗ. "cho_phep"
# CỐ Ý không nằm đây: dấu hiệu của nó là chữ "được", xuất hiện dày đặc trong thể bị
# động ("đã được cấp Giấy phép") nên không phân biệt được quyền với mô tả.
_DEONTIC_GROUPS = {"nghia_vu", "cam"}

# "(sau đây gọi là khách hàng)" · "(sau đây viết tắt là TCPHT)" · "(gọi chung là X)".
# Đo trên 11 văn bản corpus: 73 lần, văn bản nào cũng có ít nhất 1 ⇒ đáng trích tất
# định. Đây là bí danh do CHÍNH văn bản tuyên bố, hỏi LLM là thừa và rủi ro.
_ALIAS_RE = re.compile(
    r"\((?:sau\s+đây\s+)?(?:được\s+)?(?:gọi|viết)\s+(?:chung\s+|tắt\s+)*là\s+([^)]{1,80})\)",
    re.I,
)

# Bẫy "phải" — gặp thật khi chạy classifier trên corpus, 6/94 đơn vị bị gán nhầm:
#   "tổ chức KHÔNG PHẢI LÀ ngân hàng"  → hệ từ phủ định (ND52 Đ3 k5, TT40 Đ3 k13)
#   "số tiền PHẢI THU, PHẢI TRẢ"       → danh ngữ kế toán (ND52 Đ3 k15, TT40 Đ3 k7/k9)
# Che TRƯỚC khi dò, và CHỈ ở tầng phân loại này. `modality.py` cố ý giữ nguyên độ
# nhạy: ở đó bắt nhầm chỉ tốn một cảnh báo, còn bỏ sót là lọt một nghĩa vụ bịa ra.
_BAY_PHAI = [
    re.compile(r"không\s+phải\s+là", re.I),
    re.compile(
        r"(?:tiền|khoản|chênh\s+lệch|công\s+nợ|số)\b[^.;]{0,25}?"
        r"phải\s+(?:thu|trả|nộp)(?:\s*,\s*phải\s+(?:thu|trả|nộp))*",
        re.I,
    ),
]

# Mệnh đề hiệu lực thời gian. Luật thật viết "từ ngày", không phải "kể từ ngày"
# (ND52 Điều 37 khoản 1) — bắt cả hai, đừng gán chết một biến thể.
#
# Nhóm `ngay` là TUỲ CHỌN vì có mệnh đề hiệu lực không mang ngày tuyệt đối nào:
# TT40 Điều 52 khoản 6 viết *"…hết hiệu lực kể từ ngày Thông tư này có hiệu lực thi
# hành"* — mốc nêu bằng viện dẫn tương đối. Đó là "không có ngày", khác hẳn "có ngày
# mà đọc hỏng", nên phải phân biệt được chứ không cùng rơi về None không lời giải thích.
_HIEU_LUC_RE = re.compile(
    r"(?P<dong_tu>có|hết)\s+hiệu\s+lực(\s+thi\s+hành)?\s*"
    r"(?P<gioi_tu>đến\s+hết|kể\s+từ|từ|vào)?\s*ngày"
    r"(?P<ngay>\s*(?P<d>\d{1,2})\s*tháng\s*(?P<m>\d{1,2})\s*năm\s*(?P<y>\d{4}))?",
    re.I,
)
_THAY_THE_RE = re.compile(
    r"(thay\s+thế\s+cho|bãi\s+bỏ)\s+(Nghị\s+định|Thông\s+tư|Quyết\s+định|Điều)", re.I
)
# "…từ ngày X, TRỪ TRƯỜNG HỢP quy định tại khoản 2…": viện dẫn sau chữ này là NGOẠI
# LỆ của cổng, không phải phạm vi cổng phủ. Trộn hai thứ là đảo ngược ngữ nghĩa.
_TRU_RE = re.compile(r"trừ\s+(?:trường\s+hợp|quy\s+định|các\s+quy\s+định)", re.I)

# "Nghị định này áp dụng đối với…" · "Quy định tại Mục này chỉ áp dụng đối với…" ·
# "Quy định tại khoản 1 Điều này KHÔNG áp dụng đối với…" (TT40 Đ26 k2 — có thật).
_AP_DUNG_RE = re.compile(
    r"(?P<truoc>(?:Quy\s+định\s+tại\s+)?[^.;:]{0,60}?"
    r"(?P<cap>Nghị\s+định|Thông\s+tư|Quyết\s+định|Chương|Mục|Điều|Khoản)\s+này)"
    r"(?P<giua>[^.;:]{0,40}?)\s*áp\s+dụng\s+(?:đối\s+với|cho)",
    re.I,
)
_CAP_MAP = {
    "nghị định": "van_ban", "thông tư": "van_ban", "quyết định": "van_ban",
    "chương": "chuong", "mục": "muc", "điều": "dieu", "khoản": "khoan",
}
# Cấp có node tương ứng trong parser ⇒ quy được về khoá node. Chương/Mục thì không:
# cây chỉ có Điều→Khoản→Điểm. Không được im lặng trả [] ở hai cấp đó.
_CAP_CO_NODE = {"van_ban", "dieu", "khoan"}


class UnitCtx(BaseModel):
    """`position_context` — đơn vị đang xét nằm ở đâu trong văn bản."""

    dieu_id: str = ""
    dieu_so: int = 0
    dieu_hau_to: int = 0
    dieu_so_hien_thi: str = ""  # "22", "15a" — cần cho viện dẫn nội bộ "Điều này"
    dieu_tieu_de: str = ""
    khoan_so: str | None = None  # None = đang xét cả Điều
    cap: Literal["dieu", "khoan", "diem"] = "khoan"
    # HIỆN KHÔNG ĐƯỢC DÙNG ở tầng này, và đó là chủ ý: `classify_unit` chỉ đọc luật
    # TIÊU ĐỀ, vốn không đổi ở văn bản sửa đổi. Cờ này chỉ chi phối luật VỊ TRÍ
    # (Điều 1 = phạm vi, Điều 2 = đối tượng áp dụng) của `roles.classify_dieu`.
    # Giữ trong ngữ cảnh để bên gọi truyền một lần dùng cho cả hai tầng.
    van_ban_sua_doi: bool = False


class UnitVerdict(BaseModel):
    type: UnitType
    rationale: str
    test_path: list[str] = Field(default_factory=list)
    premise_kind: PremiseKind | None = None  # chỉ khi type == "premise"
    gates: list[Gate] = Field(default_factory=list)  # chỉ khi type == "meta_cu"
    # Chỉ khi type == "meta_cu" và cổng thuộc loại `thoi_gian`. `char_span` bên trong
    # được `classify_khoan` quy về `dieu.text` y như `alias_span`.
    dieu_kien_cong: DieuKienCong | None = None
    alias: str | None = None
    alias_span: tuple[int, int] | None = None  # tương đối với `text` truyền vào
    warnings: list[str] = Field(default_factory=list)


def find_alias(text: str) -> tuple[str, tuple[int, int]] | None:
    """Bí danh do văn bản tự tuyên bố → (bí danh, span trong `text`)."""
    m = _ALIAS_RE.search(text)
    if not m:
        return None
    return m.group(1).strip(), (m.start(1), m.start(1) + len(m.group(1).strip()))


def deontic_groups(text: str) -> set[str]:
    """Nhóm tình thái có mặt trong đoạn, đã che các bẫy "phải" phi-deontic."""
    for bay in _BAY_PHAI:
        text = bay.sub(lambda m: " " * len(m.group()), text)
    return groups_in(text)


def _so_hieu(ctx: UnitCtx) -> str:
    return ctx.dieu_id.split("#", 1)[0] if ctx.dieu_id else ""


def _chia_refs(doan: str, so_hieu: str):
    """Viện dẫn trong đoạn → (nội bộ, trỏ ra văn bản khác)."""
    refs = parse_citations(doan)
    ngoai = [r for r in refs if r.van_ban and r.van_ban != so_hieu]
    return [r for r in refs if r not in ngoai], ngoai


def _mo_ho(ref) -> str:
    """Viện dẫn có quy được về đúng một đích không? Trả lý do nếu KHÔNG.

    Hai hình thái đã gặp thật trong điều "Hiệu lực thi hành" của TT40 mà văn phạm
    của `citation.py` chưa đọc đúng — bắt ở đây thay vì phát ra khoá sai:

    - **Điều nằm ở cuối, dùng chung cho nhiều khoản**: "điểm c, điểm đ khoản 1,
      điểm b, điểm d khoản 2 Điều 25" — cụm đầu không nêu Điều, rơi về `ctx_dieu`
      là chính Điều 52, tức trỏ nhầm sang điều khác hẳn.
    - **Khoản phân phối lên danh sách nhiều Điều**: "khoản 2 Điều 17, Điều 18,
      Điều 19…" — cách đọc đúng là khoản 2 CHỈ của Điều 17, phần còn lại là cả điều.
    """
    if (ref.khoan or ref.diem) and not ref.dieu and not ref.dieu_self:
        return "nêu khoản/điểm nhưng không nêu Điều (Điều nằm ở cuối chuỗi viện dẫn)"
    if (ref.khoan or ref.diem) and len(ref.dieu) > 1:
        return "một khoản/điểm gắn với nhiều Điều — cách phân phối không xác định"
    return ""


def _node_ids(refs, ctx: UnitCtx) -> tuple[list[str], list[str]]:
    """→ (khoá node chắc chắn, mô tả các viện dẫn phải bỏ vì mơ hồ).

    Thà bỏ sót đích còn hơn phát ra khoá sai — cùng nguyên tắc `to_node_ids` đã
    theo khi trả rỗng cho "khoản này" thiếu ngữ cảnh.
    """
    out: list[str] = []
    bo_qua: list[str] = []
    for r in refs:
        ly_do = _mo_ho(r)
        if ly_do:
            bo_qua.append(f"{r.raw!r}: {ly_do}")
            continue
        out += to_node_ids(
            r, _so_hieu(ctx),
            ctx_dieu=ctx.dieu_so_hien_thi or None,
            ctx_khoan=ctx.khoan_so,
        )
    return list(dict.fromkeys(out)), bo_qua


def detect_dieu_kien_cong(text: str) -> DieuKienCong | None:
    """Mệnh đề hiệu lực → Θ có cấu trúc. TẤT ĐỊNH, không gọi LLM một chữ nào.

    Chạy cùng `_HIEU_LUC_RE` mà `detect_gate` dùng, nên nó 1:1 với cổng `thoi_gian`
    do `detect_gate` phát ra. Tách thành hàm riêng chứ không đổi kiểu trả về của
    `detect_gate`: mỗi hàm một việc, và `detect_gate` là API đã có test gọi thẳng.

    `char_span` = đúng span của cụm đã khớp, tính bằng regex của TA trên chính chuỗi
    truyền vào. Đây là lý do mốc ngày không thể "lan sang phần câu khác": nó không đi
    qua tay mô hình lần nào.
    """
    m = _HIEU_LUC_RE.search(text)
    if not m:
        return None

    gioi_tu = re.sub(r"\s+", " ", (m.group("gioi_tu") or "")).strip().lower()
    # "hết hiệu lực…" và "có hiệu lực… ĐẾN HẾT ngày…" đều là mốc KẾT THÚC.
    moc = "ket_thuc" if m.group("dong_tu").lower() == "hết" or gioi_tu.startswith("đến") else "bat_dau"

    ngay: str | None = None
    if not m.group("ngay"):
        ghi_chu = ("mốc nêu bằng viện dẫn tương đối — không có ngày tuyệt đối trong "
                   "đơn vị này")
    else:
        try:
            ngay = date(int(m.group("y")), int(m.group("m")), int(m.group("d"))).isoformat()
            ghi_chu = ""
        except ValueError:
            # Ngày/tháng ngoài phạm vi. Đây LÀ khiếm khuyết (khác hẳn hai case trên),
            # nên nói khác đi để bên gọi phân biệt được mà cảnh báo.
            ngay = None
            ghi_chu = (f"có cụm ngày {m.group('ngay').strip()!r} nhưng không hợp lệ — "
                       "cần người đọc soi lại")

    return DieuKienCong(
        kind="thoi_gian", ngay=ngay, moc=moc,  # type: ignore[arg-type]
        raw_text=m.group(0), char_span=(m.start(), m.end()), ghi_chu=ghi_chu,
    )


def detect_gate(text: str, ctx: UnitCtx) -> Gate | None:
    """Đơn vị có phát biểu một mệnh đề CHẶN CỔNG không? Tất định, không gọi LLM."""
    so_hieu = _so_hieu(ctx)

    m = _HIEU_LUC_RE.search(text)
    if m:
        # Phạm vi phủ nằm ở phần TRƯỚC mệnh đề hiệu lực: "Quy định tại Điều 11,
        # Điều 12… Thông tư này có hiệu lực từ ngày…". TT40 Điều 52 có 4 khoản kiểu
        # này — gán tất cả thành "cả văn bản" là sai phạm vi gấp nhiều lần.
        noi, ngoai = _chia_refs(text[: m.start()], so_hieu)
        if ngoai:
            # Điều khoản bãi bỏ văn bản khác: viện dẫn "Điều 2" trong đó thuộc VĂN
            # BẢN KIA, giải bằng số hiệu của văn bản này sẽ ra khoá sai mà không ai
            # biết. Bỏ luôn cả `ngoai_tru` — cùng lý do.
            return Gate(kind="thoi_gian", pham_vi="van_ban", targets=[], suy_ra_duoc=False,
                        ghi_chu=f"đơn vị nhắc tới văn bản khác ({ngoai[0].van_ban}) — "
                                "không quy được viện dẫn về cây node của văn bản này")
        tru = _TRU_RE.search(text)
        ngoai_tru, bo_tru = (
            _node_ids(_chia_refs(text[tru.end() :], so_hieu)[0], ctx) if tru else ([], [])
        )
        targets, bo_qua = _node_ids(noi, ctx)
        bo_qua += bo_tru
        if targets:
            cap = "khoan" if all(r.khoan or r.khoan_self for r in noi) else "dieu"
            return Gate(kind="thoi_gian", pham_vi=cap, targets=targets,  # type: ignore[arg-type]
                        suy_ra_duoc=not bo_qua, ngoai_tru=ngoai_tru,
                        ghi_chu="mốc hiệu lực riêng cho các đơn vị được nêu"
                                + (f"; bỏ viện dẫn mơ hồ — {'; '.join(bo_qua)}" if bo_qua else ""))
        if noi:
            # Có viện dẫn phạm vi nhưng không giải được cái nào ⇒ KHÔNG được tụt về
            # "cả văn bản": đó là mở rộng phạm vi hiệu lực gấp nhiều lần, im lặng.
            return Gate(kind="thoi_gian", pham_vi="van_ban", targets=[], suy_ra_duoc=False,
                        ngoai_tru=ngoai_tru,
                        ghi_chu="mệnh đề nêu phạm vi bằng viện dẫn nhưng không giải được: "
                                + "; ".join(bo_qua))
        return Gate(kind="thoi_gian", pham_vi="van_ban", targets=[], suy_ra_duoc=True,
                    ngoai_tru=ngoai_tru,
                    ghi_chu="mốc hiệu lực của cả văn bản"
                            + (f"; ngoại lệ chưa giải được — {'; '.join(bo_tru)}" if bo_tru else ""))

    if _THAY_THE_RE.search(text):
        # Phủ định hiệu lực của VĂN BẢN KHÁC. Vẫn là cổng thời gian, nhưng đích nằm
        # ngoài cây node của văn bản này ⇒ không được khai là đã suy ra được.
        return Gate(kind="thoi_gian", pham_vi="van_ban", targets=[], suy_ra_duoc=False,
                    ghi_chu="thay thế/bãi bỏ văn bản khác — đích nằm ngoài cây node hiện tại")

    m = _AP_DUNG_RE.search(text)
    if m:
        # Cực của cổng. "Quy định tại khoản 1 Điều này KHÔNG áp dụng đối với…" là
        # loại trừ, không phải trao phạm vi — đọc nhầm cực là đảo ngược hiệu lực.
        phu_dinh = bool(re.search(r"(?<![\wÀ-ỹ])không(?![\wÀ-ỹ])", m.group("giua"), re.I))
        # Đích lấy từ viện dẫn nếu có ("khoản 1 Điều này" chính xác hơn chữ "Điều").
        noi, ngoai = _chia_refs(m.group("truoc"), so_hieu)
        targets, bo_qua = _node_ids(noi, ctx) if not ngoai else ([], [])
        if targets:
            cap = "khoan" if all(r.khoan or r.khoan_self for r in noi) else "dieu"
            return Gate(kind="chu_the", pham_vi=cap, targets=targets,  # type: ignore[arg-type]
                        suy_ra_duoc=not bo_qua, phu_dinh=phu_dinh,
                        ghi_chu="phạm vi lấy từ viện dẫn trong chính mệnh đề"
                                + (f"; bỏ viện dẫn mơ hồ — {'; '.join(bo_qua)}" if bo_qua else ""))
        cap = _CAP_MAP[m.group("cap").lower().replace("\xa0", " ")]
        if cap == "dieu" and ctx.dieu_id:
            targets = [ctx.dieu_id]
        elif cap == "khoan" and ctx.dieu_id and ctx.khoan_so:
            targets = [f"{ctx.dieu_id}#khoan_{ctx.khoan_so}"]
        ghi_chu = ""
        if cap not in _CAP_CO_NODE:
            ghi_chu = (
                f"phạm vi {m.group('cap')!r} không có node tương ứng trong parser "
                "(cây chỉ có Điều→Khoản→Điểm) — chưa quy được về khoá node"
            )
        return Gate(kind="chu_the", pham_vi=cap, targets=targets,  # type: ignore[arg-type]
                    suy_ra_duoc=cap in _CAP_CO_NODE, phu_dinh=phu_dinh, ghi_chu=ghi_chu)
    return None


def classify_unit(text: str, ctx: UnitCtx) -> UnitVerdict:
    """Một đơn vị văn bản → premise · meta_cu · actor_cu, kèm đường đi đã dùng."""
    path: list[str] = []
    warnings: list[str] = []
    rule = title_rule(ctx.dieu_tieu_de)
    title_role = rule[0] if rule else None
    groups = deontic_groups(text)
    co_nghia_vu = bool(groups & _DEONTIC_GROUPS)
    gate = detect_gate(text, ctx)
    alias = find_alias(text)

    def out(t: UnitType, why: str, **kw) -> UnitVerdict:
        return UnitVerdict(
            type=t, rationale=why, test_path=path,
            alias=alias[0] if alias else None,
            alias_span=alias[1] if alias else None,
            warnings=warnings, **kw,
        )

    # --- Test A: đơn vị có cặp chủ thể + hành vi tại chỗ không? ----------------
    if gate is not None:
        # Vị ngữ của đơn vị là "áp dụng"/"có hiệu lực" — nói về PHẠM VI của quy định
        # chứ không phải hành vi của một chủ thể. Phải xét trước dấu hiệu tình thái:
        # "tổ chức đã ĐƯỢC cấp Giấy phép" có chữ "được" nhưng đó là bị động, không
        # phải trao quyền.
        path.append("A: vị ngữ là mệnh đề phạm vi/hiệu lực, không phải hành vi → B")
    elif title_role in {"premise", "meta_cu"}:
        path.append(
            f"A: đứng riêng dưới tiêu đề {ctx.dieu_tieu_de!r} (luật tiêu đề → {title_role}) → B"
        )
    elif co_nghia_vu:
        path.append(
            "A: có dấu hiệu nghĩa vụ/cấm đoán cùng đơn vị "
            f"({', '.join(sorted(groups & _DEONTIC_GROUPS))}) → actor_cu"
        )
        return out("actor_cu", "hành vi bắt buộc/cấm đoán nằm cùng đơn vị với chủ thể")
    else:
        path.append("A: không khớp khuôn phi-deontic nào và không có dấu hiệu chặn cổng → actor_cu")
        return out(
            "actor_cu",
            "mặc định — không có tín hiệu nào cho thấy đây là premise hay meta-CU",
        )

    # --- Test B: có thể bị vi phạm độc lập không? -----------------------------
    if co_nghia_vu and gate is None:
        if title_role == "premise":
            # Không lật nhãn. Luật tiêu đề đã ĐO được (40/278 điều, và 9/11 · 8/11
            # theo vị trí); từ điển tình thái là phép xấp xỉ có bẫy đã biết. Khi hai
            # tín hiệu cãi nhau ở một điều "Giải thích từ ngữ", tin cái đã đo và
            # NÊU RA mâu thuẫn — im lặng lật thành nghĩa vụ là biến một định nghĩa
            # thành quy phạm bị phán định.
            warnings.append(
                f"đơn vị có dấu hiệu {', '.join(sorted(groups & _DEONTIC_GROUPS))} "
                f"nhưng nằm trong điều {ctx.dieu_tieu_de!r} — giữ premise theo tiêu đề, "
                "cần người đọc soi lại"
            )
        else:
            # Điều "Trách nhiệm thi hành" nằm trong nhánh này: tiêu đề nghe như meta
            # nhưng nội dung giao nghĩa vụ thật cho cơ quan cụ thể.
            path.append("B: có, đơn vị đặt ra nghĩa vụ cụ thể → actor_cu")
            return out("actor_cu",
                       "tiêu đề mang dáng meta nhưng nội dung giao nghĩa vụ cho chủ thể")

    if gate is not None:
        path.append("B: không tự bị vi phạm, nhưng chặn cổng quy định khác → C")
        # --- Test C: phạm vi ảnh hưởng ---------------------------------------
        if not gate.suy_ra_duoc:
            warnings.append(f"phạm vi cổng chưa quy được về khoá node: {gate.ghi_chu}")
        path.append(f"C: phủ cấp {gate.pham_vi!r} ({gate.kind}) → meta_cu")
        # Θ có cấu trúc chỉ gắn cho cổng thời gian, và chỉ khi đơn vị ĐÃ được kết luận
        # là meta-CU — một actor-CU có nhắc chữ "hiệu lực" không được mọc ra mốc ngày.
        dkc = detect_dieu_kien_cong(text) if gate.kind == "thoi_gian" else None
        return out("meta_cu", f"mệnh đề chặn cổng {gate.kind}, phủ cấp {gate.pham_vi}",
                   gates=[gate], dieu_kien_cong=dkc)

    # Không có mệnh đề chặn cổng nào trong CHÍNH đơn vị này.
    path.append("B: không tự bị vi phạm, bản thân đơn vị không phát biểu cổng nào → premise")

    if title_role == "premise":
        kind = rule[2] if rule and rule[2] else "pham_vi"
        path.append(f"C: không chặn gì, chỉ hỗ trợ diễn giải → premise/{kind}")
        return out("premise", rule[1] if rule else "chất liệu phi-deontic",
                   premise_kind=kind)  # type: ignore[arg-type]

    # Ở đây title_role == "meta_cu" — tiêu đề kiểu "Đối tượng áp dụng"/"Hiệu lực thi
    # hành" nhưng đơn vị KHÔNG chứa mệnh đề cổng nào. Xem docs/ONTOLOGY-CLASSIFY.md §2:
    # từng khoản của "Đối tượng áp dụng" chỉ là một danh ngữ ("Tổ chức cung ứng dịch
    # vụ trung gian thanh toán."), không có vị ngữ để mà vi phạm hay để mà chặn.
    # Mệnh đề cổng nằm ở TIÊU ĐỀ + phép liệt kê, tức ở mức ĐIỀU.
    if ctx.cap == "dieu":
        g = Gate(kind="chu_the", pham_vi="van_ban", targets=[], suy_ra_duoc=True,
                 ghi_chu=f"cổng chủ thể phát biểu qua tiêu đề {ctx.dieu_tieu_de!r} + phép liệt kê")
        path.append("C: cả Điều gộp lại chặn cổng chủ thể cho toàn văn bản → meta_cu")
        return out("meta_cu", "tiêu đề + phép liệt kê hợp thành cổng chủ thể mức văn bản",
                   gates=[g])

    path.append("C: chỉ khai báo một vai chủ thể, không tự chặn gì → premise/vai_tro")
    return out(
        "premise",
        "khai báo vai trò chủ thể — danh ngữ trần, không có vị ngữ để vi phạm hay chặn cổng",
        premise_kind="vai_tro",
    )


def classify_khoan(
    khoan: KhoanNode, dieu: DieuNode, *, van_ban_sua_doi: bool = False
) -> UnitVerdict:
    """Bọc `classify_unit` cho một Khoản đã parse — offset alias đưa về `dieu.text`."""
    ctx = UnitCtx(
        dieu_id=dieu.id,
        dieu_so=dieu.so_goc,
        dieu_hau_to=dieu.so_hau_to,
        dieu_tieu_de=dieu.tieu_de,
        khoan_so=khoan.so_hien_thi or None,
        cap="khoan" if khoan.so_hien_thi else "dieu",
        van_ban_sua_doi=van_ban_sua_doi,
    )
    ctx.dieu_so_hien_thi = dieu.so_hien_thi
    v = classify_unit(khoan.text, ctx)
    # `khoan.text` là lát cắt của `dieu.text` tại `khoan.start` — MỌI span phải quy về
    # một gốc duy nhất, nếu không char_span của registry sẽ lệch trong im lặng.
    if v.alias_span:
        v.alias_span = (v.alias_span[0] + khoan.start, v.alias_span[1] + khoan.start)
    if v.dieu_kien_cong and v.dieu_kien_cong.char_span:
        a, b = v.dieu_kien_cong.char_span
        v.dieu_kien_cong.char_span = (a + khoan.start, b + khoan.start)
    return v


def classify_dieu_unit(dieu: DieuNode, *, van_ban_sua_doi: bool = False) -> UnitVerdict:
    """Phân loại cả Điều như một đơn vị (dùng cho cổng mức Điều, ví dụ Đối tượng áp dụng)."""
    return classify_unit(
        dieu.text,
        UnitCtx(dieu_id=dieu.id, dieu_so=dieu.so_goc, dieu_hau_to=dieu.so_hau_to,
                dieu_so_hien_thi=dieu.so_hien_thi, dieu_tieu_de=dieu.tieu_de,
                khoan_so=None, cap="dieu", van_ban_sua_doi=van_ban_sua_doi),
    )


__all__ = [
    "DieuKienCong",
    "Gate",
    "UnitCtx",
    "UnitVerdict",
    "classify_dieu_unit",
    "classify_khoan",
    "classify_unit",
    "detect_dieu_kien_cong",
    "detect_gate",
    "find_alias",
]
