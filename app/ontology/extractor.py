"""Trích Compliance Unit mức Khoản — 3 tầng chống bịa.

1. **Menu span (ngăn từ gốc)** — LLM chọn ID đơn vị trong một tập đóng do ta tách,
   không tự khai offset và không tự chép chuỗi. `char_span` do ta tính ⇒ bịa
   provenance là bất khả thi.
2. **Modality guard (tất định)** — mọi diễn giải của mô hình phải có tập dấu hiệu
   tình thái là tập con của đoạn luật đã neo. Thêm "phải"/"không được"/số liệu ⇒
   lỗi cứng. Đây là tầng bắt lỗi thật đã gặp ở giai đoạn 1 ("khi" → "phải").
3. **Diff (chỉ đích danh)** — khi lệch, in `khi → phải` thay vì báo chung chung.

Điểm khác căn bản so với giai đoạn 1: `subject`/`action`/`constraint` KHÔNG còn là
chữ LLM viết. Chúng là lát cắt `dieu.text[start:end]` — chữ của luật. Diễn giải của
mô hình nằm riêng ở `label`, và phải qua được modality guard.
"""
from __future__ import annotations

import json
from collections import Counter

from app.core.llm import chat_json
from app.ontology.citation import parse_citations, to_node_ids
from app.ontology.modality import (
    explain,
    modality_delta,
    relax_absence,
    relax_dereference,
)
from app.ontology.parser import tiet_logic
from app.ontology.schema import (
    ActorCU,
    ComplianceUnit,
    ConditionItem,
    DieuKienCong,
    DieuNode,
    Gate,
    GroundedField,
    Grounding,
    KhaiNiem,
    KhoanNode,
    MetaCU,
    PremiseRecord,
    SubCondition,
    Unit,
)
from app.ontology.segmenter import hull, render_menu, segment

_SYSTEM = (
    "Bạn là chuyên gia phân tích văn bản quy phạm pháp luật Việt Nam. Bạn nhận một "
    "KHOẢN đã được tách sẵn thành các ĐƠN VỊ ĐÁNH SỐ và phải phân rã thành một "
    "Compliance Unit bằng cách CHỌN SỐ HIỆU ĐƠN VỊ.\n\n"
    "NGUYÊN TẮC BẮT BUỘC:\n"
    "1. Đơn vị phân tích là cả Khoản, KHÔNG phải từng Điểm. Câu bao trùm (chapeau) "
    "mang Subject và Action chung; mỗi Điểm con là mệnh đề tiếp nối đã lược bỏ chủ "
    "ngữ, trở thành một phần tử trong 'conditions'. TUYỆT ĐỐI không tự suy ra chủ "
    "ngữ riêng cho từng Điểm.\n"
    "2. Chapeau có thể KHÔNG nằm trên đơn vị đầu tiên. Đọc hết các đơn vị để tìm câu "
    "có chủ ngữ và động từ chính.\n"
    "3. Mọi trường đều phải chỉ ra 'units' — danh sách số hiệu đơn vị chứa căn cứ. "
    "Chỉ được dùng số hiệu CÓ THẬT trong danh sách. Đơn vị [0] là tiêu đề Điều: chỉ "
    "dùng cho subject khi Khoản không tự nêu chủ ngữ (khi đó source='inherited').\n"
    "4. 'quote' là TUỲ CHỌN, dùng để thu hẹp vào một cụm nhỏ hơn bên trong các đơn vị "
    "đã chọn. Nếu có, phải CHÉP NGUYÊN VĂN, không sửa một ký tự. Không chắc thì bỏ "
    "trống — bỏ trống không bị phạt, chép sai thì bị.\n"
    "5. 'label' là diễn giải ngắn của bạn. TUYỆT ĐỐI không thêm từ chỉ nghĩa vụ "
    "('phải', 'có trách nhiệm') hay cấm đoán ('không được') nếu văn bản gốc không có, "
    "và không đổi/thêm con số. Máy sẽ đối chiếu tự động và loại bỏ bản ghi vi phạm.\n"
    "6. 'logic' = 'all' nếu phải thoả mọi điều kiện (dấu hiệu: 'đáp ứng đầy đủ', "
    "'các điều kiện sau đây'), 'any' nếu chỉ cần một, 'unknown' nếu không rõ.\n"
    "Chỉ trả JSON, không giải thích."
)

