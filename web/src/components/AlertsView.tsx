import React, { useEffect, useState } from "react";
import {
  Activity,
  ArrowDownUp,
  ArrowLeft,
  Bell,
  CheckSquare,
  Clock,
  Download,
  ExternalLink,
  Search,
  ShieldAlert,
  UserCheck,
} from "lucide-react";
import { api, downloadExport } from "../api/client";
import type { AlertDetail, AlertListItem, RiskRuleItem } from "../types/workbench";
import { Badge, IosAmount, statusVariant, tierVariant } from "./Badge";
import { LiquidGlassCard, useRowGlassMagnifier } from "./LiquidGlassSurface";
import { GlassPagination } from "./GlassPagination";
import { SavedPresetsBar } from "./SavedPresetsBar";

export interface AlertFiltersState {
  search: string;
  severity: string;
  rule_id: string;
  status: string;
  owner_analyst: string;
  sla_breached: string;
  start_date: string;
  end_date: string;
  sort_by: "risk_score" | "priority" | "created_at";
  sort_dir: "desc" | "asc";
}

interface AlertsViewProps {
  alerts: AlertListItem[];
  total: number;
  page: number;
  pageSize: number;
  rules: RiskRuleItem[];
  filters: AlertFiltersState;
  selectedDetail: AlertDetail | null;
  onFiltersChange: (next: AlertFiltersState) => void;
  onPageChange: (nextPage: number) => void;
  onPageSizeChange: (nextSize: number) => void;
  onSelectAlert: (alertId: string) => void;
  onCloseDetail: () => void;
  onOpenTransaction: (transactionId: string) => void;
  onOpenAccount: (accountId: string) => void;
  onOpenCustomer: (customerId: string) => void;
  onOpenCase: (caseId: string) => void;
  onAlertsUpdated: () => Promise<void>;
}

