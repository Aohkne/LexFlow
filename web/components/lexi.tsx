"use client";

// Lexi — linh vật trợ thủ AI. Hoạt ảnh nằm trong lexi.css (không nằm trong
// file .svg — SVGR/next/image có thể lược bỏ <style> bên trong svg).
// Bản tĩnh cho favicon/chip ≤20px: /public/lexi/*.svg.
import "./lexi.css";

export type LexiState =
  | "idle"
  | "greeting"
  | "searching"
  | "reading"
  | "found"
  | "conflict"
  | "error"
  | "static";

const C = {
  clay: "#CC785C",
  clayDeep: "#B4633E",
  clayDim: "#8F4A30",
  sage: "#5B7A5B",
  cream: "#FAF9F5",
  ink: "#26241F",
  beak: "#E0C39F",
  // trạng thái lỗi: xám "hết hiệu lực" + đỏ "vi phạm"
  drained: "#9C9686",
  drainedFace: "#F0EDE5",
  drainedBrow: "#6E6A5E",
  drainedBeak: "#D8CFBB",
  danger: "#A8412F",
  dangerWash: "#F7E6E1",
} as const;

const LABELS: Record<LexiState, string> = {
  idle: "Lexi",
  greeting: "Lexi xin chào",
  searching: "Lexi đang tra cứu",
  reading: "Lexi đang đọc văn bản",
  found: "Lexi đã tìm được nguồn",
  conflict: "Lexi phát hiện mâu thuẫn",
  error: "Lexi không tra được — đã xảy ra lỗi",
  static: "Lexi",
};

/** Đầu cú: hai túm tai + khối đầu + hai đĩa mặt. */
function Head({ fill }: { fill: string }) {
  return (
    <>
      <path d="M40 44 L44 22 L54 40 Z" fill={fill} />
      <path d="M80 44 L76 22 L66 40 Z" fill={fill} />
      <circle cx={60} cy={66} r={42} fill={fill} />
      <ellipse cx={44} cy={60} rx={20} ry={22} fill={C.cream} />
      <ellipse cx={76} cy={60} rx={20} ry={22} fill={C.cream} />
    </>
  );
}

/** Sách mở nâng ngang mỏ, dùng cho state "reading". */
function Book() {
  return (
    <>
      {/* bìa sách */}
      <path d="M60 90 Q40 84 20 90 L25 111 Q43 106 60 113 Z" fill={C.beak} />
      <path d="M60 90 Q80 84 100 90 L95 111 Q77 106 60 113 Z" fill={C.beak} />
      {/* hai trang */}
      <path d="M60 88 Q41 82 22 88 L26 108 Q43 103 60 110 Z" fill={C.cream} stroke={C.drainedBeak} strokeWidth={2} />
      <path d="M60 88 Q79 82 98 88 L94 108 Q77 103 60 110 Z" fill={C.cream} stroke={C.drainedBeak} strokeWidth={2} />
      <path d="M30 93 h18 M31 98 h14" stroke={C.drainedBeak} strokeWidth={1.8} strokeLinecap="round" />
      <path d="M72 93 h18 M75 98 h14" stroke={C.drainedBeak} strokeWidth={1.8} strokeLinecap="round" />
      <path d="M60 88 V110" stroke={C.drainedBeak} strokeWidth={2} />
    </>
  );
}

/** Cánh vẫy, dùng cho state "greeting". Cánh vẽ TRƯỚC Head (nếu không sẽ che mặt);
 *  phép nghiêng tĩnh 8° nằm trên <ellipse> vì CSS animation ghi đè transform của <g>;
 *  biên độ −8°…+16° là tối đa — vung mạnh hơn là đầu cánh bị cắt ở mép viewBox 120. */
function WavingWing() {
  return (
    <g className="lexi-wave">
      <ellipse cx={97} cy={74} rx={8.5} ry={17} fill={C.clayDeep} transform="rotate(8 97 91)" />
    </g>
  );
}

/** Một mắt mở, có vành và điểm sáng. `blink` bật hoạt ảnh chớp. */
function Eye({ cx, blink = false }: { cx: number; blink?: boolean }) {
  return (
    <g className={blink ? "lexi-blink" : undefined}>
      <circle cx={cx} cy={60} r={12.5} fill="none" stroke={C.clayDeep} strokeWidth={3} />
      <circle cx={cx} cy={60} r={9} fill={C.ink} />
      <circle cx={cx - 3.5} cy={56.5} r={2.8} fill={C.cream} />
    </g>
  );
}

