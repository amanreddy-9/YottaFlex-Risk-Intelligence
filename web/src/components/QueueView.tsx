import React, { useState } from "react";
import { ArrowRight, CheckSquare, Download, Search } from "lucide-react";
import { api, downloadExport } from "../api/client";
import type { CaseListItem, EvaluationData, OverviewData } from "../types/workbench";
import { Badge, IosAmount, statusVariant, tierVariant } from "./Badge";
import { GlassPagination } from "./GlassPagination";
import { LiquidGlassCard, LiquidGlassSegmented, useRowGlassMagnifier } from "./LiquidGlassSurface";
import { SavedPresetsBar } from "./SavedPresetsBar";

interface QueueViewProps {
  overview: OverviewData | null;
  evaluation: EvaluationData | null;
  cases: CaseListItem[];
  totalCases: number;
  page: number;
  pageSize: number;
  sort: "priority" | "fifo";
  tier: string;
  status: string;
  linkage: string;
  search: string;
  assignedAnalyst: string;
  slaFilter: string;
  minExposure: string;
  maxExposure: string;
  startDate: string;
  endDate: string;
  onSortChange: (s: "priority" | "fifo") => void;
  onTierChange: (v: string) => void;
  onStatusChange: (v: string) => void;
  onLinkageChange: (v: string) => void;
  onSearchChange: (v: string) => void;
  onAssignedAnalystChange: (v: string) => void;
  onSlaFilterChange: (v: string) => void;
  onMinExposureChange: (v: string) => void;
  onMaxExposureChange: (v: string) => void;
  onStartDateChange: (v: string) => void;
  onEndDateChange: (v: string) => void;
  onPageChange: (nextPage: number) => void;
  onPageSizeChange: (nextSize: number) => void;
  onSelectCase: (caseId: string) => void;
  onQueueUpdated: () => Promise<void>;
}

