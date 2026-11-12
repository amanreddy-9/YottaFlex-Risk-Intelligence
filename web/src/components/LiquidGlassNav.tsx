import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface NavItem<T extends string> {
  id: T;
  label: string;
  icon: React.ReactNode;
  badge?: number;
}

interface LiquidGlassNavProps<T extends string> {
  items: Array<NavItem<T>>;
  activeId: T;
  onChange: (id: T) => void;
  beaconKey?: number;
}

export function LiquidGlassNav<T extends string>({
  items,
  activeId,
  onChange,
  beaconKey = 0,
}: LiquidGlassNavProps<T>) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const btnRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const prevIdxRef = useRef<number>(0);
  const prevActiveRef = useRef<T>(activeId);

  const [lens, setLens] = useState<{ left: number; width: number; ready: boolean }>({
    left: 0,
    width: 0,
    ready: false,
  });
  const [sliding, setSliding] = useState(false);
  const [passingIds, setPassingIds] = useState<Set<string>>(new Set());
  const [glowing, setGlowing] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  useEffect(() => {
    if (prevActiveRef.current !== activeId) {
      setGlowing(false);
      prevActiveRef.current = activeId;
    }
  }, [activeId]);

  useEffect(() => {
    if (!beaconKey) {
      setGlowing(false);
      return;
    }
    setGlowing(true);
    const timer = window.setTimeout(() => setGlowing(false), 2600);
    return () => window.clearTimeout(timer);
  }, [beaconKey]);

  const updateScrollBounds = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    setCanScrollLeft(el.scrollLeft > 3);
    setCanScrollRight(maxScroll - el.scrollLeft > 3);
  }, []);

  const measure = useCallback(() => {
    const activeBtn = btnRefs.current[activeId];
    if (!activeBtn) return;
    setLens({
      left: activeBtn.offsetLeft,
      width: activeBtn.offsetWidth,
      ready: true,
    });
    updateScrollBounds();
  }, [activeId, updateScrollBounds]);

  useLayoutEffect(() => {
    measure();
    const activeBtn = btnRefs.current[activeId];
    if (activeBtn && trackRef.current && trackRef.current.scrollWidth > trackRef.current.clientWidth) {
      activeBtn.scrollIntoView({ behavior: "smooth", inline: "nearest", block: "nearest" });
    }

    const nextIdx = items.findIndex((i) => i.id === activeId);
    const prevIdx = prevIdxRef.current;
    prevIdxRef.current = nextIdx;

    setSliding(true);
    const timers: number[] = [];

    // Optical passing wave: briefly magnify intermediate tabs as the glass lens slides across them
    if (prevIdx !== -1 && nextIdx !== -1 && prevIdx !== nextIdx) {
      const step = nextIdx > prevIdx ? 1 : -1;
      const dist = Math.abs(nextIdx - prevIdx);
      for (let k = 1; k < dist; k++) {
        const idx = prevIdx + k * step;
        const passId = items[idx]?.id;
        if (!passId) continue;
        const enterDelay = Math.round((k / dist) * 240);
        timers.push(
          window.setTimeout(() => {
            setPassingIds((prev) => new Set(prev).add(passId));
          }, enterDelay)
        );
        timers.push(
          window.setTimeout(() => {
            setPassingIds((prev) => {
              const nxt = new Set(prev);
              nxt.delete(passId);
              return nxt;
            });
          }, enterDelay + 170)
        );
      }
    }

    timers.push(window.setTimeout(() => setSliding(false), 400));
    return () => timers.forEach((t) => window.clearTimeout(t));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, items.map((i) => `${i.id}:${i.label}:${i.badge ?? ""}`).join("|")]);

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(el);
    window.addEventListener("resize", updateScrollBounds);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", updateScrollBounds);
    };
  }, [measure, updateScrollBounds]);

  const scrollDockBy = (delta: number) => {
    trackRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  };

  // Dynamic CSS mask-image edge fade when horizontally overflowing
  const maskImage =
    canScrollLeft && canScrollRight
      ? "linear-gradient(to right, transparent 0px, black 26px, black calc(100% - 26px), transparent 100%)"
      : canScrollLeft
      ? "linear-gradient(to right, transparent 0px, black 26px, black 100%)"
      : canScrollRight
      ? "linear-gradient(to right, black 0px, black calc(100% - 26px), transparent 100%)"
      : undefined;

  return (
    <div
      role="tablist"
      aria-label="Primary Workbench Navigation"
      className="liquid-dock relative inline-flex items-center max-w-full p-1.5 rounded-full select-none"
    >
      {canScrollLeft && (
        <button
          type="button"
          onClick={() => scrollDockBy(-190)}
          aria-label="Scroll tabs left"
          className="relative z-20 mr-1 w-7 h-7 shrink-0 rounded-full flex items-center justify-center bg-white/75 dark:bg-zinc-900/90 border border-white/90 dark:border-white/20 text-slate-700 dark:text-zinc-200 hover:scale-105 hover:bg-white dark:hover:bg-zinc-800 shadow-[0_4px_12px_rgba(14,72,165,0.16),inset_0_1px_1px_rgba(255,255,255,0.85)] dark:shadow-[0_4px_12px_rgba(0,0,0,0.6)] transition"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>
      )}

      <div
        ref={trackRef}
        onScroll={updateScrollBounds}
        style={maskImage ? { maskImage, WebkitMaskImage: maskImage } : undefined}
        className="relative flex items-center overflow-x-auto no-scrollbar scroll-smooth min-w-0 py-1 -my-1 px-0.5"
      >
        {/* Crystal Liquid Glass Sliding Magnifier Lens */}
        {lens.ready && (
          <div
            aria-hidden="true"
            className={`liquid-lens absolute top-1 bottom-1 left-0 rounded-full pointer-events-none ${
              sliding ? "liquid-lens-sliding" : ""
            }`}
            style={{
              width: `${lens.width}px`,
              transform: `translate3d(${lens.left}px, 0, 0) scale(${sliding ? 1.07 : 1.03})`,
            }}
          />
        )}

        {items.map((item) => {
          const isActive = item.id === activeId;
          const isPassing = passingIds.has(item.id);
          const magnified = isActive || isPassing;
          const arrivalGlow = isActive && glowing;

          return (
            <button
              key={item.id}
              ref={(el) => {
                btnRefs.current[item.id] = el;
              }}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onChange(item.id)}
              className={`relative z-10 shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs ios-num transition-all duration-200 ${
                isActive
                  ? "font-bold text-azure-700 dark:text-white scale-[1.10]"
                  : isPassing
                  ? "font-bold text-slate-900 dark:text-white scale-[1.09]"
                  : "font-semibold text-slate-700/85 dark:text-zinc-400 hover:text-slate-950 dark:hover:text-white hover:scale-[1.03]"
              }`}
            >
              <span
                className={`liquid-tab-label ${
                  magnified ? "text-azure-600 dark:text-white scale-110" : "opacity-80"
                } ${arrivalGlow ? "liquid-tab-arrival-glow" : ""}`}
              >
                {item.icon}
              </span>
              <span className={`liquid-tab-label whitespace-nowrap ${arrivalGlow ? "liquid-tab-arrival-glow" : ""}`}>
                {item.label}
              </span>
              {item.badge !== undefined && (
                <span
                  className={`badge-glass badge-glass-critical px-1.5 py-0.5 rounded-full text-[10px] ios-num font-bold leading-none transition-colors ${
                    isActive ? "scale-105" : ""
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {canScrollRight && (
        <button
          type="button"
          onClick={() => scrollDockBy(190)}
          aria-label="Scroll tabs right"
          className="relative z-20 ml-1 w-7 h-7 shrink-0 rounded-full flex items-center justify-center bg-white/75 dark:bg-zinc-900/90 border border-white/90 dark:border-white/20 text-slate-700 dark:text-zinc-200 hover:scale-105 hover:bg-white dark:hover:bg-zinc-800 shadow-[0_4px_12px_rgba(14,72,165,0.16),inset_0_1px_1px_rgba(255,255,255,0.85)] dark:shadow-[0_4px_12px_rgba(0,0,0,0.6)] transition"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
