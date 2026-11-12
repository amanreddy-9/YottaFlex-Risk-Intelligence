import React, { useEffect, useState } from "react";
import { ArrowLeft, ArrowLeftRight, Download, Link2, Search, ShieldAlert, Users } from "lucide-react";
import { api, downloadExport } from "../api/client";
import type {
  AccountBurstProfile,
  AccountControlItem,
  AccountDetail,
  AccountListItem,
  AccountVelocityResponse,
} from "../types/workbench";
import { Badge, IosAmount, tierVariant } from "./Badge";
import { GlassPagination } from "./GlassPagination";
import { LiquidGlassCard, useRowGlassMagnifier } from "./LiquidGlassSurface";

interface AccountsViewProps {
  accounts: AccountListItem[];
  total: number;
  page: number;
  pageSize: number;
  search: string;
  status: string;
  dormantReactivated: boolean;
  selectedDetail: AccountDetail | null;
  onSearchChange: (v: string) => void;
  onStatusChange: (v: string) => void;
  onDormantChange: (v: boolean) => void;
  onPageChange: (nextPage: number) => void;
  onPageSizeChange: (nextSize: number) => void;
  onSelectAccount: (accountId: string) => void;
  onCloseDetail: () => void;
  onOpenCustomer: (customerId: string) => void;
  onOpenTransaction: (transactionId: string) => void;
}

