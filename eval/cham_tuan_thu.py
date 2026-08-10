"""Chấm `review.py` — đường đối chiếu tuân thủ. Thuần hàm, kiểm được bằng unit test.

Bộ nhãn `eval/tuan_thu_vang.jsonl` cố ý **nhỏ và sạch**: 5 mục nội bộ có mâu thuẫn cài sẵn
(cùng nguồn với `mau_thuan_vang.jsonl`, đã xác minh tay trong corpus) + 2 mục đối chứng thuần
chính sách phí. 7 mục còn lại của 4 văn bản SHB **không có nhãn** vì không ai từng phát biểu
verdict đúng cho chúng — tự gán nhãn rồi tự chấm là tự chấm bài của mình, phép đo mất giá trị.

Ba mức, không phải hai. `warning` là **nửa đúng** ở cả hai chiều: với một vi phạm thật, nó bắt
được mùi nhưng không dám kết luận; với một mục sạch, nó làm phiền người rà soát mà chưa tới
mức báo sai. Gộp `warning` vào "đúng" hay "sai" đều bóp méo.

`not_assessed` đứng riêng, KHÔNG tính là sai. Đó là thiết kế có chủ đích của `review.py` —
"không biết" phải khác "đạt" — nên đo nó như một đại lượng riêng: tỷ lệ bỏ trống cao nghĩa là
truy hồi không tìm ra căn cứ, một vấn đề khác hẳn với phán định sai.
"""
from __future__ import annotations

import json
from pathlib import Path

VANG = Path("eval/tuan_thu_vang.jsonl")

NOT_ASSESSED = "not_assessed"


def doc_vang(duong_dan: Path = VANG) -> list[dict]:
    return [
        json.loads(x) for x in duong_dan.read_text(encoding="utf-8").splitlines() if x.strip()
    ]


def xep_loai(vang: str, thuc: str) -> str:
    """Một phán định rơi vào ô nào: `dung` · `nua_dung` · `sai` · `chua_danh_gia`."""
    if thuc == NOT_ASSESSED:
        return "chua_danh_gia"
    if thuc == vang:
        return "dung"
    if thuc == "warning":
        return "nua_dung"
    return "sai"


def cham(vang: list[dict], phan_dinh: dict[str, str]) -> dict:
    """`phan_dinh`: `{"{doc_id}::{article}": verdict}` lấy từ `run_review`.

    Mục có nhãn mà không có phán định (văn bản chưa chạy) bị **bỏ khỏi mẫu số** — khác hẳn
    việc chấm nó là sai.
    """
    o: dict[str, list[dict]] = {"dung": [], "nua_dung": [], "sai": [], "chua_danh_gia": []}
    thieu: list[str] = []
    for c in vang:
        thuc = phan_dinh.get(c["noi_bo"])
        if thuc is None:
            thieu.append(c["noi_bo"])
            continue
        o[xep_loai(c["verdict"], thuc)].append({**c, "thuc": thuc})
    n = sum(len(v) for v in o.values())
    return {
        "n_cham": n,
        "thieu_phan_dinh": thieu,
        "dung": len(o["dung"]),
        "nua_dung": len(o["nua_dung"]),
        "sai": len(o["sai"]),
        "chua_danh_gia": len(o["chua_danh_gia"]),
        # Mẫu số loại `chua_danh_gia`, cùng cách `review._score` loại nó khỏi điểm.
        "ty_le_dung": (
            round(len(o["dung"]) / (n - len(o["chua_danh_gia"])), 3)
            if n - len(o["chua_danh_gia"]) else None
        ),
        "chi_tiet": o,
    }


def bo_sot_vi_pham(kq: dict) -> list[dict]:
    """Ca nguy hiểm nhất: nhãn `violation` mà hệ thống nói `pass`.

    Tách riêng vì nó KHÔNG cùng loại với một cảnh báo thừa. Nói "đạt" về một quy định nội bộ
    trái luật là đúng thứ sản phẩm này sinh ra để chặn.
    """
    return [
        x for x in kq["chi_tiet"]["sai"] if x["verdict"] == "violation" and x["thuc"] == "pass"
    ]
