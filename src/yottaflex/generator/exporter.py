"""Multi-format deterministic exporter (CSV, JSON, SQL seed, SQLite DB, manifest)."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from yottaflex.schema_spec import SCHEMA_VERSION, TABLES, build_schema_sql


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sql_literal(val: Any) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


def export_world(
    world: dict[str, Any],
    output_dir: Path,
    *,
    seed: int,
    scale_name: str,
    generator_command: str,
) -> dict[str, Any]:
    """Export all tables, isolated ground_truth, SQL seed, SQLite DB, and manifest."""
    csv_dir = output_dir / "csv"
    json_dir = output_dir / "json"
    sql_dir = output_dir / "sql"
    gt_dir = output_dir / "ground_truth"
    for d in (csv_dir, json_dir, sql_dir, gt_dir):
        d.mkdir(parents=True, exist_ok=True)

    checksums: dict[str, str] = {}
    row_counts: dict[str, int] = {}

    schema_sql = build_schema_sql()
    schema_sql_path = sql_dir / "schema.sql"
    schema_sql_path.write_text(schema_sql, encoding="utf-8")
    checksums[f"sql/schema.sql"] = _sha256_file(schema_sql_path)

    # Export 16 input/entity tables to CSV, JSON, and seed.sql
    seed_sql_path = sql_dir / "seed.sql"
    with seed_sql_path.open("w", encoding="utf-8", newline="\n") as sql_f:
        sql_f.write("-- YottaFlex Deterministic Seed Data\n")
        sql_f.write("PRAGMA foreign_keys = ON;\nBEGIN TRANSACTION;\n\n")

        for tbl_spec in TABLES:
            tname = tbl_spec.table_name
            rows: list[dict[str, Any]] = world[tname]
            cols = [f.name for f in tbl_spec.fields]
            row_counts[tname] = len(rows)

            # CSV
            csv_path = csv_dir / f"{tname}.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as cf:
                writer = csv.DictWriter(cf, fieldnames=cols, extrasaction="ignore")
                writer.writeheader()
                for r in rows:
                    writer.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
            checksums[f"csv/{tname}.csv"] = _sha256_file(csv_path)

            # JSON
            json_path = json_dir / f"{tname}.json"
            json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
            checksums[f"json/{tname}.json"] = _sha256_file(json_path)

            # Batched SQL INSERTs
            if rows:
                col_list = ", ".join(cols)
                batch_size = 250
                for start in range(0, len(rows), batch_size):
                    chunk = rows[start : start + batch_size]
                    sql_f.write(f"INSERT INTO {tname} ({col_list}) VALUES\n")
                    vals_sql = []
                    for r in chunk:
                        vals_sql.append("  (" + ", ".join(_sql_literal(r.get(c)) for c in cols) + ")")
                    sql_f.write(",\n".join(vals_sql) + ";\n")
                sql_f.write("\n")

        sql_f.write("COMMIT;\n")

    checksums["sql/seed.sql"] = _sha256_file(seed_sql_path)

    # Build SQLite database enforcing foreign keys
    db_path = output_dir / "yottaflex.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        for tbl_spec in TABLES:
            tname = tbl_spec.table_name
            rows = world[tname]
            if not rows:
                continue
            cols = [f.name for f in tbl_spec.fields]
            placeholders = ", ".join(["?"] * len(cols))
            col_list = ", ".join(cols)
            tuples = [tuple(r.get(c) for c in cols) for r in rows]
            conn.executemany(f"INSERT INTO {tname} ({col_list}) VALUES ({placeholders})", tuples)
        conn.commit()
    finally:
        conn.close()

    # Export isolated ground_truth
    gt_rows: list[dict[str, Any]] = world["ground_truth"]
    row_counts["ground_truth"] = len(gt_rows)
    gt_cols = [
        "scenario_id",
        "entity_type",
        "entity_id",
        "typology",
        "issue_type",
        "is_true_positive_risk",
        "expected_decision",
        "notes",
    ]
    gt_csv = gt_dir / "ground_truth.csv"
    with gt_csv.open("w", encoding="utf-8", newline="") as gcf:
        writer = csv.DictWriter(gcf, fieldnames=gt_cols)
        writer.writeheader()
        for r in gt_rows:
            writer.writerow(r)
    checksums["ground_truth/ground_truth.csv"] = _sha256_file(gt_csv)

    gt_json = gt_dir / "ground_truth.json"
    gt_json.write_text(json.dumps(gt_rows, indent=2) + "\n", encoding="utf-8")
    checksums["ground_truth/ground_truth.json"] = _sha256_file(gt_json)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "scale": scale_name,
        "generator_command": generator_command,
        "provenance": "100% synthetic deterministic generation; no external PII or restricted public data.",
        "row_counts": row_counts,
        "sha256_checksums": checksums,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return manifest
