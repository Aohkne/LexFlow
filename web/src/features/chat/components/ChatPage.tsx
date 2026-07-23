"use client";

import { useState } from "react";
import { Icon } from "@iconify/react";
import { motion, AnimatePresence } from "motion/react";
import { Button } from "@/shared/components/ui/Button";
import { Card, CardBody, CardEyebrow } from "@/shared/components/ui/Card";
import { Textarea, Input } from "@/shared/components/ui/Input";
import { Tabs } from "@/shared/components/ui/Tabs";
import { postChat, SAMPLE_QUESTIONS } from "../api";
import type { ChatMode, ChatResponse } from "../types";
import { CitationCard } from "./CitationCard";
import { ConflictAlertCard } from "./ConflictAlertCard";

export function ChatPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<ChatMode>("qa");
  const [asOf, setAsOf] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<ChatResponse | null>(null);

  async function ask(q?: string) {
    const question = (q ?? query).trim();
    if (!question) return;
    setLoading(true);
    setError(null);
    setResp(null);
    try {
      const data = await postChat({ query: question, mode, as_of: asOf || null, top_k: 6 });
      setResp(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi không xác định — kiểm tra kết nối backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <CardEyebrow>Dispatch · Tra cứu</CardEyebrow>
      <h1 className="font-heading mt-1 text-2xl font-semibold text-foreground sm:text-3xl">
        Tra cứu quy định thanh toán
      </h1>
      <p className="mt-2 max-w-xl text-sm text-dim">
        Hỏi tự nhiên, nhận câu trả lời có trích dẫn đúng điều/khoản{" "}
        <span className="font-medium text-accent-dim">đang hiệu lực</span> — kèm cảnh báo mâu thuẫn.
      </p>

      <Card className="mt-6">
        <CardBody>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <Tabs
              value={mode}
              onChange={setMode}
              options={[
                { value: "qa", label: "Hỏi–đáp" },
                { value: "checklist", label: "Checklist luồng" },
              ]}
            />
            <label className="ml-auto flex items-center gap-2 text-xs text-dim">
              Tại thời điểm
              <Input
                type="date"
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
                className="mono h-8 w-auto px-2 text-xs"
              />
            </label>
          </div>

          <Textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask();
            }}
            rows={3}
            placeholder={
              mode === "qa"
                ? "Ví dụ: Hạn mức giao dịch qua ví điện tử cá nhân là bao nhiêu một tháng?"
                : "Mô tả luồng nghiệp vụ, ví dụ: nạp ví điện tử qua ngân hàng liên kết"
            }
          />
          <div className="mt-2 flex items-center justify-between">
            <span className="mono text-xs text-faint">⌘/Ctrl + Enter để gửi</span>
            <Button onClick={() => ask()} disabled={loading}>
              {loading ? (
                <>
                  <Icon icon="ph:spinner-gap-bold" className="animate-spin" /> Đang tra cứu…
                </>
              ) : (
                <>
                  <Icon icon="ph:paper-plane-tilt-fill" /> Tra cứu
                </>
              )}
            </Button>
          </div>
        </CardBody>
      </Card>

      <div className="mt-3 flex flex-wrap gap-2">
        {SAMPLE_QUESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setQuery(s);
              ask(s);
            }}
            className="rounded-full border border-border bg-panel px-3 py-1 text-xs text-dim transition-colors hover:border-accent hover:text-accent-dim"
          >
            {s}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-6 flex items-center gap-2 rounded-lg border border-red bg-red/5 px-4 py-3 text-sm text-red">
          <Icon icon="ph:x-circle-fill" /> {error}
        </div>
      )}

      <AnimatePresence>
        {resp && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="mt-8 space-y-6"
          >
            {resp.conflicts.length > 0 && (
              <section className="space-y-2">
                {resp.conflicts.map((c, i) => (
                  <ConflictAlertCard key={i} conflict={c} />
                ))}
              </section>
            )}

            <Card>
              <CardBody>
                <CardEyebrow>Trả lời</CardEyebrow>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                  {resp.answer}
                </p>
              </CardBody>
            </Card>

            {resp.citations.length > 0 && (
              <section>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-dim">
                  Nguồn trích dẫn ({resp.citations.length})
                </div>
                <div className="space-y-2">
                  {resp.citations.map((c, i) => (
                    <CitationCard key={i} citation={c} />
                  ))}
                </div>
              </section>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
