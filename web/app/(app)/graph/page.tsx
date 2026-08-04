"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import PageShell from "@/components/page-shell";
import { getGraph, type GraphData } from "@/lib/api";
import { nhanNgan } from "@/lib/quan-he";

// Cytoscape đụng tới `window` → chỉ render phía client.
const CytoscapeComponent = dynamic(() => import("react-cytoscapejs"), { ssr: false });

const TYPE_COLOR: Record<string, string> = {
  Luật: "#8f4a30",
  "Nghị định": "#3d6a9e",
  "Thông tư": "#b85c3a",
  "Quyết định": "#9c7a2c",
  "Nội bộ": "#4c7a4f",
};


export default function GraphPage() {
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGraph()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Lỗi tải đồ thị"));
  }, []);

  const elements = useMemo(() => {
    if (!data) return [];
    const nodes = data.nodes.map((n) => ({
      // Node RỖNG (`co_toan_van === false`): biết văn bản này tồn tại và biết nó nối vào đâu,
      // nhưng chưa có toàn văn. Phải nhìn ra được — nếu không thì nó trông y hệt một văn bản
      // đã đọc, và người dùng click vào chỉ thấy trang trống mà không hiểu vì sao.
      data: {
        id: n.id,
        label: n.co_toan_van === false ? `${n.label} (chưa có toàn văn)` : n.label,
        color: n.co_toan_van === false ? "#c9c4b5" : (TYPE_COLOR[n.doc_type] ?? "#6b675c"),
        rong: n.co_toan_van === false ? 1 : 0,
      },
    }));
    const edges = data.edges.map((e, i) => ({
      data: {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        label: nhanNgan(e.rel_type),
      },
    }));
    return [...nodes, ...edges];
  }, [data]);

  const stylesheet = [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        label: "data(label)",
        color: "#201f1a",
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
      // Viền đứt = chưa có toàn văn. Khác biệt phải thấy được mà không cần đọc nhãn.
      selector: "node[rong = 1]",
      style: {
        "border-width": 2,
        "border-style": "dashed",
        "border-color": "#8f8a7c",
        "background-opacity": 0.45,
      },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": "#ddd8cb",
        "target-arrow-color": "#b85c3a",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        label: "data(label)",
        "font-size": "9px",
        color: "#8f4a30",
        "text-background-color": "#fbfaf7",
        "text-background-opacity": 1,
        "text-background-padding": "2px",
      },
    },
  ];

  return (
    <PageShell active="graph">
    <div className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="serif text-2xl font-medium tracking-[-.015em]">Đồ thị tri thức pháp lý</h1>
      <p className="mt-1 text-sm text-dim">
        Vị trí văn bản trong phân cấp Luật → Nghị định → Thông tư → Quyết định, cùng quan hệ thay
        thế / sửa đổi / hướng dẫn / dẫn chiếu.
      </p>

      {/* Chú giải */}
      <div className="mt-4 flex flex-wrap gap-3 text-xs">
        {Object.entries(TYPE_COLOR).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full" style={{ background: v }} />
            {k}
          </span>
        ))}
      </div>

      {error && (
        <div className="mt-6 rounded-lg border border-accent bg-panel px-4 py-3 text-sm text-accent-dim">
          {error} — kiểm tra cấu hình Neo4j Aura (NEO4J_URI/PASSWORD) và chạy ingest.
        </div>
      )}

      <div className="mt-6 h-[560px] overflow-hidden rounded-xl border border-border bg-panel">
        {elements.length > 0 ? (
          <CytoscapeComponent
            elements={elements}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            stylesheet={stylesheet as any}
            layout={{ name: "cose", padding: 40, animate: false }}
            style={{ width: "100%", height: "100%" }}
          />
        ) : (
          !error && <div className="grid h-full place-items-center text-sm text-faint">Đang tải đồ thị…</div>
        )}
      </div>
    </div>
    </PageShell>
  );
}
