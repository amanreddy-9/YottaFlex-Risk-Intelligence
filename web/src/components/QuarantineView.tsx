import React, { useEffect, useState } from "react";
import {
  CheckSquare,
  Download,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, downloadExport } from "../api/client";
import type {
  IntegrityCheckReport,
  QuarantineData,
  QuarantineDetail,
  QuarantineExceptionItem,
} from "../types/workbench";
import { Badge, tierVariant } from "./Badge";
import { GlassPagination } from "./GlassPagination";
import { LiquidGlassCard, useRowGlassMagnifier } from "./LiquidGlassSurface";

interface QuarantineViewProps {
  data: QuarantineData | null;
  onRefresh: () => Promise<void>;
  onOpenAccount?: (accountId: string) => void;
  onOpenTransaction?: (txnId: string) => void;
}

const REVIEW_STATUSES = ["ALL", "PENDING", "ACKNOWLEDGED", "REMEDIATED", "WAIVED"] as const;

export const QuarantineView: React.FC<QuarantineViewProps> = ({
  data,
  onRefresh,
  onOpenAccount,
  onOpenTransaction,
}) => {
  const rowMag = useRowGlassMagnifier();

  const [filteredData, setFilteredData] = useState<QuarantineData | null>(data);
  const [search, setSearch] = useState("");
  const [issueType, setIssueType] = useState("ALL");
  const [severity, setSeverity] = useState("ALL");
  const [reviewStatus, setReviewStatus] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState("severity");
  const [loadingList, setLoadingList] = useState(false);

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkStatus, setBulkStatus] = useState<"ACKNOWLEDGED" | "REMEDIATED" | "WAIVED">("REMEDIATED");
  const [bulkNote, setBulkNote] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [statusBanner, setStatusBanner] = useState<string | null>(null);

  const [detail, setDetail] = useState<QuarantineDetail | null>(null);
  const [singleStatus, setSingleStatus] = useState<"PENDING" | "ACKNOWLEDGED" | "REMEDIATED" | "WAIVED">("REMEDIATED");
  const [singleNote, setSingleNote] = useState("");
  const [singleAction, setSingleAction] = useState("");
  const [savingSingle, setSavingSingle] = useState(false);

  const [integrityReport, setIntegrityReport] = useState<IntegrityCheckReport | null>(null);
  const [runningChecks, setRunningChecks] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(30);

  const fetchFiltered = async () => {
    setLoadingList(true);
    try {
      const res = await api.quarantine({
        search: search || undefined,
        issue_type: issueType,
        severity,
        review_status: reviewStatus,
        sort_by: sortBy,
      });
      setFilteredData(res);
    } catch {
      // Fallback to parent data if query temporarily fails
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    setFilteredData(data);
  }, [data]);

  useEffect(() => {
    setPage(0);
    fetchFiltered();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, issueType, severity, reviewStatus, sortBy]);

  const active = filteredData || data;
  if (!active) return null;

  const issueTypes = Object.keys(active.counts_by_issue_type || {});
  const items: QuarantineExceptionItem[] = active.exceptions || [];
  const pagedItems = items.slice(page * pageSize, (page + 1) * pageSize);
  const reviewCounts = active.counts_by_review_status || {};

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleAllVisible = () => {
    const visibleIds = pagedItems.map((i) => i.exception_id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    setSelectedIds(allSelected ? [] : visibleIds);
  };

  const handleBulkReview = async () => {
    if (selectedIds.length === 0) return;
    setBulkBusy(true);
    try {
      const res = await api.bulkReviewQuarantine({
        exception_ids: selectedIds,
        review_status: bulkStatus,
        note: bulkNote.trim() || `Marked ${bulkStatus} in batch review`,
        action_taken: `BULK_${bulkStatus}`,
      });
      setStatusBanner(`Updated ${res.updated_count} quarantine exception(s) to ${bulkStatus}.`);
      setSelectedIds([]);
      setBulkNote("");
      await Promise.all([fetchFiltered(), onRefresh()]);
    } catch (err) {
      setStatusBanner(err instanceof Error ? err.message : "Bulk quarantine review failed");
    } finally {
      setBulkBusy(false);
    }
  };

  const openDetail = async (exceptionId: string) => {
    try {
      const res = await api.quarantineDetail(exceptionId);
      setDetail(res);
      setSingleStatus((res.exception.review_status as typeof singleStatus) || "REMEDIATED");
      setSingleNote(res.exception.remediation_note || "");
      setSingleAction(res.exception.action_taken || "");
    } catch (err) {
      setStatusBanner(err instanceof Error ? err.message : "Failed to load exception detail");
    }
  };

  const handleSingleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    setSavingSingle(true);
    try {
      const res = await api.reviewQuarantine(detail.exception.exception_id, {
        review_status: singleStatus,
        note: singleNote.trim() || `Marked ${singleStatus}`,
        action_taken: singleAction.trim() || `REVIEW_${singleStatus}`,
      });
      setDetail(res);
      setStatusBanner(`Saved review for ${detail.exception.exception_id} (${singleStatus}).`);
      await Promise.all([fetchFiltered(), onRefresh()]);
    } catch (err) {
      setStatusBanner(err instanceof Error ? err.message : "Failed to update quarantine review");
    } finally {
      setSavingSingle(false);
    }
  };

  const handleRunValidator = async () => {
    setRunningChecks(true);
    try {
      const rep = await api.validateIntegrity();
      setIntegrityReport(rep);
    } catch (err) {
      setStatusBanner(err instanceof Error ? err.message : "Live validation failed");
    } finally {
      setRunningChecks(false);
    }
  };

  const exportParams = {
    search: search || undefined,
    issue_type: issueType,
    severity,
    review_status: reviewStatus,
    sort_by: sortBy,
  };

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        <LiquidGlassCard variant="hero" className="rounded-2xl p-4 text-white">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-white/85">
            Total Quarantined
          </div>
          <div className="mt-1.5 text-2xl font-bold ios-num text-white">{active.total_exceptions}</div>
          <div className="mt-1 text-[11.5px] text-white/85">
            Pending review: {reviewCounts.PENDING ?? active.total_exceptions}
          </div>
        </LiquidGlassCard>

        <LiquidGlassCard variant="rose" className="rounded-2xl p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-800 dark:text-zinc-300">
            Quarantined Exposure
          </div>
          <div className="mt-1.5 text-2xl font-bold ios-num text-rose-700 dark:text-rose-400">
            ${Number(active.quarantined_exposure || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="mt-1 text-[11.5px] text-rose-700/80 dark:text-zinc-400">
            Pending: ${Number(active.pending_exposure || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </LiquidGlassCard>

        <LiquidGlassCard variant="emerald" className="rounded-2xl p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-800 dark:text-zinc-300">
            Remediated / Ack
          </div>
          <div className="mt-1.5 text-2xl font-bold ios-num text-emerald-700 dark:text-emerald-400">
            {(reviewCounts.REMEDIATED ?? 0) + (reviewCounts.ACKNOWLEDGED ?? 0)}
          </div>
          <div className="mt-1 text-[11.5px] text-emerald-700/80 dark:text-zinc-400">
            Waived: {reviewCounts.WAIVED ?? 0}
          </div>
        </LiquidGlassCard>

        {issueTypes.slice(0, 2).map((issue) => (
          <LiquidGlassCard key={issue} variant="glass" className="rounded-2xl p-4">
            <div className="text-[10.5px] font-mono font-semibold text-slate-700 dark:text-zinc-300 truncate" title={issue}>
              {issue}
            </div>
            <div className="mt-1.5 text-2xl font-bold ios-num text-slate-950 dark:text-white">
              {active.counts_by_issue_type[issue]}
            </div>
            <div className="mt-1 text-[11.5px] text-slate-600 dark:text-zinc-400">Isolated by validator</div>
          </LiquidGlassCard>
        ))}
      </div>

      {/* Filter & Actions Toolbar */}
      <div className="liquid-glass rounded-2xl p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 dark:text-zinc-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Exception, Entity, Account, Evidence..."
                className="pl-8 pr-3 py-1.5 glass-pill rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400 w-64 focus:outline-none"
              />
            </div>

            <select
              value={issueType}
              onChange={(e) => setIssueType(e.target.value)}
              className="px-3 py-1.5 glass-pill rounded-full text-xs text-slate-900 dark:text-white"
            >
              <option value="ALL">All Issue Types</option>
              {issueTypes.map((it) => (
                <option key={it} value={it}>{it}</option>
              ))}
            </select>

            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="px-3 py-1.5 glass-pill rounded-full text-xs text-slate-900 dark:text-white"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>

            <select
              value={reviewStatus}
              onChange={(e) => setReviewStatus(e.target.value)}
              className="px-3 py-1.5 glass-pill rounded-full text-xs text-slate-900 dark:text-white"
            >
              {REVIEW_STATUSES.map((st) => (
                <option key={st} value={st}>{st === "ALL" ? "All Review States" : st}</option>
              ))}
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-3 py-1.5 glass-pill rounded-full text-xs text-slate-900 dark:text-white"
            >
              <option value="severity">Sort: Severity</option>
              <option value="exposure">Sort: Exposure $</option>
              <option value="status">Sort: Review Status</option>
            </select>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleRunValidator}
              disabled={runningChecks}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-azure-600/90 border border-white/50 dark:border-transparent text-white hover:bg-azure-500 transition shadow-sm disabled:opacity-60"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${runningChecks ? "animate-spin" : ""}`} />
              Run Invariant Scan
            </button>
            <button
              type="button"
              onClick={() => downloadExport(api.quarantineExportUrl("csv", exportParams), "yottaflex_quarantine.csv")}
              className="glass-pill inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              <Download className="w-3.5 h-3.5" /> CSV
            </button>
            <button
              type="button"
              onClick={() => downloadExport(api.quarantineExportUrl("json", exportParams), "yottaflex_quarantine.json")}
              className="glass-pill inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              <Download className="w-3.5 h-3.5" /> JSON
            </button>
          </div>
        </div>

        {/* Bulk Action Bar */}
        {selectedIds.length > 0 && (
          <div className="flex flex-wrap items-center gap-2.5 pt-2.5 border-t border-white/50 dark:border-white/10">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold text-azure-700 dark:text-sky-300">
              <CheckSquare className="w-4 h-4" /> {selectedIds.length} selected
            </span>
            <select
              value={bulkStatus}
              onChange={(e) => setBulkStatus(e.target.value as typeof bulkStatus)}
              className="px-2.5 py-1 glass-pill rounded-full text-xs text-slate-900 dark:text-white"
            >
              <option value="ACKNOWLEDGED">Mark ACKNOWLEDGED</option>
              <option value="REMEDIATED">Mark REMEDIATED</option>
              <option value="WAIVED">Mark WAIVED</option>
            </select>
            <input
              type="text"
              value={bulkNote}
              onChange={(e) => setBulkNote(e.target.value)}
              placeholder="Optional batch remediation note..."
              className="px-3 py-1 glass-pill rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400 w-64"
            />
            <button
              type="button"
              onClick={handleBulkReview}
              disabled={bulkBusy}
              className="px-3.5 py-1.5 rounded-full text-xs font-semibold bg-emerald-600/90 border border-white/50 dark:border-transparent text-white hover:bg-emerald-500 transition disabled:opacity-60"
            >
              {bulkBusy ? "Applying..." : "Apply Batch Review"}
            </button>
            <button
              type="button"
              onClick={() => setSelectedIds([])}
              className="text-xs font-semibold text-slate-600 dark:text-zinc-400 underline"
            >
              Clear
            </button>
          </div>
        )}

        {statusBanner && (
          <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-azure-500/12 border border-azure-400/35 text-xs font-semibold text-azure-800 dark:text-sky-200">
            <span>{statusBanner}</span>
            <button type="button" onClick={() => setStatusBanner(null)} className="underline ml-3">
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Live Integrity Scan Result Cards */}
      {integrityReport && (
        <div className="liquid-glass rounded-2xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <span className="text-xs font-bold text-slate-950 dark:text-white">
                Live SQLite Ledger Invariant Diagnostics ({integrityReport.passed_checks}/{integrityReport.total_checks} Passed)
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIntegrityReport(null)}
              className="text-xs text-slate-600 dark:text-zinc-400 hover:underline"
            >
              Hide
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
            {integrityReport.checks.map((chk) => (
              <div
                key={chk.check_id}
                className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-bold text-slate-900 dark:text-white">{chk.check_id}</span>
                  <Badge variant={chk.status === "PASS" ? "LOW" : "HIGH"}>
                    {chk.status === "PASS" ? "PASS (0)" : `${chk.violations_found} ISOLATED`}
                  </Badge>
                </div>
                <div className="mt-1 font-semibold text-slate-800 dark:text-zinc-200">{chk.name}</div>
                <div className="mt-0.5 text-[11px] text-slate-600 dark:text-zinc-400">{chk.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quarantine Exception Table + Optional 360 Detail Panel */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        <div className={`${detail ? "xl:col-span-8" : "xl:col-span-12"} liquid-glass rounded-2xl overflow-hidden`}>
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Data Integrity &amp; Process Exception Quarantine
              </h3>
              <p className="text-xs text-slate-600 dark:text-zinc-400">
                Showing {items.length} of {active.total_exceptions} isolated records {loadingList ? "• Refreshing..." : ""}
              </p>
            </div>
          </div>

          <div ref={rowMag.containerRef} onMouseLeave={rowMag.onContainerLeave} className="relative overflow-x-auto">
            {rowMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-3 px-3">
                    <input
                      type="checkbox"
                      checked={pagedItems.length > 0 && pagedItems.every((i) => selectedIds.includes(i.exception_id))}
                      onChange={toggleAllVisible}
                    />
                  </th>
                  <th className="py-3 px-3">Exception</th>
                  <th className="py-3 px-3">Issue / Severity</th>
                  <th className="py-3 px-3">Review Status</th>
                  <th className="py-3 px-3">Entity &amp; Account</th>
                  <th className="py-3 px-3">Evidence &amp; Invariant</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {pagedItems.map((ex) => (
                  <tr
                    key={ex.exception_id}
                    onMouseEnter={(e) => rowMag.onRowEnter(e.currentTarget)}
                    className="liquid-row-magnify"
                  >
                    <td className="py-3 px-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(ex.exception_id)}
                        onChange={() => toggleSelect(ex.exception_id)}
                      />
                    </td>
                    <td className="py-3 px-3 font-mono">
                      <div className="font-semibold text-slate-950 dark:text-white">{ex.exception_id}</div>
                      {Number(ex.estimated_exposure || 0) > 0 && (
                        <div className="text-[11px] text-rose-600 dark:text-rose-400 ios-num">
                          ${Number(ex.estimated_exposure).toLocaleString()}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3 space-y-1">
                      <div>
                        <Badge variant="CRITICAL">{ex.issue_type}</Badge>
                      </div>
                      <div>
                        <Badge variant={tierVariant(ex.severity)}>{ex.severity}</Badge>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <Badge
                        variant={
                          ex.review_status === "REMEDIATED"
                            ? "LOW"
                            : ex.review_status === "ACKNOWLEDGED"
                            ? "BLUE"
                            : ex.review_status === "WAIVED"
                            ? "NEUTRAL"
                            : "HIGH"
                        }
                      >
                        {ex.review_status || "PENDING"}
                      </Badge>
                      {ex.reviewer_id && (
                        <div className="mt-1 font-mono text-[10.5px] text-slate-500 dark:text-zinc-400">
                          by {ex.reviewer_id}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3 font-mono">
                      {ex.entity_id.startsWith("TXN-") && onOpenTransaction ? (
                        <button
                          type="button"
                          onClick={() => onOpenTransaction(ex.entity_id)}
                          className="font-semibold text-azure-700 dark:text-sky-300 hover:underline block text-left"
                        >
                          {ex.entity_id}
                        </button>
                      ) : (
                        <div className="font-semibold text-slate-950 dark:text-white">{ex.entity_id}</div>
                      )}
                      {ex.account_id && ex.account_id.startsWith("ACC-") && onOpenAccount ? (
                        <button
                          type="button"
                          onClick={() => onOpenAccount(ex.account_id)}
                          className="text-[11px] text-slate-600 dark:text-zinc-400 hover:underline"
                        >
                          {ex.account_id}
                        </button>
                      ) : (
                        <div className="text-[11px] text-slate-500 dark:text-zinc-500">{ex.account_id}</div>
                      )}
                    </td>
                    <td className="py-3 px-3 max-w-xs">
                      <div className="text-slate-800 dark:text-zinc-200 font-medium">{ex.violated_invariant}</div>
                      <div className="font-mono text-[11px] text-slate-600 dark:text-zinc-400 mt-0.5">{ex.evidence}</div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => openDetail(ex.exception_id)}
                        className="px-2.5 py-1 rounded-lg bg-white/75 dark:bg-zinc-900 border border-white/80 dark:border-white/15 text-xs font-semibold text-azure-700 dark:text-sky-300 hover:bg-white dark:hover:bg-zinc-800 transition"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-500 dark:text-zinc-400">
                      No quarantine exceptions match the active filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <GlassPagination
            total={items.length}
            page={page}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={(sz) => {
              setPageSize(sz);
              setPage(0);
            }}
            unitLabel="exceptions"
          />
        </div>

        {/* Quarantine Exception 360 Remediation Drawer */}
        {detail && (
          <div className="xl:col-span-4 liquid-glass rounded-2xl p-5 space-y-4 self-start">
            <div className="flex items-start justify-between gap-2 border-b border-white/50 dark:border-white/10 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-rose-600 dark:text-rose-400" />
                  <h4 className="text-sm font-bold font-mono text-slate-950 dark:text-white">
                    {detail.exception.exception_id}
                  </h4>
                </div>
                <p className="text-xs text-slate-600 dark:text-zinc-400 mt-1">{detail.exception.remediation}</p>
              </div>
              <button
                type="button"
                onClick={() => setDetail(null)}
                className="p-1.5 rounded-full bg-white/60 dark:bg-zinc-900 border border-white/80 dark:border-white/15 text-slate-700 dark:text-zinc-300"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <form onSubmit={handleSingleSave} className="space-y-3 text-xs">
              <label className="block space-y-1">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Review Disposition</span>
                <select
                  value={singleStatus}
                  onChange={(e) => setSingleStatus(e.target.value as typeof singleStatus)}
                  className="w-full px-3 py-2 glass-pill rounded-full text-slate-900 dark:text-white"
                >
                  <option value="PENDING">PENDING</option>
                  <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                  <option value="REMEDIATED">REMEDIATED</option>
                  <option value="WAIVED">WAIVED</option>
                </select>
              </label>

              <label className="block space-y-1">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Remediation Action Code</span>
                <input
                  type="text"
                  value={singleAction}
                  onChange={(e) => setSingleAction(e.target.value)}
                  placeholder="e.g. REJECTED_POST_CLOSE_SETTLEMENT"
                  className="w-full px-3 py-2 glass-pill rounded-full text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400"
                />
              </label>

              <label className="block space-y-1">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Audit Note</span>
                <textarea
                  rows={3}
                  value={singleNote}
                  onChange={(e) => setSingleNote(e.target.value)}
                  placeholder="Document remediation verification & ledger isolation proof..."
                  className="w-full px-3 py-2 glass-pill rounded-2xl text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400 focus:outline-none"
                />
              </label>

              <button
                type="submit"
                disabled={savingSingle}
                className="w-full py-2 rounded-full bg-azure-600/90 border border-white/50 dark:border-transparent hover:bg-azure-500 text-white font-semibold transition disabled:opacity-60"
              >
                {savingSingle ? "Saving Review..." : "Save Quarantine Review"}
              </button>
            </form>

            <div className="pt-3 border-t border-white/50 dark:border-white/10 space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-zinc-400">
                Remediation Audit Timeline ({detail.events.length})
              </div>
              <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                {detail.events.map((ev) => (
                  <div
                    key={ev.event_id}
                    className="rounded-xl p-2.5 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12 text-[11px]"
                  >
                    <div className="flex justify-between font-mono text-slate-700 dark:text-zinc-300">
                      <span className="font-bold">{ev.new_status}</span>
                      <span>{ev.actor_id}</span>
                    </div>
                    <div className="text-slate-800 dark:text-zinc-200 mt-0.5">{ev.note}</div>
                    <div className="text-[10px] font-mono text-slate-500 dark:text-zinc-500 mt-0.5">{ev.created_at}</div>
                  </div>
                ))}
                {detail.events.length === 0 && (
                  <div className="text-xs text-slate-500 dark:text-zinc-400">No review actions recorded yet.</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
