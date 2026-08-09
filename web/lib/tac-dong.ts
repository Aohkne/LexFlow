// Lớp phủ tác động, dọn sẵn cho trình xem: phân loại, nhãn, thứ tự văn bản, tra theo địa chỉ.
import { beDoan, khoaDiaChi, type DiaChiDonVi } from "@/lib/anchors";
import type { Provision, TacDongDonVi } from "@/lib/api";

// Cùng bảng chữ với `app/ontology/parser.py::VI_LETTERS` — điểm trong văn bản QPPL có `đ`,
// không có f/j/w/z, nên `a-z` vừa sai thứ tự vừa thiếu chữ.
const VI_LETTERS = "abcdđeghiklmnopqrstuvxy";

/** Ba loại đánh dấu của thiết kế. Lớp phủ có 5 `thao_tac`, gộp về đây để bảng màu chỉ có 3 nhánh. */
export type LoaiDanhDau = "sua" | "bai_bo" | "bo_sung";

export function loaiDanhDau(t: TacDongDonVi): LoaiDanhDau {
  // `trang_thai` là chốt chặn: cạnh cũ trong artefact chưa có `thao_tac` vẫn phải ra đúng màu.
  if (t.thao_tac === "bai_bo" || t.trang_thai === "bi_bai_bo") return "bai_bo";
  if (t.thao_tac === "bo_sung") return "bo_sung";
  return "sua";
}

// Nhãn nói đúng việc đã xảy ra. Gộp `thay_cum_tu` vào màu "sửa" là chuyện trình bày, nhưng nói
// với người đọc rằng nó "bị sửa đổi" trong khi nguồn ghi "thay cụm từ" thì là nói sai.
const NHAN_THAO_TAC: Record<string, string> = {
  sua_doi: "Bị sửa đổi",
  bo_sung: "Được bổ sung",
  bai_bo: "Bị bãi bỏ",
  thay_cum_tu: "Bị thay cụm từ",
  thay_phu_luc: "Bị thay phụ lục",
};

export function nhanTacDong(t: TacDongDonVi): string {
  const n = t.thao_tac ? NHAN_THAO_TAC[t.thao_tac] : undefined;
  if (n) return n;
  return t.trang_thai === "bi_bai_bo" ? "Bị bãi bỏ" : "Bị sửa đổi";
}

/** Nhãn địa chỉ đọc được: "Điều 26 · Khoản 1 · Điểm a". */
export function nhanDiaChi(t: TacDongDonVi): string {
  return [t.article, t.khoan && `Khoản ${t.khoan}`, t.diem && `Điểm ${t.diem}`]
    .filter(Boolean)
    .join(" · ");
}

/** Id neo ngắn theo kiểu thiết kế đặt ra: "26.1", "26.1.a". */
export function idNeoNgan(t: TacDongDonVi): string {
  const so = t.article.match(/\d+[a-zđ]?/i)?.[0] ?? t.article;
  return [so, t.khoan, t.diem].filter(Boolean).join(".");
}

// "26" -> [26, 0]; "26a" -> [26, 1]; "9đ" -> [9, 5]. Số không đọc được xuống cuối thay vì
// lẫn vào giữa — sai thứ tự thì số huy hiệu và nút "thay đổi tiếp" trỏ nhầm đơn vị.
function khoaSo(s: string | null): [number, number] {
  if (!s) return [-1, -1];
  const m = s.match(/^(\d+)([a-zđ]?)$/i);
  if (!m) return [Number.MAX_SAFE_INTEGER, 0];
  const chu = m[2] ? VI_LETTERS.indexOf(m[2].toLowerCase()) + 1 : 0;
  return [Number(m[1]), chu < 0 ? Number.MAX_SAFE_INTEGER : chu];
}

function khoaDiem(s: string | null): number {
  if (!s) return -1;
  const i = VI_LETTERS.indexOf(s.toLowerCase());
  return i < 0 ? Number.MAX_SAFE_INTEGER : i;
}

/**
 * Sắp theo đúng thứ tự đọc của văn bản.
 *
 * Backend trả danh sách đã sắp theo CHUỖI khoá overlay, nên "dieu_10" đứng trước "dieu_9". Thứ
 * tự đó chảy thẳng vào số huy hiệu ở lề và vào nút duyệt trước/tiếp, nên phải sắp lại theo số.
 */
export function sapTheoVanBan(ds: TacDongDonVi[]): TacDongDonVi[] {
  return [...ds].sort((a, b) => {
    const [ad, adc] = khoaSo(a.article.match(/\d+[a-zđ]?/i)?.[0] ?? null);
    const [bd, bdc] = khoaSo(b.article.match(/\d+[a-zđ]?/i)?.[0] ?? null);
    if (ad !== bd) return ad - bd;
    if (adc !== bdc) return adc - bdc;
    const [ak, akc] = khoaSo(a.khoan);
    const [bk, bkc] = khoaSo(b.khoan);
    if (ak !== bk) return ak - bk;
    if (akc !== bkc) return akc - bkc;
    return khoaDiem(a.diem) - khoaDiem(b.diem);
  });
}

export type DanhDau = {
  t: TacDongDonVi;
  loai: LoaiDanhDau;
  /** Số thứ tự thay đổi trong văn bản, 1…N — chính là con số trên huy hiệu ở lề. */
  stt: number;
};

