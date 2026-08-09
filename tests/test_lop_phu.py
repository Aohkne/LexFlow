"""Cổng runtime của lớp phủ: chunk retrieval → chú thích hiệu lực cấp khoản."""
from pathlib import Path

import pytest

from app.knowledge.lop_phu import chu_thich_chunk, chu_thich_ket_qua, tai_lop_phu
from app.ontology.dong_goi import CanhGoi, GoiLopPhu

_MOI = '"7. Hạn mức mới là 200 triệu đồng."'


def _goi() -> GoiLopPhu:
    return GoiLopPhu(
        sinh_luc="2026-08-06",
        so_hieu_theo_doc={"TT40-2024": "40/2024/TT-NHNN", "TT41-2025": "41/2025/TT-NHNN"},
        canh=[
            CanhGoi(
                nguon="41/2025/TT-NHNN#than/dieu_1#khoan_2",
                dich="40/2024/TT-NHNN#than/dieu_8#khoan_7",
                thao_tac="sua_doi",
                valid_from="2025-07-01",
                loi_van_moi=(100, 100 + len(_MOI)),
                loi_van_moi_text=_MOI,
                xuat_xu_doc_id="TT41-2025",
                xuat_xu_article="Điều 1",
                menh_lenh="Sửa đổi khoản 7 Điều 8 như sau:",
            ),
            CanhGoi(
                nguon="41/2025/TT-NHNN#than/dieu_2",
                dich="40/2024/TT-NHNN#than/dieu_9",
                thao_tac="bai_bo",
                valid_from="2025-07-01",
                menh_lenh="Bãi bỏ Điều 9.",
            ),
            # `bo_sung` KHÔNG có `ban_hien_hanh` (chỉ `sua_doi` trọn đơn vị mới có — xem
            # `chu_thich_chunk`) dù cùng trỏ trọn khoá gốc: đúng ca `chu_thich_ket_qua` phải
            # kéo lời văn mới về qua `lay_chunk_theo_id`.
            CanhGoi(
                nguon="41/2025/TT-NHNN#than/dieu_3",
                dich="40/2024/TT-NHNN#than/dieu_10",
                thao_tac="bo_sung",
                valid_from="2025-07-01",
                xuat_xu_doc_id="TT41-2025",
                xuat_xu_article="Điều 3",
                menh_lenh="Bổ sung Điều 10 như sau:",
            ),
        ],
    )


