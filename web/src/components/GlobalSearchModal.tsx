import React, { useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { api } from "../api/client";
import type { GlobalSearchResponse } from "../types/workbench";
import { Badge, tierVariant } from "./Badge";

interface GlobalSearchModalProps {
  open: boolean;
  onClose: () => void;
  onSelectEntity: (group: string, id: string) => void;
}

export const GlobalSearchModal: React.FC<GlobalSearchModalProps> = ({
  open,
  onClose,
  onSelectEntity,
}) => {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<GlobalSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => inputRef.current?.focus(), 60);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (!q) {
      setResult(null);
      return;
    }
    setLoading(true);
    const timer = window.setTimeout(() => {
      api
        .globalSearch(q)
        .then(setResult)
        .catch(() => {})
        .finally(() => setLoading(false));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [query, open]);

  if (!open) return null;

  const groupLabels: Array<{ key: keyof GlobalSearchResponse["groups"]; label: string }> = [
    { key: "cases", label: "Investigation Cases" },
    { key: "alerts", label: "Alerts" },
    { key: "customers", label: "Customers" },
    { key: "accounts", label: "Accounts" },
    { key: "transactions", label: "Transactions" },
    { key: "quarantine", label: "Quarantine Exceptions" },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 p-4 bg-sky-950/25 dark:bg-black/60 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        className="liquid-glass w-full max-w-2xl rounded-3xl overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-white/50 dark:border-white/10">
          <Search className="w-4 h-4 text-azure-600 dark:text-sky-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Spotlight search across Cases, Alerts, Customers, Accounts, Txns, Quarantine..."
            className="flex-1 bg-transparent text-sm text-slate-950 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="glass-pill p-1.5 rounded-full text-slate-700 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="max-h-[65vh] overflow-y-auto p-4 space-y-4">
          {!query.trim() && (
            <div className="text-xs text-slate-600 dark:text-zinc-400 py-6 text-center">
              Type any entity ID (e.g. <code>CASE-2026-</code>, <code>ALT-2026-</code>, <code>CUS-</code>, <code>TXN-</code>) or customer name. Press <code>Esc</code> to close.
            </div>
          )}

          {loading && (
            <div className="text-xs text-slate-500 dark:text-zinc-400 py-2">Searching SQLite workbench...</div>
          )}

          {result && result.total_hits === 0 && !loading && (
            <div className="text-xs text-slate-500 dark:text-zinc-400 py-6 text-center">
              No matching records found for &ldquo;{result.query}&rdquo;.
            </div>
          )}

          {result &&
            groupLabels.map(({ key, label }) => {
              const rows = result.groups[key] || [];
              if (rows.length === 0) return null;
              return (
                <div key={key} className="space-y-1.5">
                  <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 px-1">
                    {label} ({rows.length})
                  </div>
                  {rows.map((r) => (
                    <button
                      key={`${key}-${r.id}`}
                      type="button"
                      onClick={() => {
                        onSelectEntity(key, r.id);
                        onClose();
                      }}
                      className="w-full text-left flex items-center justify-between gap-3 px-3 py-2 rounded-2xl bg-white/25 dark:bg-white/[0.05] hover:bg-white/45 dark:hover:bg-white/[0.10] backdrop-blur-md border border-white/65 dark:border-white/12 transition text-xs"
                    >
                      <div className="min-w-0">
                        <div className="font-mono font-bold text-azure-700 dark:text-sky-300">{r.id}</div>
                        <div className="font-medium text-slate-900 dark:text-white truncate">{r.title}</div>
                        <div className="text-[11px] text-slate-600 dark:text-zinc-400 truncate">{r.subtitle}</div>
                      </div>
                      <Badge variant={tierVariant(r.badge)}>{r.badge}</Badge>
                    </button>
                  ))}
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
};
