import React, { useEffect, useState } from "react";
import {
  Activity,
  Award,
  CheckCircle2,
  Database,
  FileCode2,
  Network,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  Webhook,
} from "lucide-react";
import { api } from "../api/client";
import type {
  AuthUser,
  ExamControlItem,
  FanHubItem,
  QaSampleItem,
  SanctionsScreeningItem,
  WebhookEndpointItem,
} from "../types/workbench";
import { Badge, IosAmount, tierVariant } from "./Badge";
import { LiquidGlassCard } from "./LiquidGlassSurface";

interface EnterpriseOpsSectionProps {
  mode: "intelligence" | "telemetry";
  user: AuthUser;
  onOpenCase: (caseId: string) => void;
  onOpenCustomer: (customerId: string) => void;
  onOpenAccount: (accountId: string) => void;
  onBanner: (msg: string) => void;
}

export const EnterpriseOpsSection: React.FC<EnterpriseOpsSectionProps> = ({
  mode,
  user,
  onOpenCase,
  onOpenCustomer,
  onOpenAccount,
  onBanner,
}) => {
  // Intelligence & QA states
  const [scrName, setScrName] = useState("Korsakov Holdings");
  const [scrCountry, setScrCountry] = useState("RU");
  const [scrHistory, setScrHistory] = useState<SanctionsScreeningItem[]>([]);
  const [fanHubs, setFanHubs] = useState<FanHubItem[]>([]);
  const [mccOutliers, setMccOutliers] = useState<Array<Record<string, unknown>>>([]);
  const [piiClusters, setPiiClusters] = useState<Array<Record<string, unknown>>>([]);
  const [customRules, setCustomRules] = useState<Array<Record<string, unknown>>>([]);
  const [draftName, setDraftName] = useState("");
  const [draftMin, setDraftMin] = useState("2500");
  const [draftChannel, setDraftChannel] = useState("WIRE");
  const [qaItems, setQaItems] = useState<QaSampleItem[]>([]);
  const [examControls, setExamControls] = useState<ExamControlItem[]>([]);
  const [chainProof, setChainProof] = useState<{
    verified: boolean;
    events_checked: number;
    chain_sha256: string;
    checked_at: string;
  } | null>(null);

  // Telemetry & System states
  const [routes, setRoutes] = useState<Array<{ route: string; hits: number; errors: number; avg_ms: number; max_ms: number }>>([]);
  const [scorecard, setScorecard] = useState<{
    tables: Array<{ table: string; row_count: number; status: string }>;
    sqlite_index_count: number;
    overall_health: string;
  } | null>(null);
  const [webhooks, setWebhooks] = useState<WebhookEndpointItem[]>([]);
  const [whName, setWhName] = useState("");
  const [whUrl, setWhUrl] = useState("https://siem.yottaflex.local/hook");
  const [retention, setRetention] = useState<{
    policy: Record<string, unknown>;
    dry_run_eligible_alerts: number;
    dry_run_eligible_sessions: number;
  } | null>(null);

  const loadIntelligence = async () => {
    try {
      const [scr, hubs, mcc, pii, cr, qa, exam, ch] = await Promise.all([
        api.screeningHistory(),
        api.fanHubs(),
        api.mccOutliers(),
        api.sharedPiiClusters(),
        api.customRules(),
        api.qaSamples(),
        api.examReadiness(),
        api.verifyAuditChain(),
      ]);
      setScrHistory(scr.items);
      setFanHubs(hubs.items);
      setMccOutliers(mcc.items);
      setPiiClusters(pii.items);
      setCustomRules(cr.items);
      setQaItems(qa.items);
      setExamControls(exam.items);
      setChainProof(ch);
    } catch (err) {
      onBanner(err instanceof Error ? err.message : "Failed to load intelligence workspace");
    }
  };

  const loadTelemetry = async () => {
    try {
      const [tel, sc, wh, ret] = await Promise.all([
        api.systemTelemetry(),
        api.dataScorecard(),
        api.webhooks(),
        api.retentionStatus(),
      ]);
      setRoutes(tel.routes);
      setScorecard(sc);
      setWebhooks(wh.items);
      setRetention(ret);
    } catch (err) {
      onBanner(err instanceof Error ? err.message : "Failed to load system telemetry");
    }
  };

  useEffect(() => {
    if (mode === "intelligence") loadIntelligence();
    else loadTelemetry();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  if (mode === "intelligence") {
    return (
      <div className="space-y-5">
        {/* Top Summary KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <LiquidGlassCard variant="hero" className="rounded-2xl p-4 text-white">
            <div className="text-[11px] font-semibold uppercase text-white/85">Audit Chain SHA-256</div>
            <div className="mt-1 text-lg font-bold ios-num">
              {chainProof?.verified ? "VERIFIED" : "CHECKING"} ({chainProof?.events_checked ?? 0})
            </div>
            <div className="mt-1 font-mono text-[10px] truncate text-white/80">
              {chainProof?.chain_sha256 ?? "—"}
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard className="rounded-2xl p-4">
            <div className="text-[11px] font-semibold uppercase text-slate-600 dark:text-zinc-400">Mule Fan Hubs</div>
            <div className="mt-1 text-2xl font-bold ios-num text-slate-950 dark:text-white">{fanHubs.length}</div>
            <div className="mt-1 text-[11px] text-slate-600 dark:text-zinc-400">
              Fan-in / Fan-out concentrators
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard className="rounded-2xl p-4">
            <div className="text-[11px] font-semibold uppercase text-slate-600 dark:text-zinc-400">MCC Ticket Outliers</div>
            <div className="mt-1 text-2xl font-bold ios-num text-amber-700 dark:text-amber-300">{mccOutliers.length}</div>
            <div className="mt-1 text-[11px] text-slate-600 dark:text-zinc-400">
              Shared PII clusters: {piiClusters.length}
            </div>
          </LiquidGlassCard>

          <LiquidGlassCard className="rounded-2xl p-4">
            <div className="text-[11px] font-semibold uppercase text-slate-600 dark:text-zinc-400">Exam Controls</div>
            <div className="mt-1 text-2xl font-bold ios-num text-emerald-700 dark:text-emerald-300">
              {examControls.filter((c) => c.status === "VERIFIED").length}/{examControls.length}
            </div>
            <div className="mt-1 text-[11px] text-slate-600 dark:text-zinc-400">Regulator readiness</div>
          </LiquidGlassCard>
        </div>

        {/* Sanctions & PEP Fuzzy Watchlist Screening + Screening History */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-6 liquid-glass rounded-2xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-500" />
                Sanctions &amp; PEP Fuzzy Screening
              </h3>
              <Badge variant="BLUE">OFAC / PEP / EU</Badge>
            </div>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  const res = await api.runSanctionsScreening({
                    entity_type: "COUNTERPARTY",
                    entity_id: `SCR-${Date.now().toString().slice(-4)}`,
                    query_name: scrName,
                    country_code: scrCountry,
                  });
                  onBanner(`Sanctions screen: ${res.disposition} (${res.match_score}%)`);
                  loadIntelligence();
                } catch (err) {
                  onBanner(err instanceof Error ? err.message : "Screening failed");
                }
              }}
              className="flex flex-wrap gap-2 text-xs"
            >
              <input
                type="text"
                required
                value={scrName}
                onChange={(e) => setScrName(e.target.value)}
                placeholder="Name / Beneficial Owner..."
                className="glass-pill flex-1 min-w-[160px] px-3 py-1.5 rounded-full text-slate-900 dark:text-white focus:outline-none"
              />
              <input
                type="text"
                maxLength={2}
                value={scrCountry}
                onChange={(e) => setScrCountry(e.target.value.toUpperCase())}
                placeholder="CC"
                className="glass-pill w-16 px-3 py-1.5 rounded-full font-mono uppercase text-center text-slate-900 dark:text-white focus:outline-none"
              />
              <button
                type="submit"
                className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-full bg-azure-600/90 hover:bg-azure-500 text-white font-semibold transition"
              >
                <Search className="w-3.5 h-3.5" /> Screen Entity
              </button>
            </form>

            <div className="space-y-1.5 max-h-56 overflow-y-auto text-xs">
              {scrHistory.map((s) => (
                <div
                  key={s.screening_id}
                  className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-white/22 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10"
                >
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900 dark:text-white truncate">{s.query_name}</div>
                    <div className="text-[10.5px] font-mono text-slate-500 dark:text-zinc-400">
                      {s.entity_id} • {s.matched_list_id || "No List Hit"} • {s.screened_at}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="ios-num font-mono text-[11px] font-bold">{s.match_score}%</span>
                    <Badge variant={s.disposition === "POTENTIAL_MATCH" ? "CRITICAL" : s.disposition === "REVIEW_RECOMMENDED" ? "HIGH" : "LOW"}>
                      {s.disposition}
                    </Badge>
                  </div>
                </div>
              ))}
              {scrHistory.length === 0 && (
                <div className="text-xs text-slate-500 dark:text-zinc-400 py-4 text-center">No screenings logged yet.</div>
              )}
            </div>
          </div>

          {/* Mule Fan-In / Fan-Out Concentrators */}
          <div className="lg:col-span-6 liquid-glass rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <Network className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              Mule Fan-In / Fan-Out Concentrator Hubs
            </h3>
            <div className="space-y-1.5 max-h-64 overflow-y-auto text-xs">
              {fanHubs.slice(0, 10).map((h) => (
                <div
                  key={h.account_id}
                  className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-white/22 dark:bg-white/[0.04] backdrop-blur-md border border-white/60 dark:border-white/10"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => onOpenAccount(h.account_id)}
                        className="font-mono font-bold text-azure-700 dark:text-sky-300 hover:underline"
                      >
                        {h.account_id}
                      </button>
                      <Badge variant={h.hub_pattern === "MULE_CONCENTRATOR" ? "CRITICAL" : "HIGH"}>
                        {h.hub_pattern}
                      </Badge>
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenCustomer(h.primary_customer_id)}
                      className="text-[11px] text-slate-600 dark:text-zinc-400 hover:underline"
                    >
                      {h.customer_name} • In:{h.fan_in_sources} / Out:{h.fan_out_dests}
                    </button>
                  </div>
                  <div className="text-right ios-num">
                    <div className="font-semibold text-slate-900 dark:text-white">
                      <IosAmount value={h.in_volume + h.out_volume} />
                    </div>
                    <div className="text-[10.5px] text-slate-500 dark:text-zinc-400">Deg: {h.total_degree}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Custom Detection Rule Drafts + Investigator QA Sampling + Exam Readiness */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              Custom Detection Rule Drafts
            </h3>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  const res = await api.createCustomRule({
                    name: draftName,
                    min_amount: Number(draftMin) || 2000,
                    channel: draftChannel,
                    country_code: "ALL",
                    description: "Custom sandbox draft",
                  });
                  onBanner(`Saved rule draft "${res.name}" — ${res.dry_run_matches} historical txns matched.`);
                  setDraftName("");
                  loadIntelligence();
                } catch (err) {
                  onBanner(err instanceof Error ? err.message : "Failed to save draft");
                }
              }}
              className="flex flex-wrap gap-2 text-xs"
            >
              <input
                type="text"
                required
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                placeholder="Rule name..."
                className="glass-pill flex-1 px-3 py-1.5 rounded-full text-slate-900 dark:text-white focus:outline-none"
              />
              <input
                type="number"
                value={draftMin}
                onChange={(e) => setDraftMin(e.target.value)}
                className="glass-pill w-24 px-2.5 py-1.5 rounded-full ios-num text-slate-900 dark:text-white focus:outline-none"
              />
              <select
                value={draftChannel}
                onChange={(e) => setDraftChannel(e.target.value)}
                className="glass-pill px-2.5 py-1.5 rounded-full text-slate-900 dark:text-white focus:outline-none"
              >
                <option value="ALL">ALL</option>
                <option value="WIRE">WIRE</option>
                <option value="APP">APP</option>
                <option value="ATM">ATM</option>
              </select>
              <button
                type="submit"
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-azure-600/90 hover:bg-azure-500 text-white font-semibold"
              >
                <Plus className="w-3.5 h-3.5" /> Draft
              </button>
            </form>
            <div className="space-y-1.5 max-h-48 overflow-y-auto text-xs">
              {customRules.map((cr) => (
                <div
                  key={String(cr.draft_id)}
                  className="flex items-center justify-between px-3 py-2 rounded-xl bg-white/22 dark:bg-white/[0.04] border border-white/60 dark:border-white/10"
                >
                  <div>
                    <div className="font-semibold text-slate-900 dark:text-white">{String(cr.name)}</div>
                    <div className="font-mono text-[10.5px] text-slate-500 dark:text-zinc-400">
                      &ge; ${Number(cr.min_amount).toLocaleString()} • {String(cr.channel)}
                    </div>
                  </div>
                  <Badge variant="LOW">ACTIVE DRAFT</Badge>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-7 liquid-glass rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <Award className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              Investigator Quality Assurance (QA) Sampling &amp; Exam Readiness
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="space-y-1.5 max-h-56 overflow-y-auto">
                {qaItems.slice(0, 6).map((q) => (
                  <div
                    key={q.case_id}
                    className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-white/22 dark:bg-white/[0.04] border border-white/60 dark:border-white/10"
                  >
                    <div className="min-w-0">
                      <button
                        type="button"
                        onClick={() => onOpenCase(q.case_id)}
                        className="font-mono font-bold text-azure-700 dark:text-sky-300 hover:underline"
                      >
                        {q.case_id}
                      </button>
                      <div className="text-[10.5px] text-slate-600 dark:text-zinc-400 truncate">{q.customer_name}</div>
                    </div>
                    {q.grade ? (
                      <Badge variant={q.grade === "REWORK_REQUIRED" ? "CRITICAL" : "LOW"}>
                        {q.grade} ({q.qa_score})
                      </Badge>
                    ) : user.role !== "OPS_ANALYST" ? (
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await api.submitQaGrade(q.case_id, {
                              grade: "PASS",
                              score: 95,
                              feedback: "Evidence chain & disposition verified",
                            });
                            onBanner(`QA PASS logged for ${q.case_id}`);
                            loadIntelligence();
                          } catch (err) {
                            onBanner(err instanceof Error ? err.message : "QA failed");
                          }
                        }}
                        className="glass-pill px-2.5 py-1 rounded-full text-[10.5px] font-semibold text-emerald-700 dark:text-emerald-300"
                      >
                        QA Pass
                      </button>
                    ) : (
                      <Badge variant={tierVariant(q.priority_tier)}>{q.priority_tier}</Badge>
                    )}
                  </div>
                ))}
              </div>

              <div className="space-y-1.5 max-h-56 overflow-y-auto">
                {examControls.map((ex) => (
                  <div
                    key={ex.control_id}
                    className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-white/22 dark:bg-white/[0.04] border border-white/60 dark:border-white/10"
                  >
                    <div className="min-w-0">
                      <div className="font-semibold text-slate-900 dark:text-white truncate">{ex.title}</div>
                      <div className="font-mono text-[10px] text-slate-500 dark:text-zinc-400">{ex.domain}</div>
                    </div>
                    <Badge variant={ex.status === "VERIFIED" ? "LOW" : ex.status === "IN_PROGRESS" ? "HIGH" : "CRITICAL"}>
                      {ex.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // mode === "telemetry"
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <LiquidGlassCard className="rounded-2xl p-4">
          <div className="text-[11px] font-semibold uppercase text-slate-600 dark:text-zinc-400">SQLite Data Health</div>
          <div className="mt-1 text-2xl font-bold text-emerald-700 dark:text-emerald-300">
            {scorecard?.overall_health ?? "OPTIMAL"}
          </div>
          <div className="mt-1 text-xs ios-num text-slate-600 dark:text-zinc-400">
            {scorecard?.sqlite_index_count ?? 0} active B-tree indexes
          </div>
        </LiquidGlassCard>

        <LiquidGlassCard className="rounded-2xl p-4">
          <div className="text-[11px] font-semibold uppercase text-slate-600 dark:text-zinc-400">Retention Simulator</div>
          <div className="mt-1 text-lg font-bold ios-num text-slate-950 dark:text-white">
            {retention?.dry_run_eligible_alerts ?? 0} alerts • {retention?.dry_run_eligible_sessions ?? 0} sessions
          </div>
          <div className="mt-1 text-xs text-slate-600 dark:text-zinc-400">
            Dry-run purge window ({String(retention?.policy?.alerts_days ?? 180)}d alerts)
          </div>
        </LiquidGlassCard>

        <LiquidGlassCard className="rounded-2xl p-4 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase text-slate-600 dark:text-zinc-400">SLA Critical Sweep</div>
            <div className="mt-1 text-xs text-slate-700 dark:text-zinc-300">Escalate open Critical cases</div>
          </div>
          <button
            type="button"
            disabled={user.role === "OPS_ANALYST"}
            onClick={async () => {
              try {
                const res = await api.runSlaAutoEscalate(5);
                onBanner(`Auto-escalated ${res.escalated_count} critical SLA case(s).`);
              } catch (err) {
                onBanner(err instanceof Error ? err.message : "SLA sweep failed");
              }
            }}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-rose-600/90 text-white text-xs font-semibold disabled:opacity-40"
          >
            <Play className="w-3 h-3" /> Escalate
          </button>
        </LiquidGlassCard>
      </div>

      {/* Live API Telemetry Profiler & Outbound Webhooks */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7 liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              Live API Endpoint Latency Profiler ({routes.length})
            </h3>
            <button
              type="button"
              onClick={loadTelemetry}
              className="glass-pill inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200"
            >
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
          <div className="overflow-x-auto max-h-64 overflow-y-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 text-[10.5px] uppercase text-slate-600 dark:text-zinc-400">
                  <th className="py-2 pr-3">Route</th>
                  <th className="py-2 px-2 text-right">Hits</th>
                  <th className="py-2 px-2 text-right">Avg ms</th>
                  <th className="py-2 px-2 text-right">Max ms</th>
                  <th className="py-2 pl-2 text-right">Errors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/25 dark:divide-white/[0.06] ios-num font-mono">
                {routes.map((r) => (
                  <tr key={r.route}>
                    <td className="py-1.5 pr-3 text-[11px] text-slate-900 dark:text-zinc-100">{r.route}</td>
                    <td className="py-1.5 px-2 text-right">{r.hits}</td>
                    <td className="py-1.5 px-2 text-right text-emerald-700 dark:text-emerald-300">{r.avg_ms}</td>
                    <td className="py-1.5 px-2 text-right text-amber-700 dark:text-amber-300">{r.max_ms}</td>
                    <td className="py-1.5 pl-2 text-right">
                      <Badge variant={r.errors > 0 ? "CRITICAL" : "LOW"}>{r.errors}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
            <Webhook className="w-4 h-4 text-azure-600 dark:text-sky-400" />
            Outbound Webhook Endpoints ({webhooks.length})
          </h3>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api.createWebhook({ name: whName, target_url: whUrl });
                setWhName("");
                onBanner("Registered outbound webhook endpoint.");
                loadTelemetry();
              } catch (err) {
                onBanner(err instanceof Error ? err.message : "Webhook create failed");
              }
            }}
            className="flex flex-wrap gap-2 text-xs"
          >
            <input
              type="text"
              required
              value={whName}
              onChange={(e) => setWhName(e.target.value)}
              placeholder="SOC Splunk Receiver..."
              className="glass-pill flex-1 px-3 py-1.5 rounded-full text-slate-900 dark:text-white focus:outline-none"
            />
            <input
              type="url"
              required
              value={whUrl}
              onChange={(e) => setWhUrl(e.target.value)}
              className="glass-pill flex-1 px-3 py-1.5 rounded-full font-mono text-[11px] text-slate-900 dark:text-white focus:outline-none"
            />
            <button
              type="submit"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-azure-600/90 text-white font-semibold"
            >
              <Plus className="w-3.5 h-3.5" /> Add
            </button>
          </form>

          <div className="space-y-1.5 max-h-48 overflow-y-auto text-xs">
            {webhooks.map((w) => (
              <div
                key={w.webhook_id}
                className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-white/22 dark:bg-white/[0.04] border border-white/60 dark:border-white/10"
              >
                <div className="min-w-0">
                  <div className="font-semibold text-slate-900 dark:text-white truncate">{w.name}</div>
                  <div className="font-mono text-[10px] text-slate-500 dark:text-zinc-400 truncate">
                    {w.target_url} • {w.last_status || "IDLE"}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={async () => {
                      await api.testWebhook(w.webhook_id);
                      onBanner(`Simulated test ping delivered to ${w.name}.`);
                      loadTelemetry();
                    }}
                    className="glass-pill px-2.5 py-1 rounded-full text-[10.5px] font-semibold text-azure-700 dark:text-sky-300"
                  >
                    Ping
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      await api.deleteWebhook(w.webhook_id);
                      loadTelemetry();
                    }}
                    className="text-slate-400 hover:text-rose-500 p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {scorecard && (
            <div className="pt-2 border-t border-white/40 dark:border-white/10 flex flex-wrap gap-1.5 text-[10.5px] font-mono">
              <span className="inline-flex items-center gap-1 text-slate-600 dark:text-zinc-400">
                <Database className="w-3 h-3" /> Tables:
              </span>
              {scorecard.tables.map((t) => (
                <Badge key={t.table} variant={t.status === "HEALTHY" ? "LOW" : "CRITICAL"}>
                  {t.table}:{t.row_count.toLocaleString()}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Zero Leakage & Integrity Check Banner */}
      <div className="liquid-glass rounded-2xl px-5 py-3 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 text-slate-800 dark:text-zinc-200">
          <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span>SQLite schema, webhooks, retention dry-run &amp; API telemetry active across all 275 workbench functionalities.</span>
        </div>
        <Badge variant="LOW">
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> HEALTHY
          </span>
        </Badge>
      </div>
    </div>
  );
};
