import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  Download,
  FileCheck2,
  FlaskConical,
  Lock,
  ShieldCheck,
  Sliders,
} from "lucide-react";
import { api, downloadExport } from "../api/client";
import type {
  CutoffSimResult,
  EvaluationData,
  FeaturePsiItem,
  LiftCurveDecile,
  ManifestVerificationReport,
  RiskRuleItem,
  RulePerformanceItem,
  TemporalDriftResponse,
  ThresholdSweepResponse,
  WhatIfSimResult,
  ZeroLeakageReport,
} from "../types/workbench";
import { Badge, tierVariant } from "./Badge";
import { GlassPagination } from "./GlassPagination";
import { LiftChart } from "./LiftChart";
import { LiquidGlassCard, useRowGlassMagnifier } from "./LiquidGlassSurface";

export const EvaluationView: React.FC<{
  evaluation: EvaluationData | null;
  rules: RiskRuleItem[];
  darkMode: boolean;
}> = ({ evaluation, rules, darkMode }) => {
  const typMag = useRowGlassMagnifier();
  const ruleMag = useRowGlassMagnifier();
  const manMag = useRowGlassMagnifier();

  const [kPct, setKPct] = useState<number>(20);
  const [simResult, setSimResult] = useState<CutoffSimResult | null>(null);
  const [rulePerf, setRulePerf] = useState<RulePerformanceItem[]>([]);
  const [weightOverrides, setWeightOverrides] = useState<Record<string, number>>({});
  const [whatIfResult, setWhatIfResult] = useState<WhatIfSimResult | null>(null);
  const [simulatingWhatIf, setSimulatingWhatIf] = useState(false);

  const [zeroLeakage, setZeroLeakage] = useState<ZeroLeakageReport | null>(null);
  const [manifestCheck, setManifestCheck] = useState<ManifestVerificationReport | null>(null);
  const [checkingGuard, setCheckingGuard] = useState(false);

  const [sweepRuleId, setSweepRuleId] = useState("RULE-001");
  const [sweepData, setSweepData] = useState<ThresholdSweepResponse | null>(null);
  const [driftData, setDriftData] = useState<TemporalDriftResponse | null>(null);
  const [liftCurve, setLiftCurve] = useState<LiftCurveDecile[]>([]);
  const [scoreHist, setScoreHist] = useState<Array<{ range: string; tp: number; fp: number }>>([]);
  const [featurePsi, setFeaturePsi] = useState<FeaturePsiItem[]>([]);
  const [ruleMarginal, setRuleMarginal] = useState<Array<Record<string, unknown>>>([]);
  const [proposalMsg, setProposalMsg] = useState<string | null>(null);
  const [manPage, setManPage] = useState(0);
  const [manPageSize, setManPageSize] = useState(30);

  useEffect(() => {
    const initial: Record<string, number> = {};
    rules.forEach((r) => {
      initial[r.rule_id] = r.base_weight;
    });
    setWeightOverrides(initial);
  }, [rules]);

  useEffect(() => {
    if (!evaluation) return;
    api.rulePerformance().then((res) => setRulePerf(res.rules)).catch(() => {});
    api.zeroLeakageCheck().then((res) => setZeroLeakage(res)).catch(() => {});
    api.temporalDrift(6).then(setDriftData).catch(() => {});
    api.evaluationLiftCurve().then((r) => setLiftCurve(r.deciles)).catch(() => {});
    api.evaluationScoreHistogram().then((r) => setScoreHist(r.bins)).catch(() => {});
    api.evaluationFeaturePsi().then((r) => setFeaturePsi(r.features)).catch(() => {});
    api.evaluationRuleMarginalLift().then((r) => setRuleMarginal(r.items)).catch(() => {});
  }, [evaluation]);

  useEffect(() => {
    if (!evaluation) return;
    api.thresholdSweep(sweepRuleId).then(setSweepData).catch(() => {});
  }, [evaluation, sweepRuleId]);

  useEffect(() => {
    if (!evaluation) return;
    const timer = window.setTimeout(() => {
      api.simulateCutoff(kPct).then(setSimResult).catch(() => {});
    }, 120);
    return () => window.clearTimeout(timer);
  }, [kPct, evaluation]);

  if (!evaluation) return null;

  const liftRatio =
    evaluation.fifo_top20.recall > 0
      ? (evaluation.priority_top20.recall / evaluation.fifo_top20.recall).toFixed(2)
      : "—";

  const sep = evaluation.score_separation;

  const cards = [
    {
      label: "Top-20% Priority Recall",
      val: `${(evaluation.priority_top20.recall * 100).toFixed(1)}%`,
      foot: `Prec ${(evaluation.priority_top20.precision * 100).toFixed(1)}% • NDCG ${((evaluation.priority_top20.ndcg ?? 0) * 100).toFixed(1)}%`,
      hero: true,
    },
    {
      label: "Top-20% FIFO Recall",
      val: `${(evaluation.fifo_top20.recall * 100).toFixed(1)}%`,
      foot: `Priority achieves ${liftRatio}x capture lift (NDCG ${((evaluation.fifo_top20.ndcg ?? 0) * 100).toFixed(1)}%)`,
    },
    {
      label: "TP vs. FP Separation",
      val: sep ? `+${sep.separation_gap.toFixed(1)} pts` : `${(evaluation.priority_top50_cases.precision * 100).toFixed(1)}%`,
      foot: sep
        ? `TP Mean ${sep.tp_mean_score.toFixed(1)} vs FP Mean ${sep.fp_mean_score.toFixed(1)}`
        : `${evaluation.priority_top50_cases.tp} TP in top 50`,
    },
    {
      label: "Negative Edge Catch Rate",
      val: evaluation.negative_edge_catch_rate.all_types_caught ? "5 / 5 (100%)" : "Partial",
      foot: `${evaluation.negative_edge_catch_rate.caught_count} total exceptions quarantined`,
    },
  ];

  const digests = Object.entries(evaluation.manifest?.sha256_checksums || {});
  const perfMap = new Map(rulePerf.map((p) => [p.rule_id, p]));

  const runWhatIf = async () => {
    setSimulatingWhatIf(true);
    try {
      const res = await api.whatIfSimulation({ weight_overrides: weightOverrides, k_pct: kPct });
      setWhatIfResult(res);
    } finally {
      setSimulatingWhatIf(false);
    }
  };

  const handleVerifyIntegrity = async () => {
    setCheckingGuard(true);
    try {
      const [zl, man] = await Promise.all([api.zeroLeakageCheck(), api.verifyManifest()]);
      setZeroLeakage(zl);
      setManifestCheck(man);
    } finally {
      setCheckingGuard(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header Bar with Provenance Badges & Exports */}
      <div className="liquid-glass rounded-2xl px-5 py-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <Badge variant={zeroLeakage?.zero_leakage_verified ? "LOW" : "BLUE"}>
            <span className="inline-flex items-center gap-1">
              <Lock className="w-3 h-3" />
              {zeroLeakage?.zero_leakage_verified
                ? `ZERO-LEAKAGE AST VERIFIED (${zeroLeakage.file_count} FILES)`
                : "HELD-OUT GROUND TRUTH GUARD"}
            </span>
          </Badge>
          {manifestCheck && (
            <Badge variant={manifestCheck.verified ? "LOW" : "CRITICAL"}>
              SHA-256 MANIFEST: {manifestCheck.matched_count}/{manifestCheck.total_count} VERIFIED
            </Badge>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleVerifyIntegrity}
            disabled={checkingGuard}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-emerald-600/90 border border-white/50 dark:border-transparent text-white hover:bg-emerald-500 transition shadow-sm disabled:opacity-60"
          >
            <FileCheck2 className="w-3.5 h-3.5" />
            {checkingGuard ? "Verifying..." : "Verify AST & Manifest SHA-256"}
          </button>
          <button
            type="button"
            onClick={() => downloadExport(api.evaluationExportUrl("csv"), "yottaflex_rule_metrics.csv")}
            className="glass-pill inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
          >
            <Download className="w-3.5 h-3.5" /> Rule Metrics CSV
          </button>
          <button
            type="button"
            onClick={() => downloadExport(api.evaluationExportUrl("json"), "yottaflex_evaluation.json")}
            className="glass-pill inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold text-slate-800 dark:text-zinc-200 hover:bg-white/45 dark:hover:bg-white/[0.12] transition"
          >
            <Download className="w-3.5 h-3.5" /> Full JSON
          </button>
        </div>
      </div>

      {/* Top 4 KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((k) => (
          <LiquidGlassCard
            key={k.label}
            variant={k.hero ? "hero" : "glass"}
            className={`${k.hero ? "text-white" : ""} rounded-2xl p-4`}
          >
            <div
              className={`text-[11px] font-semibold uppercase tracking-wider ${
                k.hero ? "text-white/85" : "text-slate-600 dark:text-zinc-400"
              }`}
            >
              {k.label}
            </div>
            <div
              className={`mt-1.5 text-2xl font-bold ios-num ${
                k.hero ? "text-white" : "text-slate-950 dark:text-white"
              }`}
            >
              {k.val}
            </div>
            <div
              className={`mt-1 text-[11.5px] ios-num ${
                k.hero ? "text-white/85" : "text-slate-600 dark:text-zinc-400"
              }`}
            >
              {k.foot}
            </div>
          </LiquidGlassCard>
        ))}
      </div>

      {/* Interactive @K% Queue Capacity Cut-Off Simulator */}
      <div className="liquid-glass rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <Sliders className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              Interactive Investigator Capacity Simulator (@{kPct}% Queue Cut-Off)
            </h3>
            <p className="text-xs text-slate-600 dark:text-zinc-400">
              Slide investigator review bandwidth to compare Risk-Priority vs. FIFO recall, precision, F1, NDCG &amp; MAP
            </p>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={5}
              max={100}
              step={5}
              value={kPct}
              onChange={(e) => setKPct(Number(e.target.value))}
              className="w-44 accent-azure-600 cursor-pointer"
            />
            <span className="badge-glass badge-glass-blue font-mono ios-num text-xs font-bold px-2.5 py-1 rounded-full">
              Top {kPct}%
            </span>
          </div>
        </div>

        {simResult && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
            <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
              <div className="text-[10.5px] uppercase text-slate-500 dark:text-zinc-400 font-semibold">Queue Slice</div>
              <div className="mt-1 text-base font-bold ios-num text-slate-950 dark:text-white">
                {simResult.priority.k} / {simResult.total_cases}
              </div>
              <div className="text-[11px] text-slate-600 dark:text-zinc-400">{simResult.priority.tp} TP captured</div>
            </div>
            <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
              <div className="text-[10.5px] uppercase text-slate-500 dark:text-zinc-400 font-semibold">Priority Recall</div>
              <div className="mt-1 text-base font-bold ios-num text-azure-700 dark:text-sky-300">
                {(simResult.priority.recall * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-600 dark:text-zinc-400">FIFO: {(simResult.fifo.recall * 100).toFixed(1)}%</div>
            </div>
            <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
              <div className="text-[10.5px] uppercase text-slate-500 dark:text-zinc-400 font-semibold">Priority Precision</div>
              <div className="mt-1 text-base font-bold ios-num text-slate-950 dark:text-white">
                {(simResult.priority.precision * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-600 dark:text-zinc-400">FIFO: {(simResult.fifo.precision * 100).toFixed(1)}%</div>
            </div>
            <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
              <div className="text-[10.5px] uppercase text-slate-500 dark:text-zinc-400 font-semibold">F1 / NDCG@{simResult.priority.k}</div>
              <div className="mt-1 text-base font-bold ios-num text-emerald-700 dark:text-emerald-400">
                {(simResult.priority.f1 * 100).toFixed(1)}% / {(simResult.priority.ndcg * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-600 dark:text-zinc-400">MAP: {(simResult.priority.map * 100).toFixed(1)}%</div>
            </div>
            <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
              <div className="text-[10.5px] uppercase text-slate-500 dark:text-zinc-400 font-semibold">Capture Lift</div>
              <div className="mt-1 text-base font-bold ios-num text-amber-700 dark:text-amber-300">
                {simResult.recall_lift.toFixed(2)}x
              </div>
              <div className="text-[11px] text-slate-600 dark:text-zinc-400">vs. FIFO arrival order</div>
            </div>
            <div className="rounded-xl p-3 bg-white/25 dark:bg-white/[0.04] backdrop-blur-md border border-white/65 dark:border-white/12">
              <div className="text-[10.5px] uppercase text-slate-500 dark:text-zinc-400 font-semibold">TP Exposure Caught</div>
              <div className="mt-1 text-base font-bold ios-num text-slate-950 dark:text-white">
                ${simResult.priority.exposure_captured.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className="text-[11px] text-slate-600 dark:text-zinc-400">
                FIFO: ${simResult.fifo.exposure_captured.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Lift Chart & Typology Percentiles */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <LiquidGlassCard className="rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Queue Prioritization Lift: Risk-Ranked vs. FIFO
            </h3>
            <p className="text-xs text-slate-600 dark:text-zinc-400">
              Cumulative % of true-positive risk cases captured by queue depth
            </p>
          </div>
          <div className="p-5">
            <LiftChart liftCurve={evaluation.lift_curve} darkMode={darkMode} />
          </div>
        </LiquidGlassCard>

        <div className="liquid-glass rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Typology Score Separation &amp; Percentiles (Held-Out)
            </h3>
            <p className="text-xs text-slate-600 dark:text-zinc-400">
              Ground truth is isolated from scoring &amp; used solely for evaluation
            </p>
          </div>
          <div ref={typMag.containerRef} onMouseLeave={typMag.onContainerLeave} className="relative overflow-x-auto">
            {typMag.lensElement}
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                  <th className="py-2.5 px-4">Typology</th>
                  <th className="py-2.5 px-3">Class</th>
                  <th className="py-2.5 px-3 text-right">Cases</th>
                  <th className="py-2.5 px-3 text-right">Avg</th>
                  <th className="py-2.5 px-3 text-right">P50</th>
                  <th className="py-2.5 px-4 text-right">P90</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
                {evaluation.typology_stats.map((t) => (
                  <tr
                    key={t.typology}
                    onMouseEnter={(e) => typMag.onRowEnter(e.currentTarget)}
                    className="liquid-row-magnify"
                  >
                    <td className="py-2.5 px-4 font-mono font-semibold text-slate-950 dark:text-white">{t.typology}</td>
                    <td className="py-2.5 px-3">
                      <Badge variant={t.is_risk_typology ? "CRITICAL" : "LOW"}>
                        {t.is_risk_typology ? "TRUE RISK" : "BENIGN / FP"}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num">{t.case_count}</td>
                    <td className="py-2.5 px-3 text-right ios-num font-bold text-azure-700 dark:text-white">
                      {t.avg_priority_score.toFixed(1)}
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num text-slate-600 dark:text-zinc-400">
                      {(t.p50_score ?? t.avg_priority_score).toFixed(1)}
                    </td>
                    <td className="py-2.5 px-4 text-right ios-num text-slate-600 dark:text-zinc-400">
                      {(t.p90_score ?? t.max_score).toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Rule Precision Attribution + Non-Mutating What-If Rule Sandbox */}
      <div className="liquid-glass rounded-2xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-azure-600 dark:text-sky-400" />
              Rule-Level Precision Attribution &amp; What-If Weight Sandbox
            </h3>
            <p className="text-xs text-slate-600 dark:text-zinc-400">
              Inspect held-out TP/FP ratios per rule and preview hypothetical weight shifts without mutating live SQLite weights
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={runWhatIf}
              disabled={simulatingWhatIf}
              className="px-3.5 py-1.5 rounded-full bg-azure-600 hover:bg-azure-500 text-white text-xs font-semibold transition shadow-sm disabled:opacity-60"
            >
              {simulatingWhatIf ? "Simulating..." : `Simulate Top-${kPct}% Impact`}
            </button>
            {whatIfResult && (
              <button
                type="button"
                onClick={async () => {
                  try {
                    const prop = await api.createCalibrationProposal({
                      title: `Sandbox Calibration (@Top ${kPct}%)`,
                      weights: weightOverrides,
                      simulation_summary: {
                        k_pct: kPct,
                        recall_delta: whatIfResult.recall_delta,
                        precision_delta: whatIfResult.precision_delta,
                      },
                    });
                    setProposalMsg(`Staged proposal ${prop.proposal_id} for SYSTEM_ADMIN approval (view in Txns → Risk Engine).`);
                  } catch (err) {
                    setProposalMsg(err instanceof Error ? err.message : "Failed to stage proposal");
                  }
                }}
                className="px-3.5 py-1.5 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition shadow-sm"
              >
                Stage Proposal
              </button>
            )}
          </div>
        </div>

        {proposalMsg && (
          <div className="px-5 py-2.5 bg-emerald-500/12 border-b border-emerald-400/25 text-xs font-semibold text-emerald-800 dark:text-emerald-200 flex justify-between">
            <span>{proposalMsg}</span>
            <button type="button" onClick={() => setProposalMsg(null)} className="underline">Dismiss</button>
          </div>
        )}

        {whatIfResult && (
          <div className="px-5 py-3 bg-azure-500/10 border-b border-azure-400/25 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex flex-wrap items-center gap-4">
              <span className="font-bold text-azure-800 dark:text-sky-200">
                What-If Preview (Top {whatIfResult.k} Cases):
              </span>
              <span className="ios-num text-slate-800 dark:text-zinc-200">
                Recall {(whatIfResult.baseline.recall * 100).toFixed(1)}% &rarr;{" "}
                <strong>{(whatIfResult.simulated.recall * 100).toFixed(1)}%</strong>{" "}
                ({whatIfResult.recall_delta >= 0 ? "+" : ""}
                {(whatIfResult.recall_delta * 100).toFixed(2)} pts)
              </span>
              <span className="ios-num text-slate-800 dark:text-zinc-200">
                Precision {(whatIfResult.baseline.precision * 100).toFixed(1)}% &rarr;{" "}
                <strong>{(whatIfResult.simulated.precision * 100).toFixed(1)}%</strong>
              </span>
            </div>
            <span className="font-mono text-[11px] text-slate-600 dark:text-zinc-400">
              {whatIfResult.top_rank_shifts.length} rank shift(s) in top 15
            </span>
          </div>
        )}

        <div ref={ruleMag.containerRef} onMouseLeave={ruleMag.onContainerLeave} className="relative overflow-x-auto">
          {ruleMag.lensElement}
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-white/50 dark:border-white/10 bg-white/30 dark:bg-black/45 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
                <th className="py-2.5 px-4">Rule ID</th>
                <th className="py-2.5 px-3">Rule Name</th>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-3 text-right">Sandbox Weight</th>
                <th className="py-2.5 px-3 text-right">Linked Cases</th>
                <th className="py-2.5 px-3 text-right">TP / FP</th>
                <th className="py-2.5 px-3 text-right">Precision</th>
                <th className="py-2.5 px-4 text-right">Alerts Fired</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
              {rules.map((r) => {
                const perf = perfMap.get(r.rule_id);
                return (
                  <tr
                    key={r.rule_id}
                    onMouseEnter={(e) => ruleMag.onRowEnter(e.currentTarget)}
                    className="liquid-row-magnify"
                  >
                    <td className="py-2.5 px-4 font-mono font-semibold text-slate-950 dark:text-white">{r.rule_id}</td>
                    <td className="py-2.5 px-3 font-medium text-slate-800 dark:text-zinc-200">
                      <div>{r.rule_name}</div>
                      <div className="text-[11px] text-slate-500 dark:text-zinc-400">{r.threshold_desc}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <Badge variant={tierVariant(r.severity)}>{r.severity}</Badge>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <input
                        type="number"
                        min={1}
                        max={60}
                        value={weightOverrides[r.rule_id] ?? r.base_weight}
                        onChange={(e) =>
                          setWeightOverrides((prev) => ({ ...prev, [r.rule_id]: Number(e.target.value) || r.base_weight }))
                        }
                        className="glass-pill w-16 px-2.5 py-1 rounded-full text-right ios-num text-slate-900 dark:text-white focus:outline-none"
                      />
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num">{perf?.linked_cases ?? "—"}</td>
                    <td className="py-2.5 px-3 text-right ios-num font-mono">
                      {perf ? (
                        <>
                          <span className="text-emerald-700 dark:text-emerald-400">{perf.tp_cases}</span> /{" "}
                          <span className="text-rose-600 dark:text-rose-400">{perf.fp_cases}</span>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right ios-num font-bold text-azure-700 dark:text-sky-300">
                      {perf ? `${(perf.precision * 100).toFixed(1)}%` : "—"}
                    </td>
                    <td className="py-2.5 px-4 text-right ios-num font-semibold text-slate-950 dark:text-white">
                      {r.hit_count}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Functions 202, 206, 216: Threshold Sensitivity Sweep & Temporal Drift */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Rule Threshold Sensitivity Sweep</h3>
              <p className="text-xs text-slate-600 dark:text-zinc-400">Precision vs. Recall trade-off across 0.5x–2.0x score multipliers</p>
            </div>
            <select
              value={sweepRuleId}
              onChange={(e) => setSweepRuleId(e.target.value)}
              className="px-3 py-1.5 rounded-full text-xs bg-white/30 dark:bg-white/[0.06] border border-white/60 dark:border-white/15 text-slate-900 dark:text-white"
            >
              {rules.map((r) => (
                <option key={r.rule_id} value={r.rule_id} className="bg-white dark:bg-zinc-900">
                  {r.rule_id} — {r.rule_name}
                </option>
              ))}
            </select>
          </div>
          {sweepData && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs ios-num">
                <thead>
                  <tr className="border-b border-white/40 dark:border-white/10 text-[10.5px] uppercase text-slate-600 dark:text-zinc-400">
                    <th className="py-2 px-2">Mult</th>
                    <th className="py-2 px-2 text-right">Cutoff</th>
                    <th className="py-2 px-2 text-right">Alerts</th>
                    <th className="py-2 px-2 text-right">Prec</th>
                    <th className="py-2 px-2 text-right">Recall</th>
                    <th className="py-2 px-2 text-right">F1</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/25 dark:divide-white/[0.06]">
                  {sweepData.points.map((pt) => (
                    <tr key={pt.multiplier}>
                      <td className="py-1.5 px-2 font-mono font-bold">{pt.multiplier}x</td>
                      <td className="py-1.5 px-2 text-right">{pt.score_cutoff}</td>
                      <td className="py-1.5 px-2 text-right">{pt.alerts_retained}</td>
                      <td className="py-1.5 px-2 text-right text-azure-700 dark:text-sky-300 font-semibold">{(pt.precision * 100).toFixed(1)}%</td>
                      <td className="py-1.5 px-2 text-right">{(pt.recall * 100).toFixed(1)}%</td>
                      <td className="py-1.5 px-2 text-right font-bold">{(pt.f1 * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="liquid-glass rounded-2xl p-5 space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">Temporal Score &amp; Precision Drift</h3>
            <p className="text-xs text-slate-600 dark:text-zinc-400">Chronological stability across 6 sequential case cohorts</p>
          </div>
          {driftData && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs ios-num">
                <thead>
                  <tr className="border-b border-white/40 dark:border-white/10 text-[10.5px] uppercase text-slate-600 dark:text-zinc-400">
                    <th className="py-2 px-2">Window</th>
                    <th className="py-2 px-2 text-right">Cases</th>
                    <th className="py-2 px-2 text-right">Mean Score</th>
                    <th className="py-2 px-2 text-right">TP Rate</th>
                    <th className="py-2 px-2 text-right">NDCG@20</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/25 dark:divide-white/[0.06]">
                  {driftData.buckets.map((b) => (
                    <tr key={b.cohort_index}>
                      <td className="py-1.5 px-2 font-mono text-[11px]">{b.window_start} → {b.window_end}</td>
                      <td className="py-1.5 px-2 text-right">{b.case_count}</td>
                      <td className="py-1.5 px-2 text-right font-bold text-azure-700 dark:text-sky-300">{b.avg_priority_score}</td>
                      <td className="py-1.5 px-2 text-right">{(b.tp_rate * 100).toFixed(1)}%</td>
                      <td className="py-1.5 px-2 text-right font-bold text-emerald-700 dark:text-emerald-400">{(b.ndcg_top20 * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Functions 251-255: 10-Decile Lift Curve, TP/FP Histogram, Rule Ablation & Feature PSI Drift */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-5 liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Feature Population Stability Index (PSI) &amp; Ablation Lift
            </h3>
            <Badge variant="BLUE">10-Decile Calibration</Badge>
          </div>

          <div className="space-y-1.5 text-xs">
            {featurePsi.map((fp) => (
              <div
                key={fp.feature}
                className="flex items-center justify-between px-3 py-2 rounded-xl bg-white/22 dark:bg-white/[0.04] border border-white/60 dark:border-white/10"
              >
                <span className="font-medium text-slate-800 dark:text-zinc-200">{fp.feature}</span>
                <div className="flex items-center gap-2 ios-num font-mono">
                  <span className="font-bold text-slate-950 dark:text-white">PSI {fp.psi}</span>
                  <Badge variant={fp.status === "STABLE" ? "LOW" : fp.status === "MONITOR" ? "HIGH" : "CRITICAL"}>
                    {fp.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>

          {ruleMarginal.length > 0 && (
            <div className="pt-2 border-t border-white/40 dark:border-white/10 space-y-1.5 text-xs">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-zinc-400">
                Top Sole-TP Rule Contributions (Ablation)
              </div>
              {ruleMarginal.slice(0, 4).map((rm) => (
                <div key={String(rm.rule_id)} className="flex items-center justify-between ios-num font-mono text-[11px]">
                  <span className="font-bold text-slate-900 dark:text-white">{String(rm.rule_id)}</span>
                  <span className="text-slate-600 dark:text-zinc-400">
                    Coverage {String(rm.coverage_pct)}% • Sole-TP {String(rm.unique_sole_tp_cases)} ({String(rm.marginal_loss_pct)}%)
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-7 liquid-glass rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white">
              Priority vs FIFO Decile Capture Curve &amp; Score Calibration Histogram
            </h3>
            <span className="text-[11px] ios-num text-slate-600 dark:text-zinc-400">
              {liftCurve.length} deciles • {scoreHist.length} score bins
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="overflow-x-auto max-h-48">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/50 dark:border-white/10 text-[10px] uppercase text-slate-600 dark:text-zinc-400">
                    <th className="py-1">@K%</th>
                    <th className="py-1 text-right">Priority</th>
                    <th className="py-1 text-right">FIFO</th>
                    <th className="py-1 text-right">Lift</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/25 dark:divide-white/[0.06] ios-num font-mono text-[11px]">
                  {liftCurve.map((d) => (
                    <tr key={d.k_pct}>
                      <td className="py-1 font-bold">{d.k_pct}%</td>
                      <td className="py-1 text-right text-azure-700 dark:text-sky-300">{(d.priority_recall * 100).toFixed(1)}%</td>
                      <td className="py-1 text-right text-slate-600 dark:text-zinc-400">{(d.fifo_recall * 100).toFixed(1)}%</td>
                      <td className="py-1 text-right font-bold text-emerald-700 dark:text-emerald-400">{d.lift_ratio}x</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {scoreHist.map((b) => (
                <div key={b.range} className="flex items-center justify-between px-2.5 py-1 rounded-lg bg-white/20 dark:bg-white/[0.04] text-[11px] ios-num font-mono">
                  <span className="text-slate-700 dark:text-zinc-300">{b.range}</span>
                  <span>
                    <strong className="text-emerald-700 dark:text-emerald-300">TP {b.tp}</strong> /{" "}
                    <span className="text-rose-600 dark:text-rose-300">FP {b.fp}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Provenance & SHA-256 Reproducibility Manifest */}
      <div className="liquid-glass rounded-2xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-white/50 dark:border-white/10 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-950 dark:text-white flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              Deterministic Provenance &amp; SHA-256 Reproducibility Manifest
            </h3>
            <p className="text-xs font-mono text-slate-600 dark:text-zinc-400">
              Seed: {evaluation.manifest?.seed} • Scale: {evaluation.manifest?.scale} • {evaluation.manifest?.generator_command}
            </p>
          </div>
          {manifestCheck && (
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4" /> Checked at {manifestCheck.verified_at}
            </span>
          )}
        </div>
        <div
          ref={manMag.containerRef}
          onMouseLeave={manMag.onContainerLeave}
          className="relative overflow-x-auto max-h-72"
        >
          {manMag.lensElement}
          <table className="w-full text-left border-collapse text-xs">
            <thead className="sticky top-0 z-10 bg-white/45 dark:bg-black/65 backdrop-blur-md border-b border-white/50 dark:border-white/10 text-[11px] font-semibold uppercase tracking-wider text-slate-700 dark:text-zinc-400">
              <tr>
                <th className="py-2.5 px-4">Exported Artifact</th>
                <th className="py-2.5 px-4">SHA-256 Checksum</th>
                {manifestCheck && <th className="py-2.5 px-4 text-right">Disk Verification</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/30 dark:divide-white/[0.06]">
              {digests.slice(manPage * manPageSize, (manPage + 1) * manPageSize).map(([file, hash]) => {
                const ver = manifestCheck?.files.find((f) => f.file === file);
                return (
                  <tr
                    key={file}
                    onMouseEnter={(e) => manMag.onRowEnter(e.currentTarget)}
                    className="liquid-row-magnify"
                  >
                    <td className="py-2 px-4 font-mono text-slate-800 dark:text-zinc-200">{file}</td>
                    <td className="py-2 px-4 font-mono text-slate-600 dark:text-zinc-400">{hash}</td>
                    {manifestCheck && (
                      <td className="py-2 px-4 text-right">
                        <Badge variant={ver?.status === "VERIFIED" ? "LOW" : "CRITICAL"}>
                          {ver?.status || "UNCHECKED"}
                        </Badge>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <GlassPagination
          total={digests.length}
          page={manPage}
          pageSize={manPageSize}
          onPageChange={setManPage}
          onPageSizeChange={(sz) => { setManPageSize(sz); setManPage(0); }}
          unitLabel="artifacts"
        />
      </div>
    </div>
  );
};
