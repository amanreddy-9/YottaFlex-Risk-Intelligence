import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Download,
  GitMerge,
  Globe2,
  Layers,
  Play,
  Plus,
  Send,
  ShieldOff,
  Store,
  Trash2,
} from "lucide-react";
import { api, downloadExport } from "../api/client";
import type {
  AuthUser,
  CapacityForecastResponse,
  CorridorRiskItem,
  FlowChainResponse,
  MerchantLeaderboardItem,
  MergeCandidateItem,
  PipelineRunItem,
  SiemOutboxItem,
  SlaRadarResponse,
  StructuringClusterItem,
  SuppressionRuleItem,
  WatchedCountryItem,
} from "../types/workbench";
import { Badge, tierVariant } from "./Badge";
import { GlassPagination } from "./GlassPagination";
import { LiquidGlassCard, useRowGlassMagnifier } from "./LiquidGlassSurface";

interface ForensicsOpsSectionProps {
  mode: "forensics" | "ops";
  user: AuthUser;
  onOpenCase: (caseId: string) => void;
  onOpenAccount: (accountId: string) => void;
  onOpenCustomer: (customerId: string) => void;
  onBanner: (msg: string) => void;
}

export const ForensicsOpsSection: React.FC<ForensicsOpsSectionProps> = ({
  mode,
  user,
  onOpenCase,
  onOpenAccount,
  onOpenCustomer,
  onBanner,
}) => {
  const corMag = useRowGlassMagnifier();
  const merMag = useRowGlassMagnifier();
  const stMag = useRowGlassMagnifier();

  // Forensics state
  const [corridors, setCorridors] = useState<CorridorRiskItem[]>([]);
  const [watchedCountries, setWatchedCountries] = useState<WatchedCountryItem[]>([]);
  const [corPage, setCorPage] = useState(0);
  const [corPageSize, setCorPageSize] = useState(30);

  const [newCountryCode, setNewCountryCode] = useState("");
  const [newCountryName, setNewCountryName] = useState("");
  const [newCountryTier, setNewCountryTier] = useState<"WATCH" | "RESTRICTED">("WATCH");
  const [newCountryMult, setNewCountryMult] = useState("1.30");

  const [merchants, setMerchants] = useState<MerchantLeaderboardItem[]>([]);
  const [merchSearch, setMerchSearch] = useState("");
  const [merchPage, setMerchPage] = useState(0);
  const [merchPageSize, setMerchPageSize] = useState(30);
  const [selectedMerchant, setSelectedMerchant] = useState<Record<string, unknown> | null>(null);

  const [flowAcctInput, setFlowAcctInput] = useState("");
  const [flowResult, setFlowResult] = useState<FlowChainResponse | null>(null);

  const [structuring, setStructuring] = useState<StructuringClusterItem[]>([]);
  const [strPage, setStrPage] = useState(0);
  const [strPageSize, setStrPageSize] = useState(30);

  // Ops, SIEM & Jobs state
  const [growthFactor, setGrowthFactor] = useState(1.5);
  const [hoursPerCase, setHoursPerCase] = useState(1.5);
  const [analystsAvail, setAnalystsAvail] = useState(4);
  const [forecast, setForecast] = useState<CapacityForecastResponse | null>(null);

  const [slaRadar, setSlaRadar] = useState<SlaRadarResponse | null>(null);
  const [pendingEsc, setPendingEsc] = useState<Array<Record<string, unknown>>>([]);
  const [mergeCands, setMergeCands] = useState<MergeCandidateItem[]>([]);
  const [suppressions, setSuppressions] = useState<SuppressionRuleItem[]>([]);
  const [supAcct, setSupAcct] = useState("");
  const [supRule, setSupRule] = useState("RULE-001");
  const [supMax, setSupMax] = useState("5000");
  const [supReason, setSupReason] = useState("");

  const [siemOutbox, setSiemOutbox] = useState<SiemOutboxItem[]>([]);
  const [pipelineJobs, setPipelineJobs] = useState<PipelineRunItem[]>([]);

  const loadForensics = async () => {
    try {
      const [cRes, mRes, sRes] = await Promise.all([
        api.corridors(),
        api.merchants(merchSearch),
        api.structuringClusters(),
      ]);
      setCorridors(cRes.items);
      setWatchedCountries(cRes.watched_countries);
      setMerchants(mRes.items);
      setStructuring(sRes.items);
      if (!flowAcctInput && sRes.items[0]?.account_id) {
        setFlowAcctInput(sRes.items[0].account_id);
      }
    } catch (err) {
      onBanner(err instanceof Error ? err.message : "Failed to load forensics telemetry");
    }
  };

  const loadOps = async () => {
    try {
      const [fc, rad, esc, mc, sup, siem, jobs] = await Promise.all([
        api.capacityForecast({ growth_factor: growthFactor, hours_per_case: hoursPerCase, analysts_available: analystsAvail }),
        api.slaRadar(8),
        api.pendingEscalations(),
        api.mergeCandidates(),
        api.suppressionRules(),
        api.siemOutbox(),
        api.pipelineJobs(),
      ]);
      setForecast(fc);
      setSlaRadar(rad);
      setPendingEsc(esc.items);
      setMergeCands(mc.items);
      setSuppressions(sup.items);
      setSiemOutbox(siem.items);
      setPipelineJobs(jobs.items);
    } catch (err) {
      onBanner(err instanceof Error ? err.message : "Failed to load operational telemetry");
    }
  };

  useEffect(() => {
    if (mode === "forensics") loadForensics();
    else loadOps();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, merchSearch]);

  useEffect(() => {
    if (mode !== "ops") return;
    api
      .capacityForecast({ growth_factor: growthFactor, hours_per_case: hoursPerCase, analysts_available: analystsAvail })
      .then(setForecast)
      .catch(() => {});
  }, [growthFactor, hoursPerCase, analystsAvail, mode]);

  if (mode === "forensics") {
    return (
      <div className="space-y-5">
        {/* Jurisdiction Watchlist Registry & Quick Editor */}
        <div className="liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
                <Globe2 className="w-4 h-4 text-azure-600 dark:text-sky-400" />
                Watched High-Risk Jurisdictions ({watchedCountries.length})
              </h3>
              <p className="text-xs text-slate-600 dark:text-zinc-400">
                FATF &amp; high-velocity transit corridors highlighted across Cross-Border Matrices
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {watchedCountries.map((wc) => (
              <span
                key={wc.country_code}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.05] backdrop-blur-md border border-white/60 dark:border-white/15 text-xs"
              >
                <Badge variant={wc.risk_tier === "RESTRICTED" ? "CRITICAL" : "HIGH"}>{wc.country_code}</Badge>
                <span className="font-semibold text-slate-900 dark:text-white">{wc.country_name}</span>
                <span className="ios-num text-[11px] text-slate-600 dark:text-zinc-400">{wc.multiplier}x</span>
                {user.role === "SYSTEM_ADMIN" && (
                  <button
                    type="button"
                    onClick={async () => {
                      await api.deleteHighRiskCountry(wc.country_code);
                      onBanner(`Removed watched jurisdiction ${wc.country_code}.`);
                      loadForensics();
                    }}
                    className="text-slate-400 hover:text-rose-500 transition"
                    title="Remove jurisdiction"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                )}
              </span>
            ))}
          </div>

          {(user.role === "SYSTEM_ADMIN" || user.role === "RISK_REVIEWER") && (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  await api.upsertHighRiskCountry({
                    country_code: newCountryCode,
                    country_name: newCountryName,
                    risk_tier: newCountryTier,
                    multiplier: Number(newCountryMult) || 1.25,
                  });
                  setNewCountryCode("");
                  setNewCountryName("");
                  onBanner("Saved watched jurisdiction.");
                  loadForensics();
                } catch (err) {
                  onBanner(err instanceof Error ? err.message : "Failed to save country");
                }
              }}
              className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/40 dark:border-white/10 text-xs"
            >
              <input
                type="text"
                maxLength={4}
                required
                value={newCountryCode}
                onChange={(e) => setNewCountryCode(e.target.value)}
                placeholder="Code (e.g. AE)"
                className="w-28 px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white placeholder:text-slate-500"
              />
              <input
                type="text"
                required
                value={newCountryName}
                onChange={(e) => setNewCountryName(e.target.value)}
                placeholder="Jurisdiction label..."
                className="w-48 px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white placeholder:text-slate-500"
              />
              <select
                value={newCountryTier}
                onChange={(e) => setNewCountryTier(e.target.value as "WATCH" | "RESTRICTED")}
                className="px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white"
              >
                <option value="WATCH" className="bg-white dark:bg-zinc-900">WATCH</option>
                <option value="RESTRICTED" className="bg-white dark:bg-zinc-900">RESTRICTED</option>
              </select>
              <input
                type="number"
                step="0.05"
                min="1.0"
                max="5.0"
                value={newCountryMult}
                onChange={(e) => setNewCountryMult(e.target.value)}
                className="w-20 px-2.5 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 ios-num text-slate-900 dark:text-white"
              />
              <button
                type="submit"
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-azure-600 text-white font-semibold hover:bg-azure-500 transition"
              >
                <Plus className="w-3.5 h-3.5" /> Add Watch
              </button>
            </form>
          )}
        </div>

        {/* Corridor Risk Matrix */}
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Cross-Border Corridor Risk Matrix ({corridors.length})
            </h3>
            <p className="text-xs text-slate-600 dark:text-zinc-400">
              Origin to counterparty volume, alert hit rate &amp; average risk scores
            </p>
          </div>
          <div ref={corMag.containerRef} onMouseLeave={corMag.onContainerLeave} className="relative overflow-x-auto">
            {corMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Corridor</th>
                  <th className="py-2.5 px-3">Jurisdiction Tier</th>
                  <th className="py-2.5 px-3 text-right">Txns</th>
                  <th className="py-2.5 px-3 text-right">Total Volume</th>
                  <th className="py-2.5 px-3 text-right">Alerts (Hit %)</th>
                  <th className="py-2.5 px-4 text-right">Avg Alert Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {corridors.slice(corPage * corPageSize, (corPage + 1) * corPageSize).map((c) => (
                  <tr
                    key={`${c.origin_country}-${c.counterparty_country}`}
                    onMouseEnter={(e) => corMag.onRowEnter(e.currentTarget)}
                    className="liquid-row-magnify"
                  >
                    <td className="py-2.5 px-4 font-mono font-bold text-slate-950 dark:text-white">
                      {c.origin_country} &rarr; {c.counterparty_country}
                      {c.is_cross_border && <span className="ml-2 text-[10px] text-azure-600 dark:text-sky-300">XBORDER</span>}
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant={c.jurisdiction_tier === "RESTRICTED" ? "CRITICAL" : c.jurisdiction_tier === "WATCH" ? "HIGH" : "NEUTRAL"}>
                        {c.jurisdiction_tier}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num">{c.txn_count.toLocaleString()}</td>
                    <td className="py-2.5 px-3 text-right ios-num font-semibold">${c.total_volume.toLocaleString()}</td>
                    <td className="py-2.5 px-3 text-right ios-num">
                      {c.alert_count} ({c.alert_rate_pct}%)
                    </td>
                    <td className="py-2.5 px-4 text-right ios-num font-bold text-azure-700 dark:text-sky-300">
                      {c.avg_alert_score.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <GlassPagination
            total={corridors.length}
            page={corPage}
            pageSize={corPageSize}
            onPageChange={setCorPage}
            onPageSizeChange={(sz) => { setCorPageSize(sz); setCorPage(0); }}
            unitLabel="corridors"
          />
        </div>

        {/* Layering Flow Chain Tracer & Structuring Clusters */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-3 self-start">
            <h4 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              Rapid Pass-Through Chain Tracer
            </h4>
            <div className="flex gap-2">
              <input
                type="text"
                value={flowAcctInput}
                onChange={(e) => setFlowAcctInput(e.target.value)}
                placeholder="ACC-CUS-..."
                className="flex-1 px-3 py-1.5 rounded-full text-xs bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white"
              />
              <button
                type="button"
                onClick={async () => {
                  try {
                    const res = await api.flowChains(flowAcctInput);
                    setFlowResult(res);
                  } catch (err) {
                    onBanner(err instanceof Error ? err.message : "Flow chain trace failed");
                  }
                }}
                className="px-3.5 py-1.5 rounded-full bg-azure-600 text-white text-xs font-semibold hover:bg-azure-500 transition"
              >
                Trace 72h Chains
              </button>
            </div>
            {flowResult && (
              <div className="space-y-2.5 text-xs">
                <div className="grid grid-cols-3 gap-2 ios-num">
                  <div className="p-2.5 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                    <div className="text-[10.5px] text-slate-600 dark:text-zinc-400">Inflow</div>
                    <div className="font-bold text-emerald-700 dark:text-emerald-400">${flowResult.total_inflow.toLocaleString()}</div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                    <div className="text-[10.5px] text-slate-600 dark:text-zinc-400">Outflow</div>
                    <div className="font-bold text-slate-950 dark:text-white">${flowResult.total_outflow.toLocaleString()}</div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                    <div className="text-[10.5px] text-slate-600 dark:text-zinc-400">Pass-Through</div>
                    <div className="font-bold text-rose-700 dark:text-rose-400">{flowResult.pass_through_pct}%</div>
                  </div>
                </div>
                <div className="space-y-1.5 max-h-56 overflow-y-auto">
                  {flowResult.pass_through_chains.map((ch, idx) => (
                    <div key={idx} className="p-2.5 rounded-xl bg-white/20 dark:bg-white/[0.04] border border-white/45 dark:border-white/10 font-mono text-[11px]">
                      <div className="font-bold text-slate-900 dark:text-white">{ch.path}</div>
                      <div className="text-slate-600 dark:text-zinc-400">
                        In ${ch.in_amount.toLocaleString()} &rarr; Out ${ch.out_amount.toLocaleString()} ({ch.retention_pct}% • {ch.lag_hours}h)
                      </div>
                    </div>
                  ))}
                  {flowResult.pass_through_chains.length === 0 && (
                    <div className="text-slate-500 dark:text-zinc-400 py-2">
                      {flowResult.edges.length} direct transfer edges recorded; no 2-hop pass-through sequences inside 72h.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-7 liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Sub-Threshold Structuring Bursts ($7.5k–$9.99k &ge; $10k)
              </h3>
            </div>
            <div ref={stMag.containerRef} onMouseLeave={stMag.onContainerLeave} className="relative overflow-x-auto">
              {stMag.lensElement}
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                    <th className="py-2.5 px-4">Account / Customer</th>
                    <th className="py-2.5 px-3 text-right">Bursts</th>
                    <th className="py-2.5 px-3 text-right">Avg Ticket</th>
                    <th className="py-2.5 px-4 text-right">Structured Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                  {structuring.slice(strPage * strPageSize, (strPage + 1) * strPageSize).map((s) => (
                    <tr key={s.account_id} onMouseEnter={(e) => stMag.onRowEnter(e.currentTarget)} className="liquid-row-magnify">
                      <td className="py-2.5 px-4">
                        <button type="button" onClick={() => onOpenAccount(s.account_id)} className="font-mono font-bold text-azure-700 dark:text-sky-300 hover:underline">
                          {s.account_id}
                        </button>
                        <div>
                          <button type="button" onClick={() => onOpenCustomer(s.primary_customer_id)} className="text-[11px] text-slate-600 dark:text-zinc-400 hover:underline">
                            {s.customer_name} ({s.primary_customer_id})
                          </button>
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-right ios-num font-bold">{s.burst_count}</td>
                      <td className="py-2.5 px-3 text-right ios-num">${s.avg_ticket.toLocaleString()}</td>
                      <td className="py-2.5 px-4 text-right ios-num font-bold text-rose-700 dark:text-rose-400">
                        ${s.total_structured_amount.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                  {structuring.length === 0 && (
                    <tr><td colSpan={4} className="py-6 text-center text-slate-500">No sub-threshold structuring clusters detected.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <GlassPagination
              total={structuring.length}
              page={strPage}
              pageSize={strPageSize}
              onPageChange={setStrPage}
              onPageSizeChange={(sz) => { setStrPageSize(sz); setStrPage(0); }}
              unitLabel="clusters"
            />
          </div>
        </div>

        {/* Merchant Leaderboard + Drilldown */}
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
                <Store className="w-4 h-4 text-azure-600 dark:text-sky-400" />
                Merchant Risk Leaderboard ({merchants.length})
              </h3>
            </div>
            <input
              type="text"
              value={merchSearch}
              onChange={(e) => { setMerchSearch(e.target.value); setMerchPage(0); }}
              placeholder="Search merchant ID, name, MCC, country..."
              className="px-3 py-1.5 rounded-full text-xs bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white placeholder:text-slate-500 w-64"
            />
          </div>
          {selectedMerchant && (
            <div className="px-5 py-3 bg-azure-500/10 border-b border-azure-400/25 flex flex-wrap items-center justify-between gap-2 text-xs">
              <span>
                <strong>{(selectedMerchant.merchant as Record<string, string>)?.merchant_name}</strong> ({(selectedMerchant.merchant as Record<string, string>)?.mcc} • {(selectedMerchant.merchant as Record<string, string>)?.country}) — Top Accounts:{" "}
                {((selectedMerchant.top_accounts as Array<Record<string, string>>) || []).slice(0, 3).map((a) => a.account_id).join(", ")}
              </span>
              <button type="button" onClick={() => setSelectedMerchant(null)} className="underline">Close</button>
            </div>
          )}
          <div ref={merMag.containerRef} onMouseLeave={merMag.onContainerLeave} className="relative overflow-x-auto">
            {merMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/25 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Merchant</th>
                  <th className="py-2.5 px-3">MCC / Country</th>
                  <th className="py-2.5 px-3">Risk</th>
                  <th className="py-2.5 px-3 text-right">Customers / Txns</th>
                  <th className="py-2.5 px-3 text-right">Volume</th>
                  <th className="py-2.5 px-4 text-right">Alerts / Max Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {merchants.slice(merchPage * merchPageSize, (merchPage + 1) * merchPageSize).map((m) => (
                  <tr
                    key={m.merchant_id}
                    onClick={() => api.merchantDetail(m.merchant_id).then(setSelectedMerchant).catch(() => {})}
                    onMouseEnter={(e) => merMag.onRowEnter(e.currentTarget)}
                    className="liquid-row-magnify cursor-pointer"
                  >
                    <td className="py-2.5 px-4">
                      <div className="font-semibold text-slate-950 dark:text-white">{m.merchant_name}</div>
                      <div className="font-mono text-[11px] text-slate-500">{m.merchant_id} • {m.category}</div>
                    </td>
                    <td className="py-2.5 px-3 font-mono">{m.mcc} • {m.country}</td>
                    <td className="py-2.5 px-3">
                      <Badge variant={tierVariant(m.risk_tier)}>{m.risk_tier}</Badge>
                      {m.is_high_risk_mcc && <span className="ml-1 text-[10px] font-bold text-rose-600">HR-MCC</span>}
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num">{m.customer_spread} / {m.txn_count}</td>
                    <td className="py-2.5 px-3 text-right ios-num font-semibold">${m.total_volume.toLocaleString()}</td>
                    <td className="py-2.5 px-4 text-right ios-num font-bold">
                      {m.alert_count} ({m.max_alert_score.toFixed(0)})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <GlassPagination
            total={merchants.length}
            page={merchPage}
            pageSize={merchPageSize}
            onPageChange={setMerchPage}
            onPageSizeChange={(sz) => { setMerchPageSize(sz); setMerchPage(0); }}
            unitLabel="merchants"
          />
        </div>
      </div>
    );
  }

  // Operations, SIEM Outbox, Merge & Jobs mode
  return (
    <div className="space-y-5">
      {/* SLA Radar + Four-Eyes & Queue Rebalance */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <LiquidGlassCard variant="rose" className="rounded-2xl p-4">
          <div className="text-[11px] font-semibold uppercase text-rose-800 dark:text-zinc-300">SLA Breach Radar</div>
          <div className="mt-1 text-2xl font-bold ios-num text-rose-700 dark:text-rose-400">
            {slaRadar?.breached_count ?? 0} Breached / {slaRadar?.at_risk_count ?? 0} At-Risk
          </div>
          <div className="mt-1 text-[11px] text-rose-700/80 dark:text-zinc-400">Cases past or within 8h of SLA policy</div>
        </LiquidGlassCard>

        <LiquidGlassCard variant="amber" className="rounded-2xl p-4 flex items-center justify-between gap-2">
          <div>
            <div className="text-[11px] font-semibold uppercase text-amber-800 dark:text-zinc-300">Four-Eyes Sign-Off Queue</div>
            <div className="mt-1 text-2xl font-bold ios-num text-amber-700 dark:text-amber-300">{pendingEsc.length}</div>
            <div className="mt-1 text-[11px] text-amber-700/80 dark:text-zinc-400">Cases &ge;$25k or ESCALATED</div>
          </div>
          {(user.role === "RISK_REVIEWER" || user.role === "SYSTEM_ADMIN") && (
            <button
              type="button"
              onClick={async () => {
                try {
                  const res = await api.rebalanceQueue(30);
                  onBanner(`Rebalanced ${res.reassigned_count} unassigned case(s) across ${res.analysts_pool.join(", ")}.`);
                  loadOps();
                } catch (err) {
                  onBanner(err instanceof Error ? err.message : "Rebalance failed");
                }
              }}
              className="px-3 py-1.5 rounded-full bg-amber-600 text-white text-xs font-semibold hover:bg-amber-500 transition shrink-0"
            >
              Auto-Rebalance Queue
            </button>
          )}
        </LiquidGlassCard>

        <LiquidGlassCard variant="hero" className="rounded-2xl p-4 text-white flex items-center justify-between gap-2">
          <div>
            <div className="text-[11px] font-semibold uppercase text-white/85">Compliance Archive</div>
            <div className="mt-1 text-lg font-bold">Audit + AST + Manifest</div>
            <div className="mt-1 text-[11px] text-white/85">Regulator-ready JSON bundle</div>
          </div>
          <button
            type="button"
            onClick={() =>
              downloadExport(api.complianceBundleUrl(), "yottaflex_compliance_bundle.json").catch((err) =>
                onBanner(err instanceof Error ? err.message : "Failed to download compliance bundle")
              )
            }
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-white/25 hover:bg-white/35 border border-white/60 text-xs font-bold text-white transition"
          >
            <Download className="w-3.5 h-3.5" /> Bundle
          </button>
        </LiquidGlassCard>
      </div>

      {/* Capacity Forecaster */}
      <div className="liquid-glass rounded-2xl p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-azure-600 dark:text-sky-400" />
            Alert Volume &amp; Investigator Capacity Forecaster
          </h3>
          <div className="flex flex-wrap items-center gap-3 text-xs ios-num">
            <label className="inline-flex items-center gap-1.5">
              Growth: <strong>{growthFactor}x</strong>
              <input type="range" min={0.5} max={3.0} step={0.25} value={growthFactor} onChange={(e) => setGrowthFactor(Number(e.target.value))} className="w-24 accent-azure-600" />
            </label>
            <label className="inline-flex items-center gap-1.5">
              Hrs/Case:
              <input type="number" step={0.5} min={0.5} max={8} value={hoursPerCase} onChange={(e) => setHoursPerCase(Number(e.target.value) || 1)} className="w-14 px-2 py-1 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-center" />
            </label>
            <label className="inline-flex items-center gap-1.5">
              Analysts:
              <input type="number" min={1} max={50} value={analystsAvail} onChange={(e) => setAnalystsAvail(Number(e.target.value) || 1)} className="w-14 px-2 py-1 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-center" />
            </label>
          </div>
        </div>
        {forecast && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs ios-num">
            <div className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
              <div className="text-slate-600 dark:text-zinc-400">Projected Alerts</div>
              <div className="mt-1 text-lg font-bold text-slate-950 dark:text-white">{forecast.projection.projected_alerts.toLocaleString()}</div>
            </div>
            <div className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
              <div className="text-slate-600 dark:text-zinc-400">Projected Open Cases</div>
              <div className="mt-1 text-lg font-bold text-azure-700 dark:text-sky-300">{forecast.projection.projected_open_cases.toLocaleString()}</div>
            </div>
            <div className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
              <div className="text-slate-600 dark:text-zinc-400">Workload Hours</div>
              <div className="mt-1 text-lg font-bold text-slate-950 dark:text-white">{forecast.projection.required_hours}h</div>
            </div>
            <div className="p-3 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
              <div className="text-slate-600 dark:text-zinc-400">Team Utilization</div>
              <div className={`mt-1 text-lg font-bold ${forecast.projection.utilization_pct > 100 ? "text-rose-600 dark:text-rose-400" : "text-emerald-700 dark:text-emerald-400"}`}>
                {forecast.projection.utilization_pct}%
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Case Merge Candidates & Alert Suppression Registry */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="liquid-glass rounded-2xl p-5 space-y-3">
          <h4 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
            <GitMerge className="w-4 h-4 text-azure-600 dark:text-sky-400" />
            Duplicate Case Merge Candidates ({mergeCands.length})
          </h4>
          <div className="space-y-2 max-h-60 overflow-y-auto text-xs">
            {mergeCands.map((mc) => (
              <div key={`${mc.primary_case_id}-${mc.secondary_case_id}`} className="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                <div>
                  <div className="font-mono font-bold text-slate-950 dark:text-white">
                    <button type="button" onClick={() => onOpenCase(mc.primary_case_id)} className="text-azure-700 dark:text-sky-300 hover:underline">{mc.primary_case_id}</button>
                    {" + "}
                    <button type="button" onClick={() => onOpenCase(mc.secondary_case_id)} className="text-azure-700 dark:text-sky-300 hover:underline">{mc.secondary_case_id}</button>
                  </div>
                  <div className="text-[11px] text-slate-600 dark:text-zinc-400">
                    {mc.customer_name} • Combined ${(mc.exp_1 + mc.exp_2).toLocaleString()}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const res = await api.mergeCases({ primary_case_id: mc.primary_case_id, secondary_case_id: mc.secondary_case_id });
                      onBanner(`Merged ${res.secondary_case_id} into ${res.primary_case_id} (${res.migrated_alerts} alert links moved).`);
                      loadOps();
                    } catch (err) {
                      onBanner(err instanceof Error ? err.message : "Merge failed");
                    }
                  }}
                  className="px-2.5 py-1 rounded-full bg-azure-600 text-white font-semibold hover:bg-azure-500 transition shrink-0"
                >
                  Merge
                </button>
              </div>
            ))}
            {mergeCands.length === 0 && (
              <div className="text-slate-500 dark:text-zinc-400 py-4 text-center">No duplicate open cases share overlapping primary customers.</div>
            )}
          </div>
        </div>

        <div className="liquid-glass rounded-2xl p-5 space-y-3">
          <h4 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
            <ShieldOff className="w-4 h-4 text-azure-600 dark:text-sky-400" />
            FP Suppression Allowlist ({suppressions.length})
          </h4>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api.createSuppressionRule({
                  account_id: supAcct,
                  rule_id: supRule,
                  max_amount: Number(supMax) || 5000,
                  reason: supReason || "Verified recurring activity",
                });
                setSupAcct("");
                setSupReason("");
                onBanner("Created active alert suppression rule.");
                loadOps();
              } catch (err) {
                onBanner(err instanceof Error ? err.message : "Failed to create suppression");
              }
            }}
            className="flex flex-wrap gap-2 text-xs"
          >
            <input type="text" required value={supAcct} onChange={(e) => setSupAcct(e.target.value)} placeholder="ACC-CUS-..." className="w-36 px-2.5 py-1 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15" />
            <input type="text" required value={supRule} onChange={(e) => setSupRule(e.target.value)} placeholder="RULE-001" className="w-24 px-2.5 py-1 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 font-mono" />
            <input type="number" required value={supMax} onChange={(e) => setSupMax(e.target.value)} placeholder="Max $" className="w-20 px-2.5 py-1 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 ios-num" />
            <input type="text" value={supReason} onChange={(e) => setSupReason(e.target.value)} placeholder="Rationale..." className="flex-1 min-w-[120px] px-2.5 py-1 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15" />
            <button type="submit" className="px-3 py-1 rounded-full bg-azure-600 text-white font-semibold">Add</button>
          </form>
          <div className="space-y-1.5 max-h-40 overflow-y-auto text-xs">
            {suppressions.map((s) => (
              <div key={s.suppression_id} className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                <div>
                  <span className="font-mono font-bold">{s.account_id}</span> • <Badge variant="BLUE">{s.rule_id}</Badge> &le; ${s.max_amount.toLocaleString()}
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    await api.deactivateSuppressionRule(s.suppression_id);
                    loadOps();
                  }}
                  className="text-rose-600 dark:text-rose-400 underline text-[11px]"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* SIEM Outbox & Pipeline Job Runner */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <Send className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              SIEM Webhook Outbox ({siemOutbox.length})
            </h4>
            <button
              type="button"
              onClick={async () => {
                await api.triggerSiemEvent({ event_type: "COMPLIANCE_HEARTBEAT", severity: "HIGH", entity_id: "WORKBENCH", payload: { actor: user.analyst_code } });
                onBanner("Dispatched dry-run SIEM webhook event.");
                loadOps();
              }}
              className="px-3 py-1 rounded-full bg-azure-600 text-white text-xs font-semibold hover:bg-azure-500 transition"
            >
              Test SIEM Dispatch
            </button>
          </div>
          <div className="space-y-1.5 max-h-52 overflow-y-auto text-xs">
            {siemOutbox.map((ev) => (
              <div key={ev.outbox_id} className="p-2.5 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10 flex justify-between items-center">
                <div>
                  <span className="font-mono font-bold">{ev.event_type}</span> • {ev.entity_id}
                  <div className="text-[10.5px] font-mono text-slate-500">{ev.created_at}</div>
                </div>
                <Badge variant={ev.delivery_status === "DISPATCHED_DRY_RUN" ? "LOW" : "BLUE"}>{ev.delivery_status}</Badge>
              </div>
            ))}
          </div>
        </div>

        <div className="liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              On-Demand Pipeline Jobs
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {(["VALIDATION_SCAN", "SLA_SWEEP", "RING_SCAN"] as const).map((jt) => (
                <button
                  key={jt}
                  type="button"
                  onClick={async () => {
                    const res = await api.runPipelineJob(jt);
                    onBanner(`Job ${res.job_id} (${jt}) finished in ${res.duration_ms}ms.`);
                    loadOps();
                  }}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white/35 dark:bg-white/[0.08] border border-white/60 dark:border-white/15 text-[11px] font-semibold hover:bg-white/60 dark:hover:bg-white/15 transition"
                >
                  <Play className="w-2.5 h-2.5" /> {jt.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5 max-h-52 overflow-y-auto text-xs">
            {pipelineJobs.map((j) => (
              <div key={j.job_id} className="p-2.5 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                <div className="flex justify-between font-mono">
                  <span className="font-bold">{j.job_type}</span>
                  <span>{j.duration_ms}ms • {j.triggered_by}</span>
                </div>
                <div className="text-slate-600 dark:text-zinc-400 mt-0.5">{j.summary}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
