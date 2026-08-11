"""Test từ điển tình thái + kiểm thêm/bớt — offline, hàm thuần."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.ontology.modality import (
    MODALITY,
    explain,
    find_markers,
    find_numbers,
    modality_delta,
    relax_dereference,
)
from app.ontology.parser import parse_dieu
from app.ontology.segmenter import segment

_FIXTURE = Path("data/fixtures/ND52-2024-dieu22.txt")

# Chuỗi Gemini trả THẬT ở giai đoạn 1 — luật viết "cấp Giấy phép KHI đáp ứng đầy đủ",
# mô hình viết "PHẢI đáp ứng đầy đủ", biến điều kiện được cấp phép thành nghĩa vụ.
_HALLUCINATION = (
    "phải đáp ứng đầy đủ và phải đảm bảo duy trì đủ các điều kiện sau đây "
    "trong quá trình cung ứng dịch vụ trung gian thanh toán"
)
_TRUNG_THANH = "khi đáp ứng đầy đủ và phải đảm bảo duy trì đủ các điều kiện sau đây"


@pytest.fixture(scope="module")
def chapeau():
    """Câu bao trùm thật của ND52 Điều 22 khoản 2."""
    dieu = parse_dieu(_FIXTURE.read_text(encoding="utf-8"), "52/2024/NĐ-CP")
    units = segment(dieu, dieu.khoan[1])
    return next(u for u in units if u.uid == 2).text


def test_khop_dai_nhat_truoc():
    """BẪY CHÍNH: 'được' là chuỗi con của 'không được'.

    Khớp ngắn trước thì mọi câu CẤM bị đọc thành CHO PHÉP — đảo ngược nghĩa pháp lý.
    """
    m = find_markers("Tổ chức không được kết nối quá 02 tổ chức")
    assert m["không được"] == 1
    assert m["được"] == 0
    assert find_markers("tổ chức được cấp Giấy phép")["được"] == 1
    assert find_markers("không được phép cung ứng")["không được phép"] == 1


def test_bien_tu_khong_khop_giua_tu():
    # "cấm" không được khớp trong "cẩm nang"; biên từ phải tính cả dấu tiếng Việt.
    assert find_markers("nghiêm cấm hành vi")["cấm"] == 0
    assert find_markers("nghiêm cấm hành vi")["nghiêm cấm"] == 1


def test_bang_tu_dien_khong_trung_lap():
    phrases = [p for ps in MODALITY.values() for p in ps]
    assert len(phrases) == len(set(phrases))


def test_them_nghia_vu_la_loi_cung():
    d = modality_delta("tổ chức phải nộp báo cáo", "tổ chức nộp báo cáo")
    assert d.hard_error
    assert d.invented_groups == ["nghia_vu"]


def test_phan_phoi_lenh_cam_khong_bi_bao_nham():
    """Case báo nhầm THẬT gặp ở TT40 Điều 25 khoản 5.

    Luật cấm 2 vế ("không được X; không được phép Y, Z"), mô hình viết lại thành 3
    vế "không được". Đếm theo số lần ra "thêm 2 lệnh cấm" — nhưng nguồn đã cấm sẵn,
    mô hình chỉ phân phối lệnh cấm ra từng ý. Chỉ tính BỊA khi nguồn KHÔNG có dấu
    hiệu nào thuộc nhóm đó.
    """
    source = ("không được nhận tiền mặt từ khách hàng để nạp tiền vào ví điện tử; "
              "không được phép cấp tín dụng cho khách hàng sử dụng ví điện tử, "
              "trả lãi trên số dư ví điện tử")
    claim = ("không được nhận tiền mặt để nạp tiền vào ví điện tử, không được cấp "
             "tín dụng, không được trả lãi trên số dư ví điện tử")
    d = modality_delta(claim, source)
    assert not d.hard_error
    assert d.invented_groups == []


def test_thay_tu_dong_nghia_chi_dieu_kien_khong_bi_bao_nham():
    """Case báo nhầm THẬT gặp ở TT17 Điều 16 khoản 2 điểm d.

    Luật viết "trong trường hợp có dấu hiệu mất an toàn", mô hình viết "khi có dấu
    hiệu mất an toàn" — cùng nhóm dieu_kien, điều kiện vẫn còn nguyên. Quy tắc
    "điều kiện → nghĩa vụ" chỉ được nổ khi diễn giải KHÔNG còn dấu hiệu điều kiện.
    """
    source = ("Ngân hàng phải thường xuyên kiểm tra, đánh giá và thực hiện tạm dừng "
              "cung ứng dịch vụ trong trường hợp có dấu hiệu mất an toàn")
    claim = ("phải thường xuyên kiểm tra, đánh giá và thực hiện tạm dừng cung ứng "
             "dịch vụ khi có dấu hiệu mất an toàn")
    d = modality_delta(claim, source)
    assert not d.condition_to_obligation
    assert not d.hard_error


def test_bia_so_la_loi_cung():
    d = modality_delta("vốn tối thiểu 500 tỷ đồng", "vốn tối thiểu 50 tỷ đồng")
    assert d.hard_error
    assert d.added_numbers == ["500"]
    # Số viết có dấu phân cách vẫn nhận ra là cùng một số.
    assert find_numbers("1.000 tỷ") == find_numbers("1000 tỷ")


def test_mat_dieu_kien_khong_kem_nghia_vu_chi_la_canh_bao():
    d = modality_delta("đáp ứng các điều kiện cấp phép", "khi đáp ứng các điều kiện cấp phép")
    assert not d.hard_error
    assert d.soft_warning
    assert d.lost["dieu_kien"] == ["khi"]


def test_hallucination_that_bi_chan_cung(chapeau):
    """Test hồi quy cho lỗi ĐÃ GẶP THẬT ở giai đoạn 1.

    Bắt được là nhờ luật "mất điều kiện + có nghĩa vụ" (`condition_to_obligation`),
    không phụ thuộc phép đếm thêm/bớt đơn thuần theo vị trí. Từ khi thêm nhóm
    `mien_tru` ("không phải"), "không phải là ngân hàng" trong nguồn giờ khớp cụm
    "không phải" thay vì lẫn vào phrase "phải" như trước — đếm thêm/bớt tình cờ cũng
    thấy dư 1 "phải", không còn triệt tiêu như khi "không phải" chưa có trong từ điển.
    Đây là hệ quả phụ của việc mở rộng từ điển, không phải bằng chứng cốt lõi của test:
    cốt lõi vẫn là `condition_to_obligation` bắt được lỗi mà đếm tập hợp một mình bỏ lọt.
    """
    d = modality_delta(_HALLUCINATION, chapeau)
    assert d.hard_error
    assert d.condition_to_obligation
    assert any("ĐIỀU KIỆN" in m and "NGHĨA VỤ" in m for m in d.describe())


def test_dien_giai_trung_thanh_thi_sach(chapeau):
    d = modality_delta(_TRUNG_THANH, chapeau)
    assert not d.hard_error
    assert d.describe() == []


def test_label_rong_khong_bi_phat(chapeau):
    assert not modality_delta("", chapeau).hard_error


# --- Hai chế độ báo nhầm bị ĐƠN VỊ LỚN HƠN phơi ra ---------------------------
#
# Sau khi segmenter gom dòng nối tiếp lại, span nguồn dài hơn hẳn. Cả hai luật dưới đây
# vẫn đúng như cũ trên đoạn ngắn, nhưng trên đoạn dài thì nổ nhầm — và cả hai đều là
# khiếm khuyết CÓ SẴN, chỉ chưa gặp dữ liệu đủ dài để lộ ra.


def test_doan_replace_dai_khong_phai_dao_cuc():
    """Case báo nhầm THẬT ở ND52 Điều 26 khoản 1 (đo được sau khi gom dòng).

    Nhãn nén cả một danh sách liệt kê thành một mệnh đề, difflib gióng 29 từ nguồn với
    6 từ nhãn. Hai vế tình cờ khác nhóm tình thái ('được' vs 'khi') nên bị đọc là đảo
    cực. Đảo cực là phát biểu về việc TRÁO MỘT TỪ — hai vế phải ngắn thì mới có nghĩa.
    """
    source = ("Trường hợp thay đổi một trong các nội dung quy định trong Giấy phép hoạt "
              "động cung ứng dịch vụ trung gian thanh toán sau: tên tổ chức, địa điểm đặt "
              "trụ sở chính, ngừng cung cấp một hoặc một số dịch vụ trung gian thanh toán "
              "đã được cấp phép, kết nối thêm hệ thống thanh toán quốc tế")
    claim = "Tổ chức cung ứng dịch vụ trung gian thanh toán khi thay đổi nội dung Giấy phép"
    d = modality_delta(claim, source)
    assert d.flips == []
    assert not d.hard_error
    # Nhưng phép tráo NGẮN thì vẫn phải bắt được — không được nới thành vô dụng.
    assert modality_delta("tổ chức phải nộp", "tổ chức khi nộp").flips == [("khi", "phải")]


def test_chep_lai_lenh_cam_roi_bo_duoi_khong_phai_dieu_kien_thanh_nghia_vu():
    """Case báo nhầm THẬT ở TT17 Điều 16 khoản 1 điểm c.

    Luật: *"các hành vi **không được** thực hiện **khi** mở và sử dụng tài khoản…"*.
    Nhãn CHÉP LẠI lệnh cấm rồi bỏ phần đuôi danh ngữ. Chữ "khi" bị mất nằm TRONG danh
    ngữ, không chi phối toán tử tình thái — không hề có chuyện biến điều kiện thành
    nghĩa vụ. Ba vế cũ của luật không tách được nó khỏi case gốc vì cả hai đều "mất
    dieu_kien + có ràng buộc cứng + nhãn hết dieu_kien"; cặp (dấu hiệu + từ liền sau)
    thì tách được: `"không được thực"` CÓ nguyên văn trong nguồn.
    """
    source = ("Hiển thị cảnh báo cho khách hàng về các hành vi không được thực hiện khi mở "
              "và sử dụng tài khoản thanh toán bằng phương tiện điện tử và có giải pháp kỹ "
              "thuật xác nhận đảm bảo việc khách hàng đã đọc đầy đủ các nội dung cảnh báo")
    claim = "hiển thị cảnh báo về hành vi không được thực hiện và xác nhận khách hàng đã đọc"
    d = modality_delta(claim, source)
    assert not d.condition_to_obligation
    assert not d.hard_error
    assert d.lost["dieu_kien"] == ["khi"]  # vẫn nêu ra như một cảnh báo


def test_dereference_dieu_nay_bi_bat_o_tang_dem_so():
    """Phép đếm một mình vẫn phải coi đây là bịa số — nới là việc của tầng sau."""
    d = modality_delta("Quy định tại khoản 1 Điều 26", "Quy định tại khoản 1 Điều này")
    assert d.hard_error and d.added_numbers == ["26"]


# --- `relax_dereference`: nới ĐÚNG một khuôn, và chỉ khuôn đó -----------------
#
# Đo trước khi dựng: quét 294 nhãn trong `pred.jsonl`, **1** nhãn thêm số so với đoạn
# đã neo, và đúng nó khớp khuôn này. Không có case nào "nguồn có viện dẫn tương đối
# nhưng số thêm vào KHÁC" — tức corpus hiện tại không kiểm được vế chống lọt. Vì vậy
# vế đó phải được canh bằng test dựng tay ở dưới, không thể dựa vào dữ liệu.

_NGUON = "Quy định tại khoản 1 Điều này không áp dụng đối với"


def test_khai_trien_dieu_nay_duoc_ha_muc():
    d = modality_delta("Quy định tại khoản 1 Điều 26", _NGUON)
    out, notes = relax_dereference(d, "Quy định tại khoản 1 Điều 26", _NGUON,
                                   so_dieu=26, so_khoan=2)
    assert not out.hard_error and out.added_numbers == []
    assert any("khai triển viện dẫn tương đối" in n and "references" in n for n in notes)


def test_khong_ha_muc_khi_so_khong_khop_don_vi_dang_xet():
    """Mô hình ghi *"Điều 27"* trong khi đang ở Điều 26 — đó là trỏ sai đích, phải đỏ."""
    claim = "Quy định tại khoản 1 Điều 27"
    d = modality_delta(claim, _NGUON)
    out, notes = relax_dereference(d, claim, _NGUON, so_dieu=26, so_khoan=2)
    assert out.hard_error and out.added_numbers == ["27"] and notes == []


def test_khong_ha_muc_khi_nguon_khong_co_cum_tu_tro():
    """Nguồn không hề viết *"Điều này"* thì số kia không phải khai triển của gì cả."""
    claim = "Quy định tại khoản 1 Điều 26"
    src = "Quy định tại khoản 1 không áp dụng đối với"
    d = modality_delta(claim, src)
    out, notes = relax_dereference(d, claim, src, so_dieu=26, so_khoan=2)
    assert out.hard_error and notes == []


def test_khong_ha_muc_khi_so_lac_o_cho_khac_trong_nhan():
    """Vế chống lọt: số khớp Điều đang xét nhưng KHÔNG đứng sau chữ "Điều".

    Thiếu vế này thì một nhãn bịa *"áp dụng cho 26 tổ chức"* nằm trong Điều 26 cũng
    được tha — mà đó mới đúng là bịa số. Corpus chưa có case nào như vậy nên test này
    dựng tay, và nói rõ là dựng tay.
    """
    claim = "Quy định này áp dụng cho 26 tổ chức"
    d = modality_delta(claim, _NGUON)
    assert d.added_numbers == ["26"]
    out, notes = relax_dereference(d, claim, _NGUON, so_dieu=26, so_khoan=2)
    assert out.hard_error and out.added_numbers == ["26"] and notes == []


def test_chi_ha_dung_so_khop_giu_nguyen_so_con_lai():
    claim = "Quy định tại khoản 1 Điều 26 áp dụng cho 500 tỷ đồng"
    d = modality_delta(claim, _NGUON)
    assert set(d.added_numbers) == {"26", "500"}
    out, notes = relax_dereference(d, claim, _NGUON, so_dieu=26, so_khoan=2)
    assert out.added_numbers == ["500"] and out.hard_error
    assert len(notes) == 1


def test_khoan_khong_co_so_thi_khong_khop_duoc():
    """Điều không chẻ khoản ⇒ `so_khoan=0`, "khoản này" không có số để khớp."""
    claim = "quy định tại khoản 0 Điều này"
    d = modality_delta(claim, "quy định tại khoản này")
    out, _ = relax_dereference(d, claim, "quy định tại khoản này", so_dieu=26, so_khoan=0)
    assert out.added_numbers == d.added_numbers


def test_explain_chi_dich_danh_chu_bi_doi():
    out = explain("tổ chức phải nộp báo cáo", "tổ chức khi nộp báo cáo")
    assert "'khi'" in out and "'phải'" in out
    assert explain("y hệt", "y hệt") == "(không khác biệt ở mức từ)"
