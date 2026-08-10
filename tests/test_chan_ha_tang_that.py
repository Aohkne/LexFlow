"""Ca test cho chính lưới an toàn `tests/conftest.py` — không phải cho code sản xuất.

Nếu ca này đỏ, `_chan_ha_tang_that` trong conftest đã bị gỡ hoặc hỏng — nghĩa là mọi ca
test khác trong repo lại có thể chạm LanceDB Cloud / Neo4j Aura thật mà không ai biết.
"""
from __future__ import annotations

import pytest

from app.core import vectordb
from app.knowledge import graph


def test_vectordb_connect_no_neu_khong_vaga():
    with pytest.raises(RuntimeError, match="LanceDB Cloud thật"):
        vectordb.connect()


def test_graph_session_no_neu_khong_vaga():
    with pytest.raises(RuntimeError, match="Neo4j Aura thật"):
        graph.session()
