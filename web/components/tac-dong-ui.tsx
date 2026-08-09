"use client";

// Đánh dấu đơn vị bị tác động trong toàn văn + bảng đối chiếu (handoff `giao_dien_dieu_khoan`,
// phương án 2a). Tách khỏi trang xem để phần dựng văn bản không lẫn với phần chú giải.
import Link from "next/link";
import { useEffect, useRef } from "react";
import { articleAnchor } from "@/lib/anchors";
import {
  idNeoNgan,
  nhanDiaChi,
  nhanTacDong,
  type DanhDau,
  type LoaiDanhDau,
} from "@/lib/tac-dong";

/** Lớp Tailwind theo loại tác động. Màu lấy từ token trong `globals.css`, không gõ mã màu. */
export const MAU: Record<
  LoaiDanhDau,
  { chu: string; vien: string; nenHuyHieu: string; highlight: string; vienPill: string }
> = {
  sua: {
    chu: "text-mark-sua",
    vien: "border-mark-sua",
    nenHuyHieu: "bg-mark-sua",
    // box-shadow cùng màu nền tạo khoảng đệm quang học mà không đẩy dòng — dùng padding thì
    // dòng chữ bị giãn ra khỏi nhịp của các đoạn xung quanh.
    highlight:
      "rounded-[2px] bg-mark-sua-bg shadow-[0_0_0_3px_var(--mark-sua-bg)] border-b-[1.5px] border-mark-sua",
    vienPill: "border-mark-sua text-mark-sua",
  },
  bai_bo: {
    chu: "text-mark-bai-bo",
    vien: "border-mark-bai-bo",
    nenHuyHieu: "bg-mark-bai-bo",
    highlight:
      "rounded-[2px] bg-mark-bai-bo-bg shadow-[0_0_0_3px_var(--mark-bai-bo-bg)] border-b-[1.5px] border-mark-bai-bo text-[#7a7266]",
    vienPill: "border-mark-bai-bo text-mark-bai-bo",
  },
  bo_sung: {
    chu: "text-mark-bo-sung",
    vien: "border-mark-bo-sung",
    nenHuyHieu: "bg-mark-bo-sung",
    highlight:
      "rounded-[2px] bg-mark-bo-sung-bg shadow-[0_0_0_3px_var(--mark-bo-sung-bg)] border-b-[1.5px] border-mark-bo-sung",
    vienPill: "border-mark-bo-sung text-mark-bo-sung",
  },
};

