"""Đẩy lớp phủ lên Neo4j: MERGE nên chạy hai lần không nhân đôi."""
from unittest.mock import MagicMock, patch

from app.knowledge.graph import push_overlay

from tests.test_lop_phu import _goi


def test_merge_node_va_canh():
    phien = MagicMock()
    with patch("app.knowledge.graph.session") as mo:
        mo.return_value.__enter__.return_value = phien
        n_node, n_canh = push_overlay(_goi())

    # `_goi()` (tests/test_lop_phu.py) dựng 3 cạnh với 6 khoá KHÔNG trùng nhau (3 nguồn +
    # 3 đích, không giao nhau) ⇒ 6 nút overlay, 3 cạnh TAC_DONG.
    assert (n_node, n_canh) == (6, 3)
    cypher = " ".join(str(c) for c in phien.run.call_args_list)
    assert "MERGE" in cypher and "CREATE (" not in cypher  # không CREATE trần → không nhân đôi
    assert ":DonVi" in cypher and ":TAC_DONG" in cypher


def test_gop_lo_khong_mot_luot_moi_hang():
    """Số lượt gọi Neo4j phải là HẰNG SỐ, không tỉ lệ với số nút.

    Bản một-lượt-mỗi-hàng chạy ~764 round-trip trong một session và Aura free rớt kết nối
    giữa chừng (gặp thật 10/08: `SessionExpired` sau khi dựng lại 221/255 cạnh `THUOC`, đồ thị
    nằm lại nửa vời). Ca này canh đúng cái tính chất khiến chuyện đó không lặp lại.
    """
    phien = MagicMock()
    with patch("app.knowledge.graph.session") as mo:
        mo.return_value.__enter__.return_value = phien
        push_overlay(_goi())

    # 2 lượt `CREATE CONSTRAINT` của `ensure_constraints` + 3 lượt gộp lô.
    assert phien.run.call_count <= 6, (
        f"{phien.run.call_count} lượt cho 6 nút — đang gọi theo từng hàng, "
        "lớp phủ thật có 293 nút thì đứt kết nối"
    )
    ghi = [str(c) for c in phien.run.call_args_list if "MERGE" in str(c)]
    assert ghi and all("UNWIND" in c for c in ghi), "câu MERGE nào cũng phải đi theo lô"


def test_ensure_constraints_phu_ca_DonVi_khoa():
    """Fix wave 06/08, IMPORTANT 5: `push_overlay` gọi `ensure_constraints()`, đọc như đã có
    ràng buộc — nhưng nó chỉ tạo ràng buộc trên `Document.doc_id`, nên MỌI
    `MERGE (d:DonVi {khoa: …})` là một label scan (~470 lượt mỗi lần đẩy)."""
    from app.knowledge.graph import ensure_constraints

    phien = MagicMock()
    with patch("app.knowledge.graph.session") as mo:
        mo.return_value.__enter__.return_value = phien
        ensure_constraints()

    cypher = " ".join(str(c) for c in phien.run.call_args_list)
    assert "(d:Document) REQUIRE d.doc_id IS UNIQUE" in cypher
    assert "(d:DonVi) REQUIRE d.khoa IS UNIQUE" in cypher
