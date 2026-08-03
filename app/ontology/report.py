"""Sinh trang HTML tự chứa để NGƯỜI đọc và kiểm span — dùng cho cả gán gold.

Kỷ luật encoding ở đây là vấn đề ĐÚNG/SAI, không phải thẩm mỹ: `char_span` đếm theo
Unicode code point, nếu file bị đọc/ghi sai codec thì `đ` thành 2 ký tự và MỌI offset
phía sau lệch hết. Do đó:
  - hàm này chỉ trả chuỗi; người gọi ghi bằng `Path.write_text(..., encoding="utf-8")`,
    KHÔNG bao giờ dùng redirect `>` của shell (PowerShell re-encode bằng codec riêng);
  - HTML luôn có `<meta charset="utf-8">` (bytes đúng mà thiếu thẻ này thì browser
    vẫn đoán sai và hiện mojibake);
  - mọi đoạn text đi qua `html.escape()`.
`tests/test_ontology_report.py` canh cả ba điều trên.
"""
from __future__ import annotations

from html import escape

from app.ontology.schema import ActorCU, ComplianceUnit, DieuNode, MetaCU

_ROLE_COLOR = {
    "subject": ("#2563eb", "#dbeafe"),
    "action": ("#b45309", "#fef3c7"),
    "condition": ("#047857", "#d1fae5"),
    # Span do regex của ta tính, không do mô hình chọn — tô màu khác để người đọc
    # nhìn ra ngay đây là chỗ máy đọc chắc chắn, không phải chỗ cần soi.
    "dieu_kien_cong": ("#7c3aed", "#ede9fe"),
}

_CSS = """
:root { color-scheme: light dark; }
body { font: 15px/1.65 system-ui, "Segoe UI", sans-serif; max-width: 60rem;
       margin: 2rem auto; padding: 0 1.25rem; }
h1 { font-size: 1.35rem; margin-bottom: .25rem; }
.meta { color: #6b7280; font-size: .85rem; margin-bottom: 1.5rem; }
.legend span { display: inline-block; padding: .1rem .5rem; border-radius: 4px;
               margin-right: .5rem; font-size: .8rem; }
pre.doc { white-space: pre-wrap; word-break: break-word; background: #fafaf9;
          border: 1px solid #e7e5e4; border-radius: 8px; padding: 1rem;
          font: inherit; margin: 1rem 0 2rem; }
mark { padding: .05rem 0; border-radius: 3px; border-bottom: 2px solid; }
table { border-collapse: collapse; width: 100%; font-size: .85rem; margin-bottom: 2rem; }
th, td { border: 1px solid #e7e5e4; padding: .4rem .6rem; text-align: left;
         vertical-align: top; }
th { background: #f5f5f4; }
td.err { color: #b91c1c; font-weight: 600; }
td.warn { color: #b45309; }
.issues li { margin-bottom: .3rem; }
.err-box { border-left: 4px solid #b91c1c; background: #fef2f2; padding: .75rem 1rem;
           border-radius: 4px; margin-bottom: 1.5rem; }
.ok-box  { border-left: 4px solid #047857; background: #ecfdf5; padding: .75rem 1rem;
           border-radius: 4px; margin-bottom: 1.5rem; }
@media (prefers-color-scheme: dark) {
  body { background: #1c1917; color: #e7e5e4; }
  pre.doc { background: #292524; border-color: #44403c; }
  th { background: #292524; } th, td { border-color: #44403c; }
  .err-box { background: #2a1315; } .ok-box { background: #05231b; }
}
"""


