"""Test trang duyệt bộ nhãn — phần Python (nhúng dữ liệu, encoding, xuất JSONL).

Phần JavaScript (selection → offset, tô màu) không test được ở đây vì repo không có
trình chạy test cho web. Đã kiểm tay trong Chrome: 8 lát text node đều có offset khớp
văn bản gốc, ghép lại bằng đúng `dieu.text`, và bôi đen "Dịch vụ trung gian thanh
toán" đọc ra đúng span [76, 105].
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eval.ontology.review_ui import (
    EXPORT_ACTOR,
    EXPORT_CHUNG,
    EXPORT_META,
    PREMISE_FIELDS,
    build_payload,
    render,
    split_rows,
    to_jsonl,
)

_MOJIBAKE_RE = re.compile(r"Ä‘|á»|áº|Ã¡|Ã´|Æ°|â€")
_SEED = Path("eval/ontology/gold.seed.jsonl")
_PSEED = Path("eval/ontology/gold.premise.seed.jsonl")

pytestmark = pytest.mark.skipif(not _SEED.exists(), reason="chưa sinh gold.seed.jsonl")


@pytest.fixture(scope="module")
def payload():
    return build_payload(_SEED, _PSEED)


@pytest.fixture(scope="module")
def cu_items(payload):
    return [i for i in payload["items"] if i.get("kind") != "premise"]


def test_nhung_du_moi_compliance_unit(payload):
    n = len([ln for ln in _SEED.read_text(encoding="utf-8").splitlines() if ln.strip()])
    if _PSEED.exists():
        n += len([ln for ln in _PSEED.read_text(encoding="utf-8").splitlines() if ln.strip()])
    assert len(payload["items"]) == n
    assert payload["fixtures"], "chưa nhúng văn bản fixture nào"


def test_don_vi_cat_dung_van_ban_goc(payload):  # noqa: D103 - xem docstring dưới
    """Nền của phép toán selection → offset trong trình duyệt.

    Nếu bất biến này hỏng thì mọi span người duyệt gán đều lệch mà không báo lỗi.
    """
    for item in payload["items"]:
        text = payload["fixtures"][item["fixture_name"]]["text"]
        for u in item["units"]:
            assert 0 <= u["start"] < u["end"] <= len(text), item["id"]
        ks, ke = item["khoan_span"]
        body = [u for u in item["units"] if u["uid"] > 0]
        assert all(ks <= u["start"] and u["end"] <= ke for u in body), item["id"]
        assert item["units"][0]["uid"] == 0  # tiêu đề Điều, cho chủ ngữ kế thừa


def test_span_may_de_xuat_nam_trong_van_ban(payload):
    for item in payload["items"]:
        n = len(payload["fixtures"][item["fixture_name"]]["text"])
        for key in ("subject_span", "action_span", "menh_de_span", "raw_span"):
            sp = item.get(key)
            if sp:
                assert 0 <= sp[0] < sp[1] <= n, f"{item['id']}.{key}"
        for c in item.get("conditions") or []:
            if c.get("span"):
                assert 0 <= c["span"][0] < c["span"][1] <= n, item["id"]


# --- Vai phải NHÌN THẤY ĐƯỢC trên trang -----------------------------------


def test_moi_muc_deu_mang_vai(payload):
    """Lỗi người dùng báo: 49 CU trong danh sách trông y hệt nhau dù 9 cái là
    meta-CU, còn 45 premise thì không hiện ra ở đâu cả."""
    for item in payload["items"]:
        if item.get("kind") == "premise":
            assert item["premise_kind"] in {"dinh_nghia", "vai_tro", "pham_vi"}
        else:
            assert item["type"] in {"actor_cu", "meta_cu"}


def test_meta_cu_mang_theo_cong(cu_items):
    metas = [i for i in cu_items if i["type"] == "meta_cu"]
    assert metas, "bộ khung không còn meta-CU nào — kiểm lại pred.jsonl"
    for m in metas:
        assert m["gates"], f"{m['id']}: meta_cu mà không có cổng"
        g = m["gates"][0]
        assert g["kind"] and g["pham_vi"]
        assert "suy_ra_duoc" in g and "phu_dinh" in g


def test_premise_co_nguyen_van_va_bi_danh(payload):
    prs = [i for i in payload["items"] if i.get("kind") == "premise"]
    assert prs
    for p in prs:
        text = payload["fixtures"][p["fixture_name"]]["text"]
        a, b = p["raw_span"]
        # `raw_text` bị cắt còn 200 ký tự trong khung — so tiền tố, không so cả khối.
        raw = p["_may_de_xuat"]["raw_text"]
        assert text[a:b].startswith(raw) or raw == text[a:b][: len(raw)]
        al = p["_may_de_xuat"].get("alias_span")
        if al:
            assert text[al[0] : al[1]] == p["alias"]


def test_trang_hien_nhan_vai(payload):
    html = render(payload, can_save=False)
    for nhan in ("ACTOR", "META", "PREMISE"):
        assert f'>{nhan}<' in html or f'"{nhan}"' in html, nhan
    assert "Cổng chặn" in html  # bảng cổng của meta-CU


def test_tach_hai_hop_dong_khi_luu(payload):
    cu, pr = split_rows(payload["items"])
    assert cu and pr
    assert all(r.get("kind") != "premise" for r in cu)
    assert all(r["kind"] == "premise" for r in pr)
    rows = [json.loads(ln) for ln in to_jsonl(pr, PREMISE_FIELDS).splitlines()]
    for r in rows:
        assert set(r) == set(PREMISE_FIELDS)
        assert "subject_span" not in r  # premise không có 4-tuple, không được lẫn vào


def test_html_tu_chua_va_dung_encoding(payload):
    html = render(payload, can_save=False)
    assert html.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in html
    assert "__DATA__" not in html and "__CAN_SAVE__" not in html
    assert not _MOJIBAKE_RE.search(html)
    # Không tải tài nguyên ngoài — mở offline vẫn chạy.
    assert "src=" not in html and "cdn" not in html.lower()


def test_du_lieu_nhung_khong_pha_the_script(payload):
    """`</script>` trong dữ liệu sẽ đóng sớm thẻ script và làm hỏng trang."""
    html = render(payload, can_save=False)
    body = html.split("const DATA = ", 1)[1].split(", CAN_SAVE", 1)[0]
    assert "</" not in body
    json.loads(body.replace("<\\/", "</"))  # vẫn parse được sau khi escape


def test_co_the_luu_bat_tat_theo_che_do(payload):
    assert "CAN_SAVE = true" in render(payload, can_save=True)
    assert "CAN_SAVE = false" in render(payload, can_save=False)


def test_xuat_jsonl_dung_hop_dong_voi_run_eval(cu_items):
    """Hai vai, hai bộ trường — và KHÔNG được chồng lấn.

    Trước khi tách kiểu, mọi bản ghi xuất cùng một danh sách phẳng nên meta-CU luôn
    mang `subject_span: null`. Ô null đó không phân biệt được "không áp dụng" với
    "người duyệt chưa gán" — đúng thứ việc tách kiểu dọn đi, nên phải canh.
    """
    out = to_jsonl(cu_items)
    rows = [json.loads(ln) for ln in out.splitlines()]
    assert len(rows) == len(cu_items)
    n_meta = 0
    for r in rows:
        rieng = EXPORT_META if r["type"] == "meta_cu" else EXPORT_ACTOR
        assert set(r) == set(EXPORT_CHUNG) | set(rieng), r["id"]
        assert "_may_de_xuat" not in r  # ghi chú của máy không lọt vào bộ nhãn
        if r["type"] == "meta_cu":
            n_meta += 1
            assert "subject_span" not in r and "subject_source" not in r
            assert "action_span" not in r  # meta-CU dùng `menh_de_span`
        else:
            assert "gates" not in r and "menh_de_span" not in r
    assert n_meta, "không còn meta-CU nào để canh — kiểm lại pred.jsonl"
    assert out.endswith("\n")


def test_xuat_giu_nguyen_tieng_viet(payload):
    out = to_jsonl(payload["items"])
    assert "Điều" in out or "dieu" in out
    assert not _MOJIBAKE_RE.search(out)
