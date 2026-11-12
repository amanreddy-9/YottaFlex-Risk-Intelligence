import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownUp,
  ArrowLeft,
  ArrowLeftRight,
  CheckCircle2,
  Download,
  Globe2,
  Laptop,
  Play,
  RefreshCw,
  Search,
  ShieldAlert,
  Store,
} from "lucide-react";
import { api, downloadExport } from "../api/client";
import type {
  CalibrationProposalItem,
  RiskEvaluationResult,
  RiskScoringOverview,
  TransactionDetail,
  TransactionItem,
} from "../types/workbench";
import { GlassPagination } from "./GlassPagination";
import { Badge, IosAmount, tierVariant } from "./Badge";
import { LiquidGlassCard, useRowGlassMagnifier } from "./LiquidGlassSurface";

export interface TransactionFiltersState {
  search: string;
  start_date: string;
  end_date: string;
  min_amount: string;
  max_amount: string;
  txn_type: string;
  risk_level: string;
  status: string;
  pattern: string;
  sort_by: "occurred_at" | "amount" | "risk_score";
  sort_dir: "desc" | "asc";
}

interface TransactionsViewProps {
  transactions: TransactionItem[];
  total: number;
  page: number;
  pageSize: number;
  filters: TransactionFiltersState;
  selectedDetail: TransactionDetail | null;
  riskScoring: RiskScoringOverview | null;
  userRole?: string;
  onRefreshScoring?: () => Promise<void> | void;
  onFiltersChange: (next: TransactionFiltersState) => void;
  onPageChange: (nextPage: number) => void;
  onPageSizeChange: (nextSize: number) => void;
  onSelectTransaction: (transactionId: string) => void;
  onCloseDetail: () => void;
  onOpenAccount: (accountId: string) => void;
  onOpenCustomer: (customerId: string) => void;
}

const PATTERN_PILLS: Array<{ id: string; label: string }> = [
  { id: "ALL", label: "All Transactions" },
  { id: "LARGE_AMOUNT", label: "Unusually Large" },
  { id: "RAPID_SUCCESSIVE", label: "Rapid Successive" },
  { id: "NEW_DEVICE", label: "New Device" },
  { id: "DORMANT_ACCOUNT", label: "Dormant Account" },
  { id: "LINKED_PATTERN", label: "Linked Pattern" },
  { id: "VALIDATION_EXCEPTION", label: "Validation Exceptions" },
];

const PATTERN_BADGE_LABEL: Record<string, string> = {
  LARGE_AMOUNT: "LARGE",
  RAPID_SUCCESSIVE: "RAPID",
  NEW_DEVICE: "NEW DEV",
  DORMANT_ACCOUNT: "DORMANT",
  LINKED_PATTERN: "LINKED",
  VALIDATION_EXCEPTION: "EXCEPTION",
};

