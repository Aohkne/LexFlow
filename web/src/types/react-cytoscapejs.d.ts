declare module "react-cytoscapejs" {
  import type { CSSProperties } from "react";

  export interface CytoscapeComponentProps {
    elements: unknown[];
    stylesheet?: unknown;
    layout?: Record<string, unknown>;
    style?: CSSProperties;
    className?: string;
    cy?: (cy: unknown) => void;
  }

  const CytoscapeComponent: React.ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
