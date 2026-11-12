import React, { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

export const PAGE_SIZE_PRESETS = [10, 20, 30, 50, 100] as const;

interface GlassPaginationProps {
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (nextPage: number) => void;
  onPageSizeChange: (nextSize: number) => void;
  unitLabel?: string;
}

function buildPageWindow(current: number, totalPages: number): Array<number | "ellipsis-l" | "ellipsis-r"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i);
  }
  const pages: Array<number | "ellipsis-l" | "ellipsis-r"> = [0];
  const start = Math.max(1, current - 1);
  const end = Math.min(totalPages - 2, current + 1);
  if (start > 1) pages.push("ellipsis-l");
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < totalPages - 2) pages.push("ellipsis-r");
  pages.push(totalPages - 1);
  return pages;
}

export const GlassPagination: React.FC<GlassPaginationProps> = ({
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  unitLabel = "items",
}) => {
  const safeSize = Math.max(1, pageSize || 30);
  const totalPages = Math.max(1, Math.ceil(total / safeSize));
  const safePage = Math.min(Math.max(0, page), totalPages - 1);
  const startRow = total === 0 ? 0 : safePage * safeSize + 1;
  const endRow = Math.min(total, (safePage + 1) * safeSize);

  const isPreset = (PAGE_SIZE_PRESETS as readonly number[]).includes(safeSize);
  const [customMode, setCustomMode] = useState(!isPreset);
  const [customSizeInput, setCustomSizeInput] = useState(String(safeSize));
  const [jumpInput, setJumpInput] = useState("");

  useEffect(() => {
    setCustomSizeInput(String(safeSize));
    if ((PAGE_SIZE_PRESETS as readonly number[]).includes(safeSize)) {
      setCustomMode(false);
    }
  }, [safeSize]);

  const applyCustomSize = () => {
    const parsed = Number.parseInt(customSizeInput, 10);
    if (!Number.isNaN(parsed)) {
      const clamped = Math.max(1, Math.min(250, parsed));
      onPageSizeChange(clamped);
      setCustomSizeInput(String(clamped));
    } else {
      setCustomSizeInput(String(safeSize));
    }
  };

  const handleJump = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = Number.parseInt(jumpInput, 10);
    if (Number.isNaN(parsed)) return;
    const target = Math.min(totalPages - 1, Math.max(0, parsed - 1));
    onPageChange(target);
    setJumpInput("");
  };

  const glassControl =
    "bg-white/10 dark:bg-white/[0.04] hover:bg-white/25 dark:hover:bg-white/[0.10] backdrop-blur-md border border-white/50 dark:border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.45)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.08)] text-slate-800 dark:text-zinc-200 transition";

  const pages = buildPageWindow(safePage, totalPages);

  return (
    <div className="px-4 py-3 border-t border-white/40 dark:border-white/10 bg-white/[0.08] dark:bg-white/[0.02] backdrop-blur-xl flex flex-wrap items-center justify-between gap-3 text-xs ios-num">
      {/* Left: Range Count + Transparent Glass Rows-Per-Page Selector */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-slate-700 dark:text-zinc-300 font-medium">
          Showing <strong className="text-slate-950 dark:text-white">{startRow.toLocaleString()}</strong>–
          <strong className="text-slate-950 dark:text-white">{endRow.toLocaleString()}</strong> of{" "}
          <strong className="text-slate-950 dark:text-white">{total.toLocaleString()}</strong> {unitLabel}
        </span>

        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/10 dark:bg-white/[0.04] backdrop-blur-md border border-white/50 dark:border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.45)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.08)]">
          <span className="text-[11px] font-semibold text-slate-600 dark:text-zinc-400">Max rows:</span>
          <select
            aria-label="Rows per page"
            value={customMode ? "custom" : String(safeSize)}
            onChange={(e) => {
              if (e.target.value === "custom") {
                setCustomMode(true);
              } else {
                setCustomMode(false);
                onPageSizeChange(Number(e.target.value));
              }
            }}
            className="bg-transparent text-xs font-bold text-slate-950 dark:text-white focus:outline-none cursor-pointer pr-1"
          >
            {PAGE_SIZE_PRESETS.map((sz) => (
              <option key={sz} value={String(sz)} className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">
                {sz}
              </option>
            ))}
            <option value="custom" className="bg-white text-slate-900 dark:bg-zinc-900 dark:text-white">
              Custom...
            </option>
          </select>

          {customMode && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                applyCustomSize();
              }}
              className="inline-flex items-center gap-1 pl-1 border-l border-white/40 dark:border-white/15"
            >
              <input
                type="number"
                min={1}
                max={250}
                value={customSizeInput}
                onChange={(e) => setCustomSizeInput(e.target.value)}
                onBlur={applyCustomSize}
                aria-label="Custom rows per page"
                className="w-12 px-1.5 py-0.5 rounded-full bg-white/15 dark:bg-white/[0.06] border border-white/50 dark:border-white/15 text-center text-[11px] font-bold text-slate-950 dark:text-white focus:outline-none"
              />
              <button
                type="submit"
                className="px-2 py-0.5 rounded-full bg-azure-500/20 dark:bg-white/15 border border-azure-400/40 dark:border-white/25 text-[10.5px] font-bold text-azure-800 dark:text-white"
              >
                Set
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Right: Transparent Glass Page Controls & Quick Jump */}
      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          disabled={safePage <= 0}
          onClick={() => onPageChange(0)}
          title="First page"
          aria-label="First page"
          className={`p-1.5 rounded-full disabled:opacity-35 ${glassControl}`}
        >
          <ChevronsLeft className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          disabled={safePage <= 0}
          onClick={() => onPageChange(safePage - 1)}
          title="Previous page"
          aria-label="Previous page"
          className={`p-1.5 rounded-full disabled:opacity-35 ${glassControl}`}
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>

        {pages.map((p) =>
          typeof p === "string" ? (
            <span key={p} className="px-1 text-slate-500 dark:text-zinc-500 select-none">
              …
            </span>
          ) : (
            <button
              key={p}
              type="button"
              onClick={() => onPageChange(p)}
              className={`min-w-[28px] h-7 px-2 rounded-full text-xs font-semibold transition backdrop-blur-md ${
                p === safePage
                  ? "bg-azure-500/22 dark:bg-white/18 border border-azure-400/60 dark:border-white/35 shadow-[0_4px_14px_rgba(24,119,242,0.18),inset_0_1px_1px_rgba(255,255,255,0.75)] dark:shadow-[inset_0_1px_1px_rgba(255,255,255,0.22)] text-azure-800 dark:text-white font-bold"
                  : glassControl
              }`}
            >
              {p + 1}
            </button>
          )
        )}

        <button
          type="button"
          disabled={safePage + 1 >= totalPages}
          onClick={() => onPageChange(safePage + 1)}
          title="Next page"
          aria-label="Next page"
          className={`p-1.5 rounded-full disabled:opacity-35 ${glassControl}`}
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          disabled={safePage + 1 >= totalPages}
          onClick={() => onPageChange(totalPages - 1)}
          title="Last page"
          aria-label="Last page"
          className={`p-1.5 rounded-full disabled:opacity-35 ${glassControl}`}
        >
          <ChevronsRight className="w-3.5 h-3.5" />
        </button>

        {totalPages > 1 && (
          <form onSubmit={handleJump} className="inline-flex items-center gap-1 ml-1">
            <input
              type="number"
              min={1}
              max={totalPages}
              value={jumpInput}
              onChange={(e) => setJumpInput(e.target.value)}
              placeholder={`1-${totalPages}`}
              aria-label="Jump to page"
              className="w-16 px-2.5 py-1 rounded-full bg-white/10 dark:bg-white/[0.04] backdrop-blur-md border border-white/50 dark:border-white/15 shadow-[inset_0_1px_1px_rgba(255,255,255,0.45)] dark:shadow-none text-center text-[11px] text-slate-950 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-500 focus:outline-none"
            />
          </form>
        )}
      </div>
    </div>
  );
};