export const TransactionsView: React.FC<TransactionsViewProps> = ({
  transactions,
  total,
  page,
  pageSize,
  filters,
  selectedDetail,
  riskScoring,
  userRole,
  onRefreshScoring,
  onFiltersChange,
  onPageChange,
  onPageSizeChange,
  onSelectTransaction,
  onCloseDetail,
  onOpenAccount,
  onOpenCustomer,
}) => {
  const rowMag = useRowGlassMagnifier();
  const relMag = useRowGlassMagnifier();
  const topAcctMag = useRowGlassMagnifier();
  const topCustMag = useRowGlassMagnifier();

  const [subMode, setSubMode] = useState<"EXPLORER" | "SCORING">("EXPLORER");
  const [liveEval, setLiveEval] = useState<RiskEvaluationResult | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [reevalMsg, setReevalMsg] = useState<string | null>(null);
  const [reevalBusy, setReevalBusy] = useState(false);
  const [ruleWeights, setRuleWeights] = useState<Record<string, number>>({});

  // Simulator inputs for Functions 71-75
  const [simAccount, setSimAccount] = useState("ACC-CUS-000001-01");
  const [simAmount, setSimAmount] = useState("4500");
  const [simType, setSimType] = useState("WIRE_OUT");
  const [simCountry, setSimCountry] = useState("CY");
  const [simDevice, setSimDevice] = useState("");
  const [simMerchant, setSimMerchant] = useState("");
  const [simTxnId, setSimTxnId] = useState("");

  // Batch 9 Functions 203-205, 218: Calibration Proposals & Ad-Hoc Pattern Sandbox
  const [proposals, setProposals] = useState<CalibrationProposalItem[]>([]);
  const [sbMinAmt, setSbMinAmt] = useState("5000");
  const [sbChannel, setSbChannel] = useState("ALL");
  const [sbCountry, setSbCountry] = useState("ALL");
  const [sbResult, setSbResult] = useState<{ matched_txns: number; matched_volume: number; distinct_accounts: number; items: Array<Record<string, unknown>> } | null>(null);

  useEffect(() => {
    if (subMode !== "SCORING") return;
    api.calibrationProposals().then((res) => setProposals(res.items)).catch(() => {});
  }, [subMode]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const toggleSort = (col: "occurred_at" | "amount" | "risk_score") => {
    if (filters.sort_by === col) {
      onFiltersChange({ ...filters, sort_dir: filters.sort_dir === "desc" ? "asc" : "desc" });
    } else {
      onFiltersChange({ ...filters, sort_by: col, sort_dir: "desc" });
    }
  };

  const runLiveEvaluation = async (body: { transaction_id?: string; payload?: Record<string, unknown> }) => {
    setEvalLoading(true);
    setEvalError(null);
    try {
      const res = await api.evaluateRisk(body);
      setLiveEval(res);
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : "Evaluation failed");
    } finally {
      setEvalLoading(false);
    }
  };

  const runFullReeval = async (ruleId?: string) => {
    setReevalBusy(true);
    setReevalMsg(null);
    setEvalError(null);
    try {
      const res = await api.reevaluateRisk(ruleId);
      setReevalMsg(res.execution_run.summary);
      if (onRefreshScoring) await onRefreshScoring();
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : "Re-evaluation failed");
    } finally {
      setReevalBusy(false);
    }
  };

  const applyRuleUpdate = async (ruleId: string, weight: number, active: boolean) => {
    setReevalBusy(true);
    setReevalMsg(null);
    setEvalError(null);
    try {
      const res = await api.updateRiskRule(ruleId, { base_weight: weight, is_active: active });
      setReevalMsg(res.execution_run.summary);
      if (onRefreshScoring) await onRefreshScoring();
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : "Rule update failed");
    } finally {
      setReevalBusy(false);
    }
  };

  // =========================================================================
  // TRANSACTION 360 DETAIL VIEW (Functions 52-63, 69, 71-75)
  // =========================================================================
  if (selectedDetail) {
    const t = selectedDetail.transaction;
    const acct = selectedDetail.account;
    const cust = selectedDetail.customer;
    const m = selectedDetail.merchant;
    const dev = selectedDetail.device;
    const tr = selectedDetail.transfer_link;

    return (
      <div className="space-y-5">
        {/* Top Banner */}
        <div className="liquid-glass rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="font-mono text-lg font-bold text-slate-950 dark:text-white">{t.transaction_id}</h2>
              <Badge variant="BLUE">{t.txn_type}</Badge>
              <Badge variant={tierVariant(t.risk_level)}>
                {t.risk_level} RISK ({t.risk_score.toFixed(1)})
              </Badge>
              <Badge variant={t.direction === "CREDIT" ? "LOW" : "NEUTRAL"}>{t.direction}</Badge>
              <Badge variant="NEUTRAL">{t.status}</Badge>
              {t.is_cross_border && <Badge variant="HIGH">CROSS-BORDER ({t.counterparty_country})</Badge>}
            </div>
            <div className="mt-1.5 text-xs font-mono text-slate-600 dark:text-zinc-400">
              Timestamp: {t.occurred_at} • Channel: {t.channel} • Counterparty Location: {t.counterparty_country} (Customer
              Home: {cust.home_country})
            </div>
            <div className="mt-1 text-xs text-slate-700 dark:text-zinc-300">Note: {t.reference_note}</div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => onOpenAccount(acct.account_id)}
              className="px-3 py-1.5 glass-pill rounded-full text-xs font-semibold text-azure-700 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              Account: {acct.account_id}
            </button>
            <button
              type="button"
              onClick={() => onOpenCustomer(cust.customer_id)}
              className="px-3 py-1.5 glass-pill rounded-full text-xs font-semibold text-azure-700 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              Customer: {cust.full_name}
            </button>
            <button
              type="button"
              onClick={() => runLiveEvaluation({ transaction_id: t.transaction_id })}
              disabled={evalLoading}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-gradient-to-r from-azure-500 to-azure-600 text-white text-xs font-semibold shadow-sm hover:opacity-95"
            >
              <Play className="w-3 h-3" /> {evalLoading ? "Evaluating..." : "Re-Run Risk Rules"}
            </button>
            <button
              type="button"
              onClick={onCloseDetail}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/60 dark:bg-zinc-900 border border-white/85 dark:border-white/15 text-xs font-semibold text-slate-800 dark:text-zinc-200 hover:bg-white transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Ledger
            </button>
          </div>
        </div>

        {/* Function 69: Processing & Validation Exceptions */}
        {selectedDetail.validation_exceptions.length > 0 && (
          <div className="liquid-glass rounded-2xl p-4 border-rose-400/60 dark:border-rose-500/40 bg-rose-500/10">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-rose-700 dark:text-rose-300 mb-2">
              <AlertTriangle className="w-4 h-4" /> Validation &amp; Processing Exceptions Detected (
              {selectedDetail.validation_exceptions.length})
            </div>
            <div className="space-y-2">
              {selectedDetail.validation_exceptions.map((ex) => (
                <div
                  key={ex.exception_id}
                  className="rounded-xl p-3 bg-white/45 dark:bg-black/45 border border-rose-300/60 dark:border-rose-500/30 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono font-bold text-rose-700 dark:text-rose-300">{ex.issue_type}</span>
                    <Badge variant="CRITICAL">{ex.severity}</Badge>
                  </div>
                  <div className="mt-1 text-slate-800 dark:text-zinc-200">{ex.violated_invariant}</div>
                  <div className="mt-0.5 font-mono text-[11px] text-slate-600 dark:text-zinc-400">{ex.evidence}</div>
                  <div className="mt-1 text-[11px] text-emerald-700 dark:text-emerald-300">
                    Remediation: {ex.remediation}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Functions 53, 54, 60, 72, 73, 74: Debit/Credit Balance & Multi-Level Risk Scores */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <LiquidGlassCard variant="hero" className="rounded-2xl p-4 text-white">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-white/85">
              Debit / Credit Amount
            </div>
            <div className="mt-1.5 text-2xl font-bold text-white">
              <IosAmount value={t.signed_amount} showPlus={t.direction === "CREDIT"} />
            </div>
            <div className="mt-1 text-[11px] text-white/85">
              {t.direction} ({t.currency}) • {t.channel}
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard variant="emerald" className="rounded-2xl p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-800 dark:text-zinc-400">
              Balance Before → After
            </div>
            <div className="mt-1.5 text-sm font-bold ios-num text-slate-950 dark:text-white flex items-center gap-1.5 flex-wrap">
              <IosAmount value={t.balance_before} />
              <span>→</span>
              <IosAmount value={t.balance_after} />
            </div>
            <div className="mt-1.5 flex items-center gap-1.5 text-[11px]">
              {t.balance_reconciled ? (
                <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300 font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Reconciled ({t.balance_delta >= 0 ? "+" : ""}
                  {t.balance_delta.toFixed(2)})
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-rose-700 dark:text-rose-300 font-semibold">
                  <AlertTriangle className="w-3.5 h-3.5" /> Balance Drift Detected
                </span>
              )}
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard variant={t.risk_level === "HIGH" ? "rose" : "amber"} className="rounded-2xl p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
              Transaction &amp; Account Risk
            </div>
            <div className="mt-1.5 text-2xl font-bold ios-num text-slate-950 dark:text-white">
              {t.risk_score.toFixed(1)}
              <span className="text-xs font-normal text-slate-500 dark:text-zinc-400 ml-1.5">
                / Acct: {selectedDetail.account_risk.risk_score.toFixed(1)} ({selectedDetail.account_risk.risk_level})
              </span>
            </div>
            <div className="mt-1 text-[11px] text-slate-600 dark:text-zinc-400">
              {selectedDetail.triggered_alerts.length} alert(s) • Classification: {t.risk_level}
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard variant="glass" className="rounded-2xl p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
              Customer Risk Score
            </div>
            <div className="mt-1.5 text-2xl font-bold ios-num text-slate-950 dark:text-white">
              {selectedDetail.customer_risk.risk_score.toFixed(1)}
            </div>
            <div className="mt-1 text-[11px] text-slate-600 dark:text-zinc-400">
              Level: {selectedDetail.customer_risk.risk_level} • {selectedDetail.customer_risk.suspicious_account_count}{" "}
              suspicious acct(s)
            </div>
          </LiquidGlassCard>
        </div>

        {/* Functions 55, 56, 57: Location, Merchant & Device Info */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="liquid-glass rounded-2xl p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white mb-3">
              <Globe2 className="w-4 h-4 text-azure-600 dark:text-azure-400" />
              Location &amp; Timestamp
            </div>
            <dl className="grid grid-cols-2 gap-y-2 text-xs">
              <dt className="text-slate-500 dark:text-zinc-400">Occurred At (UTC)</dt>
              <dd className="font-mono text-slate-950 dark:text-white">{t.occurred_at}</dd>
              <dt className="text-slate-500 dark:text-zinc-400">Counterparty Country</dt>
              <dd className="font-mono font-semibold text-slate-950 dark:text-white">{t.counterparty_country}</dd>
              <dt className="text-slate-500 dark:text-zinc-400">Customer Home</dt>
              <dd className="font-mono text-slate-800 dark:text-zinc-200">{cust.home_country}</dd>
              <dt className="text-slate-500 dark:text-zinc-400">Geo Status</dt>
              <dd>
                <Badge variant={t.is_cross_border ? "HIGH" : "LOW"}>
                  {t.is_cross_border ? "CROSS-BORDER" : "DOMESTIC"}
                </Badge>
              </dd>
            </dl>
          </div>

          <div className="liquid-glass rounded-2xl p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white mb-3">
              <Store className="w-4 h-4 text-azure-600 dark:text-azure-400" />
              Associated Merchant
            </div>
            {m ? (
              <dl className="grid grid-cols-2 gap-y-2 text-xs">
                <dt className="text-slate-500 dark:text-zinc-400">Merchant ID</dt>
                <dd className="font-mono font-semibold text-slate-950 dark:text-white">{m.merchant_id}</dd>
                <dt className="text-slate-500 dark:text-zinc-400">Name &amp; MCC</dt>
                <dd className="text-slate-900 dark:text-zinc-200">
                  {m.merchant_name} ({m.category})
                </dd>
                <dt className="text-slate-500 dark:text-zinc-400">Country / Tier</dt>
                <dd className="flex items-center gap-1.5">
                  <span className="font-mono">{m.country}</span>
                  <Badge variant={tierVariant(m.risk_tier)}>{m.risk_tier}</Badge>
                </dd>
                <dt className="text-slate-500 dark:text-zinc-400">Portfolio Avg</dt>
                <dd className="ios-num text-slate-800 dark:text-zinc-200">
                  {m.txn_count.toLocaleString("en-US")} txns • <IosAmount value={m.avg_amount} />
                </dd>
              </dl>
            ) : (
              <div className="text-xs text-slate-500 dark:text-zinc-400 py-4">
                No merchant entity linked ({t.txn_type}).
              </div>
            )}
          </div>

          <div className="liquid-glass rounded-2xl p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white mb-3">
              <Laptop className="w-4 h-4 text-azure-600 dark:text-azure-400" />
              Associated Device
            </div>
            {dev ? (
              <dl className="grid grid-cols-2 gap-y-2 text-xs">
                <dt className="text-slate-500 dark:text-zinc-400">Device ID</dt>
                <dd className="font-mono font-semibold text-slate-950 dark:text-white">{dev.device_id}</dd>
                <dt className="text-slate-500 dark:text-zinc-400">OS / IP Country</dt>
                <dd className="font-mono text-slate-900 dark:text-zinc-200">
                  {dev.os_family} • {dev.ip_country}
                </dd>
                <dt className="text-slate-500 dark:text-zinc-400">Risk &amp; Trust</dt>
                <dd className="flex items-center gap-1.5 flex-wrap">
                  <Badge variant={tierVariant(dev.risk_tier)}>{dev.risk_tier}</Badge>
                  {dev.is_emulator === 1 && <Badge variant="CRITICAL">EMULATOR</Badge>}
                  <Badge variant={dev.is_trusted ? "LOW" : "HIGH"}>{dev.is_trusted ? "TRUSTED" : "UNTRUSTED"}</Badge>
                </dd>
                <dt className="text-slate-500 dark:text-zinc-400">Shared Customers</dt>
                <dd className="ios-num font-semibold text-slate-900 dark:text-zinc-200">
                  {dev.shared_customer_count} customer(s) • Linked: {dev.first_seen_at || dev.first_observed_at}
                </dd>
              </dl>
            ) : (
              <div className="text-xs text-slate-500 dark:text-zinc-400 py-4">
                No device telemetry attached to this transaction.
              </div>
            )}
          </div>
        </div>

        {/* Functions 58 & 59: Origin/Destination Accounts & Linked Transfers */}
        {tr && (
          <div className="liquid-glass rounded-2xl p-5">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white">
                <ArrowLeftRight className="w-4 h-4 text-azure-600 dark:text-azure-400" />
                Transfer Origin &amp; Destination Legs ({tr.transfer_id})
              </div>
              <Badge variant={tr.status === "SETTLED" ? "LOW" : "CRITICAL"}>{tr.status}</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="rounded-xl p-3 bg-white/40 dark:bg-white/[0.04] border border-white/60 dark:border-white/10">
                <div className="text-[11px] font-semibold uppercase text-slate-500">Origin (Source) Account</div>
                <button
                  type="button"
                  onClick={() => onOpenAccount(tr.source_account_id)}
                  className="mt-1 font-mono font-bold text-azure-700 dark:text-white hover:underline block"
                >
                  {tr.source_account_id}
                </button>
                <div className="text-slate-600 dark:text-zinc-400">{tr.source_owner_name}</div>
                <button
                  type="button"
                  onClick={() => onSelectTransaction(tr.debit_txn_id)}
                  className="mt-1 font-mono text-[11px] text-rose-600 dark:text-rose-400 hover:underline"
                >
                  Debit Leg: {tr.debit_txn_id}
                </button>
              </div>

              <div className="rounded-xl p-3 bg-white/40 dark:bg-white/[0.04] border border-white/60 dark:border-white/10 flex flex-col justify-center items-center text-center">
                <div className="text-[11px] font-semibold uppercase text-slate-500">Transfer Amount</div>
                <div className="mt-1 text-lg font-bold text-slate-950 dark:text-white">
                  <IosAmount value={tr.transfer_amount} />
                </div>
                <div className="text-[11px] text-slate-600 dark:text-zinc-400">
                  {tr.is_same_customer ? "Internal / Same Customer" : "External Counterparty"} • Settled:{" "}
                  {tr.settled_at || "Pending"}
                </div>
              </div>

              <div className="rounded-xl p-3 bg-white/40 dark:bg-white/[0.04] border border-white/60 dark:border-white/10">
                <div className="text-[11px] font-semibold uppercase text-slate-500">Destination Account</div>
                <button
                  type="button"
                  onClick={() => onOpenAccount(tr.dest_account_id)}
                  className="mt-1 font-mono font-bold text-azure-700 dark:text-white hover:underline block"
                >
                  {tr.dest_account_id}
                </button>
                <div className="text-slate-600 dark:text-zinc-400">{tr.dest_owner_name}</div>
                {tr.credit_txn_id ? (
                  <button
                    type="button"
                    onClick={() => onSelectTransaction(tr.credit_txn_id!)}
                    className="mt-1 font-mono text-[11px] text-emerald-600 dark:text-emerald-400 hover:underline"
                  >
                    Credit Leg: {tr.credit_txn_id}
                  </button>
                ) : (
                  <div className="mt-1 font-mono text-[11px] text-rose-600 dark:text-rose-400">
                    MISSING CREDIT LEG
                  </div>
                )}
              </div>
            </div>

            {selectedDetail.linked_transfers.length > 0 && (
              <div className="mt-3 pt-3 border-t border-white/40 dark:border-white/10">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-2">
                  Linked Multi-Hop Transfers Involving Origin/Destination Accounts ({selectedDetail.linked_transfers.length})
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedDetail.linked_transfers.slice(0, 8).map((lt) => (
                    <button
                      key={lt.transfer_id}
                      type="button"
                      onClick={() => onSelectTransaction(lt.debit_txn_id)}
                      className="glass-pill px-2.5 py-1 rounded-full text-[11px] font-mono hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
                    >
                      {lt.source_account_id} → {lt.dest_account_id} (<IosAmount value={lt.transfer_amount} />)
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Functions 60-62 & 71-75: Triggered Rules, Explanations & Live 8-Rule Check Matrix */}
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-azure-600 dark:text-azure-400" />
                Triggered Risk Rules &amp; Explainability Matrix ({selectedDetail.flag_reasons.length} Flag Reason
                {selectedDetail.flag_reasons.length === 1 ? "" : "s"})
              </h3>
              <p className="text-xs text-slate-600 dark:text-zinc-400">
                Quantitative rule evaluation explaining why this transaction received score {t.risk_score.toFixed(1)} (
                {t.risk_level})
              </p>
            </div>
          </div>

          {selectedDetail.flag_reasons.length > 0 && (
            <div className="px-5 py-3 bg-amber-500/10 border-b border-white/40 dark:border-white/10 space-y-1">
              {selectedDetail.flag_reasons.map((reason, idx) => (
                <div key={idx} className="text-xs font-medium text-slate-900 dark:text-amber-200 flex items-start gap-2">
                  <span className="font-mono text-amber-700 dark:text-amber-400">•</span>
                  <span>{reason}</span>
                </div>
              ))}
            </div>
          )}

          {selectedDetail.triggered_alerts.length > 0 && (
            <div className="px-5 py-3 border-b border-white/40 dark:border-white/10 space-y-2">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-zinc-400">
                Recorded Alert Trigger Facts
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {selectedDetail.triggered_alerts.map((al) => (
                  <div
                    key={`${al.alert_id}-${al.metric_name}`}
                    className="rounded-xl p-3 bg-white/45 dark:bg-white/[0.04] border border-white/70 dark:border-white/10 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono font-bold text-slate-950 dark:text-white">
                        {al.alert_id} • {al.rule_id}
                      </span>
                      <Badge variant={tierVariant(al.severity)}>{al.risk_score.toFixed(1)}</Badge>
                    </div>
                    <div className="font-semibold text-slate-800 dark:text-zinc-200 mt-0.5">{al.rule_name}</div>
                    <div className="text-[11px] text-slate-600 dark:text-zinc-400 mt-1">{al.explanation_summary}</div>
                    <div className="font-mono text-[10.5px] text-azure-700 dark:text-azure-300 mt-1">
                      {al.metric_name}: observed {al.observed_value} vs threshold {al.threshold_value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/35 text-[11px] font-semibold uppercase text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Rule</th>
                  <th className="py-2.5 px-3">Verdict</th>
                  <th className="py-2.5 px-3">Configured Threshold</th>
                  <th className="py-2.5 px-3">Observed Metric</th>
                  <th className="py-2.5 px-4 text-right">Points</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {selectedDetail.rule_evaluations.map((re) => (
                  <tr key={re.rule_id} className="hover:bg-white/25 dark:hover:bg-white/[0.03]">
                    <td className="py-2.5 px-4">
                      <span className="font-mono font-semibold text-slate-950 dark:text-white">{re.rule_id}</span>
                      <span className="ml-2 text-slate-700 dark:text-zinc-300">{re.rule_name}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant={re.status === "TRIGGERED" ? "CRITICAL" : re.status === "PASSED" ? "LOW" : "NEUTRAL"}>
                        {re.status}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-slate-600 dark:text-zinc-400">{re.threshold_desc}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-800 dark:text-zinc-200">
                      {re.observed_metric}
                    </td>
                    <td className="py-2.5 px-4 text-right ios-num font-bold">
                      {re.points_awarded > 0 ? `+${re.points_awarded}` : "0"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Function 63: Related Transactions from Same Customer / Account */}
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Related Transactions — Same Customer &amp; Linked Accounts ({selectedDetail.related_transactions.length})
            </h3>
          </div>
          <div ref={relMag.containerRef} onMouseLeave={relMag.onContainerLeave} className="relative overflow-x-auto max-h-80">
            {relMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/35 text-[11px] font-semibold uppercase text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Transaction ID</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Account</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-4 text-right">Balance After</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {selectedDetail.related_transactions.map((rt) => (
                  <tr
                    key={rt.transaction_id}
                    onMouseEnter={(e) => relMag.onRowEnter(e.currentTarget)}
                    onClick={() => onSelectTransaction(rt.transaction_id)}
                    className="liquid-row-magnify cursor-pointer"
                  >
                    <td className="py-2 px-4 font-mono font-semibold text-azure-700 dark:text-white">
                      {rt.transaction_id}
                    </td>
                    <td className="py-2 px-3 ios-num text-slate-600 dark:text-zinc-400">{rt.occurred_at}</td>
                    <td className="py-2 px-3 font-mono text-slate-700 dark:text-zinc-300">{rt.account_id}</td>
                    <td className="py-2 px-3">
                      <Badge variant="NEUTRAL">{rt.txn_type}</Badge>
                    </td>
                    <td className="py-2 px-3 text-right font-semibold">
                      <IosAmount value={rt.direction === "CREDIT" ? rt.amount : -rt.amount} showPlus={rt.direction === "CREDIT"} />
                    </td>
                    <td className="py-2 px-4 text-right ios-num">
                      <IosAmount value={rt.balance_after} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // MAIN VIEW: LEDGER EXPLORER (48-70) OR AUTO RISK SCORING ENGINE (71-75)
  // =========================================================================
  return (
    <div className="space-y-5">
      {/* Mode Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex items-center gap-1.5 p-1 rounded-full liquid-glass">
          <button
            type="button"
            onClick={() => setSubMode("EXPLORER")}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition ${
              subMode === "EXPLORER"
                ? "bg-azure-600 text-white shadow-sm"
                : "text-slate-700 dark:text-zinc-300 hover:bg-white/40 dark:hover:bg-white/10"
            }`}
          >
            Transaction Monitoring &amp; Pattern Detection
          </button>
          <button
            type="button"
            onClick={() => setSubMode("SCORING")}
            className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold transition ${
              subMode === "SCORING"
                ? "bg-azure-600 text-white shadow-sm"
                : "text-slate-700 dark:text-zinc-300 hover:bg-white/40 dark:hover:bg-white/10"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            Automated Risk Scoring &amp; Rule Engine
          </button>
        </div>

        {subMode === "EXPLORER" && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => downloadExport(api.transactionsExportUrl("csv", { ...filters }), "yottaflex_transactions_export.csv")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 glass-pill rounded-full text-xs font-semibold text-slate-800 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              <Download className="w-3.5 h-3.5" /> Export Filtered CSV
            </button>
            <button
              type="button"
              onClick={() => downloadExport(api.transactionsExportUrl("json", { ...filters }), "yottaflex_transactions_export.json")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 glass-pill rounded-full text-xs font-semibold text-slate-800 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              <Download className="w-3.5 h-3.5" /> Export JSON
            </button>
          </div>
        )}
      </div>

      {subMode === "SCORING" && (
        <div className="space-y-5">
          {/* Functions 71-75: Multi-Level Risk Classification Overview */}
          {riskScoring && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <LiquidGlassCard variant="hero" className="rounded-2xl p-5 text-white">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-white/85">
                    Transaction Risk Scoring (Fn 72, 75)
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                    {(["HIGH", "MEDIUM", "LOW"] as const).map((lvl) => (
                      <div key={lvl} className="rounded-xl bg-white/15 p-2">
                        <div className="text-[10px] font-bold">{lvl}</div>
                        <div className="text-lg font-bold ios-num">
                          {riskScoring.transaction_risk_distribution[lvl].count.toLocaleString("en-US")}
                        </div>
                        <div className="text-[10px] text-white/80 ios-num">
                          avg {riskScoring.transaction_risk_distribution[lvl].avg_score}
                        </div>
                      </div>
                    ))}
                  </div>
                </LiquidGlassCard>

                <LiquidGlassCard variant="amber" className="rounded-2xl p-5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-300">
                    Account-Level Risk Scoring (Fn 73, 75)
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                    {(["HIGH", "MEDIUM", "LOW"] as const).map((lvl) => (
                      <div key={lvl} className="rounded-xl bg-white/45 dark:bg-white/[0.06] p-2">
                        <div className="text-[10px] font-bold text-slate-600 dark:text-zinc-400">{lvl}</div>
                        <div className="text-lg font-bold ios-num text-slate-950 dark:text-white">
                          {(riskScoring.account_risk_distribution[lvl] || 0).toLocaleString("en-US")}
                        </div>
                      </div>
                    ))}
                  </div>
                </LiquidGlassCard>

                <LiquidGlassCard variant="emerald" className="rounded-2xl p-5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-300">
                    Customer-Level Risk Scoring (Fn 74, 75)
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                    {(["HIGH", "MEDIUM", "LOW"] as const).map((lvl) => (
                      <div key={lvl} className="rounded-xl bg-white/45 dark:bg-white/[0.06] p-2">
                        <div className="text-[10px] font-bold text-slate-600 dark:text-zinc-400">{lvl}</div>
                        <div className="text-lg font-bold ios-num text-slate-950 dark:text-white">
                          {(riskScoring.customer_risk_distribution[lvl] || 0).toLocaleString("en-US")}
                        </div>
                      </div>
                    ))}
                  </div>
                </LiquidGlassCard>
              </div>

              {/* Interactive Automated Rule Evaluator Console (Functions 71-75) */}
              <div className="liquid-glass rounded-2xl p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                      Live Automated Rule Evaluation &amp; Multi-Level Risk Scorer
                    </h3>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      Thresholds: HIGH ({riskScoring.thresholds.HIGH}) • MEDIUM ({riskScoring.thresholds.MEDIUM}) • LOW (
                      {riskScoring.thresholds.LOW})
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="rounded-xl p-4 bg-white/35 dark:bg-white/[0.03] border border-white/60 dark:border-white/10 space-y-3">
                    <div className="text-xs font-semibold text-slate-900 dark:text-white">
                      Option A: Simulate / Evaluate Incoming Transaction Against All 8 Rules
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                      <input
                        type="text"
                        value={simAccount}
                        onChange={(e) => setSimAccount(e.target.value)}
                        placeholder="Account ID"
                        className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-lg px-2.5 py-1.5 font-mono text-xs"
                      />
                      <input
                        type="number"
                        value={simAmount}
                        onChange={(e) => setSimAmount(e.target.value)}
                        placeholder="Amount ($)"
                        className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-lg px-2.5 py-1.5 ios-num text-xs"
                      />
                      <select
                        value={simType}
                        onChange={(e) => setSimType(e.target.value)}
                        className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-lg px-2.5 py-1.5 text-xs"
                      >
                        <option value="WIRE_OUT">WIRE_OUT</option>
                        <option value="P2P_TRANSFER_OUT">P2P_TRANSFER_OUT</option>
                        <option value="MERCHANT_PURCHASE">MERCHANT_PURCHASE</option>
                        <option value="ATM_WITHDRAWAL">ATM_WITHDRAWAL</option>
                      </select>
                      <input
                        type="text"
                        value={simCountry}
                        onChange={(e) => setSimCountry(e.target.value)}
                        placeholder="Country (e.g. CY)"
                        className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-lg px-2.5 py-1.5 font-mono text-xs"
                      />
                      <input
                        type="text"
                        value={simDevice}
                        onChange={(e) => setSimDevice(e.target.value)}
                        placeholder="Device ID (opt)"
                        className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-lg px-2.5 py-1.5 font-mono text-xs"
                      />
                      <input
                        type="text"
                        value={simMerchant}
                        onChange={(e) => setSimMerchant(e.target.value)}
                        placeholder="Merchant ID (opt)"
                        className="bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-lg px-2.5 py-1.5 font-mono text-xs"
                      />
                    </div>
                    <button
                      type="button"
                      disabled={evalLoading}
                      onClick={() =>
                        runLiveEvaluation({
                          payload: {
                            account_id: simAccount,
                            amount: Number(simAmount) || 0,
                            txn_type: simType,
                            direction: "DEBIT",
                            counterparty_country: simCountry || "US",
                            device_id: simDevice || null,
                            merchant_id: simMerchant || null,
                          },
                        })
                      }
                      className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-gradient-to-r from-azure-500 to-azure-600 text-white text-xs font-semibold shadow-sm"
                    >
                      <Play className="w-3.5 h-3.5" /> Evaluate Rules &amp; Compute Scores
                    </button>
                  </div>

                  <div className="rounded-xl p-4 bg-white/35 dark:bg-white/[0.03] border border-white/60 dark:border-white/10 space-y-3">
                    <div className="text-xs font-semibold text-slate-900 dark:text-white">
                      Option B: Evaluate Stored Transaction by ID
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={simTxnId}
                        onChange={(e) => setSimTxnId(e.target.value)}
                        placeholder="e.g. TXN-2026-00009996"
                        className="flex-1 bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-lg px-3 py-1.5 font-mono text-xs"
                      />
                      <button
                        type="button"
                        disabled={evalLoading || !simTxnId.trim()}
                        onClick={() => runLiveEvaluation({ transaction_id: simTxnId.trim() })}
                        className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-azure-600 text-white text-xs font-semibold disabled:opacity-40"
                      >
                        Evaluate TXN
                      </button>
                    </div>
                    {evalError && <div className="text-xs text-rose-600 dark:text-rose-400">{evalError}</div>}
                    {liveEval && (
                      <div className="rounded-xl p-3 bg-white/50 dark:bg-black/40 border border-white/70 dark:border-white/10 text-xs space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={tierVariant(liveEval.transaction_risk_level)}>
                            TXN: {liveEval.transaction_risk_score.toFixed(1)} ({liveEval.transaction_risk_level})
                          </Badge>
                          <Badge variant={tierVariant(liveEval.account_risk.risk_level)}>
                            ACCT: {liveEval.account_risk.risk_score.toFixed(1)} ({liveEval.account_risk.risk_level})
                          </Badge>
                          <Badge variant={tierVariant(liveEval.customer_risk.risk_level)}>
                            CUST: {liveEval.customer_risk.risk_score.toFixed(1)} ({liveEval.customer_risk.risk_level})
                          </Badge>
                          <span className="text-[11px] font-mono text-slate-600 dark:text-zinc-400">
                            {liveEval.triggered_rule_count} rule(s) triggered
                          </span>
                        </div>
                        {liveEval.flag_reasons.map((r, i) => (
                          <div key={i} className="text-[11px] text-slate-800 dark:text-zinc-200">
                            • {r}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Top Scored Accounts & Customers */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="liquid-glass rounded-2xl overflow-hidden">
                  <div className="px-5 py-3 border-b border-white/50 dark:border-white/10 text-sm font-semibold text-slate-950 dark:text-white">
                    Top Account-Level Risk Scores
                  </div>
                  <div ref={topAcctMag.containerRef} onMouseLeave={topAcctMag.onContainerLeave} className="relative overflow-x-auto">
                    {topAcctMag.lensElement}
                    <table className="w-full text-left border-collapse text-xs">
                      <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                        {riskScoring.top_risk_accounts.map((a) => (
                          <tr
                            key={a.account_id}
                            onMouseEnter={(e) => topAcctMag.onRowEnter(e.currentTarget)}
                            onClick={() => onOpenAccount(a.account_id)}
                            className="liquid-row-magnify cursor-pointer"
                          >
                            <td className="py-2.5 px-4 font-mono font-semibold text-azure-700 dark:text-white">
                              {a.account_id}
                            </td>
                            <td className="py-2.5 px-3 text-slate-700 dark:text-zinc-300">{a.customer_name}</td>
                            <td className="py-2.5 px-3 ios-num">{a.alert_count} alerts</td>
                            <td className="py-2.5 px-4 text-right">
                              <Badge variant={tierVariant(a.risk_level)}>
                                {a.risk_level} ({a.account_risk_score.toFixed(1)})
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="liquid-glass rounded-2xl overflow-hidden">
                  <div className="px-5 py-3 border-b border-white/50 dark:border-white/10 text-sm font-semibold text-slate-950 dark:text-white">
                    Top Customer-Level Risk Scores
                  </div>
                  <div ref={topCustMag.containerRef} onMouseLeave={topCustMag.onContainerLeave} className="relative overflow-x-auto">
                    {topCustMag.lensElement}
                    <table className="w-full text-left border-collapse text-xs">
                      <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                        {riskScoring.top_risk_customers.map((c) => (
                          <tr
                            key={c.customer_id}
                            onMouseEnter={(e) => topCustMag.onRowEnter(e.currentTarget)}
                            onClick={() => onOpenCustomer(c.customer_id)}
                            className="liquid-row-magnify cursor-pointer"
                          >
                            <td className="py-2.5 px-4 font-mono font-semibold text-azure-700 dark:text-white">
                              {c.customer_id}
                            </td>
                            <td className="py-2.5 px-3 text-slate-700 dark:text-zinc-300">{c.full_name}</td>
                            <td className="py-2.5 px-3 ios-num">{c.suspicious_accts} susp accts</td>
                            <td className="py-2.5 px-4 text-right">
                              <Badge variant={tierVariant(c.risk_level)}>
                                {c.risk_level} ({c.customer_risk_score.toFixed(1)})
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* Functions 79-84: Behavioral & Network Anomaly Scanners */}
              {riskScoring.anomaly_detectors && (
                <div className="liquid-glass rounded-2xl p-5 space-y-3">
                  <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                    Behavioral &amp; Network Anomaly Scanners (Functions 79–84)
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {riskScoring.anomaly_detectors.map((det) => (
                      <button
                        key={det.function_num}
                        type="button"
                        onClick={() => {
                          onFiltersChange({ ...filters, pattern: det.key });
                          setSubMode("EXPLORER");
                        }}
                        className="text-left rounded-2xl p-3.5 bg-white/45 dark:bg-white/[0.04] border border-white/75 dark:border-white/10 hover:bg-white/70 dark:hover:bg-white/10 transition"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-bold text-slate-950 dark:text-white">{det.name}</span>
                          <Badge variant={det.alert_count > 0 ? "HIGH" : "NEUTRAL"}>
                            {det.alert_count} alert(s)
                          </Badge>
                        </div>
                        <div className="text-[11px] text-slate-600 dark:text-zinc-400 mt-1">{det.description}</div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1">
                          {det.rules.map((r) => (
                            <Badge key={r} variant="BLUE">
                              {r}
                            </Badge>
                          ))}
                          {det.extra_metric && (
                            <span className="text-[10.5px] font-mono text-azure-700 dark:text-sky-300">
                              {det.extra_metric}
                            </span>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Functions 85-88: Ledger & Reference Integrity Detectors */}
              {riskScoring.integrity_detectors && (
                <div className="liquid-glass rounded-2xl p-5 space-y-3">
                  <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                    Transaction &amp; Ledger Integrity Detectors (Functions 85–88)
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                    {[
                      {
                        label: "Closed Account Txns (Fn 85)",
                        bucket: riskScoring.integrity_detectors.closed_account_txns,
                        idKey: "transaction_id",
                        subKey: "account_id",
                      },
                      {
                        label: "Negative Balance No OD (Fn 86)",
                        bucket: riskScoring.integrity_detectors.negative_balance_no_overdraft,
                        idKey: "transaction_id",
                        subKey: "account_id",
                      },
                      {
                        label: "Mismatched Transfer Amounts (Fn 87)",
                        bucket: riskScoring.integrity_detectors.mismatched_transfer_amounts,
                        idKey: "transfer_id",
                        subKey: "source_account_id",
                      },
                      {
                        label: "Missing / Inconsistent Refs (Fn 88)",
                        bucket: riskScoring.integrity_detectors.missing_or_inconsistent_references,
                        idKey: "record_id",
                        subKey: "ref_issue",
                      },
                    ].map((card) => (
                      <div
                        key={card.label}
                        className="rounded-2xl p-3.5 bg-white/45 dark:bg-white/[0.04] border border-white/75 dark:border-white/10 space-y-2"
                      >
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-semibold text-slate-900 dark:text-white">{card.label}</span>
                          <Badge variant={card.bucket.count > 0 ? "CRITICAL" : "LOW"}>{card.bucket.count}</Badge>
                        </div>
                        {card.bucket.items.slice(0, 3).map((it, idx) => {
                          const recId = String(it[card.idKey] || "");
                          const isTxn = recId.startsWith("TXN-");
                          return (
                            <div
                              key={`${recId}-${idx}`}
                              className="text-[11px] font-mono text-slate-600 dark:text-zinc-400 truncate"
                            >
                              {isTxn ? (
                                <button
                                  type="button"
                                  onClick={() => onSelectTransaction(recId)}
                                  className="text-azure-700 dark:text-sky-300 hover:underline font-semibold"
                                >
                                  {recId}
                                </button>
                              ) : (
                                <span className="font-semibold text-slate-800 dark:text-zinc-200">{recId}</span>
                              )}{" "}
                              • {String(it[card.subKey] || "")}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Functions 76, 89: Configured Rules & Live Re-Evaluation */}
              <div className="liquid-glass rounded-2xl overflow-hidden">
                <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                      Risk Rules Configuration &amp; Re-Evaluation (Functions 76, 89)
                    </h3>
                    <p className="text-xs text-slate-600 dark:text-zinc-400">
                      Adjust rule weights or active state (Admin role) and re-evaluate alerts with full score history tracking.
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={reevalBusy}
                    onClick={() => runFullReeval("ALL")}
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-gradient-to-r from-azure-500 to-azure-600 text-white text-xs font-semibold shadow-sm"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${reevalBusy ? "animate-spin" : ""}`} />
                    {reevalBusy ? "Re-Evaluating..." : "Re-Evaluate All Rules"}
                  </button>
                </div>
                {reevalMsg && (
                  <div className="px-5 py-2.5 bg-emerald-500/12 border-b border-white/40 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                    {reevalMsg}
                  </div>
                )}
                {evalError && (
                  <div className="px-5 py-2.5 bg-rose-500/12 border-b border-white/40 text-xs font-medium text-rose-700 dark:text-rose-300">
                    {evalError}
                  </div>
                )}
                {userRole && userRole !== "SYSTEM_ADMIN" && (
                  <div className="px-5 py-2 bg-amber-500/10 border-b border-white/40 text-[11px] text-amber-800 dark:text-amber-300">
                    Signed in as {userRole}: full re-evaluation is enabled; editing rule weights requires SYSTEM_ADMIN role.
                  </div>
                )}
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/35 text-[11px] font-semibold uppercase text-slate-700 dark:text-zinc-400">
                        <th className="py-2.5 px-4">Rule</th>
                        <th className="py-2.5 px-3">Condition</th>
                        <th className="py-2.5 px-3 text-right">Hits / Avg</th>
                        <th className="py-2.5 px-3 text-right">Weight (pts)</th>
                        <th className="py-2.5 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                      {riskScoring.rules_summary.map((r) => {
                        const weightVal = ruleWeights[r.rule_id] ?? r.base_weight;
                        return (
                          <tr key={r.rule_id}>
                            <td className="py-2.5 px-4">
                              <div className="font-mono font-bold text-slate-950 dark:text-white">{r.rule_id}</div>
                              <div className="font-medium text-slate-800 dark:text-zinc-200">{r.rule_name}</div>
                            </td>
                            <td className="py-2.5 px-3 text-slate-600 dark:text-zinc-400 max-w-md">{r.threshold_desc}</td>
                            <td className="py-2.5 px-3 text-right ios-num">
                              {r.hit_count} • avg {r.avg_score.toFixed(1)}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <input
                                type="number"
                                min={1}
                                max={100}
                                value={weightVal}
                                onChange={(e) =>
                                  setRuleWeights((prev) => ({
                                    ...prev,
                                    [r.rule_id]: Number(e.target.value) || r.base_weight,
                                  }))
                                }
                                className="w-16 text-right bg-white/70 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-lg px-2 py-1 ios-num text-xs"
                              />
                            </td>
                            <td className="py-2.5 px-4 text-right space-x-1.5 whitespace-nowrap">
                              <button
                                type="button"
                                disabled={reevalBusy}
                                onClick={() => applyRuleUpdate(r.rule_id, weightVal, Boolean(r.is_active))}
                                className="px-2.5 py-1 rounded-full bg-azure-600 text-white text-[11px] font-semibold disabled:opacity-40"
                              >
                                Apply &amp; Re-Eval
                              </button>
                              <button
                                type="button"
                                disabled={reevalBusy}
                                onClick={() => applyRuleUpdate(r.rule_id, weightVal, !r.is_active)}
                                className="glass-pill px-2.5 py-1 rounded-full text-[11px] font-semibold hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
                              >
                                {r.is_active ? "Disable" : "Enable"}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Functions 78 & 90: Rule Execution Logs & Risk Score History */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="liquid-glass rounded-2xl p-5">
                  <h3 className="text-sm font-semibold text-slate-950 dark:text-white mb-3">
                    Rule Execution Results &amp; Timestamps (Function 78)
                  </h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto text-xs">
                    {(riskScoring.execution_runs || []).map((run) => (
                      <div
                        key={run.run_id}
                        className="rounded-xl p-3 bg-white/40 dark:bg-black/40 border border-white/60 dark:border-white/10"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono font-bold text-slate-950 dark:text-white">{run.run_id}</span>
                          <Badge variant="BLUE">{run.trigger_source}</Badge>
                        </div>
                        <div className="text-slate-700 dark:text-zinc-300 mt-1">{run.summary}</div>
                        <div className="ios-num text-[10.5px] text-slate-500 mt-1">
                          {run.executed_at} • By: {run.executed_by} • Avg Alert Score: {run.avg_score}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="liquid-glass rounded-2xl p-5">
                  <h3 className="text-sm font-semibold text-slate-950 dark:text-white mb-3">
                    Risk Score History &amp; Changes (Function 90)
                  </h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto text-xs">
                    {(riskScoring.score_history || []).map((h) => (
                      <div
                        key={h.history_id}
                        className="rounded-xl p-3 bg-white/40 dark:bg-black/40 border border-white/60 dark:border-white/10"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono font-bold text-slate-950 dark:text-white">
                            {h.entity_id} ({h.rule_id || "ENGINE"})
                          </span>
                          <Badge variant={tierVariant(h.new_level)}>
                            {h.prev_score.toFixed(1)} → {h.new_score.toFixed(1)} ({h.new_level})
                          </Badge>
                        </div>
                        <div className="text-slate-600 dark:text-zinc-400 mt-1">{h.reason}</div>
                        <div className="ios-num text-[10.5px] text-slate-500 mt-0.5">
                          {h.recorded_at} • Actor: {h.actor_id}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Functions 203-205, 218: Calibration Proposals & Ad-Hoc SQL-Safe Pattern Sandbox */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div className="liquid-glass rounded-2xl p-5 space-y-3 text-xs">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                      Staged Rule Calibration Proposals ({proposals.length})
                    </h3>
                  </div>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {proposals.map((p) => (
                      <div key={p.proposal_id} className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10 space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono font-bold text-slate-950 dark:text-white">{p.proposal_id} — {p.title}</span>
                          <Badge variant={p.status === "APPROVED" ? "LOW" : p.status === "REJECTED" ? "CRITICAL" : "HIGH"}>{p.status}</Badge>
                        </div>
                        <div className="text-[11px] font-mono text-slate-600 dark:text-zinc-400">
                          By {p.created_by} • Weights: {Object.entries(p.weights).slice(0, 4).map(([k, v]) => `${k}=${v}`).join(", ")}
                        </div>
                        {p.status === "PENDING_APPROVAL" && userRole === "SYSTEM_ADMIN" && (
                          <div className="flex gap-2 pt-1">
                            <button
                              type="button"
                              onClick={async () => {
                                await api.approveCalibrationProposal(p.proposal_id, "APPROVED");
                                const res = await api.calibrationProposals();
                                setProposals(res.items);
                                if (onRefreshScoring) await onRefreshScoring();
                              }}
                              className="px-3 py-1 rounded-full bg-emerald-600 text-white font-semibold hover:bg-emerald-500 transition"
                            >
                              Approve &amp; Apply
                            </button>
                            <button
                              type="button"
                              onClick={async () => {
                                await api.approveCalibrationProposal(p.proposal_id, "REJECTED");
                                const res = await api.calibrationProposals();
                                setProposals(res.items);
                              }}
                              className="px-3 py-1 rounded-full bg-rose-600 text-white font-semibold hover:bg-rose-500 transition"
                            >
                              Reject
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                    {proposals.length === 0 && (
                      <div className="text-slate-500 dark:text-zinc-400 py-4 text-center">
                        No calibration proposals staged yet. Simulate weights in Evaluation &rarr; What-If Sandbox to stage one.
                      </div>
                    )}
                  </div>
                </div>

                <div className="liquid-glass rounded-2xl p-5 space-y-3 text-xs">
                  <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                    Ad-Hoc Ledger Pattern Sandbox (Non-Mutating)
                  </h3>
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      const res = await api.sandboxPattern({
                        min_amount: sbMinAmt ? Number(sbMinAmt) : undefined,
                        channel: sbChannel,
                        country: sbCountry || "ALL",
                        limit: 20,
                      });
                      setSbResult(res);
                    }}
                    className="flex flex-wrap gap-2"
                  >
                    <input type="number" value={sbMinAmt} onChange={(e) => setSbMinAmt(e.target.value)} placeholder="Min $" className="w-24 px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 ios-num" />
                    <select value={sbChannel} onChange={(e) => setSbChannel(e.target.value)} className="px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15">
                      <option value="ALL" className="bg-white dark:bg-zinc-900">All Channels</option>
                      <option value="ONLINE" className="bg-white dark:bg-zinc-900">ONLINE</option>
                      <option value="WIRE" className="bg-white dark:bg-zinc-900">WIRE</option>
                      <option value="ATM" className="bg-white dark:bg-zinc-900">ATM</option>
                      <option value="POS" className="bg-white dark:bg-zinc-900">POS</option>
                    </select>
                    <input type="text" value={sbCountry} onChange={(e) => setSbCountry(e.target.value)} placeholder="Country (ALL/CY)" className="w-28 px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15" />
                    <button type="submit" className="px-3.5 py-1.5 rounded-full bg-azure-600 text-white font-semibold hover:bg-azure-500 transition">Test Pattern</button>
                  </form>
                  {sbResult && (
                    <div className="space-y-2">
                      <div className="font-mono text-[11px] text-azure-700 dark:text-sky-300 font-bold">
                        Matched {sbResult.matched_txns.toLocaleString()} txns • ${sbResult.matched_volume.toLocaleString()} across {sbResult.distinct_accounts} accounts
                      </div>
                      <div className="space-y-1 max-h-40 overflow-y-auto">
                        {sbResult.items.slice(0, 8).map((it) => (
                          <div key={String(it.transaction_id)} className="flex justify-between px-2.5 py-1 rounded-lg bg-white/20 dark:bg-white/[0.04]">
                            <span className="font-mono">{String(it.transaction_id)} ({String(it.channel)})</span>
                            <span className="ios-num font-bold">${Number(it.amount).toLocaleString()}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {subMode === "EXPLORER" && (
        <div className="liquid-glass rounded-2xl overflow-hidden">
          {/* Pattern Detection Pills (Functions 64-69) */}
          <div className="px-5 pt-3.5 pb-2.5 border-b border-white/40 dark:border-white/10 flex flex-wrap items-center gap-1.5">
            {PATTERN_PILLS.map((pill) => {
              const active = filters.pattern === pill.id;
              return (
                <button
                  key={pill.id}
                  type="button"
                  onClick={() => onFiltersChange({ ...filters, pattern: pill.id })}
                  className={`px-3 py-1 rounded-full text-[11px] font-semibold transition ${
                    active
                      ? "bg-azure-600 text-white shadow-sm"
                      : "bg-white/55 dark:bg-white/[0.06] text-slate-700 dark:text-zinc-300 hover:bg-white dark:hover:bg-white/15"
                  }`}
                >
                  {pill.label}
                </button>
              );
            })}
          </div>

          {/* Search, Filters & Sort Controls (Functions 49-51) */}
          <div className="px-5 py-3 border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/30 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-500 dark:text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="search"
                  value={filters.search}
                  onChange={(e) => onFiltersChange({ ...filters, search: e.target.value })}
                  placeholder="Txn ID, Account ID, Customer ID, Merchant ID..."
                  className="pl-8 pr-3 py-1.5 w-72 bg-white/60 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 focus:outline-none"
                />
              </div>

              <input
                type="date"
                value={filters.start_date}
                onChange={(e) => onFiltersChange({ ...filters, start_date: e.target.value })}
                className="glass-pill rounded-full px-2.5 py-1.5 text-xs ios-num"
                aria-label="Start Date"
              />
              <input
                type="date"
                value={filters.end_date}
                onChange={(e) => onFiltersChange({ ...filters, end_date: e.target.value })}
                className="glass-pill rounded-full px-2.5 py-1.5 text-xs ios-num"
                aria-label="End Date"
              />

              <input
                type="number"
                min="0"
                placeholder="Min $"
                value={filters.min_amount}
                onChange={(e) => onFiltersChange({ ...filters, min_amount: e.target.value })}
                className="w-24 glass-pill rounded-full px-3 py-1.5 text-xs ios-num"
              />
              <input
                type="number"
                min="0"
                placeholder="Max $"
                value={filters.max_amount}
                onChange={(e) => onFiltersChange({ ...filters, max_amount: e.target.value })}
                className="w-24 glass-pill rounded-full px-3 py-1.5 text-xs ios-num"
              />

              <select
                value={filters.txn_type}
                onChange={(e) => onFiltersChange({ ...filters, txn_type: e.target.value })}
                className="glass-pill rounded-full px-2.5 py-1.5 text-xs font-medium"
              >
                <option value="ALL">All Types</option>
                <option value="MERCHANT_PURCHASE">MERCHANT_PURCHASE</option>
                <option value="P2P_TRANSFER_OUT">P2P_TRANSFER_OUT</option>
                <option value="P2P_TRANSFER_IN">P2P_TRANSFER_IN</option>
                <option value="INTERNAL_TRANSFER_OUT">INTERNAL_TRANSFER_OUT</option>
                <option value="INTERNAL_TRANSFER_IN">INTERNAL_TRANSFER_IN</option>
                <option value="WIRE_OUT">WIRE_OUT</option>
                <option value="WIRE_IN">WIRE_IN</option>
                <option value="PAYROLL_CREDIT">PAYROLL_CREDIT</option>
                <option value="ATM_WITHDRAWAL">ATM_WITHDRAWAL</option>
              </select>

              <select
                value={filters.risk_level}
                onChange={(e) => onFiltersChange({ ...filters, risk_level: e.target.value })}
                className="glass-pill rounded-full px-2.5 py-1.5 text-xs font-medium"
              >
                <option value="ALL">All Risk Levels</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>

              <select
                value={filters.status}
                onChange={(e) => onFiltersChange({ ...filters, status: e.target.value })}
                className="glass-pill rounded-full px-2.5 py-1.5 text-xs font-medium"
              >
                <option value="ALL">All Statuses</option>
                <option value="POSTED">POSTED</option>
                <option value="REVERSED">REVERSED</option>
                <option value="FAILED">FAILED</option>
              </select>

              {/* Function 51: Sort By Amount / Timestamp / Risk Score */}
              <select
                value={filters.sort_by}
                onChange={(e) =>
                  onFiltersChange({
                    ...filters,
                    sort_by: e.target.value as TransactionFiltersState["sort_by"],
                  })
                }
                aria-label="Sort transactions by"
                className="glass-pill rounded-full px-2.5 py-1.5 text-xs font-semibold"
              >
                <option value="occurred_at">Sort: Timestamp</option>
                <option value="amount">Sort: Amount</option>
                <option value="risk_score">Sort: Risk Score</option>
              </select>

              <button
                type="button"
                onClick={() =>
                  onFiltersChange({
                    ...filters,
                    sort_dir: filters.sort_dir === "desc" ? "asc" : "desc",
                  })
                }
                className="inline-flex items-center gap-1 px-2.5 py-1.5 glass-pill rounded-full text-xs font-semibold"
              >
                <ArrowDownUp className="w-3 h-3" /> {filters.sort_dir.toUpperCase()}
              </button>
            </div>

            <div className="flex items-center gap-2 text-xs ios-num">
              <span className="font-semibold text-slate-600 dark:text-zinc-400">
                {total.toLocaleString("en-US")} txns • Page {page + 1}/{totalPages}
              </span>
            </div>
          </div>

          <div ref={rowMag.containerRef} onMouseLeave={rowMag.onContainerLeave} className="relative overflow-x-auto">
            {rowMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-3 px-4">Transaction ID</th>
                  <th
                    onClick={() => toggleSort("occurred_at")}
                    className="py-3 px-3 cursor-pointer hover:text-azure-700 dark:hover:text-white select-none"
                  >
                    Timestamp (UTC) {filters.sort_by === "occurred_at" ? (filters.sort_dir === "desc" ? "↓" : "↑") : ""}
                  </th>
                  <th className="py-3 px-3">Account / Customer</th>
                  <th className="py-3 px-3">Type / Pattern Signals</th>
                  <th className="py-3 px-3">Merchant / Location</th>
                  <th
                    onClick={() => toggleSort("amount")}
                    className="py-3 px-3 text-right cursor-pointer hover:text-azure-700 dark:hover:text-white select-none"
                  >
                    Amount {filters.sort_by === "amount" ? (filters.sort_dir === "desc" ? "↓" : "↑") : ""}
                  </th>
                  <th className="py-3 px-3 text-right">Balance After</th>
                  <th
                    onClick={() => toggleSort("risk_score")}
                    className="py-3 px-4 text-right cursor-pointer hover:text-azure-700 dark:hover:text-white select-none"
                  >
                    Risk / Rules {filters.sort_by === "risk_score" ? (filters.sort_dir === "desc" ? "↓" : "↑") : ""}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {transactions.map((tx) => (
                  <tr
                    key={tx.transaction_id}
                    onMouseEnter={(e) => rowMag.onRowEnter(e.currentTarget)}
                    onClick={() => onSelectTransaction(tx.transaction_id)}
                    className="liquid-row-magnify cursor-pointer"
                  >
                    <td className="py-2.5 px-4 font-mono font-semibold text-azure-700 dark:text-white">
                      {tx.transaction_id}
                    </td>
                    <td className="py-2.5 px-3 ios-num text-slate-600 dark:text-zinc-400">{tx.occurred_at}</td>
                    <td className="py-2.5 px-3">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenAccount(tx.account_id);
                        }}
                        className="font-mono font-semibold text-azure-700 dark:text-white hover:underline block"
                      >
                        {tx.account_id}
                      </button>
                      <div className="text-[11px] text-slate-500 dark:text-zinc-400">
                        {tx.customer_name} ({tx.customer_id})
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex flex-wrap items-center gap-1">
                        <Badge variant="NEUTRAL">{tx.txn_type}</Badge>
                        {(tx.pattern_flags || []).map((pf) => (
                          <Badge key={pf} variant={pf === "VALIDATION_EXCEPTION" ? "CRITICAL" : "HIGH"}>
                            {PATTERN_BADGE_LABEL[pf] || pf}
                          </Badge>
                        ))}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-zinc-500 mt-0.5">
                        {tx.channel} {tx.device_id ? `• ${tx.device_id}` : ""}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-slate-700 dark:text-zinc-300">
                      {tx.merchant_name ? (
                        <>
                          <div>{tx.merchant_name}</div>
                          <div className="font-mono text-[10.5px] text-slate-500">
                            {tx.merchant_id} • {tx.counterparty_country}
                          </div>
                        </>
                      ) : (
                        <>
                          <div>{tx.reference_note}</div>
                          <div className="font-mono text-[10.5px] text-slate-500">Country: {tx.counterparty_country}</div>
                        </>
                      )}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right font-semibold ${
                        tx.direction === "CREDIT" ? "text-emerald-600 dark:text-emerald-400" : "text-slate-950 dark:text-white"
                      }`}
                    >
                      <IosAmount value={tx.direction === "CREDIT" ? tx.amount : -tx.amount} showPlus={tx.direction === "CREDIT"} />
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num">
                      <IosAmount value={tx.balance_after} />
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <div className="inline-flex flex-wrap justify-end items-center gap-1">
                        <Badge variant={tierVariant(tx.risk_level)}>
                          {tx.risk_level} {tx.risk_score > 0 ? `(${tx.risk_score.toFixed(0)})` : ""}
                        </Badge>
                        {(tx.triggered_rules || []).map((rid) => (
                          <Badge key={rid} variant="BLUE">
                            {rid}
                          </Badge>
                        ))}
                      </div>
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
            unitLabel="txns"
          />
        </div>
      )}
    </div>
  );
};
