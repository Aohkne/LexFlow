// 13 quan hệ giữa văn bản theo KG v0.5 §6 — bản TS của `app/core/schemas.py::REL_TYPES`.
//
// Vì sao gom về một file: bảng này từng bị chép ở ba nơi (`lib/anchors.ts`, `graph/page.tsx`,
// `alerts/page.tsx`), và cả ba đều mắc kẹt ở bốn tên **tự đặt** của bản đầu — `THAY_THE`,
// `SUA_DOI`, `HUONG_DAN`, `DAN_CHIEU`. Khi backend chuẩn hoá về 13 mã v0.5 thì không nơi nào
// trong ba nơi đó biết, và hỏng theo kiểu **không ai thấy**: `GROUP_LABEL[rel.rel_type]` trả
// `undefined`, rơi xuống nhánh dự phòng, người dùng đọc được đúng chữ `SUA_DOI_BO_SUNG` thay
// vì "Văn bản sửa đổi, bổ sung", mà không có lỗi nào trong console.
//
// `HUONG_DAN` thì không chỉ lệch tên — nó **không phải một quan hệ có thật**. v0.5 §6.3 tách
// làm hai loại mà Điều 53 khoản 2 đối xử khác nhau: `QUY_DINH_CHI_TIET_HUONG_DAN` (ban hành
// theo uỷ quyền) và `HUONG_DAN_AP_DUNG` (hướng dẫn thuần tuý).
//
// Thứ tự cặp nhãn: [chủ động, bị động] — khớp `REL_TYPES` phía Python.

export const REL_LABELS: Record<string, readonly [string, string]> = {
  BAI_BO: ["bãi bỏ", "bị bãi bỏ"],
  // Cặp bất quy tắc: hai nhãn KHÔNG chung gốc từ ("căn cứ ban hành" ⟷ "áp dụng"), nên suy
  // nhãn bị động bằng cách thêm "được/bị" là sai đúng ở đây. Phải chép cả cặp.
  CAN_CU: ["căn cứ ban hành", "áp dụng"],
  CONG_BO: ["công bố", "được công bố"],
  DAN_CHIEU: ["dẫn chiếu", "được dẫn chiếu"],
  DINH_CHI_THI_HANH: ["đình chỉ thi hành", "bị đình chỉ thi hành"],
  DINH_CHINH: ["đính chính", "được đính chính"],
  GIAI_THICH: ["giải thích", "được giải thích"],
  HOP_NHAT: ["hợp nhất", "được hợp nhất"],
  HUONG_DAN_AP_DUNG: ["hướng dẫn áp dụng", "được hướng dẫn áp dụng"],
  QUY_DINH_CHI_TIET_HUONG_DAN: [
    "quy định chi tiết, hướng dẫn thi hành",
    "được quy định chi tiết, hướng dẫn thi hành",
  ],
  SUA_DOI_BO_SUNG: ["sửa đổi, bổ sung", "được sửa đổi, bổ sung"],
  TAM_NGUNG_HIEU_LUC: ["tạm ngưng hiệu lực", "bị tạm ngưng hiệu lực"],
  THAY_THE: ["thay thế", "được thay thế"],
};

export const REL_TYPES = Object.keys(REL_LABELS);

// Quan hệ mang **can thiệp bất lợi** — huỷ bỏ hoặc treo hiệu lực. Khớp `REL_BAT_LOI`.
export const REL_BAT_LOI = new Set([
  "BAI_BO",
  "DINH_CHI_THI_HANH",
  "TAM_NGUNG_HIEU_LUC",
]);

// Quan hệ ĐỔI NỘI DUNG của văn bản đích — dùng để dựng bản đồ sửa đổi theo từng điều.
// `SUA_DOI` cũ nằm trong tập này; đổi tên xong mà quên chỗ đó thì bản đồ sửa đổi **rỗng đi
// mà không báo gì**, vì lọc theo một tên không còn ai dùng.
export const REL_DOI_NOI_DUNG = new Set([
  "THAY_THE",
  "SUA_DOI_BO_SUNG",
  "HOP_NHAT",
  "DINH_CHINH",
]);

// Nhãn nhóm lược đồ theo quy ước thuvienphapluat: chiều "out" = văn bản đang mở là NGUỒN.
export function nhanNhom(relType: string, direction: "out" | "in"): string {
  const cap = REL_LABELS[relType];
  if (!cap) return relType;
  // Đang mở A, A -[THAY_THE]-> B  ⇒  với B thì A là văn bản thay thế nó ⇒ "Văn bản bị thay thế".
  return direction === "out" ? `Văn bản ${cap[1]}` : `Văn bản ${cap[0]}`;
}

export function nhanNgan(relType: string): string {
  return REL_LABELS[relType]?.[0] ?? relType;
}
