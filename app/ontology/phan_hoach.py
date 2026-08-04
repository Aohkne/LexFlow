"""Chứng minh các guard anh em có phủ trọn một miền giá trị hay không.

Vì sao cần: `connector` giữa các tiết thường chỉ là dấu `;` trần ⇒ `unknown`, và B22 cố ý
KHÔNG tự nâng lên `all` (xem `docs/ONTOLOGY-POC.md` §14c). Khi mọi tiết đều mang guard,
câu hỏi bàn giao cho người đổi thành *"các guard này có loại trừ nhau không?"* — nhưng
câu đó **vẫn chưa đủ**. Với mỗi tiết là một yêu cầu có guard:

    AND:  (g₁ → c₁) ∧ (g₂ → c₂)
    OR :  (g₁ ∧ c₁) ∨ (g₂ ∧ c₂)

Loại trừ nhau chỉ làm hai cách đọc trùng nhau ở những tình huống **có** một guard đúng.
Tình huống KHÔNG guard nào đúng thì AND cho ra **true** (miễn trừ hoàn toàn) còn OR cho ra
**false** (không cách nào tuân thủ) — lệch nhau theo hướng nguy hiểm nhất. Nên điều kiện
đúng là **PHÂN HOẠCH**: loại trừ nhau **và** phủ hết.

Máy không suy ra được phân hoạch (`thuoc_tinh`/`gia_tri` là chuỗi tự do). Nhưng nó không
cần suy: đây là sự thật về miền giá trị, người chốt **một lần** kèm trích dẫn, rồi máy
**đối chiếu**. Trả lời một lần cho mỗi thuộc tính thay vì một lần cho mỗi bản ghi — đó mới
là chỗ cách này thắng, chứ không phải ở 2 ca hiện có.

Đo trên 18 fixture trước khi thiết kế, và số liệu bác một giả định ban đầu: khoá bảng
**chỉ** theo miền giá trị thì SAI. `'cá nhân'` xuất hiện với **3** `thuoc_tinh` khác nhau
(`khách hàng`, `tài khoản thanh toán`, `chủ thẻ chính`) — nên miền phải tách ra dùng chung,
nhưng **binding vẫn theo `thuoc_tinh`**: `khách hàng` = {cá nhân, tổ chức} là đủ, còn
`tài khoản thanh toán` thì TT17 Điều 3 khoản 1 liệt kê **ba** hình thức, có cả `chung`.
Khoá thuần theo tập giá trị sẽ chứng minh nhầm ca thứ hai là đã phủ hết.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

_DUONG_DAN = Path("data/phan_hoach.json")
_KHOANG = re.compile(r"\s+")


def chuan_hoa(s: str) -> str:
    """So khớp phải bỏ qua hoa/thường và khoảng trắng thừa — nhưng KHÔNG dò mờ.

    Dò mờ ở đây là mở lại đúng cánh cửa mà cả thiết kế này đóng: một giá trị gần giống
    được nhận thành phủ hết thì máy tự chứng minh cho mình một điều luật không nói.
    """
    return _KHOANG.sub(" ", s.strip()).casefold()


class ChungMinh(BaseModel):
    """Kết quả đối chiếu một nhóm guard anh em với bảng phân hoạch."""

    mien: str
    can_cu: str
    trich: str
    #: True ⇒ các guard phủ trọn miền ⇒ `connector` không còn ảnh hưởng kết quả.
    du: bool
    #: Giá trị của miền mà nhóm guard KHÔNG nói tới. Đây là phần khiến AND ≠ OR.
    thieu: list[str] = []
    #: Giá trị guard nêu mà miền không có ⇒ bảng và luật lệch nhau, không kết luận.
    la: list[str] = []
    #: Hai guard anh em trùng giá trị ⇒ chồng lấn, không thể là phân hoạch.
    trung_lap: bool = False


@lru_cache(maxsize=1)
def _bang(duong_dan: str = str(_DUONG_DAN)) -> tuple[dict, dict]:
    p = Path(duong_dan)
    if not p.exists():
        return {}, {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    mien = {k: [chuan_hoa(x) for x in v] for k, v in raw.get("mien", {}).items()}
    tt = {chuan_hoa(t["ten"]): t for t in raw.get("thuoc_tinh", [])}
    return mien, tt


def chung_minh(thuoc_tinh: str, gia_tri: list[str]) -> ChungMinh | None:
    """Nhóm guard anh em → kết quả đối chiếu, hoặc `None` nếu thuộc tính chưa khai.

    `None` khác hẳn `du=False`: chưa khai nghĩa là **chưa ai trả lời**, còn `du=False`
    nghĩa là **đã trả lời và câu trả lời là chưa phủ hết**. Gộp hai cái làm một sẽ giấu
    mất chuyện bảng còn thiếu.
    """
    mien_map, tt_map = _bang()
    binding = tt_map.get(chuan_hoa(thuoc_tinh))
    if binding is None:
        return None
    ten_mien = binding["mien"]
    tap = mien_map.get(ten_mien)
    if tap is None:
        return None

    co = [chuan_hoa(g) for g in gia_tri]
    kq = ChungMinh(
        mien=ten_mien,
        can_cu=binding.get("can_cu", ""),
        trich=binding.get("trich", ""),
        du=False,
        thieu=[v for v in tap if v not in co],
        la=sorted({v for v in co if v not in tap}),
        trung_lap=len(set(co)) != len(co),
    )
    # Phủ hết CHỈ khi: luật nói miền là đóng, không guard nào lạ, không guard nào trùng
    # nhau, và không giá trị nào của miền bị bỏ sót. Thiếu một điều kiện là không kết luận.
    kq.du = bool(
        binding.get("phu_het")
        and not kq.la
        and not kq.trung_lap
        and not kq.thieu
    )
    return kq
