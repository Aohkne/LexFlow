// Logic thuần cho trình xem văn bản: slug anchor điều + gom nhóm lược đồ.
import type { DocumentDetail, RelAnchor, Relationship } from "@/lib/api";
import { REL_DOI_NOI_DUNG, nhanNhom } from "@/lib/quan-he";

// Bảng 23 chữ dùng đánh số trong văn bản QPPL Việt Nam — phải khớp
// app/ontology/parser.py::VI_LETTERS. `đ` là chữ duy nhất thêm so với ASCII;
// không có f/j/w/z; sau `e` là `g`.
const VI_LETTERS = "abcdđeghiklmnopqrstuvxy";

// "Điều 26 Khoản 1-3" → "dieu-26"; "Điều 9a" → "dieu-9a"; "Điều 15đ" → "dieu-15đ".
// Null nếu không nhận ra.
// Lớp ký tự dựng TỪ bảng trên: `[a-zA-Z]` không khớp `đ`, nên "Điều 15đ" từng bị
// cắt thành "dieu-15" và đụng slug với "Điều 15" — hai điều khác nhau cùng một
// anchor, deep-link nhảy sai chỗ mà không báo lỗi.
const ARTICLE_RE = new RegExp(`Điều\\s+(\\d+[${VI_LETTERS}]?)`);

/** Slug neo dựng từ chính số hiệu Điều ("26", "9a", "15đ").
 *
 * Đường cây có sẵn `so` nên gọi thẳng hàm này; đường phẳng chỉ có chuỗi "Điều 26" nên phải bóc số
 * trước. Hai đường buộc phải cho ra cùng một id: mục lục chỉ dựng một lần rồi dùng chung, trỏ sai
 * là bấm không nhảy mà chẳng có lỗi nào hiện ra.
 */
export function neoDieu(so: string): string {
  return `dieu-${so.toLowerCase()}`;
}

export function articleAnchor(article: string): string | null {
  const m = article.match(ARTICLE_RE);
  return m ? neoDieu(m[1]) : null;
}

/**
 * Địa chỉ một đơn vị trong văn bản — CỐ Ý trùng đúng bộ khoá mà `TacDongDonVi` dùng
 * (`article` / `khoan` / `diem`), để việc đánh dấu đơn vị bị tác động sau này chỉ là một phép
 * tra bảng, không phải một phép dò chuỗi.
 */
export type DiaChiDonVi = {
  article: string; // "Điều 5" — cùng dạng với `TacDongDonVi.article`
  khoan: string | null; // "4"
  diem: string | null; // "a"
};

export function khoaDiaChi(dc: DiaChiDonVi): string {
  return `${dc.article}|${dc.khoan ?? ""}|${dc.diem ?? ""}`;
}

// Tiền tố đánh số ở ĐẦU một đoạn. Bắt buộc có khoảng trắng sau dấu chấm/ngoặc: thiếu điều kiện
// đó thì "1.000 đồng" bị đọc thành Khoản 1. Lớp chữ cái lấy từ VI_LETTERS chứ không phải [a-z],
// vì điểm trong văn bản QPPL có cả `đ` và không có f/j/w/z.
const KHOAN_RE = new RegExp(`^(\\d+[${VI_LETTERS}]?)\\.\\s`);
const DIEM_RE = new RegExp(`^([${VI_LETTERS}])\\)\\s`);

export type BacDoan = { cap: "khoan" | "diem" | null; so: string | null };

// Khối trích dẫn mở đầu bằng dấu ngoặc kép, nên tiền tố không nằm ở đầu chuỗi: html thật của
// Nghị định 80/2016 là `"4. Tổ chức cung ứng…`. Bỏ qua dấu mở ngoặc KHI DÒ, còn khi hiển thị thì
// giữ nguyên — dấu ngoặc là của văn bản, không phải của mình.
const MO_TRICH_RE = /^[“”"'\s]+/;

/** Đọc bậc của một đoạn từ chính tiền tố nguồn đã viết ("4. ", "a) "). */
export function bacTuTienTo(doan: string): BacDoan {
  const s = doan.replace(MO_TRICH_RE, "");
  const kh = s.match(KHOAN_RE);
  if (kh) return { cap: "khoan", so: kh[1] };
  const di = s.match(DIEM_RE);
  if (di) return { cap: "diem", so: di[1] };
  return { cap: null, so: null };
}

/**
 * Tách phần HTML inline của một nút thành các đoạn theo `<br>`.
 *
 * Bên vbpl.vn các đoạn nối tiếp là những thẻ `prov-content` riêng biệt; crawler gộp chúng vào
 * nút cha bằng `<br>` (`app/ingestion/vbpl.py`), nên một nút có thể đang ôm cả một khối trích
 * dẫn với khoản và điểm của nó. Không tách ra thì cả khối đổ thành một đoạn phẳng.
 */
export function tachDoan(html: string): string[] {
  return html
    .split(/<br\s*\/?>/i)
    .map((s) => s.trim())
    .filter(Boolean);
}

export type SchemaEntry = {
  docId: string; // văn bản phía bên kia của quan hệ
  title: string;
  validFrom: string | null;
  note: string | null;
  anchors: RelAnchor[];
};

export type SchemaGroup = { label: string; entries: SchemaEntry[] };

// Gom quan hệ 2 chiều của một văn bản thành các nhóm lược đồ có nhãn tiếng Việt.
export function groupRelationships(detail: DocumentDetail): SchemaGroup[] {
  const groups = new Map<string, SchemaEntry[]>();
  const add = (rel: Relationship, direction: "out" | "in") => {
    const label = nhanNhom(rel.rel_type, direction);
    const other = direction === "out" ? rel.target_doc : rel.source_doc;
    const list = groups.get(label) ?? [];
    list.push({
      docId: other,
      title: detail.doc_titles[other] ?? other,
      validFrom: rel.valid_from,
      note: rel.note,
      anchors: rel.anchors,
    });
    groups.set(label, list);
  };
  detail.relationships_out.forEach((r) => add(r, "out"));
  detail.relationships_in.forEach((r) => add(r, "in"));
  return [...groups.entries()].map(([label, entries]) => ({ label, entries }));
}

export type AmendmentInfo = {
  sourceDoc: string;
  sourceTitle: string;
  sourceArticle: string | null;
  relType: string; // một mã trong REL_DOI_NOI_DUNG
  detail: string | null;
  validFrom: string | null;
};

// Map anchor-id điều bị tác động → danh sách văn bản/điều sửa đổi nó (từ relationships_in).
export function buildAmendmentMap(detail: DocumentDetail): Map<string, AmendmentInfo[]> {
  const map = new Map<string, AmendmentInfo[]>();
  for (const rel of detail.relationships_in) {
    // Lọc theo TẬP, không theo hai tên gõ thẳng: `SUA_DOI` đã đổi thành `SUA_DOI_BO_SUNG` ở
    // backend, và dòng cũ khiến bản đồ sửa đổi lặng lẽ bỏ qua đúng những cạnh nó cần.
    if (!REL_DOI_NOI_DUNG.has(rel.rel_type)) continue;
    for (const a of rel.anchors) {
      const key = a.target_article ? articleAnchor(a.target_article) : null;
      if (!key) continue;
      const list = map.get(key) ?? [];
      list.push({
        sourceDoc: rel.source_doc,
        sourceTitle: detail.doc_titles[rel.source_doc] ?? rel.source_doc,
        sourceArticle: a.source_article,
        relType: rel.rel_type,
        detail: a.detail,
        validFrom: rel.valid_from,
      });
      map.set(key, list);
    }
  }
  return map;
}
