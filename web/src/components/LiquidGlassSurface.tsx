import React, { useCallback, useLayoutEffect, useRef, useState } from "react";

/**
 * Interactive Liquid Glass card with cursor-tracking light reflection + diagonal glass shine.
 */
export const LiquidGlassCard: React.FC<{
  className?: string;
  variant?: "glass" | "hero" | "rose" | "amber" | "emerald";
  onClick?: () => void;
  children: React.ReactNode;
}> = ({ className = "", variant = "glass", onClick, children }) => {
  const ref = useRef<HTMLDivElement | null>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - rect.left}px`);
    el.style.setProperty("--my", `${e.clientY - rect.top}px`);
  };

  const baseCls =
    variant === "hero"
      ? "liquid-glass-hero"
      : variant === "rose"
      ? "liquid-glass-rose"
      : variant === "amber"
      ? "liquid-glass-amber"
      : variant === "emerald"
      ? "liquid-glass-emerald"
      : "liquid-glass";

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onClick={onClick}
      className={`${baseCls} liquid-glass-interactive ${className}`}
    >
      <div className="relative z-10 h-full">{children}</div>
    </div>
  );
};

/**
 * Reusable iOS 26/27 Sliding Liquid-Glass Magnifier Segmented Control (for 7D/30D/90D/ALL & Queue Sort).
 */
export function LiquidGlassSegmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (val: T) => void;
}) {
  const dockRef = useRef<HTMLDivElement | null>(null);
  const btnRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const prevIdxRef = useRef<number>(0);
  const [lens, setLens] = useState({ left: 0, width: 0, ready: false });
  const [sliding, setSliding] = useState(false);
  const [passingVals, setPassingVals] = useState<Set<string>>(new Set());

  const measure = useCallback(() => {
    const btn = btnRefs.current[value];
    if (!btn) return;
    setLens({ left: btn.offsetLeft, width: btn.offsetWidth, ready: true });
  }, [value]);

  useLayoutEffect(() => {
    measure();
    const nextIdx = options.findIndex((o) => o.value === value);
    const prevIdx = prevIdxRef.current;
    prevIdxRef.current = nextIdx;

    setSliding(true);
    const timers: number[] = [];
    if (prevIdx !== -1 && nextIdx !== -1 && prevIdx !== nextIdx) {
      const step = nextIdx > prevIdx ? 1 : -1;
      const dist = Math.abs(nextIdx - prevIdx);
      for (let k = 1; k < dist; k++) {
        const pv = options[prevIdx + k * step]?.value;
        if (!pv) continue;
        const enterDelay = Math.round((k / dist) * 220);
        timers.push(window.setTimeout(() => setPassingVals((s) => new Set(s).add(pv)), enterDelay));
        timers.push(
          window.setTimeout(() => {
            setPassingVals((s) => {
              const n = new Set(s);
              n.delete(pv);
              return n;
            });
          }, enterDelay + 160)
        );
      }
    }
    timers.push(window.setTimeout(() => setSliding(false), 380));
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [measure, value, options]);

  useLayoutEffect(() => {
    if (!dockRef.current) return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(dockRef.current);
    return () => ro.disconnect();
  }, [measure]);

  return (
    <div
      ref={dockRef}
      className="liquid-dock relative inline-flex items-center p-1 rounded-full select-none"
    >
      {lens.ready && (
        <div
          aria-hidden="true"
          className={`liquid-lens absolute top-1 bottom-1 left-0 rounded-full pointer-events-none ${
            sliding ? "liquid-lens-sliding" : ""
          }`}
          style={{
            width: `${lens.width}px`,
            transform: `translate3d(${lens.left}px, 0, 0) scale(${sliding ? 1.08 : 1.03})`,
          }}
        />
      )}

      {options.map((opt) => {
        const active = opt.value === value;
        const passing = passingVals.has(opt.value);
        return (
          <button
            key={opt.value}
            ref={(el) => {
              btnRefs.current[opt.value] = el;
            }}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`relative z-10 px-3.5 py-1.5 rounded-full text-xs ios-num transition-all duration-200 ${
              active
                ? "font-bold text-azure-700 dark:text-white scale-[1.12]"
                : passing
                ? "font-bold text-slate-900 dark:text-white scale-[1.10]"
                : "font-semibold text-slate-700/85 dark:text-zinc-400 hover:text-slate-950 dark:hover:text-white hover:scale-[1.04]"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Tracks hovered table row / feed item inside a relative container to glide a Liquid Glass Lens bar smoothly up & down.
 */
export function useRowGlassMagnifier() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [lensState, setLensState] = useState<{ top: number; height: number; visible: boolean }>({
    top: 0,
    height: 44,
    visible: false,
  });

  const onRowEnter = useCallback((el: HTMLElement | null) => {
    const container = containerRef.current;
    if (!container || !el) return;
    const cRect = container.getBoundingClientRect();
    const rRect = el.getBoundingClientRect();
    setLensState({
      top: rRect.top - cRect.top + container.scrollTop,
      height: rRect.height,
      visible: true,
    });
  }, []);

  const onContainerLeave = useCallback(() => {
    setLensState((prev) => ({ ...prev, visible: false }));
  }, []);

  const lensElement = (
    <div
      aria-hidden="true"
      className="liquid-row-lens"
      style={{
        height: `${lensState.height}px`,
        transform: `translate3d(0, ${lensState.top}px, 0) scale(${lensState.visible ? 1.008 : 0.98})`,
        opacity: lensState.visible ? 1 : 0,
      }}
    />
  );

  return { containerRef, onRowEnter, onContainerLeave, lensElement };
}
