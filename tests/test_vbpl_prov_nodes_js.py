"""Test cho đoạn JS bóc nút điều khoản — chạy Chromium trên HTML tĩnh, KHÔNG chạm mạng.

Phần còn lại của bộ test parse thuần Python (`test_vbpl_parse.py`) không với tới được
`_JS_PROVISION_NODES`, mà chính chỗ đó mới quyết định cây điều khoản đủ hay thiếu. Ở đây dựng
lại đúng hình dạng DOM đã quan sát được trên trang thật rồi chạy JS lên nó.

Thẻ trong bản dựng là `div` chứ không phải `p` như trang thật: trình duyệt tự đóng `<p>` khi
gặp `<p>` lồng bên trong lúc parse HTML, nên không dựng lại được bằng `set_content` (trang thật
dựng bằng React nên lồng được). Đoạn JS chọn phần tử theo class và attribute `type`, không đụng
tới tên thẻ, nên khác biệt này không ảnh hưởng điều đang kiểm tra.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.ingestion.vbpl import _JS_PROVISION_NODES, build_provision_tree, count_provisions

# Điều 10 Thông tư 34/2024/TT-NHNN như vbpl.vn dựng (đã rút gọn phần chữ):
# khối sửa đổi mang `type`, bên trong CÓ thẻ prov-item cho các Điểm nhưng KHÔNG có thẻ nào cho
# dòng Khoản mở đầu — Khoản 1 và 2 chỉ tồn tại dưới dạng text thuần.
HTML_TT34_DIEU_10 = """
<main>
  <style>[type] { display: flex; flex-direction: column; }</style>
  <div class="prov-article" id="id_d10">Điều 10. Quy định chung về những thay đổi</div>

  <div class="flex flex-col p-2" type="10:d9917a40-30c0-11f1-b62c-2fd0cee162fe">
    <button>Điều khoản được sửa đổi, bổ sung</button>
    <span>1. Văn phòng đại diện nước ngoài lập hồ sơ đề nghị sửa đổi, bổ sung Giấy phép:</span>
    <div class="prov-item" id="id_a1">a) Thay đổi tên;</div>
    <div class="prov-item" id="id_b1">b) Thay đổi địa bàn đặt trụ sở;</div>
    <div class="prov-item" id="id_c1">c) Gia hạn thời hạn hoạt động.</div>
  </div>
  <div class="prov-item" parent-id="id_cu1" style="display:none">a) Thay đổi tên;</div>
  <div class="prov-item" parent-id="id_cu1" style="display:none">b) Thay đổi địa bàn đặt trụ sở;</div>

  <div class="flex flex-col p-2" type="10:d9917a40-30c0-11f1-b62c-2fd0cee162fe">
    <button>Điều khoản được sửa đổi, bổ sung</button>
    <span>2. Văn phòng đại diện nước ngoài nộp văn bản thông báo:</span>
    <div class="prov-item" id="id_a2">a) Thay đổi Trưởng văn phòng đại diện nước ngoài;</div>
    <div class="prov-item" id="id_b2">b) Thay đổi địa điểm đặt trụ sở;</div>
  </div>

  <div class="prov-clause" id="id_k3">3. Sau khi được sửa đổi, bổ sung Giấy phép.</div>
</main>
"""

# Ca đã chạy đúng từ trước, giữ lại làm đối chứng: khối mở đầu bằng tiêu đề ĐIỀU (trang không
# gắn class cho nó) và có sẵn thẻ prov-clause cho Khoản bên dưới. Chỉ được bù đúng tiêu đề Điều.
HTML_KHOI_MO_DAU_BANG_DIEU = """
<main>
  <style>[type] { display: flex; flex-direction: column; }</style>
  <div class="flex flex-col p-2" type="7:aaaa1111-2222-3333-4444-555566667777">
    <button>Điều khoản được bổ sung</button>
    <span>Điều 23. Điều khoản thi hành</span>
    <div class="prov-clause" id="id_k1">1. Thông tư này có hiệu lực thi hành.</div>
    <div class="prov-clause" id="id_k2">2. Chánh Văn phòng chịu trách nhiệm thi hành.</div>
  </div>
</main>
"""


@pytest.fixture(scope="module")
def chay_js():
    """Trả về hàm: HTML -> danh sách nút phẳng do _JS_PROVISION_NODES bóc ra.

    Chromium chạy trong MỘT THREAD RIÊNG. Playwright sync API từ chối khởi động khi thread
    hiện tại đang có event loop asyncio, mà chạy cả bộ test thì TestClient của FastAPI để lại
    đúng cái loop đó — hậu quả là test này lặng lẽ bị skip dù chạy một mình vẫn pass, tức là
    im lặng đúng lúc cần lên tiếng nhất. Thread sạch thì không dính.
    """
    sync_api = pytest.importorskip("playwright.sync_api")

    def phien(html: str):
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.set_content(html)
                return page.evaluate(_JS_PROVISION_NODES)
            finally:
                browser.close()

    def chay(html: str):
        with ThreadPoolExecutor(max_workers=1) as ex:
            try:
                return ex.submit(phien, html).result()
            except sync_api.Error as exc:  # chưa `playwright install chromium`
                pytest.skip(f"không mở được Chromium: {exc}")

    return chay


def _cap_va_so(nodes):
    return [(n["cls"], n["text"].split(".")[0].split(")")[0]) for n in nodes if not n["hidden"]]


def test_khoan_khong_co_the_van_vao_cay(chay_js):
    """Khoản 1 và 2 chỉ là text thuần trong khối sửa đổi — vẫn phải thành nút prov-clause.

    Đây là ca làm cây Điều 10 TT34/2024 thiếu 2 Khoản: các Điểm a/b/c có thẻ riêng nên vào
    cây bình thường, còn dòng Khoản mở đầu thì rơi mất, để lại hai bộ điểm a/b/c treo thẳng
    dưới Điều với số trùng nhau.
    """
    nodes = chay_js(HTML_TT34_DIEU_10)
    hien = _cap_va_so(nodes)

    assert ("prov-clause", "1") in hien
    assert ("prov-clause", "2") in hien
    assert ("prov-clause", "3") in hien

    tree = build_provision_tree(nodes)
    assert count_provisions(tree) == {"dieu": 1, "khoan": 3, "diem": 5}

    dieu = tree[0]
    assert dieu["cap"] == "dieu" and dieu["so"] == "10"
    khoan = [c for c in dieu["con"] if c["cap"] == "khoan"]
    assert [k["so"] for k in khoan] == ["1", "2", "3"]
    # Điểm phải nằm dưới đúng Khoản của mình, không còn treo thẳng dưới Điều
    assert [c["so"] for c in khoan[0]["con"]] == ["a", "b", "c"]
    assert [c["so"] for c in khoan[1]["con"]] == ["a", "b"]
    assert not [c for c in dieu["con"] if c["cap"] == "diem"]


def test_khoi_da_co_the_cho_khoan_thi_khong_sinh_them(chay_js):
    """Đối chứng: Khoản đã có thẻ prov-clause thì chỉ bù tiêu đề Điều, không nhân đôi Khoản."""
    nodes = chay_js(HTML_KHOI_MO_DAU_BANG_DIEU)
    hien = _cap_va_so(nodes)

    assert hien.count(("prov-article", "Điều 23")) == 1
    assert hien.count(("prov-clause", "1")) == 1
    assert hien.count(("prov-clause", "2")) == 1

    tree = build_provision_tree(nodes)
    assert count_provisions(tree) == {"dieu": 1, "khoan": 2}
