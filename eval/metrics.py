"""Metric truy hồi theo §5.3 của bài báo SBV-LawGraph (ACIIDS 2026): R@k, P@k, MRR@k, F2@k.

Vì sao cần tầng này: `run_benchmark.py` trước đây chỉ đo `citation_accuracy` (có/không trúng
`expected_doc`) và `stale_avoidance`. Hai số đó nói được "hệ có trả đúng văn bản không", nhưng
KHÔNG nói được **trúng ở hạng mấy** và **bỏ sót bao nhiêu** khi câu hỏi cần nhiều căn cứ — tức là
không so được với bảng nào của bài báo, và cũng không đo được một thay đổi retrieval có đáng làm.

Thuần hàm, không chạm mạng, không đọc file — mọi thứ ở đây kiểm được bằng unit test.
"""
from __future__ import annotations

import re

from app.knowledge.retrieval import khop_tien_to

#: Các mốc k báo cáo, đúng bộ của bài báo (Table 3): R@1, R@2, R@5, R@10, R@20.
CAC_MOC_K = (1, 2, 5, 10, 20)

#: Nhãn chunk mở đầu bằng địa chỉ cấp ĐIỀU: `"Điều 8"`, `"Điều 8 Khoản 1-6"`, `"Điều 8 (phần 2)"`.
_DIEU_RE = re.compile(r"^(Điều\s+\d+[a-zđ]?)")


def khoa_dieu(chunk: dict) -> str:
    """Chunk → khoá cấp ĐIỀU `"{doc_id}::Điều N"` để xếp hạng ở mức điều.

    `pipeline._split_khoan` chẻ một điều dài thành nhiều chunk (`"Điều 12 Khoản 1-3"`,
    `"Điều 12 Khoản 4-6"`). Đếm chúng như hai kết quả khác nhau thì `P@k` tụt chỉ vì văn bản
    dài — một tính chất của phép chẻ, không phải của chất lượng truy hồi. Gom về cấp điều rồi
    khử trùng theo thứ hạng là cách bài báo hiểu "top-k documents/articles".

    Nhãn không mở đầu bằng `"Điều N"` thì giữ nguyên: thà một khoá lạ còn hơn gộp nhầm hai
    đơn vị khác nhau vào một hạng.
    """
    doc_id = chunk.get("doc_id") or ""
    nhan = chunk.get("article") or ""
    m = _DIEU_RE.match(nhan)
    return f"{doc_id}::{m.group(1) if m else nhan}"


def _tach(khoa: str) -> tuple[str, str]:
    doc_id, _, nhan = khoa.partition("::")
    return doc_id, nhan


def trung(ket_qua: str, vang: str) -> bool:
    """Một khoá truy hồi có khớp một nhãn vàng không — khớp tiền tố HAI CHIỀU.

    Hai chiều vì nhãn vàng và nhãn chunk có thể ở hai độ mịn khác nhau, và cả hai đều đúng:

    - vàng `"TT40-2024::Điều 12"` ↔ chunk `"TT40-2024::Điều 12 Khoản 1"` — chunk nằm TRONG điều vàng.
    - vàng `"TT40-2024::Điều 12 Khoản 1"` ↔ chunk `"TT40-2024::Điều 12"` — điều được trả về CHỨA
      khoản vàng (điều ngắn không bị chẻ thì chunk chính là cả điều).

    Ranh giới tiền tố mượn `retrieval.khop_tien_to`, không chép lại: hai luật lệch nhau thì tầng
    đo và tầng truy hồi sẽ bất đồng về việc `"Điều 3"` có khớp `"Điều 30"` hay không.
    """
    if ket_qua == vang:
        return True
    d1, n1 = _tach(ket_qua)
    d2, n2 = _tach(vang)
    if d1 != d2 or not n1 or not n2:
        return False
    return khop_tien_to(n1, n2) or khop_tien_to(n2, n1)


def _khu_trung(khoa: list[str]) -> list[str]:
    """Giữ lần xuất hiện ĐẦU TIÊN — thứ hạng của một khoá là hạng cao nhất nó đạt được."""
    da_co: set[str] = set()
    ra: list[str] = []
    for k in khoa:
        if k not in da_co:
            da_co.add(k)
            ra.append(k)
    return ra


