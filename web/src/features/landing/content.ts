export type PainpointSolution = {
  index: string;
  painpoint: string;
  solution: string;
  description: string;
  icon: string;
  href: string | null;
  tags: string[];
};

// Rút gọn từ docs/SPEC.html — lát cắt payment-integration.
export const PAINPOINT_SOLUTIONS: PainpointSolution[] = [
  {
    index: "01",
    painpoint:
      "PM/dev cần biết một luồng thanh toán phải tuân thủ quy định gì thì phải chờ pháp chế trả lời vài ngày, hoặc tự đọc PDF và đoán xem văn bản còn hiệu lực hay không.",
    solution: "Chatbot hỏi-đáp có trích dẫn nguồn",
    description:
      "Trả lời câu hỏi tự nhiên, trích đúng điều/khoản đang hiệu lực. Có chế độ checklist cho cả một luồng nghiệp vụ.",
    icon: "ph:chats-circle-fill",
    href: "/chat",
    tags: ["pháp chế", "dev / PM"],
  },
  {
    index: "02",
    painpoint:
      "Khi cần audit hoặc giải trình với thanh tra NHNN, pháp chế không có cách nào nhanh để thấy một quy định nằm ở đâu trong toàn bộ hệ thống văn bản.",
    solution: "Đồ thị tri thức trực quan",
    description:
      "Vị trí văn bản trong phân cấp Luật → Nghị định → Thông tư → Quyết định, cùng quan hệ thay thế / sửa đổi / dẫn chiếu.",
    icon: "ph:graph-fill",
    href: "/graph",
    tags: ["pháp chế"],
  },
  {
    index: "03",
    painpoint:
      "Tài liệu nguồn hiện được upload lên thư mục dùng chung, không ai kiểm duyệt hiệu lực trước khi dùng — AI có thể học nhầm văn bản đã hết hiệu lực.",
    solution: "Admin dashboard",
    description:
      "Cổng kiểm soát chất lượng dữ liệu đầu vào — thêm và duyệt văn bản mới trước khi hệ thống được phép dùng làm nguồn trả lời.",
    icon: "ph:shield-check-fill",
    href: "/admin",
    tags: ["vận hành pháp chế"],
  },
  {
    index: "04",
    painpoint:
      "Sau khi luồng thanh toán đã lên production, không có cách nào biết quy định đổi ngoài tình cờ đọc báo hoặc chờ công văn NHNN gửi tay.",
    solution: "Cảnh báo thay đổi quy định",
    description:
      "Thông báo chủ động khi có văn bản mới hoặc sắp đến mốc hiệu lực liên quan trực tiếp đến một luồng đang vận hành.",
    icon: "ph:bell-ringing-fill",
    href: "/admin/alerts",
    tags: ["pháp chế", "dev lead"],
  },
  {
    index: "05",
    painpoint:
      "Cần chứng minh kiến trúc RAG + Knowledge Graph + Versioning thực sự trả lời đúng hơn một RAG vector thông thường — không có con số thì không có lý do để tin.",
    solution: "Benchmark Suite",
    description:
      "Bộ câu hỏi kiểm thử đo độ chính xác trích dẫn và tỷ lệ phát hiện xung đột, so sánh trực tiếp với RAG vector thuần túy.",
    icon: "ph:chart-bar-fill",
    href: null,
    tags: ["đội phát triển"],
  },
];