_SCHEMA_HINT = """Trả đúng cấu trúc JSON sau:
{
  "subject": {"units": [2], "quote": "", "label": "<chủ thể chịu điều chỉnh>", "source": "explicit|inherited"},
  "action":  {"units": [2], "quote": "", "label": "<hành vi/nghĩa vụ chính>"},
  "logic": "all|any|unknown",
  "conditions": [
    {"source_diem": "a", "units": [3, 4], "quote": "", "object_label": "<đối tượng bị ràng buộc>", "constraint_label": "<nội dung ràng buộc>"}
  ]
}"""


def resolve(raw: dict, units: list[Unit], dieu_text: str) -> Grounding:
    """Chọn-đơn-vị → span. Không gọi LLM, không dò mờ.

    Bao lồi các đơn vị luôn hợp lệ (do ta tách), nên provenance không bao giờ mất
    trừ khi LLM trả uid không tồn tại. `quote` chỉ thu hẹp span BÊN TRONG bao lồi.
    """
    uids = [u for u in (raw.get("units") or []) if isinstance(u, int)]
    span = hull(units, uids)
    if span is None:
        return Grounding(units=uids, char_span=None, status="invalid",
                         quote=(raw.get("quote") or "").strip())

    quote = (raw.get("quote") or "").strip()
    if quote:
        pos = dieu_text.find(quote, span[0], span[1])
        if pos >= 0:
            return Grounding(units=uids, char_span=(pos, pos + len(quote)),
                             status="exact", quote=quote)
    return Grounding(units=uids, char_span=span, status="unit", quote=quote)


def _evidence(units: list[Unit], g: Grounding, dieu_text: str) -> str:
    """Toàn bộ bằng chứng mô hình đã trích dẫn = bao lồi các ĐƠN VỊ nó chọn.

    Khác `text` của trường: `text` là lát cắt sau khi `quote` đã thu hẹp. Hai thứ chỉ
    lệch nhau khi mô hình có dùng `quote` — và đúng chỗ lệch đó là nơi guard từng kết
    tội nhầm (xem `modality.relax_absence`).
    """
    span = hull(units, g.units)
    return dieu_text[span[0] : span[1]] if span else ""


def _check(
    label: str,
    source: str,
    where: str,
    evidence: str | None = None,
    ctx: tuple[int, int] | None = None,
) -> tuple[list[str], list[str]]:
    """Đối chiếu diễn giải với chữ của luật → (lỗi cứng, cảnh báo).

    `source` là lát cắt hẹp (sau `quote`); `evidence` là bao lồi các đơn vị đã chọn;
    `ctx` là `(số Điều, số Khoản)` đang xét.

    Hai phép nới, cả hai chỉ chạy khi ĐÃ có lỗi cứng và cả hai đều để lại cảnh báo nêu
    đích danh — không có phép nới nào diễn ra trong im lặng:

    1. `relax_dereference` — số bị tố cáo chỉ là mô hình khai triển `"Điều này"`;
    2. `relax_absence` — cáo buộc VẮNG MẶT phải kiểm trên toàn bộ bằng chứng đã trích
       dẫn, vì nhãn mô tả chữ nằm trong đó thì không phải bịa mà là `quote` thu hẹp
       sai chỗ.
    """
    if not label.strip():
        return [], []
    delta = modality_delta(label, source)
    notes: list[str] = []
    if delta.hard_error and ctx is not None:
        delta, n = relax_dereference(
            delta, label, source, so_dieu=ctx[0], so_khoan=ctx[1]
        )
        notes += n
    if delta.hard_error and evidence is not None and evidence != source:
        delta, n = relax_absence(delta, label, evidence)
        notes += n
    msgs = delta.describe()
    if delta.hard_error:
        return [f"{where}: {'; '.join(msgs)} | {explain(label, source)}"], [
            f"{where}: {n}" for n in notes
        ]
    return [], [f"{where}: {m}" for m in msgs + notes]