export const AlertsView: React.FC<AlertsViewProps> = ({
  alerts,
  total,
  page,
  pageSize,
  rules,
  filters,
  selectedDetail,
  onFiltersChange,
  onPageChange,
  onPageSizeChange,
  onSelectAlert,
  onCloseDetail,
  onOpenTransaction,
  onOpenAccount,
  onOpenCustomer,
  onOpenCase,
  onAlertsUpdated,
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkAction, setBulkAction] = useState("ACKNOWLEDGE");
  const [bulkOwner, setBulkOwner] = useState("ANL-001");
  const [bulkRationale, setBulkRationale] = useState("");
  const [busyMsg, setBusyMsg] = useState<string | null>(null);

  // Detail Triage controls (Functions 101-106, 108)
  const [ownerInput, setOwnerInput] = useState("ANL-001");
  const [statusInput, setStatusInput] = useState("ACKNOWLEDGED");
  const [suppressionInput, setSuppressionInput] = useState("");
  const [noteInput, setNoteInput] = useState("");
  const [escalateCaseInput, setEscalateCaseInput] = useState("");
  const [detailMsg, setDetailMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [savingDetail, setSavingDetail] = useState(false);

  useEffect(() => {
    if (!selectedDetail) return;
    setOwnerInput(selectedDetail.triage_meta?.owner_analyst_id || "ANL-001");
    setSuppressionInput(selectedDetail.triage_meta?.suppression_reason || "");
    setNoteInput("");
    setEscalateCaseInput("");
    setDetailMsg(null);
  }, [selectedDetail?.alert.alert_id, selectedDetail?.triage_meta?.updated_at]);

  const toggleSelectAlert = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleBulkSubmit = async () => {
    if (selectedIds.length === 0) return;
    setBusyMsg("Applying bulk alert triage...");
    try {
      const res = await api.bulkTriageAlerts({
        alert_ids: selectedIds,
        action: bulkAction,
        owner_analyst_id: bulkAction === "ASSIGN" ? bulkOwner : undefined,
        rationale: bulkRationale,
      });
      setSelectedIds([]);
      setBulkRationale("");
      setBusyMsg(`Updated ${res.updated_count} alert(s)${res.skipped.length ? ` (${res.skipped.length} skipped)` : ""}.`);
      await onAlertsUpdated();
    } catch (err) {
      setBusyMsg(err instanceof Error ? err.message : "Bulk triage failed");
    }
  };
  const rowMag = useRowGlassMagnifier();
  const txnMag = useRowGlassMagnifier();
  const sibMag = useRowGlassMagnifier();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const toggleSort = (col: AlertFiltersState["sort_by"]) => {
    if (filters.sort_by === col) {
      onFiltersChange({ ...filters, sort_dir: filters.sort_dir === "desc" ? "asc" : "desc" });
    } else {
      onFiltersChange({ ...filters, sort_by: col, sort_dir: "desc" });
    }
  };

  // =========================================================================
  // ALERT 360 DETAIL VIEW (Functions 76, 77, 90, 95-100)
  // =========================================================================
  if (selectedDetail) {
    const al = selectedDetail.alert;
    const rule = selectedDetail.rule;
    const cust = selectedDetail.customer;
    const acct = selectedDetail.account;
    const pTxn = selectedDetail.primary_transaction;

    return (
      <div className="space-y-5">
        {/* Alert Banner (Fn 95, 98) */}
        <div className="liquid-glass rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="font-mono text-lg font-bold text-slate-950 dark:text-white">{al.alert_id}</h2>
              <Badge variant={tierVariant(al.severity)}>{al.severity} SEVERITY</Badge>
              <Badge variant={al.risk_score >= 60 ? "CRITICAL" : "HIGH"}>
                RISK SCORE: {al.risk_score.toFixed(1)}
              </Badge>
              <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{al.rule_id}</span>
              <Badge variant="NEUTRAL">{al.status}</Badge>
              {al.sla_breached && <Badge variant="CRITICAL">SLA BREACHED ({al.age_hours ?? 0}h)</Badge>}
              {selectedDetail.triage_meta?.owner_analyst_id && (
                <Badge variant="BLUE">Owner: {selectedDetail.triage_meta.owner_analyst_id}</Badge>
              )}
              {(selectedDetail.watchlist_tags || []).map((t) => (
                <Badge key={t.tag_id} variant="HIGH">{t.tag}</Badge>
              ))}
            </div>
            <div className="mt-1.5 text-xs text-slate-700 dark:text-zinc-300">{al.explanation_summary}</div>
            <div className="mt-1 text-[11px] font-mono text-slate-500 dark:text-zinc-400">
              Generated: {al.created_at} • Account: {al.account_id} • Customer: {cust.full_name} ({al.customer_id})
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {selectedDetail.linked_cases.map((ca) => (
              <button
                key={ca.case_id}
                type="button"
                onClick={() => onOpenCase(ca.case_id)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-azure-600/90 text-white text-xs font-semibold shadow-sm hover:opacity-95"
              >
                <ExternalLink className="w-3 h-3" /> {ca.case_id} ({ca.priority_tier})
              </button>
            ))}
            <button
              type="button"
              onClick={() => onOpenAccount(acct.account_id)}
              className="px-3 py-1.5 glass-pill rounded-full text-xs font-semibold text-azure-700 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              Account 360°
            </button>
            <button
              type="button"
              onClick={() => onOpenCustomer(cust.customer_id)}
              className="px-3 py-1.5 glass-pill rounded-full text-xs font-semibold text-azure-700 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              Customer 360°
            </button>
            <button
              type="button"
              onClick={onCloseDetail}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/60 dark:bg-zinc-900 border border-white/85 dark:border-white/15 text-xs font-semibold"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> All Alerts
            </button>
          </div>
        </div>

        {/* Row 1: Risk Score Breakdown (Fn 76, 98), Responsible Rule (Fn 97), Triggering Transaction (Fn 96) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <LiquidGlassCard variant="hero" className="lg:col-span-4 rounded-2xl p-5 text-white">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-white/85">
              Individual Rule Risk Contributions (Fn 76)
            </div>
            <div className="mt-1.5 text-3xl font-bold ios-num text-white">{al.risk_score.toFixed(1)} / 100</div>
            <div className="mt-3 pt-3 border-t border-white/25 space-y-2 text-xs">
              {selectedDetail.risk_contributions.map((rc) => (
                <div key={rc.component} className="flex items-center justify-between gap-2">
                  <span className="text-white/90">{rc.component}</span>
                  <span className="font-mono font-bold">+{rc.points.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard className="lg:col-span-4 rounded-2xl p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white mb-2">
              <ShieldAlert className="w-4 h-4 text-azure-600 dark:text-azure-400" />
              Responsible Risk Rule (Fn 97)
            </div>
            {rule ? (
              <dl className="grid grid-cols-2 gap-y-2 text-xs">
                <dt className="text-slate-500 dark:text-zinc-400">Rule ID / Version</dt>
                <dd className="font-mono font-semibold text-slate-950 dark:text-white">
                  {rule.rule_id} ({rule.version})
                </dd>
                <dt className="text-slate-500 dark:text-zinc-400">Rule Name</dt>
                <dd className="font-semibold text-slate-900 dark:text-zinc-100">{rule.rule_name}</dd>
                <dt className="text-slate-500 dark:text-zinc-400">Category / Weight</dt>
                <dd className="ios-num">
                  {rule.category} • {rule.base_weight} pts
                </dd>
                <dt className="text-slate-500 dark:text-zinc-400">Condition</dt>
                <dd className="text-slate-700 dark:text-zinc-300">{rule.threshold_desc}</dd>
              </dl>
            ) : (
              <div className="text-xs text-slate-500">Rule metadata unavailable.</div>
            )}
          </LiquidGlassCard>

          <LiquidGlassCard variant="amber" className="lg:col-span-4 rounded-2xl p-5">
            <div className="text-sm font-semibold text-slate-950 dark:text-white mb-2">
              Primary Triggering Transaction / Event (Fn 96)
            </div>
            {pTxn ? (
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => onOpenTransaction(pTxn.transaction_id)}
                    className="font-mono font-bold text-azure-700 dark:text-white hover:underline"
                  >
                    {pTxn.transaction_id} →
                  </button>
                  <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{pTxn.txn_type}</span>
                </div>
                <div className="text-lg font-bold">
                  <IosAmount value={pTxn.amount} />
                </div>
                <div className="text-[11px] font-mono text-slate-600 dark:text-zinc-400">
                  {pTxn.occurred_at} • {pTxn.channel} • {pTxn.counterparty_country}
                </div>
                <div className="text-[11px] text-slate-700 dark:text-zinc-300">{pTxn.reference_note}</div>
              </div>
            ) : (
              <div className="rounded-xl p-3 bg-rose-500/15 border border-rose-500/30 text-xs text-rose-700 dark:text-rose-300">
                Orphan Alert: No valid primary triggering transaction reference attached.
              </div>
            )}
          </LiquidGlassCard>
        </div>

        {/* Exact Quantitative Trigger Conditions (Fn 77, 99) */}
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Exact Triggering Conditions &amp; Quantitative Evidence ({selectedDetail.trigger_facts.length})
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/40 text-[11px] font-semibold uppercase text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Fact ID</th>
                  <th className="py-2.5 px-3">Transaction</th>
                  <th className="py-2.5 px-3">Condition / Metric</th>
                  <th className="py-2.5 px-3">Observed Value</th>
                  <th className="py-2.5 px-3">Configured Threshold</th>
                  <th className="py-2.5 px-4 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {selectedDetail.trigger_facts.map((f) => (
                  <tr
                    key={f.fact_id}
                    onClick={() => f.transaction_id && onOpenTransaction(f.transaction_id)}
                    className="hover:bg-white/30 dark:hover:bg-white/[0.04] cursor-pointer"
                  >
                    <td className="py-2.5 px-4 font-mono text-slate-700 dark:text-zinc-300">{f.fact_id}</td>
                    <td className="py-2.5 px-3 font-mono font-semibold text-azure-700 dark:text-white">
                      {f.transaction_id}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-slate-900 dark:text-zinc-200">{f.metric_name}</td>
                    <td className="py-2.5 px-3 font-mono font-bold text-rose-700 dark:text-rose-300">{f.observed_value}</td>
                    <td className="py-2.5 px-3 font-mono text-slate-600 dark:text-zinc-400">{f.threshold_value}</td>
                    <td className="py-2.5 px-4 text-right">
                      {f.amount !== undefined ? <IosAmount value={f.amount} /> : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Supporting Related Transactions (Fn 99) & Other Alerts on Same Customer/Account (Fn 100) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Supporting Context Transactions (±48h Window: {selectedDetail.supporting_transactions.length})
              </h3>
            </div>
            <div ref={txnMag.containerRef} onMouseLeave={txnMag.onContainerLeave} className="relative overflow-x-auto max-h-80">
              {txnMag.lensElement}
              <table className="w-full text-left border-collapse text-xs">
                <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                  {selectedDetail.supporting_transactions.map((stx) => (
                    <tr
                      key={stx.transaction_id}
                      onMouseEnter={(e) => txnMag.onRowEnter(e.currentTarget)}
                      onClick={() => onOpenTransaction(stx.transaction_id)}
                      className="liquid-row-magnify cursor-pointer"
                    >
                      <td className="py-2 px-4 font-mono font-semibold text-azure-700 dark:text-white">
                        {stx.transaction_id}
                      </td>
                      <td className="py-2 px-3 ios-num text-slate-600 dark:text-zinc-400">{stx.occurred_at}</td>
                      <td className="py-2 px-3">
                        <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{stx.txn_type}</span>
                      </td>
                      <td className="py-2 px-4 text-right font-semibold">
                        <IosAmount
                          value={stx.direction === "CREDIT" ? stx.amount : -stx.amount}
                          showPlus={stx.direction === "CREDIT"}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Other Alerts — Same Customer / Account ({selectedDetail.sibling_alerts.length})
              </h3>
            </div>
            <div ref={sibMag.containerRef} onMouseLeave={sibMag.onContainerLeave} className="relative overflow-x-auto max-h-80">
              {sibMag.lensElement}
              <table className="w-full text-left border-collapse text-xs">
                <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                  {selectedDetail.sibling_alerts.length === 0 ? (
                    <tr>
                      <td className="py-6 px-4 text-center text-slate-500 dark:text-zinc-400">
                        No other alerts recorded for this customer or account.
                      </td>
                    </tr>
                  ) : (
                    selectedDetail.sibling_alerts.map((sa) => (
                      <tr
                        key={sa.alert_id}
                        onMouseEnter={(e) => sibMag.onRowEnter(e.currentTarget)}
                        onClick={() => onSelectAlert(sa.alert_id)}
                        className="liquid-row-magnify cursor-pointer"
                      >
                        <td className="py-2.5 px-4 font-mono font-semibold text-azure-700 dark:text-white">
                          {sa.alert_id}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{sa.rule_id}</span>
                          <div className="text-[11px] text-slate-600 dark:text-zinc-400 mt-0.5">{sa.rule_name}</div>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px]">{sa.account_id}</td>
                        <td className="py-2.5 px-4 text-right">
                          <Badge variant={tierVariant(sa.severity)}>
                            {sa.severity} ({sa.risk_score.toFixed(1)})
                          </Badge>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Functions 101-106, 108: Interactive Alert Triage, Escalation & Audit Timeline */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-7 liquid-glass rounded-2xl p-5 space-y-3.5 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white">
                <UserCheck className="w-4 h-4 text-azure-600 dark:text-sky-400" />
                <span>Alert Triage, Disposition &amp; Case Escalation (Fn 101–106)</span>
              </div>
              {selectedDetail.triage_meta?.disposition && (
                <Badge variant={selectedDetail.triage_meta.disposition === "TRUE_POSITIVE" ? "CRITICAL" : "LOW"}>
                  {selectedDetail.triage_meta.disposition}
                </Badge>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <div className="flex items-center gap-1.5">
                <select
                  value={ownerInput}
                  onChange={(e) => setOwnerInput(e.target.value)}
                  className="flex-1 glass-pill rounded-full px-2.5 py-1.5 text-xs"
                >
                  <option value="ANL-001">ANL-001 (Ops Analyst)</option>
                  <option value="ANL-002">ANL-002 (Ops Analyst)</option>
                  <option value="ANL-003">ANL-003 (Risk Reviewer)</option>
                  <option value="ADM-001">ADM-001 (System Admin)</option>
                </select>
                <button
                  type="button"
                  disabled={savingDetail}
                  onClick={async () => {
                    setSavingDetail(true);
                    setDetailMsg(null);
                    try {
                      await api.triageAlert(al.alert_id, { owner_analyst_id: ownerInput });
                      setDetailMsg({ ok: true, text: `Assigned to ${ownerInput}.` });
                      await onAlertsUpdated();
                      onSelectAlert(al.alert_id);
                    } catch (err) {
                      setDetailMsg({ ok: false, text: err instanceof Error ? err.message : "Assign failed" });
                    } finally {
                      setSavingDetail(false);
                    }
                  }}
                  className="px-3 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black font-semibold"
                >
                  Assign
                </button>
              </div>

              <div className="flex items-center gap-1.5">
                <select
                  value={statusInput}
                  onChange={(e) => setStatusInput(e.target.value)}
                  className="flex-1 glass-pill rounded-full px-2.5 py-1.5 text-xs"
                >
                  <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                  <option value="UNDER_INVESTIGATION">UNDER_INVESTIGATION</option>
                  <option value="ESCALATED">ESCALATED (True Positive)</option>
                  <option value="FALSE_POSITIVE">FALSE_POSITIVE (Suppress)</option>
                  <option value="DISMISSED">DISMISSED</option>
                </select>
                <button
                  type="button"
                  disabled={savingDetail}
                  onClick={async () => {
                    setSavingDetail(true);
                    setDetailMsg(null);
                    try {
                      await api.triageAlert(al.alert_id, {
                        status: statusInput,
                        disposition:
                          statusInput === "FALSE_POSITIVE" || statusInput === "DISMISSED"
                            ? "FALSE_POSITIVE"
                            : statusInput === "ESCALATED"
                            ? "TRUE_POSITIVE"
                            : undefined,
                        suppression_reason: suppressionInput || undefined,
                      });
                      setDetailMsg({ ok: true, text: `Updated status to ${statusInput}.` });
                      await onAlertsUpdated();
                      onSelectAlert(al.alert_id);
                    } catch (err) {
                      setDetailMsg({ ok: false, text: err instanceof Error ? err.message : "Status update failed" });
                    } finally {
                      setSavingDetail(false);
                    }
                  }}
                  className="px-3 py-1.5 rounded-full bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/20 font-semibold text-azure-700 dark:text-white"
                >
                  Apply
                </button>
              </div>

              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={escalateCaseInput}
                  onChange={(e) => setEscalateCaseInput(e.target.value)}
                  placeholder="Optional CASE-2026-..."
                  className="flex-1 glass-pill rounded-full px-2.5 py-1.5 text-xs font-mono"
                />
                <button
                  type="button"
                  disabled={savingDetail}
                  onClick={async () => {
                    setSavingDetail(true);
                    setDetailMsg(null);
                    try {
                      const res = await api.escalateAlert(al.alert_id, {
                        target_case_id: escalateCaseInput || undefined,
                        rationale: noteInput || "Escalated from Alert 360°",
                      });
                      setDetailMsg({
                        ok: true,
                        text: `${res.created_new_case ? "Created" : "Linked to"} ${res.case_id}.`,
                      });
                      await onAlertsUpdated();
                      onSelectAlert(al.alert_id);
                    } catch (err) {
                      setDetailMsg({ ok: false, text: err instanceof Error ? err.message : "Escalation failed" });
                    } finally {
                      setSavingDetail(false);
                    }
                  }}
                  className="px-3 py-1.5 rounded-full bg-rose-600/90 text-white font-semibold shrink-0"
                >
                  Escalate → Case
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <input
                type="text"
                value={suppressionInput}
                onChange={(e) => setSuppressionInput(e.target.value)}
                placeholder="FP suppression tag (e.g. VERIFIED_PAYROLL_BONUS)"
                className="glass-pill rounded-full px-3 py-1.5 text-xs"
              />
              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="Add timestamped investigation note..."
                  className="flex-1 glass-pill rounded-full px-3 py-1.5 text-xs"
                />
                <button
                  type="button"
                  disabled={savingDetail || !noteInput.trim()}
                  onClick={async () => {
                    setSavingDetail(true);
                    setDetailMsg(null);
                    try {
                      await api.triageAlert(al.alert_id, { note: noteInput });
                      setNoteInput("");
                      setDetailMsg({ ok: true, text: "Investigation note logged." });
                      onSelectAlert(al.alert_id);
                    } catch (err) {
                      setDetailMsg({ ok: false, text: err instanceof Error ? err.message : "Note failed" });
                    } finally {
                      setSavingDetail(false);
                    }
                  }}
                  className="px-3 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black font-semibold disabled:opacity-40"
                >
                  Log Note
                </button>
              </div>
            </div>

            {detailMsg && (
              <div className={detailMsg.ok ? "text-emerald-700 dark:text-emerald-400 font-semibold" : "text-rose-700 dark:text-rose-400 font-semibold"}>
                {detailMsg.text}
              </div>
            )}
          </div>

          {/* Function 108: Alert Audit Timeline */}
          <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-2.5 text-xs">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white">
              <Clock className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              <span>Alert Audit Timeline ({(selectedDetail.audit_events || []).length})</span>
            </div>
            <div className="max-h-40 overflow-y-auto space-y-2">
              {(selectedDetail.audit_events || []).length === 0 ? (
                <div className="text-slate-500 dark:text-zinc-400 py-3">
                  No analyst triage events recorded yet on this alert.
                </div>
              ) : (
                (selectedDetail.audit_events || []).map((ev) => (
                  <div
                    key={ev.event_id}
                    className="rounded-xl p-2.5 bg-white/40 dark:bg-black/40 border border-white/60 dark:border-white/10"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono font-semibold text-slate-900 dark:text-white">{ev.event_type}</span>
                      <span className="ios-num text-[10.5px] text-slate-500 dark:text-zinc-400">
                        {ev.actor_id} • {ev.created_at}
                      </span>
                    </div>
                    <div className="text-slate-700 dark:text-zinc-300 mt-0.5">{ev.detail}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Function 90: Score History for This Alert */}
        {selectedDetail.score_history.length > 0 && (
          <div className="liquid-glass rounded-2xl p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white mb-3">
              <Activity className="w-4 h-4 text-azure-600 dark:text-azure-400" />
              Alert Risk Score Change History
            </div>
            <div className="space-y-2 text-xs">
              {selectedDetail.score_history.map((h) => (
                <div
                  key={h.history_id}
                  className="rounded-xl p-3 bg-white/40 dark:bg-black/40 border border-white/60 dark:border-white/10 flex flex-wrap items-center justify-between gap-2"
                >
                  <div>
                    <span className="font-mono font-bold text-slate-950 dark:text-white">
                      {h.prev_score.toFixed(1)} ({h.prev_level}) → {h.new_score.toFixed(1)} ({h.new_level})
                    </span>
                    <div className="text-slate-600 dark:text-zinc-400 mt-0.5">{h.reason}</div>
                  </div>
                  <div className="ios-num text-[11px] text-slate-500">
                    {h.actor_id} • {h.recorded_at}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // =========================================================================
  // ALERT DIRECTORY VIEW (Functions 91-94)
  // =========================================================================
  return (
    <div className="space-y-5">
      <div className="liquid-glass rounded-2xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/30 space-y-2.5">
          {/* Row 1: Primary Search, Rule/Severity/Status, Exports & Pagination */}
          <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-500 dark:text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="search"
                  value={filters.search}
                  onChange={(e) => onFiltersChange({ ...filters, search: e.target.value })}
                  placeholder="Alert ID, Txn ID, Customer ID, Account ID..."
                  className="pl-8 pr-3 py-1.5 w-64 bg-white/60 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-500 focus:outline-none"
                />
              </div>

              <select
                value={filters.severity}
                onChange={(e) => onFiltersChange({ ...filters, severity: e.target.value })}
                className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200"
              >
                <option value="ALL">All Severities</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>

              <select
                value={filters.rule_id}
                onChange={(e) => onFiltersChange({ ...filters, rule_id: e.target.value })}
                className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200 max-w-[230px]"
              >
                <option value="ALL">All Risk Rules</option>
                {rules.map((r) => (
                  <option key={r.rule_id} value={r.rule_id}>
                    {r.rule_id}: {r.rule_name}
                  </option>
                ))}
              </select>

              <select
                value={filters.status}
                onChange={(e) => onFiltersChange({ ...filters, status: e.target.value })}
                className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200"
              >
                <option value="ALL">All Statuses</option>
                <option value="GROUPED">GROUPED</option>
                <option value="RESOLVED">RESOLVED</option>
                <option value="DISMISSED">DISMISSED</option>
                <option value="OPEN">OPEN</option>
                <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                <option value="UNDER_INVESTIGATION">UNDER_INVESTIGATION</option>
                <option value="ESCALATED">ESCALATED</option>
                <option value="FALSE_POSITIVE">FALSE_POSITIVE</option>
              </select>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs ios-num">
              <button
                type="button"
                onClick={() =>
                  downloadExport(
                    api.alertsExportUrl("csv", {
                      search: filters.search,
                      severity: filters.severity,
                      rule_id: filters.rule_id,
                      status: filters.status,
                      owner_analyst: filters.owner_analyst,
                      sla_breached: filters.sla_breached === "ALL" ? undefined : filters.sla_breached,
                      start_date: filters.start_date,
                      end_date: filters.end_date,
                      sort_by: filters.sort_by,
                      sort_dir: filters.sort_dir,
                    }),
                    "yottaflex_alerts.csv"
                  )
                }
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-white/55 dark:bg-zinc-900 border border-white/80 dark:border-white/15 font-semibold text-azure-700 dark:text-white"
              >
                <Download className="w-3 h-3" /> CSV
              </button>
              <button
                type="button"
                onClick={() =>
                  downloadExport(
                    api.alertsExportUrl("json", {
                      search: filters.search,
                      severity: filters.severity,
                      rule_id: filters.rule_id,
                      status: filters.status,
                      owner_analyst: filters.owner_analyst,
                      sla_breached: filters.sla_breached === "ALL" ? undefined : filters.sla_breached,
                      start_date: filters.start_date,
                      end_date: filters.end_date,
                      sort_by: filters.sort_by,
                      sort_dir: filters.sort_dir,
                    }),
                    "yottaflex_alerts.json"
                  )
                }
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black font-semibold"
              >
                <Download className="w-3 h-3" /> JSON
              </button>
              <span className="inline-flex items-center gap-1.5 font-semibold text-slate-600 dark:text-zinc-400">
                <Bell className="w-3.5 h-3.5" />
                {total.toLocaleString("en-US")} alerts • Page {page + 1}/{totalPages}
              </span>
            </div>
          </div>

          {/* Row 2: Owner, SLA, Date Range & Sort Controls */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/30 dark:border-white/[0.06] text-xs">
            <select
              value={filters.owner_analyst}
              onChange={(e) => onFiltersChange({ ...filters, owner_analyst: e.target.value })}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200"
              aria-label="Filter alerts by owner"
            >
              <option value="ALL">All Owners</option>
              <option value="UNASSIGNED">Unassigned</option>
              <option value="ANL-001">ANL-001</option>
              <option value="ANL-002">ANL-002</option>
              <option value="ANL-003">ANL-003</option>
              <option value="ADM-001">ADM-001</option>
            </select>

            <select
              value={filters.sla_breached}
              onChange={(e) => onFiltersChange({ ...filters, sla_breached: e.target.value })}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium text-slate-800 dark:text-zinc-200"
              aria-label="Filter alerts by SLA"
            >
              <option value="ALL">All SLA States</option>
              <option value="1">SLA Breached Only</option>
              <option value="0">Within SLA</option>
            </select>

            <input
              type="date"
              value={filters.start_date}
              onChange={(e) => onFiltersChange({ ...filters, start_date: e.target.value })}
              className="glass-pill rounded-full px-3 py-1.5 text-xs ios-num text-slate-800 dark:text-zinc-200"
              aria-label="Alert Start Date"
            />
            <input
              type="date"
              value={filters.end_date}
              onChange={(e) => onFiltersChange({ ...filters, end_date: e.target.value })}
              className="glass-pill rounded-full px-3 py-1.5 text-xs ios-num text-slate-800 dark:text-zinc-200"
              aria-label="Alert End Date"
            />

            <select
              value={filters.sort_by}
              onChange={(e) =>
                onFiltersChange({ ...filters, sort_by: e.target.value as AlertFiltersState["sort_by"] })
              }
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-semibold text-slate-800 dark:text-zinc-200"
              aria-label="Sort alerts by"
            >
              <option value="risk_score">Sort: Risk Score</option>
              <option value="priority">Sort: Case Priority</option>
              <option value="created_at">Sort: Created Date</option>
            </select>

            <button
              type="button"
              onClick={() =>
                onFiltersChange({ ...filters, sort_dir: filters.sort_dir === "desc" ? "asc" : "desc" })
              }
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/55 dark:bg-zinc-900 border border-white/80 dark:border-white/15 text-xs font-semibold text-slate-800 dark:text-zinc-200"
            >
              <ArrowDownUp className="w-3 h-3" /> {filters.sort_dir.toUpperCase()}
            </button>
          </div>

          <div className="pt-2 border-t border-white/25 dark:border-white/[0.06]">
            <SavedPresetsBar
              workspace="alerts"
              currentFilters={{
                severity: filters.severity,
                rule_id: filters.rule_id,
                status: filters.status,
                owner_analyst: filters.owner_analyst,
                sla_breached: filters.sla_breached,
                search: filters.search,
              }}
              onApplyPreset={(f) =>
                onFiltersChange({
                  ...filters,
                  severity: typeof f.severity === "string" ? f.severity : filters.severity,
                  rule_id: typeof f.rule_id === "string" ? f.rule_id : filters.rule_id,
                  status: typeof f.status === "string" ? f.status : filters.status,
                  owner_analyst: typeof f.owner_analyst === "string" ? f.owner_analyst : filters.owner_analyst,
                  sla_breached: typeof f.sla_breached === "string" ? f.sla_breached : filters.sla_breached,
                  search: typeof f.search === "string" ? f.search : filters.search,
                })
              }
            />
          </div>
        </div>

        {/* Function 107: Bulk Alert Triage Bar */}
        {(selectedIds.length > 0 || busyMsg) && (
          <div className="px-5 py-3 border-b border-white/50 dark:border-white/10 bg-azure-500/10 dark:bg-sky-500/10 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <CheckSquare className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              <span className="font-semibold text-slate-900 dark:text-white">
                {selectedIds.length} alert(s) selected
              </span>
              {selectedIds.length > 0 && (
                <>
                  <select
                    value={bulkAction}
                    onChange={(e) => setBulkAction(e.target.value)}
                    className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-full px-2.5 py-1 font-medium"
                  >
                    <option value="ACKNOWLEDGE">Acknowledge</option>
                    <option value="UNDER_INVESTIGATION">Mark Under Investigation</option>
                    <option value="ASSIGN">Assign Analyst</option>
                    <option value="DISMISS_FP">Dismiss False Positive</option>
                    <option value="ESCALATE">Escalate</option>
                  </select>
                  {bulkAction === "ASSIGN" && (
                    <select
                      value={bulkOwner}
                      onChange={(e) => setBulkOwner(e.target.value)}
                      className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-full px-2.5 py-1 font-medium"
                    >
                      <option value="ANL-001">ANL-001</option>
                      <option value="ANL-002">ANL-002</option>
                      <option value="ANL-003">ANL-003</option>
                      <option value="ADM-001">ADM-001</option>
                    </select>
                  )}
                  <input
                    type="text"
                    value={bulkRationale}
                    onChange={(e) => setBulkRationale(e.target.value)}
                    placeholder="Optional batch rationale..."
                    className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-full px-3 py-1"
                  />
                  <button
                    type="button"
                    onClick={handleBulkSubmit}
                    className="px-3.5 py-1 rounded-full bg-azure-600 dark:bg-white text-white dark:text-black font-semibold"
                  >
                    Apply Batch
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedIds([])}
                    className="px-2.5 py-1 rounded-full bg-white/55 dark:bg-zinc-900 text-slate-700 dark:text-zinc-300"
                  >
                    Clear
                  </button>
                </>
              )}
            </div>
            {busyMsg && (
              <div className="flex items-center gap-2 font-medium text-azure-800 dark:text-sky-300">
                <span>{busyMsg}</span>
                <button type="button" onClick={() => setBusyMsg(null)} className="underline text-[11px]">
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
                    aria-label="Select all alerts on page"
                    checked={alerts.length > 0 && alerts.every((a) => selectedIds.includes(a.alert_id))}
                    onChange={(e) =>
                      setSelectedIds(e.target.checked ? alerts.map((a) => a.alert_id) : [])
                    }
                  />
                </th>
                <th className="py-3 px-4">Alert ID</th>
                <th className="py-3 px-3">Risk Rule</th>
                <th className="py-3 px-3">Customer / Account</th>
                <th className="py-3 px-3">Trigger Txn / Case</th>
                <th className="py-3 px-3 text-right">Exposure</th>
                <th
                  onClick={() => toggleSort("created_at")}
                  className="py-3 px-3 cursor-pointer hover:text-azure-700 dark:hover:text-white select-none"
                >
                  Created {filters.sort_by === "created_at" ? (filters.sort_dir === "desc" ? "↓" : "↑") : ""}
                </th>
                <th
                  onClick={() => toggleSort("priority")}
                  className="py-3 px-3 text-right cursor-pointer hover:text-azure-700 dark:hover:text-white select-none"
                >
                  Priority {filters.sort_by === "priority" ? (filters.sort_dir === "desc" ? "↓" : "↑") : ""}
                </th>
                <th
                  onClick={() => toggleSort("risk_score")}
                  className="py-3 px-4 text-right cursor-pointer hover:text-azure-700 dark:hover:text-white select-none"
                >
                  Severity / Score {filters.sort_by === "risk_score" ? (filters.sort_dir === "desc" ? "↓" : "↑") : ""}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
              {alerts.map((al) => (
                <tr
                  key={al.alert_id}
                  onMouseEnter={(e) => rowMag.onRowEnter(e.currentTarget)}
                  onClick={() => onSelectAlert(al.alert_id)}
                  className="liquid-row-magnify cursor-pointer"
                >
                  <td className="py-2.5 pl-4 pr-2" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Select ${al.alert_id}`}
                      checked={selectedIds.includes(al.alert_id)}
                      onChange={() => toggleSelectAlert(al.alert_id)}
                    />
                  </td>
                  <td className="py-2.5 px-4 font-mono font-semibold text-azure-700 dark:text-white">
                    <div>{al.alert_id}</div>
                    <div className="flex flex-wrap items-center gap-1 mt-1">
                      <Badge variant={statusVariant(al.status)}>{al.status}</Badge>
                      {al.sla_breached && <Badge variant="CRITICAL">SLA</Badge>}
                      {al.owner_analyst_id && <Badge variant="BLUE">{al.owner_analyst_id}</Badge>}
                    </div>
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{al.rule_id}</span>
                      <span className="font-semibold text-slate-900 dark:text-zinc-100">{al.rule_name}</span>
                    </div>
                    <div className="text-[11px] text-slate-500 dark:text-zinc-400 truncate max-w-xs mt-0.5">
                      {al.explanation_summary}
                    </div>
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="font-semibold text-slate-900 dark:text-white">{al.customer_name}</div>
                    <div className="font-mono text-[11px] text-slate-500 dark:text-zinc-400">{al.account_id}</div>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[11px]">
                    <div className="text-slate-800 dark:text-zinc-200">{al.primary_txn_id || "ORPHAN_ALERT"}</div>
                    {al.case_id && <div className="text-azure-700 dark:text-sky-300">{al.case_id}</div>}
                  </td>
                  <td className="py-2.5 px-3 text-right font-semibold">
                    <IosAmount value={al.trigger_total_amount} />
                    <div className="text-[10.5px] ios-num text-slate-500">{al.trigger_txn_count} txn(s)</div>
                  </td>
                  <td className="py-2.5 px-3 ios-num text-slate-600 dark:text-zinc-400">{al.created_at}</td>
                  <td className="py-2.5 px-3 text-right ios-num font-bold text-slate-900 dark:text-white">
                    {al.priority_score_effective.toFixed(1)}
                  </td>
                  <td className="py-2.5 px-4 text-right">
                    <Badge variant={tierVariant(al.severity)}>
                      {al.severity} ({al.risk_score.toFixed(1)})
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <GlassPagination
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
          unitLabel="alerts"
        />
      </div>
    </div>
  );
};
