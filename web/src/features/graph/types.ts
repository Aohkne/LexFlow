export type GraphNode = {
  id: string;
  label: string;
  doc_type: string;
  valid_from: string | null;
  valid_to: string | null;
};

export type GraphEdge = { source: string; target: string; rel_type: string };

export type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };
