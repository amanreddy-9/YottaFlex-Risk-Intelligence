import React, { useEffect, useMemo, useState } from "react";
import { Bell, CheckCheck, Minus, RefreshCw } from "lucide-react";
import type { NotificationItem } from "../types/workbench";

export interface AnchorRect {
  top: number;
  right: number;
}

interface NotificationBellButtonProps {
  open: boolean;
  unreadCount: number;
  onOpenFromRect: (rect: AnchorRect) => void;
  variant?: "overview" | "dock";
}

interface NotificationWindowPanelProps {
  open: boolean;
  anchor: AnchorRect;
  onClose: () => void;
  notifications: NotificationItem[];
  unreadCount: number;
  onRefresh: () => void;
  onMarkAllRead: () => void;
  onSelectNotification: (item: NotificationItem) => void;
}

/** Track pointer position in local element coordinates so border rim shine moves dynamically on hover. */
function trackGlassBorder(e: React.MouseEvent<HTMLElement>): void {
  const rect = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--bx", `${e.clientX - rect.left}px`);
  e.currentTarget.style.setProperty("--by", `${e.clientY - rect.top}px`);
}

function measureAnchor(el: HTMLElement): AnchorRect {
  const r = el.getBoundingClientRect();
  return {
    top: Math.max(12, Math.round(r.top)),
    right: Math.max(16, Math.round(window.innerWidth - r.right)),
  };
}

export const NotificationBellButton: React.FC<NotificationBellButtonProps> = ({
  open,
  unreadCount,
  onOpenFromRect,
  variant = "dock",
}) => {
  const baseClass =
    variant === "overview"
      ? "liquid-dock chameleon-btn-bell inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-semibold text-slate-800 dark:text-white cursor-pointer"
      : "glass-pill chameleon-btn-bell h-8 min-w-[32px] px-2.5 rounded-full inline-flex items-center justify-center gap-1.5 text-xs font-semibold text-slate-800 dark:text-white shrink-0 cursor-pointer";

  return (
    <button
      type="button"
      onClick={(e) => onOpenFromRect(measureAnchor(e.currentTarget))}
      aria-label="Open Notifications Center"
      aria-hidden={open}
      title="Notifications & SLA Alerts"
      className={`ybot-launcher ${baseClass} ${
        open ? "scale-125 opacity-0 pointer-events-none blur-sm" : "scale-100 opacity-100"
      }`}
    >
      <Bell className="w-3.5 h-3.5 text-slate-700 dark:text-white/90 drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]" />
      {unreadCount > 0 && (
        <span className="badge-glass badge-glass-critical ios-num font-mono text-[10px] px-1.5 py-0.2 rounded-full font-bold leading-tight">
          {unreadCount}
        </span>
      )}
    </button>
  );
};