def _spans(cu: ComplianceUnit) -> list[tuple[int, int, str, str]]:
    """[(start, end, role, nhãn)] đã sắp, bỏ span không neo được."""
    out: list[tuple[int, int, str, str]] = []
    if isinstance(cu, ActorCU):
        khung = (("subject", cu.subject, "subject"), ("action", cu.action, "action"))
    else:
        # meta-CU tô `menh_de` bằng màu của `action` — cùng vai trò thị giác (vị ngữ
        # của mệnh đề), chỉ khác tên vì nó không phải hành vi.
        khung = (("action", cu.menh_de, "mệnh đề hiệu lực/phạm vi"),)
    for role, field, name in khung:
        if field and field.grounding.char_span:
            a, b = field.grounding.char_span
            out.append((a, b, role, name))
    if isinstance(cu, MetaCU) and cu.dieu_kien_cong and cu.dieu_kien_cong.char_span:
        a, b = cu.dieu_kien_cong.char_span
        out.append((a, b, "dieu_kien_cong", "điều kiện cổng (tất định)"))
    for c in cu.conditions:
        if c.grounding.char_span:
            a, b = c.grounding.char_span
            out.append((a, b, "condition", f"điều kiện {c.source_diem or '-'}"))
    return sorted(out)


def _render_text(text: str, spans: list[tuple[int, int, str, str]]) -> str:
    """Tô màu span. Span chồng nhau: cắt tại biên, ưu tiên span hẹp hơn."""
    # Điểm cắt = mọi biên; với mỗi lát, chọn span hẹp nhất bao nó.
    bounds = sorted({0, len(text), *[x for a, b, _, _ in spans for x in (a, b)]})
    parts: list[str] = []
    for a, b in zip(bounds, bounds[1:]):
        if a >= b:
            continue
        covering = [s for s in spans if s[0] <= a and s[1] >= b]
        chunk = escape(text[a:b])
        if not covering:
            parts.append(chunk)
            continue
        s = min(covering, key=lambda s: s[1] - s[0])
        fg, bg = _ROLE_COLOR[s[2]]
        note = " + chồng lấn" if len(covering) > 1 else ""
        parts.append(
            f'<mark style="background:{bg};border-color:{fg}" '
            f'title="{escape(s[3])}{note}">{chunk}</mark>'
        )
    return "".join(parts)


def _rows(cu: ComplianceUnit) -> str:
    def row(name: str, text: str, label: str, g, issues: list[str]) -> str:
        """`name` đã được escape tại chỗ gọi vì có thể chứa thẻ <b> cố ý."""
        cls = "err" if g.status == "invalid" else ("warn" if g.status == "unit" else "")
        return (
            f"<tr><td>{name}</td>"
            f"<td class='{cls}'>{escape(g.status)}</td>"
            f"<td>{escape(str(g.units))}</td>"
            f"<td>{escape(str(g.char_span))}</td>"
            f"<td>{escape(text[:160])}</td>"
            f"<td>{escape(label)}</td>"
            f"<td>{'<br>'.join(escape(i) for i in issues)}</td></tr>"
        )

    if isinstance(cu, ActorCU):
        body = [
            row("subject", cu.subject.text, cu.subject.label,
                cu.subject.grounding, cu.subject.issues),
            row("action", cu.action.text, cu.action.label,
                cu.action.grounding, cu.action.issues),
        ]
    else:
        # KHÔNG còn dòng "subject: không áp dụng". Bản trước phải in một dòng trống có
        # chủ ý vì ô đó tồn tại trong kiểu; nay meta-CU không có ô ấy, nên nói bằng
        # chính tên trường là đủ — thêm một dòng trống chỉ tổ gợi lại câu hỏi cũ.
        body = [
            row("menh_de", cu.menh_de.text, cu.menh_de.label,
                cu.menh_de.grounding, cu.menh_de.issues),
        ]
    if isinstance(cu, MetaCU) and cu.dieu_kien_cong:
        d = cu.dieu_kien_cong
        moc = "bắt đầu" if d.moc == "bat_dau" else "KẾT THÚC"
        ngay = f"<b>{escape(d.ngay)}</b> ({moc})" if d.ngay else "<i>không có ngày</i>"
        body.append(
            "<tr><td>dieu_kien_cong</td><td>tất định</td><td>—</td>"
            f"<td>{escape(str(d.char_span))}</td>"
            f"<td>{escape(d.raw_text[:160])}</td><td>{ngay}</td>"
            f"<td>{escape(d.ghi_chu)}</td></tr>"
        )
    if isinstance(cu, MetaCU) and cu.dieu_kien_cong and not cu.conditions:
        # Ô trống có chủ ý phải THẤY ĐƯỢC — biến mất thì người đọc không phân biệt
        # được "không áp dụng" với "quên trích". Đây vẫn cần dòng riêng vì `conditions`
        # TỒN TẠI trong kiểu `MetaCU`, chỉ là rỗng ở khoản không chẻ Điểm.
        body.append(
            "<tr><td>conditions</td><td><i>không áp dụng</i></td><td>—</td><td>—</td>"
            "<td colspan='3'><i>mệnh đề hiệu lực ở khoản không chẻ Điểm — không có "
            "điều kiện theo nghĩa nghĩa vụ</i></td></tr>"
        )
    for c in cu.conditions:
        # `source_diem` nay do parser suy ra (`extractor._suy_diem`) nên không còn là chuỗi
        # LLM điều khiển được; giữ escape làm lớp phòng thủ thứ hai. Lời khai của mô hình
        # chỉ còn đi vào HTML qua cảnh báo `diem_khai_lech`, và cảnh báo đã escape ở dưới.
        name = f"condition[{escape(c.source_diem or '-')}]"
        if c.sub:
            # Tiết không có địa chỉ node, nhưng phép kết hợp thì phải hiện ra —
            # "unknown" là chỗ cần người đọc chốt và/hoặc.
            markers = ", ".join(f"({s.marker})" for s in c.sub)
            name += f" — {len(c.sub)} tiết {markers}: <b>{escape(c.logic)}</b>"
        body.append(
            row(name, c.text, f"{c.object_label} / {c.constraint_label}", c.grounding, c.issues)
        )
    return (
        "<table><tr><th>trường</th><th>neo</th><th>đơn vị</th><th>char_span</th>"
        "<th>chữ của luật</th><th>diễn giải của mô hình</th><th>vấn đề</th></tr>"
        + "".join(body)
        + "</table>"
    )