def _field(
    raw: dict,
    units: list[Unit],
    dieu_text: str,
    where: str,
    ctx: tuple[int, int] | None = None,
) -> tuple[GroundedField, list[str], list[str]]:
    g = resolve(raw, units, dieu_text)
    text = dieu_text[g.char_span[0] : g.char_span[1]] if g.char_span else ""
    label = (raw.get("label") or "").strip()
    errors, warnings = ([], [])
    if g.status == "invalid":
        errors.append(f"{where}: đơn vị {g.units} không tồn tại — mất provenance")
    else:
        if g.status == "unit" and g.quote:
            warnings.append(
                f"{where}: quote không nằm trong đơn vị đã chọn, lùi về span đơn vị | "
                f"{explain(g.quote, text)}"
            )
        e, w = _check(
            label, text, where, evidence=_evidence(units, g, dieu_text), ctx=ctx
        )
        errors += e
        warnings += w
    field = GroundedField(text=text, label=label, grounding=g, issues=errors + warnings)
    return field, errors, warnings


# Nhóm cổng KHÔNG có bên bị ràng buộc. `chu_the` cố ý không nằm đây: role
# qualification có một vai cần định danh nên `subject` vẫn bắt buộc.
_GATE_KHONG_CO_ACTOR = {"thoi_gian", "lanh_tho"}

_SUBJECT_KHONG_AP_DUNG = (
    "\nLƯU Ý RIÊNG CHO KHOẢN NÀY: đây là mệnh đề nêu PHẠM VI/HIỆU LỰC của quy định, "
    "không ràng buộc bất kỳ chủ thể nào. Chủ ngữ ngữ pháp ('Nghị định này', 'Thông tư "
    "này') KHÔNG phải là bên bị ràng buộc. Hãy trả 'subject': {\"units\": []} và bỏ "
    "trống 'source'. TUYỆT ĐỐI không chọn bừa một đơn vị cho subject.\n"
)


_CONDITIONS_KHONG_AP_DUNG = (
    "\nLƯU Ý RIÊNG CHO KHOẢN NÀY: khoản này KHÔNG có Điểm con, và mốc hiệu lực của nó "
    "đã được máy tách sẵn bằng luật, không cần bạn trích. Mệnh đề hiệu lực không đặt ra "
    "'điều kiện' theo nghĩa nghĩa vụ. Hãy trả \"conditions\": []. TUYỆT ĐỐI không chẻ "
    "câu thành hai nửa rồi neo vào nửa này mà gắn nhãn bằng nửa kia.\n"
)


def subject_khong_ap_dung(role: str, gates: list[Gate] | None) -> bool:
    """⟨S⟩ có phải là "không áp dụng" ở đơn vị này không?

    Đúng khi và chỉ khi là meta-CU mà MỌI cổng đều thuộc nhóm không có tác nhân.
    Đòi `gates` không rỗng: một meta-CU chưa xác định được cổng thì cũng chưa có căn
    cứ nào để miễn `subject` — miễn ở đó là để lọt trích hỏng dưới vỏ "không áp dụng".
    """
    return (
        role == "meta_cu"
        and bool(gates)
        and all(g.kind in _GATE_KHONG_CO_ACTOR for g in gates)
    )


def conditions_khong_ap_dung(
    role: str, gates: list[Gate] | None, khoan: KhoanNode
) -> bool:
    """`conditions[]` có phải là "không áp dụng" ở đơn vị này không?

    Cùng lập luận với `subject_khong_ap_dung`, cộng thêm MỘT vế bắt buộc: **Khoản
    không chẻ Điểm**. TT40 Điều 52 khoản 6 cũng là cổng thời gian nhưng CÓ điểm a/b
    mang mốc hết hiệu lực riêng cho từng quy định của Thông tư 39/2014 — xoá chúng là
    mất thông tin thật, không phải dọn ô trống.

    Chỗ này KHÔNG dùng phép "char_span phải liên tục" như bản đề xuất ban đầu: `resolve()`
    trả bao lồi của các đơn vị đã chọn nên span luôn liền mạch **theo cấu trúc**, luật
    đó sẽ không bao giờ bắn và chỉ tạo cảm giác an toàn giả. Lỗi thật có hình dạng khác:
    span đúng và liền, còn *nhãn* mô tả chữ nằm NGOÀI span (TT40 Đ52 k3/k4/k5 — neo vào
    nửa câu phạm vi rồi gắn nhãn bằng nửa câu ngày). Chặn bằng cấu trúc, không bằng
    một phép đo hình học của span.
    """
    return subject_khong_ap_dung(role, gates) and not khoan.diem