export const NotificationWindowPanel: React.FC<NotificationWindowPanelProps> = ({
  open,
  anchor,
  onClose,
  notifications,
  unreadCount,
  onRefresh,
  onMarkAllRead,
  onSelectNotification,
}) => {
  const [filterMode, setFilterMode] = useState<"ALL" | "UNREAD">("ALL");

  const visibleItems = useMemo(
    () => (filterMode === "UNREAD" ? notifications.filter((n) => !n.is_read) : notifications),
    [notifications, filterMode]
  );

  // Close cleanly on Escape just like a floating glass dialog
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <div
      role="dialog"
      aria-label="Notifications Center"
      aria-hidden={!open}
      style={{ top: `${anchor.top}px`, right: `${anchor.right}px` }}
      className={`ybot-window-morph-top ybot-shell fixed z-50 w-[395px] max-w-[calc(100vw-2rem)] h-[520px] max-h-[calc(100vh-2.5rem)] flex flex-col overflow-hidden ${
        open ? "ybot-window-open" : "ybot-window-closed"
      }`}
    >
      {/* 80%-Transparent Optical Glass Header — 100% matched to YottaBotWidget */}
      <div className="px-4 py-3 border-b border-white/40 dark:border-white/18 bg-white/10 dark:bg-white/[0.02] flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2.5">
          <div
            onMouseMove={trackGlassBorder}
            className="ybot-glass-icon w-9 h-9 rounded-full p-1.5 flex items-center justify-center text-azure-700 dark:text-sky-300"
          >
            <Bell className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-950 dark:text-white flex items-center gap-1.5">
              <span>Notifications</span>
              <span
                className={`w-1.5 h-1.5 rounded-full inline-block ${
                  unreadCount > 0 ? "bg-rose-500 animate-pulse" : "bg-emerald-500"
                }`}
              />
            </div>
            <div className="ios-num text-[10.5px] font-medium text-slate-700 dark:text-zinc-300">
              {unreadCount} unread • Live SLA &amp; Alert Feed
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onMouseMove={trackGlassBorder}
            onClick={onRefresh}
            title="Refresh notifications"
            className="ybot-glass-icon w-8 h-8 rounded-full flex items-center justify-center text-slate-800 dark:text-white"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onMouseMove={trackGlassBorder}
            onClick={onMarkAllRead}
            disabled={unreadCount === 0}
            title="Mark all notifications read"
            className="ybot-glass-icon w-8 h-8 rounded-full flex items-center justify-center text-slate-800 dark:text-white disabled:opacity-40"
          >
            <CheckCheck className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onMouseMove={trackGlassBorder}
            onClick={onClose}
            title="Minimize back into Notifications icon"
            aria-label="Minimize Notifications"
            className="ybot-glass-icon w-8 h-8 rounded-full flex items-center justify-center text-slate-800 dark:text-white"
          >
            <Minus className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 80%-Transparent Glass Notifications Area — exact .ybot-glass-box bubbles */}
      <div className="flex-1 overflow-y-auto px-3.5 py-3.5 space-y-3">
        {visibleItems.length === 0 ? (
          <div
            onMouseMove={trackGlassBorder}
            className="ybot-glass-box rounded-2xl px-4 py-6 text-center text-xs text-slate-800 dark:text-zinc-200"
          >
            {filterMode === "UNREAD" ? "All caught up — zero unread notifications." : "No notifications queued."}
          </div>
        ) : (
          visibleItems.map((n) => (
            <div key={n.notif_id} className="flex items-start gap-2 justify-start">
              <div
                onMouseMove={trackGlassBorder}
                className="ybot-glass-icon w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 text-azure-700 dark:text-sky-300"
              >
                <Bell className="w-3.5 h-3.5" />
              </div>

              <button
                type="button"
                onMouseMove={trackGlassBorder}
                onClick={() => onSelectNotification(n)}
                className={`ybot-glass-box flex-1 text-left rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-xs leading-relaxed cursor-pointer ${
                  n.is_read ? "opacity-75" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2 text-[9.5px] font-mono uppercase tracking-wider text-slate-600 dark:text-zinc-400 mb-1">
                  <span>
                    {n.category} • {n.created_at}
                  </span>
                  <span className="ybot-glass-box px-2 py-0.5 rounded-full text-[9.5px] font-semibold text-azure-800 dark:text-sky-200">
                    {n.severity}
                  </span>
                </div>

                <div className="font-bold text-slate-950 dark:text-white flex items-center gap-1.5">
                  {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />}
                  <span className="truncate">{n.title}</span>
                </div>

                <div className="text-slate-900 dark:text-zinc-100 mt-0.5">{n.body}</div>

                {n.entity_id && (
                  <div className="mt-2 pt-2 border-t border-white/35 dark:border-white/15 flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] text-slate-600 dark:text-zinc-400">{n.entity_id}</span>
                    <span className="ybot-glass-box px-2.5 py-1 rounded-full text-[10.5px] font-semibold text-azure-800 dark:text-white hover:scale-[1.03] transition">
                      Inspect {n.entity_id} →
                    </span>
                  </div>
                )}
              </button>
            </div>
          ))
        )}
      </div>

      {/* Bottom Filter Strip — 100% matched to YottaBotWidget suggested prompts strip */}
      <div className="px-3.5 py-2.5 border-t border-white/40 dark:border-white/18 bg-white/10 dark:bg-white/[0.02] flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-1.5">
          {(["ALL", "UNREAD"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onMouseMove={trackGlassBorder}
              onClick={() => setFilterMode(mode)}
              className={`ybot-glass-box px-2.5 py-1 rounded-full text-[10.5px] font-semibold transition ${
                filterMode === mode
                  ? "text-azure-800 dark:text-white ring-1 ring-white/80 dark:ring-white/40"
                  : "text-slate-700 dark:text-zinc-300 opacity-80"
              }`}
            >
              {mode === "ALL" ? `All (${notifications.length})` : `Unread (${unreadCount})`}
            </button>
          ))}
        </div>

        {unreadCount > 0 && (
          <button
            type="button"
            onMouseMove={trackGlassBorder}
            onClick={onMarkAllRead}
            className="ybot-glass-box px-2.5 py-1 rounded-full text-[10.5px] font-semibold text-azure-800 dark:text-white hover:scale-[1.03] transition"
          >
            Mark all read →
          </button>
        )}
      </div>
    </div>
  );
};
