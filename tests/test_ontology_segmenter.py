"""Test tách đơn vị nguyên tử — offline, không gọi Gemini."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.ontology.parser import parse_dieu
from app.ontology.segmenter import hull, render_menu, segment

_FIXTURE = Path("data/fixtures/ND52-2024-dieu22.txt")
_SO_HIEU = "52/2024/NĐ-CP"


@pytest.fixture(scope="module")
def dieu():
    return parse_dieu(_FIXTURE.read_text(encoding="utf-8"), _SO_HIEU)


@pytest.fixture(scope="module")
def units_k2(dieu):
    return segment(dieu, dieu.khoan[1])


def test_don_vi_0_la_tieu_de_dieu(units_k2):
    """Chủ ngữ kế thừa cần một chỗ neo hợp lệ, nếu không LLM buộc phải bịa."""
    head = units_k2[0]
    assert head.uid == 0
    assert head.kind == "tieu_de"
    assert head.text.startswith("Điều 22.")


def test_round_trip_offset(dieu, units_k2):
    """Bất biến nền tảng: mọi đơn vị cắt đúng từ dieu.text."""
    for u in units_k2:
        assert dieu.text[u.start : u.end] == u.text, u.uid
        assert u.text == u.text.strip()  # không dính khoảng trắng rìa


def test_don_vi_khong_chong_lan_va_tang_dan(units_k2):
    body = units_k2[1:]  # bỏ tiêu đề Điều (nằm ngoài khoản)
    for prev, cur in zip(body, body[1:]):
        assert prev.end <= cur.start, (prev.uid, cur.uid)


def test_tach_theo_dau_cham_phay(dieu, units_k2):
    """Điểm b có 3 vế ngăn bằng ';' → phải thành 3 đơn vị riêng.

    Đây là điều làm nên độ mịn: nếu để nguyên cả điểm b thì '50 tỷ' và '300 tỷ'
    dính chung một span, không neo riêng được.
    """
    b = [u for u in units_k2 if u.source_diem == "b"]
    assert len(b) == 3
    assert "50 tỷ đồng" in b[0].text
    assert "300 tỷ đồng" in b[1].text
    assert "chịu hoàn toàn trách nhiệm" in b[2].text


def test_moi_diem_deu_co_don_vi(dieu, units_k2):
    labels = {u.source_diem for u in units_k2 if u.source_diem}
    assert labels == {"a", "b", "c", "d", "đ", "e", "g", "h"}


def test_khoan_khong_che_diem_van_duoc_tach_cau(dieu):
    """Khoản 1 là 2 câu liền → tách theo ranh giới câu, không để nguyên một khối."""
    units = segment(dieu, dieu.khoan[0])
    body = [u for u in units if u.uid > 0]
    assert len(body) == 2
    assert body[0].text.startswith("1. Dịch vụ trung gian thanh toán bao gồm")
    assert body[1].text.startswith("Hoạt động cung ứng")
    assert all(u.source_diem is None for u in body)


def test_khong_cat_o_so_khoan(dieu):
    """Dấu chấm của "1." cũng khớp mẫu ranh giới câu → dễ đẻ đơn vị rác chỉ có số."""
    body = [u for u in segment(dieu, dieu.khoan[0]) if u.uid > 0]
    assert not any(u.text.strip() in {"1.", "2.", "3."} for u in body)


def test_hull_bao_loi_va_uid_sai(units_k2):
    span = hull(units_k2, [5, 6])
    u5 = next(u for u in units_k2 if u.uid == 5)
    u6 = next(u for u in units_k2 if u.uid == 6)
    assert span == (u5.start, u6.end)
    assert hull(units_k2, [999]) is None  # uid không tồn tại → mất provenance
    assert hull(units_k2, []) is None


def test_render_menu_danh_so_va_gan_nhan(units_k2):
    menu = render_menu(units_k2)
    assert "[0] (tiêu đề Điều)" in menu
    assert "(câu bao trùm)" in menu
    assert "(điểm đ)" in menu


# --- Gom dòng nối tiếp một câu (mức 0) ---------------------------------------
#
# `clean_text` giữ mỗi dòng nguồn một dòng, mà nguồn là HTML: mỗi viện dẫn nằm trong
# thẻ <a> nên chiếm một dòng riêng. Coi `\n` là ranh giới cứng thì một câu bị vỡ thành
# nhiều "đơn vị" không cái nào đứng vững một mình — và menu hỏng thì mọi tầng chống
# bịa phía sau đều vô nghĩa, vì mô hình không có lựa chọn nào đúng để mà chọn.

_TT40_52 = Path("data/fixtures/TT40-2024-dieu52.txt")


def _tat_ca_dieu():
    import json

    index = json.loads(Path("data/fixtures/_index.json").read_text(encoding="utf-8"))
    for p in sorted(Path("data/fixtures").glob("*.txt")):
        yield p.name, parse_dieu(p.read_text(encoding="utf-8"), index[p.name])


def test_diem_a_cua_tt40_52_k6_la_MOT_don_vi():
    """Case thật đã gây lỗi cứng: 1 câu 142 ký tự bị vỡ thành 5 đơn vị.

    Bốn trong năm mảnh là câu cụt không có vị ngữ (`'a) Điều 9a và'`, `'khoản 4 Điều
    11'`, `'đã được sửa đổi, bổ sung theo Thông tư số'`, `'23/2019/TT-NHNN'`). Mô hình
    chọn mảnh duy nhất có vị ngữ rồi gắn nhãn bằng cả câu ⇒ guard báo "bịa số" — và
    báo ĐÚNG theo hợp đồng, vì bao lồi thật sự không chứa các số đó.
    """
    if not _TT40_52.exists():
        pytest.skip("chưa sinh fixture TT40-2024-dieu52.txt")
    import json

    index = json.loads(Path("data/fixtures/_index.json").read_text(encoding="utf-8"))
    dieu = parse_dieu(_TT40_52.read_text(encoding="utf-8"), index[_TT40_52.name])
    k6 = next(k for k in dieu.khoan if k.so_hien_thi == "6")
    a = [u for u in segment(dieu, k6) if u.source_diem == "a"]
    assert len(a) == 1, [u.text for u in a]
    for tok in ("Điều 9a", "khoản 4 Điều 11", "23/2019/TT-NHNN", "14 tháng 8 năm 2024"):
        assert tok in a[0].text, tok


def test_khong_don_vi_nao_ket_thuc_giua_cau():
    """Đo trên cả 16 fixture: trước khi gom là 64/293 đơn vị (22%), nay phải là 0.

    "Kết thúc giữa câu" = đơn vị không tận cùng bằng `.`/`;`/`:` mà đơn vị kế tiếp vẫn
    thuộc cùng Điểm — tức câu còn chạy tiếp qua một ranh giới do HTML để lại.
    """
    from app.ontology.parser import khoan_de_trich

    xau = []
    for name, dieu in _tat_ca_dieu():
        for k in khoan_de_trich(dieu):
            body = [u for u in segment(dieu, k) if u.uid]
            for cur, nxt in zip(body, body[1:]):
                t = cur.text.rstrip()
                if t and t[-1] not in ".;:" and cur.source_diem == nxt.source_diem:
                    xau.append(f"{name} k{k.so_hien_thi} [{cur.uid}] {t[-40:]!r}")
    assert xau == [], xau


def test_gom_dong_khong_nuot_diem_ke_tiep():
    """Ranh giới BẮT BUỘC: chỉ gom trong cùng một Điểm.

    Nếu không, một Điểm tình cờ không có dấu kết sẽ nuốt trọn Điểm sau vào đuôi nó —
    đổi một lỗi vỡ vụn lấy một lỗi dính liền, tệ hơn hẳn vì mất luôn ranh giới Điểm.
    """
    from app.ontology.parser import khoan_de_trich

    for name, dieu in _tat_ca_dieu():
        for k in khoan_de_trich(dieu):
            for u in segment(dieu, k):
                if not u.source_diem:
                    continue
                d = next(x for x in k.diem if x.so_hien_thi == u.source_diem)
                assert d.start <= u.start and u.end <= d.end, (name, k.so_hien_thi, u.uid)


def test_bat_bien_span_van_dung_tren_ca_corpus():
    """Gom dòng không được làm lệch một offset nào — đây là nền của mọi provenance."""
    from app.ontology.parser import khoan_de_trich

    for name, dieu in _tat_ca_dieu():
        for k in khoan_de_trich(dieu):
            body = [u for u in segment(dieu, k) if u.uid]
            for u in body:
                assert dieu.text[u.start : u.end] == u.text, (name, u.uid)
                assert u.text == u.text.strip()
            for prev, cur in zip(body, body[1:]):
                assert prev.end <= cur.start, (name, prev.uid)
