"""Bản ghi vbpl đã crawl → `CorpusDocument`.

**Lịch sử ngắn, vì nó giải thích hình dạng module.** Lượt crawl đầu sinh `articles[].text` bằng
cách làm phẳng cây `provisions`, và bước đó **bỏ mất số thứ tự khoản/điểm lẫn tiêu đề điều**:
`parse_dieu` trên `articles[].text` của TT15/2024 cho **98 khoản → 0, 57 điểm → 0**. Không phải
"kém chính xác hơn" mà là **mất trắng cả tầng dưới Điều**, vì mọi thứ ở tầng đó khoá bằng chính
con số ấy. Module này khi đó tự dựng lại thân điều từ `noi_dung` thô.

**Lượt crawl sau đã sửa, nên module đảo vai.** Đo lại trên 8 văn bản có toàn văn:

- `articles[].text` khớp `noi_dung` **từng ký tự qua `char_start`/`char_end` — 8/8 văn bản,
  100% số điều**. Đây là bất biến `char_span` của chính hệ thống này, do nguồn tự bảo đảm.
- Số khoản/điểm khớp đúng bảng nghiệm thu đã thoả thuận (TT15 23/97/57, ND52 38/153/102, …).
- `chapter`/`section` đã điền ở mọi văn bản **có** Chương (ND52 38/38, TT40 54/54, TT15 23/23);
  các văn bản còn 0 đều là văn bản sửa đổi ngắn, cây cũng không có Chương nào.

⇒ `articles[]` nay là **nguồn**, còn phép dựng lại từ `noi_dung` (`dieu_tu_toan_van`) ở lại làm
**đối chứng độc lập**. Giữ đối chứng chứ không xoá, vì cái đã hỏng một lần thì hỏng lại được, và
kiểu hỏng của nó là **im lặng**: 0 khoản trông y hệt một điều không chẻ khoản (25/267 điều trong
corpus đúng là như vậy), không exception nào bắn ra.

Ba chỗ **cố ý không tự quyết**:

1. **`char_span` sai thì TỪ CHỐI**, không lặng lẽ dùng `articles[]` rồi hi vọng. Sai ở đây nghĩa
   là `articles[]` không còn neo vào `noi_dung`, mà cả tầng ontology neo vào đúng chỗ đó.
2. **Văn bản 0 điều không được thành `CorpusDocument`.** `29/VBHN-NHNN` chỉ có thuộc tính và
   lược đồ (vbpl không đăng toàn văn, nhiều khả năng nằm trong tệp đính kèm). Một node khai
   "có toàn văn" mà rỗng **tệ hơn node rỗng**, vì node rỗng nói thật rằng nó chưa có gì.
3. **Không ghi đè văn bản đã có trong corpus.** Trả về để người gọi so và quyết.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.schemas import Article, CorpusDocument
from app.core.so_hieu import phan_tich
from app.ingestion.extract import split_articles
from app.ontology.parser import parse_dieu

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


def dieu_tu_ban_ghi(raw: dict, noi_dung: str) -> tuple[list[Article], list[str]]:
    """`articles[]` của bản ghi → `list[Article]`, sau khi **kiểm hai lớp**.

    Lớp 1 — `char_span`: `noi_dung[char_start:char_end]` phải bằng đúng `text`. Đây là bất biến
    mà cả tầng ontology dựa vào, và nó **kiểm được ngay tại đây** nên không có lý do gì để tin
    suông. Lệch ⇒ trả rỗng kèm cảnh báo, tức từ chối cả văn bản.

    Lớp 2 — **đánh số còn không**: chạy phép dựng lại độc lập từ `noi_dung` và so số khoản/điểm.
    Lệch thì cảnh báo chứ không từ chối: hai bộ tách ranh giới điều hơi khác nhau là chuyện
    thường, còn **0 khoản trên một văn bản nhiều điều** mới là dấu hiệu của khuyết tật cũ —
    và đó là thứ không tự lộ ra, vì 0 khoản trông y hệt một điều không chẻ khoản.
    """
    goc = raw.get("articles") or []
    if not goc:
        return [], []
    cb: list[str] = []
    lech = [
        a.get("article")
        for a in goc
        if not (
            isinstance(a.get("char_start"), int)
            and noi_dung[a["char_start"] : a.get("char_end", 0)] == a.get("text")
        )
    ]
    if lech:
        return [], [
            f"char_span sai ở {len(lech)}/{len(goc)} điều ({', '.join(map(str, lech[:5]))}"
            f"{'…' if len(lech) > 5 else ''}) — articles[] không còn neo vào noi_dung, TỪ CHỐI "
            f"cả văn bản thay vì nạp một xuất xứ không kiểm được"
        ]

    dieu = [
        Article(
            article=a["article"], text=a["text"],
            chapter=a.get("chapter"), section=a.get("section"),
            superseded=bool(a.get("superseded")),
        )
        for a in goc
    ]
    doi_chung = dieu_tu_toan_van(noi_dung, raw.get("provisions") or [])
    sh = raw.get("so_hieu") or "?"
    n_goc, n_dc = _dem_khoan_diem(dieu, sh), _dem_khoan_diem(doi_chung, sh)
    if n_goc[0] == 0 and len(dieu) > 1 and n_dc[0] > 0:
        cb.append(
            f"articles[] cho 0 khoản trên {len(dieu)} điều, trong khi dựng lại từ noi_dung cho "
            f"{n_dc[0]} — đúng dấu hiệu đánh số bị mất khi làm phẳng cây"
        )
    elif n_goc != n_dc:
        cb.append(
            f"đối chứng lệch: articles[] {n_goc[0]} khoản/{n_goc[1]} điểm, dựng lại từ noi_dung "
            f"{n_dc[0]}/{n_dc[1]} — thường do ranh giới điều, kiểm nếu chênh nhiều"
        )
    return dieu, cb


def _dem_khoan_diem(dieu: list[Article], so_hieu: str) -> tuple[int, int]:
    kh = di = 0
    for a in dieu:
        d = parse_dieu(f"{a.article}. {a.text}", so_hieu)
        kh += len(d.khoan)
        di += sum(len(k.diem) for k in d.khoan)
    return kh, di


def cat_duoi_hanh_chinh(dieu: list[Article]) -> tuple[list[Article], int]:
    """Cắt khối `Nơi nhận:`/chữ ký/phụ lục vbpl dán sau điều cuối. → (điều đã cắt, số ký tự bỏ).

    vbpl không có nút riêng cho đuôi văn bản, nên toàn bộ phần sau điều cuối — danh sách nơi
    nhận, chức danh, `(Đã ký)`, và ở TT40/2024 là cả **7k ký tự biểu mẫu phụ lục** — nằm trong
    `articles[-1].text`. Phần đó không thuộc điều nào; phụ lục theo v0.5 có nhánh `#phuluc_`
    riêng, dán vào `#than/dieu_cuoi` là sai chỗ chứ không phải "thêm dữ liệu".

    Ranh giới: **dòng đúng bằng** `Nơi nhận:` — cả 5/8 văn bản có đuôi đều in vậy, danh sách
    nơi nhận nằm các dòng sau. `Nơi nhận: <nội dung cùng dòng>` là chữ trong thân, không cắt.
    Chỉ đụng điều cuối, và chỉ SAU khi `char_span` đã kiểm xong — Article của corpus không
    mang offset nên vết neo vào `noi_dung` không bị phá.
    """
    if not dieu:
        return dieu, 0
    cuoi = dieu[-1]
    vi_tri = 0
    for dong in cuoi.text.splitlines(keepends=True):
        if dong.strip() == "Nơi nhận:":
            moi = cuoi.model_copy(update={"text": cuoi.text[:vi_tri].rstrip()})
            return [*dieu[:-1], moi], len(cuoi.text) - len(moi.text)
        vi_tri += len(dong)
    return dieu, 0


class KetQuaDoc(BaseModel):
    """Một file `*.corpus.json` đã đọc. `van_ban is None` ⇒ chưa dùng được, xem `canh_bao`."""

    duong_dan: str
    so_hieu: str | None = None
    van_ban: CorpusDocument | None = None
    doc_id_trong_file: str | None = None
    canh_bao: list[str] = Field(default_factory=list)


def duong_dan_toan_van(p: Path) -> Path:
    """File đã chuyển khuôn → bản ghi thô, nơi duy nhất còn `noi_dung` nguyên vẹn.

    Hai bố cục cùng được đỡ, vì bộ crawl đã đổi cách xếp file giữa hai lượt:

    - **thư mục** (hiện dùng): `…/corpus/<slug>.json` → `…/raw/<slug>.json`;
    - **phẳng** (lượt đầu): `<slug>.corpus.json` → `<slug>.json`.

    Không phải chiều lòng cả hai cho vui: bản ghi cũ vẫn nằm trong lịch sử git và trong các
    lần crawl trước của người dùng, nên bộ đọc mà chỉ hiểu một bố cục sẽ **im lặng đọc ra 0
    văn bản** — đúng cái đã xảy ra một lần.
    """
    if p.parent.name == "corpus":
        return p.parent.parent / "raw" / p.name
    if p.name.endswith(".corpus.json"):
        return p.with_name(p.name[: -len(".corpus.json")] + ".json")
    return p


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
    noi_dung = tho.get("noi_dung") or ""
    dieu, cb_dieu = dieu_tu_ban_ghi(raw, noi_dung)
    cb += cb_dieu
    if cb_dieu and not dieu:
        return KetQuaDoc(duong_dan=str(p), so_hieu=sh.chuan,
                         doc_id_trong_file=raw.get("doc_id"), canh_bao=cb)
    if not dieu:
        cb.append(
            "0 điều — vbpl chỉ đăng thuộc tính/lược đồ, không có toàn văn. GIỮ LÀM NODE RỖNG: "
            "một node khai 'có toàn văn' mà rỗng còn tệ hơn, vì nó không nói ra là mình trống"
        )
        return KetQuaDoc(duong_dan=str(p), so_hieu=sh.chuan,
                         doc_id_trong_file=raw.get("doc_id"), canh_bao=cb)
    dieu, bo = cat_duoi_hanh_chinh(dieu)
    if bo:
        cb.append(
            f"cắt {bo} ký tự đuôi hành chính (Nơi nhận/chữ ký/phụ lục) khỏi "
            f"{dieu[-1].article} — phần này không thuộc điều nào; phụ lục chờ nhánh #phuluc_"
        )
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


def file_da_chuyen_khuon(thu_muc: Path) -> list[Path]:
    """Các file đã chuyển khuôn trong thư mục, theo bố cục nào cũng nhận. Xem `duong_dan_toan_van`."""
    con = thu_muc / "corpus"
    if con.is_dir():
        return sorted(con.glob("*.json"))
    return sorted(thu_muc.glob("*.corpus.json"))


def file_tho(thu_muc: Path) -> list[Path]:
    """Các file **có thể** là bản ghi vbpl thô. Bố cục `raw/` hoặc phẳng đều nhận.

    "Có thể" vì tên file không nói lên điều gì — bố cục phẳng để lẫn cả `*.corpus.json` lẫn
    `crawl-report.json`. Việc lọc là của người gọi, dựa trên **hình dạng** nội dung.
    """
    con = thu_muc / "raw"
    if con.is_dir():
        return sorted(con.glob("*.json"))
    return sorted(thu_muc.glob("*.json")) if thu_muc.is_dir() else []


def tho_theo_so_hieu(thu_muc: Path) -> dict[str, Path]:
    """`{số hiệu: đường dẫn bản ghi thô}` — tra theo **nội dung file**, không theo tên file.

    Có hàm này vì tên file đã đổi hai lần (`sample.json` → `<slug>.json` → `raw/<slug>.json`),
    và mỗi lần đổi thì mọi chỗ trỏ tới đường dẫn cứng **im lặng hỏng**: test có `skipif` thì
    chuyển sang skip, công cụ thì đọc ra 0 bản ghi rồi báo "không còn gì để làm". Số hiệu nằm
    *trong* file nên không đổi theo cách xếp file.
    """
    ra: dict[str, Path] = {}
    for p in file_tho(thu_muc):
        try:
            mau = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not (isinstance(mau, dict) and isinstance(mau.get("luoc_do"), dict)):
            continue
        sh = phan_tich((mau.get("thuoc_tinh") or {}).get("so_hieu") or "")
        if sh:
            ra.setdefault(sh.chuan, p)
    return ra


def doc_thu_muc(thu_muc: Path) -> list[KetQuaDoc]:
    return [doc_file(p) for p in file_da_chuyen_khuon(thu_muc)]
