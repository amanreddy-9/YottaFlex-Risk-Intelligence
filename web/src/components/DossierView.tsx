import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileText,
  Link2,
  ShieldAlert,
  Tag,
  Unlink,
  UserCheck,
  XCircle,
} from "lucide-react";
import { api, downloadExport } from "../api/client";
import type { CaseCommentItem, CaseDossier, CasePinItem, PlaybookItem, SimilarCaseItem } from "../types/workbench";
import { Badge, IosAmount, statusVariant, tierVariant } from "./Badge";
import { GlassPagination } from "./GlassPagination";
import { NetworkGraph } from "./NetworkGraph";
import { WaterfallCard } from "./WaterfallCard";

interface DossierViewProps {
  dossier: CaseDossier | null;
  darkMode: boolean;
  onBack: () => void;
  onSubmitAction: (payload: { analyst_id: string; action_type: string; rationale: string }) => Promise<string>;
  onDossierUpdated: (caseId: string) => Promise<void>;
  onOpenCase?: (caseId: string) => void;
}

export const DossierView: React.FC<DossierViewProps> = ({
  dossier,
  darkMode,
  onBack,
  onSubmitAction,
  onDossierUpdated,
  onOpenCase,
}) => {
  const [analystId, setAnalystId] = useState("ANL-003");
  const [actionType, setActionType] = useState("ESCALATE");
  const [rationale, setRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);

  // Functions 111-112, 115-116, 121-125 local state
  const [assignee, setAssignee] = useState("ANL-001");
  const [overrideTier, setOverrideTier] = useState("CRITICAL");
  const [overrideScore, setOverrideScore] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [linkAlertId, setLinkAlertId] = useState("");
  const [opsMsg, setOpsMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [rulesReviewed, setRulesReviewed] = useState(false);
  const [ledgerReconciled, setLedgerReconciled] = useState(false);
  const [networkVerified, setNetworkVerified] = useState(false);
  const [kycCorroborated, setKycCorroborated] = useState(false);
  const [checklistNotes, setChecklistNotes] = useState("");

  const [sarText, setSarText] = useState("");
  const [sarUpdatedAt, setSarUpdatedAt] = useState<string | null>(null);

  const [tagTargetType, setTagTargetType] = useState<"CUSTOMER" | "ACCOUNT">("CUSTOMER");
  const [tagName, setTagName] = useState("MULE_SUSPECT");
  const [tagNote, setTagNote] = useState("");
  const [similarCases, setSimilarCases] = useState<SimilarCaseItem[]>([]);
  const [txPage, setTxPage] = useState(0);
  const [txPageSize, setTxPageSize] = useState(30);
  const [playbooks, setPlaybooks] = useState<PlaybookItem[]>([]);
  const [selectedPlaybook, setSelectedPlaybook] = useState("PB-STRUCTURING");
  const [pins, setPins] = useState<CasePinItem[]>([]);
  const [pinEntityId, setPinEntityId] = useState("");
  const [pinType, setPinType] = useState<"PINNED_PROOF" | "CORROBORATING" | "EXCULPATORY">("PINNED_PROOF");
  const [pinNote, setPinNote] = useState("");
  const [comments, setComments] = useState<CaseCommentItem[]>([]);
  const [commentBody, setCommentBody] = useState("");
  const [commentVis, setCommentVis] = useState<"INTERNAL" | "COMPLIANCE">("INTERNAL");
  const [rfiMarkdown, setRfiMarkdown] = useState<string | null>(null);
  const [goamlXml, setGoamlXml] = useState<string | null>(null);
  const [handoffs, setHandoffs] = useState<Array<Record<string, unknown>>>([]);
  const [handoffTo, setHandoffTo] = useState("ANL-002");
  const [handoffSummary, setHandoffSummary] = useState("");
  const [seals, setSeals] = useState<Array<Record<string, unknown>>>([]);
  const [whatIfScore, setWhatIfScore] = useState<{ original_score: number; projected_score: number; projected_tier: string } | null>(null);

  useEffect(() => {
    api.playbooks().then((res) => setPlaybooks(res.items)).catch(() => {});
  }, []);

  useEffect(() => {
    setTxPage(0);
    setRfiMarkdown(null);
    setGoamlXml(null);
    setWhatIfScore(null);
    if (!dossier?.case.case_id) {
      setSimilarCases([]);
      setPins([]);
      setComments([]);
      setHandoffs([]);
      setSeals([]);
      return;
    }
    const cid = dossier.case.case_id;
    api.similarCases(cid).then((res) => setSimilarCases(res.items)).catch(() => setSimilarCases([]));
    api.casePins(cid).then((res) => setPins(res.items)).catch(() => setPins([]));
    api.caseComments(cid).then((res) => setComments(res.items)).catch(() => setComments([]));
    api.caseHandoffs(cid).then((res) => setHandoffs(res.items)).catch(() => setHandoffs([]));
    api.caseSeals(cid).then((res) => setSeals(res.items)).catch(() => setSeals([]));
  }, [dossier?.case.case_id]);

  useEffect(() => {
    if (!dossier) return;
    setAssignee(dossier.case.assigned_analyst_id || "ANL-001");
    setOverrideTier(dossier.case.effective_priority_tier || dossier.case.priority_tier);
    setOverrideScore(
      dossier.triage_meta?.priority_override_score != null
        ? String(dossier.triage_meta.priority_override_score)
        : ""
    );
    setOverrideReason(dossier.triage_meta?.override_reason || "");
    setRulesReviewed(Boolean(dossier.checklist?.rules_reviewed));
    setLedgerReconciled(Boolean(dossier.checklist?.ledger_reconciled));
    setNetworkVerified(Boolean(dossier.checklist?.network_verified));
    setKycCorroborated(Boolean(dossier.checklist?.kyc_corroborated));
    setChecklistNotes(dossier.checklist?.notes || "");
    setSarText(dossier.triage_meta?.sar_draft || "");
    setSarUpdatedAt(dossier.triage_meta?.sar_updated_at || null);
    setOpsMsg(null);
  }, [
    dossier?.case.case_id,
    dossier?.case.assigned_analyst_id,
    dossier?.case.effective_priority_tier,
    dossier?.triage_meta?.override_at,
    dossier?.triage_meta?.sar_updated_at,
    dossier?.checklist?.updated_at,
  ]);

  if (!dossier) {
    return (
      <div className="liquid-glass rounded-2xl p-12 text-center text-sm text-slate-600 dark:text-zinc-400">
        Select any case from the <strong className="text-slate-900 dark:text-white">Triage Queue</strong> to inspect its
        entity network graph, rule facts, score waterfall, and reconciled ledger.
      </div>
    );
  }

  const c = dossier.case;
  const factsByAlert: Record<string, CaseDossier["trigger_facts"]> = {};
  for (const f of dossier.trigger_facts) {
    factsByAlert[f.alert_id] = factsByAlert[f.alert_id] || [];
    factsByAlert[f.alert_id].push(f);
  }

  const timeline = [
    ...dossier.case_state_events.map((ev) => ({
      ts: ev.effective_at,
      kind: "CASE" as const,
      title: `Case Transition: ${ev.prev_status || "NEW"} → ${ev.new_status}`,
      detail: ev.analyst_action_id ? `Triggered by ${ev.analyst_action_id}` : "Automated rule clustering",
    })),
    ...dossier.analyst_actions.map((act) => ({
      ts: act.acted_at,
      kind: "ACTION" as const,
      title: `${act.analyst_id} (${act.analyst_role}) • ${act.action_type}`,
      detail: act.rationale,
    })),
    ...dossier.account_state_events.map((aev) => ({
      ts: aev.effective_at,
      kind: "ACCT" as const,
      title: `${aev.account_id}: ${aev.prev_status || "OPENED"} → ${aev.new_status}`,
      detail: `Reason: ${aev.reason} (actor: ${aev.actor_id})`,
    })),
  ].sort((a, b) => a.ts.localeCompare(b.ts));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFeedback(null);
    try {
      const msg = await onSubmitAction({ analyst_id: analystId, action_type: actionType, rationale });
      setRationale("");
      setFeedback({ ok: true, msg });
    } catch (err) {
      setFeedback({ ok: false, msg: err instanceof Error ? err.message : "Submission failed" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Executive Dossier Header */}
      <div className="liquid-glass rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="font-mono text-lg font-bold text-slate-950 dark:text-white">{c.case_id}</h2>
            <Badge variant={tierVariant(c.effective_priority_tier ?? c.priority_tier)}>
              {c.effective_priority_tier ?? c.priority_tier} ({(c.effective_priority_score ?? c.priority_score).toFixed(2)})
            </Badge>
            <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
            <span className="text-xs font-semibold text-slate-800 dark:text-zinc-200">{c.linkage_summary}</span>
            {c.assigned_analyst_id && <Badge variant="BLUE">Owner: {c.assigned_analyst_id}</Badge>}
            {c.sla_breached && <Badge variant="CRITICAL">SLA BREACHED ({c.age_hours ?? 0}h)</Badge>}
            {c.requires_reviewer_signoff && <Badge variant="HIGH">Reviewer Sign-Off &ge;$25k</Badge>}
            {(dossier.watchlist_tags || []).map((t) => (
              <Badge key={t.tag_id} variant="CRITICAL">{t.tag}</Badge>
            ))}
          </div>
          <div className="mt-1.5 text-xs text-slate-600 dark:text-zinc-400 font-mono">
            Primary Account: {c.primary_account_id} • Customer: {c.primary_customer_id} • Opened: {c.created_at}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-6">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-600 dark:text-zinc-400 font-semibold">
              Linked Accts
            </div>
            <div className="ios-num text-lg font-bold text-slate-950 dark:text-white">{c.linked_account_count}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-600 dark:text-zinc-400 font-semibold">
              Alerts
            </div>
            <div className="ios-num text-lg font-bold text-slate-950 dark:text-white">{c.alert_count}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-600 dark:text-zinc-400 font-semibold">
              Total Exposure
            </div>
            <div className="text-lg font-bold text-azure-700 dark:text-white">
              <IosAmount value={c.total_exposure_amount} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => downloadExport(api.caseExportUrl(c.case_id, "md"), `${c.case_id}_packet.md`)}
              className="inline-flex items-center gap-1.5 px-3 py-2 glass-pill rounded-full text-xs font-semibold text-azure-700 dark:text-zinc-100 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              <Download className="w-3.5 h-3.5" /> Packet MD
            </button>
            <button
              type="button"
              onClick={() => downloadExport(api.caseExportUrl(c.case_id, "json"), `${c.case_id}_packet.json`)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black text-xs font-semibold transition"
            >
              <Download className="w-3.5 h-3.5" /> Packet JSON
            </button>
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 glass-pill rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-100 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Queue
            </button>
          </div>
        </div>
      </div>

      {/* Top Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7">
          <NetworkGraph nodes={dossier.graph.nodes} edges={dossier.graph.edges} darkMode={darkMode} />
        </div>

        <div className="lg:col-span-5 space-y-5">
          <WaterfallCard score={c.priority_score} tier={c.priority_tier} waterfall={dossier.waterfall} />

          <div className="liquid-glass rounded-2xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-white/60 dark:border-white/10">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                Analyst Disposition (Immutable Audit)
              </h3>
            </div>
            <form onSubmit={handleSubmit} className="p-5 space-y-3.5 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="block space-y-1">
                  <span className="font-semibold text-slate-700 dark:text-zinc-300">Analyst</span>
                  <select
                    value={analystId}
                    onChange={(e) => setAnalystId(e.target.value)}
                    className="w-full glass-pill rounded-full px-3 py-2 text-slate-900 dark:text-zinc-100"
                  >
                    <option value="ANL-001">ANL-001 (Ops Analyst)</option>
                    <option value="ANL-002">ANL-002 (Ops Analyst)</option>
                    <option value="ANL-003">ANL-003 (Risk Reviewer)</option>
                    <option value="ANL-004">ANL-004 (Compliance Officer)</option>
                  </select>
                </label>

                <label className="block space-y-1">
                  <span className="font-semibold text-slate-700 dark:text-zinc-300">Disposition Action</span>
                  <select
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    className="w-full glass-pill rounded-full px-3 py-2 text-slate-900 dark:text-zinc-100"
                  >
                    <option value="CLAIM_REVIEW">CLAIM_REVIEW &rarr; IN_REVIEW</option>
                    <option value="ESCALATE">ESCALATE &rarr; ESCALATED</option>
                    <option value="FILE_SAR">FILE_SAR &rarr; SAR_FILED</option>
                    <option value="CONFIRM_FRAUD">CONFIRM_FRAUD &rarr; CLOSED_CONFIRMED_FRAUD</option>
                    <option value="MARK_FALSE_POSITIVE">MARK_FALSE_POSITIVE &rarr; CLOSED_FALSE_POSITIVE</option>
                    <option value="REOPEN_CASE">REOPEN_CASE &rarr; IN_REVIEW (Reviewer+)</option>
                    <option value="ADD_NOTE">ADD_NOTE (Log Only)</option>
                  </select>
                </label>
              </div>

              <label className="block space-y-1">
                <span className="font-semibold text-slate-700 dark:text-zinc-300">Audit Rationale</span>
                <textarea
                  rows={2}
                  required
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  placeholder="Document corroborating transaction facts and compliance rationale..."
                  className="w-full bg-white/75 dark:bg-zinc-900 border border-white/80 dark:border-white/15 rounded-xl px-3 py-2 text-slate-900 dark:text-zinc-100 placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-azure-500/40 dark:focus:ring-white/25"
                />
              </label>

              <div className="flex items-center justify-between gap-3 pt-1">
                <span
                  className={`text-xs font-medium ${
                    feedback
                      ? feedback.ok
                        ? "text-emerald-700 dark:text-emerald-400"
                        : "text-rose-700 dark:text-rose-400"
                      : "text-slate-500 dark:text-zinc-500"
                  }`}
                >
                  {feedback ? feedback.msg : "Appends immutable AnalystAction & CaseStateEvent"}
                </span>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-full bg-azure-600 hover:bg-azure-700 dark:bg-white dark:hover:bg-zinc-200 text-white dark:text-black font-semibold transition disabled:opacity-50"
                >
                  {submitting ? "Recording..." : "Record Action"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* Functions 111-112, 115-116, 121-125: Case Ops, Checklist, SAR Draft & Watchlist */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 text-xs">
        {/* Assignment, Priority Override & Link Alert */}
        <div className="lg:col-span-4 liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white">
            <UserCheck className="w-4 h-4 text-azure-600 dark:text-sky-400" />
            <span>Case Assignment &amp; Priority (Fn 111–115)</span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
              className="flex-1 glass-pill rounded-full px-2.5 py-1.5"
            >
              <option value="ANL-001">ANL-001 (Ops Analyst)</option>
              <option value="ANL-002">ANL-002 (Ops Analyst)</option>
              <option value="ANL-003">ANL-003 (Risk Reviewer)</option>
              <option value="ADM-001">ADM-001 (System Admin)</option>
            </select>
            <button
              type="button"
              onClick={async () => {
                setOpsMsg(null);
                try {
                  await api.triageCase(c.case_id, { assigned_analyst_id: assignee });
                  setOpsMsg({ ok: true, text: `Assigned case to ${assignee}.` });
                  await onDossierUpdated(c.case_id);
                } catch (err) {
                  setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Assign failed" });
                }
              }}
              className="px-3 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black font-semibold"
            >
              Assign
            </button>
          </div>

          <div className="pt-2 border-t border-white/40 dark:border-white/10 space-y-2">
            <div className="font-semibold text-slate-800 dark:text-zinc-200">Priority Override (Reviewer / Admin)</div>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={overrideTier}
                onChange={(e) => setOverrideTier(e.target.value)}
                className="glass-pill rounded-full px-2.5 py-1.5"
              >
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>
              <input
                type="number"
                min={0}
                max={100}
                step="0.5"
                value={overrideScore}
                onChange={(e) => setOverrideScore(e.target.value)}
                placeholder="Score (0-100)"
                className="glass-pill rounded-full px-2.5 py-1.5 ios-num"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Mandatory override rationale..."
                className="flex-1 glass-pill rounded-full px-2.5 py-1.5"
              />
              <button
                type="button"
                onClick={async () => {
                  setOpsMsg(null);
                  try {
                    await api.triageCase(c.case_id, {
                      override_tier: overrideTier,
                      override_score: overrideScore ? Number(overrideScore) : undefined,
                      override_reason: overrideReason,
                    });
                    setOpsMsg({ ok: true, text: "Priority override recorded." });
                    await onDossierUpdated(c.case_id);
                  } catch (err) {
                    setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Override failed" });
                  }
                }}
                className="px-3 py-1.5 glass-pill rounded-full font-semibold text-azure-700 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
              >
                Override
              </button>
            </div>
          </div>

          <div className="pt-2 border-t border-white/40 dark:border-white/10 space-y-2">
            <div className="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-zinc-200">
              <Link2 className="w-3.5 h-3.5" /> Link Alert to Case
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={linkAlertId}
                onChange={(e) => setLinkAlertId(e.target.value)}
                placeholder="ALT-2026-000001"
                className="flex-1 glass-pill rounded-full px-2.5 py-1.5 font-mono"
              />
              <button
                type="button"
                disabled={!linkAlertId.trim()}
                onClick={async () => {
                  setOpsMsg(null);
                  try {
                    await api.linkCaseAlert(c.case_id, { alert_id: linkAlertId.trim(), mode: "link" });
                    setLinkAlertId("");
                    setOpsMsg({ ok: true, text: "Alert linked and exposure recalculated." });
                    await onDossierUpdated(c.case_id);
                  } catch (err) {
                    setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Link failed" });
                  }
                }}
                className="px-3 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black font-semibold disabled:opacity-40"
              >
                Link
              </button>
            </div>
          </div>

          {opsMsg && (
            <div className={opsMsg.ok ? "text-emerald-700 dark:text-emerald-400 font-semibold" : "text-rose-700 dark:text-rose-400 font-semibold"}>
              {opsMsg.text}
            </div>
          )}
        </div>

        {/* Evidence Checklist & Cross-Entity Watchlist Tags (Fn 121, 125) */}
        <div className="lg:col-span-4 liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white">
            <ClipboardCheck className="w-4 h-4 text-azure-600 dark:text-sky-400" />
            <span>Evidence Checklist &amp; Watchlist (Fn 121, 125)</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "Rules Reviewed", val: rulesReviewed, set: setRulesReviewed },
              { label: "Ledger Reconciled", val: ledgerReconciled, set: setLedgerReconciled },
              { label: "Network Verified", val: networkVerified, set: setNetworkVerified },
              { label: "KYC Corroborated", val: kycCorroborated, set: setKycCorroborated },
            ].map((chk) => (
              <label key={chk.label} className="flex items-center gap-2 rounded-xl bg-white/45 dark:bg-black/35 border border-white/60 dark:border-white/10 px-2.5 py-2 cursor-pointer">
                <input type="checkbox" checked={chk.val} onChange={(e) => chk.set(e.target.checked)} />
                <span className="font-medium text-slate-800 dark:text-zinc-200">{chk.label}</span>
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={checklistNotes}
              onChange={(e) => setChecklistNotes(e.target.value)}
              placeholder="Verification sign-off notes..."
              className="flex-1 glass-pill rounded-full px-2.5 py-1.5"
            />
            <button
              type="button"
              onClick={async () => {
                setOpsMsg(null);
                try {
                  await api.updateChecklist(c.case_id, {
                    rules_reviewed: rulesReviewed,
                    ledger_reconciled: ledgerReconciled,
                    network_verified: networkVerified,
                    kyc_corroborated: kycCorroborated,
                    notes: checklistNotes,
                  });
                  setOpsMsg({ ok: true, text: "Checklist saved to SQLite." });
                  await onDossierUpdated(c.case_id);
                } catch (err) {
                  setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Checklist save failed" });
                }
              }}
              className="px-3 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black font-semibold"
            >
              Save
            </button>
          </div>

          <div className="pt-2 border-t border-white/40 dark:border-white/10 space-y-2">
            <div className="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-zinc-200">
              <Tag className="w-3.5 h-3.5" /> Entity Watchlist Tagging
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={tagTargetType}
                onChange={(e) => setTagTargetType(e.target.value as "CUSTOMER" | "ACCOUNT")}
                className="glass-pill rounded-full px-2.5 py-1.5"
              >
                <option value="CUSTOMER">Customer ({c.primary_customer_id})</option>
                <option value="ACCOUNT">Account ({c.primary_account_id})</option>
              </select>
              <select
                value={tagName}
                onChange={(e) => setTagName(e.target.value)}
                className="glass-pill rounded-full px-2.5 py-1.5"
              >
                <option value="MULE_SUSPECT">MULE_SUSPECT</option>
                <option value="PEP_WATCH">PEP_WATCH</option>
                <option value="STRUCTURING_REPEAT">STRUCTURING_REPEAT</option>
                <option value="VELOCITY_WATCH">VELOCITY_WATCH</option>
                <option value="HIGH_RISK_ENTITY">HIGH_RISK_ENTITY</option>
                <option value="VERIFIED_PAYROLL">VERIFIED_PAYROLL</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={tagNote}
                onChange={(e) => setTagNote(e.target.value)}
                placeholder="Tag justification..."
                className="flex-1 glass-pill rounded-full px-2.5 py-1.5"
              />
              <button
                type="button"
                onClick={async () => {
                  setOpsMsg(null);
                  try {
                    await api.manageWatchlistTag({
                      entity_type: tagTargetType,
                      entity_id: tagTargetType === "CUSTOMER" ? c.primary_customer_id : c.primary_account_id,
                      tag: tagName,
                      note: tagNote,
                    });
                    setTagNote("");
                    setOpsMsg({ ok: true, text: `Applied ${tagName} tag.` });
                    await onDossierUpdated(c.case_id);
                  } catch (err) {
                    setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Tag failed" });
                  }
                }}
                className="px-3 py-1.5 rounded-full bg-rose-600/90 text-white font-semibold"
              >
                Add Tag
              </button>
            </div>
            {(dossier.watchlist_tags || []).length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {(dossier.watchlist_tags || []).map((t) => (
                  <button
                    key={t.tag_id}
                    type="button"
                    title="Click to remove tag"
                    onClick={async () => {
                      setOpsMsg(null);
                      try {
                        await api.manageWatchlistTag({
                          entity_type: t.entity_type,
                          entity_id: t.entity_id,
                          tag: t.tag,
                          remove: true,
                        });
                        setOpsMsg({ ok: true, text: `Removed ${t.tag} tag.` });
                        await onDossierUpdated(c.case_id);
                      } catch (err) {
                        setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to remove tag" });
                      }
                    }}
                    className="badge-glass badge-glass-critical inline-flex items-center gap-1 px-1.5 py-[1px] rounded-full font-semibold text-[9.5px] leading-[1.25]"
                  >
                    {t.tag} ({t.entity_id}) ×
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* SAR Narrative Auto-Draft Studio (Fn 122, 123) */}
        <div className="lg:col-span-4 liquid-glass rounded-2xl p-5 space-y-3 flex flex-col">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950 dark:text-white">
              <FileText className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              <span>SAR Narrative Studio (Fn 122)</span>
            </div>
            {c.requires_reviewer_signoff && (
              <span className="inline-flex items-center gap-1 text-[10.5px] font-semibold text-amber-700 dark:text-amber-300">
                <ShieldAlert className="w-3.5 h-3.5" /> Reviewer Sign-Off
              </span>
            )}
          </div>
          <textarea
            rows={7}
            value={sarText}
            onChange={(e) => setSarText(e.target.value)}
            placeholder="Click 'Auto-Draft SAR' to synthesize structured compliance prose from linked rules, accounts & exposure..."
            className="w-full flex-1 glass-pill rounded-2xl p-3 font-mono text-[11px] leading-relaxed text-slate-900 dark:text-zinc-100 placeholder:text-slate-500 dark:placeholder:text-zinc-500 focus:outline-none"
          />
          <div className="flex items-center justify-between gap-2">
            <span className="ios-num text-[10.5px] text-slate-500 dark:text-zinc-400">
              {sarUpdatedAt ? `Saved: ${sarUpdatedAt}` : "Not drafted yet"}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={async () => {
                  setOpsMsg(null);
                  try {
                    const res = await api.sarDraft(c.case_id, {});
                    setSarText(res.sar_draft);
                    setSarUpdatedAt(res.sar_updated_at);
                    setOpsMsg({ ok: true, text: "SAR narrative drafted." });
                    await onDossierUpdated(c.case_id);
                  } catch (err) {
                    setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to draft SAR" });
                  }
                }}
                className="px-3 py-1.5 glass-pill rounded-full font-semibold text-azure-700 dark:text-white hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
              >
                Auto-Draft SAR
              </button>
              <button
                type="button"
                disabled={!sarText.trim()}
                onClick={async () => {
                  setOpsMsg(null);
                  try {
                    const res = await api.sarDraft(c.case_id, { sar_draft: sarText });
                    setSarUpdatedAt(res.sar_updated_at);
                    setOpsMsg({ ok: true, text: "SAR draft saved." });
                    await onDossierUpdated(c.case_id);
                  } catch (err) {
                    setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to save SAR draft" });
                  }
                }}
                className="px-3 py-1.5 rounded-full bg-azure-600/90 dark:bg-white text-white dark:text-black font-semibold disabled:opacity-40"
              >
                Save Draft
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mid Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7 liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/60 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Triggered Alerts &amp; Quantitative Rule Facts
            </h3>
          </div>
          <div className="p-4 space-y-3">
            {dossier.alerts.map((a) => {
              const facts = factsByAlert[a.alert_id] || [];
              return (
                <div
                  key={a.alert_id}
                  className="rounded-xl border border-white/75 dark:border-white/10 bg-white/55 dark:bg-black/45 p-3.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono font-bold text-xs text-slate-950 dark:text-white">{a.alert_id}</span>
                      <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{a.rule_id}</span>
                      <span className="text-xs font-semibold text-slate-800 dark:text-zinc-200">{a.rule_name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={tierVariant(a.severity)}>
                        {a.severity} • {a.risk_score.toFixed(1)}
                      </Badge>
                      {dossier.alerts.length > 1 && (
                        <button
                          type="button"
                          title="Unlink alert from case"
                          onClick={async () => {
                            setOpsMsg(null);
                            try {
                              await api.linkCaseAlert(c.case_id, { alert_id: a.alert_id, mode: "unlink" });
                              setOpsMsg({ ok: true, text: `Unlinked ${a.alert_id}.` });
                              await onDossierUpdated(c.case_id);
                            } catch (err) {
                              setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Unlink failed" });
                            }
                          }}
                          className="glass-pill inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] font-semibold text-slate-700 dark:text-zinc-300 hover:text-rose-600 transition"
                        >
                          <Unlink className="w-3 h-3" /> Unlink
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-slate-700 dark:text-zinc-300">{a.explanation_summary}</p>
                  <div className="mt-2 space-y-1">
                    {facts.length > 0 ? (
                      facts.map((f) => (
                        <div key={f.fact_id} className="font-mono text-[11px] text-slate-600 dark:text-zinc-400">
                          • {f.transaction_id} {f.transfer_id ? `(${f.transfer_id})` : ""} —{" "}
                          <span className="font-semibold text-slate-800 dark:text-zinc-200">{f.metric_name}</span>:{" "}
                          <span className="text-azure-700 dark:text-white">{f.observed_value}</span> [threshold:{" "}
                          {f.threshold_value}]
                        </div>
                      ))
                    ) : (
                      <div className="font-mono text-[11px] text-rose-600 dark:text-rose-400">
                        No AlertTriggerFact rows (Orphan Alert Anomaly)
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="lg:col-span-5 liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/60 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Immutable Case &amp; Account Lifecycle Audit Log
            </h3>
          </div>
          <div className="p-5 space-y-4">
            {timeline.map((ev, idx) => (
              <div
                key={`${ev.ts}-${idx}`}
                className="relative pl-4 border-l-2 border-slate-300/80 dark:border-zinc-700"
              >
                <span
                  className={`w-2.5 h-2.5 rounded-full absolute -left-[6px] top-1 ${
                    ev.kind === "ACCT" ? "bg-amber-500" : "bg-azure-600 dark:bg-white"
                  }`}
                />
                <div className="ios-num text-[11px] text-slate-500 dark:text-zinc-500">{ev.ts}</div>
                <div className="text-xs font-semibold text-slate-900 dark:text-white mt-0.5">{ev.title}</div>
                <div className="text-xs text-slate-600 dark:text-zinc-400 mt-0.5">{ev.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Reconciled Ledger */}
      <div className="liquid-glass rounded-2xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-white/60 dark:border-white/10">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
            Reconciled Account Ledger Timeline
          </h3>
          <p className="text-xs text-slate-600 dark:text-zinc-400 ios-num">
            Showing {dossier.transactions.length} of {dossier.total_ledger_txns} transactions across{" "}
            {dossier.accounts.length} linked account(s)
          </p>
        </div>
        <div className="overflow-x-auto max-h-[420px]">
          <table className="w-full text-left border-collapse text-xs">
            <thead className="sticky top-0 bg-white/80 dark:bg-zinc-950/90 backdrop-blur-md border-b border-white/60 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-zinc-400">
              <tr>
                <th className="py-2.5 px-4">Transaction ID</th>
                <th className="py-2.5 px-3">Timestamp (UTC)</th>
                <th className="py-2.5 px-3">Account</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3">Channel / Counterparty</th>
                <th className="py-2.5 px-3 text-right">Amount</th>
                <th className="py-2.5 px-3 text-right">Before</th>
                <th className="py-2.5 px-3 text-right">After</th>
                <th className="py-2.5 px-4">Integrity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/45 dark:divide-white/[0.07]">
              {dossier.transactions
                .slice()
                .reverse()
                .slice(txPage * txPageSize, (txPage + 1) * txPageSize)
                .map((tx) => (
                  <tr key={tx.transaction_id} className="hover:bg-white/50 dark:hover:bg-white/[0.04]">
                    <td className="py-2.5 px-4 font-mono text-slate-900 dark:text-zinc-100">{tx.transaction_id}</td>
                    <td className="py-2.5 px-3 ios-num text-slate-600 dark:text-zinc-400">{tx.occurred_at}</td>
                    <td className="py-2.5 px-3 font-mono text-slate-700 dark:text-zinc-300">{tx.account_id}</td>
                    <td className="py-2.5 px-3">
                      <span className="font-mono text-xs font-semibold text-slate-800 dark:text-zinc-200">{tx.txn_type}</span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-700 dark:text-zinc-300">
                      <span className="text-slate-500 dark:text-zinc-500">{tx.channel}</span> •{" "}
                      {tx.merchant_name ? `${tx.merchant_name} (${tx.merchant_category})` : tx.reference_note}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right font-semibold ${
                        tx.direction === "CREDIT"
                          ? "text-emerald-600 dark:text-emerald-400"
                          : "text-slate-950 dark:text-white"
                      }`}
                    >
                      <IosAmount value={tx.direction === "CREDIT" ? tx.amount : -tx.amount} showPlus={tx.direction === "CREDIT"} />
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-600 dark:text-zinc-400">
                      <IosAmount value={tx.balance_before} />
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-950 dark:text-white font-medium">
                      <IosAmount value={tx.balance_after} />
                    </td>
                    <td className="py-2.5 px-4">
                      {tx.reconciled_ok ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-semibold">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Reconciled
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-rose-700 dark:text-rose-400 font-semibold">
                          <XCircle className="w-3.5 h-3.5" /> Anomaly
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <GlassPagination
          total={dossier.transactions.length}
          page={txPage}
          pageSize={txPageSize}
          onPageChange={setTxPage}
          onPageSizeChange={(sz) => {
            setTxPageSize(sz);
            setTxPage(0);
          }}
          unitLabel="ledger txns"
        />
      </div>

      {/* Functions 186, 188, 189, 190, 198: SOP Playbooks, Evidence Pinboard, Comment Thread & 314(b) RFI */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-6 liquid-glass rounded-2xl p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/40 dark:border-white/10 pb-3">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Evidence Pinboard ({pins.length}) &amp; Typology Playbooks
            </h3>
            <div className="flex items-center gap-1.5 text-xs">
              <select
                value={selectedPlaybook}
                onChange={(e) => setSelectedPlaybook(e.target.value)}
                className="px-2.5 py-1 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white"
              >
                {playbooks.map((pb) => (
                  <option key={pb.playbook_id} value={pb.playbook_id} className="bg-white dark:bg-zinc-900">
                    {pb.title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={async () => {
                  try {
                    const res = await api.applyPlaybook(c.case_id, selectedPlaybook);
                    setOpsMsg({ ok: true, text: `Applied SOP ${res.playbook.playbook_id}.` });
                    const [cm] = await Promise.all([api.caseComments(c.case_id), onDossierUpdated(c.case_id)]);
                    setComments(cm.items);
                  } catch (err) {
                    setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to apply playbook" });
                  }
                }}
                className="px-3 py-1 rounded-full bg-azure-600 text-white font-semibold hover:bg-azure-500 transition"
              >
                Apply SOP
              </button>
            </div>
          </div>

          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!pinEntityId.trim()) return;
              try {
                const et = pinEntityId.trim().startsWith("ALT-")
                  ? "ALERT"
                  : pinEntityId.trim().startsWith("ACC-")
                  ? "ACCOUNT"
                  : pinEntityId.trim().startsWith("DEV-")
                  ? "DEVICE"
                  : "TRANSACTION";
                await api.addCasePin(c.case_id, { entity_type: et, entity_id: pinEntityId.trim(), pin_type: pinType, note: pinNote });
                setPinEntityId("");
                setPinNote("");
                const res = await api.casePins(c.case_id);
                setPins(res.items);
              } catch (err) {
                setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to pin evidence" });
              }
            }}
            className="flex flex-wrap gap-2 text-xs"
          >
            <input
              type="text"
              required
              value={pinEntityId}
              onChange={(e) => setPinEntityId(e.target.value)}
              placeholder="TXN-..., ALT-..., ACC-..., or DEV-..."
              className="flex-1 min-w-[150px] px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white placeholder:text-slate-500"
            />
            <select
              value={pinType}
              onChange={(e) => setPinType(e.target.value as typeof pinType)}
              className="px-2.5 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white"
            >
              <option value="PINNED_PROOF" className="bg-white dark:bg-zinc-900">PINNED_PROOF</option>
              <option value="CORROBORATING" className="bg-white dark:bg-zinc-900">CORROBORATING</option>
              <option value="EXCULPATORY" className="bg-white dark:bg-zinc-900">EXCULPATORY</option>
            </select>
            <input
              type="text"
              value={pinNote}
              onChange={(e) => setPinNote(e.target.value)}
              placeholder="Evidence note..."
              className="w-40 px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white placeholder:text-slate-500"
            />
            <button type="submit" className="px-3 py-1.5 rounded-full bg-azure-600 text-white font-semibold">Pin</button>
          </form>

          <div className="space-y-1.5 max-h-44 overflow-y-auto text-xs">
            {pins.map((p) => (
              <div key={p.pin_id} className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                <div>
                  <span className="font-mono font-bold text-slate-950 dark:text-white mr-2">{p.entity_id}</span>
                  <Badge variant={p.pin_type === "EXCULPATORY" ? "LOW" : "CRITICAL"}>{p.pin_type}</Badge>
                  {p.note && <span className="ml-2 text-slate-600 dark:text-zinc-400">{p.note}</span>}
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    await api.deleteCasePin(c.case_id, p.pin_id);
                    const res = await api.casePins(c.case_id);
                    setPins(res.items);
                  }}
                  className="text-rose-600 dark:text-rose-400 underline text-[11px]"
                >
                  Unpin
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-6 liquid-glass rounded-2xl p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/40 dark:border-white/10 pb-3">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Investigator Notes Thread ({comments.length})
            </h3>
            <button
              type="button"
              onClick={async () => {
                try {
                  const res = await api.generateRfi(c.case_id);
                  setRfiMarkdown(res.markdown);
                } catch (err) {
                  setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to generate RFI" });
                }
              }}
              className="px-3 py-1 rounded-full bg-white/35 dark:bg-white/[0.08] border border-white/60 dark:border-white/15 text-xs font-semibold text-azure-700 dark:text-sky-300 hover:bg-white/60 dark:hover:bg-white/15 transition"
            >
              Generate 314(b) RFI Packet
            </button>
          </div>

          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!commentBody.trim()) return;
              try {
                await api.addCaseComment(c.case_id, { body: commentBody, visibility: commentVis });
                setCommentBody("");
                const res = await api.caseComments(c.case_id);
                setComments(res.items);
              } catch (err) {
                setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to post comment" });
              }
            }}
            className="flex gap-2 text-xs"
          >
            <select
              value={commentVis}
              onChange={(e) => setCommentVis(e.target.value as typeof commentVis)}
              className="px-2.5 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white"
            >
              <option value="INTERNAL" className="bg-white dark:bg-zinc-900">INTERNAL</option>
              <option value="COMPLIANCE" className="bg-white dark:bg-zinc-900">COMPLIANCE</option>
            </select>
            <input
              type="text"
              required
              value={commentBody}
              onChange={(e) => setCommentBody(e.target.value)}
              placeholder="Add investigation note or handoff comment..."
              className="flex-1 px-3 py-1.5 rounded-full bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white placeholder:text-slate-500"
            />
            <button type="submit" className="px-3 py-1.5 rounded-full bg-azure-600 text-white font-semibold">Post</button>
          </form>

          {rfiMarkdown && (
            <div className="rounded-xl p-3 bg-white/25 dark:bg-black/45 border border-white/50 dark:border-white/15 space-y-2">
              <div className="flex justify-between text-[11px] font-bold">
                <span>FinCEN 314(b) / Correspondent RFI Preview</span>
                <button type="button" onClick={() => setRfiMarkdown(null)} className="underline">Close</button>
              </div>
              <pre className="whitespace-pre-wrap font-mono text-[10.5px] text-slate-800 dark:text-zinc-200 max-h-36 overflow-y-auto">{rfiMarkdown}</pre>
            </div>
          )}

          <div className="space-y-1.5 max-h-44 overflow-y-auto text-xs">
            {comments.map((cm) => (
              <div key={cm.comment_id} className="px-3 py-2 rounded-xl bg-white/25 dark:bg-white/[0.05] border border-white/50 dark:border-white/10">
                <div className="flex justify-between text-[10.5px] font-mono text-slate-600 dark:text-zinc-400">
                  <span><strong>{cm.actor_id}</strong> ({cm.actor_role}) • {cm.visibility}</span>
                  <span>{cm.created_at}</span>
                </div>
                <div className="text-slate-900 dark:text-zinc-100 mt-0.5">{cm.body}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Function 172-173: Peer Similar Cases Comparison Strip */}
      {similarCases.length > 0 && (
        <div className="liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
                Similar Peer Cases Comparison
              </h3>
              <p className="text-xs text-slate-600 dark:text-zinc-400">
                Ranked by shared triggered rules, exposure band similarity &amp; priority score proximity
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3 text-xs">
            {similarCases.map((sim) => (
              <div
                key={sim.case_id}
                className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12 space-y-1.5"
              >
                <div className="flex items-center justify-between gap-1">
                  {onOpenCase ? (
                    <button
                      type="button"
                      onClick={() => onOpenCase(sim.case_id)}
                      className="font-mono font-bold text-azure-700 dark:text-sky-300 hover:underline"
                    >
                      {sim.case_id}
                    </button>
                  ) : (
                    <span className="font-mono font-bold text-slate-900 dark:text-white">{sim.case_id}</span>
                  )}
                  <Badge variant="BLUE">{sim.similarity_pct}% match</Badge>
                </div>
                <div className="font-medium text-slate-800 dark:text-zinc-200 truncate">{sim.customer_name}</div>
                <div className="flex items-center justify-between text-[11px] ios-num text-slate-600 dark:text-zinc-400">
                  <span>${sim.total_exposure_amount.toLocaleString()}</span>
                  <Badge variant={statusVariant(sim.status)}>{sim.status}</Badge>
                </div>
                {sim.shared_rules.length > 0 && (
                  <div className="text-[10.5px] font-mono text-slate-500 dark:text-zinc-400 truncate">
                    Rules: {sim.shared_rules.join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Functions 233-237, 264: GoAML XML, Shift Handoffs, Cryptographic Seal, What-If Score & Reopen */}
      <div className="liquid-glass rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Regulatory Filing XML, Shift Handoff &amp; Evidence Seal
            </h3>
            <p className="text-xs text-slate-600 dark:text-zinc-400">
              GoAML 5.0 XML preview, SHA-256 chain-of-custody evidence seal &amp; score sensitivity check
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <button
              type="button"
              onClick={async () => {
                try {
                  const res = await api.generateGoamlXml(c.case_id);
                  setGoamlXml(res.xml);
                } catch (err) {
                  setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "XML generation failed" });
                }
              }}
              className="glass-pill px-3 py-1.5 rounded-full font-semibold text-azure-700 dark:text-sky-300"
            >
              Generate GoAML XML
            </button>
            <button
              type="button"
              onClick={async () => {
                try {
                  const s = await api.sealCaseEvidence(c.case_id);
                  setSeals((prev) => [s, ...prev]);
                  setOpsMsg({ ok: true, text: `Evidence sealed (${String(s.sha256_digest).slice(0, 12)}...).` });
                } catch (err) {
                  setOpsMsg({ ok: false, text: err instanceof Error ? err.message : "Seal failed" });
                }
              }}
              className="glass-pill px-3 py-1.5 rounded-full font-semibold text-emerald-700 dark:text-emerald-300"
            >
              Seal Evidence SHA-256
            </button>
            <button
              type="button"
              onClick={async () => {
                const firstAlert = dossier.alerts[0]?.alert_id;
                const res = await api.whatIfCaseScore(c.case_id, firstAlert ? [firstAlert] : []);
                setWhatIfScore(res);
              }}
              className="glass-pill px-3 py-1.5 rounded-full font-semibold text-amber-700 dark:text-amber-300"
            >
              What-If Waive 1 Alert
            </button>
          </div>
        </div>

        {whatIfScore && (
          <div className="px-3.5 py-2 rounded-xl bg-white/22 dark:bg-white/[0.04] border border-white/60 dark:border-white/10 text-xs ios-num flex items-center justify-between">
            <span>
              Priority What-If Simulation: <strong>{whatIfScore.original_score}</strong> &rarr;{" "}
              <strong>{whatIfScore.projected_score}</strong> ({whatIfScore.projected_tier})
            </span>
            <Badge variant={tierVariant(whatIfScore.projected_tier)}>{whatIfScore.projected_tier}</Badge>
          </div>
        )}

        {goamlXml && (
          <pre className="p-3 rounded-xl bg-white/25 dark:bg-black/45 border border-white/60 dark:border-white/10 font-mono text-[10.5px] max-h-48 overflow-auto whitespace-pre-wrap text-slate-900 dark:text-zinc-100">
            {goamlXml}
          </pre>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
          <div className="space-y-2">
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!handoffSummary.trim()) return;
                const h = await api.addCaseHandoff(c.case_id, {
                  to_analyst: handoffTo,
                  summary: handoffSummary,
                });
                setHandoffs((prev) => [h, ...prev]);
                setHandoffSummary("");
              }}
              className="flex flex-wrap gap-2"
            >
              <input
                type="text"
                value={handoffTo}
                onChange={(e) => setHandoffTo(e.target.value)}
                placeholder="To ANL-002"
                className="glass-pill w-24 px-2.5 py-1.5 rounded-full font-mono text-slate-900 dark:text-white focus:outline-none"
              />
              <input
                type="text"
                value={handoffSummary}
                onChange={(e) => setHandoffSummary(e.target.value)}
                placeholder="Shift handoff brief..."
                className="glass-pill flex-1 px-3 py-1.5 rounded-full text-slate-900 dark:text-white focus:outline-none"
              />
              <button type="submit" className="px-3 py-1.5 rounded-full bg-azure-600/90 text-white font-semibold">
                Handoff
              </button>
            </form>
            <div className="space-y-1 max-h-28 overflow-y-auto">
              {handoffs.map((ho) => (
                <div key={String(ho.handoff_id)} className="px-2.5 py-1.5 rounded-xl bg-white/20 dark:bg-white/[0.04] border border-white/50 dark:border-white/10">
                  <span className="font-mono font-bold">{String(ho.from_analyst)} &rarr; {String(ho.to_analyst)}:</span>{" "}
                  <span>{String(ho.summary)}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-1 max-h-36 overflow-y-auto">
            <div className="font-semibold text-slate-700 dark:text-zinc-300">Cryptographic Evidence Seals ({seals.length})</div>
            {seals.map((sl) => (
              <div key={String(sl.seal_id)} className="px-2.5 py-1.5 rounded-xl bg-white/20 dark:bg-white/[0.04] border border-white/50 dark:border-white/10 font-mono text-[10.5px]">
                <div className="flex justify-between">
                  <span className="font-bold">{String(sl.seal_id)}</span>
                  <span>{String(sl.item_count)} artifacts • {String(sl.sealed_by)}</span>
                </div>
                <div className="truncate text-emerald-700 dark:text-emerald-300">{String(sl.sha256_digest)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
