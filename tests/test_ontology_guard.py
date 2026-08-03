"""Guard `ap_dung_khi` — tất định, hai tầng, không gọi Gemini.

B22: `connector` trả lời *"các vế **kết hợp** thế nào"*, guard trả lời *"vế này **khi
nào** áp dụng"*. Trộn hai câu hỏi vào một enum là mơ hồ im lặng — nên `connector` giữ
nguyên `all|any|unknown`, không thêm giá trị.

Toàn bộ tầng này là REGEX chạy trên text của nút, LLM không tham gia ⇒ test được tất
định, không cần mock.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import build_cu
from app.ontology.parser import hop_guard, parse_dieu, tach_guard
from app.ontology.segmenter import segment

_DIR = Path("data/fixtures")


@pytest.fixture(scope="module")
def index():
    return json.loads((_DIR / "_index.json").read_text(encoding="utf-8"))


def _dieu(index, name):
    p = _DIR / name
    if not p.exists():
        pytest.skip(f"chưa sinh fixture {name}")
    return parse_dieu(p.read_text(encoding="utf-8"), index[name])


def _khoan(dieu, so: str):
    return next(k for k in dieu.khoan if k.so_hien_thi == so)


def _diem(khoan, so: str):
    return next(d for d in khoan.diem if d.so_hien_thi == so)


# --- 1. CA GỐC: phân nhánh ở TẦNG TIẾT ---------------------------------------


def test_ca_goc_tt17_d16_k1_diem_a_guard_o_tang_tiet(index):
    """Hai tiết loại trừ nhau theo loại chủ thể — đúng ca đẻ ra cả thiết kế này."""
    dieu = _dieu(index, "TT17-2024-dieu16.txt")
    diem = _diem(_khoan(dieu, "1"), "a")
    got = [tach_guard(t.text, t.start)[0] for t in diem.tiet]

    assert [(g[0], g[1]) for g in got] == [
        ("khách hàng", "cá nhân"),
        ("khách hàng", "tổ chức"),
    ]
    # raw_text round-trip đúng char_span, và span nằm TRONG span của tiết tương ứng.
    for t, g in zip(diem.tiet, got):
        assert dieu.text[g[3] : g[4]] == g[2]
        assert t.start <= g[3] and g[4] <= t.end


def test_ca_goc_connector_khong_doi(index):
    """`connector` KHÔNG được mượn để diễn đạt phân nhánh — nó là câu hỏi khác."""
    dieu = _dieu(index, "TT17-2024-dieu16.txt")
    khoan = _khoan(dieu, "1")
    units = segment(dieu, khoan)
    uid = next(u.uid for u in units if u.source_diem == "a")
    cu = build_cu(
        {
            "subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": [{"source_diem": "a", "units": [uid],
                            "object_label": "", "constraint_label": ""}],
        },
        khoan, dieu, units, role="actor_cu",
    )
    c = next(x for x in cu.conditions if x.source_diem == "a")
    assert [s.ap_dung_khi.gia_tri for s in c.sub] == ["cá nhân", "tổ chức"]
    assert c.logic in {"all", "any", "unknown"}  # không có giá trị mới nào


# --- 2. Chuỗi phân nhánh ở TẦNG ĐIỂM ------------------------------------------


def test_tt18_d9_k2_ba_nhanh_o_tang_diem(index):
    dieu = _dieu(index, "TT18-2024-dieu9.txt")
    khoan = _khoan(dieu, "2")
    got = {}
    for so in ("a", "b", "c"):
        g, _ = tach_guard(_diem(khoan, so).text, _diem(khoan, so).start)
        assert g is not None, f"điểm {so} phải có guard"
        got[so] = (g[0], g[1])

    assert got["a"] == ("khách hàng cá nhân", "người Việt Nam")
    assert got["b"][0] == "khách hàng cá nhân" and "gốc Việt Nam" in got["b"][1]
    assert got["c"] == ("khách hàng cá nhân", "người nước ngoài")
    # Ba nhánh KHÁC nhau — nếu trùng thì phân nhánh vô nghĩa.
    assert len({v[1] for v in got.values()}) == 3


# --- 3. Họ thuộc tính khác — chứng minh chuỗi tự do là đúng lựa chọn ----------


def test_tt18_d13_k4_ho_thuoc_tinh_khac(index):
    """"Đối với thẻ trả trước" — trục `thẻ`, không phải `khách hàng`.

    Đây là lý do `thuoc_tinh` KHÔNG phải enum: 18 fixture đã có ba họ (`khách hàng`,
    `tài khoản thanh toán`, `thẻ`); enum sẽ phải nới mỗi lần thêm văn bản.
    """
    dieu = _dieu(index, "TT18-2024-dieu13.txt")
    khoan = _khoan(dieu, "4")
    g, _ = tach_guard(khoan.text, khoan.start)
    assert g is not None
    assert g[0] == "thẻ" and g[1] == "thẻ trả trước"
    assert dieu.text[g[3] : g[4]] == g[2]


def test_khoan_khong_che_diem_thi_dieu_kien_van_thua_huong_guard(index):
    """Guard phủ cả khoản phải tới được `ConditionItem`, dù mô hình neo hẹp tới đâu.

    Trước khi sửa, nhánh "không có Điểm" đọc guard trên **đoạn đã neo của điều kiện**
    nên TT18 Đ13 k4 mất guard trong `pred.jsonl` dù parser tách đúng — một tầng TẤT
    ĐỊNH lại phụ thuộc đầu ra của LLM. Tìm ra khi đối chiếu batch, không khi đọc code.
    """
    dieu = _dieu(index, "TT18-2024-dieu13.txt")
    khoan = _khoan(dieu, "4")
    assert not khoan.diem, "fixture đổi rồi — ca này cần khoản KHÔNG chẻ Điểm"
    units = segment(dieu, khoan)
    uid = max(u.uid for u in units)  # neo vào đơn vị CUỐI, xa cụm guard nhất
    cu = build_cu(
        {
            "subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": [{"source_diem": None, "units": [uid],
                            "object_label": "", "constraint_label": ""}],
        },
        khoan, dieu, units, role="actor_cu",
    )
    g = cu.conditions[0].ap_dung_khi
    assert g is not None and (g.thuoc_tinh, g.gia_tri) == ("thẻ", "thẻ trả trước")
    assert dieu.text[g.char_span[0] : g.char_span[1]] == g.raw_text


# --- 4. Ranh giới guard / chapeau — hai cơ chế bù nhau, không chồng nhau ------


def test_ca_chapeau_khong_sinh_guard(index):
    """"phải đảm bảo các nguyên tắc sau" là `all`, KHÔNG phải phân nhánh."""
    dieu = _dieu(index, "TT18-2024-dieu9.txt")
    diem = _diem(_khoan(dieu, "3"), "c")
    g, _ = tach_guard(diem.text, diem.start)
    assert g is None, f"chapeau không được sinh guard, nhận được {g}"


# --- 5. Không có mẫu ⇒ None, và KHÔNG cảnh báo --------------------------------


def test_khong_co_mau_thi_im_lang():
    g, w = tach_guard("Tổ chức cung ứng dịch vụ phải báo cáo định kỳ hằng quý.")
    assert g is None and w == ""


def test_vien_dan_khong_phai_guard_va_khong_canh_bao():
    """"đối với các trường hợp quy định tại Điều 5" là ĐỊA CHỈ, không phải loại."""
    g, w = tach_guard("Áp dụng đối với các trường hợp quy định tại Điều 5 Thông tư này.")
    assert g is None
    assert w == "", "viện dẫn thì bỏ hẳn, cảnh báo ở đây chỉ tạo nhiễu"


def test_giong_guard_ma_khong_tach_duoc_thi_canh_bao():
    """Nguyên văn ND52 Đ22 k2 điểm b — guard nằm ở ĐUÔI câu, phủ vế đứng trước.

    Hình thái này có thật và khá phổ biến (đo được 16 ca), nhưng cụm không mở đầu đơn
    vị nên không biết nó phủ tới đâu ⇒ **không đoán**, chỉ nói ra.
    """
    g, w = tach_guard(
        "Có vốn điều lệ thực góp hoặc được cấp tối thiểu: 50 tỷ đồng đối với "
        "dịch vụ ví điện tử, dịch vụ hỗ trợ thu hộ, chi hộ."
    )
    assert g is None
    assert w.startswith("guard_ngoai_mau"), w
    assert "dịch vụ ví điện tử" in w  # nói RA cụm bắt được, không nuốt


# --- 6. Round-trip + hợp guard dọc đường đi ----------------------------------


def test_moi_guard_tren_corpus_deu_round_trip(index):
    """`raw_text` phải bằng đúng `dieu.text[char_span]` — sai `base` là lệch âm thầm."""
    n = 0
    for name in index:
        p = _DIR / name
        if not p.exists():
            continue
        dieu = parse_dieu(p.read_text(encoding="utf-8"), index[name])
        for k in dieu.khoan:
            cho = [(k.text, k.start)] if not k.diem else []
            for d in k.diem:
                cho.append((d.text, d.start))
                cho += [(t.text, t.start) for t in d.tiet]
            for txt, base in cho:
                g, _ = tach_guard(txt, base)
                if g:
                    assert dieu.text[g[3] : g[4]] == g[2], f"{name}: {g[2]!r}"
                    n += 1
    assert n >= 10, f"chỉ tách được {n} guard — nghi mẫu hỏng"


# --- 6b. Guard đổi CÂU HỎI bàn giao, không đổi câu TRẢ LỜI ---------------------


def _cu_theo_diem(index, fixture: str, khoan_so: str, diem_so: str):
    dieu = _dieu(index, fixture)
    khoan = _khoan(dieu, khoan_so)
    units = segment(dieu, khoan)
    # Neo vào đơn vị THẬT SỰ thuộc điểm: `source_diem` nay suy từ `units` chứ không lấy
    # lời khai, nên neo vào đơn vị đầu tiên rồi khai "a" là tự tạo mâu thuẫn.
    uid = next(u.uid for u in units if u.source_diem == diem_so)
    return build_cu(
        {
            "subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": [{"source_diem": diem_so, "units": [uid],
                            "object_label": "", "constraint_label": ""}],
        },
        khoan, dieu, units, role="actor_cu",
    )


def test_moi_tiet_deu_co_guard_thi_doi_ma_va_liet_ke_gia_tri(index):
    cu = _cu_theo_diem(index, "TT17-2024-dieu16.txt", "1", "a")
    w = " ".join(cu.warnings)
    assert "tiet_semicolon_guard_da_phu" in w
    assert "tiet_semicolon_mo_ho" not in w
    # Liệt kê giá trị để người duyệt nhìn ra ngay hai nhánh có loại trừ nhau không.
    assert "'cá nhân'" in w and "'tổ chức'" in w


def test_tiet_thieu_guard_thi_giu_nguyen_ma_cu(index):
    """TT18 Đ9 k3 điểm c — ca chapeau, không tiết nào có guard ⇒ câu hỏi cũ."""
    cu = _cu_theo_diem(index, "TT18-2024-dieu9.txt", "3", "c")
    w = " ".join(cu.warnings)
    assert "tiet_semicolon_mo_ho" in w
    assert "tiet_semicolon_guard_da_phu" not in w
    assert "'và' hay 'hoặc'" in w


@pytest.mark.parametrize(
    ("fixture", "khoan_so", "diem_so"),
    [("TT17-2024-dieu16.txt", "1", "a"), ("TT18-2024-dieu9.txt", "3", "c")],
)
def test_connector_van_la_unknown_du_guard_da_phu(index, fixture, khoan_so, diem_so):
    """Guard KHÔNG được tự nâng `unknown` lên `all`.

    Nó chỉ làm connector vô hại khi các guard anh em **loại trừ nhau từng đôi**, mà
    máy không chứng minh được điều đó: `thuoc_tinh`/`gia_tri` là chuỗi tự do nên hai
    guard tương lai có thể chồng lấn. Suy diễn hộ là phán định, không phải đánh dấu.
    """
    cu = _cu_theo_diem(index, fixture, khoan_so, diem_so)
    c = next(x for x in cu.conditions if x.source_diem == diem_so)
    assert c.logic == "unknown"


def test_khong_co_duong_code_nao_ghi_all_tu_guard():
    """Canh bằng chính mã nguồn: nhánh cảnh báo ';' không được GÁN `logic`.

    Test hành vi ở trên chỉ chứng minh *hiện tại* không nâng cấp; test này chặn một
    lần sửa tương lai lặng lẽ thêm `logic = "all"` vào đúng nhánh đã có guard.
    """
    import re as _re

    src = Path("app/ontology/extractor.py").read_text(encoding="utf-8")
    dau = src.index('if logic == "unknown":')
    dam = src[dau : src.index("errors += item_err", dau)]
    gan = _re.search(r"\blogic\s*=(?!=)", dam)
    assert gan is None, f"nhánh cảnh báo ';' đang gán logic: {dam[gan.start():][:60]!r}"


def test_run_eval_van_chay_voi_ban_ghi_KHONG_co_truong_moi():
    """Bộ nhãn/bản ghi sinh trước B22 không có `ap_dung_khi` — không được vỡ.

    Trường mới là **bổ sung**, không phải bắt buộc: thiếu nó nghĩa là "chưa đo", khác
    hẳn `None` nghĩa là "vô điều kiện". Cả hai đều phải đi qua bộ đo được.
    """
    from eval.ontology.run_eval import evaluate

    cu = {
        "id": "X#than/dieu_1#khoan_1", "type": "actor_cu",
        "subject": {"grounding": {"char_span": [0, 5]}},
        "action": {"grounding": {"char_span": [6, 9]}},
        "logic": "all",
        "conditions": [{"source_diem": "a", "grounding": {"char_span": [0, 5]}}],
    }
    gold = {
        "id": cu["id"], "type": "actor_cu", "reviewed": True,
        "subject_span": [0, 5], "action_span": [6, 9], "logic": "all",
        "conditions": [{"source_diem": "a", "span": [0, 5]}],
    }
    kq = evaluate({cu["id"]: cu}, {gold["id"]: gold})
    assert kq["n_scored"] == 1 and kq["missing_from_pred"] == []
    assert kq["condition_set"]["tp"] == 1


def test_hop_guard_la_phep_AND_doc_duong_di():
    """Điểm 'cá nhân' chứa tiết 'eKYC' ⇒ tiết áp dụng khi cá nhân ∧ eKYC."""
    g_diem = ("khách hàng", "cá nhân", "đối với khách hàng là cá nhân", 0, 30)
    g_tiet = ("phương thức", "eKYC", "trường hợp mở bằng eKYC", 40, 63)

    assert hop_guard(g_diem, g_tiet) == [g_diem, g_tiet]  # ngoài → trong
    assert hop_guard(None, g_tiet) == [g_tiet]
    assert hop_guard(g_diem, None) == [g_diem]
    assert hop_guard(None, None) == []  # vô điều kiện


# --- 7. Số đo trên bộ fixture hiện tại ----------------------------------------


def test_connector_unknown_bang_0_tren_fixture_hien_tai(index):
    """Đây là KẾT QUẢ ĐO trên 18 fixture, KHÔNG phải bất biến của toàn corpus.

    `unknown` vẫn là giá trị hợp lệ cho ca mơ hồ thật trong tương lai — test này chỉ
    đóng đinh rằng ở bộ fixture hiện tại, mọi Điểm có tiết đều đã giải được bằng một
    trong hai cơ chế (guard phân nhánh, hoặc dấu hiệu chapeau). Gặp văn bản mới mà nó
    đỏ thì đọc lại ca đó rồi chỉnh kỳ vọng, đừng nới mẫu regex cho nó xanh.
    """
    con_mo_ho = []
    for name in index:
        p = _DIR / name
        if not p.exists():
            continue
        dieu = parse_dieu(p.read_text(encoding="utf-8"), index[name])
        for k in dieu.khoan:
            for d in k.diem:
                if not d.tiet:
                    continue
                co_guard = all(tach_guard(t.text, t.start)[0] for t in d.tiet)
                if not co_guard and all(t.connector == "unknown" for t in d.tiet):
                    con_mo_ho.append(f"{k.id}#diem_{d.so_hien_thi}")
    # TT18 Đ9 K3 điểm c là ca chapeau — giải bằng luật chapeau, không bằng guard.
    assert con_mo_ho == ["18/2024/TT-NHNN#than/dieu_9#khoan_3#diem_c"], con_mo_ho
