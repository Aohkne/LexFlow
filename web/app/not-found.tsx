import Link from "next/link";
import { Lexi } from "@/components/lexi";

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center bg-background px-6 text-center">
      <div>
        <span className="inline-grid h-24 w-24 place-items-center rounded-[26px] border border-red-bd bg-red-bg">
          <Lexi state="error" size={66} />
        </span>
        <h1 className="serif mt-4 text-[27px] font-medium tracking-[-.015em]">
          Không tìm thấy trang
        </h1>
        <p className="mx-auto mt-2 max-w-[400px] text-sm leading-relaxed text-dim">
          Đường dẫn không tồn tại hoặc văn bản đã được gỡ. Lexi không tra được gì ở đây.
        </p>
        <Link
          href="/"
          className="mt-5 inline-block rounded-[10px] bg-accent px-5 py-2.5 text-[13.5px] font-medium text-white transition-colors hover:bg-accent-hover"
        >
          ← Về trang Tra cứu
        </Link>
      </div>
    </div>
  );
}
