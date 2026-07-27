// Logic thuần cho trình xem văn bản: slug anchor điều + gom nhóm lược đồ.
import type { DocumentDetail, RelAnchor, Relationship } from "@/lib/api";

// "Điều 26 Khoản 1-3" → "dieu-26"; "Điều 9a" → "dieu-9a". Null nếu không nhận ra.
export function articleAnchor(article: string): string | null {
  const m = article.match(/Điều\s+(\d+[a-zA-Z]?)/);
  return m ? `dieu-${m[1].toLowerCase()}` : null;
}

// Nhãn nhóm lược đồ theo quy ước thuvienphapluat: loại quan hệ × chiều so với văn bản đang mở.
const GROUP_LABEL: Record<string, { out: string; in: string }> = {
  THAY_THE: { out: "Văn bản bị thay thế", in: "Văn bản thay thế" },
  SUA_DOI: { out: "Văn bản bị sửa đổi, bổ sung", in: "Văn bản sửa đổi, bổ sung" },
  HUONG_DAN: { out: "Văn bản được hướng dẫn", in: "Văn bản hướng dẫn" },
  DAN_CHIEU: { out: "Văn bản được dẫn chiếu", in: "Văn bản dẫn chiếu" },
};

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
    const label = GROUP_LABEL[rel.rel_type]?.[direction] ?? rel.rel_type;
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
  relType: string; // SUA_DOI | THAY_THE
  detail: string | null;
  validFrom: string | null;
};

// Map anchor-id điều bị tác động → danh sách văn bản/điều sửa đổi nó (từ relationships_in).
export function buildAmendmentMap(detail: DocumentDetail): Map<string, AmendmentInfo[]> {
  const map = new Map<string, AmendmentInfo[]>();
  for (const rel of detail.relationships_in) {
    if (rel.rel_type !== "SUA_DOI" && rel.rel_type !== "THAY_THE") continue;
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
