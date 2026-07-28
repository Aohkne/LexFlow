import Link from "next/link";
import { Lexi } from "@/components/lexi";

/** Trang giới thiệu (marketing) — theo design handoff "LexFlow Landing".
 *  Số liệu phần Stats dùng số thật của hệ thống thay cho số minh họa trong design. */

const PROBLEMS = [
  { icon: "◇", title: "Không biết dựa vào đâu", body: "Câu trả lời không kèm điều, khoản hay tên văn bản để đối chiếu." },
  { icon: "◷", title: "Nhầm bản đã hết hiệu lực", body: "Thông tư cũ vẫn được trích như đang áp dụng." },
  { icon: "⚠", title: "Bỏ lỡ mâu thuẫn", body: "Hai văn bản quy định khác nhau mà không ai được cảnh báo." },
];

const FEATURES = [
  { icon: "¹", title: "Trích dẫn nhấp được", body: "Mỗi khẳng định gắn số trích dẫn — nhấp vào là nhảy tới đúng điều khoản nguồn." },
  { icon: "◉", title: "Nhãn hiệu lực trực tiếp", body: "Từng nguồn hiển thị đang hiệu lực hay đã bị thay thế, kèm mốc thời gian." },
  { icon: "⚠", title: "Cảnh báo mâu thuẫn", body: "Đối chiếu song song hai văn bản và nêu rõ LexFlow chọn con số nào, vì sao." },
  { icon: "◷", title: "Tra cứu theo mốc thời gian", body: "Xem quy định áp dụng tại bất kỳ ngày nào — hữu ích cho hồ sơ cũ." },
  { icon: "◰", title: "Đồ thị tri thức", body: "Nhìn được văn bản nào sửa đổi, dẫn chiếu hay thay thế văn bản nào." },
  { icon: "⧉", title: "Sao chép kèm nguồn", body: "Xuất câu trả lời với chú thích văn bản, dán thẳng vào tờ trình." },
];

const STEPS = [
  { n: "1", title: "Đặt câu hỏi", body: "Hỏi tự nhiên bằng tiếng Việt, không cần từ khóa pháp lý." },
  { n: "2", title: "Truy hồi điều khoản", body: "LexFlow tìm các điều, khoản liên quan trong kho văn bản gốc." },
  { n: "3", title: "Lọc theo hiệu lực", body: "Bỏ bản đã thay thế, phát hiện mâu thuẫn giữa các văn bản." },
  { n: "4", title: "Trả lời có nguồn", body: "Mỗi câu gắn trích dẫn để bạn kiểm chứng trong vài giây." },
];

const DOC_TYPES = ["Luật", "Nghị định", "Thông tư", "Quyết định", "Quy định nội bộ"];

const TIMELINE = [
  { date: "03/2019", doc: "TT 23/2019/TT-NHNN", status: "Hết hiệu lực", note: "Hạn mức 50 triệu đồng/tháng — bị thay thế bởi TT 40/2024.", muted: true },
  { date: "01/2024", doc: "TT 40/2024/TT-NHNN", status: "✓ Đang hiệu lực", note: "Nâng hạn mức lên 100 triệu đồng/tháng, gộp theo giấy tờ tùy thân.", muted: false },
  { date: "07/2024", doc: "NĐ 52/2024/NĐ-CP", status: "✓ Đang hiệu lực", note: "Yêu cầu ví điện tử liên kết tài khoản/thẻ chính chủ.", muted: false },
];

const STATS = [
  { value: "449+", label: "điều khoản đã lập chỉ mục" },
  { value: "100%", label: "câu trả lời kèm trích dẫn" },
  { value: "36/36", label: "tránh văn bản hết hiệu lực (benchmark)" },
  { value: "7/7", label: "mâu thuẫn phát hiện đúng (benchmark)" },
];

