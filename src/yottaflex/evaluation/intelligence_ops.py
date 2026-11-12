"""Held-out Model Evaluation Intelligence, What-If Simulation & Provenance Verification (Functions 151-159)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yottaflex.evaluation.harness import _ndcg_at_k, verify_zero_leakage


def _average_precision(rels: list[int], k: int) -> float:
    if not rels or k <= 0:
        return 0.0
    k = min(k, len(rels))
    total_tp = sum(rels)
    if total_tp == 0:
        return 0.0
    hits = 0
    sum_prec = 0.0
    for idx in range(k):
        if rels[idx]:
            hits += 1
            sum_prec += hits / (idx + 1)
    return round(sum_prec / min(total_tp, k), 4)


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    idx = (len(sorted_vals) - 1) * pct
    lo = int(math.floor(idx))
    hi = min(len(sorted_vals) - 1, lo + 1)
    frac = idx - lo
    val = sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac
    return round(val, 2)


def _load_cases_and_gt(conn: sqlite3.Connection, gt_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    all_cases = [dict(r) for r in conn.execute("SELECT * FROM cases").fetchall()]
    gt_rows = json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else []
    case_gt = {r["entity_id"]: r for r in gt_rows if r.get("entity_type") == "CASE"}
    return all_cases, case_gt


def simulate_queue_cutoff(
    conn: sqlite3.Connection,
    gt_path: Path,
    *,
    k_pct: float = 20.0,
) -> dict[str, Any]:
    """Simulate Priority vs. FIFO precision, recall, F1, NDCG, and MAP at arbitrary capacity k_pct."""
    pct = max(1.0, min(100.0, float(k_pct))) / 100.0
    all_cases, case_gt = _load_cases_and_gt(conn, gt_path)
    ranked_prio = sorted(all_cases, key=lambda c: (-float(c["priority_score"]), -float(c["total_exposure_amount"]), c["case_id"]))
    ranked_fifo = sorted(all_cases, key=lambda c: (c["created_at"], c["case_id"]))

    rels_prio = [1 if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False) else 0 for c in ranked_prio]
    rels_fifo = [1 if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False) else 0 for c in ranked_fifo]
    total_tp = sum(rels_prio)
    k = max(1, int(round(len(all_cases) * pct))) if all_cases else 0

    def metrics_at(rels: list[int], ordered: list[dict[str, Any]]) -> dict[str, Any]:
        if k == 0:
            return {"k": 0, "tp": 0, "fp": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "ndcg": 0.0, "map": 0.0, "exposure_captured": 0.0}
        tp = sum(rels[:k])
        fp = k - tp
        prec = round(tp / k, 4)
        rec = round(tp / total_tp, 4) if total_tp else 0.0
        f1 = round((2 * prec * rec) / (prec + rec), 4) if (prec + rec) > 0 else 0.0
        exp_cap = round(sum(float(ordered[i]["total_exposure_amount"]) for i in range(k) if rels[i]), 2)
        return {
            "k": k,
            "tp": tp,
            "fp": fp,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "ndcg": _ndcg_at_k(rels, k),
            "map": _average_precision(rels, k),
            "exposure_captured": exp_cap,
        }

    p_m = metrics_at(rels_prio, ranked_prio)
    f_m = metrics_at(rels_fifo, ranked_fifo)
    lift = round(p_m["recall"] / f_m["recall"], 2) if f_m["recall"] > 0 else 0.0
    return {
        "k_pct": round(pct * 100, 1),
        "total_cases": len(all_cases),
        "total_true_positive": total_tp,
        "priority": p_m,
        "fifo": f_m,
        "recall_lift": lift,
    }


def get_rule_performance_attribution(conn: sqlite3.Connection, gt_path: Path) -> dict[str, Any]:
    """Compute held-out TP/FP precision, false-positive rate & case lift per RiskRule."""
    all_cases, case_gt = _load_cases_and_gt(conn, gt_path)
    case_map = {c["case_id"]: c for c in all_cases}
    rules = [dict(r) for r in conn.execute("SELECT * FROM risk_rules ORDER BY rule_id").fetchall()]

    links = conn.execute(
        """
        SELECT DISTINCT a.rule_id, cal.case_id, a.risk_score, a.alert_id
        FROM alerts a
        LEFT JOIN case_alert_links cal ON cal.alert_id = a.alert_id
        """
    ).fetchall()

    alerts_by_rule: dict[str, set[str]] = defaultdict(set)
    cases_by_rule: dict[str, set[str]] = defaultdict(set)
    score_sum_by_rule: dict[str, float] = defaultdict(float)

    for r in links:
        rid = r["rule_id"]
        aid = r["alert_id"]
        if aid not in alerts_by_rule[rid]:
            alerts_by_rule[rid].add(aid)
            score_sum_by_rule[rid] += float(r["risk_score"] or 0.0)
        if r["case_id"]:
            cases_by_rule[rid].add(r["case_id"])

    items: list[dict[str, Any]] = []
    for rule in rules:
        rid = rule["rule_id"]
        hit_alerts = len(alerts_by_rule[rid])
        linked_cases = sorted(cases_by_rule[rid])
        tp_cases = sum(1 for cid in linked_cases if case_gt.get(cid, {}).get("is_true_positive_risk", False))
        fp_cases = sum(1 for cid in linked_cases if cid in case_gt and not case_gt[cid].get("is_true_positive_risk", False))
        labeled_cnt = tp_cases + fp_cases
        precision = round(tp_cases / labeled_cnt, 4) if labeled_cnt else 0.0
        fp_rate = round(fp_cases / labeled_cnt, 4) if labeled_cnt else 0.0
        avg_case_score = (
            round(sum(float(case_map[cid]["priority_score"]) for cid in linked_cases if cid in case_map) / len(linked_cases), 2)
            if linked_cases
            else 0.0
        )
        items.append(
            {
                "rule_id": rid,
                "rule_name": rule["rule_name"],
                "category": rule["category"],
                "severity": rule["severity"],
                "base_weight": int(rule["base_weight"]),
                "alerts_fired": hit_alerts,
                "linked_cases": len(linked_cases),
                "tp_cases": tp_cases,
                "fp_cases": fp_cases,
                "precision": precision,
                "false_positive_rate": fp_rate,
                "avg_alert_score": round(score_sum_by_rule[rid] / hit_alerts, 2) if hit_alerts else 0.0,
                "avg_case_score": avg_case_score,
            }
        )
    return {"rules": items}


def run_what_if_rule_simulation(
    conn: sqlite3.Connection,
    gt_path: Path,
    *,
    weight_overrides: dict[str, float],
    k_pct: float = 20.0,
) -> dict[str, Any]:
    """Non-mutating simulation predicting Priority Top-K recall/precision if rule base weights change."""
    all_cases, case_gt = _load_cases_and_gt(conn, gt_path)
    rules = {r["rule_id"]: float(r["base_weight"]) for r in conn.execute("SELECT rule_id, base_weight FROM risk_rules").fetchall()}

    case_rules: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for r in conn.execute(
        """
        SELECT cal.case_id, a.rule_id, AVG(a.risk_score) AS mean_score
        FROM case_alert_links cal
        JOIN alerts a ON a.alert_id = cal.alert_id
        GROUP BY cal.case_id, a.rule_id
        """
    ).fetchall():
        case_rules[r["case_id"]].append((r["rule_id"], float(r["mean_score"] or 0.0)))

    simulated_cases: list[dict[str, Any]] = []
    for c in all_cases:
        cid = c["case_id"]
        base_score = float(c["priority_score"])
        linked = case_rules.get(cid, [])
        delta = 0.0
        for rid, _ in linked:
            orig_w = rules.get(rid, 20.0)
            new_w = float(weight_overrides.get(rid, orig_w))
            delta += (new_w - orig_w) * 0.45
        sim_score = max(0.0, min(100.0, base_score + delta))
        simulated_cases.append({**c, "sim_score": sim_score})

    pct = max(1.0, min(100.0, float(k_pct))) / 100.0
    k = max(1, int(round(len(simulated_cases) * pct))) if simulated_cases else 0
    baseline_ranked = sorted(all_cases, key=lambda c: (-float(c["priority_score"]), -float(c["total_exposure_amount"]), c["case_id"]))
    sim_ranked = sorted(simulated_cases, key=lambda c: (-float(c["sim_score"]), -float(c["total_exposure_amount"]), c["case_id"]))

    rels_base = [1 if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False) else 0 for c in baseline_ranked]
    rels_sim = [1 if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False) else 0 for c in sim_ranked]
    total_tp = sum(rels_base)

    base_tp = sum(rels_base[:k])
    sim_tp = sum(rels_sim[:k])
    base_rec = round(base_tp / total_tp, 4) if total_tp else 0.0
    sim_rec = round(sim_tp / total_tp, 4) if total_tp else 0.0
    base_prec = round(base_tp / k, 4) if k else 0.0
    sim_prec = round(sim_tp / k, 4) if k else 0.0

    rank_shifts = []
    base_pos = {c["case_id"]: idx + 1 for idx, c in enumerate(baseline_ranked)}
    for idx, c in enumerate(sim_ranked[:15]):
        old_pos = base_pos.get(c["case_id"], idx + 1)
        if old_pos != idx + 1:
            rank_shifts.append(
                {
                    "case_id": c["case_id"],
                    "old_rank": old_pos,
                    "new_rank": idx + 1,
                    "shift": old_pos - (idx + 1),
                    "baseline_score": round(float(c["priority_score"]), 2),
                    "simulated_score": round(float(c["sim_score"]), 2),
                }
            )

    return {
        "k": k,
        "k_pct": round(pct * 100, 1),
        "baseline": {"tp": base_tp, "precision": base_prec, "recall": base_rec, "ndcg": _ndcg_at_k(rels_base, k)},
        "simulated": {"tp": sim_tp, "precision": sim_prec, "recall": sim_rec, "ndcg": _ndcg_at_k(rels_sim, k)},
        "recall_delta": round(sim_rec - base_rec, 4),
        "precision_delta": round(sim_prec - base_prec, 4),
        "top_rank_shifts": rank_shifts[:8],
    }


def enrich_typology_percentiles(typology_stats: list[dict[str, Any]], all_cases: list[dict[str, Any]], case_gt: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compute P25/P50/P75/P90 percentiles per typology and TP-vs-FP separation gap."""
    grouped: dict[str, list[float]] = defaultdict(list)
    tp_scores: list[float] = []
    fp_scores: list[float] = []
    for c in all_cases:
        gt = case_gt.get(c["case_id"])
        t = gt["typology"] if gt else "ORPHAN_INJECTED"
        sc = float(c["priority_score"])
        grouped[t].append(sc)
        if gt:
            if gt.get("is_true_positive_risk"):
                tp_scores.append(sc)
            else:
                fp_scores.append(sc)

    enriched = []
    for row in typology_stats:
        scores = sorted(grouped.get(row["typology"], []))
        enriched.append(
            {
                **row,
                "p25_score": _percentile(scores, 0.25),
                "p50_score": _percentile(scores, 0.50),
                "p75_score": _percentile(scores, 0.75),
                "p90_score": _percentile(scores, 0.90),
            }
        )
    tp_mean = round(sum(tp_scores) / len(tp_scores), 2) if tp_scores else 0.0
    fp_mean = round(sum(fp_scores) / len(fp_scores), 2) if fp_scores else 0.0
    return {
        "typology_stats": enriched,
        "tp_mean_score": tp_mean,
        "fp_mean_score": fp_mean,
        "separation_gap": round(tp_mean - fp_mean, 2),
    }


