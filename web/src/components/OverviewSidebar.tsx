import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronDown, HelpCircle, Settings } from "lucide-react";
import type { NavItem } from "./LiquidGlassNav";
import type { AuthUser } from "../types/workbench";

interface OverviewSidebarProps<T extends string> {
  items: Array<NavItem<T>>;
  activeId: T;
  onChange: (id: T) => void;
  user: AuthUser;
  onOpenProfile: () => void;
  onOpenSupport: () => void;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "YF";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function formatRoleLabel(role: AuthUser["role"]): string {
  if (role === "OPS_ANALYST") return "Analyst";
  if (role === "RISK_REVIEWER") return "Reviewer";
  return "Admin";
}

export function OverviewSidebar<T extends string>({
  items,
  activeId,
  onChange,
  user,
  onOpenProfile,
  onOpenSupport,
}: OverviewSidebarProps<T>) {
  const initials = getInitials(user.full_name);
  const roleLabel = formatRoleLabel(user.role);

  const navRef = useRef<HTMLElement | null>(null);
  const btnRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [hoverId, setHoverId] = useState<T | null>(null);
  const [slider, setSlider] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
    ready: boolean;
  }>({ top: 0, left: 0, width: 0, height: 0, ready: false });

  const targetId = hoverId ?? activeId;

  const measureSlider = () => {
    const btn = btnRefs.current[targetId];
    if (!btn) return;
    setSlider({
      top: btn.offsetTop,
      left: btn.offsetLeft,
      width: btn.offsetWidth,
      height: btn.offsetHeight,
      ready: true,
    });
  };

  useLayoutEffect(() => {
    measureSlider();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetId, items.map((i) => `${i.id}:${i.label}:${i.badge ?? ""}`).join("|")]);

  useEffect(() => {
    if (!navRef.current) return;
    const ro = new ResizeObserver(() => measureSlider());
    ro.observe(navRef.current);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetId]);

