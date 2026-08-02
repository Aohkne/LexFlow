"""Bộ 5 case bắt buộc cho bước PHÂN LOẠI — in bảng kỳ vọng vs thực tế + ghi JSON.

    uv run python -m eval.ontology.classify_testset

Không gọi LLM một lần nào: cả 5 case chạy bằng luật tất định trong
`app/ontology/classify.py`. Bốn case đầu chạy trên VĂN BẢN THẬT trong
`data/fixtures/`; case 5 là câu giả định do đề bài nêu, được đánh dấu rõ.

Đọc kèm `docs/ONTOLOGY-CLASSIFY.md` — chỗ đó ghi các case mơ hồ và lý do chọn.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.ontology.classify import UnitCtx, classify_khoan, classify_unit
from app.ontology.parser import khoan_de_trich, parse_dieu

_DIR = Path("data/fixtures")
_INDEX = _DIR / "_index.json"
_OUT = Path("eval/ontology/classify_testset.json")


def _dieu(name: str):
    idx = json.loads(_INDEX.read_text(encoding="utf-8"))
    return parse_dieu((_DIR / name).read_text(encoding="utf-8"), idx[name])


def _khoan(name: str, so: str):
    dieu = _dieu(name)
    k = next(k for k in khoan_de_trich(dieu) if k.so_hien_thi == so)
    return dieu, k


def _cong(v) -> str:
    """Mô tả cổng + mốc ngày ở dạng cấu trúc — chỗ để bộ test bắt buộc soi được Θ."""
    if not v.gates:
        return "(không có cổng)"
    out = f"{v.gates[0].kind}/{v.gates[0].pham_vi}"
    if v.dieu_kien_cong:
        out += f" {v.dieu_kien_cong.ngay or '(không có ngày)'}"
    return out


def _row(ma, don_vi, nguon, ky_vong, v, them_ky_vong="", them_thuc_te="") -> dict:
    return {
        "case": ma,
        "don_vi": don_vi,
        "nguon": nguon,
        "ky_vong": ky_vong,
        "thuc_te": v.type,
        "khop": v.type == ky_vong and them_thuc_te.startswith(them_ky_vong),
        "them_ky_vong": them_ky_vong,
        "them_thuc_te": them_thuc_te,
        "test_path": v.test_path,
        "rationale": v.rationale,
        "warnings": v.warnings,
    }


def case_1() -> list[dict]:
    """ND52 Điều 2 "Đối tượng áp dụng" — 4 khoản, khoản 4 có bí danh "khách hàng"."""
    dieu = _dieu("ND52-2024-dieu2.txt")
    rows = []
    for k in khoan_de_trich(dieu):
        v = classify_khoan(k, dieu)
        alias_kv = "khách hàng" if k.so_hien_thi == "4" else ""
        rows.append(_row("1", f"Điều 2 khoản {k.so_hien_thi}", "ND52-2024-dieu2.txt",
                         "premise", v, alias_kv, v.alias or ""))
    return rows


def case_2() -> list[dict]:
    """Mệnh đề hiệu lực → meta-CU, cổng thời gian phủ cả văn bản.

    Đề bài viết "kể từ ngày 01 tháng 7 năm 2024"; luật thật (ND52 Điều 37 khoản 1)
    viết "**từ** ngày". Chạy cả hai để chứng minh bộ dò không gán chết một biến thể.
    """
    dieu, k = _khoan("ND52-2024-dieu37.txt", "1")
    v = classify_khoan(k, dieu)
    rows = [_row("2", "Điều 37 khoản 1", "ND52-2024-dieu37.txt", "meta_cu", v,
                 "thoi_gian/van_ban 2024-07-01", _cong(v))]

    cau = "Nghị định này có hiệu lực thi hành kể từ ngày 01 tháng 7 năm 2024"
    vp = classify_unit(cau, UnitCtx(dieu_id="52/2024/NĐ-CP#than/dieu_37",
                                    dieu_so=37, dieu_so_hien_thi="37",
                                    dieu_tieu_de="Hiệu lực thi hành", khoan_so="1"))
    rows.append(_row("2b", 'diễn đạt "kể từ ngày" của đề bài', "(chuỗi trong đề bài)",
                     "meta_cu", vp, "thoi_gian/van_ban 2024-07-01", _cong(vp)))
    return rows


def case_3() -> list[dict]:
    """ND52 Điều 22 khoản 2 — chapeau + điểm a..h, neo ở Khoản."""
    dieu, k = _khoan("ND52-2024-dieu22.txt", "2")
    v = classify_khoan(k, dieu)
    return [_row("3", "Điều 22 khoản 2", "ND52-2024-dieu22.txt", "actor_cu", v,
                 f"{len(k.diem)} điểm con", f"{len(k.diem)} điểm con")]


def case_4() -> list[dict]:
    """TT17 Điều 16 khoản 2 — điểm b có thêm một cấp tiết (i)/(ii)."""
    dieu, k = _khoan("TT17-2024-dieu16.txt", "2")
    v = classify_khoan(k, dieu)
    diem_b = next((d for d in k.diem if d.so_hien_thi == "b"), None)
    n_tiet = len(diem_b.tiet) if diem_b else 0
    # So sánh theo NGƯỠNG chứ không theo chuỗi: kỳ vọng là "có cấp tiết lồng bên
    # trong điểm", đúng bao nhiêu tiết là chi tiết của văn bản.
    return [_row("4", "Điều 16 khoản 2 (điểm b có tiết)", "TT17-2024-dieu16.txt",
                 "actor_cu", v, "điểm b có ≥2 tiết",
                 f"điểm b có ≥2 tiết (thực tế {n_tiet})" if n_tiet >= 2
                 else f"điểm b chỉ có {n_tiet} tiết")]


def case_5() -> list[dict]:
    """Câu GIẢ ĐỊNH của đề bài — không trích từ văn bản thật, chỉ để thử role gate."""
    cau = ("Quy định tại Mục này chỉ áp dụng đối với tổ chức đã được Ngân hàng Nhà "
           "nước cấp Giấy phép hoạt động cung ứng dịch vụ trung gian thanh toán.")
    v = classify_unit(cau, UnitCtx(dieu_id="52/2024/NĐ-CP#than/dieu_20",
                                   dieu_so=20, dieu_so_hien_thi="20",
                                   dieu_tieu_de="Điều kiện cung ứng dịch vụ",
                                   khoan_so="1"))
    return [_row("5", "câu giả định về phạm vi Mục", "(chuỗi trong đề bài — KHÔNG phải luật)",
                 "meta_cu", v, "chu_the/muc", _cong(v))]


CASES = [case_1, case_2, case_3, case_4, case_5]


def main() -> int:
    rows: list[dict] = []
    for fn in CASES:
        rows += fn()

    w = max(len(r["don_vi"]) for r in rows) + 2
    print(f"{'case':6}{'đơn vị':{w}}{'kỳ vọng':11}{'thực tế':11}{'':4}kiểm tra phụ")
    print("-" * (28 + w + 34))
    for r in rows:
        dau = "OK " if r["khop"] else "SAI"
        phu = ""
        if r["them_ky_vong"] or r["them_thuc_te"]:
            phu = (f"{r['them_thuc_te'] or '(rỗng)'}"
                   if r["them_thuc_te"].startswith(r["them_ky_vong"])
                   else f"cần {r['them_ky_vong']!r}, có {r['them_thuc_te']!r}")
        print(f"{r['case']:6}{r['don_vi']:{w}}{r['ky_vong']:11}{r['thuc_te']:11}{dau:4}{phu}")

    print("\n--- đường đi 3 phép thử ---")
    for r in rows:
        print(f"[{r['case']}] {r['don_vi']}")
        for b in r["test_path"]:
            print(f"     {b}")
        for wmsg in r["warnings"]:
            print(f"     [cảnh báo] {wmsg}")

    sai = [r for r in rows if not r["khop"]]
    print(f"\n→ {len(rows) - len(sai)}/{len(rows)} khớp kỳ vọng")
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[eval] Đã ghi {_OUT}")
    return 1 if sai else 0


if __name__ == "__main__":
    raise SystemExit(main())
