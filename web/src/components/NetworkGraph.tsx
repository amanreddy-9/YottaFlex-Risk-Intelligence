import React, { useEffect, useMemo, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import type { GraphEdge, GraphNode } from "../types/workbench";
import { Badge } from "./Badge";

interface PosNode extends GraphNode {
  x: number;
  y: number;
}

const W = 760;
const H = 400;

const NODE_PALETTE: Record<GraphNode["type"], { light: string; dark: string; short: string }> = {
  CUSTOMER: { light: "#0A66E6", dark: "#FFFFFF", short: "CUS" },
  ACCOUNT: { light: "#1D84FA", dark: "#E4E4E7", short: "ACC" },
  DEVICE: { light: "#E11D48", dark: "#FB7185", short: "DEV" },
  MERCHANT: { light: "#4F46E5", dark: "#A1A1AA", short: "MER" },
};

const EDGE_PALETTE: Record<GraphEdge["type"], string> = {
  TRANSFER: "#D97706",
  USES_DEVICE: "#E11D48",
  OWNS: "#0A66E6",
  MERCHANT_TXN: "#6366F1",
};

function computeLayout(rawNodes: GraphNode[], rawEdges: GraphEdge[]): PosNode[] {
  const cx = W / 2;
  const cy = H / 2;
  const nodes: PosNode[] = rawNodes.map((n) => ({ ...n, x: cx, y: cy }));
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const edges = rawEdges.filter((e) => byId[e.source] && byId[e.target]);

  const accts = nodes.filter((n) => n.type === "ACCOUNT");
  const others = nodes.filter((n) => n.type !== "ACCOUNT");

  accts.forEach((n, idx) => {
    if (accts.length === 1) {
      n.x = cx;
      n.y = cy;
    } else {
      const ang = (2 * Math.PI * idx) / accts.length - Math.PI / 2;
      const r = accts.length <= 3 ? 95 : 118;
      n.x = cx + r * Math.cos(ang);
      n.y = cy + r * Math.sin(ang);
    }
  });

  others.forEach((n, idx) => {
    const ang = (2 * Math.PI * idx) / Math.max(1, others.length) - Math.PI / 4;
    n.x = cx + 265 * Math.cos(ang);
    n.y = cy + 150 * Math.sin(ang);
  });

  for (let step = 0; step < 65; step++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 1;
        if (dist < 80) {
          const push = ((80 - dist) / dist) * 0.35;
          a.x -= dx * push;
          a.y -= dy * push;
          b.x += dx * push;
          b.y += dy * push;
        }
      }
    }
    for (const e of edges) {
      const a = byId[e.source];
      const b = byId[e.target];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 1;
      const target = e.type === "TRANSFER" ? 138 : 112;
      const pull = ((dist - target) / dist) * 0.04;
      a.x += dx * pull;
      a.y += dy * pull;
      b.x -= dx * pull;
      b.y -= dy * pull;
    }
    for (const n of nodes) {
      n.x = Math.max(58, Math.min(W - 58, n.x));
      n.y = Math.max(42, Math.min(H - 44, n.y));
    }
  }
  return nodes;
}

