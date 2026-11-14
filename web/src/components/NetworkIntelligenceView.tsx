import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowLeftRight,
  ArrowRight,
  ChevronRight,
  Compass,
  CornerDownRight,
  Crosshair,
  ExternalLink,
  Eye,
  FolderSearch,
  GitFork,
  Maximize2,
  Minimize2,
  RefreshCw,
  RotateCcw,
  Search,
  Share2,
  ShieldAlert,
  Smartphone,
  Store,
  Users,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { api } from "../api/client";
import type {
  EntityResolutionItem,
  NetworkCycle,
  NetworkGraphData,
  NetworkNode,
  NetworkOverviewMetrics,
  NetworkPathResult,
  NetworkPatternsResult,
  NetworkRiskAnalysis,
} from "../types/workbench";
import { Badge, fmtUSD, tierVariant } from "./Badge";
import { LiquidGlassSegmented, useRowGlassMagnifier } from "./LiquidGlassSurface";

interface NetworkIntelligenceViewProps {
  darkMode: boolean;
  onSelectCase?: (caseId: string) => void;
  onSelectAccount?: (accountId: string) => void;
  onSelectCustomer?: (customerId: string) => void;
  onSelectTransaction?: (txnId: string) => void;
}

type BottomTab = "patterns" | "cycles" | "paths" | "resolution" | "risk";

const ENTITY_COLORS: Record<NetworkNode["type"], { fill: string; stroke: string; label: string; icon: string }> = {
  CUSTOMER: { fill: "#0A66E6", stroke: "#60A5FA", label: "Customer", icon: "C" },
  ACCOUNT: { fill: "#0284C7", stroke: "#38BDF8", label: "Account", icon: "A" },
  MERCHANT: { fill: "#8B5CF6", stroke: "#C084FC", label: "Merchant", icon: "M" },
  DEVICE: { fill: "#F97316", stroke: "#FB923C", label: "Device", icon: "D" },
  TRANSACTION: { fill: "#475569", stroke: "#94A3B8", label: "Txn", icon: "T" },
};

const RISK_BORDER_COLORS: Record<NetworkNode["risk_classification"], string> = {
  CRITICAL: "#EF4444",
  HIGH: "#F59E0B",
  MEDIUM: "#38BDF8",
  LOW: "#10B981",
};

interface SimNode extends NetworkNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number | null;
  fy?: number | null;
}