function ngayVN(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** Huy hiệu số ở lề trái — số thứ tự thay đổi trong văn bản. */
export function HuyHieuLe({ dd }: { dd: DanhDau }) {
  return (
    <span
      aria-hidden
      className={`absolute -left-9 top-[0.5em] flex h-5 w-5 items-center justify-center rounded-md text-[10.5px] font-semibold text-white ${MAU[dd.loai].nenHuyHieu}`}
    >
      {dd.stt}
    </span>
  );
}

/** Dòng gợi ý dưới đoạn: loại · văn bản tác động · hiệu lực. */
export function DongGoiY({ dd, thutLe }: { dd: DanhDau; thutLe: boolean }) {
  const t = dd.t;
  return (
    <span
      className={`mt-1.5 block text-[11px] ${MAU[dd.loai].chu} ${thutLe ? "pl-7" : ""}`}
    >
      {nhanTacDong(t)}
      {t.boi_doc_id ? ` · ${t.boi_doc_id}` : ""}
      {t.boi_article ? ` · ${t.boi_article}` : ""}
      {t.tu_ngay ? ` · từ ${ngayVN(t.tu_ngay)}` : ""} — bấm để đối chiếu
    </span>
  );
}

export function ModalDoiChieu({
  dd,
  vanBanGoc,
  soHieuDangDoc,
  tenVanBanTacDong,
  viTri,
  tong,
  onTruoc,
  onTiep,
  onDong,
}: {
  dd: DanhDau;
  /** Nguyên văn đơn vị trong văn bản đang đọc; null khi đơn vị chưa từng có trong bản gốc. */
  vanBanGoc: string | null;
  soHieuDangDoc: string;
  tenVanBanTacDong: string | null;
  viTri: number;
  tong: number;
  onTruoc: () => void;
  onTiep: () => void;
  onDong: () => void;
}) {
  const t = dd.t;
  const mau = MAU[dd.loai];
  const hop = useRef<HTMLDivElement>(null);

  // Esc đóng, và đưa tiêu điểm vào hộp thoại để bàn phím không lạc lại trang nền.
  useEffect(() => {
    hop.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDong();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDong]);

  const neoDoc = t.boi_doc_id
    ? `/docs/${encodeURIComponent(t.boi_doc_id)}${
        t.boi_article && articleAnchor(t.boi_article) ? `#${articleAnchor(t.boi_article)}` : ""
      }`
    : null;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-[rgba(32,27,20,.42)] p-4 backdrop-blur-[2px]"
      onClick={onDong}
      role="presentation"
    >
      <div
        ref={hop}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`Đối chiếu ${nhanDiaChi(t)}`}
        onClick={(e) => e.stopPropagation()}
        className="fadeup flex max-h-[min(760px,calc(100vh-2rem))] w-[1000px] max-w-full flex-col overflow-hidden rounded-2xl border border-border bg-panel shadow-[0_30px_70px_rgba(30,24,16,.34)] outline-none"
      >
        {/* Thanh tiêu đề */}
        <div className="flex flex-none flex-wrap items-center gap-2.5 border-b border-border bg-sidebar px-5 py-3.5">
          <span
            className={`rounded-full border px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-[.04em] ${mau.vienPill}`}
          >
            {nhanTacDong(t)}
          </span>
          <span className="mono text-[13.5px] text-fg-body">{nhanDiaChi(t)}</span>
          <span className="mono ml-auto text-[11.5px] text-faint">
            hiệu lực từ {ngayVN(t.tu_ngay)}
          </span>
          <button
            onClick={onDong}
            aria-label="Đóng"
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-border bg-background text-[14px] text-dim transition-colors hover:text-foreground"
          >
            ✕
          </button>
        </div>

        {/* Thân cuộn */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="grid gap-px bg-border lg:grid-cols-2">
            <section className="bg-panel px-5 py-4">
              <div className="flex items-baseline gap-2">
                <span className="text-[9.5px] font-semibold uppercase tracking-[.1em] text-faint">
                  Điều luật gốc
                </span>
                <span className="mono text-[10.5px] text-muted">{soHieuDangDoc}</span>
              </div>
              <p className="serif mt-0.5 text-[13px] italic text-faint">{nhanDiaChi(t)}</p>
              {vanBanGoc ? (
                <p
                  className={`serif mt-3 whitespace-pre-line text-justify text-[14.5px] leading-[1.72] ${
                    dd.loai === "bai_bo"
                      ? "text-muted line-through decoration-mark-gach"
                      : "text-fg-body"
                  }`}
                >
                  {vanBanGoc}
                </p>
              ) : (
                // Không có chữ là chuyện CÓ THẬT và có hai lý do khác nhau — nói đúng lý do thay
                // vì để trống hay dựng một chuỗi rỗng cho đủ bố cục.
                <p className="mt-3 rounded-lg border border-border bg-inset px-3 py-2.5 text-[12.5px] leading-relaxed text-dim">
                  {t.thao_tac === "bo_sung"
                    ? "Đơn vị này chưa có trong bản gốc — nó được văn bản bên cạnh bổ sung thêm."
                    : "Không tìm thấy nguyên văn đơn vị này trong bản đã cào của văn bản gốc."}
                </p>
              )}
            </section>

            <section className="bg-accent-wash px-5 py-4">
              <div className="flex items-baseline gap-2">
                <span className="text-[9.5px] font-semibold uppercase tracking-[.1em] text-mark-sua">
                  Điều luật tác động
                </span>
                <span className="mono text-[10.5px] text-accent-dim">{t.boi_doc_id ?? "—"}</span>
              </div>
              <p className="serif mt-0.5 text-[13px] italic text-accent-dim">
                {[t.boi_article, tenVanBanTacDong].filter(Boolean).join(" — ") || "—"}
              </p>
              {t.menh_lenh ? (
                <p className="serif mt-3 whitespace-pre-line text-justify text-[14.5px] leading-[1.72] text-fg-body">
                  {t.menh_lenh}
                </p>
              ) : (
                <p className="mt-3 text-[12.5px] text-dim">Không có câu lệnh nguyên văn.</p>
              )}
            </section>
          </div>

          {/* Lời văn mới. Bãi bỏ thì KHÔNG có khối này — không có gì thay thế cả. */}
          {t.loi_van_moi && (
            <div className="border-t border-border px-5 pb-5 pt-4">
              <div className="flex items-center gap-2.5">
                <span className="text-[9.5px] font-semibold uppercase tracking-[.1em] text-mark-bo-sung">
                  Lời văn mới
                </span>
                <span className="h-px flex-1 bg-border" />
              </div>
              <p className="serif mt-2.5 whitespace-pre-line border-l-2 border-mark-bo-sung pl-3.5 text-justify text-[15px] leading-[1.72] text-fg-body">
                {t.loi_van_moi}
              </p>
            </div>
          )}

          {/* Dải metadata */}
          <div className="grid grid-cols-2 gap-px border-t border-border bg-border lg:grid-cols-4">
            {(
              [
                ["Loại tác động", nhanTacDong(t)],
                ["Văn bản tác động", t.boi_doc_id ?? "—"],
                ["Hiệu lực từ", ngayVN(t.tu_ngay)],
                ["Địa chỉ neo", idNeoNgan(t)],
              ] as const
            ).map(([nhan, giaTri]) => (
              <div key={nhan} className="bg-sidebar px-4 py-2.5">
                <div className="text-[10px] text-faint">{nhan}</div>
                <div className="mono mt-0.5 text-[11.5px] text-fg-body">{giaTri}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Chân */}
        <div className="flex flex-none flex-wrap items-center gap-2.5 border-t border-border bg-sidebar px-5 py-3">
          <button
            onClick={onTruoc}
            disabled={tong < 2}
            className="rounded-lg border border-border bg-background px-3 py-1.5 text-[12px] text-fg-body transition-colors hover:bg-inset-strong disabled:opacity-40"
          >
            ↑ Thay đổi trước
          </button>
          <button
            onClick={onTiep}
            disabled={tong < 2}
            className="rounded-lg border border-border bg-background px-3 py-1.5 text-[12px] text-fg-body transition-colors hover:bg-inset-strong disabled:opacity-40"
          >
            Thay đổi tiếp ↓
          </button>
          <span className="mono text-[11px] text-faint">
            {viTri} / {tong}
          </span>
          <span className="flex-1" />
          {neoDoc && (
            <Link
              href={neoDoc}
              className="rounded-lg bg-accent px-3.5 py-1.5 text-[12px] font-medium text-white transition-colors hover:bg-accent-hover"
            >
              Mở toàn văn {t.boi_doc_id} ↗
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
