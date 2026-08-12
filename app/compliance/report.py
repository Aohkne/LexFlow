"""Báo cáo side-by-side: đường cũ (`run_review`) vs đường mới (GraphCompliance CU plan).

Thuần — không gọi LLM/retrieval, test được offline. `__main__.py` gom dữ liệu động
(findings, phán quyết, cảnh báo) từ pipeline rồi truyền vào `render_md`.
"""
from __future__ import annotations

from app.compliance.hop_dong import HopDong
from app.core.schemas import ReviewFinding

_BAT_VERDICTS = {"vi_pham", "thieu_thong_tin"}


def tinh_recall(gold_rows: list[dict], phan_quyet_theo_dieu: dict[str, list[dict]]) -> dict:
    """Recall trên gold `loai=="phap_ly"`. `trong_corpus=False` → loại khỏi mẫu số.

    "Bắt được": tồn tại phán quyết đúng điều với verdict vi_pham/thieu_thong_tin và
    `cu_id` bắt đầu bằng một trong các `van_ban` của dòng gold.
    """
    mau_so = 0
    ngoai_pham_vi = 0
    bat_duoc = 0
    bo_sot: list[str] = []
    for g in gold_rows:
        if g.get("loai") != "phap_ly":
            continue
        if not g.get("trong_corpus"):
            ngoai_pham_vi += 1
            continue
        mau_so += 1
        van_ban = g.get("van_ban") or []
        bat = any(
            pq.get("verdict") in _BAT_VERDICTS
            and any(pq.get("cu_id", "").startswith(vb) for vb in van_ban)
            for pq in phan_quyet_theo_dieu.get(g["dieu_hop_dong"], [])
        )
        if bat:
            bat_duoc += 1
        else:
            bo_sot.append(g["comment_id"])
    return {"mau_so": mau_so, "bat_duoc": bat_duoc, "ngoai_pham_vi": ngoai_pham_vi,
            "bo_sot": bo_sot}


def _esc(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def _gold_cell(rows: list[dict]) -> str:
    if not rows:
        return "—"
    return "<br>".join(
        _esc(f"[{r.get('loai')}] {r.get('comment_text', '')[:200]} (id={r.get('comment_id')})")
        for r in rows
    )


def _cu_cell(finding: ReviewFinding | None) -> str:
    if finding is None:
        return "—"
    return _esc(f"{finding.verdict}: {finding.title}")


def _moi_cell(pqs: list[dict]) -> str:
    if not pqs:
        return "—"
    lines = []
    for pq in pqs:
        line = f"{pq.get('verdict')} | {pq.get('cu_id')} | {pq.get('can_cu', '')}"
        if pq.get("override"):
            line += f" | override: {pq['override']}"
        lines.append(_esc(line))
    return "<br>".join(lines)


def render_md(
    hd: HopDong,
    gold_rows: list[dict],
    cu: dict[str, ReviewFinding],
    moi: dict[str, list[dict]],
    canh_bao: list[str] | None = None,
) -> str:
    gold_theo_dieu: dict[str, list[dict]] = {}
    for g in gold_rows:
        gold_theo_dieu.setdefault(g.get("dieu_hop_dong") or "", []).append(g)

    lines = [
        f"# Báo cáo đối chiếu — {hd.ten}", "",
        "| Điều | Gold | Đường cũ | Đường mới |",
        "| --- | --- | --- | --- |",
    ]
    for d in hd.dieu:
        lines.append(
            f"| Điều {d.so}. {_esc(d.tieu_de)} | {_gold_cell(gold_theo_dieu.get(d.so, []))} "
            f"| {_cu_cell(cu.get(d.so))} | {_moi_cell(moi.get(d.so, []))} |"
        )

    r = tinh_recall(gold_rows, moi)
    lines += [
        "", "## Recall",
        f"- Mẫu số (gold pháp lý trong corpus): {r['mau_so']}",
        f"- Bắt được: {r['bat_duoc']}",
        f"- Ngoài phạm vi corpus (loại khỏi mẫu số): {r['ngoai_pham_vi']}",
        f"- Bỏ sót (comment_id): {r['bo_sot']}",
    ]

    lines += ["", "## Ca lạ"]
    lines += [f"- {c}" for c in canh_bao] if canh_bao else ["- (không có)"]

    return "\n".join(lines) + "\n"
