"""Chuyển bộ hỏi-đáp thuvienphapluat.vn (`data/evaluate/`) thành bộ câu hỏi eval của LexFlow.

Bộ gốc **không có trường ngày** — 251 dòng đúng 9 khoá, không khoá nào là thời điểm bài viết.
Nhưng không cần ngày đăng bài: mốc chặt hơn suy được từ chính corpus, là **giao các khoảng hiệu
lực** của mọi văn bản mà câu đó dẫn. Đó đúng bằng khoảng thời gian mà nhãn vàng của TVPL còn
đúng — nếu bài viết dẫn TT23-2014 thì nhãn ấy chỉ đúng trong `[2014-10-15, 2024-07-01)`, bất kể
bài được viết ngày nào.

Sinh ra HAI bộ từ cùng một tập câu, không gán nhãn tay dòng nào:

| Bộ | `as_of` | Nhãn vàng | Đo cái gì |
|---|---|---|---|
| `bo_tvpl_dung_thoi.jsonl` | ngày cuối cửa sổ | `relevant_docs`/`relevant_articles` của TVPL | truy hồi đúng luật **tại thời điểm đó** |
| `bo_tvpl_hien_nay.jsonl` | hôm nay | `relevant_docs` = văn bản kế thừa; `must_not_doc` = văn bản cũ | có bỏ luật đã chết và chuyển sang luật thay thế không |

Bộ thứ hai là chỗ LexFlow tách khỏi mọi baseline của bài báo SBV-LawGraph: BM25 / Naive RAG /
Advanced RAG không có khái niệm `as_of` nên trả **cùng một kết quả** ở cả hai bộ.

**Nhãn của bộ thứ hai là SUY DIỄN, không phải nhãn người.** Nó lấy từ cạnh `THAY_THE` trong
corpus, mà thay thế ở cấp văn bản không đảm bảo từng điều ánh xạ 1-1: một khoản có thể chuyển
sang văn bản khác hoặc bị bỏ hẳn. Vì thế bộ này **chỉ mang nhãn cấp văn bản**, cố ý không có
`relevant_articles` — xem `docs/EVAL-IR.md`.

Chạy:
    uv run python eval/chuyen_tvpl.py
    uv run python -u eval/run_benchmark.py --bo eval/bo_tvpl_dung_thoi.jsonl --bo eval/bo_tvpl_hien_nay.jsonl
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
NGUON = GOC / "data/evaluate/eval_filtered_clean.jsonl"
CORPUS = GOC / "data/corpus.real.json"
RA_DUNG_THOI = GOC / "eval/bo_tvpl_dung_thoi.jsonl"
RA_HIEN_NAY = GOC / "eval/bo_tvpl_hien_nay.jsonl"

#: Không có `valid_to` = còn hiệu lực. Dùng một mốc xa để so sánh chuỗi ngày cho đồng nhất.
XA = "9999-12-31"

_SO_HIEU = re.compile(r"^\d+/\d{4}/[A-ZĐ]+(?:-[A-ZĐ]+)*")
_SO_DIEU = re.compile(r"(\d+[a-zđ]?)")


def chuan_so_hieu(s: str) -> str:
    """Chuẩn hoá số hiệu về dạng so khớp được với `so_hieu` trong corpus.

    `law_label` của bộ gốc được tách từ slug URL nên còn dính đuôi chữ thường
    ("23/2014/TT-NHNN-huong-dan-mo..."). Phải cắt đuôi **trước** khi viết hoa: viết hoa trước
    thì "huong" thành "HUONG" và không còn phân biệt được với ký hiệu cơ quan ban hành.

    Xoá sạch khoảng trắng trước khi khớp regex: vbpl.vn để lọt dấu cách vào giữa số hiệu
    ("21/2017/TT- NHNN", "81 /2025/TT- NHNN" — gặp thật khi cào 12/08). Regex dừng ở dấu cách
    nên không xoá thì "21/2017/TT- NHNN" còn "21/2017/TT", không khớp nhãn nào và cũng không
    ném lỗi — văn bản lặng lẽ biến mất khỏi mọi phép nối. Số hiệu không bao giờ chứa dấu cách
    có nghĩa, nên xoá hết là an toàn; chuỗi không có dấu cách thì đây là phép đồng nhất, không
    đụng tới ca đuôi slug ở trên.
    """
    sach = re.sub(r"\s+", "", s)
    m = _SO_HIEU.match(sach)
    # Cả hai nhánh đều dùng bản đã xoá khoảng trắng: nhánh dự phòng ăn chuỗi viết thường (nhãn
    # bộ SBV), mà chuỗi đó cũng có thể dính dấu cách — trả `s` gốc thì lỗi im lặng quay lại.
    return (m.group(0) if m else sach).upper().replace("Đ", "D")


def tra_cuu(corpus: dict) -> tuple[dict[str, str], dict[str, tuple[str, str]], dict[str, str]]:
    """corpus → (số hiệu→doc_id, doc_id→khoảng hiệu lực, doc_id cũ→doc_id thay thế)."""
    so_hieu2id, hieu_luc = {}, {}
    for d in corpus["documents"]:
        if d.get("so_hieu"):
            so_hieu2id[chuan_so_hieu(d["so_hieu"])] = d["doc_id"]
        hieu_luc[d["doc_id"]] = (d.get("valid_from") or "0000-01-01", d.get("valid_to") or XA)

    thay_the: dict[str, list[str]] = {}
    for r in corpus.get("relationships", []):
        if r.get("rel_type") == "THAY_THE":
            thay_the.setdefault(r["target_doc"], []).append(r["source_doc"])
    # Nhiều văn bản cùng thay thế một văn bản thì không suy được cái nào là kế thừa — bỏ, đừng đoán.
    ke_thua = {cu: moi[0] for cu, moi in thay_the.items() if len(moi) == 1}
    return so_hieu2id, hieu_luc, ke_thua


def cua_so(doc_ids: list[str], hieu_luc: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    """Giao các khoảng `[valid_from, valid_to)`. `None` khi giao rỗng.

    Giao rỗng nghĩa là bài viết dẫn các văn bản chưa từng cùng hiệu lực — nhãn vàng của nó
    không đúng ở bất kỳ thời điểm nào, nên câu đó phải bị loại chứ không phải gán bừa một mốc.
    """
    tu = max(hieu_luc[d][0] for d in doc_ids)
    den = min(hieu_luc[d][1] for d in doc_ids)
    return (tu, den) if tu < den else None


def _nhan_dieu(article: str | None) -> str | None:
    """`"Dieu 11"` → `"Điều 11"`. Bộ gốc bỏ dấu trong trường này."""
    if not article:
        return None
    m = _SO_DIEU.search(article)
    return f"Điều {m.group(1)}" if m else None


def truoc_mot_ngay(ngay: str) -> str:
    """Ngày cuối cùng nhãn vàng còn đúng — `valid_to` là mốc **mở**, nên phải lùi một ngày."""
    return (date.fromisoformat(ngay) - timedelta(days=1)).isoformat()


def chuyen(rows: list[dict], corpus: dict, hom_nay: str) -> tuple[list[dict], list[dict], Counter]:
    so_hieu2id, hieu_luc, ke_thua = tra_cuu(corpus)
    dung_thoi, hien_nay, bo = [], [], Counter()

    for r in rows:
        refs = [
            x for x in (r.get("reference_parsed") or [])
            if not x.get("is_topic_tag_page") and x.get("law_label")
        ]
        if not refs:
            bo["không dẫn văn bản nào"] += 1
            continue

        labs = {chuan_so_hieu(x["law_label"]) for x in refs}
        ngoai = labs - set(so_hieu2id)
        if ngoai:
            bo["dẫn văn bản ngoài corpus"] += 1
            continue

        docs = sorted({so_hieu2id[lab] for lab in labs})
        cs = cua_so(docs, hieu_luc)
        if cs is None:
            bo["các văn bản không cùng hiệu lực (cửa sổ rỗng)"] += 1
            continue
        tu, den = cs

        arts = sorted({
            f"{so_hieu2id[chuan_so_hieu(x['law_label'])]}::{nhan}"
            for x in refs
            if (nhan := _nhan_dieu(x.get("article")))
        })

        chung = {
            "query": r["question"],
            "group": (r.get("category") or ["tvpl"])[0],
            "questionoid": r.get("questionoid"),
            "nguon": "tvpl",
            "cua_so": [tu, None if den == XA else den],
        }
        dung_thoi.append({
            **chung,
            # Ngày cuối cửa sổ: mốc chặt nhất mà nhãn vàng còn đúng. Văn bản chưa hết hiệu lực
            # thì cửa sổ mở tới nay, lấy luôn hôm nay.
            "as_of": truoc_mot_ngay(den) if den != XA else hom_nay,
            "expected_doc": docs[0],
            "relevant_docs": docs,
            "relevant_articles": arts,
        })

        # Bộ "hiện nay" chỉ có nghĩa với câu mà luật của nó ĐÃ chết và có văn bản kế thừa rõ ràng.
        if den == XA or den > hom_nay:
            bo["luật còn hiệu lực, không có mặt lỗi thời để đo"] += 1
            continue
        moi = sorted({ke_thua[d] for d in docs if d in ke_thua})
        if len(moi) != len(docs):
            bo["thiếu cạnh THAY_THE để suy văn bản kế thừa"] += 1
            continue
        hien_nay.append({
            **chung,
            "as_of": hom_nay,
            "expected_doc": moi[0],
            "relevant_docs": moi,
            # KHÔNG có `relevant_articles`: THAY_THE là quan hệ cấp văn bản, suy xuống cấp điều
            # là bịa. Bộ này cố ý chỉ đo được ở mức văn bản.
            "must_not_doc": docs[0],
            "nhan_suy_dien": "THAY_THE",
        })

    return dung_thoi, hien_nay, bo


def ghi_jsonl(duong_dan: Path, rows: list[dict]) -> None:
    duong_dan.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def main() -> None:
    rows = [
        json.loads(dong)
        for dong in NGUON.read_text(encoding="utf-8").splitlines()
        if dong.strip()
    ]
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    dung_thoi, hien_nay, bo = chuyen(rows, corpus, date.today().isoformat())

    ghi_jsonl(RA_DUNG_THOI, dung_thoi)
    ghi_jsonl(RA_HIEN_NAY, hien_nay)

    print(f"nguồn: {len(rows)} câu")
    print(f"  → {RA_DUNG_THOI.name}: {len(dung_thoi)} câu")
    print(f"  → {RA_HIEN_NAY.name}: {len(hien_nay)} câu (nhãn suy từ cạnh THAY_THE)")
    print("bỏ:")
    for ly_do, n in bo.most_common():
        print(f"  {n:4d}  {ly_do}")


if __name__ == "__main__":
    main()
