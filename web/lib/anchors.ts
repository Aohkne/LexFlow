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

export function articleAnchor(article: string): string | null {
  const m = article.match(ARTICLE_RE);
  return m ? `dieu-${m[1].toLowerCase()}` : null;
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
