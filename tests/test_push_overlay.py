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
