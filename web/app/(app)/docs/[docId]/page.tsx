"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PageShell from "@/components/page-shell";
import {
  downloadSourceFile,
  getDocument,
  type DocumentDetail,
  type Provision,
  type SourceFile,
  type TacDongDonVi,
} from "@/lib/api";
import { renderInline } from "@/lib/inline-html";
import {
  articleAnchor,
  bacTuTienTo,
  buildAmendmentMap,
  groupRelationships,
  khoaDiaChi,
  neoDieu,
  tachDoan,
  type AmendmentInfo,
  type DiaChiDonVi,
} from "@/lib/anchors";
import {
  dongPhang,
  mucLucTuCay,
  mucLucTuDongPhang,
  neoChuong,
  neoMuc,
  phangMucLuc,
  type DongPhang,
  type MucMucLuc,
} from "@/lib/muc-luc";

// ——— Chế độ đọc ————————————————————————————————————————————————————————————————
// Người tra luật ngồi với một văn bản hàng giờ, và mỗi người một cỡ chữ. Ba thứ chỉnh được:
// cỡ chữ, bề rộng cột, và có đặt cột chữ lên một "trang giấy" nổi hay không.
const KHOA_CAI_DAT = "lexflow:doc-doc";

type CaiDatDoc = {
  co: number; // px, cỡ gốc của thân văn bản — mọi cỡ khác tính theo em nên co giãn cùng
  rong: number; // rem, bề rộng tối đa của cột chữ
  giay: boolean;
};

const MAC_DINH: CaiDatDoc = { co: 16, rong: 48, giay: false };
const CO_MIN = 14;
const CO_MAX = 22;
const BE_RONG: [nhan: string, rem: number][] = [
  ["Hẹp", 38],
  ["Vừa", 48],
  ["Rộng", 62],
];

function docCaiDat(): CaiDatDoc {
  if (typeof window === "undefined") return MAC_DINH;
  try {
    const s = window.localStorage.getItem(KHOA_CAI_DAT);
    // Trộn với mặc định: bản lưu từ phiên trước có thể thiếu khoá mới thêm.
    return s ? { ...MAC_DINH, ...(JSON.parse(s) as Partial<CaiDatDoc>) } : MAC_DINH;
  } catch {
    return MAC_DINH; // localStorage bị chặn (chế độ riêng tư, cookie tắt) thì đọc vẫn chạy
  }
}

/**
 * Mốc đang đọc, tính từ vị trí thật của các neo trên màn hình.
 *
 * Vùng cuộn là thẻ `<main>` chứ không phải cửa sổ (`components/page-shell.tsx`), mà sự kiện
 * `scroll` của một phần tử KHÔNG nổi bọt lên window — nghe `window.scroll` kiểu thường sẽ không
 * bao giờ nhận được gì. Bắt ở pha capture thì window vẫn thấy.
 *
 * Dùng `getBoundingClientRect` thay cho IntersectionObserver vì một Điều dài có thể phủ kín màn
 * hình: lúc đó không neo nào "đang giao nhau" và observer trả về rỗng, còn phép so mốc vẫn chỉ
 * đúng Điều đang đọc.
 */
function useDangDoc(neos: string[]): string | null {
  const [dang, setDang] = useState<string | null>(null);

  useEffect(() => {
    if (neos.length === 0) {
      return;
    }
    let rafId = 0;
    const tinh = () => {
      rafId = 0;
      // Mốc đặt ngay dưới thanh định vị: mốc cuối cùng còn nằm trên nó là mốc đang đọc.
      const MOC = 128;
      let hien = neos[0];
      for (const id of neos) {
        const el = document.getElementById(id);
        if (!el) continue;
        if (el.getBoundingClientRect().top > MOC) break;
        hien = id;
      }
      setDang(hien);
    };
    const hen = () => {
      if (!rafId) rafId = requestAnimationFrame(tinh);
    };
    // Không gọi tinh() thẳng trong thân effect: đặt state đồng bộ ở đó là thứ
    // `react-hooks/set-state-in-effect` cấm. Hẹn qua rAF vừa tránh luật vừa đo sau khi đã layout.
    hen();
    window.addEventListener("scroll", hen, { capture: true, passive: true });
    window.addEventListener("resize", hen, { passive: true });
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      window.removeEventListener("scroll", hen, { capture: true });
      window.removeEventListener("resize", hen);
    };
  }, [neos]);

  return dang;
}

