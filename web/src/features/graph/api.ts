import { ENDPOINTS } from "@/constant/endpoints";
import type { GraphData } from "./types";

export async function getGraph(): Promise<GraphData> {
  const res = await fetch(ENDPOINTS.graph);
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export const DOC_TYPE_COLOR: Record<string, string> = {
  "Luật": "#8f4a30",
  "Nghị định": "#3d6a9e",
  "Thông tư": "#b85c3a",
  "Quyết định": "#9c7a2c",
  "Nội bộ": "#4c7a4f",
};

export const REL_LABEL: Record<string, string> = {
  THAY_THE: "thay thế",
  SUA_DOI: "sửa đổi",
  HUONG_DAN: "hướng dẫn",
  DAN_CHIEU: "dẫn chiếu",
};
