"""Bản ghi vbpl đã crawl → `CorpusDocument`. Offline, đọc `data/raw/vbpl/`.

Điều đáng canh nhất là **đánh số khoản/điểm**, vì mất nó thì cả tầng ontology mất theo mà
**không lỗi nào bắn ra**: `parse_dieu` chỉ trả về 0 khoản, và một văn bản 0 khoản trông y hệt
một văn bản không chẻ khoản (25/267 điều thật sự như thế). Đo trên TT15/2024 — văn bản duy nhất
có ở cả corpus lẫn bản crawl nên so được: `articles[].text` của bản crawl cho **0/0**, còn
`noi_dung` thô cho **102 khoản / 57 điểm**.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.vbpl_corpus import (
    dieu_tu_ban_ghi,
    dieu_tu_toan_van,
    doc_file,
    doc_id_theo_corpus,
    duong_dan_toan_van,
    file_da_chuyen_khuon,
    phan_cap_tu_cay,
)
from app.ontology.parser import parse_dieu

_GOC = Path("data/raw/vbpl")


def _tim(so_hieu: str) -> Path | None:
    """Tra file đã chuyển khuôn theo **số hiệu bên trong**, không theo đường dẫn cứng.

    Bố cục đã đổi hai lần (`<slug>.corpus.json` → `corpus/<slug>.json`) và lần nào đường dẫn
    cứng cũng lặng lẽ chuyển cả file test này sang skip — suite vẫn xanh, chỉ là không kiểm gì.
    """
    for p in file_da_chuyen_khuon(_GOC):
        if json.loads(p.read_text(encoding="utf-8")).get("so_hieu") == so_hieu:
            return p
    return None


_TT15 = _tim("15/2024/TT-NHNN")
_VBHN = _tim("29/VBHN-NHNN")

# Guard phải kiểm CẢ HAI bố cục, không chỉ `corpus/`. `_tim` tìm trong `corpus/` — thư mục
# được version — nên trên CI nó LUÔN tìm thấy; nhưng mọi test dưới đây đọc tiếp bản ghi thô ở
# `data/raw/vbpl/raw/`, vốn **gitignored**. Guard cũ chỉ hỏi vế đầu nên trên CI nó cho chạy rồi
# vỡ bằng `FileNotFoundError` — CI đỏ liên tục từ 05/08 vì đúng chỗ này, trong khi ở máy có
# thư mục `raw/` thì suite vẫn xanh. Đây là mặt trái của việc gitignore nguồn: cái chạy được
# trên một máy không chạy được ở nơi khác, và test là chỗ đầu tiên lộ ra.
_THIEU_TOAN_VAN = _TT15 is None or not duong_dan_toan_van(_TT15).exists()
pytestmark = pytest.mark.skipif(
    _THIEU_TOAN_VAN,
    reason="chưa crawl TT15/2024, hoặc thiếu bản ghi thô data/raw/vbpl/raw/ (gitignored)",
)


def _dem(arts, so_hieu="15/2024/TT-NHNN") -> tuple[int, int]:
    kh = di = 0
    for a in arts:
        d = parse_dieu(f"{a.article}. {a.text}", so_hieu)
        kh += len(d.khoan)
        di += sum(len(k.diem) for k in d.khoan)
    return kh, di


# --- 1. articles[] đã được sửa, và ĐÓ là thứ phải kiểm ------------------------


def test_articles_giu_du_danh_so():
    """Lượt crawl đầu cho **0 khoản / 0 điểm** ở đây — làm phẳng cây làm mất đánh số.

    Test cũ khoá con số 0 đó lại và ghi *"ngày nào bộ crawl sửa được thì test này sẽ đỏ, và đỏ
    ở đây là tin tốt"*. Ngày đó đã tới; con số nghiệm thu 23/98/57 nay là hợp đồng với nguồn.

    (98, không phải 97 như nghiệm thu đầu: con số 97 đo bằng thước hỏng — `_KHOAN_RE` đòi dấu
    cách sau chấm, còn vbpl in `3.Dịch vụ thu hộ` dính liền, nên khoản 3 Điều 14 bị nuốt vào
    khoản 2. Cây sau sửa khớp corpus cũ từng khoản.)
    """
    kq = doc_file(_TT15)
    assert kq.van_ban is not None
    assert (len(kq.van_ban.articles), *_dem(kq.van_ban.articles)) == (23, 98, 57)


def test_char_span_la_thu_lam_articles_DANG_TIN():
    """Không tin suông: `noi_dung[char_start:char_end] == text` kiểm được ngay tại đây.

    Đây đúng là bất biến xuất xứ mà cả tầng ontology dựa vào, nên nguồn tự bảo đảm được nó là
    lý do duy nhất đủ mạnh để lấy `articles[]` làm nguồn thay vì tự dựng lại.
    """
    raw = json.loads(_TT15.read_text(encoding="utf-8"))
    nd = json.loads(duong_dan_toan_van(_TT15).read_text(encoding="utf-8"))["noi_dung"]
    assert raw["articles"], "bản ghi phải có articles"
    for a in raw["articles"]:
        assert nd[a["char_start"] : a["char_end"]] == a["text"], a["article"]


def test_char_span_sai_thi_TU_CHOI_ca_van_ban():
    """Nạp một xuất xứ không kiểm được còn tệ hơn không nạp: mọi `char_span` sau đó đều trỏ sai."""
    raw = {
        "so_hieu": "1/2020/TT-NHNN",
        "articles": [{"article": "Điều 1", "text": "Nội dung.", "char_start": 0, "char_end": 9}],
    }
    dieu, cb = dieu_tu_ban_ghi(raw, "Nội dung.")
    assert len(dieu) == 1 and cb == []

    dieu, cb = dieu_tu_ban_ghi(raw, "NỘI DUNG KHÁC HẲN.")
    assert dieu == [], "lệch char_span thì không được nạp phần nào"
    assert any("TỪ CHỐI" in c for c in cb)


def test_doi_chung_bat_lai_dung_khuyet_tat_cu():
    """Phép dựng lại từ `noi_dung` ở lại làm đối chứng — cái đã hỏng một lần thì hỏng lại được.

    Dựng bản ghi mang đúng chữ ký của khuyết tật cũ: `text` mất hết `1.`/`a)`, `char_span` vẫn
    khớp. Chỉ `char_span` thôi **không** bắt được ca này, nên cần lớp thứ hai.
    """
    nd = "Điều 1. Phạm vi\n1. Khoản một.\na) Điểm a.\nĐiều 2. Đối tượng\n1. Khoản một."
    mat_so = "Phạm vi\nKhoản một.\nĐiểm a."
    raw = {
        "so_hieu": "1/2020/TT-NHNN",
        "articles": [
            {"article": "Điều 1", "text": mat_so,
             "char_start": len(nd) + 1, "char_end": len(nd) + 1 + len(mat_so)},
            {"article": "Điều 2", "text": "Đối tượng",
             "char_start": len(nd) + 2 + len(mat_so), "char_end": len(nd) + 11 + len(mat_so)},
        ],
    }
    dieu, cb = dieu_tu_ban_ghi(raw, nd + "\n" + mat_so + "\nĐối tượng")
    assert len(dieu) == 2, "char_span vẫn khớp nên lớp 1 cho qua"
    assert any("0 khoản" in c for c in cb), "lớp 2 phải bắt được"


def test_duoi_hanh_chinh_khong_vao_dieu_cuoi():
    """vbpl dán khối `Nơi nhận:` + chữ ký (TT40 còn cả 7k ký tự phụ lục biểu mẫu) vào sau
    điều cuối. Phần đó không thuộc điều nào — v0.5 dành nhánh `#phuluc_` riêng cho phụ lục —
    nên phải cắt trước khi thành `CorpusDocument`, và cắt CÓ VẾT (cảnh báo nói rõ cắt bao nhiêu).
    """
    kq = doc_file(_TT15)
    cuoi = kq.van_ban.articles[-1]
    assert "Nơi nhận" not in cuoi.text
    assert "(Đã ký)" not in cuoi.text
    assert cuoi.text.endswith("chịu trách nhiệm thi hành Thông tư này.")
    assert any("đuôi hành chính" in c for c in kq.canh_bao)


def test_cat_duoi_chi_dong_vao_dieu_cuoi():
    """Đuôi thật ở cả 5/8 văn bản crawl là **dòng đúng bằng** `Nơi nhận:` — danh sách nơi
    nhận nằm các dòng sau. `Nơi nhận: …` có nội dung cùng dòng là chữ trong thân, không cắt."""
    from app.core.schemas import Article
    from app.ingestion.vbpl_corpus import cat_duoi_hanh_chinh

    giua = Article(article="Điều 1", text="Thân điều.\nNơi nhận:\n-Bẫy: y hệt đuôi nhưng KHÔNG ở điều cuối.")
    cuoi = Article(article="Điều 2", text="Hiệu lực./.\nNơi nhận:\n-Lưu VT.\nTHỐNG ĐỐC\n(Đã ký)")
    dieu, bo = cat_duoi_hanh_chinh([giua, cuoi])
    assert dieu[0].text == giua.text, "điều giữa không được đụng"
    assert dieu[1].text == "Hiệu lực./."
    assert bo == len(cuoi.text) - len("Hiệu lực./.")

    trong_cau = Article(article="Điều 9", text="Thân.\nNơi nhận: hồ sơ nộp về Vụ Thanh toán.")
    sach, bo0 = cat_duoi_hanh_chinh([trong_cau])
    assert bo0 == 0 and sach[0].text == trong_cau.text


# --- 2. Chương/Mục: việc duy nhất cây provisions làm được ---------------------


def test_chuong_muc_lay_tu_cay_dien_du_23_dieu():
    """`Article.chapter` khai đã lâu mà 0/278 điều có giá trị — nguồn vbpl có sẵn."""
    moi = doc_file(_TT15).van_ban
    assert all(a.chapter for a in moi.articles)
    assert next(a for a in moi.articles if a.article == "Điều 2").chapter == "Chương I. QUY ĐỊNH CHUNG"


def test_cay_rong_thi_khong_gan_bua_nhan_phan_cap():
    assert phan_cap_tu_cay([]) == {}
    arts = dieu_tu_toan_van("Điều 1. Phạm vi\nNội dung điều một.", [])
    assert len(arts) == 1 and arts[0].chapter is None and arts[0].section is None


# --- 3. doc_id: theo quy ước corpus, không sinh không gian tên thứ ba ---------


@pytest.mark.parametrize(
    ("so_hieu", "cho"),
    [
        ("101/2012/NĐ-CP", "ND101-2012"),   # khớp corpus đang có
        ("15/2024/TT-NHNN", "TT15-2024"),   # khớp corpus đang có
        ("29/VBHN-NHNN", "VBHN29-NHNN"),    # không năm ⇒ lấy cơ quan làm phần phân biệt
        ("59/2020/QH14", "L59-2020"),
        ("không phải số hiệu", None),
    ],
)
def test_doc_id_theo_quy_uoc_corpus(so_hieu, cho):
    assert doc_id_theo_corpus(so_hieu) == cho


def test_bo_crawl_nay_da_theo_quy_uoc_corpus():
    """Lượt đầu bộ crawl đặt `15-2024-TT-NHNN` — theo nó ⇒ **hai node cho một văn bản**. Lượt
    này nó đã theo `TT15-2024`, nên không còn cảnh báo nào để bắn.
    """
    kq = doc_file(_TT15)
    assert kq.doc_id_trong_file == "TT15-2024"
    assert kq.van_ban.doc_id == "TT15-2024"
    assert not any("quy ước corpus" in c for c in kq.canh_bao)


def test_neu_nguon_lech_quy_uoc_lan_nua_thi_van_bao_ra():
    """Chốt chặn phải còn sống kể cả khi hiện không ca nào chạm tới — nguồn đổi lại được."""
    from app.ingestion.vbpl_corpus import doc_id_theo_corpus

    assert doc_id_theo_corpus("15/2024/TT-NHNN") == "TT15-2024" != "15-2024-TT-NHNN"


# --- 4. Không có toàn văn thì KHÔNG giả vờ là có -----------------------------


@pytest.mark.skipif(not _VBHN.exists(), reason="chưa crawl 29/VBHN-NHNN")
def test_van_ban_khong_co_toan_van_thi_giu_lam_node_rong():
    kq = doc_file(_VBHN)
    assert kq.van_ban is None, "0 điều mà vẫn dựng CorpusDocument là khai khống"
    assert kq.so_hieu == "29/VBHN-NHNN"
    assert any("0 điều" in c for c in kq.canh_bao)


def test_thieu_ban_ghi_tho_thi_TU_CHOI_chu_khong_bo_qua_kiem_tra():
    """Không có `noi_dung` thì không kiểm được `char_span` — mà đó là điều kiện để tin `articles[]`."""
    assert duong_dan_toan_van(_TT15).exists()
    assert "noi_dung" in json.loads(duong_dan_toan_van(_TT15).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("duong_dan", "cho"),
    [
        ("data/raw/vbpl/corpus/x.json", "data/raw/vbpl/raw/x.json"),   # bố cục thư mục
        ("data/raw/vbpl/x.corpus.json", "data/raw/vbpl/x.json"),       # bố cục phẳng, lượt đầu
    ],
)
def test_hai_bo_cuc_thu_muc_deu_tim_duoc_ban_ghi_tho(duong_dan, cho):
    """Bộ đọc chỉ hiểu một bố cục thì lần đổi sau nó đọc ra **0 văn bản mà không kêu**."""
    assert duong_dan_toan_van(Path(duong_dan)).as_posix() == cho