export const NetworkIntelligenceView: React.FC<NetworkIntelligenceViewProps> = ({
  darkMode,
  onSelectCase,
  onSelectAccount,
  onSelectCustomer,
  onSelectTransaction,
}) => {
  // State: High-level metrics
  const [overview, setOverview] = useState<NetworkOverviewMetrics | null>(null);

  // State: Graph controls & data
  const [seedId, setSeedId] = useState<string | null>(null);
  const [depth, setDepth] = useState<number>(2);
  const graphLimit = 75;
  const [graphData, setGraphData] = useState<NetworkGraphData | null>(null);
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [loadingGraph, setLoadingGraph] = useState(false);

  // State: Filters
  const [activeTypes, setActiveTypes] = useState<Record<NetworkNode["type"], boolean>>({
    CUSTOMER: true,
    ACCOUNT: true,
    MERCHANT: true,
    DEVICE: true,
    TRANSACTION: true,
  });

  // State: Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<
    Array<{ id: string; label: string; type: string; risk_score: number; risk_classification: string; subtitle: string }>
  >([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);

  // State: Viewport (Pan & Zoom)
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // State: Bottom Analytical Tabs
  const [bottomTab, setBottomTab] = useState<BottomTab>("patterns");
  const [patterns, setPatterns] = useState<NetworkPatternsResult | null>(null);
  const [cycles, setCycles] = useState<NetworkCycle[]>([]);
  const [pathSource, setPathSource] = useState("");
  const [pathDest, setPathDest] = useState("");
  const [pathResult, setPathResult] = useState<NetworkPathResult | null>(null);
  const [loadingPath, setLoadingPath] = useState(false);
  const [resolutions, setResolutions] = useState<EntityResolutionItem[]>([]);
  const [riskAnalysis, setRiskAnalysis] = useState<NetworkRiskAnalysis | null>(null);
  const resMag = useRowGlassMagnifier();
  const riskMag = useRowGlassMagnifier();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  // Load High-Level Overview
  const fetchOverview = useCallback(async () => {
    try {
      const data = await api.getNetworkOverview();
      setOverview(data);
    } catch (e) {
      console.error("Failed to load network overview", e);
    }
  }, []);

  // Load Graph Data
  const fetchGraph = useCallback(
    async (seed?: string | null, d = depth, lim = graphLimit) => {
      try {
        setLoadingGraph(true);
        const data = await api.getNetworkGraph(seed || undefined, d, lim);
        setGraphData(data);

        // Compute Initial Concentric Layout for simulation
        const W = 950;
        const H = 550;
        const cx = W / 2;
        const cy = H / 2;

        const nodes: SimNode[] = data.nodes.map((n, idx) => {
          let r = 160;
          let angle = (2 * Math.PI * idx) / Math.max(1, data.nodes.length);
          if (n.type === "ACCOUNT") {
            r = 90;
          } else if (n.type === "CUSTOMER") {
            r = 180;
          } else if (n.type === "DEVICE") {
            r = 250;
          } else if (n.type === "MERCHANT") {
            r = 230;
          } else if (n.type === "TRANSACTION") {
            r = 130;
          }
          return {
            ...n,
            x: cx + r * Math.cos(angle) + (Math.random() - 0.5) * 30,
            y: cy + r * Math.sin(angle) + (Math.random() - 0.5) * 30,
            vx: 0,
            vy: 0,
          };
        });

        // Run simulation relaxation steps
        const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
        const edges = data.edges.filter((e) => byId[e.source] && byId[e.target]);

        for (let step = 0; step < 75; step++) {
          // Node repulsion
          for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
              const a = nodes[i];
              const b = nodes[j];
              const dx = b.x - a.x;
              const dy = b.y - a.y;
              const dist = Math.hypot(dx, dy) || 1;
              if (dist < 120) {
                const push = ((120 - dist) / dist) * 0.4;
                a.x -= dx * push;
                a.y -= dy * push;
                b.x += dx * push;
                b.y += dy * push;
              }
            }
          }
          // Edge attraction
          for (const e of edges) {
            const a = byId[e.source];
            const b = byId[e.target];
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const dist = Math.hypot(dx, dy) || 1;
            const targetDist = e.relationship === "TRANSFER" ? 120 : 90;
            const pull = ((dist - targetDist) / dist) * 0.05;
            a.x += dx * pull;
            a.y += dy * pull;
            b.x -= dx * pull;
            b.y -= dy * pull;
          }
          // Center gravity
          for (const n of nodes) {
            n.x += (cx - n.x) * 0.015;
            n.y += (cy - n.y) * 0.015;
            n.x = Math.max(60, Math.min(W - 60, n.x));
            n.y = Math.max(50, Math.min(H - 50, n.y));
          }
        }

        setSimNodes(nodes);
      } catch (e) {
        console.error("Failed to load network graph", e);
      } finally {
        setLoadingGraph(false);
      }
    },
    [depth, graphLimit]
  );

  // Load Bottom Tab Data
  const fetchPatterns = useCallback(async () => {
    try {
      const data = await api.getNetworkPatterns();
      setPatterns(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchCycles = useCallback(async () => {
    try {
      const data = await api.getNetworkCycles(15);
      setCycles(data.cycles);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchResolutions = useCallback(async () => {
    try {
      const data = await api.getEntityResolution(30);
      setResolutions(data.items);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchRiskAnalysis = useCallback(async (seed?: string | null) => {
    try {
      const data = await api.getNetworkRiskAnalysis(seed || undefined);
      setRiskAnalysis(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  // Initial mount
  useEffect(() => {
    fetchOverview();
    fetchGraph(null);
    fetchPatterns();
    fetchCycles();
    fetchResolutions();
    fetchRiskAnalysis(null);
  }, [fetchOverview, fetchGraph, fetchPatterns, fetchCycles, fetchResolutions, fetchRiskAnalysis]);

  // Handle Search Input Debounce
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setSearchResults([]);
      setShowSearchResults(false);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        setIsSearching(true);
        const res = await api.searchNetworkEntities(searchQuery.trim());
        setSearchResults(res.items);
        setShowSearchResults(true);
      } catch (e) {
        console.error(e);
      } finally {
        setIsSearching(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Trace Money Flow Path Action
  const handleTracePath = async (src?: string, dst?: string) => {
    const s = src || pathSource;
    const d = dst || pathDest;
    if (!s || !d) return;
    try {
      setLoadingPath(true);
      const res = await api.traceMoneyFlowPath(s.trim(), d.trim(), 4);
      setPathResult(res);
      setBottomTab("paths");
    } catch (e) {
      console.error("Path trace failed", e);
    } finally {
      setLoadingPath(false);
    }
  };

  // Node Map & Neighbors Calculation for Selection Highlighting
  const nodeById = useMemo(() => Object.fromEntries(simNodes.map((n) => [n.id, n])), [simNodes]);

  const visibleNodes = useMemo(() => {
    return simNodes.filter((n) => activeTypes[n.type]);
  }, [simNodes, activeTypes]);

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes]);

  const visibleEdges = useMemo(() => {
    if (!graphData) return [];
    return graphData.edges.filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target));
  }, [graphData, visibleNodeIds]);

  // Neighbors of selected node
  const neighborIds = useMemo(() => {
    if (!selectedNodeId) return new Set<string>();
    const set = new Set<string>();
    set.add(selectedNodeId);
    visibleEdges.forEach((e) => {
      if (e.source === selectedNodeId) set.add(e.target);
      if (e.target === selectedNodeId) set.add(e.source);
    });
    return set;
  }, [selectedNodeId, visibleEdges]);

  const selectedNode = selectedNodeId ? nodeById[selectedNodeId] : null;

  // Viewport navigation helpers
  const handleZoomIn = () => setZoom((z) => Math.min(2.5, z + 0.2));
  const handleZoomOut = () => setZoom((z) => Math.max(0.4, z - 0.2));
  const handleResetViewport = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };
  const handleFitViewport = () => {
    if (visibleNodes.length === 0) return;
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    visibleNodes.forEach((n) => {
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    });
    const padding = 60;
    const w = maxX - minX + padding * 2;
    const h = maxY - minY + padding * 2;
    const scaleX = 950 / Math.max(w, 200);
    const scaleY = 550 / Math.max(h, 200);
    const newZoom = Math.max(0.4, Math.min(1.8, Math.min(scaleX, scaleY)));
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    setZoom(newZoom);
    setPan({
      x: 950 / 2 - centerX * newZoom,
      y: 550 / 2 - centerY * newZoom,
    });
  };

  // Pan interaction
  const handleMouseDownSvg = (e: React.MouseEvent<SVGSVGElement>) => {
    if (e.target === svgRef.current || (e.target as HTMLElement).id === "net-bg-rect") {
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMoveSvg = (e: React.MouseEvent<SVGSVGElement>) => {
    if (isPanning) {
      setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
    } else if (draggingNodeId && svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const rawX = (e.clientX - rect.left - pan.x) / zoom;
      const rawY = (e.clientY - rect.top - pan.y) / zoom;
      setSimNodes((prev) =>
        prev.map((n) => (n.id === draggingNodeId ? { ...n, x: rawX, y: rawY, vx: 0, vy: 0 } : n))
      );
    }
  };

  const handleMouseUpSvg = () => {
    setIsPanning(false);
    setDraggingNodeId(null);
  };

  const handleWheelSvg = (e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    setZoom((z) => Math.max(0.4, Math.min(2.5, z * factor)));
  };

  // Node Drag Handlers
  const handleNodeMouseDown = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setDraggingNodeId(id);
    setSelectedNodeId(id);
  };

  const handleSelectSeed = (id: string) => {
    setSeedId(id);
    fetchGraph(id, depth);
    fetchRiskAnalysis(id);
    setShowSearchResults(false);
    setSearchQuery("");
  };

  return (
    <div
      ref={containerRef}
      className={`space-y-5 transition-all ${
        isFullscreen ? "fixed inset-0 z-50 p-6 overflow-y-auto bg-slate-950/95 backdrop-blur-2xl" : ""
      }`}
    >
      {/* 1. Header Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="liquid-glass rounded-2xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400">
            <span className="text-[11px] font-semibold tracking-wider uppercase">Entities</span>
            <Users className="w-3.5 h-3.5 text-azure-600 dark:text-sky-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl sm:text-2xl font-bold text-slate-950 dark:text-white ios-num">
              {(overview?.total_customers ?? 5000) + (overview?.total_accounts ?? 7000)}
            </span>
            <span className="text-[10px] text-slate-500 dark:text-zinc-400">active</span>
          </div>
          <div className="mt-1 text-[10px] text-slate-500 dark:text-zinc-400">
            {overview?.total_customers?.toLocaleString() ?? "5,000"} Cus • {overview?.total_accounts?.toLocaleString() ?? "7,000"} Accts
          </div>
        </div>

        <div className="liquid-glass rounded-2xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400">
            <span className="text-[11px] font-semibold tracking-wider uppercase">Transfers</span>
            <ArrowLeftRight className="w-3.5 h-3.5 text-sky-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl sm:text-2xl font-bold text-slate-950 dark:text-white ios-num">
              {overview?.total_transfers?.toLocaleString() ?? "4,640"}
            </span>
            <span className="text-[10px] text-slate-500 dark:text-zinc-400">links</span>
          </div>
          <div className="mt-1 text-[10px] text-sky-600 dark:text-sky-400 font-medium">
            Vol: {fmtUSD(overview?.total_transfer_volume ?? 22849000)}
          </div>
        </div>

        <div className="liquid-glass rounded-2xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400">
            <span className="text-[11px] font-semibold tracking-wider uppercase">Merchants</span>
            <Store className="w-3.5 h-3.5 text-purple-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl sm:text-2xl font-bold text-slate-950 dark:text-white ios-num">
              {overview?.total_merchants ?? 400}
            </span>
            <span className="text-[10px] text-slate-500 dark:text-zinc-400">destinations</span>
          </div>
          <div className="mt-1 text-[10px] text-slate-500 dark:text-zinc-400">57,000+ purchases linked</div>
        </div>

        <div className="liquid-glass rounded-2xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400">
            <span className="text-[11px] font-semibold tracking-wider uppercase">Devices</span>
            <Smartphone className="w-3.5 h-3.5 text-orange-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl sm:text-2xl font-bold text-slate-950 dark:text-white ios-num">
              {overview?.total_devices?.toLocaleString() ?? "6,247"}
            </span>
            <span className="text-[10px] text-slate-500 dark:text-zinc-400">fingerprints</span>
          </div>
          <div className="mt-1 text-[10px] text-orange-600 dark:text-orange-400 font-medium">Root/Emulators indexed</div>
        </div>

        <div className="liquid-glass rounded-2xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400">
            <span className="text-[11px] font-semibold tracking-wider uppercase">Circular Loops</span>
            <RotateCcw className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl sm:text-2xl font-bold text-amber-600 dark:text-amber-400 ios-num">
              {overview?.detected_cycles ?? cycles.length}
            </span>
            <span className="text-[10px] text-amber-600 dark:text-amber-400 font-semibold">Cycles</span>
          </div>
          <div className="mt-1 text-[10px] text-slate-500 dark:text-zinc-400">Closed fund loops identified</div>
        </div>

        <div className="liquid-glass rounded-2xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 dark:text-zinc-400">
            <span className="text-[11px] font-semibold tracking-wider uppercase">Collusion Rings</span>
            <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="text-xl sm:text-2xl font-bold text-rose-600 dark:text-rose-400 ios-num">
              {overview?.collusion_clusters ?? 12}
            </span>
            <span className="text-[10px] text-rose-600 dark:text-rose-400 font-semibold">Flagged</span>
          </div>
          <div className="mt-1 text-[10px] text-slate-500 dark:text-zinc-400">Device/Entity clusters</div>
        </div>
      </div>

      {/* 2. Interactive Search & Controls Toolbar */}
      <div className="liquid-glass rounded-2xl p-3.5 flex flex-wrap items-center justify-between gap-3">
        {/* Left: Entity Search with Autocomplete */}
        <div className="relative flex-1 min-w-[260px] max-w-md">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Customer, Account, Device or Txn ID..."
              className="w-full h-8 pl-8 pr-8 text-xs bg-white/50 dark:bg-black/40 border border-slate-200 dark:border-white/10 rounded-full text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-azure-500"
            />
            {isSearching && (
              <RefreshCw className="w-3 h-3 text-azure-500 animate-spin absolute right-3 top-1/2 -translate-y-1/2" />
            )}
          </div>

          {showSearchResults && (
            <div className="absolute top-10 left-0 right-0 z-40 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-xl border border-slate-200 dark:border-white/15 rounded-xl shadow-2xl max-h-72 overflow-y-auto p-1.5 space-y-1">
              <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                Matching Entities ({searchResults.length})
              </div>
              {searchResults.length === 0 ? (
                <div className="px-3 py-2 text-xs text-slate-400">No entities match query</div>
              ) : (
                searchResults.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleSelectSeed(item.id)}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-azure-500/10 flex items-center justify-between text-xs transition"
                  >
                    <div>
                      <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: ENTITY_COLORS[item.type as NetworkNode["type"]]?.fill }}
                        />
                        <span>{item.label}</span>
                        <span className="font-mono text-[10px] text-slate-400">({item.id})</span>
                      </div>
                      <div className="text-[10px] text-slate-500 dark:text-zinc-400">{item.subtitle}</div>
                    </div>
                    <Badge variant={tierVariant(item.risk_classification)}>{item.risk_classification}</Badge>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Center: Depth Selector & Node Type Filter Toggles */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Depth Selector */}
          <div className="inline-flex items-center gap-1 bg-white/40 dark:bg-black/30 p-1 rounded-full border border-slate-200 dark:border-white/10 text-xs">
            <span className="px-2 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Depth:</span>
            {[1, 2, 3].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => {
                  setDepth(d);
                  fetchGraph(seedId, d);
                }}
                className={`px-2.5 py-0.5 rounded-full text-xs font-semibold transition ${
                  depth === d
                    ? "bg-azure-600 text-white shadow-sm"
                    : "text-slate-600 dark:text-zinc-300 hover:text-slate-950 dark:hover:text-white"
                }`}
              >
                {d} {d === 1 ? "Hop" : "Hops"}
              </button>
            ))}
          </div>

          {/* Entity Type Visibility Filters */}
          <div className="inline-flex items-center gap-1 bg-white/40 dark:bg-black/30 p-1 rounded-full border border-slate-200 dark:border-white/10 text-xs">
            {(Object.keys(ENTITY_COLORS) as Array<NetworkNode["type"]>).map((type) => {
              const active = activeTypes[type];
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => setActiveTypes((prev) => ({ ...prev, [type]: !prev[type] }))}
                  className={`px-2 py-0.5 rounded-full text-[10.5px] font-medium flex items-center gap-1.5 transition ${
                    active
                      ? "bg-white/80 dark:bg-white/10 text-slate-900 dark:text-white shadow-xs"
                      : "opacity-40 line-through text-slate-400"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: ENTITY_COLORS[type].fill }} />
                  <span>{ENTITY_COLORS[type].label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Graph Action Controls */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleZoomIn}
            title="Zoom In"
            className="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-700 dark:text-zinc-200 hover:bg-white dark:hover:bg-zinc-800 transition"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleZoomOut}
            title="Zoom Out"
            className="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-700 dark:text-zinc-200 hover:bg-white dark:hover:bg-zinc-800 transition"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleFitViewport}
            title="Fit Viewport"
            className="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-700 dark:text-zinc-200 hover:bg-white dark:hover:bg-zinc-800 transition"
          >
            <Crosshair className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleResetViewport}
            title="Reset View"
            className="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-700 dark:text-zinc-200 hover:bg-white dark:hover:bg-zinc-800 transition"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          {seedId && (
            <button
              type="button"
              onClick={() => {
                setSeedId(null);
                fetchGraph(null, depth);
                fetchRiskAnalysis(null);
              }}
              title="Clear Seed & Reset Global Subgraph"
              className="px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30 hover:bg-rose-500/25 transition"
            >
              Clear Seed ({seedId})
            </button>
          )}
          <button
            type="button"
            onClick={() => setIsFullscreen((f) => !f)}
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
            className="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 flex items-center justify-center text-slate-700 dark:text-zinc-200 hover:bg-white dark:hover:bg-zinc-800 transition"
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* 3. Main Graph Viewport & Side Inspector Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 items-start">
        {/* Interactive SVG Canvas Area */}
        <div className="lg:col-span-3 liquid-glass rounded-2xl overflow-hidden relative border border-slate-200/80 dark:border-white/10">
          {/* Subgraph Header Ribbon */}
          <div className="px-4 py-2.5 border-b border-slate-200/60 dark:border-white/10 flex items-center justify-between text-xs bg-white/30 dark:bg-black/30">
            <div className="flex items-center gap-2">
              <GitFork className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              <span className="font-semibold text-slate-900 dark:text-white">
                {seedId ? `Seed Subgraph: ${seedId}` : "High-Risk Multi-Hop Subgraph"}
              </span>
              <span className="text-[11px] text-slate-500 dark:text-zinc-400">
                ({visibleNodes.length} nodes, {visibleEdges.length} edges)
              </span>
            </div>
            {loadingGraph && (
              <div className="flex items-center gap-1.5 text-azure-600 dark:text-sky-400 text-xs">
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>Relaxing network...</span>
              </div>
            )}
          </div>

          {/* SVG Graph Viewport */}
          <div className="relative bg-slate-50/50 dark:bg-black/75 cursor-grab active:cursor-grabbing select-none h-[560px]">
            <svg
              ref={svgRef}
              viewBox="0 0 950 560"
              className="w-full h-full block"
              onMouseDown={handleMouseDownSvg}
              onMouseMove={handleMouseMoveSvg}
              onMouseUp={handleMouseUpSvg}
              onWheel={handleWheelSvg}
            >
              <defs>
                {/* Background dot grid pattern */}
                <pattern id="net-grid" width="30" height="30" patternUnits="userSpaceOnUse">
                  <circle cx="2" cy="2" r="1.2" fill={darkMode ? "#3F3F46" : "#CBD5E1"} opacity="0.45" />
                </pattern>

                {/* Arrow markers */}
                <marker id="arrow-default" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 1 L 10 5 L 0 9 z" fill={darkMode ? "#71717A" : "#94A3B8"} />
                </marker>
                <marker id="arrow-transfer" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#F59E0B" />
                </marker>
                <marker id="arrow-highlight" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
                  <path d="M 0 0.5 L 10 5 L 0 9.5 z" fill="#38BDF8" />
                </marker>
              </defs>

              {/* Grid Background - Click deselects active node */}
              <rect
                id="net-bg-rect"
                width="950"
                height="560"
                fill="url(#net-grid)"
                onClick={() => setSelectedNodeId(null)}
              />

              {/* Pan & Zoom Transform Group */}
              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                {/* 1. EDGES */}
                <g className="edges">
                  {visibleEdges.map((edge) => {
                    const sourceNode = nodeById[edge.source];
                    const targetNode = nodeById[edge.target];
                    if (!sourceNode || !targetNode) return null;

                    const isHighlighted =
                      selectedNodeId &&
                      (edge.source === selectedNodeId || edge.target === selectedNodeId);
                    const isDimmed = selectedNodeId && !isHighlighted;
                    const isTransfer = edge.relationship === "TRANSFER";

                    const midX = (sourceNode.x + targetNode.x) / 2;
                    const midY = (sourceNode.y + targetNode.y) / 2;

                    let strokeColor = darkMode ? "#52525B" : "#CBD5E1";
                    let markerId = "url(#arrow-default)";
                    let strokeWidth = 1.4;

                    if (isHighlighted) {
                      strokeColor = "#38BDF8";
                      markerId = "url(#arrow-highlight)";
                      strokeWidth = 2.8;
                    } else if (isTransfer) {
                      strokeColor = "#F59E0B";
                      markerId = "url(#arrow-transfer)";
                      strokeWidth = 2.0;
                    }

                    return (
                      <g key={edge.id} className="transition-opacity duration-300" opacity={isDimmed ? 0.18 : 1}>
                        <line
                          x1={sourceNode.x}
                          y1={sourceNode.y}
                          x2={targetNode.x}
                          y2={targetNode.y}
                          stroke={strokeColor}
                          strokeWidth={strokeWidth}
                          strokeDasharray={edge.relationship === "USES_DEVICE" ? "4 3" : undefined}
                          markerEnd={markerId}
                        />

                        {/* Midpoint Amount Pill on Transfer / Payment Edges */}
                        {(isTransfer || isHighlighted) && edge.amount ? (
                          <g transform={`translate(${midX}, ${midY})`}>
                            <rect
                              x="-26"
                              y="-8"
                              width="52"
                              height="16"
                              rx="8"
                              fill={darkMode ? "#18181B" : "#FFFFFF"}
                              stroke={isHighlighted ? "#38BDF8" : "#F59E0B"}
                              strokeWidth="1"
                              opacity="0.95"
                            />
                            <text
                              x="0"
                              y="3"
                              textAnchor="middle"
                              className="text-[8.5px] font-bold font-mono"
                              fill={isHighlighted ? "#38BDF8" : "#F59E0B"}
                            >
                              {fmtUSD(edge.amount).split(".")[0]}
                            </text>
                          </g>
                        ) : null}
                      </g>
                    );
                  })}
                </g>

                {/* 2. NODES */}
                <g className="nodes">
                  {visibleNodes.map((node) => {
                    const isSelected = selectedNodeId === node.id;
                    const isNeighbor = neighborIds.has(node.id);
                    const isDimmed = selectedNodeId && !isSelected && !isNeighbor;

                    const color = ENTITY_COLORS[node.type] || ENTITY_COLORS.ACCOUNT;
                    const riskBorder = RISK_BORDER_COLORS[node.risk_classification] || "#38BDF8";
                    const radius = node.type === "ACCOUNT" ? 17 : node.type === "CUSTOMER" ? 20 : 15;

                    return (
                      <g
                        key={node.id}
                        transform={`translate(${node.x}, ${node.y})`}
                        className="cursor-pointer transition-opacity duration-300"
                        opacity={isDimmed ? 0.22 : 1}
                        onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedNodeId(node.id);
                        }}
                        onMouseEnter={() => setHoveredNodeId(node.id)}
                        onMouseLeave={() => setHoveredNodeId(null)}
                        onDoubleClick={(e) => {
                          e.stopPropagation();
                          handleSelectSeed(node.id);
                        }}
                      >
                        {/* Outer Selection / Risk Ring */}
                        <circle
                          r={radius + (isSelected ? 7 : 4)}
                          fill="none"
                          stroke={isSelected ? "#38BDF8" : riskBorder}
                          strokeWidth={isSelected ? 2.5 : 1.5}
                          strokeDasharray={isSelected ? "4 2" : undefined}
                          opacity={isSelected || node.risk_score > 60 ? 1 : 0.65}
                        />

                        {/* Node Main Body */}
                        <circle
                          r={radius}
                          fill={color.fill}
                          stroke="#FFFFFF"
                          strokeWidth="1.8"
                          className="drop-shadow-md"
                        />

                        {/* Inner Entity Symbol */}
                        <text
                          textAnchor="middle"
                          dy="4"
                          fill="#FFFFFF"
                          className="text-[10px] font-extrabold select-none pointer-events-none"
                        >
                          {color.icon}
                        </text>

                        {/* Node Label Below */}
                        <text
                          y={radius + 13}
                          textAnchor="middle"
                          className={`text-[9.5px] font-semibold select-none pointer-events-none ${
                            isSelected
                              ? "fill-sky-500 font-bold"
                              : darkMode
                              ? "fill-zinc-200"
                              : "fill-slate-800"
                          }`}
                        >
                          {node.label.length > 14 ? `${node.label.slice(0, 12)}…` : node.label}
                        </text>

                        {/* Sub-ID below label */}
                        <text
                          y={radius + 23}
                          textAnchor="middle"
                          className="text-[8px] font-mono fill-slate-400 select-none pointer-events-none"
                        >
                          {node.id}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </g>
            </svg>

            {/* Hover Tooltip Overlay */}
            {hoveredNodeId && nodeById[hoveredNodeId] && (
              <div className="absolute bottom-3 left-3 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-md border border-slate-200 dark:border-white/15 px-3 py-2 rounded-xl shadow-xl text-xs pointer-events-none z-30">
                <div className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: ENTITY_COLORS[nodeById[hoveredNodeId].type]?.fill }}
                  />
                  <span>{nodeById[hoveredNodeId].label}</span>
                  <span className="font-mono text-[10px] text-slate-400">({nodeById[hoveredNodeId].id})</span>
                </div>
                <div className="text-[10.5px] text-slate-500 dark:text-zinc-400 mt-0.5 flex items-center gap-2">
                  <span>Type: {nodeById[hoveredNodeId].type}</span>
                  <span>•</span>
                  <span>Risk Score: {nodeById[hoveredNodeId].risk_score}/100</span>
                  <span>•</span>
                  <Badge variant={tierVariant(nodeById[hoveredNodeId].risk_classification)}>
                    {nodeById[hoveredNodeId].risk_classification}
                  </Badge>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Entity Intelligence Inspector Panel */}
        <div className="liquid-glass rounded-2xl p-4 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-white/50 dark:border-white/10">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white flex items-center gap-1.5">
              <Eye className="w-3.5 h-3.5 text-azure-600 dark:text-sky-400" />
              <span>Entity Intelligence</span>
            </h3>
            {selectedNode && (
              <div className="flex items-center gap-2">
                <Badge variant={tierVariant(selectedNode.risk_classification)}>
                  {selectedNode.risk_classification}
                </Badge>
                <button
                  type="button"
                  onClick={() => setSelectedNodeId(null)}
                  title="Deselect entity"
                  className="w-5 h-5 rounded-full hover:bg-slate-200 dark:hover:bg-zinc-800 text-slate-400 hover:text-slate-700 dark:hover:text-white flex items-center justify-center transition"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {selectedNode ? (
            <div className="space-y-4 text-xs">
              {/* Entity Identity Box */}
              <div className="p-3 rounded-xl bg-white/40 dark:bg-white/5 border border-slate-200/60 dark:border-white/10 space-y-1.5">
                <div className="font-bold text-sm text-slate-900 dark:text-white">{selectedNode.label}</div>
                <div className="font-mono text-[11px] text-slate-500 dark:text-zinc-400">{selectedNode.id}</div>
                <div className="flex items-center gap-2 pt-1 text-[11px]">
                  <span className="px-2 py-0.5 rounded-md font-semibold text-white text-[10px]" style={{ backgroundColor: ENTITY_COLORS[selectedNode.type]?.fill }}>
                    {selectedNode.type}
                  </span>
                  <span className="text-slate-500 dark:text-zinc-400">Risk Score:</span>
                  <span className="font-bold ios-num text-rose-600 dark:text-rose-400">{selectedNode.risk_score}/100</span>
                </div>
              </div>

              {/* Topology / Degree Metrics */}
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded-xl bg-white/30 dark:bg-white/5 border border-slate-200/50 dark:border-white/5">
                  <div className="text-[10px] text-slate-500 uppercase font-semibold">Incoming Edges</div>
                  <div className="text-base font-bold text-slate-900 dark:text-white ios-num mt-0.5">
                    {selectedNode.in_degree}
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-white/30 dark:bg-white/5 border border-slate-200/50 dark:border-white/5">
                  <div className="text-[10px] text-slate-500 uppercase font-semibold">Outgoing Edges</div>
                  <div className="text-base font-bold text-slate-900 dark:text-white ios-num mt-0.5">
                    {selectedNode.out_degree}
                  </div>
                </div>
              </div>

              {/* Specific Metadata Attributes */}
              <div className="space-y-1.5">
                <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Entity Attributes</div>
                <div className="p-3 rounded-xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-sm border border-white/60 dark:border-white/10 space-y-1 text-[11.5px]">
                  {Object.entries(selectedNode.metadata || {}).map(([k, v]) => (
                    <div key={k} className="flex justify-between items-center py-1 border-b border-white/30 dark:border-white/5 last:border-0">
                      <span className="text-slate-500 dark:text-zinc-400 capitalize">{k.replace(/_/g, " ")}:</span>
                      <span className="font-semibold text-slate-900 dark:text-white font-mono text-[11px]">
                        {typeof v === "number" && k.toLowerCase().includes("balance") ? fmtUSD(v) : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Quick Actions */}
              <div className="space-y-2 pt-2">
                <button
                  type="button"
                  onClick={() => handleSelectSeed(selectedNode.id)}
                  className="w-full py-2 px-3 rounded-xl bg-azure-600 hover:bg-azure-700 text-white font-semibold flex items-center justify-center gap-1.5 transition text-xs shadow-sm"
                >
                  <Crosshair className="w-3.5 h-3.5" />
                  <span>Seed &amp; Expand Subgraph</span>
                </button>

                {selectedNode.type === "ACCOUNT" && (
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setPathSource(selectedNode.id);
                        setBottomTab("paths");
                      }}
                      className="py-1.5 px-2.5 rounded-xl bg-white/60 dark:bg-white/10 hover:bg-white dark:hover:bg-zinc-800 border border-white/60 dark:border-white/15 text-slate-800 dark:text-zinc-200 font-medium text-[11px] transition text-center"
                    >
                      Set As Source
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setPathDest(selectedNode.id);
                        setBottomTab("paths");
                      }}
                      className="py-1.5 px-2.5 rounded-xl bg-white/60 dark:bg-white/10 hover:bg-white dark:hover:bg-zinc-800 border border-white/60 dark:border-white/15 text-slate-800 dark:text-zinc-200 font-medium text-[11px] transition text-center"
                    >
                      Set As Dest
                    </button>
                  </div>
                )}

                {/* Drill-down cross-navigation links */}
                {selectedNode.type === "CUSTOMER" && onSelectCustomer && (
                  <button
                    type="button"
                    onClick={() => onSelectCustomer(selectedNode.id)}
                    className="w-full py-1.5 px-3 rounded-lg border border-azure-500/40 text-azure-600 dark:text-sky-400 hover:bg-azure-500/10 text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                  >
                    <span>View Customer Profile</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                )}

                {selectedNode.type === "ACCOUNT" && onSelectAccount && (
                  <button
                    type="button"
                    onClick={() => onSelectAccount(selectedNode.id)}
                    className="w-full py-1.5 px-3 rounded-lg border border-sky-500/40 text-sky-600 dark:text-sky-400 hover:bg-sky-500/10 text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                  >
                    <span>View Account Ledger</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                )}

                {selectedNode.type === "TRANSACTION" && onSelectTransaction && (
                  <button
                    type="button"
                    onClick={() => onSelectTransaction(selectedNode.id)}
                    className="w-full py-1.5 px-3 rounded-lg border border-slate-400/40 text-slate-700 dark:text-zinc-300 hover:bg-slate-500/10 text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                  >
                    <span>Inspect Transaction Detail</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                )}

                {onSelectCase && (
                  <button
                    type="button"
                    onClick={() => onSelectCase(selectedNode.metadata?.active_case_id || "CASE-2026-0001")}
                    className="w-full py-1.5 px-3 rounded-lg border border-purple-500/40 text-purple-600 dark:text-purple-400 hover:bg-purple-500/10 text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                  >
                    <FolderSearch className="w-3 h-3" />
                    <span>Open Case Dossier</span>
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="py-16 text-center text-slate-400 space-y-2">
              <Compass className="w-8 h-8 mx-auto text-slate-300 dark:text-zinc-600" />
              <div className="font-semibold text-xs">No Entity Selected</div>
              <p className="text-[11px] max-w-[200px] mx-auto text-slate-500 dark:text-zinc-500">
                Click any node on the graph or search an ID above to inspect its multi-hop relations.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 4. Bottom Analytical Investigation Deck (5 Specialized Tabs) */}
      <div className="liquid-glass rounded-2xl overflow-hidden shadow-[0_12px_36px_rgba(0,0,0,0.18)]">
        {/* Navigation Tabs Header with Liquid Glass Slider (matching Overview) */}
        <div className="px-4 py-3 border-b border-white/50 dark:border-white/10 flex items-center justify-between overflow-x-auto gap-3 bg-white/25 dark:bg-white/[0.03] backdrop-blur-xl">
          <LiquidGlassSegmented<BottomTab>
            value={bottomTab}
            onChange={setBottomTab}
            options={[
              {
                value: "patterns",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <Activity className="w-3.5 h-3.5 text-amber-500" />
                    <span>Suspicious Patterns</span>
                  </span>
                ),
              },
              {
                value: "cycles",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <RotateCcw className="w-3.5 h-3.5 text-amber-500" />
                    <span>Circular Transfers ({cycles.length})</span>
                  </span>
                ),
              },
              {
                value: "paths",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <ArrowLeftRight className="w-3.5 h-3.5 text-sky-500" />
                    <span>Fund Flow Paths</span>
                  </span>
                ),
              },
              {
                value: "resolution",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <Users className="w-3.5 h-3.5 text-purple-500" />
                    <span>Entity Resolution ({resolutions.length})</span>
                  </span>
                ),
              },
              {
                value: "risk",
                label: (
                  <span className="flex items-center gap-1.5 whitespace-nowrap">
                    <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
                    <span>Network Risk Analysis</span>
                  </span>
                ),
              },
            ]}
          />
        </div>

        {/* Tab 1: Suspicious Patterns (Concentration, Rapid Dispersion, Collusion) */}
        {bottomTab === "patterns" && (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Fan-in Concentration */}
              <div className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-[0_4px_20px_rgba(0,0,0,0.04)] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                    <CornerDownRight className="w-3.5 h-3.5 text-amber-500" />
                    <span>Fan-In Concentration</span>
                  </div>
                  <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-400">Layering In</span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                  Multiple distinct source accounts transferring funds into a single destination account.
                </p>
                <div className="space-y-2">
                  {patterns?.fan_in_concentration.slice(0, 3).map((item) => (
                    <div
                      key={item.destination_account}
                      className="p-2.5 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/60 dark:border-white/10 hover:border-azure-500/40 dark:hover:border-sky-400/30 transition flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="font-semibold text-slate-900 dark:text-white font-mono text-[11px]">
                          {item.destination_account}
                        </div>
                        <div className="text-[10px] text-slate-500 dark:text-zinc-400">
                          {item.customer_name} • {item.inflow_sources} sources
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-amber-600 dark:text-amber-400 font-mono text-[11px]">
                          {fmtUSD(item.total_inflow_amount)}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSelectSeed(item.destination_account)}
                          className="text-[10px] text-azure-600 dark:text-sky-400 hover:underline font-semibold"
                        >
                          Focus Graph
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Rapid Fund Dispersion */}
              <div className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-[0_4px_20px_rgba(0,0,0,0.04)] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                    <Share2 className="w-3.5 h-3.5 text-sky-500" />
                    <span>Rapid Fund Dispersion</span>
                  </div>
                  <span className="text-[10px] font-semibold text-sky-600 dark:text-sky-400">Fan-Out</span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                  Single origin account rapidly dispersing funds into multiple beneficiary accounts.
                </p>
                <div className="space-y-2">
                  {patterns?.rapid_dispersion.slice(0, 3).map((item) => (
                    <div
                      key={item.origin_account}
                      className="p-2.5 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/60 dark:border-white/10 hover:border-azure-500/40 dark:hover:border-sky-400/30 transition flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="font-semibold text-slate-900 dark:text-white font-mono text-[11px]">
                          {item.origin_account}
                        </div>
                        <div className="text-[10px] text-slate-500 dark:text-zinc-400">
                          {item.customer_name} • {item.outflow_targets} targets
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-sky-600 dark:text-sky-400 font-mono text-[11px]">
                          {fmtUSD(item.total_outflow_amount)}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSelectSeed(item.origin_account)}
                          className="text-[10px] text-azure-600 dark:text-sky-400 hover:underline font-semibold"
                        >
                          Focus Graph
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Shared Device Collusion Rings */}
              <div className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-[0_4px_20px_rgba(0,0,0,0.04)] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                    <Smartphone className="w-3.5 h-3.5 text-orange-500" />
                    <span>Shared Hardware Rings</span>
                  </div>
                  <span className="text-[10px] font-semibold text-rose-600 dark:text-rose-400">Multi-Account</span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                  Devices with root/emulator indicators shared across multiple customer identities.
                </p>
                <div className="space-y-2">
                  {patterns?.shared_device_clusters.slice(0, 3).map((item) => (
                    <div
                      key={item.device_id}
                      className="p-2.5 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/60 dark:border-white/10 hover:border-azure-500/40 dark:hover:border-sky-400/30 transition flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="font-semibold text-slate-900 dark:text-white font-mono text-[11px]">
                          {item.device_id}
                        </div>
                        <div className="text-[10px] text-orange-600 dark:text-orange-400">
                          {item.os} • {item.is_emulator ? "Emulator" : "Device"} • {item.shared_customers_count} cus
                        </div>
                      </div>
                      <div className="text-right">
                        <button
                          type="button"
                          onClick={() => handleSelectSeed(item.device_id)}
                          className="text-[10px] text-azure-600 dark:text-sky-400 hover:underline font-semibold"
                        >
                          Inspect Ring
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Circular Transfers (Cycles) */}
        {bottomTab === "cycles" && (
          <div className="p-4 space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
              <span>Closed transfer loops where money returns to an initiating account:</span>
              <span className="font-semibold text-slate-900 dark:text-white">{cycles.length} loops detected</span>
            </div>

            {cycles.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">No circular transfer loops detected</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {cycles.map((c) => (
                  <div
                    key={c.cycle_id}
                    className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-[0_4px_20px_rgba(0,0,0,0.04)] space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-mono font-bold text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>{c.cycle_id}</span>
                        <span className="text-[10px] font-normal text-slate-400">({c.length} Hops)</span>
                      </div>
                      <Badge variant="HIGH">{c.confidence}</Badge>
                    </div>

                    {/* Cycle Nodes Path Flow */}
                    <div className="flex items-center gap-1.5 flex-wrap text-xs font-mono py-1">
                      {c.nodes.map((node, i) => (
                        <React.Fragment key={i}>
                          <button
                            type="button"
                            onClick={() => handleSelectSeed(node)}
                            className="px-2.5 py-1 rounded-full bg-white/70 dark:bg-white/10 backdrop-blur-sm border border-white/60 dark:border-white/15 hover:border-azure-500 hover:bg-white dark:hover:bg-white/20 transition text-[11px] font-semibold text-slate-800 dark:text-zinc-200"
                          >
                            {node}
                          </button>
                          {i < c.nodes.length - 1 && <ArrowRight className="w-3 h-3 text-amber-500 shrink-0" />}
                        </React.Fragment>
                      ))}
                    </div>

                    <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-white/40 dark:border-white/10">
                      <div className="text-slate-500 dark:text-zinc-400">
                        Total Loop Volume:{" "}
                        <span className="font-bold text-slate-900 dark:text-white font-mono">
                          {fmtUSD(c.total_cycle_volume)}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleSelectSeed(c.nodes[0])}
                        className="text-xs font-semibold text-azure-600 dark:text-sky-400 hover:underline flex items-center gap-1"
                      >
                        <span>Focus on Graph</span>
                        <ChevronRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Fund Flow Paths Tracer */}
        {bottomTab === "paths" && (
          <div className="p-4 space-y-4">
            {/* Input Picker Bar */}
            <div className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm flex flex-wrap items-center gap-3">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Source Account</label>
                <input
                  type="text"
                  value={pathSource}
                  onChange={(e) => setPathSource(e.target.value)}
                  placeholder="e.g. ACC-CUS-000003-01"
                  className="w-full h-8 px-3 text-xs bg-white/80 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 rounded-xl text-slate-900 dark:text-white font-mono focus:outline-none focus:border-azure-500"
                />
              </div>

              <ArrowRight className="w-4 h-4 text-slate-400 mt-4 shrink-0 hidden sm:block" />

              <div className="flex-1 min-w-[200px]">
                <label className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Destination Account</label>
                <input
                  type="text"
                  value={pathDest}
                  onChange={(e) => setPathDest(e.target.value)}
                  placeholder="e.g. ACC-CUS-000588-01"
                  className="w-full h-8 px-3 text-xs bg-white/80 dark:bg-black/40 backdrop-blur-sm border border-white/60 dark:border-white/15 rounded-xl text-slate-900 dark:text-white font-mono focus:outline-none focus:border-azure-500"
                />
              </div>

              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => handleTracePath()}
                  disabled={loadingPath || !pathSource || !pathDest}
                  className="h-8 px-4 rounded-xl bg-azure-600 hover:bg-azure-700 disabled:opacity-50 text-white font-semibold text-xs transition flex items-center gap-1.5 shadow-sm"
                >
                  {loadingPath ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <GitFork className="w-3.5 h-3.5" />}
                  <span>Trace Money Path</span>
                </button>
              </div>
            </div>

            {/* Quick Demo Pre-fills */}
            <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
              <span className="text-[11px]">Quick Pre-fills:</span>
              <button
                type="button"
                onClick={() => {
                  setPathSource("ACC-CUS-000003-01");
                  setPathDest("ACC-CUS-000588-01");
                  handleTracePath("ACC-CUS-000003-01", "ACC-CUS-000588-01");
                }}
                className="px-2.5 py-1 rounded-full bg-white/60 dark:bg-white/10 backdrop-blur-sm border border-white/60 dark:border-white/15 hover:border-azure-500 font-mono text-[10px] text-azure-600 dark:text-sky-400 transition"
              >
                3-Hop Chain (ACC-003 → ACC-588)
              </button>
            </div>

            {/* Path Result Card */}
            {pathResult && (
              <div className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/40 dark:border-white/10">
                  <div>
                    <div className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
                      <span>Directional Path Reconstruction</span>
                      <Badge variant="BLUE">{pathResult.flow_confidence}</Badge>
                    </div>
                    <div className="text-[11px] text-slate-500 dark:text-zinc-400 mt-0.5">
                      Found {pathResult.paths_found} transfer path(s) • {pathResult.shortest_path_hops} intermediate hops
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs">
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Transaction Volume</div>
                      <div className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                        {fmtUSD(pathResult.total_transaction_volume)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-sky-500">Estimated Unique Flow</div>
                      <div className="text-sm font-bold text-sky-600 dark:text-sky-400 font-mono">
                        {fmtUSD(pathResult.estimated_unique_flow)}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Step-by-Step Hop Sequence */}
                <div className="space-y-2">
                  {pathResult.paths.map((p, pIdx) => (
                    <div key={pIdx} className="space-y-2">
                      <div className="text-[11px] font-semibold text-slate-600 dark:text-zinc-300">
                        Path Route #{pIdx + 1}:
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                        {p.map((hop) => (
                          <div
                            key={hop.hop}
                            className="p-3 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/60 dark:border-white/10 space-y-1.5"
                          >
                            <div className="flex items-center justify-between text-[11px]">
                              <span className="font-bold text-slate-900 dark:text-white">Hop #{hop.hop}</span>
                              <span className="font-mono text-amber-600 dark:text-amber-400 font-bold">
                                {fmtUSD(hop.amount)}
                              </span>
                            </div>
                            <div className="font-mono text-[10.5px] text-slate-600 dark:text-zinc-300 flex items-center justify-between">
                              <span className="truncate max-w-[90px]">{hop.from_account}</span>
                              <ArrowRight className="w-3 h-3 text-slate-400 shrink-0" />
                              <span className="truncate max-w-[90px]">{hop.to_account}</span>
                            </div>
                            <div className="text-[9.5px] text-slate-400 flex justify-between pt-1 border-t border-white/30 dark:border-white/10">
                              <span>{hop.transfer_id}</span>
                              <span>{new Date(hop.initiated_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Entity Resolution (Confirmed vs Potential Matches) */}
        {bottomTab === "resolution" && (
          <div className="p-4 space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
              <span>Conservative entity matching across shared devices, contact details and addresses:</span>
              <span className="font-semibold text-slate-900 dark:text-white">{resolutions.length} clusters identified</span>
            </div>

            <div ref={resMag.containerRef} onMouseLeave={resMag.onContainerLeave} className="relative overflow-x-auto">
              {resMag.lensElement}
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-white/50 dark:border-white/10 text-slate-500 dark:text-zinc-400 text-[10px] uppercase font-bold tracking-wider">
                    <th className="py-2.5 px-3">Cluster</th>
                    <th className="py-2.5 px-3">Primary Entity</th>
                    <th className="py-2.5 px-3">Matched Entity</th>
                    <th className="py-2.5 px-3">Confidence</th>
                    <th className="py-2.5 px-3">Shared Identifiers</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                  {resolutions.map((item) => (
                    <tr
                      key={item.cluster_id}
                      onMouseEnter={(e) => resMag.onRowEnter(e.currentTarget)}
                      className="liquid-row-magnify cursor-pointer transition"
                    >
                      <td className="py-2.5 px-3 font-mono text-[11px] font-semibold text-slate-500 dark:text-zinc-400">{item.cluster_id}</td>
                      <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white">
                        <div>{item.primary_name}</div>
                        <div className="font-mono text-[10px] text-slate-500 dark:text-zinc-400">{item.primary_customer_id}</div>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white">
                        <div>{item.matched_name}</div>
                        <div className="font-mono text-[10px] text-slate-500 dark:text-zinc-400">{item.matched_customer_id}</div>
                      </td>
                      <td className="py-2.5 px-3 font-bold font-mono text-azure-600 dark:text-sky-400">
                        {item.match_confidence}%
                      </td>
                      <td className="py-2.5 px-3 text-[11px] text-slate-700 dark:text-zinc-300">
                        {item.shared_identifiers.join(", ")}
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge variant={item.resolution_status === "CONFIRMED_MATCH" ? "CRITICAL" : "HIGH"}>
                          {item.resolution_status.replace("_", " ")}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          type="button"
                          onClick={() => handleSelectSeed(item.primary_customer_id)}
                          className="px-2.5 py-1 rounded-full bg-azure-600/15 dark:bg-white/10 text-azure-700 dark:text-sky-300 hover:bg-azure-600/25 dark:hover:bg-white/20 font-semibold text-[11px] transition"
                        >
                          Graph Link
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 5: Network Risk Analysis */}
        {bottomTab === "risk" && (
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch">
              {/* Overall Score Card */}
              <div className="p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm space-y-2">
                <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                  Network Intelligence Risk Score
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-rose-600 dark:text-rose-400 ios-num">
                    {riskAnalysis?.overall_network_risk_score ?? 68}
                  </span>
                  <span className="text-sm font-semibold text-slate-400">/ 100</span>
                  <Badge variant={tierVariant(riskAnalysis?.risk_tier || "HIGH")}>
                    {riskAnalysis?.risk_tier || "HIGH"}
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-zinc-400 leading-relaxed">
                  {riskAnalysis?.explanation ||
                    "Network topology exhibits multiple high-risk indicators including circular transfer loops and multi-account hardware clustering."}
                </p>
              </div>

              {/* Subgraph Topology Stats */}
              <div className="md:col-span-2 p-4 rounded-2xl bg-white/40 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm space-y-3">
                <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                  Topology Diagnostics &amp; Metrics
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div className="p-2.5 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/50 dark:border-white/10">
                    <div className="text-[10px] text-slate-400">Nodes in Subgraph</div>
                    <div className="font-bold text-slate-900 dark:text-white font-mono text-sm mt-0.5">
                      {riskAnalysis?.subgraph_metrics.total_nodes ?? visibleNodes.length}
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/50 dark:border-white/10">
                    <div className="text-[10px] text-slate-400">Edges in Subgraph</div>
                    <div className="font-bold text-slate-900 dark:text-white font-mono text-sm mt-0.5">
                      {riskAnalysis?.subgraph_metrics.total_edges ?? visibleEdges.length}
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/50 dark:border-white/10">
                    <div className="text-[10px] text-slate-400">Avg Node Degree</div>
                    <div className="font-bold text-slate-900 dark:text-white font-mono text-sm mt-0.5">
                      {riskAnalysis?.subgraph_metrics.avg_node_degree ?? 2.4}
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white/60 dark:bg-white/[0.05] backdrop-blur-sm border border-white/50 dark:border-white/10">
                    <div className="text-[10px] text-slate-400">Volume Flowed</div>
                    <div className="font-bold text-amber-600 dark:text-amber-400 font-mono text-xs mt-0.5">
                      {fmtUSD(riskAnalysis?.subgraph_metrics.total_volume ?? 1250000)}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Factor Attribution Breakdown */}
            <div className="space-y-2 pt-1">
              <div className="text-xs font-bold text-slate-900 dark:text-white">Factor Attribution Breakdown</div>
              <div ref={riskMag.containerRef} onMouseLeave={riskMag.onContainerLeave} className="relative overflow-x-auto">
                {riskMag.lensElement}
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/50 dark:border-white/10 text-slate-500 dark:text-zinc-400 text-[10px] uppercase font-bold tracking-wider">
                      <th className="py-2.5 px-3">Factor Name</th>
                      <th className="py-2.5 px-3">Factor Score</th>
                      <th className="py-2.5 px-3">Model Weight</th>
                      <th className="py-2.5 px-3">Factual Detail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                    {riskAnalysis?.factors.map((f, i) => (
                      <tr
                        key={i}
                        onMouseEnter={(e) => riskMag.onRowEnter(e.currentTarget)}
                        className="liquid-row-magnify cursor-pointer transition"
                      >
                        <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white">{f.factor}</td>
                        <td className="py-2.5 px-3 font-mono font-bold text-rose-600 dark:text-rose-400">
                          {f.score}/100
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-500 dark:text-zinc-400">{(f.weight * 100).toFixed(0)}%</td>
                        <td className="py-2.5 px-3 text-[11px] text-slate-600 dark:text-zinc-300">{f.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