  return (
    <aside
      aria-label="Overview Workbench Navigation"
      className="overview-glass-sidebar rounded-[30px] w-full lg:w-[248px] shrink-0 lg:sticky lg:top-4 lg:min-h-[calc(100vh-2rem)] p-4 flex flex-col justify-between gap-4 select-none overflow-hidden"
    >
      {/* Optical Glass Caustics */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-0 overflow-hidden rounded-[inherit]">
        {/* Diagonal internal glass refraction sweep */}
        <div
          className="absolute inset-x-[-20%] top-[28%] h-44 -rotate-12 bg-gradient-to-b from-white/25 via-sky-200/10 to-transparent dark:from-sky-300/16 dark:via-blue-400/5 dark:to-transparent blur-xl"
        />
        {/* Vertical side glass prism highlight */}
        <div className="absolute inset-y-6 left-0 w-[1.5px] bg-gradient-to-b from-white/70 via-sky-200/20 to-white/65 opacity-80" />
        <div className="absolute inset-y-6 right-0 w-[1.5px] bg-gradient-to-b from-white/35 via-sky-300/45 to-white/40 opacity-80" />
      </div>

      {/* Top Brand Header + Vertical Functions List with Cursor-Following Sliding Glass Slider */}
      <div className="relative z-10 space-y-4">
        <a
          href="https://stg.yottaflex.ai"
          target="_blank"
          rel="noopener noreferrer"
          title="https://stg.yottaflex.ai"
          className="group flex flex-col items-center text-center pt-2 pb-1 px-2 rounded-2xl transition"
        >
          <img
            src="/yottaflex-logo.webp"
            alt="YottaFlex Logo"
            className="w-[68px] h-[68px] object-contain dark:brightness-0 dark:invert drop-shadow-[0_6px_16px_rgba(14,72,165,0.20)] dark:drop-shadow-[0_8px_18px_rgba(56,189,248,0.28)] transition-transform duration-500 group-hover:-translate-y-0.5 group-hover:scale-105"
          />
          <div className="mt-2.5 text-[19px] font-bold tracking-tight text-slate-950 dark:text-white group-hover:text-azure-700 dark:group-hover:text-sky-300 transition-colors">
            YottaFlex
          </div>
          <div className="text-[12.5px] font-medium text-slate-700/85 dark:text-sky-100/75 leading-snug mt-0.5">
            AML Risk &amp; Ledger
            <br />
            Triage
          </div>
        </a>

        <nav
          ref={navRef}
          onMouseLeave={() => setHoverId(null)}
          className="relative grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-1 gap-1.5"
          aria-label="All Workbench Functions"
        >
          {/* Floating Luminous Glass Pill Slider (Slides to Hovered Option or Active Tab) */}
          {slider.ready && (
            <div
              aria-hidden="true"
              className="overview-nav-slider pointer-events-none absolute top-0 left-0 rounded-full z-0"
              style={{
                width: `${slider.width}px`,
                height: `${slider.height}px`,
                transform: `translate3d(${slider.left}px, ${slider.top}px, 0)`,
              }}
            />
          )}

          {items.map((item) => {
            const isHighlighted = item.id === targetId;
            return (
              <button
                key={item.id}
                ref={(el) => {
                  btnRefs.current[item.id] = el;
                }}
                type="button"
                onMouseEnter={() => setHoverId(item.id)}
                onFocus={() => setHoverId(item.id)}
                onBlur={() => setHoverId(null)}
                onClick={() => onChange(item.id)}
                className={`relative z-10 w-full flex items-center justify-between gap-2 px-3.5 py-2.5 rounded-full text-[13px] transition-colors duration-200 ${
                  isHighlighted
                    ? "text-slate-950 dark:text-white font-semibold"
                    : "text-slate-800 dark:text-zinc-200/90 hover:text-slate-950 dark:hover:text-white font-medium"
                }`}
              >
                <span className="flex items-center gap-2.5 min-w-0">
                  <span
                    className={`shrink-0 transition-transform duration-200 ${
                      isHighlighted ? "text-azure-600 dark:text-white scale-105" : "text-slate-600 dark:text-sky-100/75"
                    }`}
                  >
                    {item.icon}
                  </span>
                  <span className="truncate">{item.label}</span>
                </span>

                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`shrink-0 px-2 py-0.5 rounded-full text-[10.5px] ios-num font-bold leading-none transition-colors ${
                      isHighlighted
                        ? "bg-rose-500 text-white dark:bg-white/25 dark:text-white shadow-[0_0_12px_rgba(244,63,94,0.45)] dark:shadow-[0_0_10px_rgba(255,255,255,0.28)]"
                        : "bg-rose-500 text-white shadow-[0_0_12px_rgba(244,63,94,0.60)]"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Settings, Help & Support, and Frosted User Profile Card */}
      <div className="relative z-10 pt-3 border-t border-white/45 dark:border-white/18 space-y-1.5">
        <button
          type="button"
          onClick={onOpenProfile}
          className="w-full flex items-center gap-2.5 px-3.5 py-2 rounded-full text-[13px] font-medium text-slate-800 dark:text-zinc-200/90 hover:bg-white/40 dark:hover:bg-white/[0.10] hover:text-slate-950 dark:hover:text-white border border-transparent hover:border-white/55 dark:hover:border-white/25 transition"
        >
          <Settings className="w-4 h-4 text-slate-600 dark:text-sky-100/75 shrink-0" />
          <span className="truncate">Settings</span>
        </button>

        <button
          type="button"
          onClick={onOpenSupport}
          className="w-full flex items-center gap-2.5 px-3.5 py-2 rounded-full text-[13px] font-medium text-slate-800 dark:text-zinc-200/90 hover:bg-white/40 dark:hover:bg-white/[0.10] hover:text-slate-950 dark:hover:text-white border border-transparent hover:border-white/55 dark:hover:border-white/25 transition"
        >
          <HelpCircle className="w-4 h-4 text-slate-600 dark:text-sky-100/75 shrink-0" />
          <span className="truncate">Help &amp; Support</span>
        </button>

        <button
          type="button"
          onClick={onOpenProfile}
          className="mt-2 w-full flex items-center justify-between gap-2.5 px-2.5 py-2 rounded-2xl bg-white/35 dark:bg-white/[0.08] hover:bg-white/55 dark:hover:bg-white/[0.14] border border-white/60 dark:border-white/28 shadow-[inset_0_1px_1px_rgba(255,255,255,0.45)] transition text-left"
        >
          <span className="flex items-center gap-2.5 min-w-0">
            <span className="w-9 h-9 rounded-full bg-gradient-to-br from-sky-400/90 to-azure-600/95 dark:from-sky-400/70 dark:to-azure-600/75 border border-white/85 dark:border-white/45 shadow-[0_4px_14px_rgba(56,189,248,0.35)] flex items-center justify-center text-xs font-bold text-white shrink-0">
              {initials}
            </span>
            <span className="min-w-0">
              <span className="block text-[12.5px] font-bold text-slate-950 dark:text-white truncate">
                {user.full_name}
              </span>
              <span className="block text-[10.5px] font-medium text-slate-700/85 dark:text-sky-100/70 truncate">
                {roleLabel}
              </span>
            </span>
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-slate-500 dark:text-sky-100/70 shrink-0" />
        </button>
      </div>
    </aside>
  );
}