def build_prompt(
    khoan: KhoanNode,
    dieu: DieuNode,
    units: list[Unit],
    role: str = "actor_cu",
    gates: list[Gate] | None = None,
) -> str:
    return (
        f"Văn bản: {dieu.id.split('#')[0]}\n"
        f"Điều {dieu.so_hien_thi}. {dieu.tieu_de}\n\n"
        f"--- CÁC ĐƠN VỊ CỦA KHOẢN {khoan.so_hien_thi} ---\n"
        f"{render_menu(units)}\n"
        f"--- HẾT ---\n"
        + (_SUBJECT_KHONG_AP_DUNG if subject_khong_ap_dung(role, gates) else "")
        + (
            _CONDITIONS_KHONG_AP_DUNG
            if conditions_khong_ap_dung(role, gates, khoan)
            else ""
        )
        + f"\n{_SCHEMA_HINT}"
    )


def _resolve_references(khoan: KhoanNode, dieu: DieuNode) -> tuple[list[str], bool]:
    """Viện dẫn trong Khoản → khoá node đích. Tất định, không gọi LLM.

    `citation.py` đã có từ trước nhưng chưa ai dùng ngoài test — nối vào đây.
    Ví dụ điểm g của ND52 Đ22: "ngoài các điều kiện quy định tại điểm a, điểm b,
    điểm c, điểm d và điểm đ khoản 2 Điều này" trước đây nằm chết trong `text`.
    """
    so_hieu = dieu.id.split("#", 1)[0]
    refs: list[str] = []
    hep_hon = False
    for ref in parse_citations(khoan.text):
        refs += to_node_ids(
            ref, so_hieu, ctx_dieu=dieu.so_hien_thi, ctx_khoan=khoan.so_hien_thi
        )
        hep_hon = hep_hon or ref.co_tiet
    # Bỏ viện dẫn trỏ về chính Khoản đang xét — không mang thông tin.
    refs = [r for r in dict.fromkeys(refs) if r != khoan.id]
    return refs, hep_hon


def _ctx(khoan: KhoanNode, dieu: DieuNode) -> tuple[int, int]:
    """Ngữ cảnh giải viện dẫn tự trỏ (*"Điều này"* / *"khoản này"*).

    Khoản 0 = Điều không chẻ khoản, khi đó "khoản này" không có số để mà khớp.
    """
    return (dieu.so_goc, khoan.so_goc if khoan.so_hien_thi else 0)


