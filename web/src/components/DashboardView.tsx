import React, { useState } from "react";
import { Download } from "lucide-react";
import { api, downloadExport } from "../api/client";
import type { DashboardData } from "../types/workbench";
import { Badge, IosAmount, statusVariant, tierVariant } from "./Badge";
import { LiquidGlassCard, LiquidGlassSegmented, useRowGlassMagnifier } from "./LiquidGlassSurface";

interface DashboardViewProps {
  data: DashboardData | null;
  darkMode: boolean;
  filters: {
    period: string;
    start_date: string;
    end_date: string;
    risk_level: string;
    txn_type: string;
    status: string;
  };
  onFiltersChange: (next: DashboardViewProps["filters"]) => void;
  onOpenCustomer: (customerId: string) => void;
  onOpenAccount: (accountId: string) => void;
  onOpenTransaction: (transactionId: string) => void;
  onFilterTransactionsRisk: (riskLevel: "HIGH" | "MEDIUM" | "LOW") => void;
  onOpenCase: (caseId: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  data,
  darkMode,
  filters,
  onFiltersChange,
  onOpenCustomer,
  onOpenAccount,
  onOpenTransaction,
  onFilterTransactionsRisk,
  onOpenCase,
}) => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const suspMag = useRowGlassMagnifier();
  const actMag = useRowGlassMagnifier();
  const custMag = useRowGlassMagnifier();
  const acctMag = useRowGlassMagnifier();

  if (!data) {
    return <div className="liquid-glass rounded-2xl p-8 text-center text-xs">Loading dashboard analytics...</div>;
  }

  const s = data.summary;
  const totalRiskTxns = Math.max(1, s.high_risk_txns + s.medium_risk_txns + s.low_risk_txns);
  const maxRuleCount = Math.max(1, ...data.rule_distribution.map((r) => r.alert_count));

  const W = 620;
  const H = 220;
  const pad = { l: 46, r: 16, t: 20, b: 32 };
  const pw = W - pad.l - pad.r;
  const ph = H - pad.t - pad.b;
  const pts = data.volume_series;
  const maxVol = Math.max(1, ...pts.map((p) => p.volume_usd));
  const maxSusp = Math.max(1, ...pts.map((p) => p.suspicious_count));

  const xPos = (i: number) => pad.l + (pts.length <= 1 ? pw / 2 : (i / (pts.length - 1)) * pw);
  const yVol = (v: number) => pad.t + ph - (v / maxVol) * ph;
  const ySusp = (v: number) => pad.t + ph - (v / maxSusp) * ph;

  const volPath = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xPos(i)} ${yVol(p.volume_usd)}`).join(" ");
  const volArea =
    pts.length > 0
      ? `${volPath} L ${xPos(pts.length - 1)} ${pad.t + ph} L ${xPos(0)} ${pad.t + ph} Z`
      : "";
  const suspPath = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xPos(i)} ${ySusp(p.suspicious_count)}`).join(" ");

  const exportCsvUrl = api.dashboardExportUrl("csv", filters);
  const exportJsonUrl = api.dashboardExportUrl("json", filters);

  const activePeriod = (["7D", "30D", "90D", "ALL"].includes(filters.period) ? filters.period : "ALL") as
    | "7D"
    | "30D"
    | "90D"
    | "ALL";

  return (
    <div className="space-y-5">
      {/* Filter & Export Toolbar with Sliding Glass Magnifier for Time Duration */}
      <div className="liquid-glass rounded-2xl px-5 py-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          <LiquidGlassSegmented
            value={activePeriod}
            options={[
              { value: "7D", label: "7D" },
              { value: "30D", label: "30D" },
              { value: "90D", label: "90D" },
              { value: "ALL", label: "ALL" },
            ]}
            onChange={(p) => onFiltersChange({ ...filters, period: p, start_date: "", end_date: "" })}
          />

          <input
            type="date"
            value={filters.start_date}
            onChange={(e) => onFiltersChange({ ...filters, start_date: e.target.value, period: "CUSTOM" })}
            className="glass-pill rounded-full px-3 py-1.5 text-xs ios-num backdrop-blur-md"
            aria-label="Start Date"
          />
          <input
            type="date"
            value={filters.end_date}
            onChange={(e) => onFiltersChange({ ...filters, end_date: e.target.value, period: "CUSTOM" })}
            className="glass-pill rounded-full px-3 py-1.5 text-xs ios-num backdrop-blur-md"
            aria-label="End Date"
          />

          <select
            value={filters.risk_level}
            onChange={(e) => onFiltersChange({ ...filters, risk_level: e.target.value })}
            className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium backdrop-blur-md"
          >
            <option value="ALL">All Risk Levels</option>
            <option value="HIGH">High-Risk Txns</option>
            <option value="MEDIUM">Medium-Risk Txns</option>
            <option value="LOW">Low-Risk Txns</option>
          </select>

          <select
            value={filters.txn_type}
            onChange={(e) => onFiltersChange({ ...filters, txn_type: e.target.value })}
            className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium backdrop-blur-md"
          >
            <option value="ALL">All Txn Types</option>
            <option value="MERCHANT_PURCHASE">MERCHANT_PURCHASE</option>
            <option value="P2P_TRANSFER_OUT">P2P_TRANSFER_OUT</option>
            <option value="INTERNAL_TRANSFER_OUT">INTERNAL_TRANSFER_OUT</option>
            <option value="WIRE_OUT">WIRE_OUT</option>
            <option value="WIRE_IN">WIRE_IN</option>
            <option value="PAYROLL_CREDIT">PAYROLL_CREDIT</option>
            <option value="ATM_WITHDRAWAL">ATM_WITHDRAWAL</option>
          </select>

          <select
            value={filters.status}
            onChange={(e) => onFiltersChange({ ...filters, status: e.target.value })}
            className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium backdrop-blur-md"
          >
            <option value="ALL">All Statuses</option>
            <option value="POSTED">Txn: POSTED</option>
            <option value="OPEN">Case: OPEN</option>
            <option value="IN_REVIEW">Case: IN_REVIEW</option>
            <option value="ESCALATED">Case: ESCALATED</option>
          </select>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <button
            type="button"
            onClick={() => downloadExport(exportCsvUrl, "yottaflex_dashboard_report.csv")}
            className="glass-pill inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full font-semibold text-azure-700 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
          >
            <Download className="w-3.5 h-3.5" /> Export CSV
          </button>
          <button
            type="button"
            onClick={() => downloadExport(exportJsonUrl, "yottaflex_dashboard_report.json")}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black font-semibold transition backdrop-blur-md"
          >
            <Download className="w-3.5 h-3.5" /> Export JSON
          </button>
        </div>
      </div>

      {/* KPI Row 1: Interactive Specular Glass Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3.5">
        <LiquidGlassCard variant="hero" className="rounded-2xl p-4 text-white col-span-2 sm:col-span-2 lg:col-span-2">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-white/85">
            Filtered Ledger Volume
          </div>
          <div className="mt-1.5 text-2xl font-bold text-white">
            <IosAmount value={s.total_volume_usd} />
          </div>
          <div className="mt-1 text-[11.5px] text-white/85 ios-num">
            {s.transactions.toLocaleString("en-US")} transactions evaluated
          </div>
        </LiquidGlassCard>

        {[
          { label: "Customers", val: s.customers.toLocaleString("en-US") },
          { label: "Accounts", val: s.accounts.toLocaleString("en-US") },
          { label: "Merchants", val: s.merchants.toLocaleString("en-US") },
          { label: "Devices", val: s.devices.toLocaleString("en-US") },
          { label: "Alerts / Cases", val: `${s.alerts.toLocaleString("en-US")} / ${s.cases}` },
        ].map((k) => (
          <LiquidGlassCard key={k.label} className="rounded-2xl p-4">
            <div className="flex flex-col justify-between h-full">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700/80 dark:text-zinc-400">
                {k.label}
              </div>
              <div className="mt-2 text-xl font-bold ios-num text-slate-950 dark:text-white">{k.val}</div>
            </div>
          </LiquidGlassCard>
        ))}
      </div>

      {/* KPI Row 2: Colored Liquid Glass Risk Breakdown + Case Lifecycle */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="liquid-glass rounded-2xl p-4">
          <div className="text-xs font-semibold text-slate-900 dark:text-zinc-100 mb-3">
            Transaction Risk Classification Breakdown
          </div>
          <div className="grid grid-cols-3 gap-3">
            <LiquidGlassCard
              variant="rose"
              onClick={() => onFilterTransactionsRisk("HIGH")}
              className="rounded-2xl p-3.5 cursor-pointer"
            >
              <div className="text-[10.5px] font-semibold uppercase text-rose-800 dark:text-rose-300">
                High-Risk Txns
              </div>
              <div className="mt-1 text-xl font-bold ios-num text-rose-800 dark:text-rose-200">
                {s.high_risk_txns.toLocaleString("en-US")}
              </div>
              <div className="text-[11px] ios-num font-semibold text-rose-700/85 dark:text-rose-300/80">
                {((s.high_risk_txns / totalRiskTxns) * 100).toFixed(2)}%
              </div>
            </LiquidGlassCard>

            <LiquidGlassCard
              variant="amber"
              onClick={() => onFilterTransactionsRisk("MEDIUM")}
              className="rounded-2xl p-3.5 cursor-pointer"
            >
              <div className="text-[10.5px] font-semibold uppercase text-amber-800 dark:text-amber-300">
                Medium-Risk Txns
              </div>
              <div className="mt-1 text-xl font-bold ios-num text-amber-800 dark:text-amber-200">
                {s.medium_risk_txns.toLocaleString("en-US")}
              </div>
              <div className="text-[11px] ios-num font-semibold text-amber-700/85 dark:text-amber-300/80">
                {((s.medium_risk_txns / totalRiskTxns) * 100).toFixed(2)}%
              </div>
            </LiquidGlassCard>

            <LiquidGlassCard
              variant="emerald"
              onClick={() => onFilterTransactionsRisk("LOW")}
              className="rounded-2xl p-3.5 cursor-pointer"
            >
              <div className="text-[10.5px] font-semibold uppercase text-emerald-800 dark:text-emerald-300">
                Low-Risk Txns
              </div>
              <div className="mt-1 text-xl font-bold ios-num text-emerald-800 dark:text-emerald-200">
                {s.low_risk_txns.toLocaleString("en-US")}
              </div>
              <div className="text-[11px] ios-num font-semibold text-emerald-700/85 dark:text-emerald-300/80">
                {((s.low_risk_txns / totalRiskTxns) * 100).toFixed(2)}%
              </div>
            </LiquidGlassCard>
          </div>
        </div>

        <div className="liquid-glass rounded-2xl p-4">
          <div className="text-xs font-semibold text-slate-900 dark:text-zinc-100 mb-3">
            Investigation Case Lifecycle Status
          </div>
          <div className="grid grid-cols-4 gap-2.5">
            {[
              { label: "Open", val: s.open_cases, cls: "text-azure-700 dark:text-white" },
              { label: "Under Review", val: s.under_investigation_cases, cls: "text-amber-700 dark:text-amber-300" },
              { label: "Escalated", val: s.escalated_cases, cls: "text-rose-700 dark:text-rose-300" },
              { label: "Closed", val: s.closed_cases, cls: "text-emerald-700 dark:text-emerald-300" },
            ].map((cs) => (
              <LiquidGlassCard key={cs.label} className="rounded-2xl p-3">
                <div className="text-[10.5px] font-semibold uppercase text-slate-600 dark:text-zinc-400">
                  {cs.label}
                </div>
                <div className={`mt-1 text-xl font-bold ios-num ${cs.cls}`}>{cs.val}</div>
              </LiquidGlassCard>
            ))}
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <LiquidGlassCard className="lg:col-span-7 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Transaction Volume &amp; Suspicious Activity Trends
              </h3>
              <p className="text-xs text-slate-700/80 dark:text-zinc-400">
                Blue area = USD volume • Rose line = suspicious activity count (hover points for detail)
              </p>
            </div>
            {hoverIdx !== null && pts[hoverIdx] && (
              <div className="glass-pill px-3 py-1 rounded-full text-[11px] ios-num">
                {pts[hoverIdx].start_day}: <IosAmount value={pts[hoverIdx].volume_usd} /> • {pts[hoverIdx].suspicious_count} susp.
              </div>
            )}
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block">
            <defs>
              <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={darkMode ? "#FFFFFF" : "#1D84FA"} stopOpacity={darkMode ? 0.25 : 0.40} />
                <stop offset="100%" stopColor={darkMode ? "#FFFFFF" : "#1D84FA"} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            {[0, 0.5, 1].map((f) => {
              const y = pad.t + ph * (1 - f);
              return (
                <line
                  key={f}
                  x1={pad.l}
                  y1={y}
                  x2={W - pad.r}
                  y2={y}
                  stroke={darkMode ? "#27272A" : "rgba(255,255,255,0.55)"}
                  strokeDasharray="3,3"
                />
              );
            })}
            {volArea && <path d={volArea} fill="url(#volGrad)" />}
            {volPath && <path d={volPath} fill="none" stroke={darkMode ? "#FFFFFF" : "#0A66E6"} strokeWidth="2.5" />}
            {suspPath && <path d={suspPath} fill="none" stroke="#F43F5E" strokeWidth="2" strokeDasharray="4,3" />}
            {pts.map((p, i) => (
              <g key={`${p.start_day}-${i}`}>
                <circle
                  cx={xPos(i)}
                  cy={yVol(p.volume_usd)}
                  r={hoverIdx === i ? 5 : 2.5}
                  fill={darkMode ? "#FFFFFF" : "#0A66E6"}
                  className="cursor-pointer"
                  onMouseEnter={() => setHoverIdx(i)}
                  onMouseLeave={() => setHoverIdx(null)}
                />
                {(i === 0 || i === pts.length - 1 || i % Math.max(1, Math.floor(pts.length / 6)) === 0) && (
                  <text
                    x={xPos(i)}
                    y={H - 10}
                    textAnchor="middle"
                    fontSize="10"
                    fill={darkMode ? "#A1A1AA" : "#334155"}
                  >
                    {p.label}
                  </text>
                )}
              </g>
            ))}
          </svg>
        </LiquidGlassCard>

        <LiquidGlassCard className="lg:col-span-5 rounded-2xl p-5">
          <h3 className="text-sm font-semibold text-slate-950 dark:text-white mb-1">
            Rule-Wise Alert Distribution
          </h3>
          <p className="text-xs text-slate-700/80 dark:text-zinc-400 mb-4">
            Transparent rule contribution across active filter window
          </p>
          <div className="space-y-2.5">
            {data.rule_distribution.map((r) => (
              <div key={r.rule_id} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-900 dark:text-zinc-200 truncate pr-2">
                    <span className="font-mono font-semibold text-azure-700 dark:text-white">{r.rule_id}</span>{" "}
                    {r.rule_name}
                  </span>
                  <span className="ios-num font-bold text-slate-950 dark:text-white">{r.alert_count}</span>
                </div>
                <div className="h-2 rounded-full bg-white/45 dark:bg-zinc-800/80 overflow-hidden border border-white/60 dark:border-white/10">
                  <div
                    className="h-full rounded-full bg-azure-600 dark:bg-white"
                    style={{ width: `${Math.round((r.alert_count / maxRuleCount) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </LiquidGlassCard>
      </div>

      {/* Feeds with Sliding Glass Row Magnifier (Image 7) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7 liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Recent Suspicious Transactions</h3>
          </div>
          <div
            ref={suspMag.containerRef}
            onMouseLeave={suspMag.onContainerLeave}
            className="relative overflow-x-auto max-h-80"
          >
            {suspMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 z-10 bg-white/45 dark:bg-black/65 backdrop-blur-md border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                <tr>
                  <th className="py-2.5 px-4">Transaction</th>
                  <th className="py-2.5 px-3">Customer</th>
                  <th className="py-2.5 px-3">Rule</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-4 text-right">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {data.recent_suspicious_txns.map((tx) => (
                  <tr
                    key={tx.transaction_id}
                    onMouseEnter={(e) => suspMag.onRowEnter(e.currentTarget)}
                    onClick={() => onOpenTransaction(tx.transaction_id)}
                    className="liquid-row-magnify cursor-pointer"
                  >
                    <td className="py-2.5 px-4">
                      <div className="font-mono font-semibold text-slate-950 dark:text-white">{tx.transaction_id}</div>
                      <div className="ios-num text-[11px] text-slate-600 dark:text-zinc-400">{tx.occurred_at}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="font-semibold text-slate-900 dark:text-zinc-100">{tx.customer_name}</div>
                      <div className="font-mono text-[11px] text-slate-600 dark:text-zinc-400">{tx.account_id}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{tx.rule_id || "MERCHANT_RISK"}</span>
                    </td>
                    <td className="py-2.5 px-3 text-right font-semibold text-slate-950 dark:text-white">
                      <IosAmount value={tx.amount} />
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <Badge variant={tierVariant(tx.risk_level)}>
                        {tx.risk_level} ({tx.risk_score.toFixed(0)})
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lg:col-span-5 liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Recent Alerts &amp; Case Activity</h3>
          </div>
          <div
            ref={actMag.containerRef}
            onMouseLeave={actMag.onContainerLeave}
            className="relative p-3 space-y-2 max-h-80 overflow-y-auto text-xs"
          >
            {actMag.lensElement}
            {data.recent_case_events.map((ev) => (
              <div
                key={ev.id}
                onMouseEnter={(e) => actMag.onRowEnter(e.currentTarget)}
                onClick={() => onOpenCase(ev.case_id)}
                className="liquid-row-magnify cursor-pointer rounded-xl px-3.5 py-2.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-azure-700 dark:text-white">{ev.case_id}</span>
                  <Badge variant={statusVariant(ev.new_status)}>{ev.new_status}</Badge>
                </div>
                <div className="text-[11px] text-slate-700 dark:text-zinc-300 mt-1">
                  {ev.action_type ? `${ev.analyst_id}: ${ev.action_type}` : "Automated clustering"} • {ev.occurred_at}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top High-Risk Customers & Accounts with Vertical Sliding Liquid-Glass Magnifier (Image 7) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Top High-Risk Customers</h3>
          </div>
          <div ref={custMag.containerRef} onMouseLeave={custMag.onContainerLeave} className="relative overflow-x-auto">
            {custMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Customer</th>
                  <th className="py-2.5 px-3">KYC</th>
                  <th className="py-2.5 px-3 text-right">Cases</th>
                  <th className="py-2.5 px-3 text-right">Exposure</th>
                  <th className="py-2.5 px-4 text-right">Max Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {data.top_risk_customers.map((cu) => (
                  <tr
                    key={cu.customer_id}
                    onMouseEnter={(e) => custMag.onRowEnter(e.currentTarget)}
                    onClick={() => onOpenCustomer(cu.customer_id)}
                    className="liquid-row-magnify cursor-pointer"
                  >
                    <td className="py-2.5 px-4">
                      <div className="font-semibold text-slate-950 dark:text-white">{cu.full_name}</div>
                      <div className="font-mono text-[11px] text-slate-600 dark:text-zinc-400">{cu.customer_id}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant="NEUTRAL">{cu.kyc_tier}</Badge>
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num">{cu.case_count}</td>
                    <td className="py-2.5 px-3 text-right font-semibold text-slate-950 dark:text-white">
                      <IosAmount value={cu.total_exposure} />
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <Badge variant="CRITICAL">{cu.max_priority_score.toFixed(1)}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Top High-Risk Accounts</h3>
          </div>
          <div ref={acctMag.containerRef} onMouseLeave={acctMag.onContainerLeave} className="relative overflow-x-auto">
            {acctMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Account</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Alerts</th>
                  <th className="py-2.5 px-3 text-right">Balance</th>
                  <th className="py-2.5 px-4 text-right">Max Alert</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {data.top_risk_accounts.map((a) => (
                  <tr
                    key={a.account_id}
                    onMouseEnter={(e) => acctMag.onRowEnter(e.currentTarget)}
                    onClick={() => onOpenAccount(a.account_id)}
                    className="liquid-row-magnify cursor-pointer"
                  >
                    <td className="py-2.5 px-4">
                      <div className="font-mono font-semibold text-slate-950 dark:text-white">{a.account_id}</div>
                      <div className="text-[11px] text-slate-600 dark:text-zinc-400">{a.customer_name}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant="BLUE">{a.status}</Badge>
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num">{a.alert_count}</td>
                    <td className="py-2.5 px-3 text-right font-semibold text-slate-950 dark:text-white">
                      <IosAmount value={a.current_balance} />
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <Badge variant="HIGH">{a.max_risk_score.toFixed(1)}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
