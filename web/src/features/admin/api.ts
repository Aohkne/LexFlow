import { readLocalStore, writeLocalStore } from "@/shared/store/localStore";
import type { AdminDocument, RegulatoryAlert } from "./types";

const DOCS_KEY = "lexflow_admin_documents";
const ALERTS_KEY = "lexflow_admin_alerts";

// Dữ liệu mẫu — chờ backend nối vào pipeline ingest thật (app/ingestion).
const SEED_DOCUMENTS: AdminDocument[] = [
  {
    id: "doc-01",
    title: "Nghị định quy định về thanh toán không dùng tiền mặt",
    doc_type: "Nghị định",
    status: "approved",
    valid_from: "2024-07-01",
    valid_to: null,
    submitted_by: "phapche.a@shb.com.vn",
    submitted_at: "2024-06-18T09:12:00",
    conflict_warning: null,
  },
  {
    id: "doc-02",
    title: "Nghị định về hoạt động cung ứng dịch vụ trung gian thanh toán",
    doc_type: "Nghị định",
    status: "approved",
    valid_from: "2024-07-01",
    valid_to: null,
    submitted_by: "phapche.a@shb.com.vn",
    submitted_at: "2024-06-18T09:20:00",
    conflict_warning: null,
  },
  {
    id: "doc-03",
    title: "Thông tư hướng dẫn mở và sử dụng tài khoản thanh toán",
    doc_type: "Thông tư",
    status: "pending",
    valid_from: "2025-01-01",
    valid_to: null,
    submitted_by: "phapche.b@shb.com.vn",
    submitted_at: "2026-07-20T14:05:00",
    conflict_warning: null,
  },
  {
    id: "doc-04",
    title: "Quyết định về hạn mức giao dịch ví điện tử cá nhân",
    doc_type: "Quyết định",
    status: "pending",
    valid_from: "2025-03-01",
    valid_to: null,
    submitted_by: "phapche.b@shb.com.vn",
    submitted_at: "2026-07-21T10:40:00",
    conflict_warning: "Chồng hạn mức với Quyết định 12/2019/QĐ-NHNN — cần đối chiếu trước khi duyệt.",
  },
  {
    id: "doc-05",
    title: "Thông tư sửa đổi quy định về Open API trong hoạt động ngân hàng",
    doc_type: "Thông tư",
    status: "rejected",
    valid_from: "2025-05-01",
    valid_to: null,
    submitted_by: "phapche.c@shb.com.vn",
    submitted_at: "2026-07-15T08:30:00",
    conflict_warning: "Bản scan thiếu trang phụ lục — yêu cầu nộp lại bản đầy đủ.",
  },
];

const SEED_ALERTS: RegulatoryAlert[] = [
  {
    id: "alert-01",
    title: "Dự thảo sửa đổi hạn mức ví điện tử cá nhân",
    doc_type: "Quyết định",
    published_at: "2026-07-18",
    effective_at: "2026-09-01",
    affected_flows: ["Nạp ví điện tử qua ngân hàng liên kết", "Rút tiền về tài khoản liên kết"],
    severity: "critical",
    summary: "NHNN lấy ý kiến giảm hạn mức giao dịch/tháng đối với ví chưa định danh mức 2.",
  },
  {
    id: "alert-02",
    title: "Thông tư hướng dẫn báo cáo giao dịch đáng ngờ qua trung gian thanh toán",
    doc_type: "Thông tư",
    published_at: "2026-07-10",
    effective_at: "2026-10-15",
    affected_flows: ["Nạp ví điện tử qua ngân hàng liên kết"],
    severity: "warning",
    summary: "Bổ sung ngưỡng báo cáo giao dịch đáng ngờ, ảnh hưởng luồng giám sát AML hiện tại.",
  },
  {
    id: "alert-03",
    title: "Công văn hướng dẫn áp dụng chuẩn kỹ thuật QR động",
    doc_type: "Công văn",
    published_at: "2026-06-30",
    effective_at: "2026-08-01",
    affected_flows: ["Thanh toán QR liên ngân hàng"],
    severity: "info",
    summary: "Cập nhật chuẩn kỹ thuật QR động theo VietQR 2.0 — không thay đổi nghiệp vụ.",
  },
];

function delay<T>(value: T, ms = 350): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export async function listDocuments(): Promise<AdminDocument[]> {
  return delay(readLocalStore(DOCS_KEY, SEED_DOCUMENTS));
}

export async function setDocumentStatus(
  id: string,
  status: AdminDocument["status"],
): Promise<AdminDocument[]> {
  const docs = readLocalStore(DOCS_KEY, SEED_DOCUMENTS).map((d) =>
    d.id === id ? { ...d, status } : d,
  );
  writeLocalStore(DOCS_KEY, docs);
  return delay(docs, 200);
}

export async function listAlerts(): Promise<RegulatoryAlert[]> {
  return delay(readLocalStore(ALERTS_KEY, SEED_ALERTS));
}