export default function LandingPage() {
  return (
    <div className="bg-background">
      {/* NAV */}
      <header
        className="sticky top-0 z-30 border-b border-border"
        style={{ background: "rgba(240,238,230,.86)", backdropFilter: "blur(12px)" }}
      >
        <div className="mx-auto flex max-w-[1120px] items-center gap-4 px-8 py-3">
          <Link href="/landing" className="flex items-center gap-2.5">
            <span className="grid h-[29px] w-[29px] place-items-center rounded-lg bg-accent text-[15px] text-white">
              ⎈
            </span>
            <span className="text-[15px] font-semibold tracking-[-.01em]">Hoa Tiêu Pháp Lý</span>
            <span className="mono text-[10.5px] text-muted">/ LexFlow</span>
          </Link>
          <nav className="ml-auto hidden items-center gap-6 text-[13.5px] md:flex">
            <a href="#tinhnang" className="text-dim hover:text-foreground">Tính năng</a>
            <a href="#cachhoatdong" className="text-dim hover:text-foreground">Cách hoạt động</a>
            <a href="#nguon" className="text-dim hover:text-foreground">Nguồn dữ liệu</a>
          </nav>
          <div className="ml-2.5 flex items-center gap-2">
            <Link href="/login" className="rounded-[9px] px-3.5 py-2 text-[13.5px] font-medium text-dim hover:bg-inset hover:text-foreground">
              Đăng nhập
            </Link>
            <Link href="/login" className="rounded-[10px] bg-accent px-4 py-2 text-[13.5px] font-medium text-white transition-colors hover:bg-accent-hover">
              Dùng thử miễn phí
            </Link>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="mx-auto max-w-[1120px] px-8 pt-[64px] text-center">
        <span className="mb-5 inline-grid h-24 w-24 place-items-center rounded-[26px] border border-accent-wash-border bg-accent-wash">
          <Lexi state="idle" size={72} decorative={false} label="Lexi — trợ thủ pháp lý của LexFlow" />
        </span>
        <br />
        <span className="inline-flex items-center gap-1.5 rounded-full border border-accent-wash-border bg-accent-wash px-3 py-1 text-xs text-accent-dim">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Dành cho khối Pháp chế &amp; Tuân thủ ngân hàng
        </span>
        <h1 className="serif mx-auto mt-5 max-w-[760px] text-[42px] font-medium leading-[1.06] tracking-[-.025em] md:text-6xl">
          Tra cứu pháp luật mà <span className="italic text-accent-hover">không phải tin</span> vào
          trí nhớ của AI
        </h1>
        <p className="mx-auto mt-5 max-w-[600px] text-[17px] leading-relaxed text-dim">
          Hỏi bằng ngôn ngữ tự nhiên. Mỗi khẳng định gắn với đúng điều &amp; khoản{" "}
          <b className="font-semibold text-fg-strong">đang hiệu lực</b> — và LexFlow chủ động cảnh
          báo khi các văn bản mâu thuẫn nhau.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/login" className="rounded-[11px] bg-accent px-6 py-3 text-[14.5px] font-medium text-white transition-colors hover:bg-accent-hover">
            Bắt đầu tra cứu →
          </Link>
          <Link href="/login" className="rounded-[11px] border border-border bg-panel px-6 py-3 text-[14.5px] font-medium text-fg-strong hover:border-border-hover">
            Xem bản demo
          </Link>
        </div>
        <p className="mono mt-4 text-[11px] text-muted">Không cần thẻ tín dụng · Dữ liệu lưu tại Việt Nam</p>

        {/* Product preview */}
        <div
          className="mt-13 overflow-hidden rounded-t-[18px] border border-border bg-panel text-left"
          style={{ marginTop: 52, boxShadow: "0 -1px 0 #fff inset,0 24px 60px rgba(40,34,24,.13)" }}
        >
          <div className="flex items-center gap-1.5 border-b border-border-soft px-4 py-3">
            <span className="h-[9px] w-[9px] rounded-full bg-border" />
            <span className="h-[9px] w-[9px] rounded-full bg-border" />
            <span className="h-[9px] w-[9px] rounded-full bg-border" />
            <span className="mono ml-2.5 text-[10.5px] text-muted">lexflow.vn/tra-cuu</span>
          </div>
          <div className="mx-auto max-w-[660px] px-8 pb-9 pt-6">
            <div className="flex justify-end">
              <div className="serif rounded-[14px_14px_4px_14px] border border-user-bubble-border bg-user-bubble px-4 py-2.5 text-[15px] text-fg-strong">
                Hạn mức giao dịch qua ví điện tử cá nhân là bao nhiêu một tháng?
              </div>
            </div>
            <div className="mt-4 flex gap-2.5">
              <span className="flex-none">
                <Lexi state="static" size={26} />
              </span>
              <div className="flex-1">
                <div className="mb-2.5 flex flex-wrap gap-1.5">
                  <span className="inline-flex items-center gap-1 rounded-full border border-green-bd bg-green-bg px-2 py-0.5 text-[11px] text-green">
                    <span className="h-[5px] w-[5px] rounded-full bg-green" />2 nguồn đang hiệu lực
                  </span>
                  <span className="rounded-full border border-amber-bd bg-amber-bg px-2 py-0.5 text-[11px] text-amber">⚠ 1 mâu thuẫn</span>
                </div>
                <p className="serif text-base leading-[1.65] text-fg-body">
                  Tổng hạn mức giao dịch qua ví điện tử của khách hàng cá nhân tối đa{" "}
                  <b className="font-semibold">100 triệu đồng/tháng</b>
                  <span className="mono mx-px rounded-[5px] bg-cite px-1 py-0.5 align-super text-[9.5px] font-semibold text-accent-dim">1</span>
                  , tính gộp mọi ví cùng một giấy tờ tùy thân.
                </p>
                <div className="mt-3 rounded-[11px] border border-border bg-background px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="mono grid h-[21px] w-[21px] place-items-center rounded-md bg-cite text-[11px] font-semibold text-accent-dim">1</span>
                    <span className="rounded-[5px] bg-inset-strong px-1.5 py-0.5 text-[9.5px] uppercase tracking-[.04em] text-faint">Thông tư</span>
                    <span className="text-[13px] font-semibold">TT 40/2024/TT-NHNN</span>
                    <span className="mono text-[10.5px] text-accent-hover">Điều 26</span>
                    <span className="mono ml-auto text-[10px] text-muted">từ 07/2024</span>
                  </div>
                  <p className="serif mt-2 text-[13.5px] italic leading-[1.55] text-fg-strong">
                    “Tổng hạn mức giao dịch qua các Ví điện tử cá nhân của 1 khách hàng tối đa 100
                    triệu đồng Việt Nam trong một tháng.”
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* PROBLEM */}
      <section className="border-y border-border bg-panel">
        <div className="mx-auto grid max-w-[1120px] items-center gap-14 px-8 py-16 md:grid-cols-2">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-[.11em] text-accent-hover">Vấn đề</span>
            <h2 className="serif mt-3 text-[34px] font-medium leading-[1.18] tracking-[-.02em]">
              Một câu trả lời sai điều khoản có thể thành rủi ro tuân thủ
            </h2>
            <p className="mt-4 text-[15px] leading-[1.65] text-dim">
              Chatbot thông thường trả lời trôi chảy nhưng không cho biết dựa vào văn bản nào, bản
              đó còn hiệu lực không, hay có thông tư mới thay thế chưa. Cán bộ pháp chế vẫn phải tự
              mở lại toàn bộ văn bản để kiểm chứng.
            </p>
          </div>
          <div className="flex flex-col gap-3">
            {PROBLEMS.map((p) => (
              <div key={p.title} className="flex gap-3 rounded-[13px] border border-border bg-background px-4 py-3.5">
                <span className="flex-none text-base text-accent">{p.icon}</span>
                <div>
                  <div className="text-sm font-semibold">{p.title}</div>
                  <p className="mt-1 text-[13px] leading-[1.55] text-dim">{p.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="tinhnang" className="mx-auto max-w-[1120px] px-8 pt-18" style={{ paddingTop: 72 }}>
        <div className="mx-auto max-w-[620px] text-center">
          <span className="text-[10px] font-semibold uppercase tracking-[.11em] text-accent-hover">Tính năng</span>
          <h2 className="serif mt-3 text-[40px] font-medium leading-[1.12] tracking-[-.022em]">
            Thiết kế quanh một việc: giúp bạn kiểm chứng nhanh
          </h2>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-[15px] border border-border bg-panel px-5 pb-6 pt-5 transition-all hover:-translate-y-0.5 hover:border-border-hover"
            >
              <span className="grid h-[34px] w-[34px] place-items-center rounded-[10px] border border-accent-wash-border bg-accent-wash text-base text-accent-hover">
                {f.icon}
              </span>
              <h3 className="mt-3.5 text-[15.5px] font-semibold tracking-[-.01em]">{f.title}</h3>
              <p className="mt-2 text-[13.5px] leading-relaxed text-dim">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="cachhoatdong" className="mx-auto max-w-[1120px] px-8" style={{ paddingTop: 76 }}>
        <div className="rounded-[20px] border border-border bg-panel px-11 pb-12 pt-11">
          <div className="mx-auto max-w-[560px] text-center">
            <span className="text-[10px] font-semibold uppercase tracking-[.11em] text-accent-hover">Cách hoạt động</span>
            <h2 className="serif mt-3 text-[34px] font-medium leading-[1.15] tracking-[-.02em]">
              Từ câu hỏi đến điều khoản gốc trong bốn bước
            </h2>
          </div>
          <div className="mt-9 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <div key={s.n} className="rounded-[13px] border border-border-soft px-4 pb-5 pt-[18px] transition-colors hover:bg-background">
                <span className="mono grid h-[26px] w-[26px] place-items-center rounded-lg bg-accent text-xs font-semibold text-white">
                  {s.n}
                </span>
                <h3 className="mt-3 text-[14.5px] font-semibold">{s.title}</h3>
                <p className="mt-1.5 text-[13px] leading-[1.55] text-dim">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SOURCES */}
      <section id="nguon" className="mx-auto max-w-[1120px] px-8" style={{ paddingTop: 76 }}>
        <div className="grid items-center gap-14 md:grid-cols-[1fr_1.1fr]">
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-[.11em] text-accent-hover">Nguồn dữ liệu</span>
            <h2 className="serif mt-3 text-[34px] font-medium leading-[1.18] tracking-[-.02em]">
              Chỉ dùng văn bản gốc, cập nhật theo ngày hiệu lực
            </h2>
            <p className="mt-4 text-[15px] leading-[1.65] text-dim">
              LexFlow theo dõi vòng đời từng văn bản: ngày ban hành, ngày hiệu lực, văn bản sửa đổi
              và thay thế. Bạn có thể tra cứu lại tình trạng pháp lý ở bất kỳ mốc thời gian nào.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {DOC_TYPES.map((d) => (
                <span key={d} className="rounded-full border border-border bg-panel px-3 py-1.5 text-[12.5px] text-dim">
                  {d}
                </span>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-border bg-panel p-2">
            {TIMELINE.map((t, i) => (
              <div
                key={t.doc}
                className={`rounded-[11px] px-4 py-3.5 ${i > 0 ? "border-t border-border-soft" : ""} ${t.muted ? "opacity-[.62]" : ""}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mono w-[58px] text-[11px] text-muted">{t.date}</span>
                  <span className="text-[13.5px] font-semibold">{t.doc}</span>
                  <span
                    className={`ml-auto whitespace-nowrap rounded-full border px-2 py-0.5 text-[10.5px] ${
                      t.muted
                        ? "border-border bg-grey-bg text-grey"
                        : "border-green-bd bg-green-bg text-green"
                    }`}
                  >
                    {t.status}
                  </span>
                </div>
                <p className="ml-[67px] mt-1.5 text-[12.5px] leading-normal text-dim">{t.note}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* STATS */}
      <section className="mx-auto max-w-[1120px] px-8" style={{ paddingTop: 72 }}>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border bg-border lg:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label} className="bg-panel px-5 py-6 text-center">
              <div className="serif text-4xl font-medium tracking-[-.02em]">{s.value}</div>
              <div className="mt-1 text-[12.5px] leading-snug text-dim">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-[1120px] px-8" style={{ paddingTop: 76 }}>
        <div className="rounded-[20px] bg-cta-bg px-11 py-14 text-center">
          <h2 className="serif text-[40px] font-medium leading-[1.12] tracking-[-.022em] text-cta-heading">
            Tra cứu lần đầu chỉ mất một phút
          </h2>
          <p className="mx-auto mt-4 max-w-[480px] text-[15.5px] leading-relaxed text-cta-body">
            Tạo tài khoản bằng email công việc và thử ngay với một câu hỏi thật từ hồ sơ của bạn.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link href="/login" className="rounded-[11px] bg-accent px-7 py-3 text-[14.5px] font-medium text-white transition-colors hover:bg-accent-hover">
              Tạo tài khoản
            </Link>
            <Link
              href="/login"
              className="rounded-[11px] border px-6 py-3 text-[14.5px] font-medium text-cta-heading"
              style={{ background: "rgba(255,255,255,.08)", borderColor: "rgba(255,255,255,.16)" }}
            >
              Đặt lịch demo
            </Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="mx-auto mt-11 flex max-w-[1120px] flex-wrap items-center gap-4 border-t border-border px-8 pb-10 pt-11">
        <div className="flex items-center gap-2">
          <span className="grid h-6 w-6 place-items-center rounded-[7px] bg-accent text-xs text-white">⎈</span>
          <span className="text-[13px] font-semibold">Hoa Tiêu Pháp Lý</span>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-5 text-[12.5px] text-faint">
          <span>Điều khoản</span>
          <span>Bảo mật</span>
          <span>Liên hệ</span>
          <span className="mono text-[11px] text-muted">© 2026 LexFlow</span>
        </div>
      </footer>
      <p className="mx-auto max-w-[1120px] px-8 pb-11 text-[11px] leading-normal text-muted">
        LexFlow hỗ trợ tra cứu và không thay thế ý kiến tư vấn pháp lý chính thức. Luôn đối chiếu
        văn bản gốc trước khi ra quyết định.
      </p>
    </div>
  );
}
