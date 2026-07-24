"use client";

import Link from "next/link";
import { Icon } from "@iconify/react";
import { motion } from "motion/react";
import { Button } from "@/shared/components/ui/Button";
import { CardEyebrow } from "@/shared/components/ui/Card";
import { PAINPOINT_SOLUTIONS } from "../content";
import { PainpointCard } from "./PainpointCard";

export function LandingPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="border-b border-border pb-10"
      >
        <CardEyebrow>Số I · Payment Integration</CardEyebrow>
        <h1 className="font-heading mt-2 max-w-3xl text-3xl font-semibold leading-tight text-foreground sm:text-5xl">
          Tra cứu quy định thanh toán — có trích dẫn, không đoán mò.
        </h1>
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-dim sm:text-base">
          Hoa Tiêu Pháp Lý dịch quy định ngân hàng thành câu trả lời tức thì cho pháp chế và đội kỹ
          thuật — trích đúng điều/khoản đang hiệu lực, cảnh báo khi hai văn bản mâu thuẫn.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/chat">
            <Button size="lg">
              <Icon icon="ph:chats-circle-fill" /> Bắt đầu tra cứu
            </Button>
          </Link>
          <Link href="/graph">
            <Button size="lg" variant="outline">
              <Icon icon="ph:graph" /> Xem đồ thị tri thức
            </Button>
          </Link>
        </div>
      </motion.section>

      <section className="mt-10">
        <div className="mb-6 flex items-baseline gap-2">
          <span className="text-accent">■</span>
          <h2 className="font-heading text-sm font-semibold uppercase tracking-[0.14em] text-foreground">
            Painpoint → Giải pháp
          </h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PAINPOINT_SOLUTIONS.map((item, i) => (
            <motion.div
              key={item.index}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.35, delay: i * 0.05 }}
            >
              <PainpointCard item={item} />
            </motion.div>
          ))}
        </div>
      </section>

      <footer className="mono mt-14 border-t border-border pt-6 text-xs text-faint">
        <span className="text-accent">&gt;</span> nguồn văn bản pháp lý tham chiếu: 9 văn bản lõi
        phạm vi thanh toán — xem docs/SPEC.html.
      </footer>
    </div>
  );
}
