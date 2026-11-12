import React from "react";
import type { PriorityTier, Waterfall } from "../types/workbench";
import { Badge, tierVariant } from "./Badge";

export const WaterfallCard: React.FC<{
  score: number;
  tier: PriorityTier;
  waterfall: Waterfall;
}> = ({ score, tier, waterfall }) => {
  const rows = [
    { label: "Rule Severity", val: waterfall.rule_severity, max: 48, bar: "bg-azure-600 dark:bg-white" },
    { label: "Network Blast Radius", val: waterfall.network_blast_radius, max: 26, bar: "bg-sky-500 dark:bg-zinc-300" },
    { label: "Financial Exposure", val: waterfall.financial_exposure, max: 18, bar: "bg-indigo-500 dark:bg-zinc-400" },
    { label: "Entity & Lifecycle", val: waterfall.entity_lifecycle_context, max: 15, bar: "bg-slate-500 dark:bg-zinc-500" },
    { label: "Benign Mitigators", val: waterfall.benign_mitigators, max: 35, bar: "bg-emerald-500 dark:bg-emerald-400", isNeg: true },
  ];

  return (
    <div className="liquid-glass rounded-2xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-white/60 dark:border-white/10 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Explainable Priority Waterfall</h3>
          <p className="text-xs text-slate-600 dark:text-zinc-400">Additive factor decomposition (zero leakage)</p>
        </div>
        <Badge variant={tierVariant(tier)}>{tier}</Badge>
      </div>

      <div className="p-5 space-y-3">
        {rows.map((r) => {
          const pct = Math.min(100, Math.round((Math.abs(r.val) / r.max) * 100));
          const sign = r.val > 0 ? "+" : "";
          return (
            <div key={r.label} className="grid grid-cols-[150px_1fr_56px] items-center gap-3 text-xs">
              <span className="font-medium text-slate-700 dark:text-zinc-300">{r.label}</span>
              <div className="h-2 rounded-full bg-slate-900/10 dark:bg-white/10 overflow-hidden backdrop-blur-sm">
                <div className={`h-full rounded-full ${r.bar}`} style={{ width: `${pct}%` }} />
              </div>
              <span
                className={`text-right ios-num font-semibold ${
                  r.isNeg && r.val < 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-900 dark:text-white"
                }`}
              >
                {sign}
                {r.val.toFixed(1)}
              </span>
            </div>
          );
        })}

        <div className="pt-3 border-t border-white/60 dark:border-white/10 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-zinc-400">
            Composite Priority Score
          </span>
          <span className="ios-num text-base font-bold text-azure-700 dark:text-white">
            {score.toFixed(2)} / 100
          </span>
        </div>
      </div>
    </div>
  );
};