def _build_conditions(
    raw_conditions: list[dict],
    khoan: KhoanNode,
    dieu: DieuNode,
    units: list[Unit],
    ctx: tuple[int, int],
) -> tuple[list[ConditionItem], list[str], list[str]]:
    """Phần dùng chung của cả hai vai: neo từng Điểm + kiểm nhãn + lấy tiết.

    Với actor-CU đây là các điều kiện phải thoả; với meta-CU đây là các đơn vị được
    liệt kê riêng trong mệnh đề cổng. Cơ chế neo giống hệt nhau nên dùng chung.
    """
    errors: list[str] = []
    warnings: list[str] = []
    known_diem = {d.so_hien_thi for d in khoan.diem}
    conditions: list[ConditionItem] = []
    # Nhiều điều kiện CÙNG trỏ về một Điểm là chuyện thường: đo trên corpus có 3/49
    # bản ghi như vậy, nặng nhất là ND52 Đ22 K2 với điểm `g` xuất hiện 5 lần. Nếu nhãn
    # cảnh báo chỉ ghi "điều kiện g" thì 5 cảnh báo mang CHUNG một địa chỉ và người
    # duyệt không có cách nào biết mở cái nào — địa chỉ mơ hồ đúng loại lỗi im lặng mà
    # `suy_ra_duoc`/`co_tiet` đã phải sinh ra để chặn ở chỗ khác. Chỉ đánh số khi thật
    # sự trùng, để nhãn của các bản ghi còn lại không đổi.
    src_total: Counter = Counter((r.get("source_diem") or None) for r in raw_conditions)
    src_seen: Counter = Counter()
    for raw in raw_conditions:
        src = raw.get("source_diem") or None
        src_seen[src] += 1
        ten = src or "(không rõ điểm)"
        if src_total[src] > 1:
            ten = f"{ten}#{src_seen[src]}"
        where = f"điều kiện {ten}"
        if src and src not in known_diem:
            warnings.append(f"{where}: điểm không tồn tại trong khoản này")
        g = resolve(raw, units, dieu.text)
        text = dieu.text[g.char_span[0] : g.char_span[1]] if g.char_span else ""
        item_err: list[str] = []
        item_warn: list[str] = []
        if g.status == "invalid":
            item_err.append(f"{where}: đơn vị {g.units} không tồn tại — mất provenance")
        else:
            if g.status == "unit" and g.quote:
                item_warn.append(f"{where}: quote không nằm trong đơn vị đã chọn | {explain(g.quote, text)}")
            evidence = _evidence(units, g, dieu.text)
            for label_key in ("object_label", "constraint_label"):
                e, w = _check(
                    (raw.get(label_key) or "").strip(), text,
                    f"{where}.{label_key}", evidence=evidence, ctx=ctx,
                )
                item_err += e
                item_warn += w
        # Tiết "(i)/(ii)" và phép kết hợp của chúng lấy TẤT ĐỊNH từ parser, không
        # hỏi LLM: "(i) …; hoặc (ii) …" là phép TUYỂN bên trong một điểm, bỏ đi là
        # mất nghĩa pháp lý. Xem TietSpan về lý do tiết không được cấp địa chỉ.
        diem_node = next((d for d in khoan.diem if d.so_hien_thi == src), None)
        sub: list[SubCondition] = []
        logic = "unknown"
        if diem_node and diem_node.tiet:
            logic = tiet_logic(diem_node)
            sub = [
                SubCondition(marker=t.marker, text=t.text, char_span=(t.start, t.end))
                for t in diem_node.tiet
            ]
            if logic == "unknown":
                item_warn.append(
                    f"{where}: có {len(sub)} tiết nhưng chỉ ngăn bằng ';' — không "
                    "xác định được là 'và' hay 'hoặc', cần người đọc chốt"
                )
            if g.char_span and not (
                g.char_span[0] <= sub[0].char_span[0] and sub[-1].char_span[1] <= g.char_span[1]
            ):
                item_warn.append(f"{where}: span không bao hết các tiết của điểm {src}")

        errors += item_err
        warnings += item_warn
        conditions.append(
            ConditionItem(
                source_diem=src,
                text=text,
                object_label=(raw.get("object_label") or "").strip(),
                constraint_label=(raw.get("constraint_label") or "").strip(),
                grounding=g,
                logic=logic,  # type: ignore[arg-type]
                sub=sub,
                issues=item_err + item_warn,
            )
        )

    missing = known_diem - {c.source_diem for c in conditions}
    if missing:
        warnings.append(f"bỏ sót điểm: {', '.join(sorted(missing))}")
    return conditions, errors, warnings


def _logic(data: dict, ep_unknown: bool = False) -> str:
    logic = data.get("logic")
    return "unknown" if (logic not in {"all", "any", "unknown"} or ep_unknown) else logic


def build_actor_cu(
    data: dict, khoan: KhoanNode, dieu: DieuNode, units: list[Unit]
) -> ActorCU:
    """JSON của LLM → `ActorCU`. Không gọi LLM (test được offline)."""
    ctx = _ctx(khoan, dieu)
    errors: list[str] = []
    warnings: list[str] = []

    # `subject` BẮT BUỘC ở đây. Không có nhánh "không áp dụng" nào: một nghĩa vụ mà
    # không có bên bị ràng buộc thì không phán định tuân thủ được ⇒ luôn là trích hỏng.
    subject, e, w = _field(data.get("subject") or {}, units, dieu.text, "subject", ctx=ctx)
    errors += e
    warnings += w
    subject_source = (data.get("subject") or {}).get("source")
    if subject_source not in {"explicit", "inherited"}:
        subject_source = "explicit"
        warnings.append("subject.source thiếu/không hợp lệ — mặc định 'explicit'")
    if subject_source == "explicit" and subject.grounding.units == [0]:
        subject_source = "inherited"
        warnings.append(
            "subject khai 'explicit' nhưng neo vào tiêu đề Điều → hạ về 'inherited'"
        )

    action, e, w = _field(data.get("action") or {}, units, dieu.text, "action", ctx=ctx)
    errors += e
    warnings += w

    conditions, e, w = _build_conditions(
        list(data.get("conditions") or []), khoan, dieu, units, ctx
    )
    errors += e
    warnings += w

    refs, hep_hon = _resolve_references(khoan, dieu)
    return ActorCU(
        id=khoan.id,
        subject=subject,
        subject_source=subject_source,  # type: ignore[arg-type]
        action=action,
        logic=_logic(data),  # type: ignore[arg-type]
        conditions=conditions,
        references=refs,
        references_hep_hon=hep_hon,
        warnings=warnings,
        errors=errors,
    )


