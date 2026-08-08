// Mục lục của một văn bản: cây Chương → Mục → Điều, dùng cho thanh định vị và ngăn kéo mục lục.
//
// Hai đường dựng vì backend trả hai dạng: văn bản đã crawl lại có cây `provisions`, văn bản duyệt
// từ trước chỉ có danh sách Điều phẳng kèm chuỗi `chapter`/`section`. Cả hai phải ra cùng một kiểu
// dữ liệu, nếu không cùng một trang lại có mục lục theo hai kiểu tuỳ văn bản đã crawl lại hay chưa
// (38/2019/TT-NHNN hiện là văn bản duy nhất đi đường phẳng mà vẫn có chữ).
import type { Article, Provision } from "@/lib/api";
import { articleAnchor, neoDieu } from "@/lib/anchors";

export type CapMucLuc = "chuong" | "muc" | "dieu";

export type MucMucLuc = {
  anchor: string;
  cap: CapMucLuc;
  nhan: string; // "Chương I" | "Mục 1" | "Điều 4"
  tieuDe: string; // "QUY ĐỊNH CHUNG" | "Phạm vi điều chỉnh"
  con: MucMucLuc[];
};

// Giữ chữ Việt (`\p{L}` có cả `đ`), bỏ dấu chấm và ký tự lạ để id không phải escape khi vào CSS
// selector hay URL fragment.
function slug(s: string): string {
  return s
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^\p{L}\p{N}-]/gu, "");
}

export function neoChuong(so: string | null, thuTu: number): string {
  return `chuong-${so ? slug(so) : thuTu + 1}`;
}

/**
 * Neo của một Mục PHẢI mang theo Chương cha.
 *
 * "Mục 1" lặp lại ở từng Chương — 40/2024/TT-NHNN có 6 Mục nằm rải trong 5 Chương. Đặt id chỉ theo
 * số Mục thì hai Mục 1 khác nhau trùng id: HTML sai, và deep-link luôn nhảy về cái đầu tiên.
 */
export function neoMuc(neoChuongCha: string | null, so: string | null, thuTu: number): string {
  return `${neoChuongCha ?? "vb"}-muc-${so ? slug(so) : thuTu + 1}`;
}

/** Dựng mục lục từ cây `provisions`. */
export function mucLucTuCay(nodes: Provision[]): MucMucLuc[] {
  const di = (ns: Provision[], neoCha: string | null): MucMucLuc[] => {
    const ra: MucMucLuc[] = [];
    ns.forEach((n, i) => {
      if (n.cap === "chuong") {
        const anchor = neoChuong(n.so, i);
        ra.push({
          anchor,
          cap: "chuong",
          nhan: `Chương ${n.so ?? ""}`.trim(),
          tieuDe: n.tieu_de,
          con: di(n.con, anchor),
        });
      } else if (n.cap === "muc") {
        const anchor = neoMuc(neoCha, n.so, i);
        ra.push({
          anchor,
          cap: "muc",
          nhan: `Mục ${n.so ?? ""}`.trim(),
          tieuDe: n.tieu_de,
          con: di(n.con, anchor),
        });
      } else if (n.cap === "dieu" && n.so) {
        // Dừng ở cấp Điều. 40/2024/TT-NHNN có 193 khoản và 221 điểm — đưa xuống tới đó thì mục lục
        // dài đúng bằng cái văn bản mà nó phải tóm tắt.
        ra.push({ anchor: neoDieu(n.so), cap: "dieu", nhan: `Điều ${n.so}`, tieuDe: n.tieu_de, con: [] });
      }
    });
    return ra;
  };
  return di(nodes, null);
}

// "Chương I. QUY ĐỊNH CHUNG" → nhãn "Chương I", tên "QUY ĐỊNH CHUNG". Nguồn ghép hai phần bằng
// dấu chấm ở đường phẳng, còn đường cây trả rời sẵn thành `so` và `tieu_de`.
const NHAN_RE = /^(Chương|Mục)\s+([^.]+?)\s*(?:\.\s*(.*))?$/;

