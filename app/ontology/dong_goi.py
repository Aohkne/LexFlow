"""Đóng gói lớp phủ thành artefact TỰ CHỨA cho runtime.

Vì sao phải đóng gói thay vì để runtime tự giải: `loi_van_moi` là span vào `noi_dung` của
văn bản sửa, mà `noi_dung` chỉ nằm ở `data/raw/vbpl/raw/` — thư mục **gitignored**. Một
checkout sạch hay một image Cloud Run không có gì để giải. Nên giải một lần ở đây, ghi chữ
đã giải vào artefact tracked, và runtime không bao giờ chạm `raw/`.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.ingestion.vbpl_corpus import duong_dan_toan_van, file_da_chuyen_khuon
from app.ontology.tac_dong import CanhTacDong, doc_tac_dong


class CanhGoi(BaseModel):
    """Cạnh tác động + chữ đã giải sẵn, đủ để runtime làm việc mà không cần `raw/`."""

    nguon: str
    dich: str
    thao_tac: str
    valid_from: str | None = None
    loi_van_moi: tuple[int, int] | None = None
    #: Lát cắt NGUYÊN VĂN `noi_dung[char_start:char_end]` — không strip, không chuẩn hoá.
    loi_van_moi_text: str | None = None
    #: Điều của văn bản SỬA chứa khối lời văn mới (cấp ĐIỀU, vì `articles[]` chỉ tới điều).
    xuat_xu_doc_id: str | None = None
    xuat_xu_article: str | None = None
    menh_lenh: str

    def thanh_canh(self) -> CanhTacDong:
        """Quay về `CanhTacDong` để dùng lại nguyên luật của `hien_hanh`/`dinh_tuyen`."""
        return CanhTacDong(
            nguon=self.nguon,
            dich=self.dich,
            thao_tac=self.thao_tac,
            loi_van_moi=self.loi_van_moi,
            valid_from=self.valid_from,
            menh_lenh=self.menh_lenh,
        )


class GoiLopPhu(BaseModel):
    sinh_luc: str
    #: `doc_id` → `so_hieu`, đúng chiều `dinh_tuyen.khoa_tu_chunk_id` cần.
    so_hieu_theo_doc: dict[str, str]
    canh: list[CanhGoi]


def _dieu_chua_span(articles: list[dict], span: tuple[int, int]) -> str | None:
    a0, b0 = span
    for a in articles:
        cs, ce = a.get("char_start"), a.get("char_end")
        if isinstance(cs, int) and isinstance(ce, int) and cs <= a0 and b0 <= ce:
            return a.get("article")
    return None


def boi_dap(
    canh: list[CanhTacDong],
    ban_do: dict[str, tuple[str, list[dict]]],
    doc_id_theo_so_hieu: dict[str, str],
) -> tuple[list[CanhGoi], list[str]]:
    """Cạnh → cạnh-đã-bồi-đắp + cảnh báo. Hàm THUẦN (không I/O) để test được không cần `raw/`."""
    ra: list[CanhGoi] = []
    canh_bao: list[str] = []
    for c in canh:
        text: str | None = None
        xx_doc: str | None = None
        xx_art: str | None = None
        if c.loi_van_moi is not None:
            sh = c.nguon.split("#", 1)[0]
            muc = ban_do.get(sh)
            if muc is None:
                canh_bao.append(
                    f"{sh}: thiếu toàn văn để giải span {c.loi_van_moi} — bỏ lời văn mới"
                )
            else:
                noi_dung, articles = muc
                a0, b0 = c.loi_van_moi
                if 0 <= a0 < b0 <= len(noi_dung):
                    text = noi_dung[a0:b0]
                    xx_art = _dieu_chua_span(articles, c.loi_van_moi)
                    xx_doc = doc_id_theo_so_hieu.get(sh)
                else:
                    canh_bao.append(
                        f"{sh}: span {c.loi_van_moi} ngoài phạm vi noi_dung "
                        f"({len(noi_dung)} ký tự) — bỏ lời văn mới"
                    )
        ra.append(
            CanhGoi(
                nguon=c.nguon,
                dich=c.dich,
                thao_tac=c.thao_tac,
                valid_from=c.valid_from,
                loi_van_moi=c.loi_van_moi,
                loi_van_moi_text=text,
                xuat_xu_doc_id=xx_doc,
                xuat_xu_article=xx_art,
                menh_lenh=c.menh_lenh,
            )
        )
    return ra, canh_bao


def _ban_do_toan_van(thu_muc: Path) -> tuple[dict[str, tuple[str, list[dict]]], list[str]]:
    """`so_hieu` → (`noi_dung` thô, `articles` có char_start/char_end). Chỉ dùng lúc build.

    Trả kèm CẢNH BÁO cho từng file đọc không được. Trước đây chỗ này `continue` trong im lặng
    — đó chính là cơ chế làm cho "đóng gói ra 0 cạnh" trở nên vô hình: nguồn hỏng hay nguồn
    thiếu đều cho ra cùng một kết quả trống, không dòng nào nói vì sao.
    """
    ra: dict[str, tuple[str, list[dict]]] = {}
    canh_bao: list[str] = []
    for p in file_da_chuyen_khuon(thu_muc):
        try:
            corpus = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            canh_bao.append(f"{p.name}: không đọc được file đã chuyển khuôn ({e}) — bỏ qua")
            continue
        so_hieu = corpus.get("so_hieu")
        p_tho = duong_dan_toan_van(p)
        if not so_hieu or not p_tho.exists():
            continue
        try:
            tho = json.loads(p_tho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            canh_bao.append(f"{p_tho.name}: không đọc được bản ghi thô ({e}) — bỏ toàn văn")
            continue
        ra[so_hieu] = (tho.get("noi_dung") or "", corpus.get("articles") or [])
    return ra, canh_bao


def dong_goi(thu_muc: Path, corpus_path: Path, ngay: str) -> tuple[GoiLopPhu, list[str]]:
    canh, canh_bao = doc_tac_dong(thu_muc)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    so_hieu_theo_doc = {
        d["doc_id"]: d["so_hieu"]
        for d in corpus.get("documents", [])
        if d.get("doc_id") and d.get("so_hieu")
    }
    doc_id_theo_so_hieu = {v: k for k, v in so_hieu_theo_doc.items()}
    ban_do, cb_ban_do = _ban_do_toan_van(thu_muc)
    boi, cb = boi_dap(canh, ban_do, doc_id_theo_so_hieu)
    return (
        GoiLopPhu(sinh_luc=ngay, so_hieu_theo_doc=so_hieu_theo_doc, canh=boi),
        canh_bao + cb_ban_do + cb,
    )


#: Nơi artefact runtime nằm. Là hằng module (không chuỗi rời trong `main`) để test chĩa được
#: sang `tmp_path` mà không phải chạy `main()` trên cây làm việc thật.
DUONG_DAN_ARTEFACT = Path("data/overlay/lop_phu.json")

#: Ngưỡng co ngót cho phép giữa hai lần đóng gói. Số cạnh là kết quả của một lần crawl ĐẦY ĐỦ;
#: mất hơn 10% nghĩa là nguồn thiếu chứ không phải luật đổi. Ngưỡng thấp hơn thì một checkout
#: chỉ crawl được nửa corpus vẫn lọt qua và ghi đè artefact tốt.
_NGUONG_CO_NGOT = 0.9


def _so_canh_da_co(dich: Path) -> int | None:
    """Số cạnh của artefact đang nằm ở `dich`. Không có / không đọc được ⇒ None."""
    try:
        cu = json.loads(dich.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    canh = cu.get("canh") if isinstance(cu, dict) else None
    return len(canh) if isinstance(canh, list) else None


def ly_do_tu_choi_ghi(so_canh_moi: int, dich: Path) -> str | None:
    """Vì sao KHÔNG được ghi đè artefact — `None` nghĩa là ghi được.

    `main()` từng ghi vô điều kiện. Trên một checkout sạch `data/raw/vbpl/raw/` không tồn tại
    (gitignored) nên `doc_tac_dong` bỏ qua mọi văn bản và lần chạy đó ghi đè artefact 178 cạnh
    bằng `canh: []`: nó in `cạnh: 0` rồi đi tiếp, không gì chặn. Artefact là dữ liệu tracked mà
    runtime SỐNG BẰNG — mất nó là cả lớp phủ tắt lặng lẽ trên sản phẩm.
    """
    if so_canh_moi == 0:
        return (
            "đóng gói ra 0 cạnh — KHÔNG ghi đè artefact. Nguyên nhân thường gặp: thiếu "
            "`data/raw/vbpl/raw/` (gitignored, không có trên checkout sạch hay CI) nên "
            "`doc_tac_dong` bỏ qua mọi văn bản."
        )
    cu = _so_canh_da_co(dich)
    if cu and so_canh_moi < cu * _NGUONG_CO_NGOT:
        return (
            f"đóng gói ra {so_canh_moi} cạnh trong khi artefact đang có {cu} — co quá "
            f"{1 - _NGUONG_CO_NGOT:.0%}, KHÔNG ghi đè. Kiểm `data/raw/vbpl/raw/` đã đủ văn "
            f"bản chưa; nếu số giảm là ĐÚNG thì xoá tay artefact cũ rồi chạy lại."
        )
    return None


def main() -> None:
    import datetime

    goi, canh_bao = dong_goi(
        Path("data/raw/vbpl"),
        Path("data/corpus.real.json"),
        datetime.date.today().isoformat(),
    )
    dich = DUONG_DAN_ARTEFACT

    ly_do = ly_do_tu_choi_ghi(len(goi.canh), dich)
    if ly_do is not None:
        for c in canh_bao[:10]:
            print(f"cảnh báo: {c}")
        raise SystemExit(f"[dong_goi] {ly_do}")

    dich.parent.mkdir(parents=True, exist_ok=True)
    dich.write_text(goi.model_dump_json(indent=1), encoding="utf-8")

    co_span = sum(1 for c in goi.canh if c.loi_van_moi is not None)
    giai_duoc = sum(1 for c in goi.canh if c.loi_van_moi_text is not None)
    print(f"cạnh:            {len(goi.canh)}")
    print(f"có lời văn mới:  {co_span}")
    print(f"giải được chữ:   {giai_duoc}")
    print(f"cảnh báo:        {len(canh_bao)}")
    print(f"ghi -> {dich} ({dich.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