def build_meta_cu(
    data: dict,
    khoan: KhoanNode,
    dieu: DieuNode,
    units: list[Unit],
    gates: list[Gate] | None = None,
    dieu_kien_cong: DieuKienCong | None = None,
) -> MetaCU:
    """JSON của LLM → `MetaCU`. Không có ô `subject`, và đó là điều muốn nói.

    Nếu mô hình vẫn khai `subject`, các đơn vị đó được **gộp vào `menh_de`** chứ không
    bị vứt: ở TT40 Đ26 k2 hai span liền kề nhau, ghép lại mới ra trọn mệnh đề. Vứt đi
    là mất nửa câu; giữ thành một ô riêng là quay lại đúng chỗ sai đang muốn bỏ.
    """
    ctx = _ctx(khoan, dieu)
    errors: list[str] = []
    warnings: list[str] = []
    gates = list(gates or [])

    raw_menh_de = dict(data.get("action") or {})
    raw_subject = data.get("subject") or {}
    if raw_subject.get("units"):
        raw_menh_de["units"] = sorted(
            {*(raw_menh_de.get("units") or []), *raw_subject["units"]}
        )
        # `quote` của một trong hai vế không còn bao đúng bao lồi đã gộp ⇒ bỏ, để
        # `resolve` lùi về span đơn vị thay vì thu hẹp sai chỗ.
        raw_menh_de.pop("quote", None)
        warnings.append(
            "cổng không có bên bị ràng buộc — mô hình vẫn khai 'subject', đã gộp đơn "
            f"vị {raw_subject['units']} vào `menh_de` để không mất nửa mệnh đề"
        )

    menh_de, e, w = _field(raw_menh_de, units, dieu.text, "menh_de", ctx=ctx)
    errors += e
    warnings += w

    raw_conditions = list(data.get("conditions") or [])
    bo_dieu_kien = conditions_khong_ap_dung("meta_cu", gates, khoan)
    if bo_dieu_kien and raw_conditions:
        # KHÔNG âm thầm xoá: nêu ra đã bỏ cái gì. Cảnh báo chứ không phải lỗi cứng —
        # mốc ngày đã được tách TẤT ĐỊNH ở bước phân loại, không phụ thuộc ô này.
        nhan = "; ".join(
            (r.get("constraint_label") or r.get("object_label")
             or f"điểm {r.get('source_diem')}").strip()[:60]
            for r in raw_conditions
        )
        warnings.append(
            f"mệnh đề hiệu lực ở khoản không chẻ Điểm — bỏ {len(raw_conditions)} "
            f"'điều kiện' mô hình sinh ra: {nhan}"
        )
        raw_conditions = []

    conditions, e, w = _build_conditions(raw_conditions, khoan, dieu, units, ctx)
    errors += e
    warnings += w

    if not gates:
        # Chặn im lặng: một meta-CU không nói được nó chặn cái gì thì downstream
        # không dùng được, mà nhìn bản ghi lại tưởng đã đầy đủ.
        warnings.append("meta_cu nhưng chưa xác định được phạm vi chặn cổng")
    if any(g.kind == "thoi_gian" for g in gates) and dieu_kien_cong is None:
        # Chỗ hổng cấu trúc phải HIỆN RA: một cổng thời gian không có mốc thời gian ở
        # dạng máy đọc được thì downstream không gate được bằng gì.
        warnings.append(
            "cổng thời gian nhưng chưa tách được mốc ngày ở dạng cấu trúc — "
            "mốc (nếu có) chỉ còn là chữ tự do trong `menh_de`"
        )

    refs, hep_hon = _resolve_references(khoan, dieu)
    return MetaCU(
        id=khoan.id,
        gates=gates,
        dieu_kien_cong=dieu_kien_cong,
        menh_de=menh_de,
        logic=_logic(data, ep_unknown=bo_dieu_kien),  # type: ignore[arg-type]
        conditions=conditions,
        references=refs,
        references_hep_hon=hep_hon,
        warnings=warnings,
        errors=errors,
    )