export const NetworkGraph: React.FC<{
  nodes: GraphNode[];
  edges: GraphEdge[];
  darkMode: boolean;
}> = ({ nodes: rawNodes, edges: rawEdges, darkMode }) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [nodes, setNodes] = useState<PosNode[]>(() => computeLayout(rawNodes, rawEdges));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);

  useEffect(() => {
    setNodes(computeLayout(rawNodes, rawEdges));
    setSelectedId(null);
  }, [rawNodes, rawEdges]);

  const byId = useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), [nodes]);
  const validEdges = useMemo(
    () => rawEdges.filter((e) => byId[e.source] && byId[e.target]),
    [rawEdges, byId]
  );

  const selectedNode = selectedId ? byId[selectedId] : null;
  const selectedConnections = useMemo(
    () => (selectedId ? validEdges.filter((e) => e.source === selectedId || e.target === selectedId).length : 0),
    [selectedId, validEdges]
  );

  const handleMouseMove = (ev: React.MouseEvent<SVGSVGElement>) => {
    if (!draggingId || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const nx = Math.max(36, Math.min(W - 36, ((ev.clientX - rect.left) * W) / rect.width));
    const ny = Math.max(32, Math.min(H - 36, ((ev.clientY - rect.top) * H) / rect.height));
    setNodes((prev) => prev.map((n) => (n.id === draggingId ? { ...n, x: nx, y: ny } : n)));
  };

  return (
    <div className="liquid-glass rounded-2xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-white/60 dark:border-white/10 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
            Entity Linkage &amp; Fund-Flow Network
          </h3>
          <p className="text-xs text-slate-600 dark:text-zinc-400">
            Drag nodes to inspect topology • Click any entity for metadata
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-[11.5px] text-slate-700 dark:text-zinc-300">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-azure-600 dark:bg-white" /> Customer
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-azure-500 dark:bg-zinc-300" /> Account
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-600 dark:bg-rose-400" /> Device
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-600 dark:bg-zinc-400" /> Merchant
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3.5 h-0.5 bg-amber-500" /> Transfer
          </span>
          <button
            type="button"
            onClick={() => setNodes(computeLayout(rawNodes, rawEdges))}
            className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 text-slate-700 dark:text-zinc-200 hover:bg-white dark:hover:bg-zinc-800 transition"
          >
            <RotateCcw className="w-3 h-3" /> Reset
          </button>
        </div>
      </div>

      <div className="relative bg-white/35 dark:bg-black/65">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full h-[390px] block select-none"
          onMouseMove={handleMouseMove}
          onMouseUp={() => setDraggingId(null)}
          onMouseLeave={() => setDraggingId(null)}
          onClick={() => setSelectedId(null)}
        >
          <defs>
            <pattern id="grid-bg" width="24" height="24" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill={darkMode ? "#27272A" : "#93C5FD"} opacity="0.55" />
            </pattern>
            {(Object.keys(EDGE_PALETTE) as Array<GraphEdge["type"]>).map((etype) => (
              <marker
                key={etype}
                id={`mk-${etype}`}
                viewBox="0 0 10 10"
                refX="23"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill={EDGE_PALETTE[etype]} />
              </marker>
            ))}
          </defs>

          <rect width={W} height={H} fill="url(#grid-bg)" />

          {validEdges.map((e, i) => {
            const a = byId[e.source];
            const b = byId[e.target];
            const color = darkMode && e.type === "OWNS" ? "#A1A1AA" : EDGE_PALETTE[e.type];
            return (
              <g key={`${e.source}-${e.target}-${i}`}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={color}
                  strokeWidth={e.type === "TRANSFER" ? 2.4 : 1.5}
                  strokeOpacity={e.type === "TRANSFER" ? 0.92 : 0.55}
                  strokeDasharray={e.type === "USES_DEVICE" ? "5,4" : undefined}
                  markerEnd={e.type === "TRANSFER" || e.type === "MERCHANT_TXN" ? `url(#mk-${e.type})` : undefined}
                />
                <text
                  x={(a.x + b.x) / 2}
                  y={(a.y + b.y) / 2 - 5}
                  textAnchor="middle"
                  fontSize="10"
                  fontFamily="-apple-system, BlinkMacSystemFont, SF Pro Display, sans-serif"
                  fontWeight="600"
                  fill={e.type === "TRANSFER" ? (darkMode ? "#FBBF24" : "#B45309") : darkMode ? "#A1A1AA" : "#334155"}
                >
                  {e.label}
                </text>
              </g>
            );
          })}

          {nodes.map((n) => {
            const pal = NODE_PALETTE[n.type];
            const stroke = darkMode ? pal.dark : pal.light;
            const r = n.type === "ACCOUNT" ? (n.is_primary ? 20 : 17) : 14;
            const isSel = selectedId === n.id;

            return (
              <g
                key={n.id}
                transform={`translate(${n.x.toFixed(1)}, ${n.y.toFixed(1)})`}
                style={{ cursor: draggingId === n.id ? "grabbing" : "grab" }}
                onMouseDown={(ev) => {
                  ev.stopPropagation();
                  setDraggingId(n.id);
                }}
                onClick={(ev) => {
                  ev.stopPropagation();
                  setSelectedId(n.id);
                }}
              >
                {n.is_primary && (
                  <circle
                    r={r + 6}
                    fill="none"
                    stroke={darkMode ? "#FFFFFF" : "#0A66E6"}
                    strokeWidth="1.5"
                    strokeDasharray="3,3"
                  />
                )}
                <circle
                  r={r}
                  fill={darkMode ? "#09090B" : "#FFFFFF"}
                  stroke={isSel ? (darkMode ? "#FFFFFF" : "#0A66E6") : stroke}
                  strokeWidth={isSel || n.risk === "HIGH" ? 3 : 2}
                />
                <text
                  textAnchor="middle"
                  dy="0.35em"
                  fontSize="9.5"
                  fontWeight="700"
                  fontFamily="SF Mono, JetBrains Mono, monospace"
                  fill={stroke}
                >
                  {pal.short}
                </text>
                <text
                  y={r + 14}
                  textAnchor="middle"
                  fontSize="10.5"
                  fontWeight="600"
                  fill={darkMode ? "#FAFAFA" : "#0F172A"}
                >
                  {n.label.length > 20 ? `${n.label.slice(0, 18)}..` : n.label}
                </text>
              </g>
            );
          })}
        </svg>

        {selectedNode && (
          <div className="liquid-glass absolute bottom-3 left-3 rounded-xl p-3 max-w-xs text-xs">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="font-mono font-semibold text-slate-900 dark:text-white">{selectedNode.id}</span>
              <Badge variant={selectedNode.risk === "HIGH" ? "HIGH" : "BLUE"}>{selectedNode.type}</Badge>
            </div>
            <div className="font-semibold text-slate-800 dark:text-zinc-100">{selectedNode.label}</div>
            <div className="text-slate-600 dark:text-zinc-400 mt-0.5">{selectedNode.sublabel}</div>
            <div className="text-slate-500 dark:text-zinc-500 mt-1.5 ios-num text-[11px]">
              {selectedConnections} linked edge(s)
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
