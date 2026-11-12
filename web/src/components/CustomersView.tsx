import React, { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, CreditCard, Download, Laptop, Search, ShieldAlert, ShieldCheck } from "lucide-react";
import { api, downloadExport } from "../api/client";
import type {
  CustomerChronologyItem,
  CustomerListItem,
  CustomerProfile,
  KycReviewItem,
  PeerBaselineResponse,
} from "../types/workbench";
import { Badge, IosAmount, statusVariant, tierVariant } from "./Badge";
import { GlassPagination } from "./GlassPagination";
import { LiquidGlassCard, useRowGlassMagnifier } from "./LiquidGlassSurface";

interface CustomersViewProps {
  customers: CustomerListItem[];
  total: number;
  page: number;
  pageSize: number;
  search: string;
  kycTier: string;
  riskRating: string;
  accountStatus: string;
  multiSuspicious: boolean;
  selectedProfile: CustomerProfile | null;
  onSearchChange: (v: string) => void;
  onKycChange: (v: string) => void;
  onRiskChange: (v: string) => void;
  onAccountStatusChange: (v: string) => void;
  onMultiSuspiciousChange: (v: boolean) => void;
  onPageChange: (nextPage: number) => void;
  onPageSizeChange: (nextSize: number) => void;
  onSelectCustomer: (customerId: string) => void;
  onCloseProfile: () => void;
  onOpenAccount: (accountId: string) => void;
  onOpenTransaction: (transactionId: string) => void;
  onOpenCase: (caseId: string) => void;
}

