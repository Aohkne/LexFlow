"""CLI thử nghiệm pipeline ontology.

Sinh fixture từ HTML gốc (không gọi LLM):
    uv run python -m app.ontology --from-html data/raw/ND52-2024.html --dieu 22,23,26

Xem cây cấu trúc + đơn vị đã tách (không gọi LLM):
    uv run python -m app.ontology data/fixtures/ND52-2024-dieu22.txt --no-llm --units 2

Trích Compliance Unit (cần GEMINI_API_KEY):
    uv run python -m app.ontology data/fixtures/ND52-2024-dieu22.txt --khoan 2 --html out.html
    uv run python -m app.ontology --batch data/fixtures --out eval/ontology/pred.jsonl

Lưu ý encoding: mọi file do CLI TỰ ghi bằng write_text(encoding="utf-8"). Không bao
giờ dùng redirect `>` của shell — PowerShell sẽ re-encode bằng codec riêng và làm
lệch toàn bộ char_span.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.ingestion.extract import _SO_HIEU_RE, read_text
from app.ontology.classify import classify_dieu_unit, classify_khoan
from app.ontology.extractor import (
    build_premise_record,
    extract_cu,
    extract_khai_niem,
    grounding_report,
)
from app.ontology.parser import clean_text, khoan_de_trich, parse_dieu, slice_dieu
from app.ontology.report import render
from app.ontology.roles import classify_dieu, is_van_ban_sua_doi
from app.ontology.schema import DieuNode
from app.ontology.segmenter import render_menu, segment

_FIXTURE_DIR = Path("data/fixtures")
_DEFAULT_SO_HIEU = "52/2024/NĐ-CP"
# Số hiệu của từng fixture, ghi lúc sinh. KHÔNG được dò lại từ thân Điều: các
# Thông tư đều trích dẫn "52/2024/NĐ-CP" nên regex sẽ bắt nhầm văn bản ĐƯỢC DẪN
# thay vì văn bản CHỨA nó → khoá node KG sai im lặng.
_INDEX = _FIXTURE_DIR / "_index.json"


def _print_tree(dieu: DieuNode) -> None:
    print(f"Điều {dieu.so_hien_thi}. {dieu.tieu_de}")
    print(f"  id={dieu.id}  span=[{dieu.start},{dieu.end})  {len(dieu.khoan)} khoản")
    for k in khoan_de_trich(dieu):
        diem = ", ".join(d.so_hien_thi for d in k.diem) or "(không chẻ điểm)"
        n = len(segment(dieu, k)) - 1  # trừ đơn vị [0] = tiêu đề Điều
        nhan = f"Khoản {k.so_hien_thi}" if k.so_hien_thi else "(thân điều, không chẻ khoản)"
        print(f"  - {nhan}: span=[{k.start},{k.end}), "
              f"{len(k.diem)} điểm → {diem} | {n} đơn vị")


def _print_report(cu) -> None:
    rows = grounding_report(cu)
    exact = sum(1 for r in rows if r["status"] == "exact")
    unit = sum(1 for r in rows if r["status"] == "unit")
    print(f"\n--- Neo bằng chứng ({cu.id}) ---")
    print(f"{'field':<22}{'neo':<10}{'đơn vị':<14}char_span")
    for r in rows:
        print(f"{r['field']:<22}{r['status']:<10}{str(r['units']):<14}{r['char_span']}")
    print(f"→ {exact} thu hẹp chính xác, {unit} ở mức đơn vị, "
          f"{len(rows) - exact - unit} MẤT provenance")
    for e in cu.errors:
        print(f"  [LỖI CỨNG] {e}")
    for w in cu.warnings:
        print(f"  [cảnh báo]  {w}")


def _read_index() -> dict[str, str]:
    if not _INDEX.exists():
        return {}
    return json.loads(_INDEX.read_text(encoding="utf-8"))


def _load_dieu(path: Path, so_hieu: str) -> DieuNode:
    """Nạp fixture. Số hiệu lấy từ _index.json, KHÔNG dò lại trong thân Điều."""
    text = path.read_text(encoding="utf-8")
    resolved = _read_index().get(path.name)
    if not resolved:
        print(f"  [cảnh báo] {path.name} chưa có trong {_INDEX} — dùng {so_hieu!r}")
        resolved = so_hieu
    return parse_dieu(text, resolved)


def _gen_fixtures(html: Path, dieu_list: list[int], so_hieu: str) -> list[Path]:
    raw = read_text(html)
    clean = clean_text(raw)
    # Dò trên TOÀN VĂN BẢN GỐC: số hiệu của chính văn bản nằm ở header, đứng trước
    # mọi trích dẫn văn bản khác. Đây là chỗ duy nhất được phép dò.
    found = _SO_HIEU_RE.search(raw)
    resolved = found.group() if found else so_hieu
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    index = _read_index()
    out: list[Path] = []
    for n in dieu_list:
        try:
            block = slice_dieu(clean, n)
        except ValueError as exc:
            print(f"  [bỏ qua] {exc}")
            continue
        path = _FIXTURE_DIR / f"{html.stem}-dieu{n}.txt"
        path.write_text(block, encoding="utf-8")
        index[path.name] = resolved
        out.append(path)
        print(f"[ontology] {path} ({len(block)} ký tự) — số hiệu {resolved}")
        _print_tree(parse_dieu(block, resolved))
    _INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True),
                      encoding="utf-8")
    return out


def _load_all(folder: Path, so_hieu: str) -> list[tuple[Path, DieuNode]]:
    return [(p, _load_dieu(p, so_hieu)) for p in sorted(folder.glob("*.txt"))]


def _sua_doi_map(loaded: list[tuple[Path, DieuNode]]) -> dict[str, bool]:
    """Văn bản nào là văn bản sửa đổi — cần Điều 1 để biết.

    Quy ước vị trí (Điều 1 = phạm vi, Điều 2 = đối tượng áp dụng) đo được đúng
    9/11 và 8/11; cả hai ngoại lệ đều là văn bản sửa đổi, nơi Điều 1 là "Sửa đổi,
    bổ sung một số điều của…". Nên phải biết để TẮT luật vị trí.
    """
    out: dict[str, bool] = {}
    for _, dieu in loaded:
        if dieu.so_goc == 1 and not dieu.so_hau_to:
            out[dieu.id.split("#", 1)[0]] = is_van_ban_sua_doi(dieu.tieu_de)
    return out


def _print_roles(loaded: list[tuple[Path, DieuNode]]) -> dict[str, str]:
    sua_doi = _sua_doi_map(loaded)
    print(f"{'fixture':26s}{'Điều':7s}{'vai':10s}{'nguồn':10s}tiêu đề")
    roles: dict[str, str] = {}
    for path, dieu in loaded:
        so_hieu = dieu.id.split("#", 1)[0]
        v = classify_dieu(dieu, van_ban_sua_doi=sua_doi.get(so_hieu, False))
        roles[path.name] = v.role
        print(f"{path.stem:26s}{dieu.so_hien_thi:7s}{v.role:10s}{v.nguon:10s}{dieu.tieu_de[:44]}")
        for w in v.warnings:
            print(f"    [cảnh báo] {w}")
    n = {r: sum(1 for x in roles.values() if x == r) for r in ("premise", "meta_cu", "actor_cu")}
    print(f"\n→ premise {n['premise']} · meta_cu {n['meta_cu']} · actor_cu {n['actor_cu']}")
    return roles


def _print_classify(loaded: list[tuple[Path, DieuNode]]) -> list[dict]:
    """Bảng phân loại mức ĐƠN VỊ (Khoản) — không gọi LLM một lần nào."""
    sua_doi = _sua_doi_map(loaded)
    rows: list[dict] = []
    print(f"{'đơn vị':44s}{'loại':10s}{'kind/gate':16s}alias · lý do")
    for path, dieu in loaded:
        sd = sua_doi.get(dieu.id.split("#", 1)[0], False)
        for k in khoan_de_trich(dieu):
            v = classify_khoan(k, dieu, van_ban_sua_doi=sd)
            nhan = f"{path.stem} k{k.so_hien_thi or '-'}"
            phu = v.premise_kind or (v.gates[0].pham_vi if v.gates else "")
            if v.dieu_kien_cong:
                phu += f" {v.dieu_kien_cong.ngay or '?'}"
            print(f"{nhan:44s}{v.type:10s}{phu:16s}"
                  f"{('«' + v.alias + '» ') if v.alias else ''}{v.rationale[:50]}")
            for w in v.warnings:
                print(f"    [cảnh báo] {w}")
            rows.append({"id": k.id, "fixture": path.name, **v.model_dump()})
    n = {t: sum(1 for r in rows if r["type"] == t) for t in ("premise", "meta_cu", "actor_cu")}
    print(f"\n→ {len(rows)} đơn vị: premise {n['premise']} · meta_cu {n['meta_cu']} "
          f"· actor_cu {n['actor_cu']}")
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="PoC trích Compliance Unit mức Khoản")
    ap.add_argument("file", nargs="?", help="file .txt chứa MỘT Điều đã làm sạch")
    ap.add_argument("--from-html", help="sinh fixture từ HTML gốc trong data/raw")
    ap.add_argument("--dieu", help="số Điều cần cắt, phân tách bằng dấu phẩy (với --from-html)")
    ap.add_argument("--batch", help="thư mục fixture: trích mọi khoản của mọi file")
    ap.add_argument("--roles", help="thư mục fixture: in bảng vai premise/meta_cu/actor_cu")
    ap.add_argument("--classify", help="thư mục fixture: in bảng phân loại mức KHOẢN (Test A/B/C)")
    ap.add_argument("--khoan", help="chỉ trích một khoản, ví dụ 2 (mặc định: tất cả)")
    ap.add_argument("--so-hieu", default=_DEFAULT_SO_HIEU, help="số hiệu dự phòng khi không dò được")
    ap.add_argument("--no-llm", action="store_true", help="chỉ in cấu trúc, không gọi Gemini")
    ap.add_argument("--units", help="in menu đơn vị của một khoản rồi thoát")
    ap.add_argument("--html", help="ghi trang HTML kiểm span")
    ap.add_argument("--html-dir", help="với --batch: ghi mỗi CU một trang HTML vào thư mục này")
    ap.add_argument("--out", help="ghi kết quả JSON/JSONL")
    args = ap.parse_args(argv)

    if args.from_html:
        if not args.dieu:
            ap.error("--from-html cần đi kèm --dieu")
        _gen_fixtures(Path(args.from_html), [int(x) for x in args.dieu.split(",")], args.so_hieu)
        return

    if args.roles:
        _print_roles(_load_all(Path(args.roles), args.so_hieu))
        return

    if args.classify:
        rows = _print_classify(_load_all(Path(args.classify), args.so_hieu))
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                encoding="utf-8",
            )
            print(f"[ontology] Đã ghi {args.out}")
        return

    if args.batch:
        rows: list[dict] = []
        kn_rows: list[dict] = []
        html_dir = Path(args.html_dir) if args.html_dir else None
        if html_dir:
            html_dir.mkdir(parents=True, exist_ok=True)
        pr_rows: list[dict] = []
        loaded = _load_all(Path(args.batch), args.so_hieu)
        sua_doi = _sua_doi_map(loaded)
        for path, dieu in loaded:
            so_hieu = dieu.id.split("#", 1)[0]
            sd = sua_doi.get(so_hieu, False)
            # Vai mức Điều vẫn tính để đối chứng; phân loại QUYẾT ĐỊNH nằm ở mức Khoản.
            dv = classify_dieu(dieu, van_ban_sua_doi=sd)
            du = classify_dieu_unit(dieu, van_ban_sua_doi=sd)
            gate_dieu = dieu.id if du.type == "meta_cu" and du.gates else None
            for k in khoan_de_trich(dieu):
                v = classify_khoan(k, dieu, van_ban_sua_doi=sd)
                if v.type != dv.role:
                    print(f"[ontology] {path.name} khoản {k.so_hien_thi}: "
                          f"vai Điều {dv.role!r} → vai Khoản {v.type!r}")
                print(f"[ontology] {path.name} khoản {k.so_hien_thi} ({v.type}) ...")

                if v.type == "premise":
                    # Điều/khoản premise KHÔNG sinh Compliance Unit — ép sinh thì ra
                    # "nghĩa vụ" không tồn tại. Đây là chỗ chặn CU rác.
                    pr = build_premise_record(k, dieu, v, gop_vao_gate=gate_dieu)
                    pr_rows.append({"fixture": str(path).replace("\\", "/"), **pr.model_dump()})
                    print(f"  → premise/{pr.premise_kind}"
                          + (f", bí danh {pr.alias!r}" if pr.alias else ""))
                    if v.premise_kind != "dinh_nghia":
                        continue  # phạm vi/vai trò không có thuật ngữ để trích
                    kn = extract_khai_niem(k, dieu)
                    if kn is None:
                        print("  → khoản này không định nghĩa thuật ngữ nào, bỏ qua")
                        continue
                    kn_rows.append({"fixture": str(path).replace("\\", "/"), **kn.model_dump()})
                    print(f"  → khái niệm: {kn.thuat_ngu[:60]!r}")
                    continue

                cu = extract_cu(
                    k, dieu, role=v.type, gates=v.gates,
                    dieu_kien_cong=v.dieu_kien_cong,
                )
                rows.append({"fixture": str(path).replace("\\", "/"), **cu.model_dump()})
                flag = "LỖI" if cu.errors else "ok"
                d = cu.dieu_kien_cong
                print(f"  → {flag}, {len(cu.conditions)} điều kiện, "
                      f"{len(cu.references)} viện dẫn, {len(cu.warnings)} cảnh báo"
                      + (f", cổng {cu.gates[0].pham_vi}" if cu.gates else "")
                      + (f", mốc {d.moc} {d.ngay or '(không có ngày)'}" if d else ""))
                if html_dir:
                    (html_dir / f"{path.stem}-khoan{k.so_hien_thi}.html").write_text(
                        render(cu, dieu), encoding="utf-8"
                    )
        out = Path(args.out or "eval/ontology/pred.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
        )
        bad = sum(1 for r in rows if r["errors"])
        meta = sum(1 for r in rows if r["role"] == "meta_cu")
        print(f"\n[ontology] Đã ghi {out} — {len(rows)} CU ({meta} meta_cu), {bad} có lỗi cứng")
        if pr_rows:
            pr_out = out.with_name("premise.jsonl")
            pr_out.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in pr_rows) + "\n",
                encoding="utf-8",
            )
            n_alias = sum(1 for r in pr_rows if r["alias"])
            print(f"[ontology] Đã ghi {pr_out} — {len(pr_rows)} premise, {n_alias} có bí danh")
        if kn_rows:
            kn_out = out.with_name("khainiem.jsonl")
            kn_out.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in kn_rows) + "\n",
                encoding="utf-8",
            )
            print(f"[ontology] Đã ghi {kn_out} — {len(kn_rows)} khái niệm (tầng premise)")
        return

    if not args.file:
        ap.error("Cần chỉ định file (hoặc dùng --from-html / --batch)")
    dieu = _load_dieu(Path(args.file), args.so_hieu)
    _print_tree(dieu)

    if args.units:
        k = next((k for k in dieu.khoan if k.so_hien_thi == args.units), None)
        if not k:
            ap.error(f"Không có khoản {args.units!r}")
        print(f"\n--- Đơn vị của khoản {k.so_hien_thi} ---\n{render_menu(segment(dieu, k))}")
        return
    if args.no_llm:
        return

    targets = [k for k in dieu.khoan if args.khoan in (None, k.so_hien_thi)]
    if not targets:
        ap.error(f"Không có khoản {args.khoan!r} trong Điều {dieu.so_hien_thi}")

    units = []
    for k in targets:
        print(f"\n[ontology] Đang trích khoản {k.so_hien_thi} (Gemini)...")
        cu = extract_cu(k, dieu)
        units.append(cu.model_dump())
        print(json.dumps(cu.model_dump(), ensure_ascii=False, indent=2))
        _print_report(cu)
        if args.html:
            path = Path(args.html)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(cu, dieu), encoding="utf-8")
            print(f"[ontology] Đã ghi trang kiểm: {path}")

    if args.out:
        Path(args.out).write_text(
            json.dumps(units, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[ontology] Đã ghi {args.out}")


if __name__ == "__main__":
    main(sys.argv[1:])