def build_cu(
    data: dict,
    khoan: KhoanNode,
    dieu: DieuNode,
    units: list[Unit],
    role: str = "actor_cu",
    gates: list[Gate] | None = None,
    dieu_kien_cong: DieuKienCong | None = None,
) -> ComplianceUnit:
    """Rẽ nhánh theo vai. Vai do bước phân loại quyết định, KHÔNG do mô hình khai."""
    if role == "meta_cu":
        return build_meta_cu(data, khoan, dieu, units, gates, dieu_kien_cong)
    if gates:
        raise ValueError(f"actor_cu không được mang cổng: {khoan.id}")
    if dieu_kien_cong is not None:
        raise ValueError(f"actor_cu không được mang điều kiện cổng: {khoan.id}")
    return build_actor_cu(data, khoan, dieu, units)


def extract_cu(
    khoan: KhoanNode,
    dieu: DieuNode,
    role: str = "actor_cu",
    gates: list[Gate] | None = None,
    dieu_kien_cong: DieuKienCong | None = None,
) -> ComplianceUnit:
    """Gọi Gemini rồi neo + kiểm. temperature=0 cho tái lập được."""
    units = segment(dieu, khoan)
    data = chat_json(
        build_prompt(khoan, dieu, units, role=role, gates=gates),
        system=_SYSTEM, reasoning=True, temperature=0.0,
    )
    if "_raw" in data:  # chat_json trả nguyên văn khi JSON hỏng
        raise ValueError(f"Gemini trả JSON không hợp lệ:\n{data['_raw'][:500]}")
    return build_cu(
        data, khoan, dieu, units,
        role=role, gates=gates, dieu_kien_cong=dieu_kien_cong,
    )


# --- Sổ đăng ký PREMISE: không gọi LLM, không sinh Compliance Unit ------------


def build_premise_record(
    khoan: KhoanNode, dieu: DieuNode, verdict, *, gop_vao_gate: str | None = None
) -> PremiseRecord:
    """Đơn vị premise → bản ghi registry. TẤT ĐỊNH — không hỏi LLM một chữ nào.

    Premise không có 4-tuple để trích: giá trị của nó nằm ở chỗ giữ nguyên khối
    văn bản + neo span + bí danh mà văn bản tự tuyên bố. Cho LLM động vào chỉ thêm
    đường bịa mà không thêm thông tin.

    `verdict` là `classify.UnitVerdict` (không import để tránh vòng phụ thuộc).
    """
    warnings = list(verdict.warnings)
    alias_span = verdict.alias_span
    if alias_span and dieu.text[alias_span[0] : alias_span[1]] != verdict.alias:
        # Chỉ xảy ra khi offset bị quy sai gốc — im lặng thì cả registry lệch.
        warnings.append("alias_span không round-trip về dieu.text — bỏ span, giữ chữ")
        alias_span = None
    return PremiseRecord(
        id=khoan.id,
        premise_kind=verdict.premise_kind or "pham_vi",
        raw_text=khoan.text,
        char_span=(khoan.start, khoan.end),
        alias=verdict.alias,
        alias_span=alias_span,
        gop_vao_gate=gop_vao_gate,
        warnings=warnings,
    )


# --- Tầng PREMISE: Điều định nghĩa → KhaiNiem, KHÔNG sinh ComplianceUnit ------

_KN_SYSTEM = (
    "Bạn nhận một KHOẢN trong điều 'Giải thích từ ngữ' của văn bản quy phạm pháp "
    "luật Việt Nam, đã tách sẵn thành các ĐƠN VỊ ĐÁNH SỐ. Hãy chỉ ra thuật ngữ "
    "được định nghĩa và phần định nghĩa của nó, bằng cách CHỌN SỐ HIỆU ĐƠN VỊ.\n"
    "Khuôn phổ biến: '<thuật ngữ> là <định nghĩa>' hoặc '<thuật ngữ> bao gồm ...'.\n"
    "'quote' là TUỲ CHỌN để thu hẹp vào cụm nhỏ hơn bên trong đơn vị đã chọn; nếu "
    "có phải CHÉP NGUYÊN VĂN. Không chắc thì bỏ trống.\n"
    "Khoản này không định nghĩa thuật ngữ nào thì trả units rỗng.\n"
    "Chỉ trả JSON, không giải thích."
)

