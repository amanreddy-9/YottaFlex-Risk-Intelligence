import React, { useEffect, useState } from "react";
import {
  Activity,
  Award,
  Download,
  FileText,
  Globe2,
  Network,
  Scale,
  Search,
  Shield,
  Sliders,
  Tag,
  Users,
} from "lucide-react";
import { api, downloadExport } from "../api/client";
import type {
  AdminUserItem,
  AnalystStatsItem,
  AuthUser,
  CollusionRingItem,
  EntityNetworkResponse,
  ExecutiveDigestResponse,
  SarRegistryItem,
  SlaPolicyItem,
  SystemHealthResponse,
  UnifiedAuditResponse,
  WatchlistTagItem,
} from "../types/workbench";
import { Badge, tierVariant } from "./Badge";
import { EnterpriseOpsSection } from "./EnterpriseOpsSection";
import { ForensicsOpsSection } from "./ForensicsOpsSection";
import { GlassPagination } from "./GlassPagination";
import { LiquidGlassCard, useRowGlassMagnifier } from "./LiquidGlassSurface";

interface GovernanceViewProps {
  user: AuthUser;
  onOpenCase: (caseId: string) => void;
  onOpenCustomer: (customerId: string) => void;
  onOpenAccount: (accountId: string) => void;
  onRefreshQueue?: () => Promise<void>;
}

type SubPanel = "audit" | "sar" | "rings" | "forensics" | "ops" | "intelligence" | "telemetry" | "policies" | "admin";