export const CustomersView: React.FC<CustomersViewProps> = ({
  customers,
  total,
  page,
  pageSize,
  search,
  kycTier,
  riskRating,
  accountStatus,
  multiSuspicious,
  selectedProfile,
  onSearchChange,
  onKycChange,
  onRiskChange,
  onAccountStatusChange,
  onMultiSuspiciousChange,
  onPageChange,
  onPageSizeChange,
  onSelectCustomer,
  onCloseProfile,
  onOpenAccount,
  onOpenTransaction,
  onOpenCase,
}) => {
  const custRowMag = useRowGlassMagnifier();
  const txnMag = useRowGlassMagnifier();
  const [chronoOrder, setChronoOrder] = useState<"ASC" | "DESC">("ASC");
  const [peerBaseline, setPeerBaseline] = useState<PeerBaselineResponse | null>(null);
  const [kycReviews, setKycReviews] = useState<KycReviewItem[]>([]);
  const [kycOutcome, setKycOutcome] = useState<"VERIFIED" | "EDD_REQUIRED" | "OVERDUE">("VERIFIED");
  const [kycJustification, setKycJustification] = useState("");
  const [kycMsg, setKycMsg] = useState<string | null>(null);
  const [chronology, setChronology] = useState<CustomerChronologyItem[]>([]);
  const [custCorridors, setCustCorridors] = useState<Array<{ country: string; txn_count: number; volume: number; share_pct: number }>>([]);
  const [screenResult, setScreenResult] = useState<string | null>(null);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    const cid = selectedProfile?.customer.customer_id;
    setKycMsg(null);
    setScreenResult(null);
    if (!cid) {
      setPeerBaseline(null);
      setKycReviews([]);
      setChronology([]);
      setCustCorridors([]);
      return;
    }
    api.customerPeerBaseline(cid).then(setPeerBaseline).catch(() => setPeerBaseline(null));
    api.kycReviews(cid).then((res) => setKycReviews(res.reviews)).catch(() => setKycReviews([]));
    api.customerChronology(cid).then((r) => setChronology(r.items)).catch(() => setChronology([]));
    api.customerCorridorExposure(cid).then((r) => setCustCorridors(r.corridors)).catch(() => setCustCorridors([]));
  }, [selectedProfile?.customer.customer_id]);

  if (selectedProfile) {
    const cu = selectedProfile.customer;
    const kyc = selectedProfile.kyc_summary;
    const orderedTxns =
      chronoOrder === "ASC" ? selectedProfile.transactions : [...selectedProfile.transactions].reverse();

    return (
      <div className="space-y-5">
        {/* Header + Export Customer Summary (Function 33) */}
        <div className="liquid-glass rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="text-lg font-bold text-slate-950 dark:text-white">{cu.full_name}</h2>
              <span className="font-mono text-xs text-slate-600 dark:text-zinc-400">{cu.customer_id}</span>
              <Badge variant="BLUE">{cu.segment}</Badge>
              <Badge variant={tierVariant(selectedProfile.customer_risk_level)}>
                SCORE: {selectedProfile.customer_risk_score.toFixed(1)} ({selectedProfile.customer_risk_level})
              </Badge>
              {selectedProfile.has_multiple_suspicious_accounts && (
                <Badge variant="CRITICAL">MULTI-ACCOUNT RISK ({selectedProfile.suspicious_account_count} ACCTS)</Badge>
              )}
              <Badge variant="LOW">{cu.status}</Badge>
              {(selectedProfile.watchlist_tags || []).map((t) => (
                <Badge key={t.tag_id} variant="HIGH">{t.tag}</Badge>
              ))}
            </div>
            <div className="mt-1.5 text-xs text-slate-600 dark:text-zinc-400 font-mono">
              {cu.email} • {cu.phone} • Country: {cu.home_country} • Onboarded: {cu.created_at}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => downloadExport(api.customerExportUrl(cu.customer_id, "csv"), `${cu.customer_id}_investigation_summary.csv`)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 glass-pill rounded-full text-xs font-semibold text-azure-700 dark:text-white"
            >
              <Download className="w-3.5 h-3.5" /> Export CSV
            </button>
            <button
              type="button"
              onClick={() => downloadExport(api.customerExportUrl(cu.customer_id, "json"), `${cu.customer_id}_investigation_summary.json`)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black text-xs font-semibold"
            >
              <Download className="w-3.5 h-3.5" /> Export JSON
            </button>
            <button
              type="button"
              onClick={onCloseProfile}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 glass-pill rounded-full text-xs font-semibold"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back
            </button>
          </div>
        </div>

        {/* Row 1: KYC Profile, Risk Score Factors (Fn 30), Risk Timeline (Fn 31) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <LiquidGlassCard className="lg:col-span-4 rounded-2xl p-5">
            <div className="space-y-3 text-xs">
              <div className="flex items-center gap-2 font-semibold text-sm text-slate-950 dark:text-white">
                <ShieldCheck className="w-4 h-4 text-azure-600 dark:text-white" />
                <span>KYC Profile &amp; Verification</span>
              </div>
              <div className="rounded-xl bg-emerald-500/12 border border-emerald-500/25 px-3.5 py-2 flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 font-semibold text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="w-4 h-4" /> KYC Verified
                </span>
                <Badge variant="BLUE">{kyc.kyc_tier}</Badge>
              </div>
              <div className="space-y-2 pt-1">
                <div className="flex justify-between py-1.5 border-b border-white/40 dark:border-white/10">
                  <span className="text-slate-600 dark:text-zinc-400">Verified At</span>
                  <span className="ios-num font-medium text-slate-950 dark:text-white">{kyc.kyc_verified_at}</span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-white/40 dark:border-white/10">
                  <span className="text-slate-600 dark:text-zinc-400">Declared Annual Income</span>
                  <span className="font-semibold text-slate-950 dark:text-white">
                    <IosAmount value={kyc.declared_annual_income} />
                  </span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-white/40 dark:border-white/10">
                  <span className="text-slate-600 dark:text-zinc-400">Onboarding Rating</span>
                  <Badge variant={tierVariant(kyc.risk_rating === "HIGH" ? "CRITICAL" : kyc.risk_rating)}>
                    {kyc.risk_rating}
                  </Badge>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-600 dark:text-zinc-400">Suspicious Accounts</span>
                  <span className="ios-num font-bold text-slate-950 dark:text-white">
                    {selectedProfile.suspicious_account_count} / {selectedProfile.accounts.length}
                  </span>
                </div>
              </div>
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard className="lg:col-span-4 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Customer Risk Contributing Factors
              </h3>
              <span className="ios-num font-bold text-sm text-azure-700 dark:text-white">
                {selectedProfile.customer_risk_score.toFixed(1)} / 100
              </span>
            </div>
            <div className="space-y-2.5 text-xs">
              {selectedProfile.risk_factors.map((rf) => (
                <div key={rf.factor} className="space-y-1">
                  <div className="flex justify-between">
                    <span className="font-medium text-slate-800 dark:text-zinc-200">{rf.factor}</span>
                    <span className="ios-num font-bold text-slate-950 dark:text-white">+{rf.points.toFixed(1)}</span>
                  </div>
                  <div className="text-[11px] text-slate-600 dark:text-zinc-400">{rf.detail}</div>
                </div>
              ))}
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard className="lg:col-span-4 rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white mb-3">
              Risk Level Changes Over Time
            </h3>
            <div className="space-y-3 max-h-56 overflow-y-auto pr-1">
              {selectedProfile.risk_level_timeline.map((ev, idx) => (
                <div key={`${ev.timestamp}-${idx}`} className="relative pl-4 border-l-2 border-white/60 dark:border-zinc-700 text-xs">
                  <span className="w-2 h-2 rounded-full bg-azure-600 dark:bg-white absolute -left-[5px] top-1.5" />
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-slate-950 dark:text-white">{ev.event}</span>
                    <Badge variant={tierVariant(ev.risk_level)}>
                      {ev.risk_level} ({ev.risk_score.toFixed(0)})
                    </Badge>
                  </div>
                  <div className="text-[11px] text-slate-600 dark:text-zinc-400">{ev.detail}</div>
                  <div className="ios-num text-[10.5px] text-slate-500 dark:text-zinc-500">{ev.timestamp}</div>
                </div>
              ))}
            </div>
          </LiquidGlassCard>
        </div>

        {/* Functions 182, 183, 199: Peer-Cohort Behavioral Baseline & KYC Periodic Review */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Peer-Cohort Behavioral Baseline</h3>
              {peerBaseline && <Badge variant="BLUE">{peerBaseline.cohort}</Badge>}
            </div>
            {peerBaseline ? (
              <div className="grid grid-cols-2 gap-3 ios-num">
                <div className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                  <div className="text-slate-600 dark:text-zinc-400">Customer Volume</div>
                  <div className="mt-1 text-base font-bold text-slate-950 dark:text-white">${peerBaseline.customer_volume.toLocaleString()}</div>
                  <div className="text-[11px] text-azure-700 dark:text-sky-300">{peerBaseline.volume_ratio_to_mean}x vs cohort mean</div>
                </div>
                <div className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                  <div className="text-slate-600 dark:text-zinc-400">Cohort Mean / P95</div>
                  <div className="mt-1 text-sm font-bold text-slate-950 dark:text-white">${peerBaseline.cohort_mean_volume.toLocaleString()}</div>
                  <div className="text-[11px] text-slate-600 dark:text-zinc-400">P95: ${peerBaseline.cohort_p95_volume.toLocaleString()}</div>
                </div>
                <div className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                  <div className="text-slate-600 dark:text-zinc-400">Avg Ticket (vs Peer)</div>
                  <div className="mt-1 font-bold text-slate-950 dark:text-white">
                    ${peerBaseline.customer_avg_ticket.toLocaleString()} vs ${peerBaseline.cohort_mean_ticket.toLocaleString()}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                  <div className="text-slate-600 dark:text-zinc-400">Cross-Border Share</div>
                  <div className="mt-1 text-base font-bold text-slate-950 dark:text-white">{peerBaseline.cross_border_pct}%</div>
                </div>
              </div>
            ) : (
              <div className="text-slate-500">Loading cohort telemetry...</div>
            )}
          </div>

          <div className="lg:col-span-7 liquid-glass rounded-2xl p-5 space-y-3 text-xs">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">KYC Periodic Refresh &amp; EDD Review</h3>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  await api.submitKycReview(cu.customer_id, { outcome: kycOutcome, risk_justification: kycJustification });
                  setKycJustification("");
                  setKycMsg(`Recorded KYC review (${kycOutcome}).`);
                  const res = await api.kycReviews(cu.customer_id);
                  setKycReviews(res.reviews);
                } catch (err) {
                  setKycMsg(err instanceof Error ? err.message : "Failed to save KYC review");
                }
              }}
              className="flex flex-wrap gap-2"
            >
              <select
                value={kycOutcome}
                onChange={(e) => setKycOutcome(e.target.value as typeof kycOutcome)}
                className="px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white"
              >
                <option value="VERIFIED" className="bg-white dark:bg-zinc-900">VERIFIED</option>
                <option value="EDD_REQUIRED" className="bg-white dark:bg-zinc-900">EDD_REQUIRED</option>
                <option value="OVERDUE" className="bg-white dark:bg-zinc-900">OVERDUE</option>
              </select>
              <input
                type="text"
                required
                value={kycJustification}
                onChange={(e) => setKycJustification(e.target.value)}
                placeholder="Corroboration rationale & source of wealth check..."
                className="flex-1 min-w-[200px] px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white placeholder:text-slate-500"
              />
              <button type="submit" className="px-3.5 py-1.5 rounded-full bg-azure-600 text-white font-semibold hover:bg-azure-500 transition">
                Log KYC Review
              </button>
            </form>
            {kycMsg && <div className="text-azure-700 dark:text-sky-300 font-semibold">{kycMsg}</div>}
            <div className="space-y-1.5 max-h-28 overflow-y-auto">
              {kycReviews.map((kr) => (
                <div key={kr.review_id} className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-white/20 dark:bg-white/[0.04] border border-white/45 dark:border-white/10">
                  <div>
                    <Badge variant={kr.outcome === "VERIFIED" ? "LOW" : kr.outcome === "EDD_REQUIRED" ? "HIGH" : "CRITICAL"}>{kr.outcome}</Badge>
                    <span className="ml-2 text-slate-800 dark:text-zinc-200">{kr.risk_justification}</span>
                  </div>
                  <span className="font-mono text-[10.5px] text-slate-500">{kr.reviewer_id} • {kr.reviewed_at.slice(0, 10)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Functions 226, 229, 230: Quick Sanctions Check, Corridor Exposure & Unified Customer Chronology */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 text-xs">
          <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Corridor Exposure &amp; Sanctions Check</h3>
              <button
                type="button"
                onClick={async () => {
                  const res = await api.runSanctionsScreening({
                    entity_type: "CUSTOMER",
                    entity_id: cu.customer_id,
                    query_name: cu.full_name,
                    country_code: cu.home_country,
                  });
                  setScreenResult(`${res.disposition} (${res.match_score}%)`);
                }}
                className="glass-pill px-3 py-1 rounded-full font-semibold text-azure-700 dark:text-sky-300"
              >
                Screen PEP/OFAC
              </button>
            </div>
            {screenResult && (
              <div className="px-3 py-1.5 rounded-xl bg-white/25 dark:bg-white/[0.04] font-semibold text-emerald-700 dark:text-emerald-300">
                Screening Result: {screenResult}
              </div>
            )}
            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              {custCorridors.map((cc) => (
                <div key={cc.country} className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-white/20 dark:bg-white/[0.04] border border-white/50 dark:border-white/10 ios-num">
                  <span className="font-mono font-bold">{cc.country}</span>
                  <span>{cc.txn_count} txns • {cc.share_pct}%</span>
                  <IosAmount value={cc.volume} />
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-7 liquid-glass rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Unified Customer Chronology ({chronology.length})
            </h3>
            <div className="space-y-1.5 max-h-44 overflow-y-auto">
              {chronology.slice(0, 15).map((ev, idx) => (
                <div key={`${ev.ref_id}-${idx}`} className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-xl bg-white/20 dark:bg-white/[0.04] border border-white/50 dark:border-white/10">
                  <div className="min-w-0 truncate">
                    <Badge variant={tierVariant(ev.severity)}>{ev.event_type}</Badge>{" "}
                    <span className="ml-1.5 text-slate-900 dark:text-zinc-100">{ev.summary}</span>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500 shrink-0">{ev.timestamp.slice(0, 10)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Row 2: Associated Accounts + Associated Devices (Fn 25, 27) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-7 liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-azure-600 dark:text-white" />
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Associated Accounts ({selectedProfile.accounts.length})
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-zinc-400">
                    <th className="py-2.5 px-4">Account ID</th>
                    <th className="py-2.5 px-3">Type / Role</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Balance</th>
                    <th className="py-2.5 px-4 text-right">Alerts</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                  {selectedProfile.accounts.map((a) => (
                    <tr
                      key={a.account_id}
                      onClick={() => onOpenAccount(a.account_id)}
                      className="cursor-pointer hover:bg-white/45 dark:hover:bg-white/[0.04]"
                    >
                      <td className="py-2.5 px-4 font-mono font-semibold text-azure-700 dark:text-white">{a.account_id}</td>
                      <td className="py-2.5 px-3">
                        <div className="font-semibold">{a.account_type}</div>
                        <div className="text-[11px] text-slate-500 dark:text-zinc-400">
                          {a.ownership_role} ({a.ownership_pct}%)
                        </div>
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge variant={a.status === "ACTIVE" ? "LOW" : a.status === "CLOSED" ? "CRITICAL" : "HIGH"}>
                          {a.status}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-right font-bold">
                        <IosAmount value={a.current_balance} />
                      </td>
                      <td className="py-2.5 px-4 text-right ios-num">{a.alert_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="lg:col-span-5 liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex items-center gap-2">
              <Laptop className="w-4 h-4 text-azure-600 dark:text-white" />
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Associated Devices ({selectedProfile.devices.length})
              </h3>
            </div>
            <div className="p-4 space-y-2.5 max-h-64 overflow-y-auto text-xs">
              {selectedProfile.devices.map((d) => (
                <div
                  key={`${d.device_id}-${d.account_id}`}
                  className="rounded-xl bg-white/40 dark:bg-black/40 border border-white/60 dark:border-white/10 p-3 flex items-center justify-between"
                >
                  <div>
                    <div className="font-mono font-semibold text-slate-950 dark:text-white">
                      {d.device_id} • {d.os_family} {d.is_emulator ? "(EMULATOR)" : ""}
                    </div>
                    <div className="text-[11px] text-slate-600 dark:text-zinc-400 font-mono">
                      Account: {d.account_id} • IP: {d.ip_country} • First: {d.first_seen_at.slice(0, 10)}
                    </div>
                  </div>
                  <Badge variant={d.is_trusted ? "LOW" : "CRITICAL"}>
                    {d.is_trusted ? "TRUSTED" : "UNTRUSTED"}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Row 3: Customer Alerts & Investigation Cases (Fn 29) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-600 dark:text-rose-400" />
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Customer Alerts ({selectedProfile.alerts.length})
              </h3>
            </div>
            <div className="p-4 space-y-2 max-h-64 overflow-y-auto text-xs">
              {selectedProfile.alerts.length === 0 ? (
                <div className="text-slate-500 dark:text-zinc-400">No alerts triggered for this customer.</div>
              ) : (
                selectedProfile.alerts.map((al) => (
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
                    <div className="ios-num text-[10.5px] text-slate-500 dark:text-zinc-500 mt-0.5">
                      {al.account_id} • {al.created_at}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Customer Investigation Cases ({selectedProfile.cases.length})
              </h3>
            </div>
            <div className="p-4 flex flex-wrap gap-3">
              {selectedProfile.cases.length === 0 ? (
                <div className="text-xs text-slate-500 dark:text-zinc-400">No investigation cases opened.</div>
              ) : (
                selectedProfile.cases.map((ca) => (
                  <button
                    key={ca.case_id}
                    type="button"
                    onClick={() => onOpenCase(ca.case_id)}
                    className="glass-pill rounded-2xl px-4 py-3 text-left hover:scale-[1.02] transition"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-xs text-azure-700 dark:text-white">{ca.case_id}</span>
                      <Badge variant={tierVariant(ca.priority_tier)}>{ca.priority_score.toFixed(1)}</Badge>
                      <Badge variant={statusVariant(ca.status)}>{ca.status}</Badge>
                    </div>
                    <div className="mt-1 text-xs text-slate-600 dark:text-zinc-400">
                      Exposure: <IosAmount value={ca.total_exposure_amount} />
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Row 4: Customer Chronological Transaction History (Functions 26, 28) */}
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Customer Transaction History ({orderedTxns.length})
              </h3>
              <p className="text-xs text-slate-600 dark:text-zinc-400">
                Chronological ledger across all customer-owned accounts
              </p>
            </div>
            <button
              type="button"
              onClick={() => setChronoOrder((o) => (o === "ASC" ? "DESC" : "ASC"))}
              className="px-3 py-1.5 glass-pill rounded-full text-xs font-semibold"
            >
              Order: {chronoOrder === "ASC" ? "Oldest → Newest (Chronological)" : "Newest → Oldest"}
            </button>
          </div>
          <div ref={txnMag.containerRef} onMouseLeave={txnMag.onContainerLeave} className="relative overflow-x-auto max-h-96">
            {txnMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead className="sticky top-0 z-10 bg-white/45 dark:bg-black/65 backdrop-blur-md border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                <tr>
                  <th className="py-2.5 px-4">Transaction ID</th>
                  <th className="py-2.5 px-3">Timestamp (UTC)</th>
                  <th className="py-2.5 px-3">Account</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3 text-right">Balance After</th>
                  <th className="py-2.5 px-4 text-right">Alert Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {orderedTxns.map((tx) => (
                  <tr
                    key={tx.transaction_id}
                    onMouseEnter={(e) => txnMag.onRowEnter(e.currentTarget)}
                    onClick={() => onOpenTransaction(tx.transaction_id)}
                    className="liquid-row-magnify cursor-pointer"
                  >
                    <td className="py-2.5 px-4 font-mono text-slate-950 dark:text-white">{tx.transaction_id}</td>
                    <td className="py-2.5 px-3 ios-num text-slate-600 dark:text-zinc-400">{tx.occurred_at}</td>
                    <td className="py-2.5 px-3 font-mono text-azure-700 dark:text-zinc-200">{tx.account_id}</td>
                    <td className="py-2.5 px-3">
                      <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{tx.txn_type}</span>
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
                      {tx.txn_risk_score > 0 ? (
                        <Badge variant={tx.txn_risk_score >= 60 ? "CRITICAL" : "HIGH"}>{tx.txn_risk_score.toFixed(0)}</Badge>
                      ) : (
                        <span className="text-slate-400 ios-num">—</span>
                      )}
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
              value={kycTier}
              onChange={(e) => onKycChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium backdrop-blur-md"
            >
              <option value="ALL">All KYC Tiers</option>
              <option value="LOW">KYC: LOW</option>
              <option value="STANDARD">KYC: STANDARD</option>
              <option value="ENHANCED">KYC: ENHANCED</option>
            </select>

            <select
              value={riskRating}
              onChange={(e) => onRiskChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium backdrop-blur-md"
            >
              <option value="ALL">All Risk Ratings</option>
              <option value="HIGH">Risk: HIGH</option>
              <option value="MEDIUM">Risk: MEDIUM</option>
              <option value="LOW">Risk: LOW</option>
            </select>

            <select
              value={accountStatus}
              onChange={(e) => onAccountStatusChange(e.target.value)}
              className="glass-pill rounded-full px-3 py-1.5 text-xs font-medium backdrop-blur-md"
            >
              <option value="ALL">All Account Statuses</option>
              <option value="ACTIVE">Has ACTIVE Account</option>
              <option value="INACTIVE">Has INACTIVE Account</option>
              <option value="DORMANT">Has DORMANT Account</option>
              <option value="SUSPENDED">Has SUSPENDED Account</option>
              <option value="CLOSED">Has CLOSED Account</option>
            </select>

            <button
              type="button"
              onClick={() => onMultiSuspiciousChange(!multiSuspicious)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                multiSuspicious
                  ? "bg-rose-500/20 text-rose-700 dark:text-rose-200 border-rose-500/40"
                  : "bg-white/55 dark:bg-zinc-900 border-white/80 dark:border-white/15 text-slate-700 dark:text-zinc-300"
              }`}
            >
              Multi-Suspicious Accounts Only
            </button>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 dark:text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="search"
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Search ID, Name, Email, Phone, Account..."
                className="pl-8 pr-3 py-1.5 w-72 glass-pill rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-500 focus:outline-none"
              />
            </div>
            <span className="ios-num text-xs font-semibold text-slate-600 dark:text-zinc-400">
              {total.toLocaleString("en-US")} customers • Page {page + 1}/{totalPages}
            </span>
            <button
              type="button"
              onClick={() =>
                downloadExport(
                  api.customersExportUrl("csv", {
                    search: search || undefined,
                    kyc_tier: kycTier,
                    risk_rating: riskRating,
                    account_status: accountStatus,
                    multi_suspicious: multiSuspicious ? "1" : "0",
                  }),
                  "yottaflex_customers_directory.csv"
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
                  api.customersExportUrl("json", {
                    search: search || undefined,
                    kyc_tier: kycTier,
                    risk_rating: riskRating,
                    account_status: accountStatus,
                    multi_suspicious: multiSuspicious ? "1" : "0",
                  }),
                  "yottaflex_customers_directory.json"
                )
              }
              className="glass-pill inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200"
            >
              <Download className="w-3.5 h-3.5" /> JSON
            </button>
          </div>
        </div>

        <div ref={custRowMag.containerRef} onMouseLeave={custRowMag.onContainerLeave} className="relative overflow-x-auto">
          {custRowMag.lensElement}
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                <th className="py-3 px-4">Customer ID</th>
                <th className="py-3 px-3">Customer &amp; Contact</th>
                <th className="py-3 px-3">KYC / Segment</th>
                <th className="py-3 px-3">Risk Rating</th>
                <th className="py-3 px-3 text-right">Accts / Susp.</th>
                <th className="py-3 px-3 text-right">Total Balance</th>
                <th className="py-3 px-3 text-right">Alerts / Cases</th>
                <th className="py-3 px-4 text-right">Max Case Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
              {customers.map((c) => (
                <tr
                  key={c.customer_id}
                  onMouseEnter={(e) => custRowMag.onRowEnter(e.currentTarget)}
                  onClick={() => onSelectCustomer(c.customer_id)}
                  className="liquid-row-magnify cursor-pointer"
                >
                  <td className="py-3 px-4 font-mono font-semibold text-slate-950 dark:text-white">{c.customer_id}</td>
                  <td className="py-3 px-3">
                    <div className="font-semibold text-slate-900 dark:text-white">{c.full_name}</div>
                    <div className="font-mono text-[11px] text-slate-500 dark:text-zinc-400">
                      {c.email} • {c.phone}
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-1.5">
                      <Badge variant="BLUE">{c.kyc_tier}</Badge>
                      <span className="text-slate-600 dark:text-zinc-400">{c.segment}</span>
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <Badge variant={tierVariant(c.risk_rating === "HIGH" ? "CRITICAL" : c.risk_rating)}>
                      {c.risk_rating}
                    </Badge>
                  </td>
                  <td className="py-3 px-3 text-right ios-num">
                    {c.account_count} /{" "}
                    <span className={c.suspicious_account_count >= 2 ? "text-rose-600 dark:text-rose-400 font-bold" : ""}>
                      {c.suspicious_account_count}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right font-semibold">
                    <IosAmount value={c.total_balance} />
                  </td>
                  <td className="py-3 px-3 text-right ios-num">
                    {c.alert_count} / {c.case_count}
                  </td>
                  <td className="py-3 px-4 text-right">
                    {c.max_case_score > 0 ? (
                      <Badge variant={c.max_case_score >= 60 ? "CRITICAL" : "HIGH"}>
                        {c.max_case_score.toFixed(1)}
                      </Badge>
                    ) : (
                      <span className="text-slate-400 ios-num">—</span>
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
          unitLabel="customers"
        />
      </div>
    </div>
  );
};
