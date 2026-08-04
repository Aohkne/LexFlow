"""Bản ghi vbpl đã crawl → `CorpusDocument`: **thân điều lấy từ `noi_dung` thô, Chương/Mục lấy
từ cây `provisions`**.

Vì sao không dùng `articles` có sẵn trong `*.corpus.json`: bước làm phẳng cây thành
`articles[].text` **bỏ mất số thứ tự khoản/điểm và tiêu đề điều**. Đo trên TT15/2024 — văn bản
duy nhất có mặt ở cả corpus lẫn bản crawl, nên so được: chạy `parse_dieu` trên `articles[].text`
cho **98 khoản → 0, 57 điểm → 0**. Không phải "kém chính xác hơn" mà là **mất trắng cả tầng dưới
Điều**, vì mọi thứ ở tầng đó khoá bằng chính con số ấy — `#than/dieu_n#khoan_m#diem_x`,
`source_diem`, `char_span`, `tach_guard`.

Vì sao cũng **không** dựng từ cây `provisions`: dựng lại từ cây lấy về 88/48, khá hơn 0/0 nhưng
vẫn thiếu. Truy ra thì **cây tự nó không đầy đủ**: ở `Điều 7`, khoản `1.` và điểm `a) Lập, gửi
chứng từ` không có trong cây, con của chúng bị nâng thẳng lên dưới Điều. Một cây thiếu nút thì
không phép dựng lại nào cứu được.

`noi_dung` thô thì nguyên vẹn, và đo được là **tập cha thật sự** của corpus hiện có:

| nguồn | điều | khoản | điểm |
|---|---|---|---|
| `data/corpus.real.json` | 22 | 98 | 57 |
| `noi_dung` thô qua `split_articles` | **23** | **102** | 57 |

— không điều nào của corpus vắng mặt, và có thêm `Điều 19` mà corpus đang **thiếu hẳn**.

Cây `provisions` vẫn có một việc không ai thay được: nó mang **Chương/Mục**. `Article.chapter`
khai trong schema đã lâu mà **0/278 điều có giá trị**, vì `extract.py` bỏ dòng Chương khi tách.
Nên chia vai: *thân điều* theo văn bản thô, *nhãn phân cấp* theo cây.

Hai chỗ **cố ý không tự quyết**:

1. **Văn bản 0 điều không được thành `CorpusDocument`.** `29/VBHN-NHNN` chỉ có thuộc tính và
   lược đồ (vbpl không đăng toàn văn, nhiều khả năng nằm trong tệp đính kèm). Một node khai
   "có toàn văn" mà rỗng **tệ hơn node rỗng**, vì node rỗng nói thật rằng nó chưa có gì.
2. **Không ghi đè văn bản đã có trong corpus.** Trả về để người gọi so và quyết.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.schemas import Article, CorpusDocument
from app.core.so_hieu import phan_tich
from app.ingestion.extract import split_articles

#: `NĐ` → `ND`: `doc_id` của corpus dùng ASCII (`ND52-2024`), xem `data/corpus.real.json`.
_ASCII = {"Đ": "D", "đ": "d"}


def doc_id_theo_corpus(so_hieu: str) -> str | None:
    """Số hiệu → `doc_id` theo **đúng quy ước corpus đang dùng**, không phải quy ước mới.

    Đo trên 11 văn bản ngoại trong `data/corpus.real.json`: `101/2012/NĐ-CP` → `ND101-2012`,
    `15/2024/TT-NHNN` → `TT15-2024`. Tức `<loại ASCII><số>-<năm>`.

    Đây **không phải** bịa `doc_id` như ở node rỗng: ở đó ta chưa có văn bản nên mọi cái tên đều
    là phỏng đoán; ở đây ta đang cầm chính văn bản, nên đặt tên theo quy ước là việc xác định.
    Không theo quy ước thì `15/2024/TT-NHNN` vào corpus lần hai dưới tên `15-2024-TT-NHNN` và
    thành **hai node cho một văn bản** — đúng kiểu hỏng mà cả lớp bắc cầu này sinh ra để chặn.

    Ký hiệu không có năm (`29/VBHN-NHNN`) thì lấy cơ quan làm phần phân biệt: `VBHN29-NHNN`.
    """
    sh = phan_tich(so_hieu)
    if sh is None:
        return None
    if sh.khoa_qh:  # nhóm Quốc hội: 59/2020/QH14 → L59-2020
        return f"L{sh.so}-{sh.nam}"
    loai = "".join(_ASCII.get(c, c) for c in (sh.loai or ""))
    duoi = sh.nam or (sh.co_quan[0] if sh.co_quan else None)
    return f"{loai}{sh.so}-{duoi}" if loai and duoi else None


def _nhan(cap: str, so: str, tieu_de: str) -> str:
    ten = {"chuong": "Chương", "muc": "Mục"}[cap]
    return f"{ten} {so}. {tieu_de}".strip().rstrip(".")


def phan_cap_tu_cay(provisions: list[dict]) -> dict[str, tuple[str | None, str | None]]:
    """Cây `provisions` → `{"Điều 5": (chapter, section)}`.

    Đây là phần **duy nhất** lấy từ cây: nhãn phân cấp. Thân điều lấy từ `noi_dung` thô, vì cây
    thiếu nút ở tầng khoản/điểm (xem docstring module).
    """
    ra: dict[str, tuple[str | None, str | None]] = {}

    def di(nut: dict, chuong: str | None, muc: str | None) -> None:
        cap = nut.get("cap")
        if cap == "chuong":
            chuong, muc = _nhan(cap, nut.get("so", ""), nut.get("tieu_de") or ""), None
        elif cap == "muc":
            muc = _nhan(cap, nut.get("so", ""), nut.get("tieu_de") or "")
        elif cap == "dieu":
            ra.setdefault(f"Điều {nut.get('so')}", (chuong, muc))
            return
        for c in nut.get("con") or []:
            di(c, chuong, muc)

    for n in provisions:
        di(n, None, None)
    return ra


def dieu_tu_toan_van(noi_dung: str, provisions: list[dict]) -> list[Article]:
    """Toàn văn thô → `list[Article]`, gắn `chapter`/`section` suy từ cây.

    Dùng lại `split_articles` của `extract.py` — cùng một bộ tách đã sinh ra corpus hiện tại,
    nên hai bên so được với nhau chứ không phải so hai cách đọc khác nhau.
    """
    bang = phan_cap_tu_cay(provisions)
    ra = []
    for a in split_articles(noi_dung):
        ch, mu = bang.get(a.article, (None, None))
        ra.append(a.model_copy(update={"chapter": ch, "section": mu}))
    return ra


class KetQuaDoc(BaseModel):
    """Một file `*.corpus.json` đã đọc. `van_ban is None` ⇒ chưa dùng được, xem `canh_bao`."""

    duong_dan: str
    so_hieu: str | None = None
    van_ban: CorpusDocument | None = None
    doc_id_trong_file: str | None = None
    canh_bao: list[str] = Field(default_factory=list)


def duong_dan_toan_van(p: Path) -> Path:
    """`…-t.corpus.json` → `…-t.json` — bản ghi thô, nơi duy nhất còn `noi_dung` nguyên vẹn."""
    return p.with_name(p.name[: -len(".corpus.json")] + ".json")


def doc_file(p: Path) -> KetQuaDoc:
    raw = json.loads(p.read_text(encoding="utf-8"))
    cb: list[str] = []
    sh_raw = raw.get("so_hieu")
    sh = phan_tich(sh_raw or "")
    if sh is None:
        return KetQuaDoc(duong_dan=str(p), canh_bao=[f"không đọc được số hiệu {sh_raw!r}"])
    cb += [f"số hiệu: {x}" for x in sh.canh_bao]

    p_tho = duong_dan_toan_van(p)
    if not p_tho.exists():
        return KetQuaDoc(
            duong_dan=str(p), so_hieu=sh.chuan, doc_id_trong_file=raw.get("doc_id"),
            canh_bao=cb + [
                f"thiếu bản ghi thô {p_tho.name!r} — không dựng được thân điều. KHÔNG dùng "
                f"`articles` sẵn có: nó đã mất đánh số khoản/điểm"
            ],
        )
    tho = json.loads(p_tho.read_text(encoding="utf-8"))
    dieu = dieu_tu_toan_van(tho.get("noi_dung") or "", raw.get("provisions") or [])
    if not dieu:
        cb.append(
            "0 điều — vbpl chỉ đăng thuộc tính/lược đồ, không có toàn văn. GIỮ LÀM NODE RỖNG: "
            "một node khai 'có toàn văn' mà rỗng còn tệ hơn, vì nó không nói ra là mình trống"
        )
        return KetQuaDoc(duong_dan=str(p), so_hieu=sh.chuan,
                         doc_id_trong_file=raw.get("doc_id"), canh_bao=cb)
    thieu_ch = sum(1 for a in dieu if not a.chapter)
    if thieu_ch and thieu_ch < len(dieu):
        cb.append(f"{thieu_ch}/{len(dieu)} điều không suy được Chương từ cây provisions")

    doc_id = doc_id_theo_corpus(sh.chuan)
    if doc_id and raw.get("doc_id") and raw["doc_id"] != doc_id:
        cb.append(
            f"doc_id trong file là {raw['doc_id']!r}, quy ước corpus là {doc_id!r} — dùng quy "
            f"ước corpus để không sinh hai node cho một văn bản"
        )
    return KetQuaDoc(
        duong_dan=str(p),
        so_hieu=sh.chuan,
        doc_id_trong_file=raw.get("doc_id"),
        canh_bao=cb,
        van_ban=CorpusDocument(
            doc_id=doc_id or raw.get("doc_id") or sh.chuan,
            title=unicodedata.normalize("NFC", raw.get("title") or "").strip() or sh.chuan,
            doc_type=raw.get("doc_type") or "Thông tư",
            source=raw.get("source") or "external",
            so_hieu=sh.chuan,
            valid_from=raw.get("valid_from"),
            valid_to=raw.get("valid_to"),
            articles=dieu,
        ),
    )


def doc_thu_muc(thu_muc: Path) -> list[KetQuaDoc]:
    return [doc_file(p) for p in sorted(thu_muc.glob("*.corpus.json"))]
