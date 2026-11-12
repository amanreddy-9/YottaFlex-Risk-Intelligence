# YottaFlex Risk Intelligence — Architectural Reasoning & Technical Decisions

> **Submission Document Reference:** *YottaFlex AI Recruitment Drive — Candidate Project Submission Guidelines (Item 04: MAKE YOUR REASONING VISIBLE)*  
> **Project:** YottaFlex Risk Intelligence — AI-Powered Risk & Ledger Intelligence  
> **Author:** `amanreddy-9` (`amanreddyjukonti@gmail.com`)

---

## 1. Problem Statement & Business Context

Financial crime investigation teams face a persistent operational crisis: **alert fatigue** and **opaque prioritization**. Traditional rule-based transaction monitoring systems generate massive false-positive volumes (>95% in typical tier-1 banks), burying true criminal rings beneath isolated, disconnected alerts. When machine learning models are deployed to re-score alerts, compliance officers and regulatory examiners (FinCEN, FCA, BaFin) frequently reject them due to lack of explainability, data leakage, and untraceable decisions.

**YottaFlex Risk Intelligence** solves this problem end-to-end:
1. **Reconciled Synthetic Ledger:** Eliminates proprietary data exposure with a mathematically sound, double-entry reconciled synthetic banking world (seed `20261022`).
2. **Transparent, Explainable Prioritization:** Evaluates observable behavioral rules (velocity spikes, rapid movement, fan-in/fan-out mule structuring, new device anomalies) into deterministic priority scores ($[0, 100]$).
3. **Entity-Linkage Graph Clustering:** Automatically clusters isolated alerts across shared accounts, counterparties, and devices into consolidated **Cases** ($3.25\times$ compression).
4. **9-Check Exception Quarantine:** Isolates corrupt or anomalous data into an immutable Quarantine Queue without halting clean transaction processing.
5. **Zero Ground-Truth Leakage Guarantee:** Enforces strict AST-level separation between observable transaction features and evaluation ground truth.
6. **Institutional Analyst Workbench:** A high-fidelity, dual-mode (Light & Dark) React + TypeScript interface styled with custom **3D Liquid Glassmorphism**, interactive graph exploration, GoAML XML generation, cryptographic evidence sealing, and conversational AI guidance.

---

## 2. Key Assumptions

1. **Deterministic Reproducibility:** Every customer, account, balance change, and transaction must be strictly reproducible from a single integer seed (`20261022`). Two independent runs must yield 100% identical SHA-256 checksums across all CSV, JSON, and SQL exports.
2. **Double-Entry Accounting Invariant:** For every debit leg of an internal transfer, an exact matching credit leg must exist at the identical timestamp. Account balances must never drop below allowed overdraft limits.
3. **Graph-Centric Criminal Structuring:** Money laundering and mule operations do not occur in isolated accounts. Real-world typologies (mule rings, smurfing, circular flow) expose themselves via shared hardware identifiers (`device_id`) and counterparty transfer paths (`transfer_links`).
4. **Observable vs. Latent Knowledge Separation:** Compliance analysts must prioritize cases based solely on facts available at transaction time. Ground-truth criminal labels (`is_synthetic_anomaly`, `planted_typology`) exist strictly for benchmarking model lift and must never leak into scoring logic.

---

## 3. Core Architectural Decisions

### A. Zero External Python Dependencies for Backend & CLI
- **Decision:** The entire backend engine, synthetic generator, 9-check validator, evaluation harness, and REST server run on **Python 3.11+ standard library only** (`sqlite3`, `http.server`, `hashlib`, `json`, `csv`, `math`).
- **Reasoning:** Zero dependency drift, zero installation friction, no conflicting virtual environment C-extensions, and instant startup in any air-gapped or containerized banking infrastructure.

