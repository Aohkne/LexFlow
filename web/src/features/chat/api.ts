import { ENDPOINTS } from "@/constant/endpoints";
import type { ChatRequest, ChatResponse } from "./types";

export async function postChat(body: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(ENDPOINTS.chat, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export const SAMPLE_QUESTIONS = [
  "Hạn mức giao dịch qua ví điện tử cá nhân hiện nay là bao nhiêu một tháng?",
  "Khách hàng có được nạp tiền mặt trực tiếp vào ví điện tử không?",
  "Nạp ví điện tử qua ngân hàng liên kết cần tuân thủ quy định gì?",
];
