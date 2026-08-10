"""Chấm bộ phát hiện mâu thuẫn ở tầng **cặp điều khoản**, nơi nó thật sự làm việc.

Vì sao không dùng `expect_conflict` của `eval/questions.jsonl`: nhãn đó gắn cho **câu hỏi**,
còn `detect_conflicts` chạy trên **tập chunk lấy về**. Hai thứ lệch nhau, và lệch theo hướng
gây hiểu nhầm — đo 10/08: câu *"Tổng hạn mức rút tiền mặt của thẻ tín dụng…"* không gắn
`expect_conflict` nhưng truy hồi lấy về cả `TT18-2024::Điều 13` lẫn `SHB-QD-THE-2023::Mục 5.2`,
nên báo mâu thuẫn ở đó là **đúng**, không phải dương tính giả.

Nhãn ở đây gắn vào **cặp**, nên không mục khi retrieval đổi:

* `mau_thuan_vang.jsonl` liệt kê các cặp mâu thuẫn có thật trong corpus;
* với mỗi lượt, **kỳ vọng** = những cặp có ĐỦ HAI PHÍA trong tập chunk lấy về;
* precision/recall tính trên tập kỳ vọng đó.

Giới hạn phải nói rõ: bộ vàng là các mâu thuẫn **cài có chủ đích** (xác minh tay 10/08 trên
`data/corpus.real.json` — đủ cả hai phía, số liệu khớp). Một mâu thuẫn có thật nhưng KHÔNG cài
chủ đích sẽ bị chấm thành dương tính giả. Corpus là bản mô phỏng nên rủi ro đó thấp, nhưng nó
tồn tại và số đo phải đọc kèm điều này.

Thuần hàm — không mạng, không LLM, kiểm được bằng unit test.
"""
from __future__ import annotations

import json
from pathlib import Path

VANG = Path("eval/mau_thuan_vang.jsonl")


def doc_vang(duong_dan: Path = VANG) -> list[dict]:
    return [
        json.loads(x) for x in duong_dan.read_text(encoding="utf-8").splitlines() if x.strip()
    ]


def khop_dia_chi(cu_the: str, tong_quat: str) -> bool:
    """`cu_the` có nằm dưới `tong_quat` không — ranh giới là DẤU CÁCH.

    Bộ phát hiện thường trích chi tiết hơn nhãn vàng (`"…::Điều 13 Khoản 4"` cho nhãn
    `"…::Điều 13"`), nên so bằng `==` sẽ trượt. Ranh giới dấu cách để `"Điều 1"` không nuốt
    `"Điều 13"` — cùng luật với `retrieval.lay_chunk_theo_tien_to`.
    """
    return cu_the == tong_quat or cu_the.startswith(tong_quat + " ")


def cap_ky_vong(vang: list[dict], id_chunk: list[str]) -> list[dict]:
    """Cặp vàng có ĐỦ HAI PHÍA trong tập chunk này — tức là cặp lượt chạy PHẢI bắt được."""
    return [
        c for c in vang
        if any(khop_dia_chi(i, c["noi_bo"]) for i in id_chunk)
        and any(khop_dia_chi(i, c["luat"]) for i in id_chunk)
    ]


def khop_cap(bao: tuple[str, str], cap_vang: dict) -> bool:
    a, b = bao
    return (khop_dia_chi(a, cap_vang["noi_bo"]) and khop_dia_chi(b, cap_vang["luat"])) or (
        khop_dia_chi(b, cap_vang["noi_bo"]) and khop_dia_chi(a, cap_vang["luat"])
    )


def cham(vang: list[dict], id_chunk: list[str], bao: list[tuple[str, str]]) -> dict:
    """Chấm MỘT lượt. `bao` = các cặp địa chỉ `"{doc_id}::{article}"` bộ phát hiện trả về."""
    ky_vong = cap_ky_vong(vang, id_chunk)
    bat_duoc = [c for c in ky_vong if any(khop_cap(b, c) for b in bao)]
    # Cảnh báo không khớp cặp vàng NÀO (không chỉ cặp kỳ vọng) mới tính là dương tính giả:
    # một cặp vàng thiếu một phía trong chunk thì bộ phát hiện không đủ dữ kiện để báo, nhưng
    # nếu nó vẫn báo đúng cặp ấy thì đó không phải lỗi.
    gia = [b for b in bao if not any(khop_cap(b, c) for c in vang)]
    return {
        "ky_vong": len(ky_vong),
        "bat_duoc": len(bat_duoc),
        "bao": len(bao),
        "duong_tinh_gia": len(gia),
        "cap_bo_sot": [c["mo_ta"] for c in ky_vong if c not in bat_duoc],
        "cap_bao_thua": gia,
    }


def gop(cac_luot: list[dict]) -> dict:
    """Cộng dồn nhiều lượt → precision / recall trên toàn bộ."""
    ky_vong = sum(x["ky_vong"] for x in cac_luot)
    bat_duoc = sum(x["bat_duoc"] for x in cac_luot)
    bao = sum(x["bao"] for x in cac_luot)
    gia = sum(x["duong_tinh_gia"] for x in cac_luot)
    return {
        "ky_vong": ky_vong,
        "bat_duoc": bat_duoc,
        "bao": bao,
        "duong_tinh_gia": gia,
        "recall": round(bat_duoc / ky_vong, 3) if ky_vong else None,
        "precision": round((bao - gia) / bao, 3) if bao else None,
    }