### B. SQLite + In-Memory Caching for Hybrid OLTP/Graph Queries
- **Decision:** Use an embedded SQLite database with automatic indexing on foreign keys (`alert_trigger_facts`, `transfer_links`, `case_alert_links`, `account_device_links`) and automatic hydration from `sql/seed.sql`.
- **Reasoning:** Avoids requiring an external PostgreSQL or Neo4j server for local evaluation while delivering **sub-millisecond query latencies** (`0.4ms` for account burst profiling, `15.4ms` for full-graph fan-in/fan-out mule hub detection across 100k transactions).

### C. Connected-Component Entity Graph Clustering
- **Decision:** Group alerts into cases using breadth-first search (BFS) over bipartite entity graphs (Accounts $\leftrightarrow$ Devices $\leftrightarrow$ Counterparties).
- **Reasoning:** Reduces 923 fragmented raw alerts to 284 multi-alert investigation cases ($3.25\times$ workload reduction), presenting analysts with a holistic view of the entire syndicate rather than piecemeal tickets.

### D. Multi-Check Quarantine Queue
- **Decision:** When transactions violate fundamental ledger rules (e.g., transaction on closed account, negative balance without overdraft, unreconciled transfer leg), the validator quarantines them into `quarantine_exceptions.json` with an audit reason and disables them from alert generation.
- **Reasoning:** Production ledgers must never silently swallow data corruption, nor should they allow bad data to pollute downstream risk scores.

### E. Static Analysis AST Zero-Leakage Enforcement
- **Decision:** Enforce architectural separation via `tests/test_zero_leakage_ast_guard.py`, parsing the AST of `yottaflex/engine` and `yottaflex/validation` to guarantee that no non-docstring identifiers reference `ground_truth`.
- **Reasoning:** Prevents subtle lookahead bias or label leakage from inflating model lift metrics.

---

## 4. Key Trade-Offs

| Trade-Off Considered | Chosen Approach | Alternative Considered | Justification |
| :--- | :--- | :--- | :--- |
| **Data Processing Framework** | Pure Python standard library with typed dataclasses | Pandas / Polars | Eliminates 200MB+ virtual environment dependencies; runs anywhere with Python 3.11+ in under 1 second. |
| **Database Persistence in Git** | Push SQL seeds (`seed.sql`), auto-bootstrap SQLite on `serve` | Commit binary `yottaflex.db` (43MB) | Prevents binary git conflicts during ongoing development and saves repository bloat while guaranteeing instant 0.6s bootstrap. |
| **Case Clustering Algorithm** | Bipartite BFS connected components | Louvain / Spectral community detection | Connected components provide deterministic, fully explainable boundaries without tuning hyperparameter thresholds ($\gamma$). |
| **Evaluation Metrics** | Top-$k$ Precision, Recall@20%, NDCG@50, FP Suppression | Raw ROC-AUC | In AML compliance, analyst capacity is strictly constrained (e.g., 50 cases/day); ROC-AUC is misleading when class imbalance exceeds 1:100. Top-$k$ Lift directly measures saved analyst hours. |
| **Frontend Architecture** | Production-built React 18 SPA served by Python backend | Separate Node.js proxy server | Single-command launch (`make serve`) serves both API and rich UI without requiring Node.js on the evaluator's machine. |

---

## 5. Verification & Testing Strategy

The repository includes a comprehensive 34-suite automated test harness (`python3 -m unittest discover -s tests -v`):