export function Lexi({
  state = "idle",
  size = 40,
  label,
  decorative = true,
  className,
}: {
  state?: LexiState;
  size?: number;
  /** Ghi đè aria-label. Bỏ qua khi `decorative`. */
  label?: string;
  /** true (mặc định): aria-hidden, vì cạnh Lexi thường đã có chữ. */
  decorative?: boolean;
  className?: string;
}) {
  const a11y = decorative
    ? { "aria-hidden": true as const }
    : { role: "img", "aria-label": label ?? LABELS[state] };

  return (
    <svg
      className={className ? `lexi ${className}` : "lexi"}
      viewBox="0 0 120 120"
      width={size}
      height={size}
      {...a11y}
    >
      {state === "static" && (
        <>
          <circle cx={60} cy={60} r={52} fill={C.clay} />
          <ellipse cx={42} cy={56} rx={22} ry={24} fill={C.cream} />
          <ellipse cx={78} cy={56} rx={22} ry={24} fill={C.cream} />
          <circle cx={42} cy={56} r={11} fill={C.ink} />
          <circle cx={78} cy={56} r={11} fill={C.ink} />
          <circle cx={38} cy={52} r={3.2} fill={C.cream} />
          <circle cx={74} cy={52} r={3.2} fill={C.cream} />
          <path d="M60 68 L69 80 L60 88 L51 80 Z" fill={C.beak} />
        </>
      )}

      {state === "idle" && (
        <g className="lexi-sway">
          <Head fill={C.clay} />
          <Eye cx={44} blink />
          <Eye cx={76} blink />
          {/* chân mày cong lên — vẻ thân thiện */}
          <path d="M28 37 q13 -6 26 3" fill="none" stroke={C.clayDeep} strokeWidth={4.6} strokeLinecap="round" />
          <path d="M92 37 q-13 -6 -26 3" fill="none" stroke={C.clayDeep} strokeWidth={4.6} strokeLinecap="round" />
          <path d="M60 71 L68 82 L60 89 L52 82 Z" fill={C.beak} />
        </g>
      )}

      {state === "greeting" && (
        <>
          <WavingWing />
          <g className="lexi-hop">
            <Head fill={C.clay} />
            {/* mắt nheo cười + chân mày cong lên */}
            <path d="M34 63 q10 -13 20 0" fill="none" stroke={C.ink} strokeWidth={5} strokeLinecap="round" />
            <path d="M66 63 q10 -13 20 0" fill="none" stroke={C.ink} strokeWidth={5} strokeLinecap="round" />
            <path d="M28 37 q13 -6 26 3" fill="none" stroke={C.clayDeep} strokeWidth={4.6} strokeLinecap="round" />
            <path d="M92 37 q-13 -6 -26 3" fill="none" stroke={C.clayDeep} strokeWidth={4.6} strokeLinecap="round" />
            <path d="M60 71 L68 82 L60 89 L52 82 Z" fill={C.beak} />
          </g>
        </>
      )}

      {state === "reading" && (
        <>
          <Head fill={C.clay} />
          {/* mắt hạ xuống — đang nhìn vào trang sách */}
          <g className="lexi-read">
            <circle cx={44} cy={63} r={12.5} fill="none" stroke={C.clayDeep} strokeWidth={3} />
            <circle cx={44} cy={63} r={9} fill={C.ink} />
            <circle cx={76} cy={63} r={12.5} fill="none" stroke={C.clayDeep} strokeWidth={3} />
            <circle cx={76} cy={63} r={9} fill={C.ink} />
          </g>
          <rect x={26} y={40} width={27} height={4.6} rx={2.3} fill={C.clayDeep} />
          <rect x={67} y={40} width={27} height={4.6} rx={2.3} fill={C.clayDeep} />
          <path d="M60 72 L68 83 L60 90 L52 83 Z" fill={C.beak} />
          <Book />
        </>
      )}

      {state === "searching" && (
        <>
          <Head fill={C.clay} />
          <g className="lexi-search">
            <circle cx={44} cy={60} r={12.5} fill="none" stroke={C.clayDeep} strokeWidth={3} />
            <circle cx={44} cy={60} r={9} fill={C.ink} />
            <circle cx={76} cy={60} r={12.5} fill="none" stroke={C.clayDeep} strokeWidth={3} />
            <circle cx={76} cy={60} r={9} fill={C.ink} />
          </g>
          {/* chân mày phẳng — đang tập trung */}
          <rect x={26} y={40} width={27} height={4.6} rx={2.3} fill={C.clayDeep} />
          <rect x={67} y={40} width={27} height={4.6} rx={2.3} fill={C.clayDeep} />
          <path d="M60 71 L68 82 L60 89 L52 82 Z" fill={C.beak} />
        </>
      )}

      {state === "found" && (
        <>
          <g className="lexi-nod">
            <Head fill={C.sage} />
            {/* mắt nheo cười */}
            <path d="M34 63 q10 -13 20 0" fill="none" stroke={C.ink} strokeWidth={5} strokeLinecap="round" />
            <path d="M66 63 q10 -13 20 0" fill="none" stroke={C.ink} strokeWidth={5} strokeLinecap="round" />
            <path d="M60 71 L68 82 L60 89 L52 82 Z" fill={C.beak} />
          </g>
          <g className="lexi-pop">
            <circle cx={96} cy={30} r={17} fill="#EAF0E7" stroke={C.sage} strokeWidth={2.5} />
            <path d="M88 30 l6 6 l11 -12" fill="none" stroke={C.sage} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
          </g>
        </>
      )}

      {state === "error" && (
        <>
          <g className="lexi-droop">
            <Head fill={C.drained} />
            {/* đĩa mặt xám hơn, mắt thành hai gạch — hết cách */}
            <ellipse cx={44} cy={60} rx={20} ry={22} fill={C.drainedFace} />
            <ellipse cx={76} cy={60} rx={20} ry={22} fill={C.drainedFace} />
            <path d="M35 60 h18" fill="none" stroke={C.ink} strokeWidth={4.4} strokeLinecap="round" />
            <path d="M67 60 h18" fill="none" stroke={C.ink} strokeWidth={4.4} strokeLinecap="round" />
            <rect x={26} y={34} width={27} height={4.6} rx={2.3} fill={C.drainedBrow} />
            <rect x={67} y={34} width={27} height={4.6} rx={2.3} fill={C.drainedBrow} />
            <path d="M60 71 L68 82 L60 89 L52 82 Z" fill={C.drainedBeak} />
          </g>
          <g className="lexi-pop">
            <circle cx={97} cy={28} r={17} fill={C.dangerWash} stroke={C.danger} strokeWidth={2.5} />
            <path d="M91 22 L103 34" fill="none" stroke={C.danger} strokeWidth={4} strokeLinecap="round" />
            <path d="M103 22 L91 34" fill="none" stroke={C.danger} strokeWidth={4} strokeLinecap="round" />
          </g>
        </>
      )}

      {state === "conflict" && (
        <>
          <g className="lexi-shake">
            <Head fill={C.clayDeep} />
            <circle cx={44} cy={62} r={10} fill={C.ink} />
            <circle cx={76} cy={62} r={10} fill={C.ink} />
            {/* chân mày cau xuống */}
            <rect x={26} y={32} width={28} height={5} rx={2.5} fill={C.clayDim} transform="rotate(19 40 34)" />
            <rect x={66} y={32} width={28} height={5} rx={2.5} fill={C.clayDim} transform="rotate(-19 80 34)" />
            <path d="M60 73 L68 84 L60 91 L52 84 Z" fill={C.beak} />
          </g>
          <g className="lexi-pop">
            <circle cx={97} cy={28} r={17} fill="#F7EDE6" stroke={C.clay} strokeWidth={2.5} />
            <rect x={94.6} y={19} width={4.8} height={12} rx={2.4} fill={C.clay} />
            <circle cx={97} cy={35.5} r={2.8} fill={C.clay} />
          </g>
        </>
      )}
    </svg>
  );
}

/** Suy ra trạng thái từ luồng hỏi đáp. Dưới 24px thì truyền thẳng "static".
 *  "greeting" KHÔNG nằm ở đây — do sản phẩm chủ động chọn, không suy từ request. */
export function lexiState({
  isLoading,
  reading,
  hasError,
  hasConflict,
  hasAnswer,
}: {
  isLoading: boolean;
  /** tác vụ dài hàng chục giây (đối chiếu tài liệu) — thay searching bằng reading */
  reading?: boolean;
  hasError?: boolean;
  hasConflict: boolean;
  hasAnswer: boolean;
}): LexiState {
  if (isLoading) return reading ? "reading" : "searching";
  if (hasError) return "error";
  if (hasConflict) return "conflict";
  if (hasAnswer) return "found";
  return "idle";
}