def hang_dau_tien(khoa: list[str], vang: list[str]) -> int | None:
    """Hạng (đếm từ 1) của kết quả liên quan ĐẦU TIÊN; `None` nếu không có kết quả nào trúng."""
    for i, k in enumerate(_khu_trung(khoa), start=1):
        if any(trung(k, v) for v in vang):
            return i
    return None


def f2(precision: float, recall: float) -> float:
    """F2 = 5·P·R / (4·P + R) — nghiêng về recall, đúng công thức bài báo (§5.3).

    `P = R = 0` ⇒ 0 (mẫu số bằng 0), không phải lỗi chia: câu không trúng gì vẫn phải có mặt
    trong mẫu số của trung bình, nếu không thì bảng đẹp lên nhờ bỏ bớt câu khó.
    """
    mau = 4 * precision + recall
    return 0.0 if mau <= 0 else 5 * precision * recall / mau


def do_mot_cau(khoa: list[str], vang: list[str], k: int) -> dict[str, float]:
    """R@k, P@k, RR@k, F2@k cho MỘT câu hỏi.

    `khoa`  — khoá truy hồi theo thứ hạng (đã hoặc chưa khử trùng, hàm tự khử).
    `vang`  — nhãn vàng (`relevant_docs` hoặc `relevant_articles`).

    Tử số của cả recall lẫn precision là `|R̂k ∩ R|` theo bài báo, nhưng hai vế đếm hai thứ khác
    nhau khi có khớp tiền tố: recall đếm **nhãn vàng được phủ** (mẫu số `|R|`), precision đếm
    **vị trí trong top-k có liên quan** (mẫu số `k`). Với khớp chính xác 1-1 hai cách trùng nhau,
    đúng như định nghĩa gốc; với khớp tiền tố thì đây là cách duy nhất không cho ra tỷ lệ > 1.
    """
    if not vang:
        return {"recall": 0.0, "precision": 0.0, "rr": 0.0, "f2": 0.0}
    top = _khu_trung(khoa)[:k]
    phu = sum(1 for v in vang if any(trung(x, v) for x in top))
    lien_quan = sum(1 for x in top if any(trung(x, v) for v in vang))

    recall = phu / len(vang)
    precision = lien_quan / k
    hang = hang_dau_tien(khoa, vang)
    rr = 1 / hang if hang is not None and hang <= k else 0.0
    return {"recall": recall, "precision": precision, "rr": rr, "f2": f2(precision, recall)}


def tong_hop(theo_cau: list[dict[str, float]]) -> dict[str, float]:
    """Trung bình trên toàn bộ câu hỏi (macro-average, đúng như `MRR@k = 1/|Q| · Σ 1/rank`).

    **Hai cách tính F2, báo cáo cả hai.** Bài báo viết `F2@k = 5·P@k·R@k / (4·P@k + R@k)` với
    `P@k`/`R@k` là các số đã đứng trong cùng một hàng của Table 3 — tức là F2 tính TỪ hai trung
    bình (`f2`, dùng để so với bài báo). Trung bình của F2 từng câu (`f2_macro`) là một số khác,
    và là số đúng hơn khi các câu có `|R|` chênh nhau. Ghi cả hai để không ai phải đoán ô trong
    bảng được tính bằng đường nào.

    Danh sách rỗng ⇒ 0.0 ở mọi metric. Không trả `None`: bảng kết quả cần một ô đọc được, còn
    "không có câu nào" đã hiện ở cột `n` bên cạnh.
    """
    if not theo_cau:
        return {"recall": 0.0, "precision": 0.0, "mrr": 0.0, "f2": 0.0, "f2_macro": 0.0}
    n = len(theo_cau)
    recall = sum(c["recall"] for c in theo_cau) / n
    precision = sum(c["precision"] for c in theo_cau) / n
    return {
        "recall": recall,
        "precision": precision,
        "mrr": sum(c["rr"] for c in theo_cau) / n,
        "f2": f2(precision, recall),
        "f2_macro": sum(c["f2"] for c in theo_cau) / n,
    }