function tachNhan(s: string): { nhan: string; so: string | null; tieuDe: string } {
  const m = s.match(NHAN_RE);
  if (!m) return { nhan: s.trim(), so: null, tieuDe: "" };
  return { nhan: `${m[1]} ${m[2]}`, so: m[2], tieuDe: (m[3] ?? "").trim() };
}

/** Một dòng của đường render phẳng: Điều, kèm tiêu đề Chương/Mục nếu nhãn vừa đổi. */
export type DongPhang = {
  a: Article;
  neo: string | null;
  chuong: { anchor: string; nhan: string; tieuDe: string } | null;
  muc: { anchor: string; nhan: string; tieuDe: string } | null;
};

/**
 * Chuẩn bị đường render phẳng: chèn mốc Chương/Mục ở đúng chỗ nhãn đổi, và cấp neo cho từng mốc.
 *
 * Trang render và mục lục đều đọc từ kết quả này. Nếu mỗi bên tự tính neo thì chỉ cần một bên đổi
 * quy tắc là mục lục trỏ vào id không tồn tại — mà lỗi đó im lặng, bấm vào chỉ thấy không nhảy.
 */
export function dongPhang(articles: Article[]): DongPhang[] {
  const ra: DongPhang[] = [];
  let sChuong: string | null = null;
  let sMuc: string | null = null;
  let neoChuongHienTai: string | null = null;

  articles.forEach((a, i) => {
    let chuong: DongPhang["chuong"] = null;
    let muc: DongPhang["muc"] = null;

    if (a.chapter && a.chapter !== sChuong) {
      sChuong = a.chapter;
      sMuc = null; // sang Chương mới thì Mục đánh số lại từ đầu
      const t = tachNhan(a.chapter);
      neoChuongHienTai = neoChuong(t.so, i);
      chuong = { anchor: neoChuongHienTai, nhan: t.nhan, tieuDe: t.tieuDe };
    }
    if (a.section && a.section !== sMuc) {
      sMuc = a.section;
      const t = tachNhan(a.section);
      muc = { anchor: neoMuc(neoChuongHienTai, t.so, i), nhan: t.nhan, tieuDe: t.tieuDe };
    }
    ra.push({ a, neo: articleAnchor(a.article), chuong, muc });
  });
  return ra;
}

/** Dựng mục lục từ chính các dòng mà đường phẳng sẽ render. */
export function mucLucTuDongPhang(dong: DongPhang[]): MucMucLuc[] {
  const goc: MucMucLuc[] = [];
  let chuong: MucMucLuc | null = null;
  let muc: MucMucLuc | null = null;

  for (const d of dong) {
    if (d.chuong) {
      chuong = { ...d.chuong, cap: "chuong", con: [] };
      muc = null;
      goc.push(chuong);
    }
    if (d.muc) {
      muc = { ...d.muc, cap: "muc", con: [] };
      (chuong?.con ?? goc).push(muc);
    }
    if (d.neo) {
      const m: MucMucLuc = { anchor: d.neo, cap: "dieu", nhan: d.a.article, tieuDe: "", con: [] };
      (muc?.con ?? chuong?.con ?? goc).push(m);
    }
  }
  return goc;
}

export type NeoDoc = {
  anchor: string;
  cap: CapMucLuc;
  nhan: string;
  tieuDe: string;
  duongDan: string[]; // nhãn tổ tiên, ngoài cùng trước — chính là đường dẫn hiện trên thanh định vị
};

/** Trải mục lục thành danh sách theo đúng thứ tự văn bản, kèm đường dẫn tới từng mốc. */
export function phangMucLuc(nodes: MucMucLuc[], duongDan: string[] = []): NeoDoc[] {
  const ra: NeoDoc[] = [];
  for (const n of nodes) {
    ra.push({ anchor: n.anchor, cap: n.cap, nhan: n.nhan, tieuDe: n.tieuDe, duongDan });
    if (n.con.length > 0) ra.push(...phangMucLuc(n.con, [...duongDan, n.nhan]));
  }
  return ra;
}