1. **Integrity & Generation Tests:**
   - [`test_part1_generation.py`](file:///Users/amanreddyj/Downloads/YottaFlexproject/tests/test_part1_generation.py): Verifies ledger balancing, foreign key consistency, and deterministic seeds.
   - [`test_part3_validation_eval.py`](file:///Users/amanreddyj/Downloads/YottaFlexproject/tests/test_part3_validation_eval.py): Verifies that all 10 injected negative scenarios across 5 distinct issue types are quarantined.
2. **Scoring & Engine Tests:**
   - [`test_batch3_txn_detail_patterns_scoring.py`](file:///Users/amanreddyj/Downloads/YottaFlexproject/tests/test_batch3_txn_detail_patterns_scoring.py): Checks velocity spike, circular flow, and dormant reactivation scoring math.
   - [`test_batch4_risk_reeval_and_alerts.py`](file:///Users/amanreddyj/Downloads/YottaFlexproject/tests/test_batch4_risk_reeval_and_alerts.py): Validates rule threshold updates and dynamic case recalculation.
3. **Workflow, RBAC & Forensics Tests:**
   - [`test_batch5_alert_triage_queue_dossier.py`](file:///Users/amanreddyj/Downloads/YottaFlexproject/tests/test_batch5_alert_triage_queue_dossier.py): Validates analyst triage, case state transitions, and dossier assembly.
   - [`test_batch8_forensics_playbooks_controls.py`](file:///Users/amanreddyj/Downloads/YottaFlexproject/tests/test_batch8_forensics_playbooks_controls.py): Maker-checker four-eyes approvals, SIEM outbox queuing, and playbook checklist automation.
4. **Enterprise Intelligence & Deep Evaluation Tests:**
   - [`test_batch10_enterprise_intelligence_qa.py`](file:///Users/amanreddyj/Downloads/YottaFlexproject/tests/test_batch10_enterprise_intelligence_qa.py): Tests sanctions fuzzy matching, GoAML XML export, cryptographic SHA-256 evidence seals, and QA sampling.
   - [`test_batch11_deep_eval_telemetry_exports.py`](file:///Users/amanreddyj/Downloads/YottaFlexproject/tests/test_batch11_deep_eval_telemetry_exports.py): Tests 10-decile lift curve, TP/FP score histogram, PSI drift calculation, and live API telemetry.
5. **Zero-Leakage AST Guard:**
   - Statically verifies no access to `ground_truth` in `engine/` or `validation/`.
6. **Bit-for-Bit 2x Reproducibility:**
   - Validates that running generation twice produces 100% identical SHA-256 digests across all 36 exported files.

---

## 6. Observed Benchmarks & Performance Metrics

On the full synthetic dataset (**5,000 customers, 7,000 accounts, 100,000 transactions, 4,640 transfer links, 923 alerts, 284 cases**):

- **Top-50 Queue Precision:** **`100.0%`** (`50/50`) vs. **`50.0%`** (`25/50`) FIFO baseline ($2.0\times$ lift).
- **Top-20% Recall:** **`34.1%`** vs. **`16.2%`** FIFO baseline.
- **NDCG@50:** **`1.0000`** vs. **`0.6305`** FIFO baseline.
- **False-Positive Suppression:** **`100.0%`** of false positives scored below the `MEDIUM` (40) threshold.
- **Validation Catch Rate:** **`10/10`** (`100%`) injected edge cases caught across all 5 failure modes.
- **API Latencies (SQLite on Apple Silicon):**
  - Account burst profiling: `0.4 ms`
  - Audit chain cryptographic verification: `0.8 ms`
  - Alert co-occurrence matrix: `0.9 ms`
  - 10-decile lift curve computation: `5.3 ms`
  - Fan-in / Fan-out mule hub detection: `15.4 ms`
  - Feature PSI drift computation: `37.0 ms`
  - Balance continuity audit: `112.5 ms`

---

## 7. Known Limitations & Production Roadmap

1. **Scale Horizons:** Single-node SQLite performs sub-second up to $\sim 10^6$ transactions. For 100M+ real-time streaming transactions, the storage layer should be swapped for Cassandra/PostgreSQL partitioned by account shard, coupled with Apache Flink for real-time rule evaluation.
2. **Graph Expansion:** The bipartite BFS clustering algorithm runs in memory. In an enterprise with 50M accounts, graph clustering would transition to distributed GraphX or Amazon Neptune.
3. **External Sanctions Integration:** The current sanctions engine utilizes Jaro-Winkler/Levenshtein fuzzy matching against synthetic PEP/OFAC lists. In enterprise production, this connects to live Dow Jones or Refinitiv World-Check feeds via the webhook registry implemented in Batch 10.
