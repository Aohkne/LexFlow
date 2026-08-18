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
from app.ontology.schema import ActorCU, ComplianceUnit, Gate, KhaiNiem, MetaCU

_SO_DIEU_RE = re.compile(r"Điều\s+(\d+[a-z]?)")
_TOP_K = 8
_GIOI_HAN_DINH_NGHIA = 8
#: Nâng khi LOGIC chọn lọc của gate đổi (khoá cache per-điều băm cả hằng này —
#: dữ liệu pred/khainiem đã băm riêng, nhưng đổi thuật toán thì chỉ có nó biết).
#: "2" = thêm khớp gần thiếu-token cho định nghĩa (T28, 17/08).
#: "3" = cổng chủ-thể phủ-định phân bậc mạnh/yếu, khớp yếu fail-open (T30, 18/08).
PHIEN_BAN_GATE = "3"


class PlanItem(BaseModel):
    cu: ActorCU
    ly_do: str
    gate_chua_xac_quyet: bool = False


class CUPlan(BaseModel):
    items: list[PlanItem]
    ghi_chu: list[str]
    # Tầng premise: định nghĩa pháp lý mà điều hợp đồng có dùng thuật ngữ —
    # judge đối chiếu CÁCH DÙNG, không phải nghĩa vụ (schema.py KhaiNiem, 16/08).
    dinh_nghia: list[KhaiNiem] = []


def _target_hit(cu_id: str, targets: list[str]) -> bool:
    """`targets` rỗng = phủ cả cấp (Gate.targets, schema.py) ⇒ khớp mọi CU."""
    return not targets or cu_id in targets or dieu_prefix(cu_id) in targets


def _khop_subject(cu: ActorCU, hypernym: str) -> bool:
    return hypernym.lower() in (cu.subject.text + " " + cu.subject.label).lower()


