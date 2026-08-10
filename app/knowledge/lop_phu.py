"""Cổng DUY NHẤT giữa sản phẩm và lớp phủ dưới-văn-bản.

`answer.py`/`review.py`/`api` không gọi thẳng `dinh_tuyen`/`phien_ban_hien_hanh`: đường nóng
cần đúng một chỗ để đọc, để tắt bằng cờ, và để hỏng một cách vô hại. Mọi lỗi ở đây (artefact
thiếu, JSON hỏng, văn bản lạ) đều trả `None` — lớp phủ làm câu trả lời ĐÚNG HƠN, nó không
phải điều kiện để có câu trả lời.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from app.core.config import settings
from app.ontology.dinh_tuyen import dinh_tuyen, khoa_tu_chunk_id
from app.ontology.dong_goi import CanhGoi, GoiLopPhu
from app.ontology.hien_hanh import phien_ban_hien_hanh
from app.ontology.tac_dong import CanhTacDong
from app.ontology.tac_dong import _DICH_RE as _KHOA_RE  # cùng cách dinh_tuyen.py đã mượn

if TYPE_CHECKING:
    from app.core.schemas import TacDongDonVi

DUONG_DAN_MAC_DINH = "data/overlay/lop_phu.json"

#: Sentinel phân biệt "người gọi KHÔNG truyền `lp`" (⇒ tự tải artefact mặc định) với "người
#: gọi ĐÃ truyền `lp=None`" (⇒ chính họ vừa thử tải và hỏng — trả `None` ngay, không âm thầm
#: cứu bằng cách tải lại artefact mặc định). Không sentinel thì hai trường hợp trộn lẫn: một
#: test dùng `tai_lop_phu(duong_dan_hong)` (= None) rồi truyền thẳng vào `chu_thich_chunk` sẽ
#: vô tình được "cứu" bằng artefact thật nếu `doc_id` trong chunk trùng tên với văn bản thật
#: (ca thật: `"TT40-2024"` của fixture test trùng đúng `doc_id` thật trong
#: `data/overlay/lop_phu.json`) — vi phạm fail-open mà test đòi hỏi.
_CHUA_TRUYEN = object()


class ChuThichHieuLuc(BaseModel):
    """Đơn vị luật của một chunk, đọc tại `as_of`, thì sao."""

    nhanh: str
    trang_thai: Literal["nguyen_ven", "da_sua", "bi_bai_bo", "la_loi_sua"]
    trich_dan_dung_chu: str
    khoa_goc: str
    khoa_dich: str | None = None
    sua_boi_doc_id: str | None = None
    sua_boi_article: str | None = None
    #: Lời văn mới NGUYÊN VĂN — chỉ điền khi sửa đổi thay TRỌN đơn vị của chunk.
    ban_hien_hanh: str | None = None
    xuat_xu_doc_id: str | None = None
    xuat_xu_article: str | None = None


@dataclass
class LopPhuRuntime:
    canh: list[CanhTacDong]
    goi_theo_canh: dict[tuple, CanhGoi]
    so_hieu_theo_doc: dict[str, str]
    #: Chiều ngược, dựng sẵn một lần. `doc_id` là thứ corpus TỰ ĐẶT, không suy ra được từ số
    #: hiệu — đo 09/08 trên artefact thật: 4/26 văn bản (toàn bộ nhóm nội bộ SHB) có `doc_id`
    #: khác hẳn thứ quy ước `<loại><số>-<năm>` sinh ra. Nên chỗ nào cần `doc_id` thật thì phải
    #: hỏi bảng này, không được suy.
    doc_id_theo_so_hieu: dict[str, str]
    #: Ngày artefact được sinh — để `/health` nói được đang phục vụ bản lớp phủ nào.
    sinh_luc: str


def _khoa_canh(c: CanhTacDong | CanhGoi) -> tuple:
    return (c.nguon, c.dich, c.thao_tac, c.valid_from, c.loi_van_moi)


@lru_cache(maxsize=4)
def tai_lop_phu(duong_dan: str | None = None) -> LopPhuRuntime | None:
    """Nạp artefact một lần. Hỏng/thiếu ⇒ None (fail-open), không ném lỗi.

    Đường dẫn mặc định giải bên TRONG chứ không đặt ở chữ ký: đặt ở chữ ký thì mọi lượt gọi
    không tham số và mọi lượt gọi truyền đúng đường dẫn đó thành hai khoá cache khác nhau —
    artefact bị parse và giữ hai bản. Giải bên trong cũng là thứ cho test đổi
    `DUONG_DAN_MAC_DINH` mà không phải sửa nơi gọi.
    """
    try:
        duong_dan = duong_dan or DUONG_DAN_MAC_DINH
        goi = GoiLopPhu.model_validate_json(Path(duong_dan).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    # Chuyển MỘT LẦN rồi dùng lại đúng danh sách đó: `dinh_tuyen` kiểm `c in pb.cac_lan`
    # bằng so sánh giá trị pydantic — chuyển lại lần hai vẫn đúng, nhưng chuyển mỗi lượt hỏi
    # là phí và dễ lệch nếu sau này thêm trường không so được.
    canh = [c.thanh_canh() for c in goi.canh]
    return LopPhuRuntime(
        canh=canh,
        goi_theo_canh={_khoa_canh(c): c for c in goi.canh},
        so_hieu_theo_doc=goi.so_hieu_theo_doc,
        doc_id_theo_so_hieu={sh: d for d, sh in goi.so_hieu_theo_doc.items()},
        sinh_luc=goi.sinh_luc,
    )


def tinh_trang() -> dict:
    """Lớp phủ hiện đang ở tình trạng nào — cho `/health` và log lúc khởi động.

    Tồn tại vì fail-open không có tiếng nói: artefact thiếu trong image thì badge hiệu lực
    biến mất khỏi toàn sản phẩm và không có chỗ nào nói ra. Đây là chỗ nói ra.

    Dùng lại `tai_lop_phu()` (đã `lru_cache`) nên không thêm lượt đọc đĩa nào; gọi lúc khởi
    động thì lượt chat đầu tiên khỏi trả giá parse.
    """
    if not settings.overlay_router:
        return {"bat": False}
    lp = tai_lop_phu()
    if lp is None:
        return {"bat": True, "nap": False, "duong_dan": DUONG_DAN_MAC_DINH}
    return {
        "bat": True,
        "nap": True,
        "so_canh": len(lp.canh),
        "sinh_luc": lp.sinh_luc,
        "duong_dan": DUONG_DAN_MAC_DINH,
    }


def tach_khoa(khoa: str, lp: LopPhuRuntime) -> tuple[str | None, str | None]:
    """Khoá overlay → (`doc_id`, nhãn kiểu `"Điều 1 Khoản 2"`). Không giải được ⇒ (None, None).

    `doc_id` tra từ bảng của artefact, **không suy theo quy ước đặt tên**. Số hiệu không có
    trong bảng nghĩa là văn bản nằm ngoài corpus (vd `135/2015/NĐ-CP`, đích của 39/177 cạnh) —
    khi đó không có `doc_id` nào đúng, nên trả `None` chứ không sinh ra một mã trông như thật:
    phía web dựng link `/docs/{id}` từ giá trị này, và một mã bịa dẫn thẳng tới trang trống.
    Nhãn vẫn giải được nên vẫn trả — mất `doc_id` không có nghĩa là mất địa chỉ.
    """
    m = _KHOA_RE.match(khoa)
    if not m:
        return None, None
    nhan = f"Điều {m.group('dieu')}"
    if m.group("khoan"):
        nhan += f" Khoản {m.group('khoan')}"
    if m.group("diem"):
        nhan += f" Điểm {m.group('diem')}"
    return lp.doc_id_theo_so_hieu.get(m.group("sh")), nhan


def _span_loi_van(chunk: dict, lp: LopPhuRuntime) -> tuple[int, int] | None:
    """Chunk này CÓ PHẢI là khối lời văn mới của một cạnh không — so bằng CHỮ.

    `dinh_tuyen` nhận `span_chunk` (toạ độ trong `noi_dung`), nhưng hàng LanceDB không mang
    toạ độ ký tự, và thêm toạ độ vào chunk nghĩa là đổi ingest + re-embed toàn bộ. Chữ đã đủ:
    nếu lời văn mới nằm trong chunk (hoặc ngược lại, khi chunk bị chẻ nhỏ hơn khối trích) thì
    chunk chính là khối đó. Trả span CỦA CHÍNH CẠNH ĐÓ để `dinh_tuyen` tự giao và giữ trọn
    luật trích dẫn (cổng cạnh-chết) bên trong nó.
    """
    doc_id = (chunk.get("id") or "").partition("::")[0]
    so_hieu = lp.so_hieu_theo_doc.get(doc_id)
    text = chunk.get("text") or ""
    if so_hieu is None or not text:
        return None
    for c in lp.canh:
        if c.loi_van_moi is None or c.nguon.split("#", 1)[0] != so_hieu:
            continue
        g = lp.goi_theo_canh.get(_khoa_canh(c))
        lv = g.loi_van_moi_text if g else None
        if lv and (lv in text or text in lv):
            return c.loi_van_moi
    return None


def tac_dong_cua_van_ban(
    doc_id: str, as_of: str, lp: LopPhuRuntime | None = _CHUA_TRUYEN  # type: ignore[assignment]
) -> list["TacDongDonVi"]:
    """Mọi đơn vị của `doc_id` đang bị chạm tại `as_of` — cho trình xem toàn văn.

    Đi từ ĐÍCH của cạnh (đơn vị bị tác động) chứ không quét từng điều của văn bản: lớp phủ
    thưa, chỉ đơn vị "có chuyện để nói" mới có mặt, nên duyệt cạnh là đủ và rẻ.
    """
    from app.core.schemas import TacDongDonVi

    if lp is _CHUA_TRUYEN:
        lp = tai_lop_phu()
    if lp is None:
        return []
    ra: list[TacDongDonVi] = []
    for khoa in sorted({c.dich for c in lp.canh}):
        d_id, _nhan = tach_khoa(khoa, lp)
        if d_id != doc_id:
            continue
        pb = phien_ban_hien_hanh(khoa, lp.canh, as_of)
        if pb.trang_thai == "nguyen_ven":
            continue
        m = _KHOA_RE.match(khoa)
        if m is None:
            continue
        c = pb.cac_lan[-1]
        boi_doc, boi_art = tach_khoa(c.nguon, lp)
        # Chữ đã được `dong_goi` giải sẵn vào gói; đọc kèm ở đây để trình xem dựng được bảng
        # đối chiếu ngay, khỏi phải mở `raw/` (thứ API không phục vụ) hay hỏi thêm một lượt.
        g = lp.goi_theo_canh.get(_khoa_canh(c))
        ra.append(
            TacDongDonVi(
                article=f"Điều {m.group('dieu')}",
                khoan=m.group("khoan"),
                diem=m.group("diem"),
                trang_thai=pb.trang_thai,
                boi_doc_id=boi_doc,
                boi_article=boi_art,
                tu_ngay=c.valid_from,
                thao_tac=c.thao_tac,
                menh_lenh=g.menh_lenh if g else None,
                loi_van_moi=g.loi_van_moi_text if g else None,
            )
        )
    return ra


def chu_thich_chunk(
    chunk: dict, as_of: str, lp: LopPhuRuntime | None = _CHUA_TRUYEN  # type: ignore[assignment]
) -> ChuThichHieuLuc | None:
    if lp is _CHUA_TRUYEN:
        lp = tai_lop_phu()
    if lp is None:
        return None
    chunk_id = chunk.get("id") or ""
    if khoa_tu_chunk_id(chunk_id, lp.so_hieu_theo_doc) is None:
        return None
    kq = dinh_tuyen(chunk_id, _span_loi_van(chunk, lp), lp.canh, lp.so_hieu_theo_doc, as_of)
    if kq is None:
        return None

    if kq.nhanh == "trich_trong_van_ban_sua":
        trang_thai: Literal["nguyen_ven", "da_sua", "bi_bai_bo", "la_loi_sua"] = "la_loi_sua"
    elif kq.nhanh == "nguyen_ven":
        trang_thai = "nguyen_ven"
    else:
        # Nhánh 2 có hai đường: rộng-hơn-hoặc-bằng (đọc được trạng thái thẳng từ
        # `phien_ban_hien_hanh`) và sâu-hơn (cạnh sửa một điểm BÊN TRONG khoản — khoản chưa bị
        # bãi bỏ, nên trạng thái là `da_sua` dù cạnh đó là `bai_bo` cấp điểm).
        pb = phien_ban_hien_hanh(kq.khoa_goc, lp.canh, as_of)
        trang_thai = pb.trang_thai if pb.trang_thai != "nguyen_ven" else "da_sua"

    sua_boi_doc = sua_boi_art = ban_hien_hanh = xx_doc = xx_art = None
    if kq.canh is not None:
        sua_boi_doc, sua_boi_art = tach_khoa(kq.canh.nguon, lp)
        g = lp.goi_theo_canh.get(_khoa_canh(kq.canh))
        if g is not None:
            xx_doc, xx_art = g.xuat_xu_doc_id, g.xuat_xu_article
            # Chỉ khi sửa đổi thay TRỌN đơn vị của chunk mới được coi lời văn mới là "bản hiện
            # hành" của nó. Cạnh sâu hơn (sửa một điểm bên trong) hay `bo_sung`/`thay_cum_tu`
            # thì lời văn mới KHÔNG phải toàn bộ đơn vị — dán vào là bịa.
            if (
                kq.nhanh == "nen_da_sua"
                and kq.canh.thao_tac == "sua_doi"
                and kq.canh.dich == kq.khoa_goc
            ):
                ban_hien_hanh = g.loi_van_moi_text

    return ChuThichHieuLuc(
        nhanh=kq.nhanh,
        trang_thai=trang_thai,
        trich_dan_dung_chu=kq.trich_dan_dung_chu,
        khoa_goc=kq.khoa_goc,
        khoa_dich=kq.khoa_dich,
        sua_boi_doc_id=sua_boi_doc,
        sua_boi_article=sua_boi_art,
        ban_hien_hanh=ban_hien_hanh,
        xuat_xu_doc_id=xx_doc,
        xuat_xu_article=xx_art,
    )


def chu_thich_ket_qua(
    chunks: list[dict],
    as_of: str,
    lp=_CHUA_TRUYEN,  # type: ignore[assignment]
    *,
    pham_vi: set[str] | None = None,
) -> tuple[list[dict], dict[str, ChuThichHieuLuc]]:
    """Chú thích cả mẻ hit: loại cái đã bị bãi bỏ, kéo thêm lời văn mới khi cần.

    Trả `(danh sách dùng để trả lời, map id → chú thích)`. Map giữ CẢ hit đã bị loại — tầng
    trên vẫn cần chữ để nói "điều này đã bị bãi bỏ".

    `pham_vi` là tập `doc_id` mà NGƯỜI GỌI cho phép (chat: `req.doc_ids`; review:
    `against_ids`). Đặt thì chunk kéo thêm không bao giờ ra ngoài tập đó — người dùng đã chủ
    động loại một văn bản ra thì lớp phủ không được lén đưa nó trở lại vào trích dẫn, còn
    `/reviews` thì `legal_doc_id` không được rơi ra ngoài phạm vi đối chiếu. `None` = không
    giới hạn (đường chat mở).
    """
    if lp is _CHUA_TRUYEN:
        lp = tai_lop_phu()
    if lp is None:
        return chunks, {}

    ct: dict[str, ChuThichHieuLuc] = {}
    for c in chunks:
        t = chu_thich_chunk(c, as_of, lp)
        cid = c.get("id")
        # Nhất quán với `chu_thich_chunk` (`chunk.get("id") or ""`): id thiếu/rỗng thì không
        # có gì để làm khoá — coi như không có chú thích, không bịa khoá rác vào `ct`.
        if t is not None and cid:
            ct[cid] = t

    con = [
        c for c in chunks
        if (t := ct.get(c.get("id"))) is None or t.trang_thai != "bi_bai_bo"
    ]
    if not con:
        # Loại hết: người hỏi đang hỏi đúng một điều đã bị bãi bỏ. Trả lại kèm nhãn còn thật
        # hơn là "chưa tìm thấy quy định phù hợp".
        con = list(chunks)

    # Kéo lời văn mới về cho hit đã sửa mà KHÔNG có sẵn bản hiện hành (bổ sung, thay cụm từ…).
    #
    # Hỏi bằng TIỀN TỐ `"{doc_id}::Điều N"`, không phải id chính xác (fix wave 06/08,
    # IMPORTANT 2): lớp phủ chỉ biết địa chỉ tới cấp ĐIỀU, còn `pipeline._split_khoan` chẻ mọi
    # điều dài hơn `_MAX_CHUNK` thành `"Điều N Khoản a-b"` — id cấp điều KHÔNG tồn tại ở 31/40
    # ca cần đường này, và fail-open nuốt mất. Xem `retrieval.lay_chunk_theo_tien_to`.
    co_san = {c.get("id") for c in con if c.get("id")}
    can_them = sorted(
        {
            f"{t.xuat_xu_doc_id}::{t.xuat_xu_article}"
            for t in ct.values()
            if t.trang_thai == "da_sua"
            and t.ban_hien_hanh is None
            and t.xuat_xu_doc_id
            and t.xuat_xu_article
            # Phạm vi chặn NGAY Ở CHỖ HỎI, không chỉ ở chỗ nhận: không tốn một lượt tra
            # LanceDB cho thứ chắc chắn sẽ bị loại.
            and (pham_vi is None or t.xuat_xu_doc_id in pham_vi)
        }
    )
    # Bỏ tiền tố mà danh sách hit ĐÃ phủ — cùng luật ranh giới dấu cách với hàm tra, để
    # `"Điều 1"` không bị coi là đã phủ chỉ vì có sẵn `"Điều 10"`.
    can_them = [
        t for t in can_them if not any(i == t or i.startswith(t + " ") for i in co_san)
    ]
    if can_them:
        from app.ingestion.versioning import is_effective
        from app.knowledge.retrieval import lay_chunk_theo_tien_to

        try:
            them = lay_chunk_theo_tien_to(can_them)
        except Exception:  # noqa: BLE001 — fail-open: kéo thêm hỏng thì bớt đi, không ném
            them = []
        for c in them:
            cid = c.get("id")
            if not cid or cid in co_san:
                continue
            if pham_vi is not None and c.get("doc_id") not in pham_vi:
                continue
            # `lay_chunk_theo_tien_to` không lọc hiệu lực (nó chỉ tra địa chỉ). Mọi đường truy
            # hồi khác lọc bằng `is_effective` với đúng `as_of` — đường này phải giống, nếu
            # không thì lớp phủ trở thành cửa hậu đưa điều đã hết hiệu lực vào câu trả lời.
            if not is_effective(
                c.get("valid_from"), c.get("valid_to"), c.get("superseded", False), as_of
            ):
                continue
            # Chunk kéo thêm cũng là một hit sẽ nổi lên UI ⇒ phải mang nhãn như mọi hit khác
            # (thường là `la_loi_sua`: nó là LỜI VĂN SỬA, không phải quy định độc lập). Không
            # nhãn thì nó hiện ra như một `Citation` trần và người đọc tưởng đó là điều luật.
            t = chu_thich_chunk(c, as_of, lp)
            if t is not None:
                if t.trang_thai == "bi_bai_bo":
                    continue  # cùng luật với hit gốc: không kéo về căn cứ đã chết
                ct.setdefault(cid, t)
            co_san.add(cid)
            con.append(c)
    return con, ct