export default function DocViewerPage() {
  const params = useParams<{ docId: string }>();
  const docId = decodeURIComponent(params.docId);
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"content" | "properties" | "schema">("content");
  const [mucLucMo, setMucLucMo] = useState(false);
  const [chinhMo, setChinhMo] = useState(false);
  // Khởi tạo lười, đọc đúng nguồn mà mọi lần đọc sau này dùng. Nhánh đang tải không phụ thuộc
  // giá trị này nên lúc hydrate DOM không lệch, dù server luôn dựng bằng mặc định.
  const [caiDat, setCaiDat] = useState<CaiDatDoc>(docCaiDat);

  const doiCaiDat = useCallback((phan: Partial<CaiDatDoc>) => {
    setCaiDat((cu) => {
      const moi = { ...cu, ...phan };
      try {
        window.localStorage.setItem(KHOA_CAI_DAT, JSON.stringify(moi));
      } catch {
        // Không lưu được thì vẫn đổi cho phiên này, không chặn thao tác.
      }
      return moi;
    });
  }, []);

  useEffect(() => {
    getDocument(docId)
      .then(setDoc)
      .catch((e) => setError(e instanceof Error ? e.message : "Lỗi tải văn bản"));
  }, [docId]);

  // Đường phẳng và mục lục dựng một lần: cả trang render, mục lục lẫn thanh định vị đều đọc từ đây.
  const dong: DongPhang[] = useMemo(() => (doc ? dongPhang(doc.articles) : []), [doc]);
  const mucLuc: MucMucLuc[] = useMemo(
    () =>
      doc && doc.provisions && doc.provisions.length > 0
        ? mucLucTuCay(doc.provisions)
        : mucLucTuDongPhang(dong),
    [doc, dong],
  );
  const neoTheoThuTu = useMemo(() => phangMucLuc(mucLuc), [mucLuc]);
  const dsNeo = useMemo(
    () => (tab === "content" ? neoTheoThuTu.map((n) => n.anchor) : []),
    [neoTheoThuTu, tab],
  );
  const dangDoc = useDangDoc(dsNeo);
  const mocDangDoc = neoTheoThuTu.find((n) => n.anchor === dangDoc) ?? null;

  const nhay = useCallback((anchor: string) => {
    const el = document.getElementById(anchor);
    if (!el) return;
    el.scrollIntoView({ block: "start", behavior: "smooth" });
    // Đổi hash mà không đẩy thêm một mục vào lịch sử — bấm Back vẫn về trang trước, không phải
    // lần lượt lùi qua từng Điều vừa xem.
    window.history.replaceState(null, "", `#${anchor}`);
    setMucLucMo(false);
  }, []);

  // Cuộn tới #dieu-N sau khi nội dung render.
  useEffect(() => {
    if (!doc || tab !== "content") return;
    const hash = window.location.hash.slice(1);
    if (hash) document.getElementById(hash)?.scrollIntoView({ block: "start" });
  }, [doc, tab]);

  // Bấm ra ngoài thì đóng bảng chỉnh.
  //
  // Bắt ở document chứ không dựng một lớp phủ `fixed inset-0`: thanh định vị có `backdrop-blur`,
  // mà backdrop-filter tạo containing block cho con `position: fixed` — lớp phủ đặt trong đó chỉ
  // phủ đúng cái thanh chứ không phủ trang. Vùng tham chiếu là cả cụm nút + bảng, nếu chỉ tính
  // riêng bảng thì cú bấm lên chính nút "Aa" vừa đóng (mousedown) vừa mở lại (click).
  const hopChinh = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!chinhMo) return;
    const onDown = (e: MouseEvent) => {
      if (!hopChinh.current?.contains(e.target as Node)) setChinhMo(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [chinhMo]);

  // Esc đóng lớp phủ đang mở — ngăn kéo trước, rồi mới tới bảng chỉnh.
  useEffect(() => {
    if (!mucLucMo && !chinhMo) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (mucLucMo) setMucLucMo(false);
      else setChinhMo(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mucLucMo, chinhMo]);

  if (error) {
    return (
      <PageShell active="docs">
        <div className="mx-auto max-w-3xl px-6 py-10">
          <div className="rounded-lg border border-red-bd bg-red-bg px-4 py-3 text-sm text-red">{error}</div>
        </div>
      </PageShell>
    );
  }
  if (!doc) {
    return (
      <PageShell active="docs">
        <div className="mx-auto max-w-3xl px-6 py-10 text-sm text-faint">Đang tải…</div>
      </PageShell>
    );
  }

  const amendments = buildAmendmentMap(doc);
  const replacedBy = doc.relationships_in.filter((r) => r.rel_type === "THAY_THE");
  const expired =
    replacedBy.length > 0 || (doc.valid_to !== null && doc.valid_to <= new Date().toISOString().slice(0, 10));

  return (
    <PageShell active="docs">
    {mucLucMo && (
      <NganKeoMucLuc
        mucLuc={mucLuc}
        dangDoc={dangDoc}
        onChon={nhay}
        onDong={() => setMucLucMo(false)}
      />
    )}
    <div className="mx-auto px-6 py-10" style={{ maxWidth: `${caiDat.rong}rem` }}>
      <Link href="/docs" className="text-xs text-dim hover:text-accent-dim">
        ← Thư viện văn bản
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="rounded bg-inset px-2 py-0.5 text-xs text-dim">{doc.doc_type}</span>
        <span className="mono text-xs text-accent-dim">{doc.doc_id}</span>
        <span className="mono ml-auto text-xs text-faint">
          hiệu lực từ {doc.valid_from ?? "—"}
          {doc.valid_to ? ` đến ${doc.valid_to}` : ""}
        </span>
      </div>
      <h1 className="mt-1 text-xl font-semibold leading-snug">{doc.title}</h1>

      {expired && (
        <div className="mt-4 rounded-lg border-l-4 border-red bg-panel px-4 py-3 text-sm">
          <span className="font-semibold text-red">⚠ Văn bản đã hết hiệu lực</span>
          {replacedBy.map((r) => (
            <span key={r.source_doc} className="text-foreground">
              {" "}
              — được thay thế bởi{" "}
              <Link
                href={`/docs/${encodeURIComponent(r.source_doc)}`}
                className="font-medium text-accent-dim underline decoration-dotted hover:text-accent"
              >
                {doc.doc_titles[r.source_doc] ?? r.source_doc}
              </Link>
              {r.valid_from ? ` (từ ${r.valid_from})` : ""}
            </span>
          ))}
        </div>
      )}

      {/* Thanh định vị — dính lại khi cuộn.
          Ba tab trước đây nằm chết ở đỉnh trang: cuộn tới Điều 30 là mất hút, muốn xem Lược đồ
          phải cuộn ngược hết lên. Kéo chúng vào thanh dính thì vừa giữ được đường ra, vừa có
          chỗ đặt đường dẫn Chương › Mục › Điều đang đọc.
          `top-0` bám theo vùng cuộn gần nhất, chính là thẻ <main> của PageShell. */}
      <div className="sticky top-0 z-30 -mx-6 mt-6 border-b border-border bg-background/90 px-6 py-2 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-border bg-background p-0.5 text-sm">
            {(
              [
                ["content", "Nội dung"],
                ["properties", "Thuộc tính"],
                ["schema", "Lược đồ"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`rounded-md px-3 py-1 transition-colors ${
                  tab === key ? "bg-accent text-white" : "text-dim hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "content" && (
            <div className="ml-auto flex items-center gap-2">
              {mucLuc.length > 0 && (
                <button
                  onClick={() => setMucLucMo(true)}
                  className="rounded-lg border border-border px-2.5 py-1 text-[12.5px] text-dim transition-colors hover:border-border-hover hover:text-foreground"
                  aria-haspopup="dialog"
                >
                  ☰ Mục lục
                </button>
              )}
              <div className="relative" ref={hopChinh}>
                <button
                  onClick={() => setChinhMo((v) => !v)}
                  aria-expanded={chinhMo}
                  className={`rounded-lg border px-2.5 py-1 text-[12.5px] transition-colors ${
                    chinhMo
                      ? "border-accent text-accent-dim"
                      : "border-border text-dim hover:border-border-hover hover:text-foreground"
                  }`}
                >
                  <span className="serif">Aa</span>
                </button>
                {chinhMo && <BangChinhDoc caiDat={caiDat} onDoi={doiCaiDat} />}
              </div>
            </div>
          )}
        </div>

        {/* Đường dẫn chỉ hiện khi đã cuộn vào phần thân — ở đầu trang nó chỉ lặp lại tiêu đề. */}
        {tab === "content" && mocDangDoc && (
          <nav aria-label="Vị trí trong văn bản" className="mt-1.5 truncate text-[12px] text-dim">
            {mocDangDoc.duongDan.map((b) => (
              <span key={b}>
                {b} <span className="text-muted">›</span>{" "}
              </span>
            ))}
            <span className="font-medium text-foreground">{mocDangDoc.nhan}</span>
            {mocDangDoc.tieuDe && <span>. {mocDangDoc.tieuDe}</span>}
          </nav>
        )}
      </div>

      {/* Cỡ chữ đặt ở đây một lần; mọi cấp bên trong tính theo em nên co giãn cùng nhau. */}
      <div
        style={{ fontSize: `${caiDat.co}px` }}
        className={
          caiDat.giay
            ? "mt-8 rounded-xl border border-border bg-panel px-7 py-6 shadow-[0_1px_4px_rgba(0,0,0,.04)]"
            : "mt-8"
        }
      >
        {tab === "content" && <ContentTab doc={doc} amendments={amendments} dong={dong} />}
        {tab === "properties" && <PropertiesTab doc={doc} />}
        {tab === "schema" && <SchemaTab doc={doc} />}
      </div>
    </div>
    </PageShell>
  );
}

/** Ngăn kéo mục lục. Mở ra khi cần, chọn xong đóng lại — không chiếm chiều ngang lúc đọc. */
function NganKeoMucLuc({
  mucLuc,
  dangDoc,
  onChon,
  onDong,
}: {
  mucLuc: MucMucLuc[];
  dangDoc: string | null;
  onChon: (anchor: string) => void;
  onDong: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label="Mục lục">
      <button className="absolute inset-0 bg-black/25" onClick={onDong} aria-label="Đóng mục lục" />
      <aside className="relative z-10 flex h-full w-[min(23rem,86vw)] flex-col border-r border-border bg-panel shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">Mục lục</h2>
          <button
            onClick={onDong}
            className="rounded-md px-2 py-0.5 text-lg leading-none text-dim transition-colors hover:text-foreground"
            aria-label="Đóng"
          >
            ×
          </button>
        </div>
        <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          <CayMucLuc nodes={mucLuc} dangDoc={dangDoc} onChon={onChon} />
        </nav>
      </aside>
    </div>
  );
}

function CayMucLuc({
  nodes,
  dangDoc,
  onChon,
  bac = 0,
}: {
  nodes: MucMucLuc[];
  dangDoc: string | null;
  onChon: (anchor: string) => void;
  bac?: number;
}) {
  return (
    <ul>
      {nodes.map((n) => {
        const dang = n.anchor === dangDoc;
        const dam = n.cap === "chuong";
        return (
          <li key={n.anchor}>
            {/* Thẻ <a> thật với href="#…" để bấm giữa/chuột phải vẫn mở được như một liên kết;
                onClick chặn mặc định để cuộn mượt và đóng ngăn kéo. */}
            <a
              href={`#${n.anchor}`}
              onClick={(e) => {
                e.preventDefault();
                onChon(n.anchor);
              }}
              style={{ paddingLeft: `${0.5 + bac * 0.75}rem` }}
              className={`block rounded-md py-1 pr-2 text-[12.5px] leading-snug transition-colors ${
                dang ? "bg-accent-wash text-accent-dim" : "text-dim hover:bg-inset hover:text-foreground"
              } ${dam ? "mt-2 font-semibold uppercase tracking-wide" : ""}`}
            >
              <span className={dam ? "" : "font-medium"}>{n.nhan}</span>
              {n.tieuDe && <span className="font-normal">. {n.tieuDe}</span>}
            </a>
            {n.con.length > 0 && (
              <CayMucLuc nodes={n.con} dangDoc={dangDoc} onChon={onChon} bac={bac + 1} />
            )}
          </li>
        );
      })}
    </ul>
  );
}

function BangChinhDoc({
  caiDat,
  onDoi,
}: {
  caiDat: CaiDatDoc;
  onDoi: (phan: Partial<CaiDatDoc>) => void;
}) {
  return (
      <div className="absolute right-0 top-full z-50 mt-1.5 w-60 rounded-xl border border-border bg-panel p-3 shadow-lg">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-dim">Cỡ chữ</span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onDoi({ co: Math.max(CO_MIN, caiDat.co - 1) })}
              disabled={caiDat.co <= CO_MIN}
              className="h-6 w-6 rounded-md border border-border text-[13px] text-dim transition-colors hover:text-foreground disabled:opacity-40"
              aria-label="Giảm cỡ chữ"
            >
              −
            </button>
            <span className="mono w-8 text-center text-[11.5px] text-faint">{caiDat.co}</span>
            <button
              onClick={() => onDoi({ co: Math.min(CO_MAX, caiDat.co + 1) })}
              disabled={caiDat.co >= CO_MAX}
              className="h-6 w-6 rounded-md border border-border text-[13px] text-dim transition-colors hover:text-foreground disabled:opacity-40"
              aria-label="Tăng cỡ chữ"
            >
              +
            </button>
          </div>
        </div>

        <div className="mt-3">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-dim">Bề rộng cột</span>
          <div className="mt-1.5 flex gap-1">
            {BE_RONG.map(([nhan, rem]) => (
              <button
                key={rem}
                onClick={() => onDoi({ rong: rem })}
                className={`flex-1 rounded-md border py-1 text-[12px] transition-colors ${
                  caiDat.rong === rem
                    ? "border-accent bg-accent-wash text-accent-dim"
                    : "border-border text-dim hover:text-foreground"
                }`}
              >
                {nhan}
              </button>
            ))}
          </div>
        </div>

        <label className="mt-3 flex cursor-pointer items-center gap-2 text-[12.5px] text-dim">
          <input
            type="checkbox"
            checked={caiDat.giay}
            onChange={(e) => onDoi({ giay: e.target.checked })}
            className="accent-[var(--accent)]"
          />
          Đặt lên trang giấy
        </label>
      </div>
  );
}

const AMEND_LABELS: Record<string, string> = {
  sua_doi_bo_sung: "Sửa đổi, bổ sung",
  thay_the: "Thay thế",
  bo_sung: "Bổ sung",
  bai_bo: "Bãi bỏ",
  het_hieu_luc: "Hết hiệu lực",
};

function AmendBadge({ kind }: { kind: string }) {
  const danger = kind === "thay_the" || kind === "bai_bo" || kind === "het_hieu_luc";
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[11px] ${
        danger ? "border border-red text-red" : "border border-accent text-accent-dim"
      }`}
    >
      {/* nhãn lạ từ nguồn (khac:...) vẫn hiện nguyên văn thay vì bị nuốt */}
      {AMEND_LABELS[kind] ?? kind.replace(/^khac:/, "")}
    </span>
  );
}

/** Tác động cấp khoản/điểm của một Điều — dùng chung cho cả đường cây lẫn đường danh sách phẳng.
 *
 * Hai đường render phải nói CÙNG một thứ: văn bản đã crawl lại (có `provisions`) đi đường cây,
 * văn bản cũ đi đường phẳng, nhưng trạng thái hiệu lực cấp khoản là dữ liệu của lớp phủ chứ
 * không phải của đường render. Tách ra đây để không có đường nào lặng lẽ thiếu nó. */
function TacDongDieu({ muc }: { muc: TacDongDonVi[] }) {
  if (muc.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1">
      {muc.map((t, i) => (
        <li key={i} className="text-[11.5px] text-dim">
          <span className={t.trang_thai === "bi_bai_bo" ? "text-red" : "text-accent-dim"}>
            {t.khoan ? `Khoản ${t.khoan}` : "Cả điều"}
            {t.diem ? ` Điểm ${t.diem}` : ""} —{" "}
            {t.trang_thai === "bi_bai_bo" ? "đã bị bãi bỏ" : "đã bị sửa đổi"}
          </span>
          {t.boi_doc_id ? ` bởi ${t.boi_doc_id} ${t.boi_article ?? ""}` : ""}
          {t.tu_ngay ? ` (từ ${t.tu_ngay})` : ""}
        </li>
      ))}
    </ul>
  );
}

// Thân văn bản: serif, giãn dòng rộng, canh đều hai bên và thụt đầu dòng — đúng cách một văn bản
// quy phạm được in ra. Gom lại một chỗ để mọi cấp nói cùng một giọng.
//
// KHÔNG ghim cỡ chữ ở đây nữa: cỡ do chế độ đọc đặt trên khối bao ngoài, thân văn bản thừa kế,
// còn các tiêu đề tính theo `em` nên cả trang phóng to thu nhỏ cùng một nhịp. `leading-[1.75]`
// là số không đơn vị nên cũng giãn theo cỡ chữ.
const THAN = "serif indent-7 text-justify leading-[1.75] text-fg-body";

/** Một đoạn đã tách khỏi nút, kèm bậc hiển thị và địa chỉ của chính nó. */
type Doan = {
  html: string;
  cap: "dieu" | "khoan" | "diem";
  dc: DiaChiDonVi | null;
};

/**
 * Bẻ phần nội dung của một nút thành các đoạn có địa chỉ riêng.
 *
 * Bậc của MỌI đoạn đều đọc từ chính tiền tố nguồn đã viết, không suy từ vị trí trong cây. Lý do
 * nằm ở dữ liệu thật: nút cấp `dieu` của Nghị định 80/2016 đang ôm nguyên một khối trích dẫn
 * `"4. Tổ chức… :<br>a) …<br>b) …"`. Nếu tin vào cấp của nút thì cả khối đó đổ ra thành một
 * đoạn phẳng, mất sạch bậc khoản/điểm. Đoạn nào không có tiền tố thì mới lấy cấp của nút — đó
 * đúng là các đoạn nối tiếp và đoạn dẫn.
 *
 * Đây là phép đọc lúc HIỂN THỊ, không phải đánh số lại: chữ và số giữ nguyên như nguồn trả, nên
 * khối trích dẫn vẫn mang đánh số của văn bản BỊ SỬA như nó vốn có.
 */
function beDoan(html: string, capNut: Doan["cap"], goc: DiaChiDonVi | null): Doan[] {
  let khoan = goc?.khoan ?? null;
  return tachDoan(html).map((doan) => {
    const bac = bacTuTienTo(doan);
    if (bac.cap === "khoan") khoan = bac.so;
    const cap = bac.cap ?? capNut;
    let dc = goc;
    if (goc && bac.cap === "khoan") dc = { article: goc.article, khoan: bac.so, diem: null };
    else if (goc && bac.cap === "diem") dc = { article: goc.article, khoan, diem: bac.so };
    return { html: doan, cap, dc };
  });
}

/**
 * Một đoạn thân văn bản.
 *
 * `data-dia-chi` là điểm móc để sau này gắn việc đánh dấu đơn vị bị tác động: giá trị của nó
 * chính là `khoaDiaChi()` dựng từ `TacDongDonVi`, nên tính năng đó chỉ cần lập bảng từ
 * `doc.tac_dong` rồi tra, không phải dò lại chuỗi. Cố ý dùng `data-` chứ không phải `id`: một
 * đơn vị có thể xuất hiện nhiều lần trên trang (bản gốc và bản trong khối trích dẫn), mà `id`
 * trùng là HTML sai còn `data-` thì `querySelectorAll` gom được cả cụm — đúng thứ việc đánh dấu
 * cần.
 */
function DoanThan({
  doan,
  children,
  className = "",
}: {
  doan: Doan;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      data-dia-chi={doan.dc ? khoaDiaChi(doan.dc) : undefined}
      className={`${THAN} mt-2.5 ${doan.cap === "diem" ? "pl-7" : ""} ${className}`}
    >
      {children}
    </p>
  );
}

/** Toàn văn dựng lại từ cây Chương → Mục → Điều → Khoản → Điểm.
 *
 * Trình bày bám theo bản in của một văn bản quy phạm: Chương và Mục căn giữa và tách làm hai
 * dòng (số hiệu rồi mới tới tên), Điều là tiêu đề đứng riêng một dòng, khoản và điểm là đoạn
 * văn thụt đầu dòng theo bậc.
 *
 * Bỏ khung viền quanh từng Điều. Khung biến một văn bản liền mạch thành chồng thẻ rời — đó
 * chính là thứ khiến trang này đọc như bảng điều khiển chứ không như văn bản. Nhịp giữa các
 * phần giờ do lề trên đảm nhiệm, khác nhau theo cấp, thay cho `space-y-*` chia đều máy móc.
 *
 * Tiền tố số ("1.", "a)") vẫn nằm nguyên trong `n.text` như nguồn trả. KHÔNG chuyển sang cho
 * CSS tự đánh số: khối trích dẫn trong văn bản sửa đổi mang đánh số của văn bản BỊ SỬA, để CSS
 * đếm lại là ra số sai.
 */
function ProvisionNodes({
  nodes,
  tacDong,
  // Địa chỉ của phần văn bản đang bao quanh — Điều nào, và nếu đang trong một Khoản thì Khoản
  // nào. Nút Điểm không tự biết nó thuộc Khoản nào nên phải nhận từ trên xuống.
  ctx = { article: null, khoan: null, neoChuong: null },
  depth = 0,
}: {
  nodes: Provision[];
  tacDong: Map<string, TacDongDonVi[]>;
  // `neoChuong` chảy xuống để một Mục biết nó nằm trong Chương nào: "Mục 1" lặp lại ở từng Chương
  // nên neo phải mang Chương cha, không thì hai Mục khác nhau trùng id.
  ctx?: { article: string | null; khoan: string | null; neoChuong: string | null };
  depth?: number;
}) {
  return (
    <>
      {nodes.map((n, i) => {
        const marks = n.bi_tac_dong ?? [];
        const key = n.id ?? `${n.cap}-${n.so}-${i}`;

        if (n.cap === "chuong" || n.cap === "muc") {
          const chuong = n.cap === "chuong";
          // Neo tính bằng đúng hàm mà mục lục dùng, với cùng chỉ số trong cùng danh sách anh em —
          // hai bên buộc phải ra một chuỗi, nếu không mục lục trỏ vào id không tồn tại.
          const anchor = chuong ? neoChuong(n.so, i) : neoMuc(ctx.neoChuong, n.so, i);
          return (
            <section
              key={key}
              id={anchor}
              className={`scroll-mt-28 ${chuong ? "mt-12 first:mt-0" : "mt-9 first:mt-0"}`}
            >
              <h2
                className={`serif text-center font-semibold ${
                  chuong ? "text-[1.19em] uppercase tracking-[.06em]" : "text-[1.06em]"
                }`}
              >
                {`${chuong ? "Chương" : "Mục"} ${n.so ?? ""}`.trim()}
              </h2>
              {/* Tên chương xuống dòng riêng, không nối bằng dấu chấm như bản cũ */}
              {n.tieu_de && (
                <p
                  className={`serif mt-1 text-center font-semibold leading-snug ${
                    chuong ? "text-[1em] uppercase tracking-[.03em]" : "text-[0.97em]"
                  }`}
                >
                  {n.tieu_de}
                </p>
              )}
              {n.con.length > 0 && (
                <ProvisionNodes
                  nodes={n.con}
                  tacDong={tacDong}
                  ctx={chuong ? { ...ctx, neoChuong: anchor } : ctx}
                  depth={depth + 1}
                />
              )}
            </section>
          );
        }

        if (n.cap === "dieu") {
          const article = n.so ? `Điều ${n.so}` : null;
          const goc = article ? { article, khoan: null, diem: null } : null;
          return (
            <section
              key={key}
              id={n.so ? neoDieu(n.so) : undefined}
              className="mt-7 scroll-mt-28 first:mt-0"
            >
              <h3 className="serif text-[1.03em] font-semibold leading-snug">
                {[`Điều ${n.so ?? ""}`.trim(), n.tieu_de].filter(Boolean).join(". ")}
                {marks.map((k) => (
                  <span key={k} className="ml-2 align-middle">
                    <AmendBadge kind={k} />
                  </span>
                ))}
              </h3>
              {/* Đoạn dẫn của Điều — hoặc cả một khối trích dẫn có khoản/điểm của nó */}
              {n.html &&
                beDoan(n.html, "dieu", goc).map((d, j) => (
                  <DoanThan key={j} doan={d}>
                    {renderInline(d.html)}
                  </DoanThan>
                ))}
              {n.so && <TacDongDieu muc={tacDong.get(`Điều ${n.so}`) ?? []} />}
              {n.con.length > 0 && (
                <ProvisionNodes
                  nodes={n.con}
                  tacDong={tacDong}
                  ctx={{ ...ctx, article, khoan: null }}
                  depth={depth + 1}
                />
              )}
            </section>
          );
        }

        // Khoản / Điểm.
        const goc: DiaChiDonVi | null = ctx.article
          ? n.cap === "khoan"
            ? { article: ctx.article, khoan: n.so, diem: null }
            : { article: ctx.article, khoan: ctx.khoan, diem: n.so }
          : null;
        const doans: Doan[] = n.html
          ? beDoan(n.html, n.cap, goc)
          : [{ html: n.text, cap: n.cap, dc: goc }];
        return (
          <div
            key={key}
            // Vạch lề cho đơn vị bị tác động, đặt ở KHỐI chứ không ở từng đoạn: kéo ngược bằng
            // -ml-3 để chữ vẫn thẳng hàng với các đoạn khác, vạch nằm ngoài cột chữ như ghi chú
            // bên lề bản in. Để ở đoạn thì `pl-3` của vạch đá nhau với `pl-7` thụt lề của Điểm.
            className={marks.length ? "-ml-3 border-l-2 border-accent pl-3" : ""}
          >
            {doans.map((d, j) => (
              <DoanThan key={j} doan={d}>
                {n.html ? renderInline(d.html) : d.html}
                {j === 0 &&
                  marks.map((k) => (
                    <span key={k} className="ml-2 align-middle">
                      <AmendBadge kind={k} />
                    </span>
                  ))}
              </DoanThan>
            ))}
            {n.con.length > 0 && (
              <ProvisionNodes
                nodes={n.con}
                tacDong={tacDong}
                ctx={{ ...ctx, khoan: n.cap === "khoan" ? n.so : ctx.khoan }}
                depth={depth + 1}
              />
            )}
          </div>
        );
      })}
    </>
  );
}

function ContentTab({
  doc,
  amendments,
  dong,
}: {
  doc: DocumentDetail;
  amendments: Map<string, AmendmentInfo[]>;
  // Đường phẳng đã chuẩn bị sẵn ở trang: mục lục và phần render phải đọc cùng một danh sách,
  // nếu mỗi bên tự tính mốc Chương/Mục thì chỉ cần lệch một chỗ là bấm mục lục không nhảy.
  dong: DongPhang[];
}) {
  // Tác động cấp khoản dựng TRƯỚC nhánh rẽ: cả đường cây lẫn đường phẳng đều cần nó.
  const theoDieu = new Map<string, TacDongDonVi[]>();
  for (const t of doc.tac_dong ?? []) {
    const ds = theoDieu.get(t.article) ?? [];
    ds.push(t);
    theoDieu.set(t.article, ds);
  }

  // Không có gì để dựng thì NÓI RÕ, đừng trả về một trang trắng. 8/22 văn bản trong kho là văn
  // bản hợp nhất: vbpl.vn chỉ đăng thuộc tính và lược đồ của chúng chứ không đăng toàn văn, nên
  // rỗng ở đây là giới hạn của nguồn chứ không phải lỗi tải.
  if ((doc.provisions?.length ?? 0) === 0 && doc.articles.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-panel px-4 py-3.5 text-sm text-dim">
        Bản ghi này không có toàn văn. Nguồn chỉ đăng thuộc tính và lược đồ cho văn bản hợp nhất,
        không đăng nội dung điều khoản. Xem tab <span className="text-foreground">Thuộc tính</span>{" "}
        để mở bản gốc tại nguồn hoặc tải file đính kèm.
      </div>
    );
  }

  // Có cây thì dựng toàn văn đúng phân cấp như bản gốc; chưa crawl lại thì vẫn dùng
  // danh sách Điều phẳng cũ, không để trang trống.
  if (doc.provisions && doc.provisions.length > 0) {
    return <ProvisionNodes nodes={doc.provisions} tacDong={theoDieu} />;
  }

  // Đường phẳng phải nói cùng một giọng với đường cây, nếu không cùng một trang lại đọc ra hai
  // kiểu tuỳ văn bản đã crawl lại hay chưa.
  return (
    <div>
      {dong.map(({ a, neo: anchor, chuong, muc }) => {
        const hits = anchor ? amendments.get(anchor) ?? [] : [];
        const inactive = a.superseded || (a.valid_to !== null && a.valid_to <= new Date().toISOString().slice(0, 10));
        return (
          <div key={a.article}>
            {chuong && (
              <h2
                id={chuong.anchor}
                className="serif mt-12 scroll-mt-28 text-center text-[1.19em] font-semibold uppercase tracking-[.06em]"
              >
                {[chuong.nhan, chuong.tieuDe].filter(Boolean).join(". ")}
              </h2>
            )}
            {muc && (
              <h3
                id={muc.anchor}
                className="serif mt-9 scroll-mt-28 text-center text-[1.06em] font-semibold"
              >
                {[muc.nhan, muc.tieuDe].filter(Boolean).join(". ")}
              </h3>
            )}
            <section
              id={anchor ?? undefined}
              className={`mt-7 scroll-mt-28 ${
                hits.some((h) => h.relType === "THAY_THE")
                  ? "-ml-3 border-l-2 border-red pl-3"
                  : hits.length > 0
                    ? "-ml-3 border-l-2 border-accent pl-3"
                    : ""
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="serif text-[1.03em] font-semibold">{a.article}</span>
                {hits.length > 0 && (
                  <span className="rounded border border-accent px-2 py-0.5 text-xs text-accent-dim">
                    Bị sửa đổi
                  </span>
                )}
                {inactive && (
                  <span className="rounded border border-red px-2 py-0.5 text-xs text-red">
                    Hết hiệu lực{a.valid_to ? ` từ ${a.valid_to}` : ""}
                  </span>
                )}
              </div>
              <TacDongDieu muc={theoDieu.get(a.article) ?? []} />
              {hits.length > 0 && (
                <div className="mt-2 space-y-1 rounded-md bg-inset px-3 py-2 text-xs">
                  {hits.map((h, i) => (
                    <p key={i} className="text-dim">
                      {h.relType === "THAY_THE" ? "Điều này bị thay thế bởi" : "Điều này bị sửa đổi, bổ sung bởi"}{" "}
                      <span className="font-medium text-foreground">{h.sourceTitle}</span>
                      {h.sourceArticle ? ` — ${h.sourceArticle}` : ""}
                      {h.detail ? ` (${h.detail})` : ""}
                      {h.validFrom ? `, hiệu lực từ ${h.validFrom}` : ""}{" "}
                      <Link
                        href={`/docs/${encodeURIComponent(h.sourceDoc)}${
                          h.sourceArticle && articleAnchor(h.sourceArticle)
                            ? `#${articleAnchor(h.sourceArticle)}`
                            : ""
                        }`}
                        className="text-accent-dim underline decoration-dotted hover:text-accent"
                      >
                        [xem]
                      </Link>
                    </p>
                  ))}
                </div>
              )}
              <p className={`${THAN} mt-2 whitespace-pre-wrap`}>{a.text}</p>
            </section>
          </div>
        );
      })}
    </div>
  );
}

// Thứ tự hiển thị bám theo bảng Thuộc tính của vbpl.vn để người dùng đối chiếu được.
const PROPERTY_ROWS: [label: string, key: keyof DocumentDetail][] = [
  ["Số hiệu", "so_hieu"],
  ["Loại văn bản", "doc_type"],
  ["Ngành", "nganh"],
  ["Ngày ban hành", "ngay_ban_hanh"],
  ["Lĩnh vực", "linh_vuc"],
  ["Ngày có hiệu lực", "valid_from"],
  ["Tình trạng hiệu lực", "tinh_trang_hieu_luc"],
  ["Ngày hết hiệu lực", "valid_to"],
  ["Cơ quan ban hành", "co_quan_ban_hanh"],
  ["Chức danh", "chuc_danh"],
  ["Người ký", "nguoi_ky"],
];

function PropertiesTab({ doc }: { doc: DocumentDetail }) {
  const rows = PROPERTY_ROWS.map(([label, key]) => {
    const raw = doc[key];
    return { label, value: typeof raw === "string" && raw.trim() ? raw : null };
  });
  const known = rows.filter((r) => r.value !== null).length;

  return (
    <div className="mt-4 space-y-4">
      {known === 0 && (
        <p className="rounded-lg border border-border bg-panel px-4 py-3 text-sm text-dim">
          Văn bản này chưa có thuộc tính chi tiết — bản ghi được duyệt trước khi hệ thống lưu
          nhóm trường này. Nội dung và lược đồ vẫn đầy đủ.
        </p>
      )}
      <section className="overflow-hidden rounded-xl border border-border bg-panel">
        <h2 className="border-b border-border px-4 py-2 text-xs font-semibold uppercase tracking-wide text-dim">
          Thuộc tính
        </h2>
        <dl className="grid grid-cols-1 sm:grid-cols-2">
          {rows.map(({ label, value }) => (
            <div
              key={label}
              className="flex gap-3 border-b border-border px-4 py-2.5 last:border-b-0 sm:odd:border-r"
            >
              <dt className="w-40 shrink-0 text-xs text-dim">{label}</dt>
              <dd className={`text-sm ${value ? "" : "text-faint"}`}>{value ?? "—"}</dd>
            </div>
          ))}
        </dl>
      </section>

      <SourceFiles doc={doc} />
    </div>
  );
}

function SourceFiles({ doc }: { doc: DocumentDetail }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Backend cũ chưa trả khoá này -> undefined, không phải mảng rỗng.
  const files = doc.source_files ?? [];

  async function onDownload(file: SourceFile) {
    setError(null);
    setBusy(file.ten);
    try {
      await downloadSourceFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tải file thất bại");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-xl border border-border bg-panel p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-dim">Văn bản gốc</h2>

      {doc.source_url && (
        <a
          href={doc.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-sm text-accent-dim underline decoration-dotted hover:text-accent"
        >
          Xem bản gốc tại nguồn ↗
        </a>
      )}

      {files.length === 0 ? (
        <p className="mt-2 text-sm text-faint">Chưa có file gốc đính kèm văn bản này.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {files.map((f) => (
            <li
              key={f.ten}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-background px-3 py-2"
            >
              <span className="min-w-0 flex-1 truncate text-sm">{f.ten}</span>
              {f.kich_thuoc && <span className="mono text-xs text-faint">{f.kich_thuoc}</span>}
              {f.url ? (
                <button
                  onClick={() => onDownload(f)}
                  disabled={busy === f.ten}
                  className="rounded-md border border-accent px-3 py-1 text-xs text-accent-dim transition-colors hover:bg-accent hover:text-white disabled:opacity-50"
                >
                  {busy === f.ten ? "Đang tải…" : "Tải về"}
                </button>
              ) : (
                // Biết là có file nhưng nguồn không cho link — nói rõ thay vì nút bấm không chạy
                <span className="text-xs text-faint">chưa có link tải</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="mt-2 rounded-lg border border-red-bd bg-red-bg px-3 py-2 text-xs text-red">
          {error}
        </div>
      )}
    </section>
  );
}

function SchemaTab({ doc }: { doc: DocumentDetail }) {
  const groups = groupRelationships(doc);
  if (groups.length === 0) {
    return <p className="mt-6 text-sm text-faint">Chưa ghi nhận quan hệ nào với văn bản khác.</p>;
  }
  return (
    <div className="mt-4 space-y-4">
      {groups.map((g) => (
        <section key={g.label} className="rounded-xl border border-border bg-panel p-4">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-dim">{g.label}</h2>
          <div className="mt-2 space-y-2">
            {g.entries.map((e) => (
              <Link
                key={e.docId}
                href={`/docs/${encodeURIComponent(e.docId)}`}
                className="block rounded-lg border border-border bg-background p-3 transition-colors hover:border-accent"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{e.title}</span>
                  <span className="mono text-xs text-accent-dim">{e.docId}</span>
                  {e.validFrom && (
                    <span className="mono ml-auto text-xs text-faint">từ {e.validFrom}</span>
                  )}
                </div>
                {e.note && <p className="mt-1 text-xs text-dim">{e.note}</p>}
                {e.anchors.length > 0 && (
                  <p className="mono mt-1 text-xs text-faint">
                    {e.anchors
                      .map((a) =>
                        [a.source_article, a.target_article].filter(Boolean).join(" → "),
                      )
                      .join(" · ")}
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
