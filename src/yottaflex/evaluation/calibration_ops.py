"""Held-Out Rule Threshold Sensitivity Sweep & Temporal Drift Evaluation (Functions 202 & 206)."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from yottaflex.evaluation.harness import _ndcg_at_k


def sweep_rule_threshold(
    conn: sqlite3.Connection,
    gt_path: Path,
    *,
    rule_id: str = "RULE-001",
) -> dict[str, Any]:
    """Sweep candidate threshold multipliers (0.5x..2.0x) on a rule against held-out TP/FP labels."""
    gt_rows = json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else []
    case_gt = {r["entity_id"]: r for r in gt_rows if r.get("entity_type") == "CASE"}

    alerts = [
        dict(r)
        for r in conn.execute(
            """
            SELECT a.alert_id, a.risk_score, cal.case_id
            FROM alerts a
            LEFT JOIN case_alert_links cal ON cal.alert_id = a.alert_id
            WHERE a.rule_id = ?
            """,
            (rule_id.strip().upper(),),
        ).fetchall()
    ]
    total_tp_cases = sum(1 for v in case_gt.values() if v.get("is_true_positive_risk"))
    points = []
    for mult in (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
        # Stricter threshold multiplier lowers caught volume while raising precision
        cutoff = 50.0 * mult
        caught = [a for a in alerts if float(a["risk_score"] or 0.0) >= cutoff]
        caught_cases = {a["case_id"] for a in caught if a["case_id"]}
        tp = sum(1 for cid in caught_cases if case_gt.get(cid, {}).get("is_true_positive_risk", False))
        fp = sum(1 for cid in caught_cases if cid in case_gt and not case_gt[cid].get("is_true_positive_risk", False))
        denom = tp + fp
        prec = round(tp / denom, 4) if denom else 0.0
        rec = round(tp / total_tp_cases, 4) if total_tp_cases else 0.0
        f1 = round((2 * prec * rec) / (prec + rec), 4) if (prec + rec) > 0 else 0.0
        points.append(
            {
                "multiplier": mult,
                "score_cutoff": round(cutoff, 1),
                "alerts_retained": len(caught),
                "tp_cases": tp,
                "fp_cases": fp,
                "precision": prec,
                "recall": rec,
                "f1": f1,
            }
        )
    return {"rule_id": rule_id.strip().upper(), "total_rule_alerts": len(alerts), "points": points}


def compute_temporal_drift(
    conn: sqlite3.Connection,
    gt_path: Path,
    *,
    buckets: int = 6,
) -> dict[str, Any]:
    """Evaluate chronological stability of priority score, TP density & NDCG@20 across time cohorts."""
    gt_rows = json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else []
    case_gt = {r["entity_id"]: r for r in gt_rows if r.get("entity_type") == "CASE"}

    all_cases = [
        dict(r)
        for r in conn.execute("SELECT case_id, priority_score, priority_tier, total_exposure_amount, created_at FROM cases ORDER BY created_at ASC, case_id ASC").fetchall()
    ]
    b_cnt = max(2, min(12, int(buckets)))
    if not all_cases:
        return {"buckets": []}
    chunk_sz = max(1, (len(all_cases) + b_cnt - 1) // b_cnt)
    series = []
    for idx in range(0, len(all_cases), chunk_sz):
        grp = all_cases[idx : idx + chunk_sz]
        if not grp:
            continue
        ranked = sorted(grp, key=lambda c: (-float(c["priority_score"]), c["case_id"]))
        rels = [1 if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False) else 0 for c in ranked]
        avg_score = round(sum(float(c["priority_score"]) for c in grp) / len(grp), 2)
        high_share = round(sum(1 for c in grp if c["priority_tier"] in {"CRITICAL", "HIGH"}) / len(grp), 4)
        tp_rate = round(sum(rels) / len(grp), 4)
        series.append(
            {
                "cohort_index": len(series) + 1,
                "window_start": grp[0]["created_at"][:10],
                "window_end": grp[-1]["created_at"][:10],
                "case_count": len(grp),
                "avg_priority_score": avg_score,
                "high_critical_share": high_share,
                "tp_rate": tp_rate,
                "ndcg_top20": _ndcg_at_k(rels, max(1, int(round(len(rels) * 0.2)))),
            }
        )
    return {"buckets": series}


def _load_case_gt(gt_path: Path) -> dict[str, dict[str, Any]]:
    gt_rows = json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else []
    return {r["entity_id"]: r for r in gt_rows if r.get("entity_type") == "CASE"}


def compute_lift_curve(conn: sqlite3.Connection, gt_path: Path) -> dict[str, Any]:
    """Function 251: Compute 10-decile Priority vs FIFO recall & lift curve (@10%..@100%)."""
    case_gt = _load_case_gt(gt_path)
    cases = [dict(r) for r in conn.execute("SELECT case_id, priority_score, created_at FROM cases").fetchall()]
    if not cases:
        return {"deciles": []}
    prio_sorted = sorted(cases, key=lambda c: (-float(c["priority_score"]), c["case_id"]))
    fifo_sorted = sorted(cases, key=lambda c: (str(c["created_at"]), c["case_id"]))
    total_tp = max(1, sum(1 for c in cases if case_gt.get(c["case_id"], {}).get("is_true_positive_risk")))

    deciles = []
    for k_pct in range(10, 101, 10):
        k = max(1, int(round(len(cases) * k_pct / 100.0)))
        prio_tp = sum(1 for c in prio_sorted[:k] if case_gt.get(c["case_id"], {}).get("is_true_positive_risk"))
        fifo_tp = sum(1 for c in fifo_sorted[:k] if case_gt.get(c["case_id"], {}).get("is_true_positive_risk"))
        p_rec = round(prio_tp / total_tp, 4)
        f_rec = round(fifo_tp / total_tp, 4)
        deciles.append(
            {
                "k_pct": k_pct,
                "cases_reviewed": k,
                "priority_tp": prio_tp,
                "fifo_tp": fifo_tp,
                "priority_recall": p_rec,
                "fifo_recall": f_rec,
                "lift_ratio": round(p_rec / f_rec, 2) if f_rec > 0 else 1.0,
            }
        )
    return {"total_cases": len(cases), "total_tp": total_tp, "deciles": deciles}


def compute_score_histogram(conn: sqlite3.Connection, gt_path: Path) -> dict[str, Any]:
    """Function 252: 10-bin calibration histogram of priority_score split into TP vs FP cases."""
    case_gt = _load_case_gt(gt_path)
    cases = conn.execute("SELECT case_id, priority_score FROM cases").fetchall()
    bins = [{"range": f"{b * 10}-{b * 10 + 10}", "low": b * 10, "high": b * 10 + 10, "tp": 0, "fp": 0} for b in range(10)]
    for c in cases:
        idx = min(9, max(0, int(float(c["priority_score"] or 0.0) // 10)))
        if case_gt.get(c["case_id"], {}).get("is_true_positive_risk"):
            bins[idx]["tp"] += 1
        else:
            bins[idx]["fp"] += 1
    return {"bins": bins}


def compute_typology_severity_matrix(conn: sqlite3.Connection, gt_path: Path) -> dict[str, Any]:
    """Function 253: Cross-tabulate planted typologies against priority_tier counts."""
    case_gt = _load_case_gt(gt_path)
    cases = conn.execute("SELECT case_id, priority_tier, priority_score FROM cases").fetchall()
    matrix: dict[str, dict[str, Any]] = {}
    for c in cases:
        gt = case_gt.get(c["case_id"], {})
        typ = str(gt.get("typology") or "UNKNOWN")
        if typ not in matrix:
            matrix[typ] = {"typology": typ, "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": 0, "_sum": 0.0}
        tier = str(c["priority_tier"])
        if tier in matrix[typ]:
            matrix[typ][tier] += 1
        matrix[typ]["total"] += 1
        matrix[typ]["_sum"] += float(c["priority_score"] or 0.0)
    rows = []
    for item in matrix.values():
        item["avg_score"] = round(item.pop("_sum") / max(1, item["total"]), 1)
        rows.append(item)
    rows.sort(key=lambda r: -r["total"])
    return {"rows": rows}


def compute_rule_marginal_lift(conn: sqlite3.Connection, gt_path: Path) -> dict[str, Any]:
    """Function 254: Ablate each rule (RULE-001..008) to estimate unique TP case contribution."""
    case_gt = _load_case_gt(gt_path)
    links = conn.execute("SELECT cal.case_id, al.rule_id FROM case_alert_links cal JOIN alerts al ON al.alert_id = cal.alert_id").fetchall()
    case_rules: dict[str, set[str]] = defaultdict(set)
    all_rules: set[str] = set()
    for r in links:
        case_rules[r["case_id"]].add(r["rule_id"])
        all_rules.add(r["rule_id"])
    tp_cases = [cid for cid, gt in case_gt.items() if gt.get("is_true_positive_risk")]
    total_tp = max(1, len(tp_cases))

    items = []
    for rid in sorted(all_rules):
        with_rule = sum(1 for cid in tp_cases if rid in case_rules.get(cid, set()))
        sole_tp = sum(1 for cid in tp_cases if case_rules.get(cid, set()) == {rid})
        items.append(
            {
                "rule_id": rid,
                "tp_cases_covered": with_rule,
                "unique_sole_tp_cases": sole_tp,
                "coverage_pct": round(100.0 * with_rule / total_tp, 1),
                "marginal_loss_pct": round(100.0 * sole_tp / total_tp, 1),
            }
        )
    items.sort(key=lambda x: (-x["unique_sole_tp_cases"], -x["tp_cases_covered"]))
    return {"total_tp_cases": len(tp_cases), "items": items}


def _psi_from_samples(expected: list[float], actual: list[float], edges: list[float]) -> float:
    if not expected or not actual:
        return 0.0
    n_e, n_a = len(expected), len(actual)
    total = 0.0
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        e_cnt = sum(1 for v in expected if (lo <= v < hi) or (i == len(edges) - 2 and v >= hi))
        a_cnt = sum(1 for v in actual if (lo <= v < hi) or (i == len(edges) - 2 and v >= hi))
        e_pct = max(0.001, e_cnt / n_e)
        a_pct = max(0.001, a_cnt / n_a)
        total += (a_pct - e_pct) * math.log(a_pct / e_pct)
    return round(total, 4)


def compute_feature_psi(conn: sqlite3.Connection) -> dict[str, Any]:
    """Function 255: Population Stability Index comparing earliest half vs latest half of transactions & cases."""
    txns = [float(r[0]) for r in conn.execute("SELECT amount FROM transactions ORDER BY occurred_at ASC, transaction_id ASC").fetchall()]
    mid_t = len(txns) // 2
    amt_psi = _psi_from_samples(txns[:mid_t], txns[mid_t:], [0.0, 100.0, 500.0, 2000.0, 5000.0, 1e9])

    cases = [float(r[0]) for r in conn.execute("SELECT priority_score FROM cases ORDER BY created_at ASC, case_id ASC").fetchall()]
    mid_c = len(cases) // 2
    score_psi = _psi_from_samples(cases[:mid_c], cases[mid_c:], [0.0, 25.0, 50.0, 75.0, 100.0])

    alerts = [float(r[0]) for r in conn.execute("SELECT risk_score FROM alerts ORDER BY created_at ASC, alert_id ASC").fetchall()]
    mid_a = len(alerts) // 2
    alert_psi = _psi_from_samples(alerts[:mid_a], alerts[mid_a:], [0.0, 25.0, 50.0, 75.0, 100.0])

    features = [
        {"feature": "Transaction Amount ($)", "psi": amt_psi, "status": "STABLE" if amt_psi < 0.1 else ("MONITOR" if amt_psi < 0.25 else "DRIFT")},
        {"feature": "Case Priority Score", "psi": score_psi, "status": "STABLE" if score_psi < 0.1 else ("MONITOR" if score_psi < 0.25 else "DRIFT")},
        {"feature": "Alert Risk Score", "psi": alert_psi, "status": "STABLE" if alert_psi < 0.1 else ("MONITOR" if alert_psi < 0.25 else "DRIFT")},
    ]
    return {"features": features}
