"""LLM Judgment: một lượt phán định giữ nguyên cả CU plan của một điều hợp đồng.

Paper GraphCompliance §Judgment: một lời gọi holistic đối chiếu TOÀN BỘ CU plan
với văn bản điều, CẤM suy diễn từ im lặng (verdict lạ/thiếu dữ kiện → thieu_thong_tin,
không phải tuan_thu). Tự nhất quán theo mẫu `review.py._judge` nhưng đa số tính
RIÊNG theo từng cu_id (một lượt gọi có thể đúng CU này, sai CU khác).

vi_pham → thử lật bằng vòng override (Eq. 6): đóng bao R(c) qua `PolicyGraph.closure`,
lọc các CU mien_tru trong đó, hỏi LLM đúng một câu "có thuộc trường hợp miễn trừ
không" — CẤM suy từ im lặng ở đây nữa (ap_dung mặc định False khi không xác quyết).
"""
from __future__ import annotations

from pydantic import BaseModel

from app.compliance.gate import CUPlan, PlanItem
from app.compliance.policy_graph import PolicyGraph
from app.core.llm import chat_json
from app.ontology.schema import ActorCU

_VERDICTS = {"tuan_thu", "vi_pham", "thieu_thong_tin", "khong_ap_dung"}
_SYSTEM = (
    "Bạn là chuyên gia pháp chế ngân hàng. Đối chiếu MỘT điều khoản hợp đồng với "
    "danh sách Compliance Unit (CU) trích từ luật. Với TỪNG CU trả verdict:\n"
    "- vi_pham: hợp đồng TRÁI với CU (chú ý modality: 'cam' mà hợp đồng cho làm; "
    "'chi_duoc' mà hợp đồng làm ngoài điều kiện; 'nghia_vu' mà hợp đồng gạt bỏ).\n"
    "- tuan_thu: phù hợp, hoặc hợp đồng CHẶT HƠN luật.\n"
    "- khong_ap_dung: CU không liên quan điều khoản này.\n"
    "- thieu_thong_tin: không đủ dữ kiện kết luận. CẤM suy từ im lặng.\n"
    "CU có trường 'nguong': PHẢI so trực tiếp số trong hợp đồng với số của ngưỡng "
    "(cùng đơn vị mới so; 'toi_da' nghĩa là hợp đồng vượt số đó = vi_pham).\n"
    'Chỉ trả JSON: {"phan_quyet": [{"cu_id": "...", "verdict": "...", '
    '"can_cu": "...", "quote_hop_dong": "...", "quote_luat": "..."}]}'
)
_SYSTEM_OVERRIDE = (
    "Bạn là chuyên gia pháp chế ngân hàng. Một điều khoản hợp đồng đang bị coi là "
    "VI PHẠM một Compliance Unit. Dưới đây là các CU MIỄN TRỪ (mien_tru) có liên hệ "
    "trực tiếp với CU đó. Hỏi ĐÚNG MỘT câu: điều khoản hợp đồng có thuộc trường hợp "
    "được miễn trừ theo một trong các CU này không? CẤM suy từ im lặng — không xác "
    "quyết được thì trả ap_dung=false.\n"
    'Chỉ trả JSON: {"ap_dung": true|false, "ly_do": "..."}'
)
_TOM_TAT_DIEU_KIEN = 200


class PhanQuyet(BaseModel):
    cu_id: str
    verdict: str  # tuan_thu | vi_pham | thieu_thong_tin | khong_ap_dung
    can_cu: str  # 1-2 câu
    quote_hop_dong: str
    quote_luat: str
    override: str | None = None  # căn cứ miễn trừ nếu verdict bị lật


def _dong_cu(item: PlanItem) -> str:
    cu = item.cu
    phan = [f"id={cu.id}", f"modality={cu.modality}", f"action={cu.action.text}"]
    if cu.nguong:
        phan.append("nguong=[" + "; ".join(
            f"{n.huong} {n.so}{' ' + n.don_vi if n.don_vi else ''}" for n in cu.nguong
        ) + "]")
    if cu.conditions:
        phan.append("conditions=[" + "; ".join(
            c.text[:_TOM_TAT_DIEU_KIEN] for c in cu.conditions
        ) + "]")
    if item.gate_chua_xac_quyet:
        phan.append("gate_chua_xac_quyet=true")
    return "- " + " | ".join(phan)