_KN_HINT = """Trả đúng cấu trúc JSON sau:
{"thuat_ngu": {"units": [1], "quote": ""}, "dinh_nghia": {"units": [1], "quote": ""}}"""


def build_khai_niem(
    data: dict, khoan: KhoanNode, dieu: DieuNode, units: list[Unit]
) -> KhaiNiem | None:
    """Ghép JSON của LLM + neo. Không gọi LLM (test được offline).

    Trả `None` khi Khoản không định nghĩa thuật ngữ nào — LLM trả `units` rỗng.
    Phân biệt với uid sai: rỗng là "ở đây không có gì", không phải mất provenance.
    """
    warnings: list[str] = []
    out: dict[str, tuple[str, tuple[int, int] | None]] = {}
    for key in ("thuat_ngu", "dinh_nghia"):
        raw = data.get(key) or {}
        if not (raw.get("units") or []):
            return None
        g = resolve(raw, units, dieu.text)
        if g.status == "invalid":
            warnings.append(f"{key}: đơn vị {g.units} không tồn tại — mất provenance")
            out[key] = ("", None)
        else:
            out[key] = (dieu.text[g.char_span[0] : g.char_span[1]], g.char_span)
    return KhaiNiem(
        id=khoan.id,
        thuat_ngu=out["thuat_ngu"][0],
        dinh_nghia=out["dinh_nghia"][0],
        char_span_thuat_ngu=out["thuat_ngu"][1],
        char_span_dinh_nghia=out["dinh_nghia"][1],
        warnings=warnings,
    )


def extract_khai_niem(khoan: KhoanNode, dieu: DieuNode) -> KhaiNiem | None:
    units = segment(dieu, khoan)
    prompt = (
        f"Văn bản: {dieu.id.split('#')[0]}\n"
        f"Điều {dieu.so_hien_thi}. {dieu.tieu_de}\n\n"
        f"--- CÁC ĐƠN VỊ CỦA KHOẢN {khoan.so_hien_thi} ---\n"
        f"{render_menu(units)}\n--- HẾT ---\n\n{_KN_HINT}"
    )
    data = chat_json(prompt, system=_KN_SYSTEM, reasoning=False, temperature=0.0)
    if "_raw" in data:
        raise ValueError(f"Gemini trả JSON không hợp lệ:\n{data['_raw'][:500]}")
    return build_khai_niem(data, khoan, dieu, units)


def _row(ten: str, f: GroundedField) -> dict:
    return {"field": ten, "status": f.grounding.status,
            "units": f.grounding.units, "char_span": f.grounding.char_span}


def grounding_report(cu: ComplianceUnit) -> list[dict]:
    """Bảng đối chiếu từng field. Hai vai có bộ trường khác nhau nên rẽ nhánh rõ.

    Không còn dòng `subject: khong_ap_dung` như bản trước: meta-CU giờ **không có**
    ô đó để mà báo trống — kiểu dữ liệu đã nói điều ấy thay cho một dòng trạng thái.
    """
    if isinstance(cu, ActorCU):
        rows = [_row("subject", cu.subject), _row("action", cu.action)]
    else:
        rows = [_row("menh_de", cu.menh_de)]
        if cu.dieu_kien_cong:
            # `status="tat_dinh"`: span này do REGEX của ta tính, không đi qua tay mô
            # hình lần nào — không cùng thang đo với exact/unit/invalid của menu-span.
            rows.append({"field": "dieu_kien_cong", "status": "tat_dinh",
                         "units": [], "char_span": cu.dieu_kien_cong.char_span})
    rows += [
        {"field": f"condition[{c.source_diem or '-'}]", "status": c.grounding.status,
         "units": c.grounding.units, "char_span": c.grounding.char_span}
        for c in cu.conditions
    ]
    return rows


def dump_json(cu: ComplianceUnit) -> str:
    return json.dumps(cu.model_dump(), ensure_ascii=False, indent=2)
