"""Chuyển bộ test của bài báo SBV-LawGraph thành bộ câu hỏi eval của LexFlow.

Nguồn: `data/evaluate/svb_graph/sbv_testset_tvpl.json` — 100 câu, nhãn dạng
`"12/2022/tt-nhnn_3"` = số hiệu + số điều, tức **nhãn cấp điều trên 100% câu**.

Sinh HAI file, không gán nhãn tay dòng nào:

| File | Nội dung | Ai dùng |
|---|---|---|
| `eval/bo_sbv.jsonl` | câu mà corpus phủ đủ văn bản | `run_benchmark.py`, `quet_trong_so.py` |
| `eval/bo_sbv_khong_can_cu.jsonl` | câu dẫn văn bản corpus KHÔNG có | T17 (ngưỡng τ), chưa chạy |

**File thứ hai KHÔNG chạy được bằng `run_benchmark`** — nó không có nhãn vàng nên mọi mức IR bỏ
qua nó (`run_benchmark._tong_hop_ir`). Chạy rồi tưởng hệ điểm 0 là đọc sai. Nó là dữ liệu cho
T17: câu hỏi mà câu trả lời đúng là "không đủ căn cứ".

Chạy:
    uv run python eval/chuyen_sbv.py
    uv run python -u eval/run_benchmark.py --bo eval/bo_sbv.jsonl
"""
from __future__ import annotations

import re
from collections import Counter

from eval.chuyen_tvpl import XA, chuan_so_hieu, cua_so, tra_cuu, truoc_mot_ngay

_SO_DIEU = re.compile(r"^\d+[a-zđ]?$")
_DIEU_TRONG_NHAN = re.compile(r"^Điều\s+(\d+[a-zđ]?)")


class NhanHong(ValueError):
    """Nhãn không đúng dạng `{số hiệu}_{số điều}`.

    Ném chứ không bỏ qua: nhãn hỏng là lỗi định dạng của file nguồn, khác hẳn "câu này dẫn văn
    bản ngoài corpus". Trộn hai thứ vào một nhánh bỏ-qua là cách mất dữ liệu êm nhất.
    """


def tach_nhan(nhan: str) -> tuple[str, str]:
    """`"12/2022/tt-nhnn_3"` → `("12/2022/TT-NHNN", "3")`.

    Tách từ **phải** (`rpartition`): hậu tố là số điều, số hiệu ở trước và bản thân nó chứa dấu
    gạch. Tách từ trái thì `"08/2023/tt-nhnn_21"` ra `"2"`.

    Số hiệu đi qua `chuan_so_hieu` ở dạng **thô, chữ thường**. Ở đó regex cắt đuôi slug
    (`^\\d+/\\d{4}/[A-ZĐ]+…`) sẽ KHÔNG khớp chuỗi thường, nên hàm rơi vào nhánh dự phòng
    `.upper().replace("Đ","D")` — và đó đúng là điều ta cần, vì định dạng SBV **không có đuôi
    slug** để cắt. Đừng "sửa" bằng cách viết hoa trước khi gọi: đuôi slug viết hoa lên thì regex
    nuốt luôn nó, đúng lỗi đã gặp 11/08. Cũng đừng thêm `re.IGNORECASE` vào regex đó vì cùng lý do.
    """
    so_hieu, sep, so_dieu = nhan.rpartition("_")
    if not sep or not _SO_DIEU.match(so_dieu):
        raise NhanHong(f"nhãn {nhan!r} không đúng dạng {{số hiệu}}_{{số điều}}")
    return chuan_so_hieu(so_hieu), so_dieu


def dieu_co_that(corpus: dict) -> dict[str, set[str]]:
    """`doc_id` → tập **số điều** có thật trong corpus.

    Gom về số điều chứ không giữ nhãn nguyên văn: `pipeline._split_khoan` chẻ một điều dài thành
    `"Điều 23 Khoản 1-3"` / `"Điều 23 Khoản 4-6"`, nên so khớp nguyên văn sẽ coi mọi điều dài là
    không tồn tại và loại sạch những câu hỏi đáng giá nhất.
    """
    ra: dict[str, set[str]] = {}
    for d in corpus["documents"]:
        so: set[str] = set()
        for a in d.get("articles", []):
            m = _DIEU_TRONG_NHAN.match(a.get("article", ""))
            if m:
                so.add(m.group(1))
        ra[d["doc_id"]] = so
    return ra


def chuyen(
    rows: list[dict], corpus: dict, hom_nay: str
) -> tuple[list[dict], list[dict], Counter]:
    """100 câu nguồn → (bộ dùng được, bộ không căn cứ, đếm lý do bị loại).

    Ba nhánh, và ba nhánh đó phải cộng lại đúng bằng số câu vào — kiểm ở `main()`. Một câu biến
    mất im lặng làm mẫu số nhỏ đi mà bảng vẫn trông bình thường.
    """
    so_hieu2id, hieu_luc, _ = tra_cuu(corpus)
    co_that = dieu_co_that(corpus)
    dung: list[dict] = []
    khong_can_cu: list[dict] = []
    bo: Counter = Counter()

    for r in rows:
        cap = [tach_nhan(a) for a in (r.get("relevant_articles") or [])]
        if not cap:
            bo["không có nhãn"] += 1
            continue

        labs = {lab for lab, _ in cap}
        thieu = sorted(labs - set(so_hieu2id))
        if thieu:
            # Negative sạch: không văn bản nào trong câu này có mặt trong corpus. Câu trả lời
            # đúng là "không đủ căn cứ" — dữ liệu cho T17, không phải câu bị hỏng.
            khong_can_cu.append({
                "query": r["question"],
                "question_id": r["question_id"],
                "van_ban_thieu": thieu,
                "nguon": "sbv",
            })
            continue

        docs = sorted({so_hieu2id[lab] for lab in labs})
        cs = cua_so(docs, hieu_luc)
        if cs is None:
            bo["các văn bản không cùng hiệu lực (cửa sổ rỗng)"] += 1
            continue
        tu, den = cs

        if any(sd not in co_that[so_hieu2id[lab]] for lab, sd in cap):
            bo["nhãn trỏ vào điều không có trong corpus"] += 1
            continue

        dung.append({
            "query": r["question"],
            "question_id": r["question_id"],
            "group": "sbv",
            "nguon": "sbv",
            # Tính từ cửa sổ chứ không hard-code hôm nay: khi một trong các văn bản bị thay thế,
            # `as_of` tự lùi về ngày cuối cửa sổ thay vì lặng lẽ sai.
            "as_of": truoc_mot_ngay(den) if den != XA else hom_nay,
            "cua_so": [tu, None if den == XA else den],
            "expected_doc": docs[0],
            "relevant_docs": docs,
            "relevant_articles": sorted(
                {f"{so_hieu2id[lab]}::Điều {sd}" for lab, sd in cap}
            ),
            # KHÔNG có `must_not_doc`: bộ này không có mặt lỗi thời nào để đo, nên
            # `stale_avoidance` sẽ bằng 1.0 và rỗng nghĩa — ghi rõ cạnh bảng, đừng tạo nhãn giả.
        })

    return dung, khong_can_cu, bo