def verify_export_manifest(export_dir: Path) -> dict[str, Any]:
    """Recompute SHA-256 checksums across manifest.json entries and return verification report."""
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.exists():
        return {"verified": False, "error": "manifest.json missing", "files": [], "matched_count": 0, "total_count": 0}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksums = manifest.get("sha256_checksums", {}) or {}
    files = []
    matched = 0
    for rel_path, expected in sorted(checksums.items()):
        target = export_dir / rel_path
        if not target.exists():
            files.append({"file": rel_path, "expected": expected, "actual": None, "status": "MISSING"})
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        ok = actual == expected
        if ok:
            matched += 1
        files.append({"file": rel_path, "expected": expected, "actual": actual, "status": "VERIFIED" if ok else "MISMATCH"})
    return {
        "verified": matched == len(files) and len(files) > 0,
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matched_count": matched,
        "total_count": len(files),
        "files": files,
    }


def check_live_zero_leakage(src_root: Path) -> dict[str, Any]:
    """Run live AST inspection verifying engine and validation never reference held-out ground truth."""
    res = verify_zero_leakage(src_root)
    res["checked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    res["file_count"] = len(res.get("files_inspected", []))
    return res


def export_evaluation_report(
    evaluation_payload: dict[str, Any],
    rule_perf: dict[str, Any],
    *,
    fmt: str = "json",
) -> tuple[bytes, str, str]:
    """Export held-out evaluation benchmark + rule precision attribution as JSON or CSV."""
    if str(fmt).lower() == "csv":
        buf = io.StringIO()
        cols = ["rule_id", "rule_name", "category", "severity", "base_weight", "alerts_fired", "linked_cases", "tp_cases", "fp_cases", "precision", "false_positive_rate", "avg_alert_score", "avg_case_score"]
        writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for r in rule_perf.get("rules", []):
            writer.writerow({k: r.get(k, "") for k in cols})
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "yottaflex_evaluation_report.csv"

    bundle = {**evaluation_payload, "rule_performance": rule_perf.get("rules", [])}
    return json.dumps(bundle, indent=2).encode("utf-8"), "application/json; charset=utf-8", "yottaflex_evaluation_report.json"
