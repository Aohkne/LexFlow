"""Đóng gói cạnh tác động thành artefact tự chứa — giải span thành chữ, không bịa."""
import json

from app.ontology.dong_goi import (
    GoiLopPhu,
    _ban_do_toan_van,
    boi_dap,
    ly_do_tu_choi_ghi,
)
from app.ontology.tac_dong import CanhTacDong

_NOI_DUNG = 'Điều 1. Sửa đổi\n1. Sửa khoản 2 như sau:\n"2. Lời văn mới."\nĐiều 2. Hiệu lực\n'
_ARTICLES = [
    {"article": "Điều 1", "char_start": 0, "char_end": 63},
    {"article": "Điều 2", "char_start": 63, "char_end": len(_NOI_DUNG)},
]
_SPAN = (_NOI_DUNG.index('"2.'), _NOI_DUNG.index('mới."') + len('mới."'))


def _canh(**kw) -> CanhTacDong:
    goc = dict(
        nguon="41/2025/TT-NHNN#than/dieu_1#khoan_1",
        dich="40/2024/TT-NHNN#than/dieu_5#khoan_2",
        thao_tac="sua_doi",
        loi_van_moi=_SPAN,
        valid_from="2025-07-01",
        menh_lenh="Sửa khoản 2 như sau:",
    )
    return CanhTacDong(**{**goc, **kw})


_BAN_DO = {"41/2025/TT-NHNN": (_NOI_DUNG, _ARTICLES)}
_DOC_ID = {"41/2025/TT-NHNN": "TT41-2025"}


def test_giai_span_thanh_chu_nguyen_van():
    ra, cb = boi_dap([_canh()], _BAN_DO, _DOC_ID)
    assert cb == []
    assert ra[0].loi_van_moi_text == _NOI_DUNG[_SPAN[0]:_SPAN[1]]
    assert ra[0].loi_van_moi_text.startswith('"2.')  # nguyên văn, không strip dấu ngoặc
    assert ra[0].xuat_xu_doc_id == "TT41-2025"
    assert ra[0].xuat_xu_article == "Điều 1"


def test_thieu_toan_van_thi_bao_chu_khong_bia():
    ra, cb = boi_dap([_canh()], {}, _DOC_ID)
    assert ra[0].loi_van_moi_text is None
    assert len(cb) == 1 and "41/2025/TT-NHNN" in cb[0]


def test_span_ngoai_pham_vi_thi_bao():
    ra, cb = boi_dap([_canh(loi_van_moi=(10, 9_999))], _BAN_DO, _DOC_ID)
    assert ra[0].loi_van_moi_text is None
    assert len(cb) == 1 and "9999" in cb[0].replace(" ", "")


def test_bai_bo_khong_co_loi_van_moi_thi_khong_canh_bao():
    ra, cb = boi_dap([_canh(thao_tac="bai_bo", loi_van_moi=None)], _BAN_DO, _DOC_ID)
    assert ra[0].loi_van_moi_text is None and cb == []


def test_thanh_canh_quay_ve_dung_CanhTacDong():
    c = boi_dap([_canh()], _BAN_DO, _DOC_ID)[0][0].thanh_canh()
    assert isinstance(c, CanhTacDong)
    assert (c.nguon, c.dich, c.thao_tac, c.loi_van_moi) == (
        "41/2025/TT-NHNN#than/dieu_1#khoan_1",
        "40/2024/TT-NHNN#than/dieu_5#khoan_2",
        "sua_doi",
        _SPAN,
    )


def test_goi_lop_phu_round_trip_json():
    goi = GoiLopPhu(
        sinh_luc="2026-08-06",
        so_hieu_theo_doc={"TT41-2025": "41/2025/TT-NHNN"},
        canh=boi_dap([_canh()], _BAN_DO, _DOC_ID)[0],
    )
    lai = GoiLopPhu.model_validate_json(goi.model_dump_json())
    assert lai.canh[0].loi_van_moi == _SPAN  # tuple sống sót qua JSON
    assert lai.canh[0].loi_van_moi_text == goi.canh[0].loi_van_moi_text


# --- Fix wave 06/08, IMPORTANT 4: lần đóng gói hỏng KHÔNG được phá artefact --------------
#
# `main()` từng ghi vô điều kiện. Trên checkout sạch `data/raw/vbpl/raw/` không tồn tại
# (gitignored) nên `doc_tac_dong` bỏ qua mọi văn bản, và lần chạy đó ghi đè artefact 178 cạnh
# bằng `canh: []` — in `cạnh: 0` rồi đi tiếp, không ai chặn.


def _viet_artefact(p, so_canh: int) -> None:
    p.write_text(
        json.dumps({"sinh_luc": "2026-08-06", "so_hieu_theo_doc": {},
                    "canh": [{"x": i} for i in range(so_canh)]}),
        encoding="utf-8",
    )


def test_khong_ghi_khi_dong_goi_ra_rong(tmp_path):
    dich = tmp_path / "lop_phu.json"
    _viet_artefact(dich, 178)
    ly_do = ly_do_tu_choi_ghi(0, dich)
    assert ly_do is not None
    assert "data/raw/vbpl/raw/" in ly_do  # nói thẳng nguyên nhân thường gặp


def test_khong_ghi_khi_co_ngot_manh(tmp_path):
    dich = tmp_path / "lop_phu.json"
    _viet_artefact(dich, 178)
    ly_do = ly_do_tu_choi_ghi(100, dich)
    assert ly_do is not None and "178" in ly_do and "100" in ly_do


def test_van_ghi_khi_co_ngot_nhe_hoac_tang(tmp_path):
    dich = tmp_path / "lop_phu.json"
    _viet_artefact(dich, 178)
    assert ly_do_tu_choi_ghi(175, dich) is None  # sửa vặt, còn trên ngưỡng
    assert ly_do_tu_choi_ghi(200, dich) is None


def test_chua_co_artefact_thi_van_ghi_duoc(tmp_path):
    assert ly_do_tu_choi_ghi(178, tmp_path / "chua-co.json") is None
    assert ly_do_tu_choi_ghi(0, tmp_path / "chua-co.json") is not None  # rỗng vẫn chặn


def test_main_thoat_khac_khong_khi_bi_tu_choi(tmp_path, monkeypatch):
    """Không chỉ in ra rồi đi tiếp — phải thoát khác 0 để CI/người chạy biết là hỏng."""
    import pytest

    from app.ontology import dong_goi as mod

    dich = tmp_path / "lop_phu.json"
    _viet_artefact(dich, 178)
    monkeypatch.setattr(mod, "DUONG_DAN_ARTEFACT", dich)
    monkeypatch.setattr(
        mod, "dong_goi",
        lambda *a, **kw: (GoiLopPhu(sinh_luc="2026-08-06", so_hieu_theo_doc={}, canh=[]), []),
    )
    with pytest.raises(SystemExit) as e:
        mod.main()
    assert e.value.code not in (0, None)
    assert json.loads(dich.read_text(encoding="utf-8"))["canh"], "artefact cũ đã bị phá"


def test_ban_do_toan_van_bao_file_hong_thay_vi_im_lang(tmp_path):
    """File corpus hỏng bị `continue` trong im lặng chính là cơ chế làm '0 cạnh' vô hình."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "hong.json").write_text("{ không phải json", encoding="utf-8")

    ra, canh_bao = _ban_do_toan_van(tmp_path)
    assert ra == {}
    assert len(canh_bao) == 1 and "hong.json" in canh_bao[0]

