"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import { Icon } from "@iconify/react";
import { Card, CardEyebrow } from "@/shared/components/ui/Card";
import { EmptyState } from "@/shared/components/ui/EmptyState";
import { Spinner } from "@/shared/components/ui/Spinner";
import { getGraph, DOC_TYPE_COLOR, REL_LABEL } from "../api";
import type { GraphData } from "../types";
import { GraphLegend } from "./GraphLegend";

// Cytoscape đụng tới `window` → chỉ render phía client.
const CytoscapeComponent = dynamic(() => import("react-cytoscapejs"), { ssr: false });

const PALETTE = {
  light: { text: "#201f1a", edge: "#ddd8cb", arrow: "#b85c3a", labelBg: "#fbfaf7" },
  dark: { text: "#f3ede0", edge: "#3a3324", arrow: "#d9814f", labelBg: "#18150f" },
};

export function GraphPage() {
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { resolvedTheme } = useTheme();
  const palette = resolvedTheme === "dark" ? PALETTE.dark : PALETTE.light;

  useEffect(() => {
    getGraph()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Lỗi tải đồ thị"));
  }, []);

  const elements = useMemo(() => {
    if (!data) return [];
    const nodes = data.nodes.map((n) => ({
      data: { id: n.id, label: n.label, color: DOC_TYPE_COLOR[n.doc_type] ?? "#6b675c" },
    }));
    const edges = data.edges.map((e, i) => ({
      data: {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        label: REL_LABEL[e.rel_type] ?? e.rel_type,
      },
    }));
    return [...nodes, ...edges];
  }, [data]);

  const stylesheet = useMemo(
    () => [
      {
        selector: "node",
        style: {
          "background-color": "data(color)",
          label: "data(label)",
          color: palette.text,
          "font-size": "10px",
          "text-wrap": "wrap",
          "text-max-width": "140px",
          "text-valign": "bottom",
          "text-margin-y": 6,
          width: 40,
          height: 40,
        },
      },
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": palette.edge,
          "target-arrow-color": palette.arrow,
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(label)",
          "font-size": "9px",
          color: palette.arrow,
          "text-background-color": palette.labelBg,
          "text-background-opacity": 1,
          "text-background-padding": "2px",
        },
      },
    ],
    [palette],
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
      <CardEyebrow>Dispatch · Đồ thị tri thức</CardEyebrow>
      <h1 className="font-heading mt-1 text-2xl font-semibold text-foreground sm:text-3xl">
        Đồ thị tri thức pháp lý
      </h1>
      <p className="mt-2 max-w-xl text-sm text-dim">
        Vị trí văn bản trong phân cấp Luật → Nghị định → Thông tư → Quyết định, cùng quan hệ thay
        thế / sửa đổi / hướng dẫn / dẫn chiếu.
      </p>

      <div className="mt-4">
        <GraphLegend />
      </div>

      {error && (
        <div className="mt-6 flex items-center gap-2 rounded-lg border border-accent bg-panel px-4 py-3 text-sm text-accent-dim">
          <Icon icon="ph:warning-fill" /> {error} — kiểm tra cấu hình Neo4j Aura và chạy ingest.
        </div>
      )}

      <Card className="mt-6 h-[560px] overflow-hidden">
        {elements.length > 0 ? (
          <CytoscapeComponent
            elements={elements}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            stylesheet={stylesheet as any}
            layout={{ name: "cose", padding: 40, animate: false }}
            style={{ width: "100%", height: "100%" }}
          />
        ) : !error ? (
          <div className="grid h-full place-items-center">
            <Spinner className="text-2xl" />
          </div>
        ) : (
          <EmptyState
            icon="ph:graph"
            title="Chưa có dữ liệu đồ thị"
            description="Kết nối backend và chạy ingest để hiển thị đồ thị tri thức."
          />
        )}
      </Card>
    </div>
  );
}
