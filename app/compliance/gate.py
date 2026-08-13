"""Compliance Gate — phần TẤT ĐỊNH đứng trước judge, đúng thứ tự paper:
meta-CU đánh giá trước, actor-CU mới vào plan.

Fail-open có chủ đích: gate không xác quyết được (lanh_tho/khac/suy_ra_duoc=False)
thì GIỮ CU + cờ `gate_chua_xac_quyet` — mục tiêu POC là recall trên điểm pháp lý
đã đánh dấu, thà judge thừa còn hơn gate nuốt. Cùng triết lý fail-open của lớp
phủ (lop_phu.py:36).
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from app.compliance.hypernym import DeXuat
from app.compliance.policy_graph import PolicyGraph, dieu_prefix
from app.knowledge.lop_phu import chu_thich_ket_qua
from app.knowledge.retrieval import search_in_docs
from app.ontology.schema import ActorCU, ComplianceUnit, Gate, MetaCU

_SO_DIEU_RE = re.compile(r"Điều\s+(\d+[a-z]?)")
_TOP_K = 8


class PlanItem(BaseModel):
    cu: ActorCU
    ly_do: str
    gate_chua_xac_quyet: bool = False


class CUPlan(BaseModel):
    items: list[PlanItem]
    ghi_chu: list[str]


def _target_hit(cu_id: str, targets: list[str]) -> bool:
    """`targets` rỗng = phủ cả cấp (Gate.targets, schema.py) ⇒ khớp mọi CU."""
    return not targets or cu_id in targets or dieu_prefix(cu_id) in targets


def _khop_subject(cu: ActorCU, hypernym: str) -> bool:
    return hypernym.lower() in (cu.subject.text + " " + cu.subject.label).lower()


def _khop_dieu_kien_phu_dinh(m: MetaCU, hyp_set: set[str]) -> set[str]:
    """Hypernym nào khớp đối tượng bị loại trừ trong `m.conditions`.

    `Gate.targets` của cổng `chu_the` là khoá node (phạm vi bị chặn — vd
    ["…#khoan_1"], xem `classify.py:296-300`), KHÔNG phải tên chủ thể — giao thẳng
    với hypernym set (chuỗi như "đại lý thanh toán") luôn rỗng. Tên chủ thể bị loại
    trừ thật sự nằm ở `conditions[].object_label`/`constraint_label`/`text` (mẫu
    thật TT40 Đ26 k2: `pred.jsonl` dòng "chu_the"), do mệnh đề "…không áp dụng đối
    với:" liệt kê chúng ở các Điểm con, không nằm trong bản thân Gate.
    """
    text = " ".join(
        f"{c.text} {c.object_label} {c.constraint_label}" for c in m.conditions
    ).lower()
    return {hy for hy in hyp_set if hy.lower() in text}


def _fail_open(g: Gate, cands: dict[str, tuple[ComplianceUnit, str]], unresolved: set[str]) -> None:
    unresolved.update(
        cid for cid, (cu, _) in cands.items()
        if isinstance(cu, ActorCU) and _target_hit(cid, g.targets)
    )


def _ung_vien(
    text_dieu_hd: str, hypernyms: list[DeXuat], pg: PolicyGraph,
    against_ids: list[str], as_of: str, so_hieu_cua: dict[str, str],
) -> dict[str, tuple[ComplianceUnit, str]]:
    """Bước 1-2: retrieval → chú thích hiệu lực → ứng viên theo Điều/subject → nở 1 hop."""
    chunks = search_in_docs(
        text_dieu_hd, against_ids, top_k=_TOP_K, as_of=as_of, effective_only=True
    )
    chunks, ct = chu_thich_ket_qua(chunks, as_of, pham_vi=set(against_ids))
    chunks = [
        c for c in chunks
        if not ((t := ct.get(c.get("id"))) is not None and t.trang_thai == "bi_bai_bo")
    ]

    cands: dict[str, tuple[ComplianceUnit, str]] = {}
    for c in chunks:
        so_hieu = so_hieu_cua.get(c["doc_id"])
        m = _SO_DIEU_RE.search(c["article"]) if so_hieu else None
        if not m:
            continue
        for cu in pg.cu_cua_dieu(so_hieu, m.group(1)):
            cands.setdefault(cu.id, (cu, f"retrieval {c['article']}"))

    for h in hypernyms:
        for cu in pg.cu.values():
            if isinstance(cu, ActorCU) and _khop_subject(cu, h.hypernym):
                cands.setdefault(cu.id, (cu, f"subject khớp '{h.hypernym}'"))

    for cid in list(cands):
        for nb in pg.lang_gieng(cid):
            cands.setdefault(nb.id, (nb, f"REFERS_TO từ {cid}"))

    return cands


def _meta_cu_ung_vien(cands: dict[str, tuple[ComplianceUnit, str]], pg: PolicyGraph) -> set[str]:
    """Meta-CU trong tập ứng viên + meta-CU cùng Điều với actor-CU ứng viên."""
    meta_ids = {cid for cid, (cu, _) in cands.items() if isinstance(cu, MetaCU)}
    dieu_actor = {dieu_prefix(cid) for cid, (cu, _) in cands.items() if isinstance(cu, ActorCU)}
    meta_ids |= {
        cid for cid, cu in pg.cu.items()
        if isinstance(cu, MetaCU) and dieu_prefix(cid) in dieu_actor
    }
    return meta_ids


def _ap_dung_gate(
    m: MetaCU, g: Gate, as_of: str, hyp_set: set[str],
    cands: dict[str, tuple[ComplianceUnit, str]], unresolved: set[str], ghi_chu: list[str],
) -> None:
    if not g.suy_ra_duoc:
        _fail_open(g, cands, unresolved)
        ghi_chu.append(f"meta {m.id} gate {g.kind} không xác quyết được (suy_ra_duoc=False)")
        return

    if g.kind == "thoi_gian":
        dkc = m.dieu_kien_cong
        if dkc is None or not dkc.ngay:
            _fail_open(g, cands, unresolved)
            ghi_chu.append(f"meta {m.id} gate thoi_gian thiếu ngày, không xác quyết được")
            return
        chan = (dkc.moc == "bat_dau" and dkc.ngay > as_of) or (
            dkc.moc == "ket_thuc" and dkc.ngay <= as_of
        )
        if chan:
            bi_chan = [
                cid for cid, (cu, _) in cands.items()
                if isinstance(cu, ActorCU) and _target_hit(cid, g.targets)
            ]
            for cid in bi_chan:
                del cands[cid]
            ghi_chu.append(f"meta {m.id} chặn {bi_chan}: mốc {dkc.moc} {dkc.ngay}")
        return

    if g.kind == "chu_the":
        if g.phu_dinh:
            khop = _khop_dieu_kien_phu_dinh(m, hyp_set)
            if khop:
                bi_loai = [
                    cid for cid, (cu, _) in cands.items()
                    if isinstance(cu, ActorCU) and _target_hit(cid, g.targets)
                ]
                for cid in bi_loai:
                    del cands[cid]
                ghi_chu.append(
                    f"meta {m.id} loại {bi_loai}: chủ thể khớp phủ định {sorted(khop)}"
                )
        else:
            # Cổng chủ thể KHẲNG ĐỊNH ("chỉ áp dụng đối với X") chưa có cách
            # đánh giá tất định — giữ CU + cờ như lanh_tho/khac, không rơi im lặng.
            _fail_open(g, cands, unresolved)
            ghi_chu.append(f"meta {m.id} gate chu_the khẳng định không xác quyết được")
        return

    # lanh_tho, khac — không có cách đánh giá tất định
    _fail_open(g, cands, unresolved)
    ghi_chu.append(f"meta {m.id} gate {g.kind} không xác quyết được")


def lap_cu_plan(
    text_dieu_hd: str, hypernyms: list[DeXuat], pg: PolicyGraph,
    against_ids: list[str], as_of: str, so_hieu_cua: dict[str, str],
) -> CUPlan:
    cands = _ung_vien(text_dieu_hd, hypernyms, pg, against_ids, as_of, so_hieu_cua)
    hyp_set = {h.hypernym for h in hypernyms}
    ghi_chu: list[str] = []
    unresolved: set[str] = set()

    for mid in sorted(_meta_cu_ung_vien(cands, pg)):
        m = pg.cu[mid]
        assert isinstance(m, MetaCU)
        for g in m.gates:
            _ap_dung_gate(m, g, as_of, hyp_set, cands, unresolved, ghi_chu)

    items = [
        PlanItem(cu=cu, ly_do=ly_do, gate_chua_xac_quyet=cid in unresolved)
        for cid, (cu, ly_do) in cands.items()
        if isinstance(cu, ActorCU)
    ]
    return CUPlan(items=items, ghi_chu=ghi_chu)
