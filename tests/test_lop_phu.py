"""Cổng runtime của lớp phủ: chunk retrieval → chú thích hiệu lực cấp khoản."""
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
    """Artefact do Task 1 sinh phải nạp được và cho ra cạnh."""
    tai_lop_phu.cache_clear()
    lp = tai_lop_phu()
    tai_lop_phu.cache_clear()
    assert lp is not None and len(lp.canh) == 178


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
        "app.knowledge.retrieval.lay_chunk_theo_id", gia_lay_chunk_theo_id
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
        "app.knowledge.retrieval.lay_chunk_theo_id", gia_lay_chunk_theo_id
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
        "app.knowledge.retrieval.lay_chunk_theo_id", gia_lay_chunk_theo_id
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
        "app.knowledge.retrieval.lay_chunk_theo_id", gia_lay_chunk_theo_id
    )

    con, ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 10")], "2026-08-06", lp)

    assert [c["id"] for c in con] == ["TT40-2024::Điều 10"]
    assert ct["TT40-2024::Điều 10"].trang_thai == "da_sua"


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
