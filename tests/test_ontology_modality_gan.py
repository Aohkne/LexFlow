"""Gán nhãn tình thái tất định cho ActorCU — 6 nhãn VN, không hỏi LLM."""
from app.ontology.modality import gan_modality


def test_sau_nhan_co_ban():
    assert gan_modality("Ngân hàng phải cung cấp thông tin") == "nghia_vu"
    assert gan_modality("không được thu phí ngoài biểu phí") == "cam"
    assert gan_modality("khách hàng được quyền tra soát") == "cho_phep"
    assert gan_modality("chỉ được thu phí khi đã niêm yết") == "chi_duoc"
    assert gan_modality("không phải bồi thường thiệt hại") == "mien_tru"
    assert gan_modality("danh sách đơn vị chấp nhận thanh toán") == "khong_ro"


def test_chi_duoc_thang_duoc():
    # BẪY: "chỉ được" chứa "được" — khớp dài nhất trước phải thắng
    assert gan_modality("chỉ được cung ứng dịch vụ khi có Giấy phép") == "chi_duoc"


def test_khong_phai_la_khong_phai_mien_tru():
    # "không phải LÀ" = phủ định danh xưng, không phải miễn trừ nghĩa vụ
    assert gan_modality("tổ chức không phải là ngân hàng phải đăng ký") == "nghia_vu"


def test_uu_tien_cam_truoc():
    # Câu vừa có "phải" vừa có "không được" → cấm thắng (khắt khe hơn)
    assert gan_modality("phải niêm yết và không được thu thêm") == "cam"


def test_duoc_mien():
    assert gan_modality("được miễn phí dịch vụ trong 12 tháng") == "mien_tru"