/**
 * Bảng tra theo địa chỉ đơn vị.
 *
 * Khoá dùng đúng `khoaDiaChi` mà mỗi đoạn văn đã gắn sẵn vào `data-dia-chi` từ bước trước, nên
 * việc đánh dấu chỉ là một phép tra, không phải dò chuỗi trong nội dung.
 */
export function bangDanhDau(ds: TacDongDonVi[]): Map<string, DanhDau> {
  const map = new Map<string, DanhDau>();
  sapTheoVanBan(ds).forEach((t, i) => {
    const dc: DiaChiDonVi = { article: t.article, khoan: t.khoan, diem: t.diem };
    const khoa = khoaDiaChi(dc);
    // Một đơn vị bị chạm nhiều lần thì lớp phủ đã chọn lần gần nhất; giữ bản ghi đầu tiên gặp
    // để số thứ tự không nhảy cóc.
    if (!map.has(khoa)) map.set(khoa, { t, loai: loaiDanhDau(t), stt: i + 1 });
  });
  return map;
}

/** Danh sách phẳng theo thứ tự văn bản — dùng cho "2 / 4" và nút duyệt trước/tiếp. */
export function danhSachDanhDau(ds: TacDongDonVi[]): DanhDau[] {
  return [...bangDanhDau(ds).values()].sort((a, b) => a.stt - b.stt);
}

// HTML ở đây đã được backend lọc còn vài thẻ inline (`b/i/u/sup/sub/br`), nên bóc thẻ bằng regex
// là đủ và không có rủi ro: chuỗi này chỉ dùng làm CHỮ trong bảng đối chiếu, không đổ vào DOM.
function boThe(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .trim();
}

/**
 * Nguyên văn từng đơn vị, tra theo cùng khoá địa chỉ mà lớp phủ dùng.
 *
 * Bảng đối chiếu cần chữ của đơn vị KHÁC với đơn vị vừa bấm (nút "thay đổi trước/tiếp" nhảy
 * vòng qua cả văn bản), nên không thể lấy từ chỗ bấm. Đi lại đúng phép bẻ đoạn mà trang dùng
 * khi render — nếu hai bên bẻ khác nhau thì modal hiện một đoạn, trang hiện một đoạn khác.
 */
export function bangVanBanDonVi(nodes: Provision[]): Map<string, string> {
  const ra = new Map<string, string>();
  const them = (khoa: string, chu: string) => {
    if (!chu) return;
    const cu = ra.get(khoa);
    ra.set(khoa, cu ? `${cu}\n${chu}` : chu);
  };

  /**
   * Gom TỪ DƯỚI LÊN và trả về chữ của cả nhánh.
   *
   * Một Điều thường không có chữ của riêng nó — tiêu đề nằm ở `tieu_de`, còn nội dung nằm hết
   * trong các khoản con. Chỉ lấy `html` của chính nút thì địa chỉ cấp Điều tra ra rỗng, mà lớp
   * phủ có đánh dấu ở cấp Điều (bãi bỏ cả điều). Nên mỗi đơn vị nhận chữ của chính nó CỘNG chữ
   * của mọi đơn vị con: đó đúng là "nguyên văn của đơn vị" mà bảng đối chiếu cần.
   */
  const di = (ns: Provision[], article: string | null, khoan: string | null): string => {
    const manh: string[] = [];
    for (const n of ns) {
      if (n.cap === "chuong" || n.cap === "muc") {
        di(n.con, article, khoan);
        continue;
      }

      if (n.cap === "dieu") {
        const a = n.so ? `Điều ${n.so}` : null;
        const goc: DiaChiDonVi | null = a ? { article: a, khoan: null, diem: null } : null;
        const rieng: string[] = [];
        if (n.html && goc) {
          for (const d of beDoan(n.html, "dieu", goc)) {
            const chu = boThe(d.html);
            rieng.push(chu);
            // Đoạn dẫn có thể mang địa chỉ khoản/điểm riêng (khối trích dẫn), ghi theo địa chỉ
            // của chính nó chứ không dồn hết vào Điều.
            if (d.dc && khoaDiaChi(d.dc) !== (goc ? khoaDiaChi(goc) : "")) {
              them(khoaDiaChi(d.dc), chu);
            }
          }
        }
        const con = di(n.con, a, null);
        if (goc) them(khoaDiaChi(goc), [...rieng, con].filter(Boolean).join("\n"));
        continue;
      }

      const goc: DiaChiDonVi | null = article
        ? n.cap === "khoan"
          ? { article, khoan: n.so, diem: null }
          : { article, khoan, diem: n.so }
        : null;
      const rieng: string[] = [];
      if (n.html && goc) {
        for (const d of beDoan(n.html, n.cap, goc)) {
          const chu = boThe(d.html);
          rieng.push(chu);
          if (d.dc && khoaDiaChi(d.dc) !== khoaDiaChi(goc)) them(khoaDiaChi(d.dc), chu);
        }
      } else if (n.text) {
        rieng.push(n.text.trim());
      }
      const con = di(n.con, article, n.cap === "khoan" ? n.so : khoan);
      const capNay = [...rieng, con].filter(Boolean).join("\n");
      if (goc) them(khoaDiaChi(goc), capNay);
      manh.push(capNay);
    }
    return manh.filter(Boolean).join("\n");
  };

  di(nodes, null, null);
  return ra;
}