def _khop_dieu_kien_phu_dinh(m: MetaCU, hyp_set: set[str]) -> tuple[set[str], set[str]]:
    """Hypernym khớp đối tượng bị loại trừ trong `m.conditions` — trả (mạnh, yếu).

    `Gate.targets` của cổng `chu_the` là khoá node (phạm vi bị chặn — vd
    ["…#khoan_1"], xem `classify.py:296-300`), KHÔNG phải tên chủ thể — giao thẳng
    với hypernym set (chuỗi như "đại lý thanh toán") luôn rỗng. Tên chủ thể bị loại
    trừ thật sự nằm ở `conditions[].object_label`/`constraint_label`/`text` (mẫu
    thật TT40 Đ26 k2: `pred.jsonl` dòng "chu_the"), do mệnh đề "…không áp dụng đối
    với:" liệt kê chúng ở các Điểm con, không nằm trong bản thân Gate.

    Hai bậc chứng cứ (pilot T30, 18/08): **mạnh** = hypernym BẰNG nguyên cụm
    object/constraint_label (chuẩn hoá hoa-thường + khoảng trắng) — đủ để xóa CU;
    **yếu** = chỉ là substring của văn xuôi điều kiện — hypernym generic "giao
    dịch thanh toán" nằm gọn trong "Các giao dịch thanh toán: … điện; nước…" dù
    ngoại lệ thật là thanh-toán-tiện-ích, xóa theo nó thì gate nuốt oan CU trần
    100tr (Đ26k1 trượt cả 3 case synthetic). Yếu → fail-open, judge quyết.
    """
    def _chuan(s: str) -> str:
        return " ".join(s.lower().split())

    nhan = {_chuan(c.object_label) for c in m.conditions} | {
        _chuan(c.constraint_label) for c in m.conditions
    }
    text = _chuan(" ".join(
        f"{c.text} {c.object_label} {c.constraint_label}" for c in m.conditions
    ))
    manh = {hy for hy in hyp_set if _chuan(hy) in nhan}
    yeu = {hy for hy in hyp_set if _chuan(hy) in text} - manh
    return manh, yeu


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
            manh, yeu = _khop_dieu_kien_phu_dinh(m, hyp_set)
            if manh:
                bi_loai = [
                    cid for cid, (cu, _) in cands.items()
                    if isinstance(cu, ActorCU) and _target_hit(cid, g.targets)
                ]
                for cid in bi_loai:
                    del cands[cid]
                ghi_chu.append(
                    f"meta {m.id} loại {bi_loai}: chủ thể khớp phủ định {sorted(manh)}"
                )
            elif yeu:
                _fail_open(g, cands, unresolved)
                ghi_chu.append(
                    f"meta {m.id} khớp phủ định yếu {sorted(yeu)} "
                    "(substring văn xuôi điều kiện, không bằng label) — giữ CU + cờ"
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


def _ap_meta_va_dong_goi(
    cands: dict[str, tuple[ComplianceUnit, str]], hyp_set: set[str],
    pg: PolicyGraph, as_of: str,
) -> CUPlan:
    """Đuôi chung của hai đường lập plan: áp meta-gate rồi đóng gói actor-CU."""
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


def _khop_gan(thuat_ngu_norm: str, text_norm: str) -> bool:
    """Thuật ngữ luật khớp điều dù hợp đồng viết THIẾU 1-2 token CUỐI.

    Lớp lỗi thật của gold #13 (phân xử 17/08): hợp đồng ghi "dịch vụ cổng thanh
    toán" thiếu đuôi "điện tử" (2 token) so với thuật ngữ NĐ52 Đ3 k18 — đường
    nguyên văn chắc chắn trượt nên định nghĩa không bao giờ vào plan. So mức
    TOKEN chứ không Levenshtein ký tự: thuật ngữ tiếng Việt đa-từ lệch cả từ,
    ngưỡng ký tự đủ rộng để bắt sẽ ôm oan cặp sai.

    CHỈ bỏ đuôi, phần còn lại ≥4 token — đo 17/08 trên 2 hợp đồng thật: cho bỏ
    token giữa/đầu thì "Chủ [tài] khoản thanh toán"→"tài khoản thanh toán",
    "Hợp đồng thanh toán [thẻ]"→"hợp đồng thanh toán" — cụm phổ thông, plan
    phình +27/+29 định nghĩa toàn khớp oan.
    """
    # ponytail: chỉ bắt ca THIẾU ĐUÔI — ca lệch chính tả/thừa từ/thiếu đầu chưa
    # có mẫu thật, thêm (difflib/prefix-drop) khi xuất hiện.
    tok = thuat_ngu_norm.split()
    return any(
        len(tok) - bo >= 4 and " ".join(tok[:-bo]) in text_norm
        for bo in (1, 2)
    )


def khai_niem_lien_quan(
    text_dieu_hd: str, hypernyms: list[DeXuat], pg: PolicyGraph,
    gioi_han: int = _GIOI_HAN_DINH_NGHIA,
) -> tuple[list[KhaiNiem], list[str]]:
    """Khái niệm mà điều hợp đồng CÓ dùng — chọn tất định, không LLM.

    Khớp khi thuật ngữ nằm nguyên văn trong điều (không phân biệt hoa thường,
    đã gộp khoảng trắng), trùng một hypernym đã map, hoặc KHỚP GẦN (điều chứa
    biến thể thiếu 1-2 token của thuật ngữ — `_khop_gan`, T28). Nguyên văn xếp
    trước khớp gần khi phải cắt theo `gioi_han`; cắt có ghi chú (không cắt im
    lặng); thuật ngữ dài bẩn (cả câu, đo 16/08 có bản ghi 352 ký tự) tự rơi vì
    không bao giờ khớp.
    """
    low = " ".join(text_dieu_hd.lower().split())
    hyp = {h.hypernym.lower() for h in hypernyms}
    chinh: list[KhaiNiem] = []
    gan: list[KhaiNiem] = []
    for k in pg.khai_niem:
        tn = " ".join(k.thuat_ngu.lower().split())
        if not tn:
            continue
        if tn in low or tn in hyp:
            chinh.append(k)
        elif _khop_gan(tn, low):
            gan.append(k)
    ghi_chu = []
    if gan:
        ghi_chu.append(
            "định nghĩa khớp gần (điều thiếu 1-2 từ của thuật ngữ): "
            + ", ".join(k.id for k in gan)
        )
    khop = chinh + gan
    if len(khop) > gioi_han:
        ghi_chu.append(
            f"định nghĩa: khớp {len(khop)}, chỉ đưa {gioi_han} đầu vào judge"
        )
    return khop[:gioi_han], ghi_chu


def lap_cu_plan(
    text_dieu_hd: str, hypernyms: list[DeXuat], pg: PolicyGraph,
    against_ids: list[str], as_of: str, so_hieu_cua: dict[str, str],
) -> CUPlan:
    cands = _ung_vien(text_dieu_hd, hypernyms, pg, against_ids, as_of, so_hieu_cua)
    plan = _ap_meta_va_dong_goi(cands, {h.hypernym for h in hypernyms}, pg, as_of)
    plan.dinh_nghia, ghi_chu_dn = khai_niem_lien_quan(text_dieu_hd, hypernyms, pg)
    plan.ghi_chu += ghi_chu_dn
    return plan


_HD_TOAN_VAN_RE = re.compile(r"hợp đồng|thỏa thuận")


def lap_plan_toan_van(pg: PolicyGraph, against_so_hieu: list[str], as_of: str) -> CUPlan:
    """CU ràng buộc NỘI DUNG hợp đồng — gate ở mức TOÀN văn bản, không qua retrieval.

    Vì sao tồn tại: CU dạng "hợp đồng phải có tối thiểu…" (TT40-Đ8) chỉ bắt được
    theo từng điều khi retrieval may mắn — điều hợp đồng quá ngắn (243 ký tự, nội
    dung thật ở Phụ lục) thì chunk luật không vào top-k và CU không bao giờ thành
    ứng viên (miss #194, đo 13/08). Ứng viên ở đây chọn TẤT ĐỊNH: điều luật có ≥1
    actor-CU mà CHỦ THỂ là "hợp đồng/thỏa thuận" thì CẢ điều vào plan (giữ trọn danh
    sách nội dung tối thiểu); meta-gate vẫn áp như `lap_cu_plan`. Chỉ xét subject —
    nghĩa vụ của tổ chức có nhắc hợp đồng trong action ("phải có thỏa thuận…",
    TT15-Đ20-k1) vẫn thuộc gate theo điều; đo 16/08 trên 61 CU: subject-only chọn
    đúng 2 điều nội-dung-hợp-đồng (TT40-Đ8, TT18-Đ9), nới sang action thì 5 điều.
    Không có hypernym ở mức toàn văn → cổng chủ thể phủ định fail-open kèm cờ.
    """
    so_hieu = set(against_so_hieu)
    dieu_hd: set[str] = set()
    for cid, cu in pg.cu.items():
        if not isinstance(cu, ActorCU) or cid.split("#")[0] not in so_hieu:
            continue
        if _HD_TOAN_VAN_RE.search((cu.subject.text + " " + cu.subject.label).lower()):
            dieu_hd.add(dieu_prefix(cid))
    cands: dict[str, tuple[ComplianceUnit, str]] = {
        cid: (cu, f"CU mức hợp đồng ({dieu_prefix(cid)} nhắc 'hợp đồng/thỏa thuận')")
        for cid, cu in pg.cu.items()
        if isinstance(cu, ActorCU) and dieu_prefix(cid) in dieu_hd
    }
    return _ap_meta_va_dong_goi(cands, set(), pg, as_of)
