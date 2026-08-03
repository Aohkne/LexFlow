"""Câu bao trùm của một Điểm quyết phép nối các tiết — offline, không gọi Gemini.

Vì sao có file này: đo trước khi viết luật, cả 18 fixture chỉ có **5 Điểm có tiết**;
2 giải được bằng liên từ hiện ("hoặc"), 3 còn `unknown`, và trong 3 cái đó chỉ **1**
mang cụm chapeau (TT18 Đ9 k3 điểm c, *"phải đảm bảo các nguyên tắc sau:"*). Một ca thật
thì KHÔNG đủ để tin một mẫu — nên phần lớn test dưới đây chạy trên **cụm nguyên văn lấy
từ chỗ khác trong chính corpus**, nơi chúng chưa nằm trong ngữ cảnh tiết nhưng chắc chắn
sẽ nằm khi corpus lớn ra.

Điều đáng canh nhất là **ba cực trái ngược** cùng chia nhau chữ "sau":

    ALL        "phải đảm bảo các nguyên tắc sau:"
    ANY        "đáp ứng ít nhất MỘT TRONG các tiêu chí sau:"
    loại trừ   "KHÔNG ÁP DỤNG đối với các trường hợp sau:"
    định nghĩa "(sau đây GỌI LÀ …)"  ← dạng ĐÔNG NHẤT trong corpus, 15+ lần

Đọc `any` thành `all` là **đảo nghĩa pháp lý**; bắt nhầm dạng định nghĩa là gán phép nối
cho một danh sách thuật ngữ. Cả hai đều im lặng nếu không có test.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import build_cu
from app.ontology.parser import (
    chapeau_cua_diem,
    chapeau_logic,
    parse_dieu,
    tiet_logic,
)
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


def _diem(dieu, khoan_so: str, diem_so: str):
    k = next(x for x in dieu.khoan if x.so_hien_thi == khoan_so)
    return k, next(x for x in k.diem if x.so_hien_thi == diem_so)


# --- 1. Ba cực, trên cụm nguyên văn của corpus -------------------------------


@pytest.mark.parametrize(
    ("chapeau", "cho"),
    [
        # ALL — bốn cụm có thật trong 18 fixture
        ("nhưng phải đảm bảo các nguyên tắc sau:", "all"),
        ("khi đáp ứng đầy đủ và phải đảm bảo duy trì đủ các điều kiện sau đây:", "all"),
        ("và phải đáp ứng tối thiểu các yêu cầu sau:", "all"),
        ("đảm bảo an toàn, bảo mật và bao gồm tối thiểu các bước như sau:", "all"),
        # ANY — đọc thành 'all' là ĐẢO NGHĨA PHÁP LÝ
        ("đáp ứng ít nhất một trong các tiêu chí sau:", "any"),
        ("Trường hợp thay đổi một trong các nội dung sau:", "any"),
        # Danh sách NGOẠI LỆ — không phải phép nối các yêu cầu
        ("bằng phương tiện điện tử không áp dụng đối với các trường hợp sau:", "unknown"),
        ("trừ các quy định sau đây:", "unknown"),
        # Danh sách ĐỊNH NGHĨA
        ("Trong Nghị định này, các từ ngữ dưới đây được hiểu như sau:", "unknown"),
        ("Trong Thông tư này, các từ ngữ sau đây được hiểu như sau:", "unknown"),
        # Không có cụm nào ⇒ im lặng, không đoán
        ("b) Xác nhận việc khách hàng chấp thuận với các nội dung tại thỏa thuận:", "unknown"),
        ("theo quy định tại khoản 2, 3 Điều 12 Thông tư này và:", "unknown"),
    ],
)
def test_ba_cuc_cua_cum_sau(chapeau, cho):
    assert chapeau_logic(chapeau)[0] == cho, chapeau


def test_cum_dinh_nghia_giua_cau_khong_bao_gio_khop():
    """`(sau đây gọi là …)` là dạng ĐÔNG NHẤT trong corpus — 15+ lần.

    Chốt chặn chính không phải từ điển mà là **vị trí**: cụm phải nằm ở ĐUÔI chapeau.
    Các cụm này luôn nằm giữa câu nên bị loại trước khi cần tới luật "gọi là".
    """
    for t in (
        "Dịch vụ thanh toán không dùng tiền mặt (sau đây gọi là dịch vụ thanh toán) là",
        "Tổ chức chủ trì Hệ thống bù trừ điện tử (sau đây gọi tắt là Tổ chức chủ trì)",
        "Ngân hàng Nhà nước Việt Nam (sau đây gọi là Ngân hàng Nhà nước) cấp Giấy phép",
    ):
        assert chapeau_logic(t) == ("unknown", None), t


def test_bu_tru_khong_bi_doc_thanh_menh_de_loai_tru():
    """"Hệ thống bù trừ điện tử" chứa chuỗi 'trừ' — không được nuốt mất một chapeau thật."""
    got, cum = chapeau_logic("Tổ chức chủ trì Hệ thống bù trừ điện tử phải đáp ứng các yêu cầu sau:")
    assert got == "all" and cum is not None


# --- 2. Liên từ hiện luôn thắng chapeau --------------------------------------


def test_lien_tu_hien_thang_chapeau(index):
    """"hoặc" nói về đúng hai tiết đang xét; chapeau nói về cả danh sách."""
    dieu = _dieu(index, "TT40-2024-dieu25.txt")
    _, d = _diem(dieu, "6", "c")
    assert any(t.connector == "hoac" for t in d.tiet)
    assert tiet_logic(d) == "any"


def test_chapeau_khong_lam_doi_hai_ca_da_giai_duoc(index):
    """Hai Điểm đã ra 'any' bằng liên từ phải GIỮ NGUYÊN — luật mới không được đụng."""
    for name, ks, ds in (("TT17-2024-dieu16.txt", "1", "b"), ("TT40-2024-dieu25.txt", "6", "c")):
        dieu = _dieu(index, name)
        _, d = _diem(dieu, ks, ds)
        assert tiet_logic(d) == "any", f"{name} k{ks} điểm {ds}"


# --- 3. Ca thật duy nhất, đi qua toàn bộ đường ống ---------------------------


def test_tt18_d9_k3_diem_c_giai_duoc_bang_chapeau(index):
    dieu = _dieu(index, "TT18-2024-dieu9.txt")
    khoan, d = _diem(dieu, "3", "c")
    assert not {t.connector for t in d.tiet} & {"hoac", "va"}, "ca này phải KHÔNG có liên từ"
    assert "các nguyên tắc sau" in chapeau_cua_diem(d)
    assert tiet_logic(d) == "all"

    units = segment(dieu, khoan)
    uid = next(u.uid for u in units if u.source_diem == "c")
    cu = build_cu(
        {
            "subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": [{"source_diem": "c", "units": [uid],
                            "object_label": "", "constraint_label": ""}],
        },
        khoan, dieu, units, role="actor_cu",
    )
    c = next(x for x in cu.conditions if x.source_diem == "c")
    assert c.logic == "all"
    w = " ".join(cu.warnings)
    # Cờ cũ phải BIẾN MẤT — không còn câu hỏi nào bàn giao cho người…
    assert "tiet_semicolon_mo_ho" not in w
    # …nhưng quyết định của máy phải để lại vết, kèm đúng cụm đã khớp.
    assert "tiet_logic_tu_chapeau" in w and "các nguyên tắc sau" in w


def test_diem_khong_co_tiet_thi_chapeau_rong(index):
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    _, d = _diem(dieu, "2", "a")
    assert not d.tiet
    assert chapeau_cua_diem(d) == ""


# --- 4. Bất biến trên toàn corpus --------------------------------------------


def test_khong_diem_nao_bi_doi_sang_any_ngoai_y_muon(index):
    """Quét mọi Điểm có tiết: `any` chỉ được sinh từ liên từ hiện, không từ chapeau.

    Corpus hiện chưa có ca chapeau dạng "một trong … sau" đứng trên tiết. Nếu một ngày
    có, test này đỏ và bắt người viết xác nhận — thay vì để nó lặng lẽ đổi nghĩa.
    """
    n = 0
    for name, so_hieu in json.loads((_DIR / "_index.json").read_text(encoding="utf-8")).items():
        p = _DIR / name
        if not p.exists():
            continue
        dieu = parse_dieu(p.read_text(encoding="utf-8"), so_hieu)
        for k in dieu.khoan:
            for d in k.diem:
                if not d.tiet:
                    continue
                n += 1
                if tiet_logic(d) == "any":
                    assert "hoac" in {t.connector for t in d.tiet}, f"{name} k{k.so_hien_thi} {d.so_hien_thi}"
    assert n == 5, f"corpus có {n} Điểm có tiết, luật này được đo trên 5 — xem lại"