def render(cu: ComplianceUnit, dieu: DieuNode) -> str:
    """ComplianceUnit + Điều gốc → trang HTML tự chứa (chuỗi, chưa ghi file)."""
    legend = " ".join(
        f'<span style="background:{bg};border-bottom:2px solid {fg}">{escape(role)}</span>'
        for role, (fg, bg) in _ROLE_COLOR.items()
    )
    status = (
        f"<div class='err-box'><b>{len(cu.errors)} lỗi cứng</b> — bản ghi không được "
        "dùng ở downstream.<ul class='issues'>"
        + "".join(f"<li>{escape(e)}</li>" for e in cu.errors)
        + "</ul></div>"
        if cu.errors
        else "<div class='ok-box'>Không có lỗi cứng.</div>"
    )
    warns = (
        "<h2>Cảnh báo</h2><ul class='issues'>"
        + "".join(f"<li>{escape(w)}</li>" for w in cu.warnings)
        + "</ul>"
        if cu.warnings
        else ""
    )
    return (
        "<!doctype html>\n<html lang='vi'>\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(cu.id)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        f"<h1>{escape(cu.id)}</h1>\n"
        f"<p class='meta'>Điều {escape(dieu.so_hien_thi)}. {escape(dieu.tieu_de)} — "
        f"logic=<b>{escape(cu.logic)}</b>, vai=<b>{escape(cu.type)}</b>"
        + (
            f", subject_source=<b>{escape(cu.subject_source)}</b>"
            if isinstance(cu, ActorCU)
            else f", cổng=<b>{escape(cu.gates[0].kind if cu.gates else '—')}</b>"
        )
        + "</p>\n"
        f"<p class='legend'>{legend}</p>\n"
        f"{status}\n"
        f"<pre class='doc'>{_render_text(dieu.text, _spans(cu))}</pre>\n"
        f"{_rows(cu)}\n{warns}\n</body>\n</html>\n"
    )