export const AccountsView: React.FC<AccountsViewProps> = ({
  accounts,
  total,
  page,
  pageSize,
  search,
  status,
  dormantReactivated,
  selectedDetail,
  onSearchChange,
  onStatusChange,
  onDormantChange,
  onPageChange,
  onPageSizeChange,
  onSelectAccount,
  onCloseDetail,
  onOpenCustomer,
  onOpenTransaction,
}) => {
  const listMag = useRowGlassMagnifier();
  const txnMag = useRowGlassMagnifier();
  const trlMag = useRowGlassMagnifier();
  const [ctrl, setCtrl] = useState<AccountControlItem | null>(null);
  const [ctrlStatus, setCtrlStatus] = useState<"NONE" | "DEBIT_HOLD" | "POST_NO_DEBITS" | "FULL_FREEZE">("NONE");
  const [ctrlReason, setCtrlReason] = useState("");
  const [ctrlMsg, setCtrlMsg] = useState<string | null>(null);
  const [velocity, setVelocity] = useState<AccountVelocityResponse | null>(null);
  const [burstProfile, setBurstProfile] = useState<AccountBurstProfile | null>(null);
  const [transferMatrix, setTransferMatrix] = useState<Array<Record<string, unknown>>>([]);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    const aid = selectedDetail?.account.account_id;
    setCtrlMsg(null);
    if (!aid) {
      setCtrl(null);
      setVelocity(null);
      setBurstProfile(null);
      setTransferMatrix([]);
      return;
    }
    api
      .accountControl(aid)
      .then((res) => {
        setCtrl(res);
        setCtrlStatus(res.control_status);
        setCtrlReason(res.reason || "");
      })
      .catch(() => {});
    api.accountVelocity(aid).then(setVelocity).catch(() => setVelocity(null));
    api.accountBurstProfile(aid).then(setBurstProfile).catch(() => setBurstProfile(null));
    api.accountTransferMatrix(aid).then((r) => setTransferMatrix(r.counterparties)).catch(() => setTransferMatrix([]));
  }, [selectedDetail?.account.account_id]);

  if (selectedDetail) {
    const a = selectedDetail.account;
    return (
      <div className="space-y-5">
        {/* Account Banner (Functions 37, 39, 40, 44, 45) */}
        <div className="liquid-glass rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="font-mono text-lg font-bold text-slate-950 dark:text-white">{a.account_id}</h2>
              <Badge variant="BLUE">{a.account_type}</Badge>
              <Badge variant={a.status === "ACTIVE" ? "LOW" : a.status === "CLOSED" ? "CRITICAL" : "HIGH"}>
                {a.status}
              </Badge>
              {selectedDetail.is_dormant_reactivated && (
                <Badge variant="CRITICAL">DORMANT REACTIVATED</Badge>
              )}
              <Badge variant={selectedDetail.account_risk_score >= 60 ? "CRITICAL" : "HIGH"}>
                ACCOUNT RISK: {selectedDetail.account_risk_score.toFixed(1)}
              </Badge>
            </div>
            <div className="mt-1.5 text-xs font-mono text-slate-600 dark:text-zinc-400">
              Opened: {a.opened_at} • Last Activity: {selectedDetail.last_activity_at || "None"} • Overdraft:{" "}
              {a.overdraft_allowed ? `Allowed ($${a.overdraft_limit})` : "Disabled"}
            </div>
          </div>

          <button
            type="button"
            onClick={onCloseDetail}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 glass-pill rounded-full text-xs font-semibold"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Accounts
          </button>
        </div>

        {/* Balance Hero + Holders (Fn 38, 39) + Lifecycle History (Fn 47) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <LiquidGlassCard variant="hero" className="lg:col-span-4 rounded-2xl p-5 text-white">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-white/85">
              Current Reconciled Balance
            </div>
            <div className="mt-2 text-3xl font-bold text-white">
              <IosAmount value={a.current_balance} />
            </div>
            <div className="mt-3 pt-3 border-t border-white/25 flex justify-between text-xs text-white/85">
              <span>Opening Balance</span>
              <IosAmount value={a.opening_balance} />
            </div>
            <div className="mt-1 flex justify-between text-xs text-white/85">
              <span>Total Ledger Txns</span>
              <span className="ios-num font-bold">{selectedDetail.total_transactions.toLocaleString("en-US")}</span>
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard className="lg:col-span-4 rounded-2xl p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white mb-3">
              <Users className="w-4 h-4 text-azure-600 dark:text-white" />
              <span>Account Holders ({selectedDetail.holders.length})</span>
            </div>
            <div className="space-y-2.5 text-xs">
              {selectedDetail.holders.map((h) => (
                <button
                  key={`${h.customer_id}-${h.ownership_role}`}
                  type="button"
                  onClick={() => onOpenCustomer(h.customer_id)}
                  className="w-full text-left rounded-xl bg-white/45 dark:bg-black/45 border border-white/65 dark:border-white/10 p-3 hover:bg-white/70 dark:hover:bg-zinc-900 transition"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-950 dark:text-white">{h.full_name}</span>
                    <Badge variant="BLUE">
                      {h.ownership_role} ({h.ownership_pct}%)
                    </Badge>
                  </div>
                  <div className="font-mono text-[11px] text-slate-600 dark:text-zinc-400 mt-0.5">
                    {h.customer_id} • {h.kyc_tier} KYC • {h.email}
                  </div>
                </button>
              ))}
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard className="lg:col-span-4 rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white mb-3">
              Account Lifecycle &amp; Status History
            </h3>
            <div className="space-y-3 max-h-48 overflow-y-auto pr-1 text-xs">
              {selectedDetail.lifecycle_events.map((ev) => (
                <div key={ev.event_id} className="relative pl-4 border-l-2 border-white/60 dark:border-zinc-700">
                  <span className="w-2 h-2 rounded-full bg-azure-600 dark:bg-white absolute -left-[5px] top-1.5" />
                  <div className="font-semibold text-slate-950 dark:text-white">
                    {ev.prev_status || "OPENED"} &rarr; {ev.new_status}
                  </div>
                  <div className="text-[11px] text-slate-600 dark:text-zinc-400">
                    {ev.reason} (actor: {ev.actor_id})
                  </div>
                  <div className="ios-num text-[10.5px] text-slate-500 dark:text-zinc-500">{ev.effective_at}</div>
                </div>
              ))}
            </div>
          </LiquidGlassCard>
        </div>

        {/* Functions 184, 185, 199: Account Controls (Hold/Freeze) & Daily Cashflow Velocity */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Operational Account Control</h3>
              <Badge variant={ctrl?.control_status && ctrl.control_status !== "NONE" ? "CRITICAL" : "LOW"}>
                {ctrl?.control_status || "NONE"}
              </Badge>
            </div>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  const res = await api.setAccountControl(a.account_id, {
                    control_status: ctrlStatus,
                    reason: ctrlReason || `Applied ${ctrlStatus}`,
                  });
                  setCtrl(res);
                  setCtrlMsg(`Updated account control to ${res.control_status}.`);
                } catch (err) {
                  setCtrlMsg(err instanceof Error ? err.message : "Failed to set account control");
                }
              }}
              className="space-y-2.5"
            >
              <div className="flex gap-2">
                <select
                  value={ctrlStatus}
                  onChange={(e) => setCtrlStatus(e.target.value as typeof ctrlStatus)}
                  className="px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white"
                >
                  <option value="NONE" className="bg-white dark:bg-zinc-900">NONE (Unrestricted)</option>
                  <option value="DEBIT_HOLD" className="bg-white dark:bg-zinc-900">DEBIT_HOLD</option>
                  <option value="POST_NO_DEBITS" className="bg-white dark:bg-zinc-900">POST_NO_DEBITS</option>
                  <option value="FULL_FREEZE" className="bg-white dark:bg-zinc-900">FULL_FREEZE (Reviewer/Admin)</option>
                </select>
                <button type="submit" className="px-3.5 py-1.5 rounded-full bg-azure-600 text-white font-semibold hover:bg-azure-500 transition">
                  Apply Control
                </button>
              </div>
              <input
                type="text"
                value={ctrlReason}
                onChange={(e) => setCtrlReason(e.target.value)}
                placeholder="Restriction reason / SAR reference..."
                className="w-full px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white placeholder:text-slate-500"
              />
            </form>
            {ctrlMsg && <div className="text-azure-700 dark:text-sky-300 font-semibold">{ctrlMsg}</div>}
          </div>

          <div className="lg:col-span-7 liquid-glass rounded-2xl p-5 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Daily Cashflow Velocity (Credits vs. Debits)</h3>
              <span className="ios-num text-slate-500 dark:text-zinc-400">{velocity?.buckets.length ?? 0} active days</span>
            </div>
            {velocity && velocity.buckets.length > 0 ? (
              <div className="flex items-end gap-1 h-24 pt-2 overflow-x-auto">
                {(() => {
                  const maxVal = Math.max(1, ...velocity.buckets.map((b) => Math.max(b.credits, b.debits)));
                  return velocity.buckets.slice(-30).map((b) => (
                    <div key={b.day} title={`${b.day}\nCredits: $${b.credits.toLocaleString()}\nDebits: $${b.debits.toLocaleString()}`} className="flex-1 min-w-[8px] flex items-end gap-[1px] h-full">
                      <div className="w-1/2 rounded-t bg-emerald-500/75" style={{ height: `${Math.max(4, (b.credits / maxVal) * 100)}%` }} />
                      <div className="w-1/2 rounded-t bg-azure-500/75" style={{ height: `${Math.max(4, (b.debits / maxVal) * 100)}%` }} />
                    </div>
                  ));
                })()}
              </div>
            ) : (
              <div className="text-slate-500 py-6 text-center">No daily velocity buckets recorded.</div>
            )}
            {burstProfile && (
              <div className="pt-2 border-t border-white/40 dark:border-white/10 flex flex-wrap items-center justify-between gap-2 text-[11px] ios-num">
                <span>15m bursts: <strong>{burstProfile.rapid_under_15m}</strong></span>
                <span>60m bursts: <strong>{burstProfile.rapid_under_60m}</strong></span>
                <span>Night txns: <strong>{burstProfile.night_window_pct}%</strong></span>
                <span>Round-$: <strong>{burstProfile.round_dollar_pct}%</strong></span>
                <span>Counterparties: <strong>{transferMatrix.length}</strong></span>
              </div>
            )}
          </div>
        </div>

        {/* Linked Accounts (Fn 43) & Suspicious Activities (Fn 46) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex items-center gap-2">
              <Link2 className="w-4 h-4 text-azure-600 dark:text-white" />
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Linked Accounts (Common Owner / Transfer Relationships)
              </h3>
            </div>
            <div className="p-4 space-y-2 max-h-64 overflow-y-auto text-xs">
              {selectedDetail.linked_accounts.length === 0 ? (
                <div className="text-slate-500 dark:text-zinc-400">No linked accounts found.</div>
              ) : (
                selectedDetail.linked_accounts.map((la) => (
                  <button
                    key={`${la.account_id}-${la.link_relation}`}
                    type="button"
                    onClick={() => onSelectAccount(la.account_id)}
                    className="w-full text-left rounded-xl bg-white/40 dark:bg-black/40 border border-white/60 dark:border-white/10 p-3 flex items-center justify-between hover:bg-white/70 dark:hover:bg-zinc-900 transition"
                  >
                    <div>
                      <div className="font-mono font-semibold text-azure-700 dark:text-white">{la.account_id}</div>
                      <div className="text-[11px] text-slate-600 dark:text-zinc-400">
                        Owner: {la.owner_name} • Balance: <IosAmount value={la.current_balance} />
                      </div>
                    </div>
                    <Badge variant="BLUE">{la.link_relation}</Badge>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-600 dark:text-rose-400" />
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Account Suspicious Activities &amp; Alerts ({selectedDetail.alerts.length})
              </h3>
            </div>
            <div className="p-4 space-y-2 max-h-64 overflow-y-auto text-xs">
              {selectedDetail.alerts.length === 0 ? (
                <div className="text-slate-500 dark:text-zinc-400">No suspicious alerts on this account.</div>
              ) : (
                selectedDetail.alerts.map((al) => (
                  <div key={al.alert_id} className="rounded-xl bg-white/40 dark:bg-black/40 border border-white/60 dark:border-white/10 p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-semibold text-slate-950 dark:text-white">
                        {al.alert_id} • {al.rule_id}
                      </span>
                      <Badge variant={tierVariant(al.severity)}>
                        {al.severity} ({al.risk_score.toFixed(1)})
                      </Badge>
                    </div>
                    <div className="text-[11px] text-slate-700 dark:text-zinc-300 mt-1">{al.explanation_summary}</div>
                    <div className="ios-num text-[10.5px] text-slate-500 dark:text-zinc-500 mt-0.5">{al.created_at}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Incoming & Outgoing Transfers (Fn 42) */}
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex items-center gap-2">
            <ArrowLeftRight className="w-4 h-4 text-azure-600 dark:text-white" />
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Incoming &amp; Outgoing Transfers ({selectedDetail.transfers.length})
            </h3>
          </div>
          <div ref={trlMag.containerRef} onMouseLeave={trlMag.onContainerLeave} className="relative overflow-x-auto max-h-64">
            {trlMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Transfer ID</th>
                  <th className="py-2.5 px-3">Direction</th>
                  <th className="py-2.5 px-3">Counterparty Account</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-4">Initiated At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {selectedDetail.transfers.map((tr) => (
                  <tr
                    key={tr.transfer_id}
                    onMouseEnter={(e) => trlMag.onRowEnter(e.currentTarget)}
                    onClick={() => onSelectAccount(tr.counterparty_account_id)}
                    className="liquid-row-magnify cursor-pointer"
                  >
                    <td className="py-2.5 px-4 font-mono font-semibold text-slate-950 dark:text-white">{tr.transfer_id}</td>
                    <td className="py-2.5 px-3">
                      <Badge variant={tr.transfer_direction === "INCOMING" ? "LOW" : "HIGH"}>
                        {tr.transfer_direction}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-azure-700 dark:text-white">{tr.counterparty_account_id}</td>
                    <td className="py-2.5 px-3 text-right font-semibold">
                      <IosAmount value={tr.transfer_amount} />
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant={tr.status === "SETTLED" ? "LOW" : "CRITICAL"}>{tr.status}</Badge>
                    </td>
                    <td className="py-2.5 px-4 ios-num text-slate-600 dark:text-zinc-400">{tr.initiated_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Account Transaction History (Fn 41) */}
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Account Transaction History ({selectedDetail.transactions.length} shown of {selectedDetail.total_transactions})
            </h3>
          </div>
          <div ref={txnMag.containerRef} onMouseLeave={txnMag.onContainerLeave} className="relative overflow-x-auto max-h-80">
            {txnMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 z-10 bg-white/45 dark:bg-black/65 backdrop-blur-md border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                <tr>
                  <th className="py-2.5 px-4">Transaction ID</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Note / Merchant</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3 text-right">Before</th>
                  <th className="py-2.5 px-4 text-right">After</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {selectedDetail.transactions
                  .slice()
                  .reverse()
                  .map((tx) => (
                    <tr
                      key={tx.transaction_id}
                      onMouseEnter={(e) => txnMag.onRowEnter(e.currentTarget)}
                      onClick={() => onOpenTransaction(tx.transaction_id)}
                      className="liquid-row-magnify cursor-pointer"
                    >
                      <td className="py-2.5 px-4 font-mono text-slate-950 dark:text-white">{tx.transaction_id}</td>
                      <td className="py-2.5 px-3 ios-num text-slate-600 dark:text-zinc-400">{tx.occurred_at}</td>
                      <td className="py-2.5 px-3">
                        <Badge variant="NEUTRAL">{tx.txn_type}</Badge>
                      </td>
                      <td className="py-2.5 px-3 text-slate-700 dark:text-zinc-300">
                        {tx.merchant_name || tx.reference_note}
                      </td>
                      <td
                        className={`py-2.5 px-3 text-right font-semibold ${
                          tx.direction === "CREDIT" ? "text-emerald-600 dark:text-emerald-400" : "text-slate-950 dark:text-white"
                        }`}
                      >
                        <IosAmount value={tx.direction === "CREDIT" ? tx.amount : -tx.amount} showPlus={tx.direction === "CREDIT"} />
                      </td>
                      <td className="py-2.5 px-3 text-right text-slate-600 dark:text-zinc-400">
                        <IosAmount value={tx.balance_before} />
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold">
                        <IosAmount value={tx.balance_after} />
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

  return (
    <div className="space-y-5">
      <div className="liquid-glass rounded-2xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/30 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <select
              value={status}
              onChange={(e) => onStatusChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium backdrop-blur-md"
            >
              <option value="ALL">All Account Statuses</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="INACTIVE">INACTIVE</option>
              <option value="DORMANT">DORMANT</option>
              <option value="SUSPENDED">SUSPENDED / FROZEN</option>
              <option value="CLOSED">CLOSED</option>
            </select>

            <button
              type="button"
              onClick={() => onDormantChange(!dormantReactivated)}
              className={`px-3.5 py-1.5 rounded-full text-xs font-semibold border transition ${
                dormantReactivated
                  ? "bg-rose-500/20 text-rose-700 dark:text-rose-200 border-rose-500/40"
                  : "bg-white/55 dark:bg-zinc-900 border-white/80 dark:border-white/15 text-slate-700 dark:text-zinc-300"
              }`}
            >
              Dormant Reactivated Only
            </button>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 dark:text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="search"
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Search Account ID or Customer ID..."
                className="pl-8 pr-3 py-1.5 w-64 glass-pill rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 focus:outline-none"
              />
            </div>
            <span className="ios-num text-xs font-semibold text-slate-600 dark:text-zinc-400">
              {total.toLocaleString("en-US")} accounts • Page {page + 1}/{totalPages}
            </span>
            <button
              type="button"
              onClick={() =>
                downloadExport(
                  api.accountsExportUrl("csv", {
                    search: search || undefined,
                    status,
                    dormant_reactivated: dormantReactivated ? "1" : "0",
                  }),
                  "yottaflex_accounts_directory.csv"
                )
              }
              className="glass-pill inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold text-azure-700 dark:text-white"
            >
              <Download className="w-3.5 h-3.5" /> CSV
            </button>
            <button
              type="button"
              onClick={() =>
                downloadExport(
                  api.accountsExportUrl("json", {
                    search: search || undefined,
                    status,
                    dormant_reactivated: dormantReactivated ? "1" : "0",
                  }),
                  "yottaflex_accounts_directory.json"
                )
              }
              className="glass-pill inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200"
            >
              <Download className="w-3.5 h-3.5" /> JSON
            </button>
          </div>
        </div>

        <div ref={listMag.containerRef} onMouseLeave={listMag.onContainerLeave} className="relative overflow-x-auto">
          {listMag.lensElement}
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                <th className="py-3 px-4">Account ID</th>
                <th className="py-3 px-3">Account Holder</th>
                <th className="py-3 px-3">Type / Status</th>
                <th className="py-3 px-3 text-right">Current Balance</th>
                <th className="py-3 px-3">Opened / Last Activity</th>
                <th className="py-3 px-3 text-right">Alerts</th>
                <th className="py-3 px-4 text-right">Risk Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
              {accounts.map((a) => (
                <tr
                  key={a.account_id}
                  onMouseEnter={(e) => listMag.onRowEnter(e.currentTarget)}
                  onClick={() => onSelectAccount(a.account_id)}
                  className="liquid-row-magnify cursor-pointer"
                >
                  <td className="py-3 px-4">
                    <div className="font-mono font-semibold text-slate-950 dark:text-white">{a.account_id}</div>
                    {Boolean(a.is_dormant_reactivated) && (
                      <Badge variant="CRITICAL" className="mt-1">
                        DORMANT REACTIVATED
                      </Badge>
                    )}
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-semibold text-slate-900 dark:text-white">{a.customer_name}</div>
                    <div className="font-mono text-[11px] text-slate-500 dark:text-zinc-400">
                      {a.primary_customer_id} • {a.kyc_tier}
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-1.5">
                      <Badge variant="NEUTRAL">{a.account_type}</Badge>
                      <Badge variant={a.status === "ACTIVE" ? "LOW" : a.status === "CLOSED" ? "CRITICAL" : "HIGH"}>
                        {a.status}
                      </Badge>
                    </div>
                  </td>
                  <td className="py-3 px-3 text-right font-semibold">
                    <IosAmount value={a.current_balance} />
                  </td>
                  <td className="py-3 px-3 ios-num text-[11px] text-slate-600 dark:text-zinc-400">
                    <div>Open: {a.opened_at.slice(0, 10)}</div>
                    <div>Last: {a.last_activity_at ? a.last_activity_at.slice(0, 10) : "—"}</div>
                  </td>
                  <td className="py-3 px-3 text-right ios-num">{a.alert_count}</td>
                  <td className="py-3 px-4 text-right">
                    {a.account_risk_score > 0 ? (
                      <Badge variant={a.account_risk_score >= 60 ? "CRITICAL" : "HIGH"}>
                        {a.account_risk_score.toFixed(1)}
                      </Badge>
                    ) : (
                      <span className="text-slate-400 ios-num">0.0</span>
                    )}
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
          unitLabel="accounts"
        />
      </div>
    </div>
  );
};