export const QueueView: React.FC<QueueViewProps> = ({
  overview,
  evaluation,
  cases,
  totalCases,
  page,
  pageSize,
  sort,
  tier,
  status,
  linkage,
  search,
  assignedAnalyst,
  slaFilter,
  minExposure,
  maxExposure,
  startDate,
  endDate,
  onSortChange,
  onTierChange,
  onStatusChange,
  onLinkageChange,
  onSearchChange,
  onAssignedAnalystChange,
  onSlaFilterChange,
  onMinExposureChange,
  onMaxExposureChange,
  onStartDateChange,
  onEndDateChange,
  onPageChange,
  onPageSizeChange,
  onSelectCase,
  onQueueUpdated,
}) => {
  const rowMag = useRowGlassMagnifier();
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [bulkAction, setBulkAction] = useState("CLAIM_REVIEW");
  const [bulkAssignee, setBulkAssignee] = useState("ANL-001");
  const [bulkMsg, setBulkMsg] = useState<string | null>(null);

  const toggleCaseSel = (id: string) => {
    setSelectedCaseIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const applyBulkCases = async () => {
    if (selectedCaseIds.length === 0) return;
    setBulkMsg("Applying bulk queue action...");
    try {
      const res = await api.bulkTriageCases({
        case_ids: selectedCaseIds,
        action: bulkAction,
        assigned_analyst_id: bulkAction === "ASSIGN" ? bulkAssignee : undefined,
      });
      setSelectedCaseIds([]);
      setBulkMsg(`Updated ${res.updated_count} case(s)${res.skipped.length ? ` (${res.skipped.length} skipped)` : ""}.`);
      await onQueueUpdated();
    } catch (err) {
      setBulkMsg(err instanceof Error ? err.message : "Bulk queue action failed");
    }
  };
  const c = overview?.counts;
  const liftRatio =
    evaluation && evaluation.fifo_top20.recall > 0
      ? (evaluation.priority_top20.recall / evaluation.fifo_top20.recall).toFixed(2)
      : "—";

  const barColor = (t: string) =>
    t === "CRITICAL"
      ? "bg-rose-500 dark:bg-rose-400"
      : t === "HIGH"
      ? "bg-amber-500 dark:bg-amber-400"
      : t === "MEDIUM"
      ? "bg-azure-500 dark:bg-sky-400"
      : "bg-emerald-500 dark:bg-emerald-400";

  return (
    <div className="space-y-5">
      {/* Top KPI Bento Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <LiquidGlassCard variant="hero" className="rounded-2xl px-5 py-4 text-white">
          <div className="flex flex-col justify-between h-full">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-white/85">
                Total Case Exposure
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white/25 text-white backdrop-blur-sm ios-num">
                {c ? `${c.open_cases} Active` : "—"}
              </span>
            </div>
            <div className="mt-2 text-[26px] font-bold leading-tight text-white">
              <IosAmount value={c?.total_case_exposure} />
            </div>
            <div className="mt-1.5 text-[11.5px] text-white/85 ios-num">
              {c ? `${c.cases.toLocaleString("en-US")} cases • ${c.closed_cases} resolved` : "Loading..."}
            </div>
          </div>
        </LiquidGlassCard>

        <LiquidGlassCard className="rounded-2xl px-5 py-4">
          <div className="flex flex-col justify-between h-full">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700/80 dark:text-zinc-400">
              Monitored Ledger
            </div>
            <div className="mt-2 text-2xl font-bold ios-num text-slate-950 dark:text-white">
              {c ? c.transactions.toLocaleString("en-US") : "—"}
            </div>
            <div className="mt-1.5 text-[11.5px] text-slate-600/90 dark:text-zinc-400 ios-num">
              {c ? `${c.customers.toLocaleString("en-US")} customers • ${c.accounts.toLocaleString("en-US")} accounts` : ""}
            </div>
          </div>
        </LiquidGlassCard>

        <LiquidGlassCard className="rounded-2xl px-5 py-4">
          <div className="flex flex-col justify-between h-full">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700/80 dark:text-zinc-400">
              Alert &rarr; Case Compression
            </div>
            <div className="mt-2 text-2xl font-bold ios-num text-azure-700 dark:text-white">
              {overview ? `${overview.alert_to_case_compression}x` : "—"}
            </div>
            <div className="mt-1.5 text-[11.5px] text-slate-600/90 dark:text-zinc-400 ios-num">
              {c ? `${c.alerts.toLocaleString("en-US")} alerts grouped cleanly` : ""}
            </div>
          </div>
        </LiquidGlassCard>

        <LiquidGlassCard className="rounded-2xl px-5 py-4">
          <div className="flex flex-col justify-between h-full">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700/80 dark:text-zinc-400">
              Top-20% Capture Lift
            </div>
            <div className="mt-2 text-2xl font-bold ios-num text-slate-950 dark:text-white">
              {evaluation ? `${(evaluation.priority_top20.recall * 100).toFixed(1)}%` : "—"}
            </div>
            <div className="mt-1.5 text-[11.5px] text-slate-600/90 dark:text-zinc-400 ios-num">
              {evaluation ? `vs ${(evaluation.fifo_top20.recall * 100).toFixed(1)}% FIFO (${liftRatio}x lift)` : ""}
            </div>
          </div>
        </LiquidGlassCard>

        <LiquidGlassCard className="rounded-2xl px-5 py-4">
          <div className="flex flex-col justify-between h-full">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700/80 dark:text-zinc-400">
              Quarantine Exceptions
            </div>
            <div className="mt-2 text-2xl font-bold ios-num text-rose-600 dark:text-rose-400">
              {overview ? overview.quarantine_count : "—"}
            </div>
            <div className="mt-1.5 text-[11.5px] text-slate-600/90 dark:text-zinc-400">
              5/5 negative scenarios isolated
            </div>
          </div>
        </LiquidGlassCard>
      </div>

      {/* Main Clear Liquid Glass Queue Table */}
      <div className="liquid-glass rounded-2xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/30 space-y-2.5">
          {/* Row 1: Priority vs FIFO Switch, Search, Exports & Count */}
          <div className="flex flex-wrap items-center justify-between gap-2.5">
            <LiquidGlassSegmented
              value={sort}
              options={[
                { value: "priority", label: "Risk-Prioritized Queue" },
                { value: "fifo", label: "FIFO Baseline" },
              ]}
              onChange={onSortChange}
            />

            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-600 dark:text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => onSearchChange(e.target.value)}
                  placeholder="Search Case, Account, Customer..."
                  className="pl-8 pr-3 py-1.5 w-56 glass-pill rounded-full text-xs text-slate-950 dark:text-zinc-100 placeholder:text-slate-600 dark:placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-azure-500/40 dark:focus:ring-white/25"
                />
              </div>
              <button
                type="button"
                onClick={() =>
                  downloadExport(
                    api.casesExportUrl("csv", {
                      sort,
                      tier,
                      status,
                      linkage,
                      search,
                      assigned_analyst: assignedAnalyst,
                      min_exposure: minExposure,
                      max_exposure: maxExposure,
                      start_date: startDate,
                      end_date: endDate,
                      sla_breached: slaFilter === "ALL" ? undefined : slaFilter,
                    }),
                    "yottaflex_cases.csv"
                  )
                }
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-white/55 dark:bg-zinc-900 border border-white/80 dark:border-white/15 text-xs font-semibold text-azure-700 dark:text-white"
              >
                <Download className="w-3 h-3" /> CSV
              </button>
              <button
                type="button"
                onClick={() =>
                  downloadExport(
                    api.casesExportUrl("json", {
                      sort,
                      tier,
                      status,
                      linkage,
                      search,
                      assigned_analyst: assignedAnalyst,
                      min_exposure: minExposure,
                      max_exposure: maxExposure,
                      start_date: startDate,
                      end_date: endDate,
                      sla_breached: slaFilter === "ALL" ? undefined : slaFilter,
                    }),
                    "yottaflex_cases.json"
                  )
                }
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black text-xs font-semibold"
              >
                <Download className="w-3 h-3" /> JSON
              </button>
              <span className="ios-num text-xs font-semibold text-slate-700 dark:text-zinc-400">
                {totalCases} cases
              </span>
            </div>
          </div>

          {/* Row 2: Tier, Status, Linkage, Assignee, SLA, Exposure & Dates */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/30 dark:border-white/[0.06]">
            <select
              value={tier}
              onChange={(e) => onTierChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200 backdrop-blur-md focus:outline-none"
            >
              <option value="ALL">All Priority Tiers</option>
              <option value="CRITICAL">CRITICAL (&ge;80)</option>
              <option value="HIGH">HIGH (60–79)</option>
              <option value="MEDIUM">MEDIUM (40–59)</option>
              <option value="LOW">LOW (&lt;40)</option>
            </select>

            <select
              value={status}
              onChange={(e) => onStatusChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200 backdrop-blur-md focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE_QUEUE">Active Queue</option>
              <option value="OPEN">OPEN</option>
              <option value="IN_REVIEW">IN_REVIEW</option>
              <option value="ESCALATED">ESCALATED</option>
              <option value="SAR_FILED">SAR_FILED</option>
              <option value="CLOSED_CONFIRMED_FRAUD">CLOSED_CONFIRMED_FRAUD</option>
              <option value="CLOSED_FALSE_POSITIVE">CLOSED_FALSE_POSITIVE</option>
            </select>

            <select
              value={linkage}
              onChange={(e) => onLinkageChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200 backdrop-blur-md focus:outline-none"
            >
              <option value="ALL">All Linkage Types</option>
              <option value="TRANSFER_RING">TRANSFER_RING</option>
              <option value="SHARED_DEVICE">SHARED_DEVICE</option>
              <option value="MULTI_RULE_ACCOUNT">MULTI_RULE_ACCOUNT</option>
              <option value="SINGLE_ACCOUNT_BURST">SINGLE_ACCOUNT_BURST</option>
            </select>

            <select
              value={assignedAnalyst}
              onChange={(e) => onAssignedAnalystChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200 backdrop-blur-md focus:outline-none"
              aria-label="Filter by assigned analyst"
            >
              <option value="ALL">All Assignees</option>
              <option value="UNASSIGNED">Unassigned</option>
              <option value="ANL-001">ANL-001 (Analyst)</option>
              <option value="ANL-002">ANL-002 (Analyst)</option>
              <option value="ANL-003">ANL-003 (Reviewer)</option>
              <option value="ADM-001">ADM-001 (Admin)</option>
            </select>

            <select
              value={slaFilter}
              onChange={(e) => onSlaFilterChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200 backdrop-blur-md focus:outline-none"
              aria-label="Filter by Case SLA"
            >
              <option value="ALL">All SLA States</option>
              <option value="1">SLA Breached</option>
              <option value="0">Within SLA</option>
            </select>

            <input
              type="number"
              value={minExposure}
              onChange={(e) => onMinExposureChange(e.target.value)}
              placeholder="Min $"
              className="w-24 glass-pill rounded-full px-3 py-1.5 text-xs ios-num text-slate-900 dark:text-zinc-100 placeholder:text-slate-600 dark:placeholder:text-zinc-500 focus:outline-none"
            />
            <input
              type="number"
              value={maxExposure}
              onChange={(e) => onMaxExposureChange(e.target.value)}
              placeholder="Max $"
              className="w-24 glass-pill rounded-full px-3 py-1.5 text-xs ios-num text-slate-900 dark:text-zinc-100 placeholder:text-slate-600 dark:placeholder:text-zinc-500 focus:outline-none"
            />
            <input
              type="date"
              value={startDate}
              onChange={(e) => onStartDateChange(e.target.value)}
              aria-label="Queue start date"
              className="glass-pill rounded-full px-2.5 py-1.5 text-xs ios-num text-slate-800 dark:text-zinc-200 focus:outline-none"
            />
            <input
              type="date"
              value={endDate}
              onChange={(e) => onEndDateChange(e.target.value)}
              aria-label="Queue end date"
              className="glass-pill rounded-full px-2.5 py-1.5 text-xs ios-num text-slate-800 dark:text-zinc-200 focus:outline-none"
            />
          </div>

          <div className="pt-2 border-t border-white/25 dark:border-white/[0.06]">
            <SavedPresetsBar
              workspace="queue"
              currentFilters={{ sort, tier, status, linkage, assignedAnalyst, slaFilter, search }}
              onApplyPreset={(f) => {
                if (typeof f.sort === "string") onSortChange(f.sort === "fifo" ? "fifo" : "priority");
                if (typeof f.tier === "string") onTierChange(f.tier);
                if (typeof f.status === "string") onStatusChange(f.status);
                if (typeof f.linkage === "string") onLinkageChange(f.linkage);
                if (typeof f.assignedAnalyst === "string") onAssignedAnalystChange(f.assignedAnalyst);
                if (typeof f.slaFilter === "string") onSlaFilterChange(f.slaFilter);
                if (typeof f.search === "string") onSearchChange(f.search);
              }}
            />
          </div>
        </div>

        {(selectedCaseIds.length > 0 || bulkMsg) && (
          <div className="px-5 py-2.5 border-b border-white/50 dark:border-white/10 bg-azure-500/10 dark:bg-sky-500/10 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <CheckSquare className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              <span className="font-semibold text-slate-900 dark:text-white">{selectedCaseIds.length} case(s) selected</span>
              {selectedCaseIds.length > 0 && (
                <>
                  <select
                    value={bulkAction}
                    onChange={(e) => setBulkAction(e.target.value)}
                    className="glass-pill rounded-full px-2.5 py-1 font-medium"
                  >
                    <option value="CLAIM_REVIEW">Claim Review</option>
                    <option value="ESCALATE">Escalate Batch</option>
                    <option value="ASSIGN">Assign Analyst</option>
                  </select>
                  {bulkAction === "ASSIGN" && (
                    <select
                      value={bulkAssignee}
                      onChange={(e) => setBulkAssignee(e.target.value)}
                      className="glass-pill rounded-full px-2.5 py-1 font-medium"
                    >
                      <option value="ANL-001">ANL-001</option>
                      <option value="ANL-002">ANL-002</option>
                      <option value="ANL-003">ANL-003</option>
                      <option value="ADM-001">ADM-001</option>
                    </select>
                  )}
                  <button
                    type="button"
                    onClick={applyBulkCases}
                    className="px-3.5 py-1 rounded-full bg-azure-600 dark:bg-white text-white dark:text-black font-semibold"
                  >
                    Apply Batch
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedCaseIds([])}
                    className="px-2.5 py-1 rounded-full bg-white/55 dark:bg-zinc-900 text-slate-700 dark:text-zinc-300"
                  >
                    Clear
                  </button>
                </>
              )}
            </div>
            {bulkMsg && (
              <div className="flex items-center gap-2 font-medium text-azure-800 dark:text-sky-300">
                <span>{bulkMsg}</span>
                <button type="button" onClick={() => setBulkMsg(null)} className="underline text-[11px]">
                  Dismiss
                </button>
              </div>
            )}
          </div>
        )}

        <div ref={rowMag.containerRef} onMouseLeave={rowMag.onContainerLeave} className="relative overflow-x-auto">
          {rowMag.lensElement}
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                <th className="py-3 pl-4 pr-2 w-8">
                  <input
                    type="checkbox"
                    aria-label="Select all cases"
                    checked={cases.length > 0 && cases.every((c) => selectedCaseIds.includes(c.case_id))}
                    onChange={(e) =>
                      setSelectedCaseIds(e.target.checked ? cases.map((c) => c.case_id) : [])
                    }
                  />
                </th>
                <th className="py-3 px-4">Rank / Δ FIFO</th>
                <th className="py-3 px-3">Case ID</th>
                <th className="py-3 px-3">Primary Customer</th>
                <th className="py-3 px-3">Linkage Pattern</th>
                <th className="py-3 px-3">Rules Fired</th>
                <th className="py-3 px-3 text-right">Accts</th>
                <th className="py-3 px-3 text-right">Alerts</th>
                <th className="py-3 px-3 text-right">Exposure</th>
                <th className="py-3 px-3">Priority Score</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
              {cases.map((item) => (
                <tr
                  key={item.case_id}
                  onMouseEnter={(e) => rowMag.onRowEnter(e.currentTarget)}
                  onClick={() => onSelectCase(item.case_id)}
                  className="liquid-row-magnify cursor-pointer"
                >
                  <td className="py-3 pl-4 pr-2" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Select ${item.case_id}`}
                      checked={selectedCaseIds.includes(item.case_id)}
                      onChange={() => toggleCaseSel(item.case_id)}
                    />
                  </td>
                  <td className="py-3 px-4 ios-num font-semibold text-slate-600 dark:text-zinc-400">
                    <div>#{item.queue_rank}</div>
                    {item.fifo_rank !== undefined && item.rank_delta !== undefined && (
                      <div className="mt-0.5 flex items-center gap-1 text-[10px]">
                        <span className="text-slate-500 dark:text-zinc-500">FIFO #{item.fifo_rank}</span>
                        {item.rank_delta !== 0 && (
                          <span className={item.rank_delta > 0 ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-slate-500"}>
                            {item.rank_delta > 0 ? `+${item.rank_delta}` : item.rank_delta}
                          </span>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-mono font-semibold text-slate-950 dark:text-white">{item.case_id}</div>
                    <div className="ios-num text-[11px] text-slate-600 dark:text-zinc-500">
                      {item.created_at.slice(0, 16).replace("T", " ")} UTC
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-semibold text-slate-950 dark:text-zinc-100">{item.customer_name}</div>
                    <div className="font-mono text-[11px] text-slate-600 dark:text-zinc-400">
                      {item.primary_customer_id} • {item.kyc_tier}
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <Badge variant="BLUE">{item.linkage_summary}</Badge>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex flex-wrap gap-1">
                      {item.rules_triggered.map((r) => (
                        <Badge key={r} variant="NEUTRAL">
                          {r}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right ios-num font-medium text-slate-900 dark:text-zinc-200">
                    {item.linked_account_count}
                  </td>
                  <td className="py-3 px-3 text-right ios-num font-medium text-slate-900 dark:text-zinc-200">
                    {item.alert_count}
                  </td>
                  <td className="py-3 px-3 text-right font-semibold text-slate-950 dark:text-white text-[13px]">
                    <IosAmount value={item.total_exposure_amount} />
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2.5 min-w-[165px]">
                      <span className="ios-num font-bold w-10 text-slate-950 dark:text-white">
                        {(item.effective_priority_score ?? item.priority_score).toFixed(1)}
                      </span>
                      <div className="flex-1 h-1.5 rounded-full bg-white/45 dark:bg-zinc-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${barColor(item.effective_priority_tier ?? item.priority_tier)}`}
                          style={{ width: `${Math.min(100, item.effective_priority_score ?? item.priority_score)}%` }}
                        />
                      </div>
                      <Badge variant={tierVariant(item.effective_priority_tier ?? item.priority_tier)}>
                        {item.effective_priority_tier ?? item.priority_tier}
                      </Badge>
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex flex-wrap items-center gap-1">
                      <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                      {item.sla_breached && <Badge variant="CRITICAL">SLA</Badge>}
                      {item.assigned_analyst_id && <Badge variant="BLUE">{item.assigned_analyst_id}</Badge>}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold text-azure-700 dark:text-white bg-white/55 dark:bg-zinc-800/80 border border-white/80 dark:border-white/15 hover:bg-white dark:hover:bg-zinc-700 transition"
                    >
                      Inspect <ArrowRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <GlassPagination
          total={totalCases}
          page={page}
          pageSize={pageSize}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
          unitLabel="cases"
        />
      </div>
    </div>
  );
};
