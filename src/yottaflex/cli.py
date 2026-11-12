"""CLI entrypoint for YottaFlex generation, schema export, and reproducibility checks."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from yottaflex import DEFAULT_SEED
from yottaflex.api.server import run_server
from yottaflex.evaluation.harness import run_evaluation
from yottaflex.generator.exporter import export_world
from yottaflex.generator.world_generator import generate_world
from yottaflex.schema_spec import write_schema_artifacts
from yottaflex.validation.validator import run_validation


def cmd_generate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    write_schema_artifacts(root)
    out_dir = Path(args.output) if args.output else root / "data" / "exports" / args.scale
    cmd_str = f"python3 -m yottaflex.cli generate --scale {args.scale} --seed {args.seed}"

    world = generate_world(seed=args.seed, scale_name=args.scale)
    manifest = export_world(
        world,
        out_dir,
        seed=args.seed,
        scale_name=args.scale,
        generator_command=cmd_str,
    )
    print(f"[yottaflex] Generated '{args.scale}' dataset (seed={args.seed}) -> {out_dir}")
    for k, v in manifest["row_counts"].items():
        print(f"  - {k}: {v:,} rows")
    return 0


def cmd_verify_reproducibility(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    cmd_str = f"python3 -m yottaflex.cli generate --scale {args.scale} --seed {args.seed}"
    with tempfile.TemporaryDirectory() as tmp:
        d1 = Path(tmp) / "run1"
        d2 = Path(tmp) / "run2"
        w1 = generate_world(seed=args.seed, scale_name=args.scale)
        m1 = export_world(w1, d1, seed=args.seed, scale_name=args.scale, generator_command=cmd_str)
        w2 = generate_world(seed=args.seed, scale_name=args.scale)
        m2 = export_world(w2, d2, seed=args.seed, scale_name=args.scale, generator_command=cmd_str)

        assert m1["row_counts"] == m2["row_counts"], "Row count mismatch between runs!"
        assert m1["sha256_checksums"] == m2["sha256_checksums"], "Checksum mismatch between runs!"

        print(f"[yottaflex] Reproducibility PASSED for scale='{args.scale}', seed={args.seed}:")
        print(f"  - Verified {len(m1['sha256_checksums'])} files across 2 independent runs (100% identical SHA-256).")
        for fname, digest in sorted(m1["sha256_checksums"].items())[:6]:
            print(f"    {fname}: {digest[:16]}...")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    export_dir = Path(args.data_dir) if args.data_dir else root / "data" / "exports" / args.scale
    dist_dir = root / "web" / "dist"
    web_dir = dist_dir if dist_dir.is_dir() else root / "web"
    run_server(export_dir=export_dir, web_dir=web_dir, host=args.host, port=args.port)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    export_dir = Path(args.data_dir) if args.data_dir else root / "data" / "exports" / args.scale
    res = run_validation(export_dir, write_reports=True)
    s = res["summary"]
    print(f"[yottaflex] Validation complete ({export_dir}):")
    print(f"  - Checks passed clean: {s['checks_passed_clean']}/{s['total_checks']}")
    print(f"  - Quarantined exceptions: {s['total_quarantined_exceptions']}")
    for k, v in sorted(s["exceptions_by_issue_type"].items()):
        print(f"    * {k}: {v}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    export_dir = Path(args.data_dir) if args.data_dir else root / "data" / "exports" / args.scale
    rep = run_evaluation(export_dir, src_root=root / "src", write_reports=True)
    pm = rep["prioritization_metrics"]
    vc = rep["validation_catch_rate"]
    print(f"[yottaflex] Evaluation complete ({export_dir}):")
    print(f"  - Zero Ground-Truth Leakage: {rep['zero_leakage']['zero_leakage_verified']}")
    print(f"  - Top-50 Precision: {pm['priority_top50']['precision']:.1%} (FIFO: {pm['fifo_top50']['precision']:.1%})")
    print(f"  - Top-20% Recall:   {pm['priority_top20pct']['recall']:.1%} (FIFO: {pm['fifo_top20pct']['recall']:.1%})")
    print(f"  - NDCG@50:          {pm['priority_ndcg_at_50']:.4f} (FIFO: {pm['fifo_ndcg_at_50']:.4f})")
    print(f"  - FP Suppression (<40): {pm['false_positive_suppression_rate_below_40']:.1%}")
    print(f"  - Edge Cases Caught: {vc['quarantined_exceptions']}/{vc['injected_edge_cases']} (all 5 types={vc['all_issue_types_caught']})")
    return 0


def cmd_run_all(args: argparse.Namespace) -> int:
    args.output = None
    args.data_dir = None
    cmd_generate(args)
    cmd_verify_reproducibility(args)
    cmd_validate(args)
    cmd_evaluate(args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yottaflex", description="YottaFlex Transaction Prioritization CLI")
    p.add_argument("--root", default=".", help="Project root directory")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Generate schema docs and synthetic dataset exports")
    g.add_argument("--scale", choices=["starter", "full"], default="starter")
    g.add_argument("--seed", type=int, default=DEFAULT_SEED)
    g.add_argument("--output", default=None, help="Optional custom export directory")
    g.set_defaults(func=cmd_generate)

    r = sub.add_parser("verify-repro", help="Run generator twice with same seed and compare checksums")
    r.add_argument("--scale", choices=["starter", "full"], default="starter")
    r.add_argument("--seed", type=int, default=DEFAULT_SEED)
    r.set_defaults(func=cmd_verify_reproducibility)

    v = sub.add_parser("validate", help="Run 9-check integrity & reconciliation validator")
    v.add_argument("--scale", choices=["starter", "full"], default="full")
    v.add_argument("--data-dir", default=None, help="Optional custom export directory")
    v.set_defaults(func=cmd_validate)

    e = sub.add_parser("evaluate", help="Run ground-truth evaluation & prioritization lift harness")
    e.add_argument("--scale", choices=["starter", "full"], default="full")
    e.add_argument("--data-dir", default=None, help="Optional custom export directory")
    e.set_defaults(func=cmd_evaluate)

    ra = sub.add_parser("run-all", help="Generate, verify 2x reproducibility, validate, and evaluate")
    ra.add_argument("--scale", choices=["starter", "full"], default="full")
    ra.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ra.set_defaults(func=cmd_run_all)

    s = sub.add_parser("serve", help="Launch Analyst Triage & Graph Investigation Workbench")
    s.add_argument("--scale", choices=["starter", "full"], default="full")
    s.add_argument("--data-dir", default=None, help="Optional custom export directory")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