export const GovernanceView: React.FC<GovernanceViewProps> = ({
  user,
  onOpenCase,
  onOpenCustomer,
  onOpenAccount,
  onRefreshQueue,
}) => {
  const auditMag = useRowGlassMagnifier();
  const sarMag = useRowGlassMagnifier();
  const ringMag = useRowGlassMagnifier();

  const [sub, setSub] = useState<SubPanel>("audit");
  const [banner, setBanner] = useState<string | null>(null);

  // Audit Ledger & Leaderboard
  const [auditSource, setAuditSource] = useState("ALL");
  const [auditSearch, setAuditSearch] = useState("");
  const [auditPage, setAuditPage] = useState(0);
  const [auditPageSize, setAuditPageSize] = useState(30);
  const [auditData, setAuditData] = useState<UnifiedAuditResponse | null>(null);
  const [leaderboard, setLeaderboard] = useState<AnalystStatsItem[]>([]);

  // SAR Registry
  const [sarFilter, setSarFilter] = useState("ALL");
  const [sarPage, setSarPage] = useState(0);
  const [sarPageSize, setSarPageSize] = useState(30);
  const [sarItems, setSarItems] = useState<SarRegistryItem[]>([]);
  const [sarCounts, setSarCounts] = useState<Record<string, number>>({});

  // Collusion Rings & Entity Network Explorer
  const [rings, setRings] = useState<CollusionRingItem[]>([]);
  const [ringPage, setRingPage] = useState(0);
  const [ringPageSize, setRingPageSize] = useState(30);
  const [netInput, setNetInput] = useState("");
  const [entityNet, setEntityNet] = useState<EntityNetworkResponse | null>(null);

  // Watchlists, SLA Policies & Executive Digest
  const [watchlists, setWatchlists] = useState<WatchlistTagItem[]>([]);
  const [wlSearch, setWlSearch] = useState("");
  const [slaItems, setSlaItems] = useState<SlaPolicyItem[]>([]);
  const [digest, setDigest] = useState<ExecutiveDigestResponse | null>(null);

  // Admin Users & System Health
  const [adminUsers, setAdminUsers] = useState<AdminUserItem[]>([]);
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);

  const loadAudit = async () => {
    try {
      const [au, lb] = await Promise.all([
        api.auditEvents({
          source: auditSource,
          search: auditSearch || undefined,
          limit: auditPageSize,
          offset: auditPage * auditPageSize,
        }),
        api.analystStats(),
      ]);
      setAuditData(au);
      setLeaderboard(lb.analysts);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to load audit ledger");
    }
  };

  const loadSar = async () => {
    try {
      const res = await api.sarRegistry(sarFilter);
      setSarItems(res.items);
      setSarCounts(res.counts_by_status);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to load SAR registry");
    }
  };

  const loadRings = async () => {
    try {
      const res = await api.networkRings(2);
      setRings(res.rings);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to load network rings");
    }
  };

  const loadPoliciesAndDigest = async () => {
    try {
      const [wl, sla, dig] = await Promise.all([
        api.watchlistTags({ search: wlSearch || undefined }),
        api.slaPolicies(),
        api.executiveDigest(),
      ]);
      setWatchlists(wl.items);
      setSlaItems(sla.items);
      setDigest(dig);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to load governance policies");
    }
  };

  const loadAdminAndHealth = async () => {
    try {
      const h = await api.systemHealth();
      setHealth(h);
      if (user.role === "SYSTEM_ADMIN" || user.role === "RISK_REVIEWER") {
        const u = await api.adminUsers();
        setAdminUsers(u.users);
      }
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to load telemetry");
    }
  };

  useEffect(() => {
    if (sub === "audit") loadAudit();
    if (sub === "sar") loadSar();
    if (sub === "rings") loadRings();
    if (sub === "policies") loadPoliciesAndDigest();
    if (sub === "admin") loadAdminAndHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sub, auditSource, auditSearch, auditPage, auditPageSize, sarFilter, wlSearch]);

  const handleTransitionSar = async (caseId: string, nextStatus: "READY_FOR_FILING" | "SUBMITTED") => {
    try {
      await api.transitionSarStatus(caseId, {
        sar_status: nextStatus,
        note: `Governance transition to ${nextStatus}`,
      });
      setBanner(`Case ${caseId} SAR status updated to ${nextStatus}.`);
      await loadSar();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "SAR status update failed");
    }
  };

  const handleExploreEntity = async (entityId: string) => {
    if (!entityId.trim()) return;
    try {
      const net = await api.entityNetwork(entityId.trim());
      setEntityNet(net);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Entity network lookup failed");
    }
  };

  const handleSaveSla = async () => {
    try {
      const updates = slaItems.map((it) => ({
        entity_scope: it.entity_scope,
        tier: it.tier,
        sla_hours: Number(it.sla_hours),
      }));
      const res = await api.updateSlaPolicies(updates);
      setSlaItems(res.items);
      setBanner("SLA Escalation Policies saved cleanly.");
      if (onRefreshQueue) await onRefreshQueue();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to update SLA policies");
    }
  };

  const handleRoleChange = async (targetUser: AdminUserItem, nextRole: string) => {
    try {
      await api.updateAdminUser(targetUser.user_id, { role: nextRole });
      setBanner(`Updated role for ${targetUser.full_name} to ${nextRole}.`);
      await loadAdminAndHealth();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to update user role");
    }
  };

  const handleToggleActive = async (targetUser: AdminUserItem) => {
    try {
      await api.updateAdminUser(targetUser.user_id, { is_active: !targetUser.is_active });
      setBanner(`Toggled active state for ${targetUser.full_name}.`);
      await loadAdminAndHealth();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to toggle user active status");
    }
  };

  const tabs: Array<{ id: SubPanel; label: string; icon: React.ReactNode }> = [
    { id: "audit", label: "Audit Ledger & Stats", icon: <Scale className="w-3.5 h-3.5" /> },
    { id: "sar", label: "SAR Filing Registry", icon: <FileText className="w-3.5 h-3.5" /> },
    { id: "rings", label: "Collusion Rings & Links", icon: <Network className="w-3.5 h-3.5" /> },
    { id: "forensics", label: "Forensics Lab", icon: <Globe2 className="w-3.5 h-3.5" /> },
    { id: "ops", label: "Ops, SIEM & Merge", icon: <Activity className="w-3.5 h-3.5" /> },
    { id: "intelligence", label: "Sanctions, QA & Hubs", icon: <Award className="w-3.5 h-3.5" /> },
    { id: "telemetry", label: "API Telemetry & Hooks", icon: <Sliders className="w-3.5 h-3.5" /> },
    { id: "policies", label: "Watchlist, SLA & Digest", icon: <Sliders className="w-3.5 h-3.5" /> },
    { id: "admin", label: "RBAC Users & Health", icon: <Shield className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="space-y-5">
      {/* Sub-navigation glass pill bar */}
      <div className="liquid-glass rounded-2xl p-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSub(t.id)}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold transition ${
                sub === t.id
                  ? "bg-azure-600 text-white shadow-sm"
                  : "glass-pill text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12]"
              }`}
            >
              {t.icon}
              <span>{t.label}</span>
            </button>
          ))}
        </div>

        <div className="text-xs font-mono text-slate-600 dark:text-zinc-400">
          Governance Console • Role: <strong className="text-slate-900 dark:text-white">{user.role}</strong>
        </div>
      </div>

      {banner && (
        <div className="liquid-glass rounded-2xl px-4 py-2.5 text-xs font-semibold text-azure-800 dark:text-sky-200 flex items-center justify-between">
          <span>{banner}</span>
          <button type="button" onClick={() => setBanner(null)} className="underline">
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Unified Audit Ledger & Analyst Leaderboard */}
      {sub === "audit" && (
        <div className="space-y-5">
          {/* Analyst Leaderboard */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {leaderboard.slice(0, 3).map((an, idx) => (
              <LiquidGlassCard key={an.analyst_id} variant={idx === 0 ? "hero" : "glass"} className={`rounded-2xl p-4 ${idx === 0 ? "text-white" : ""}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Award className={`w-4 h-4 ${idx === 0 ? "text-amber-300" : "text-azure-600 dark:text-sky-400"}`} />
                    <span className="text-xs font-bold">{an.full_name}</span>
                  </div>
                  <span className="font-mono text-[10.5px] opacity-80">{an.analyst_id}</span>
                </div>
                <div className="mt-2.5 grid grid-cols-3 gap-2 text-[11px] ios-num">
                  <div>
                    <div className="opacity-75">Cases Resolved</div>
                    <div className="text-base font-bold">{an.cases_resolved}/{an.assigned_cases}</div>
                  </div>
                  <div>
                    <div className="opacity-75">Alerts Triaged</div>
                    <div className="text-base font-bold">{an.alerts_triaged}</div>
                  </div>
                  <div>
                    <div className="opacity-75">Quarantine / Actions</div>
                    <div className="text-base font-bold">{an.quarantine_reviews + an.actions_logged}</div>
                  </div>
                </div>
              </LiquidGlassCard>
            ))}
          </div>

          <div className="liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                  Unified Immutable Compliance Audit Ledger
                </h3>
                <p className="text-xs font-mono text-slate-600 dark:text-zinc-400">
                  Batch SHA-256 Digest: {auditData?.batch_digest ?? "—"} • {auditData?.total ?? 0} matching events
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 dark:text-zinc-400" />
                  <input
                    type="text"
                    value={auditSearch}
                    onChange={(e) => {
                      setAuditSearch(e.target.value);
                      setAuditPage(0);
                    }}
                    placeholder="Entity, Actor, Action..."
                    className="glass-pill pl-8 pr-3 py-1.5 rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400 focus:outline-none"
                  />
                </div>
                <select
                  value={auditSource}
                  onChange={(e) => {
                    setAuditSource(e.target.value);
                    setAuditPage(0);
                  }}
                  className="glass-pill px-3 py-1.5 rounded-full text-xs text-slate-900 dark:text-white focus:outline-none"
                >
                  <option value="ALL">All Audit Streams</option>
                  <option value="CASE">CASE Dispositions</option>
                  <option value="ALERT">ALERT Triage</option>
                  <option value="QUARANTINE">QUARANTINE Reviews</option>
                  <option value="RISK_ENGINE">RISK_ENGINE Runs</option>
                  <option value="AUTH">AUTH &amp; RBAC</option>
                </select>
                <button
                  type="button"
                  onClick={() =>
                    downloadExport(
                      api.auditExportUrl("csv", { source: auditSource, search: auditSearch || undefined }),
                      "yottaflex_audit_ledger.csv"
                    ).catch((e) => setBanner(e instanceof Error ? e.message : "Export failed"))
                  }
                  className="glass-pill inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
                >
                  <Download className="w-3.5 h-3.5" /> CSV
                </button>
                <button
                  type="button"
                  onClick={() =>
                    downloadExport(
                      api.auditExportUrl("json", { source: auditSource, search: auditSearch || undefined }),
                      "yottaflex_audit_ledger.json"
                    ).catch((e) => setBanner(e instanceof Error ? e.message : "Export failed"))
                  }
                  className="glass-pill inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
                >
                  <Download className="w-3.5 h-3.5" /> JSON
                </button>
              </div>
            </div>

            <div ref={auditMag.containerRef} onMouseLeave={auditMag.onContainerLeave} className="relative overflow-x-auto max-h-[520px]">
              {auditMag.lensElement}
              <table className="w-full text-left border-collapse text-xs">
                <thead className="sticky top-0 z-10 bg-white/55 dark:bg-black/75 backdrop-blur-md border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <tr>
                    <th className="py-2.5 px-4">Timestamp</th>
                    <th className="py-2.5 px-3">Stream</th>
                    <th className="py-2.5 px-3">Entity</th>
                    <th className="py-2.5 px-3">Actor</th>
                    <th className="py-2.5 px-3">Action &amp; Detail</th>
                    <th className="py-2.5 px-4 text-right">Digest</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                  {(auditData?.items || []).map((ev) => (
                    <tr
                      key={ev.event_id}
                      onMouseEnter={(e) => auditMag.onRowEnter(e.currentTarget)}
                      className="liquid-row-magnify"
                    >
                      <td className="py-2.5 px-4 font-mono text-[11px] text-slate-600 dark:text-zinc-400">{ev.occurred_at}</td>
                      <td className="py-2.5 px-3">
                        <Badge variant={tierVariant(ev.severity)}>{ev.source}</Badge>
                      </td>
                      <td className="py-2.5 px-3 font-mono font-semibold text-slate-950 dark:text-white">
                        {ev.entity_id.startsWith("CASE-") ? (
                          <button type="button" onClick={() => onOpenCase(ev.entity_id)} className="text-azure-700 dark:text-sky-300 hover:underline">
                            {ev.entity_id}
                          </button>
                        ) : (
                          ev.entity_id
                        )}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-700 dark:text-zinc-300">{ev.actor_id}</td>
                      <td className="py-2.5 px-3">
                        <span className="font-semibold text-slate-900 dark:text-white">{ev.action_type}</span>{" "}
                        <span className="text-slate-600 dark:text-zinc-400">{ev.detail}</span>
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-[10.5px] text-slate-500 dark:text-zinc-500">
                        {ev.integrity_hash}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <GlassPagination
              total={auditData?.total ?? 0}
              page={auditPage}
              pageSize={auditPageSize}
              onPageChange={setAuditPage}
              onPageSizeChange={(sz) => {
                setAuditPageSize(sz);
                setAuditPage(0);
              }}
              unitLabel="events"
            />
          </div>
        </div>
      )}

      {/* 2. Centralized SAR Registry & Readiness Scoring */}
      {sub === "sar" && (
        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                SAR Draft &amp; Filing Governance Registry
              </h3>
              <p className="text-xs text-slate-600 dark:text-zinc-400">
                Drafts: {sarCounts.DRAFT || 0} • Ready: {sarCounts.READY_FOR_FILING || 0} • Submitted: {sarCounts.SUBMITTED || 0}
              </p>
            </div>
            <select
              value={sarFilter}
              onChange={(e) => {
                setSarFilter(e.target.value);
                setSarPage(0);
              }}
              className="glass-pill px-3 py-1.5 rounded-full text-xs text-slate-900 dark:text-white focus:outline-none"
            >
              <option value="ALL">All SAR Lifecycle States</option>
              <option value="DRAFT">DRAFT</option>
              <option value="READY_FOR_FILING">READY_FOR_FILING</option>
              <option value="SUBMITTED">SUBMITTED</option>
            </select>
          </div>

          <div ref={sarMag.containerRef} onMouseLeave={sarMag.onContainerLeave} className="relative overflow-x-auto">
            {sarMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Case &amp; Customer</th>
                  <th className="py-2.5 px-3 text-right">Exposure</th>
                  <th className="py-2.5 px-3">Completeness</th>
                  <th className="py-2.5 px-3">SAR Status</th>
                  <th className="py-2.5 px-3">Narrative Excerpt</th>
                  <th className="py-2.5 px-4 text-right">Lifecycle Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {sarItems.slice(sarPage * sarPageSize, (sarPage + 1) * sarPageSize).map((it) => (
                  <tr key={it.case_id} onMouseEnter={(e) => sarMag.onRowEnter(e.currentTarget)} className="liquid-row-magnify">
                    <td className="py-3 px-4">
                      <button type="button" onClick={() => onOpenCase(it.case_id)} className="font-mono font-bold text-azure-700 dark:text-sky-300 hover:underline">
                        {it.case_id}
                      </button>
                      <div className="text-slate-700 dark:text-zinc-300">{it.customer_name} ({it.customer_id})</div>
                    </td>
                    <td className="py-3 px-3 text-right ios-num font-semibold text-slate-950 dark:text-white">
                      ${it.total_exposure_amount.toLocaleString()}
                    </td>
                    <td className="py-3 px-3">
                      <Badge variant={it.readiness.readiness_score >= 80 ? "LOW" : it.readiness.readiness_score >= 60 ? "MEDIUM" : "HIGH"}>
                        {it.readiness.readiness_score}% ({it.readiness.passed_criteria}/5)
                      </Badge>
                    </td>
                    <td className="py-3 px-3">
                      <Badge variant={it.sar_status === "SUBMITTED" ? "LOW" : it.sar_status === "READY_FOR_FILING" ? "BLUE" : "NEUTRAL"}>
                        {it.sar_status}
                      </Badge>
                    </td>
                    <td className="py-3 px-3 max-w-xs truncate text-slate-600 dark:text-zinc-400" title={it.sar_excerpt}>
                      {it.sar_excerpt || "—"}
                    </td>
                    <td className="py-3 px-4 text-right space-x-1.5">
                      {it.sar_status === "DRAFT" && (
                        <button
                          type="button"
                          onClick={() => handleTransitionSar(it.case_id, "READY_FOR_FILING")}
                          className="px-3 py-1 rounded-full bg-azure-600/90 hover:bg-azure-500 border border-white/50 dark:border-transparent text-white font-semibold transition"
                        >
                          Mark Ready
                        </button>
                      )}
                      {it.sar_status !== "SUBMITTED" && (user.role === "RISK_REVIEWER" || user.role === "SYSTEM_ADMIN") && (
                        <button
                          type="button"
                          onClick={() => handleTransitionSar(it.case_id, "SUBMITTED")}
                          className="px-3 py-1 rounded-full bg-emerald-600/90 hover:bg-emerald-500 border border-white/50 dark:border-transparent text-white font-semibold transition"
                        >
                          Submit SAR
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {sarItems.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500 dark:text-zinc-400">
                      No SAR drafts saved yet. Open any Dossier and click Auto-Draft SAR to begin tracking.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <GlassPagination
            total={sarItems.length}
            page={sarPage}
            pageSize={sarPageSize}
            onPageChange={setSarPage}
            onPageSizeChange={(sz) => {
              setSarPageSize(sz);
              setSarPage(0);
            }}
            unitLabel="SARs"
          />
        </div>
      )}

      {/* 3. Shared-Device Collusion Rings & Multi-Hop Entity Link Explorer */}
      {sub === "rings" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-7 liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Shared-Device &amp; Cross-Customer Collusion Rings ({rings.length})
              </h3>
              <p className="text-xs text-slate-600 dark:text-zinc-400">
                Ranked by distinct customer linkage, emulator risk &amp; cumulative alert exposure
              </p>
            </div>
            <div ref={ringMag.containerRef} onMouseLeave={ringMag.onContainerLeave} className="relative overflow-x-auto">
              {ringMag.lensElement}
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                    <th className="py-2.5 px-4">Ring / Device</th>
                    <th className="py-2.5 px-3">Fingerprint</th>
                    <th className="py-2.5 px-3 text-right">Cust / Acct</th>
                    <th className="py-2.5 px-3 text-right">Alert Exposure</th>
                    <th className="py-2.5 px-4 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                  {rings.slice(ringPage * ringPageSize, (ringPage + 1) * ringPageSize).map((r) => (
                    <tr key={r.ring_id} onMouseEnter={(e) => ringMag.onRowEnter(e.currentTarget)} className="liquid-row-magnify">
                      <td className="py-2.5 px-4 font-mono">
                        <div className="font-bold text-slate-950 dark:text-white">{r.ring_id}</div>
                        <div className="text-[11px] text-slate-600 dark:text-zinc-400">{r.device_id}</div>
                      </td>
                      <td className="py-2.5 px-3">
                        <div>{r.os_family} • {r.ip_country}</div>
                        {r.is_emulator && <Badge variant="CRITICAL">EMULATOR</Badge>}
                      </td>
                      <td className="py-2.5 px-3 text-right ios-num font-bold text-slate-900 dark:text-white">
                        {r.customer_count} / {r.account_count}
                      </td>
                      <td className="py-2.5 px-3 text-right ios-num font-mono">
                        ${r.alert_exposure.toLocaleString()} ({r.alert_count})
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setNetInput(r.device_id);
                            handleExploreEntity(r.device_id);
                          }}
                          className="px-3 py-1 rounded-full bg-azure-600/90 hover:bg-azure-500 border border-white/50 dark:border-transparent text-white font-semibold transition"
                        >
                          Trace Graph
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <GlassPagination
              total={rings.length}
              page={ringPage}
              pageSize={ringPageSize}
              onPageChange={setRingPage}
              onPageSizeChange={(sz) => {
                setRingPageSize(sz);
                setRingPage(0);
              }}
              unitLabel="rings"
            />
          </div>

          <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-4 self-start">
            <h4 className="text-sm font-semibold text-slate-950 dark:text-white">Multi-Hop Entity Link Explorer</h4>
            <div className="flex gap-2">
              <input
                type="text"
                value={netInput}
                onChange={(e) => setNetInput(e.target.value)}
                placeholder="CUS-000001, ACC-..., CASE-..., or DEV-..."
                className="glass-pill flex-1 px-3.5 py-1.5 rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => handleExploreEntity(netInput)}
                className="px-4 py-1.5 rounded-full bg-azure-600/90 hover:bg-azure-500 border border-white/50 dark:border-transparent text-white text-xs font-semibold transition"
              >
                Explore
              </button>
            </div>

            {entityNet && (
              <div className="space-y-3 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-white/50 dark:border-white/10">
                  <div>
                    <div className="font-mono font-bold text-slate-950 dark:text-white">{entityNet.root_id}</div>
                    <div className="text-slate-600 dark:text-zinc-400">{entityNet.root_type} • {entityNet.root_label}</div>
                  </div>
                  <div className="font-mono text-right">
                    <div>{entityNet.node_count} nodes / {entityNet.edge_count} edges</div>
                    <div className="text-azure-700 dark:text-sky-300 font-bold">
                      Transfers: ${entityNet.transfer_exposure.toLocaleString()}
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5 max-h-60 overflow-y-auto">
                  {entityNet.nodes.map((n) => (
                    <div key={n.id} className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                      <div className="min-w-0">
                        <span className="font-mono font-semibold text-slate-900 dark:text-white mr-2">{n.id}</span>
                        <span className="text-slate-600 dark:text-zinc-400 truncate">{n.label}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Badge variant={tierVariant(n.risk)}>{n.type}</Badge>
                        {n.type === "CUSTOMER" && (
                          <button type="button" onClick={() => onOpenCustomer(n.id)} className="text-azure-700 dark:text-sky-300 underline">
                            Open
                          </button>
                        )}
                        {n.type === "ACCOUNT" && (
                          <button type="button" onClick={() => onOpenAccount(n.id)} className="text-azure-700 dark:text-sky-300 underline">
                            Open
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. Watchlist Registry, SLA Policy Manager & Executive Digest */}
      {sub === "policies" && (
        <div className="space-y-5">
          {digest && (
            <div className="liquid-glass rounded-2xl p-5 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                    Five-Pillar Executive Compliance Digest
                  </h3>
                  <p className="text-xs font-mono text-slate-600 dark:text-zinc-400">
                    Scale `{digest.scale}` • Seed `{digest.seed}` • {digest.generated_at}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      downloadExport(api.executiveDigestExportUrl("md"), "yottaflex_executive_digest.md").catch((e) =>
                        setBanner(e instanceof Error ? e.message : "Export failed")
                      )
                    }
                    className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-azure-600/90 hover:bg-azure-500 border border-white/50 dark:border-transparent text-white transition"
                  >
                    <Download className="w-3.5 h-3.5" /> Digest .MD
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      downloadExport(api.executiveDigestExportUrl("json"), "yottaflex_executive_digest.json").catch((e) =>
                        setBanner(e instanceof Error ? e.message : "Export failed")
                      )
                    }
                    className="glass-pill inline-flex items-center gap-1 px-3.5 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
                  >
                    <Download className="w-3.5 h-3.5" /> .JSON
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
                <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                  <div className="text-slate-500 dark:text-zinc-400 font-semibold">High/Crit Exposure</div>
                  <div className="mt-1 text-base font-bold ios-num text-slate-950 dark:text-white">
                    {digest.pillars.exposure_concentration.high_critical_share_pct}%
                  </div>
                </div>
                <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                  <div className="text-slate-500 dark:text-zinc-400 font-semibold">Compression Ratio</div>
                  <div className="mt-1 text-base font-bold ios-num text-azure-700 dark:text-sky-300">
                    {digest.pillars.alert_compression.compression_ratio}x
                  </div>
                </div>
                <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                  <div className="text-slate-500 dark:text-zinc-400 font-semibold">Case Resolution</div>
                  <div className="mt-1 text-base font-bold ios-num text-emerald-700 dark:text-emerald-400">
                    {digest.pillars.case_resolution.resolution_pct}%
                  </div>
                </div>
                <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                  <div className="text-slate-500 dark:text-zinc-400 font-semibold">Quarantine Shield</div>
                  <div className="mt-1 text-base font-bold ios-num text-rose-700 dark:text-rose-400">
                    {digest.pillars.quarantine_shield.total_quarantined} isolated
                  </div>
                </div>
                <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                  <div className="text-slate-500 dark:text-zinc-400 font-semibold">SARs / Rings</div>
                  <div className="mt-1 text-base font-bold ios-num text-slate-950 dark:text-white">
                    {digest.pillars.sar_readiness.total_sar_tracked} / {digest.pillars.sar_readiness.shared_device_rings}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* SLA Policy Matrix */}
            <div className="liquid-glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-slate-950 dark:text-white">SLA Target Policies (Hours)</h4>
                {user.role === "SYSTEM_ADMIN" && (
                  <button
                    type="button"
                    onClick={handleSaveSla}
                    className="px-3.5 py-1.5 rounded-full bg-azure-600/90 hover:bg-azure-500 border border-white/50 dark:border-transparent text-white text-xs font-semibold transition"
                  >
                    Save Policies
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2.5 text-xs">
                {slaItems.map((it) => (
                  <div key={it.policy_key} className="flex items-center justify-between px-3 py-2 rounded-xl bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                    <span className="font-mono font-semibold text-slate-800 dark:text-zinc-200">{it.policy_key}</span>
                    <input
                      type="number"
                      min={1}
                      max={720}
                      disabled={user.role !== "SYSTEM_ADMIN"}
                      value={it.sla_hours}
                      onChange={(e) => {
                        const val = Number(e.target.value) || 1;
                        setSlaItems((prev) => prev.map((x) => (x.policy_key === it.policy_key ? { ...x, sla_hours: val } : x)));
                      }}
                      className="glass-pill w-16 px-2.5 py-1 rounded-full text-right ios-num text-slate-900 dark:text-white disabled:opacity-70 focus:outline-none"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Watchlist Registry */}
            <div className="liquid-glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-1.5">
                  <Tag className="w-4 h-4 text-azure-600 dark:text-sky-400" />
                  Watchlist Registry ({watchlists.length})
                </h4>
                <input
                  type="text"
                  value={wlSearch}
                  onChange={(e) => setWlSearch(e.target.value)}
                  placeholder="Filter entity or tag..."
                  className="glass-pill px-3 py-1 rounded-full text-xs text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-zinc-400 focus:outline-none"
                />
              </div>
              <div className="space-y-1.5 max-h-60 overflow-y-auto text-xs">
                {watchlists.map((w) => (
                  <div key={w.tag_id} className="flex items-center justify-between px-3 py-2 rounded-xl bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                    <div>
                      <span className="font-mono font-bold text-slate-950 dark:text-white mr-2">{w.entity_id}</span>
                      <Badge variant="CRITICAL">{w.tag}</Badge>
                      {w.note && <div className="text-[11px] text-slate-600 dark:text-zinc-400 mt-0.5">{w.note}</div>}
                    </div>
                    <span className="font-mono text-[10.5px] text-slate-500 dark:text-zinc-400">{w.actor_id}</span>
                  </div>
                ))}
                {watchlists.length === 0 && (
                  <div className="text-xs text-slate-500 dark:text-zinc-400 py-4 text-center">No watchlist tags registered yet.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5. RBAC User Directory & System Health Telemetry */}
      {sub === "admin" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {health && (
            <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  SQLite &amp; Runtime Telemetry
                </h4>
                <Badge variant="LOW">{health.status}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2.5 text-xs">
                <div className="p-2.5 rounded-xl bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                  <div className="text-slate-500 dark:text-zinc-400">DB Size / Indexes</div>
                  <div className="ios-num font-mono font-bold text-slate-950 dark:text-white mt-0.5">
                    {health.db_size_mb} MB / {health.sqlite_index_count}
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                  <div className="text-slate-500 dark:text-zinc-400">Active Sessions</div>
                  <div className="ios-num font-mono font-bold text-slate-950 dark:text-white mt-0.5">{health.active_sessions}</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-1.5 text-[11px] font-mono">
                {Object.entries(health.table_counts).map(([tbl, cnt]) => (
                  <div key={tbl} className="flex justify-between px-2.5 py-1 rounded-full bg-white/20 dark:bg-white/[0.04] border border-white/50 dark:border-white/10">
                    <span className="text-slate-600 dark:text-zinc-400">{tbl}</span>
                    <span className="ios-num font-bold text-slate-900 dark:text-white">{cnt.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="lg:col-span-7 liquid-glass rounded-2xl p-5 space-y-3">
            <h4 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <Users className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              RBAC User &amp; Access Governance
            </h4>
            {adminUsers.length === 0 ? (
              <div className="text-xs text-slate-600 dark:text-zinc-400 py-6">
                Sign in as <code>SYSTEM_ADMIN</code> or <code>RISK_REVIEWER</code> to inspect and manage workbench user accounts.
              </div>
            ) : (
              <div className="space-y-2 text-xs">
                {adminUsers.map((u) => (
                  <div key={u.user_id} className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
                    <div>
                      <div className="font-bold text-slate-950 dark:text-white">
                        {u.full_name} <span className="font-mono text-[11px] text-slate-500">({u.analyst_code})</span>
                      </div>
                      <div className="font-mono text-[11px] text-slate-600 dark:text-zinc-400">
                        {u.email} • Sessions: {u.active_sessions}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        disabled={user.role !== "SYSTEM_ADMIN" || u.user_id === user.user_id}
                        value={u.role}
                        onChange={(e) => handleRoleChange(u, e.target.value)}
                        className="glass-pill px-3 py-1 rounded-full text-xs text-slate-900 dark:text-white disabled:opacity-60 focus:outline-none"
                      >
                        <option value="OPS_ANALYST">OPS_ANALYST</option>
                        <option value="RISK_REVIEWER">RISK_REVIEWER</option>
                        <option value="SYSTEM_ADMIN">SYSTEM_ADMIN</option>
                      </select>
                      {user.role === "SYSTEM_ADMIN" && u.user_id !== user.user_id && (
                        <button
                          type="button"
                          onClick={() => handleToggleActive(u)}
                          className={`px-3 py-1 rounded-full border border-white/40 dark:border-transparent font-semibold text-white transition ${
                            u.is_active ? "bg-rose-600/90 hover:bg-rose-500" : "bg-emerald-600/90 hover:bg-emerald-500"
                          }`}
                        >
                          {u.is_active ? "Lock" : "Activate"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {(sub === "forensics" || sub === "ops") && (
        <ForensicsOpsSection
          mode={sub}
          user={user}
          onOpenCase={onOpenCase}
          onOpenAccount={onOpenAccount}
          onOpenCustomer={onOpenCustomer}
          onBanner={setBanner}
        />
      )}

      {(sub === "intelligence" || sub === "telemetry") && (
        <EnterpriseOpsSection
          mode={sub}
          user={user}
          onOpenCase={onOpenCase}
          onOpenAccount={onOpenAccount}
          onOpenCustomer={onOpenCustomer}
          onBanner={setBanner}
        />
      )}
    </div>
  );
};