@pytest.fixture
def lp(tmp_path):
    p = tmp_path / "lop_phu.json"
    p.write_text(_goi().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    ra = tai_lop_phu(str(p))
    yield ra
    tai_lop_phu.cache_clear()


def _chunk(cid: str, text: str = "nội dung nền") -> dict:
    return {"id": cid, "doc_id": cid.partition("::")[0], "text": text}


def test_nguyen_ven(lp):
    ct = chu_thich_chunk(_chunk("TT40-2024::Điều 3"), "2026-08-06", lp)
    assert ct.trang_thai == "nguyen_ven" and ct.ban_hien_hanh is None


def test_da_sua_co_ban_hien_hanh_va_xuat_xu(lp):
    ct = chu_thich_chunk(_chunk("TT40-2024::Điều 8 Khoản 7"), "2026-08-06", lp)
    assert ct.trang_thai == "da_sua"
    assert ct.ban_hien_hanh == _MOI
    assert (ct.sua_boi_doc_id, ct.sua_boi_article) == ("TT41-2025", "Điều 1 Khoản 2")
    assert (ct.xuat_xu_doc_id, ct.xuat_xu_article) == ("TT41-2025", "Điều 1")


def test_bi_bai_bo(lp):
    ct = chu_thich_chunk(_chunk("TT40-2024::Điều 9"), "2026-08-06", lp)
    assert ct.trang_thai == "bi_bai_bo"
    assert "đã bị bãi bỏ bởi" in ct.trich_dan_dung_chu
    assert ct.ban_hien_hanh is None  # bãi bỏ thì KHÔNG có bản hiện hành


def test_chua_toi_ngay_hieu_luc_thi_van_nguyen_ven(lp):
    ct = chu_thich_chunk(_chunk("TT40-2024::Điều 8 Khoản 7"), "2025-01-01", lp)
    assert ct.trang_thai == "nguyen_ven"


def test_nhanh_3_nhan_dien_bang_chu_khong_can_toa_do(lp):
    """Chunk của văn bản SỬA mang đúng khối lời văn mới → trích dẫn về đúng chủ (TT40)."""
    ct = chu_thich_chunk(
        _chunk("TT41-2025::Điều 1", f"Sửa đổi khoản 7 Điều 8 như sau:\n{_MOI}"),
        "2026-08-06",
        lp,
    )
    assert ct.trang_thai == "la_loi_sua"
    assert ct.khoa_dich == "40/2024/TT-NHNN#than/dieu_8#khoan_7"
    assert "TT40-2024" in ct.trich_dan_dung_chu


def test_chunk_van_ban_la_tra_None(lp):
    assert chu_thich_chunk(_chunk("LA-XYZ::Điều 1"), "2026-08-06", lp) is None


def test_artefact_hong_thi_fail_open(tmp_path):
    p = tmp_path / "hong.json"
    p.write_text("{ không phải json", encoding="utf-8")
    tai_lop_phu.cache_clear()
    assert tai_lop_phu(str(p)) is None
    assert chu_thich_chunk(_chunk("TT40-2024::Điều 9"), "2026-08-06", tai_lop_phu(str(p))) is None
    tai_lop_phu.cache_clear()


def test_artefact_thieu_thi_fail_open(tmp_path):
    tai_lop_phu.cache_clear()
    assert tai_lop_phu(str(tmp_path / "khong-co.json")) is None
    tai_lop_phu.cache_clear()


def test_artefact_that_tai_duoc():
    """Artefact do Task 1 sinh phải nạp được và cho ra cạnh.

    **`== 177` là CHIM HOÀNG YẾN canh `data/overlay/lop_phu.json`, không phải một con số cho
    đẹp.** Artefact là dữ liệu tracked mà runtime sống bằng; nó chỉ dựng lại được từ
    `data/raw/vbpl/raw/` — thư mục gitignored, không có trên checkout sạch hay CI. Một lần
    `uv run python -m app.ontology.dong_goi` chạy ở nơi thiếu `raw/` từng ghi đè nó bằng
    `canh: []` mà không ai chặn (`ly_do_tu_choi_ghi` nay chặn, xem `app/ontology/dong_goi.py`).
    Test này là lớp bảo vệ thứ hai.

    Số này ĐỔI ĐƯỢC — nhưng chỉ khi bạn vừa crawl thêm/bớt văn bản và đã đối chứng với
    `eval/overlay/canh_tac_dong.jsonl` (tracked). Thấy nó đỏ mà không biết vì sao thì artefact
    đã bị phá, ĐỪNG chỉnh con số cho xanh — khôi phục artefact bằng `git checkout` trước.

    178 → 177: bỏ đúng một cạnh GIẢ, không phải mất dữ liệu. `menh_lenh` từng nuốt cả khối
    "Nơi nhận" ở đuôi văn bản, nên dòng "- Như Điều 5;" bị đọc thành viện dẫn và đẻ ra cạnh
    "22/2026 Điều 6 Khoản 2 bãi bỏ Điều 5 của 40/2024" — trong khi câu lệnh thật bãi bỏ Điều
    16/17/18 của 41/2025. Xem `_che_khoi_ket` và issue #12. Cả hai artefact đã sinh lại cùng
    lượt nên `eval/overlay/canh_tac_dong.jsonl` cũng là 177.
    """
    tai_lop_phu.cache_clear()
    lp = tai_lop_phu()
    tai_lop_phu.cache_clear()
    assert lp is not None and len(lp.canh) == 177


def test_loai_hit_bi_bai_bo_nhung_giu_hit_con_lai(lp):
    chunks = [_chunk("TT40-2024::Điều 9"), _chunk("TT40-2024::Điều 3")]
    con, ct = chu_thich_ket_qua(chunks, "2026-08-06", lp)
    assert [c["id"] for c in con] == ["TT40-2024::Điều 3"]
    assert ct["TT40-2024::Điều 9"].trang_thai == "bi_bai_bo"  # vẫn chú thích, chỉ không dùng


def test_loai_het_thi_giu_lai_kem_nhan(lp):
    """Hỏi đúng một điều đã bị bãi bỏ: phải nghe 'đã bị bãi bỏ', không phải 'chưa tìm thấy'."""
    con, ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 9")], "2026-08-06", lp)
    assert [c["id"] for c in con] == ["TT40-2024::Điều 9"]
    assert ct["TT40-2024::Điều 9"].trang_thai == "bi_bai_bo"


def test_khong_co_lop_phu_thi_tra_nguyen_danh_sach():
    chunks = [_chunk("TT40-2024::Điều 9")]
    con, ct = chu_thich_ket_qua(chunks, "2026-08-06", None)
    assert con == chunks and ct == {}


def test_da_sua_khong_co_ban_hien_hanh_thi_keo_chunk_xuat_xu(lp, monkeypatch):
    """`bo_sung` không có `ban_hien_hanh` đóng gói sẵn → phải tra chunk xuất xứ về."""
    goi_voi: list[list[str]] = []

    def gia_lay_chunk_theo_id(ids: list[str]) -> list[dict]:
        goi_voi.append(ids)
        return [_chunk("TT41-2025::Điều 3", "Bổ sung Điều 10 như sau: ...")]

    monkeypatch.setattr(
        "app.knowledge.retrieval.lay_chunk_theo_tien_to", gia_lay_chunk_theo_id
    )

    con, ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 10")], "2026-08-06", lp)

    assert ct["TT40-2024::Điều 10"].trang_thai == "da_sua"
    assert ct["TT40-2024::Điều 10"].ban_hien_hanh is None
    assert goi_voi == [["TT41-2025::Điều 3"]]  # gọi đúng id "xuất_xứ_doc::xuất_xứ_điều"
    assert [c["id"] for c in con] == ["TT40-2024::Điều 10", "TT41-2025::Điều 3"]


def test_da_sua_co_san_ban_hien_hanh_thi_khong_keo(lp, monkeypatch):
    """Có `ban_hien_hanh` đóng gói sẵn (sửa trọn đơn vị) → không cần tra thêm."""
    da_goi = False

    def gia_lay_chunk_theo_id(ids: list[str]) -> list[dict]:
        nonlocal da_goi
        da_goi = True
        return []

    monkeypatch.setattr(
        "app.knowledge.retrieval.lay_chunk_theo_tien_to", gia_lay_chunk_theo_id
    )

    con, ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 8 Khoản 7")], "2026-08-06", lp)

    assert ct["TT40-2024::Điều 8 Khoản 7"].ban_hien_hanh == _MOI
    assert da_goi is False
    assert [c["id"] for c in con] == ["TT40-2024::Điều 8 Khoản 7"]


def test_khong_keo_trung_khi_chunk_xuat_xu_da_co_san(lp, monkeypatch):
    """Chunk xuất xứ đã có sẵn trong danh sách hit gốc → không tra lại, không nối trùng."""
    da_goi = False

    def gia_lay_chunk_theo_id(ids: list[str]) -> list[dict]:
        nonlocal da_goi
        da_goi = True
        return [_chunk("TT41-2025::Điều 3")]

    monkeypatch.setattr(
        "app.knowledge.retrieval.lay_chunk_theo_tien_to", gia_lay_chunk_theo_id
    )

    chunks = [_chunk("TT40-2024::Điều 10"), _chunk("TT41-2025::Điều 3")]
    con, ct = chu_thich_ket_qua(chunks, "2026-08-06", lp)

    assert da_goi is False
    assert [c["id"] for c in con] == ["TT40-2024::Điều 10", "TT41-2025::Điều 3"]


def test_tra_chunk_xuat_xu_loi_thi_khong_nem(lp, monkeypatch):
    """`lay_chunk_theo_id` hỏng (lỗi tầng LanceDB) → vẫn trả danh sách bình thường, không ném."""

    def gia_lay_chunk_theo_id(ids: list[str]) -> list[dict]:
        raise RuntimeError("LanceDB lỗi")

    monkeypatch.setattr(
        "app.knowledge.retrieval.lay_chunk_theo_tien_to", gia_lay_chunk_theo_id
    )

    con, ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 10")], "2026-08-06", lp)

    assert [c["id"] for c in con] == ["TT40-2024::Điều 10"]
    assert ct["TT40-2024::Điều 10"].trang_thai == "da_sua"


# --- Fix wave 06/08, CRITICAL 1 (đi qua cả cổng runtime, không chỉ `dinh_tuyen`) ----------
#
# Cùng hai ca đã dựng ở `tests/test_dinh_tuyen.py`, nhưng vào bằng đường THẬT của sản phẩm:
# chunk retrieval → `_span_loi_van` (so bằng CHỮ) → `dinh_tuyen`. Fixture, không đụng
# `data/raw/vbpl/` (gitignored).

_KHOI_ND80 = '"4. Lời văn mới của khoản 4 tới khoản 8 Điều 4."'
_KHOI_ND16 = '"Điều 7 và Điều 1 nay được sửa như sau: ..."'


def _goi_chung_span() -> GoiLopPhu:
    return GoiLopPhu(
        sinh_luc="2026-08-06",
        so_hieu_theo_doc={
            "ND80-2016": "80/2016/NĐ-CP",
            "ND101-2012": "101/2012/NĐ-CP",
            "ND16-2019": "16/2019/NĐ-CP",
        },
        canh=[
            *[
                CanhGoi(
                    nguon="80/2016/NĐ-CP#than/dieu_1#khoan_1",
                    dich=f"101/2012/NĐ-CP#than/dieu_4#khoan_{k}",
                    thao_tac="sua_doi", valid_from="2016-07-01",
                    loi_van_moi=(1071, 1071 + len(_KHOI_ND80)), loi_van_moi_text=_KHOI_ND80,
                    xuat_xu_doc_id="ND80-2016", xuat_xu_article="Điều 1",
                    menh_lenh="Sửa đổi khoản 4, 5, 6, 7, 8 Điều 4 như sau:",
                )
                for k in (4, 5, 6, 7, 8)
            ],
            *[
                CanhGoi(
                    nguon="16/2019/NĐ-CP#than/dieu_4", dich=dich,
                    thao_tac="sua_doi", valid_from="2019-03-20",
                    loi_van_moi=(7121, 7121 + len(_KHOI_ND16)), loi_van_moi_text=_KHOI_ND16,
                    xuat_xu_doc_id="ND16-2019", xuat_xu_article="Điều 4",
                    menh_lenh="Sửa đổi như sau:",
                )
                for dich in ("10/2010/NĐ-CP#than/dieu_7", "57/2016/NĐ-CP#than/dieu_1")
            ],
        ],
    )


@pytest.fixture
def lp_chung_span(tmp_path):
    p = tmp_path / "chung_span.json"
    p.write_text(_goi_chung_span().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    ra = tai_lop_phu(str(p))
    yield ra
    tai_lop_phu.cache_clear()


def test_nam_khoan_chung_mot_khoi_trich_deu_duoc_ke(lp_chung_span):
    ct = chu_thich_chunk(
        _chunk("ND80-2016::Điều 1 Khoản 1", f"1. Sửa đổi Điều 4 như sau:\n{_KHOI_ND80}"),
        "2026-08-06",
        lp_chung_span,
    )
    assert ct.trang_thai == "la_loi_sua"
    assert ct.trich_dan_dung_chu == (
        "ND101-2012 Điều 4 Khoản 4, 5, 6, 7, 8 (sửa bởi ND80-2016 Điều 1 Khoản 1)"
    )
    assert ct.khoa_dich == "101/2012/NĐ-CP#than/dieu_4#khoan_4"


def test_hai_van_ban_nen_chung_mot_khoi_trich_deu_duoc_ke(lp_chung_span):
    ct = chu_thich_chunk(
        _chunk("ND16-2019::Điều 4", f"Điều 4. Sửa đổi\n{_KHOI_ND16}"),
        "2026-08-06",
        lp_chung_span,
    )
    assert ct.trang_thai == "la_loi_sua"
    assert "ND10-2010 Điều 7" in ct.trich_dan_dung_chu
    assert "ND57-2016 Điều 1" in ct.trich_dan_dung_chu


# --- Fix wave 06/08, IMPORTANT 2: kéo lời văn mới về phải TRÚNG khi điều bị chẻ ----------
#
# Ca thật: `TT66-2025 Điều 12` dài 7217 ký tự nên `_split_khoan` chẻ thành 6 mảnh — id
# `"TT66-2025::Điều 12"` KHÔNG tồn tại. Đường kéo cũ hỏi đúng id đó và nhận rỗng ở 31/40 ca.
# Test này đi qua bảng GIẢ dựng từ id thật (`tests/test_lay_chunk_tien_to.py` giữ bảng đó),
# không mock hàm tra.

_CORPUS_REAL = Path("data/corpus.real.json")


def _goi_xuat_xu_dieu_dai() -> GoiLopPhu:
    return GoiLopPhu(
        sinh_luc="2026-08-06",
        so_hieu_theo_doc={"TT34-2024": "34/2024/TT-NHNN", "TT66-2025": "66/2025/TT-NHNN"},
        canh=[
            CanhGoi(
                nguon="66/2025/TT-NHNN#than/dieu_12",
                dich="34/2024/TT-NHNN#than/dieu_5",
                thao_tac="bo_sung",  # `bo_sung` ⇒ KHÔNG có `ban_hien_hanh` ⇒ phải kéo về
                valid_from="2025-07-01",
                xuat_xu_doc_id="TT66-2025",
                xuat_xu_article="Điều 12",
                menh_lenh="Bổ sung Điều 5 như sau:",
            )
        ],
    )


def _bang_corpus_that(monkeypatch) -> list[dict]:
    from tests.test_lay_chunk_tien_to import _BangGia
    from app.ingestion.pipeline import build_chunks, load_corpus
    from app.knowledge import retrieval

    docs, _rels = load_corpus(_CORPUS_REAL)
    hang = [{k: v for k, v in r.items() if k != "vector"} for r in build_chunks(docs)]
    monkeypatch.setattr(retrieval, "_open_table", lambda: _BangGia(hang))
    return hang


@pytest.mark.skipif(not _CORPUS_REAL.exists(), reason="thiếu data/corpus.real.json")
def test_keo_duoc_manh_cua_dieu_bi_che_theo_khoan(tmp_path, monkeypatch):
    hang = _bang_corpus_that(monkeypatch)
    assert not any(r["id"] == "TT66-2025::Điều 12" for r in hang)  # tiền đề của ca này

    p = tmp_path / "dieu_dai.json"
    p.write_text(_goi_xuat_xu_dieu_dai().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    lp_dai = tai_lop_phu(str(p))

    con, ct = chu_thich_ket_qua([_chunk("TT34-2024::Điều 5")], "2026-08-06", lp_dai)
    tai_lop_phu.cache_clear()

    assert ct["TT34-2024::Điều 5"].trang_thai == "da_sua"
    assert ct["TT34-2024::Điều 5"].ban_hien_hanh is None
    keo = [c["id"] for c in con if c["id"] != "TT34-2024::Điều 5"]
    assert keo, "điều xuất xứ bị chẻ theo khoản mà kéo về rỗng — đúng lỗi đang sửa"
    assert all(k.startswith("TT66-2025::Điều 12 ") for k in keo)


# --- Fix wave 06/08, IMPORTANT 3: chunk kéo thêm phải qua ĐỦ ba cổng như mọi hit khác ----
#
# Trước bản vá, chunk kéo thêm vào thẳng `con` mà (1) không có mục nào trong map chú thích nên
# nổi lên UI như một `Citation` trần không nhãn, (2) không qua lọc hiệu lực như mọi đường truy
# hồi khác, (3) không tôn trọng phạm vi văn bản người gọi đã giới hạn (`req.doc_ids` của chat,
# `against_ids` của review) — tức trích một văn bản người dùng đã loại ra.


def _keo_ve(monkeypatch, hang: list[dict]):
    monkeypatch.setattr(
        "app.knowledge.retrieval.lay_chunk_theo_tien_to", lambda ids, **kw: list(hang)
    )


def _hang_xuat_xu(**kw) -> dict:
    goc = {
        "id": "TT41-2025::Điều 3", "doc_id": "TT41-2025", "article": "Điều 3",
        "text": "Bổ sung Điều 10 như sau: ...", "valid_from": "2025-07-01",
        "valid_to": "", "superseded": False,
    }
    return {**goc, **kw}


_KHOI_BO_SUNG = '"Điều 11. Nội dung bổ sung mới."'


def _goi_bo_sung_co_loi_van() -> GoiLopPhu:
    """`bo_sung` CÓ khối lời văn mới đóng gói — chunk kéo về phải nhận nhãn `la_loi_sua`."""
    return GoiLopPhu(
        sinh_luc="2026-08-06",
        so_hieu_theo_doc={"TT40-2024": "40/2024/TT-NHNN", "TT41-2025": "41/2025/TT-NHNN"},
        canh=[
            CanhGoi(
                nguon="41/2025/TT-NHNN#than/dieu_4",
                dich="40/2024/TT-NHNN#than/dieu_11",
                thao_tac="bo_sung",
                valid_from="2025-07-01",
                loi_van_moi=(300, 300 + len(_KHOI_BO_SUNG)),
                loi_van_moi_text=_KHOI_BO_SUNG,
                xuat_xu_doc_id="TT41-2025",
                xuat_xu_article="Điều 4",
                menh_lenh="Bổ sung Điều 11 như sau:",
            )
        ],
    )


def test_chunk_keo_them_duoc_chu_thich(tmp_path, monkeypatch):
    p = tmp_path / "bo_sung.json"
    p.write_text(_goi_bo_sung_co_loi_van().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    lp_bs = tai_lop_phu(str(p))
    _keo_ve(monkeypatch, [
        _hang_xuat_xu(
            id="TT41-2025::Điều 4", article="Điều 4",
            text=f"Bổ sung Điều 11 như sau:\n{_KHOI_BO_SUNG}",
        )
    ])

    con, ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 11")], "2026-08-06", lp_bs)
    tai_lop_phu.cache_clear()

    assert [c["id"] for c in con] == ["TT40-2024::Điều 11", "TT41-2025::Điều 4"]
    assert "TT41-2025::Điều 4" in ct, "chunk kéo thêm nổi lên UI mà không có nhãn"
    assert ct["TT41-2025::Điều 4"].trang_thai == "la_loi_sua"
    assert "TT40-2024 Điều 11" in ct["TT41-2025::Điều 4"].trich_dan_dung_chu


def test_chunk_keo_them_bi_loc_hieu_luc(lp, monkeypatch):
    """Chưa tới ngày hiệu lực / đã hết hiệu lực ⇒ không được kéo vào, như mọi đường truy hồi."""
    _keo_ve(monkeypatch, [_hang_xuat_xu(valid_from="2027-01-01")])
    con, _ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 10")], "2026-08-06", lp)
    assert [c["id"] for c in con] == ["TT40-2024::Điều 10"]

    _keo_ve(monkeypatch, [_hang_xuat_xu(superseded=True)])
    con, _ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 10")], "2026-08-06", lp)
    assert [c["id"] for c in con] == ["TT40-2024::Điều 10"]


def test_chunk_keo_them_ton_trong_pham_vi(lp, monkeypatch):
    """Người gọi đã giới hạn văn bản ⇒ không kéo về chunk của văn bản ngoài phạm vi."""
    goi_voi: list[list[str]] = []

    def _gia(ids, **kw):
        goi_voi.append(ids)
        return [_hang_xuat_xu()]

    monkeypatch.setattr("app.knowledge.retrieval.lay_chunk_theo_tien_to", _gia)

    con, _ct = chu_thich_ket_qua(
        [_chunk("TT40-2024::Điều 10")], "2026-08-06", lp, pham_vi={"TT40-2024"}
    )
    assert [c["id"] for c in con] == ["TT40-2024::Điều 10"]
    assert goi_voi == [], "không được hỏi chunk của văn bản ngoài phạm vi"

    con, _ct = chu_thich_ket_qua(
        [_chunk("TT40-2024::Điều 10")], "2026-08-06", lp,
        pham_vi={"TT40-2024", "TT41-2025"},
    )
    assert [c["id"] for c in con] == ["TT40-2024::Điều 10", "TT41-2025::Điều 3"]


def test_chunk_thieu_hoac_rong_id_thi_khong_nem(lp):
    """Chunk hiểm (thiếu hẳn khoá `id`, hoặc `id` rỗng) không được làm sập `chu_thich_ket_qua`.

    `chu_thich_chunk` đã phòng bằng `chunk.get("id") or ""`; hàm này phải giữ đúng cùng hợp
    đồng — không index thẳng `c["id"]`.
    """
    thieu_id = {"doc_id": "TT40-2024", "text": "nội dung nền"}  # không có khoá "id"
    id_rong = _chunk("")

    con, ct = chu_thich_ket_qua([thieu_id, id_rong, _chunk("TT40-2024::Điều 3")], "2026-08-06", lp)

    assert thieu_id in con
    assert id_rong in con
    assert "TT40-2024::Điều 3" in [c.get("id") for c in con]
    assert None not in ct and "" not in ct  # không bịa khoá rác vào map