def _prompt(text_dieu_hd: str, plan: CUPlan) -> str:
    listing = "\n".join(_dong_cu(item) for item in plan.items)
    return (
        f"Điều hợp đồng cần đối chiếu:\n{text_dieu_hd}\n\n"
        f"Danh sách Compliance Unit (CU) cần phán định:\n{listing}"
    )


def _index_by_cu(vote: dict) -> dict[str, dict]:
    return {
        pq["cu_id"]: pq for pq in vote.get("phan_quyet", [])
        if isinstance(pq, dict) and pq.get("cu_id")
    }


def _norm_verdict(v: str | None) -> str:
    return v if v in _VERDICTS else "thieu_thong_tin"


def _da_so(cu_id: str, recs: list[dict | None]) -> PhanQuyet:
    """Verdict xuất hiện ≥ 2 lần trong các phiếu có CU này → thắng. Không có → thieu_thong_tin."""
    norm = [_norm_verdict(r.get("verdict")) if r else None for r in recs]
    for v in {n for n in norm if n is not None}:
        if norm.count(v) >= 2:
            rec = next(r for r, n in zip(recs, norm, strict=True) if n == v)
            return PhanQuyet(
                cu_id=cu_id, verdict=v,
                can_cu=rec.get("can_cu", ""),
                quote_hop_dong=rec.get("quote_hop_dong", ""),
                quote_luat=rec.get("quote_luat", ""),
            )
    can_cu = "LLM bỏ sót CU này" if any(r is None for r in recs) else (
        "các lượt phán định không đồng nhất"
    )
    return PhanQuyet(cu_id=cu_id, verdict="thieu_thong_tin", can_cu=can_cu,
                      quote_hop_dong="", quote_luat="")


def _prompt_override(cu_id: str, pq: PhanQuyet, mien_tru: list[ActorCU]) -> str:
    listing = "\n".join(f"- id={c.id} | {c.action.text}" for c in mien_tru)
    return (
        f"CU bị coi là vi phạm: {cu_id} — {pq.can_cu}\n"
        f"Trích hợp đồng: {pq.quote_hop_dong}\n\n"
        f"Các CU miễn trừ liên quan (đóng bao tham chiếu 2 hop):\n{listing}"
    )


def _thu_override(pq: PhanQuyet, pg: PolicyGraph) -> PhanQuyet:
    mien_tru = pg.mien_tru_trong([c.id for c in pg.closure(pq.cu_id)])
    if not mien_tru:
        return pq
    data = chat_json(_prompt_override(pq.cu_id, pq, mien_tru),
                      system=_SYSTEM_OVERRIDE, temperature=0.0)
    if data.get("ap_dung") is True:
        return pq.model_copy(update={"verdict": "tuan_thu", "override": data.get("ly_do", "")})
    return pq


def phan_dinh(text_dieu_hd: str, plan: CUPlan, pg: PolicyGraph) -> list[PhanQuyet]:
    if not plan.items:
        return []
    prompt = _prompt(text_dieu_hd, plan)
    cu_ids = [item.cu.id for item in plan.items]

    votes = [chat_json(prompt, system=_SYSTEM, temperature=0.0) for _ in range(2)]
    by_cu = [_index_by_cu(v) for v in votes]
    bat_dong = any(
        _norm_verdict((by_cu[0].get(cid) or {}).get("verdict"))
        != _norm_verdict((by_cu[1].get(cid) or {}).get("verdict"))
        for cid in cu_ids
    )
    if bat_dong:
        votes.append(chat_json(prompt, system=_SYSTEM, temperature=0.0))
        by_cu.append(_index_by_cu(votes[-1]))

    ra = []
    for cid in cu_ids:
        pq = _da_so(cid, [bv.get(cid) for bv in by_cu])
        if pq.verdict == "vi_pham":
            pq = _thu_override(pq, pg)
        ra.append(pq)
    return ra
