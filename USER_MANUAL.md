# RiskOS — Comprehensive System & Operational Reference Manual

```text
  ██████╗ ██╗███████╗██╗  ██╗     ██████╗ ███████╗
  ██╔══██╗██║██╔════╝██║ ██╔╝    ██╔═══██╗██╔════╝
  ██████╔╝██║███████╗█████╔╝     ██║   ██║███████╗
  ██╔══██╗██║╚════██║██╔═██╗     ██║   ██║╚════██║
  ██║  ██║██║███████║██║  ██╗    ╚██████╔╝███████║
  ╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝     ╚═════╝ ╚══════╝
       AI-Powered Risk & Ledger Intelligence
```

> **Document Classification:** Official System & Operational Reference Manual  
> **Release:** Enterprise Edition v1.0.0  
> **Applicable System:** RiskOS Financial Crime & Ledger Intelligence Platform  
> **Author & Chief Architect:** Aman Reddy J (`amanreddy-9`, `amanreddyjukonti@gmail.com`)  
> **Reference Repository:** `https://github.com/amanreddy-9/YottaFlex-Risk-Intelligence`  
> **Default Engine Calibration Seed:** `20261022`  

---

## Safety Warnings, Regulatory Disclaimers & Operational Conventions

Before operating RiskOS, all operators (Financial Crime Analysts, Compliance Officers, Risk Examiners, and System Administrators) must review the following operational conventions:

> [!IMPORTANT]
> **Regulatory Admissibility Notice:** All investigative actions taken within RiskOS—including alert dispositioning, case closures, SAR escalations, and GoAML XML exports—are cryptographically logged with immutable SHA-256 digital seals. Operator actions are subject to regulatory examination under FinCEN (31 CFR Chapter X), FATF Recommendations 10 & 20, FCA MLRs, and BaFin AML regulations.

> [!WARNING]
> **Four-Eyes Verification Mandate:** Cases involving high-value funds ($> \$25,000.00$) or cross-border sanctions screening alerts require two-party authorization (Maker-Checker protocol). An Analyst cannot independently seal or file a SAR dossier without Senior Reviewer sign-off.

> [!NOTE]
> **Operational Manual Structure:** This manual is formatted as an institutional financial engineering and compliance operations guide. Chapters progress sequentially from system initialization to workspace navigation, triage operations, behavioral rule engines, network forensics, model evaluation, and disaster recovery.

---

## Master Table of Contents

- [Chapter 1: System Overview & Architectural Specifications](#chapter-1-system-overview--architectural-specifications)
- [Chapter 2: Quick Start & Environment Initialization](#chapter-2-quick-start--environment-initialization)
- [Chapter 3: Workspace Navigation & User Personas (RBAC)](#chapter-3-workspace-navigation--user-personas-rbac)
- [Chapter 4: Executive Overview & Financial Ledger Telemetry](#chapter-4-executive-overview--financial-ledger-telemetry)
- [Chapter 5: Priority Case Queue & Risk Triage Operations](#chapter-5-priority-case-queue--risk-triage-operations)
- [Chapter 6: Entity Registry — Customer Directory & 360° Profile](#chapter-6-entity-registry--customer-directory--360-profile)
- [Chapter 7: Account Management & Burst Activity Profiling](#chapter-7-account-management--burst-activity-profiling)
- [Chapter 8: Transaction Monitoring & Live Rule Evaluation Engine](#chapter-8-transaction-monitoring--live-rule-evaluation-engine)
- [Chapter 9: Financial Network Intelligence & Money Flow Graph](#chapter-9-financial-network-intelligence--money-flow-graph)
- [Chapter 10: Behavioral Alerts Management & Co-Occurrence Matrix](#chapter-10-behavioral-alerts-management--co-occurrence-matrix)
- [Chapter 11: Case Dossiers, GoAML XML & Cryptographic Evidence Sealing](#chapter-11-case-dossiers-goaml-xml--cryptographic-evidence-sealing)
- [Chapter 12: 9-Check Ledger Validator & Exception Quarantine Queue](#chapter-12-9-check-ledger-validator--exception-quarantine-queue)
- [Chapter 13: Model Evaluation Harness, Lift Curves & Population Stability Index](#chapter-13-model-evaluation-harness-lift-curves--population-stability-index)
- [Chapter 14: Compliance Governance, QA Grading & Regulatory Exam Readiness](#chapter-14-compliance-governance-qa-grading--regulatory-exam-readiness)
- [Chapter 15: Yotta Bot Conversational AI Assistant & Command Palette](#chapter-15-yotta-bot-conversational-ai-assistant--command-palette)
- [Chapter 16: Synthetic Banking Universe & Deterministic Seeding Engine](#chapter-16-synthetic-banking-universe--deterministic-seeding-engine)
- [Chapter 17: Immutable Audit Trail & Cryptographic Chain of Custody](#chapter-17-immutable-audit-trail--cryptographic-chain-of-custody)
- [Chapter 18: System Diagnostics, Troubleshooting & Administration](#chapter-18-system-diagnostics-troubleshooting--administration)

---

## Chapter 1: System Overview & Architectural Specifications

### 1.1 What is RiskOS?
**RiskOS** is an institutional-grade, full-stack Financial Crime & Ledger Risk Intelligence operating system. It was engineered from the ground up to eliminate the twin failures of modern transaction monitoring: **alert fatigue** (where 95% of rule hits are benign noise) and **black-box opacity** (where opaque ML models produce unexplainable scores rejected by banking examiners).

### 1.2 System Architecture & Processing Pipeline

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         ANALYST WORKBENCH & UI                              │
  │  React 18 + TypeScript + Vite 5 + Tailwind CSS 3                           │
  │  Liquid Glassmorphism: Optical Caustics, Specular Rims, Responsive Canvas   │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │ JSON over HTTP/1.1 (Sub-15ms Latency)
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                      RISK ENGINE & API CONTROLLER                           │
  │  Python 3.10+ Standard Library Only (Zero Pip Wheels, Zero Dependency Drift)│
  │  Multi-Threaded REST API Server, BFS Entity Clustering, 8-Rule Risk Scorer  │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │ Embedded High-Speed Foreign-Key Bus
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                      TRANSACTION LEDGER & STORAGE                           │
  │  SQLite 3.35+ in WAL Mode (Write-Ahead Logging)                             │
  │  Double-Entry Reconciled Ledger ($124,426,844.83 / 100,000 Transactions)    │
  └─────────────────────────────────────────────────────────────────────────────┘
```

| Technical Specification | Engineering Value & Capability |
| :--- | :--- |
| **Ledger Processing Capacity** | 100,000 Reconciled Ledger Transactions; 5,000 Customers; 7,000 Accounts |
| **Memory Footprint (RAM)** | `< 45 MB` Idle RAM; `< 120 MB` under heavy 100k query load |
| **Storage & Database Engine** | SQLite 3 in WAL Mode with sub-millisecond query optimization |
| **Cold Boot Startup Latency** | `< 600 ms` cold boot from CLI to operational web server |
| **UI Design & Visual Styling** | iOS-inspired 3D Liquid Glassmorphism with dual-mode lighting (Light & Dark) |
| **Ledger Invariant & Failsafe Guard** | 9-Check Ledger Validator isolating corrupt records into Quarantine |

---

## Chapter 2: Quick Start & Environment Initialization

### 2.1 System Prerequisites
Verify that your machine has the following runtimes installed:
- Python `>= 3.10` (`python3 --version`)
- Node.js `>= 18` (`node --version`)
- npm `>= 9` (`npm --version`)
- Git (`git --version`)

### 2.2 Initialization in 3 Steps
```bash
# Step 1: Clone the repository
git clone https://github.com/amanreddy-9/YottaFlex-Risk-Intelligence.git
cd YottaFlex-Risk-Intelligence

# Step 2: Run automated environment setup
chmod +x setup.sh
./setup.sh

# Step 3: Launch Unified Server (API + Web Bundle)
make serve
```

The system will initialize on **`http://localhost:8080`**. Open your web browser to access the workbench.

---

## Chapter 3: Workspace Navigation & User Personas (RBAC)

### 3.1 Workspace Navigation & Interface Zones
When you enter the dashboard, the viewport is divided into three primary zones:
1. **Collapsible Glass Navigation Chassis (Left):** Houses direct links to all 10 analytical workspaces, with dynamic notification badges showing open cases and quarantine count.
2. **Global Telemetry Bar (Top):** Displays active operator greeting, current system time, global date-range filters (`7D`, `30D`, `90D`, `ALL`), export shortcuts, theme toggle, and operator authentication pill.
3. **Primary Viewport (Center-Right):** Transradiant, multi-layered workspace rendering the selected analytical module.

### 3.2 Operator Personas & Role-Based Access Control (RBAC)

```
                     ┌──────────────────────────────────────┐
                     │          SYSTEM_ADMIN                │
                     │  (Rule Weights, Retentions, Audits)  │
                     └──────────────────┬───────────────────┘
                                        │
                     ┌──────────────────▼───────────────────┐
                     │         SENIOR_REVIEWER              │
                     │  (Maker-Checker Sign-off, QA, SAR)   │
                     └──────────────────┬───────────────────┘
                                        │
                     ┌──────────────────▼───────────────────┐
                     │          OPS_ANALYST                 │
                     │  (Triage, Search, Graph, Evidence)   │
                     └──────────────────────────────────────┘
```

Three pre-calibrated operator accounts are provided for evaluation:

#### Persona 1: Risk Operations Analyst (`OPS_ANALYST`)
- **Keycard Credentials:** `demo_analyst@yottaflex.ai` / `DemoAnalyst2026!`
- **Primary Duties:** Review high-priority alert queues, investigate customer 360 profiles, trace money movements on the Network Graph, attach evidence notes, and transition cases to `IN_REVIEW`.

#### Persona 2: Senior Compliance Reviewer (`SENIOR_REVIEWER`)
- **Keycard Credentials:** `demo_reviewer@yottaflex.ai` / `DemoAnalyst2026!`
- **Primary Duties:** Perform four-eyes Maker-Checker verification, approve regulatory SAR filings, reopen closed cases when new evidence emerges, and complete blind QA grading scorecards.

#### Persona 3: System Administrator (`SYSTEM_ADMIN`)
- **Keycard Credentials:** `demo_admin@yottaflex.ai` / `DemoAnalyst2026!`
- **Primary Duties:** Recalibrate risk rule weights, evaluate what-if impact proposals, trigger automated SLA escalations, verify cryptographic audit chains, and execute data retention purges.

---

## Chapter 4: Executive Overview & Financial Ledger Telemetry

The **Overview Workspace** acts as the primary executive monitoring console, displaying live ledger vitals:

### 4.1 Ledger KPI Metrics
- **Filtered Ledger Volume:** Total capital moving across the ledger (`$124,426,844.83` across 100,000 transactions).
- **Transaction Risk Breakdown:**
  - `HIGH-RISK`: **92 transactions** ($0.09\%$ of ledger volume, composite score $\ge 60.0$).
  - `MEDIUM-RISK`: **762 transactions** ($0.76\%$ of ledger volume, composite score $20.0 \dots 59.9$).
  - `LOW-RISK`: **99,146 transactions** ($99.15\%$ clean baseline commerce).
- **Queue Load Indicator:** **244 Open Cases** currently awaiting operator disposition.
- **Quarantine Containment:** **10 isolated anomalies** preventing ledger corruption.

### 4.2 Interactive Temporal Trends & Charts
- **Transaction Volume & Anomaly Over-Time Area Chart:** Displays daily USD throughput (blue shaded curve) overlaid with high-risk anomaly spikes (rose peak line). Hovering reveals exact daily dollar volume and triggered rule counts.
- **Top Merchant Counterparties:** Bar chart illustrating merchant volume, high-risk merchant categories (crypto exchanges, shell entities, foreign gaming), and high-risk flags.

### 4.3 Data Export Operations
- **Export CSV:** Downloads a streaming CSV file of all ledger metrics.
- **Export JSON:** Downloads complete machine-readable ledger state for SIEM integration.

---

## Chapter 5: Priority Case Queue & Risk Triage Operations

The **Case Queue Workspace** is the core operational engine where analysts triage suspicious activity.

### 5.1 Case Clustering Mathematics (3.25x Workload Compression)
Rather than forcing analysts to inspect 923 disconnected alerts, RiskOS executes **Bipartite BFS Connected-Component Clustering**:
- All alerts sharing an Account, Counterparty Transfer Link, or Hardware Device ID are consolidated into a single **Case Dossier**.
- **Result:** 923 fragmented alerts compress into **284 holistic multi-alert cases**, saving an estimated $69\%$ in analyst triage hours.

### 5.2 Case Prioritization Scoring Formula
Each case is scored from $0.0$ to $100.0$ using a deterministic, explainable weighting formula:

$$\text{PriorityScore} = \min\left(100, \max_{a \in \text{Alerts}}(a.\text{score}) + \ln(|\text{Alerts}|) \cdot 5.0 + \sum_{d \in \text{Devices}} \text{DeviceRisk}(d)\right)$$

### 5.3 Operating the Queue
1. **Sort Modes:** Click the sort dropdown to order cases by `Priority Score (High → Low)`, `Creation Date`, `Alert Count`, or `Total Amount at Risk`.
2. **Status Filtering:** Filter cases by `OPEN`, `IN_REVIEW`, `CLOSED`, or `ESCALATED`.
3. **Inline Triage Actions:**
   - **Assign to Me:** Locks case ownership to the current operator.
   - **Attach Note:** Appends markdown-formatted investigation notes to the audit trail.
   - **Escalate to SAR:** Elevates case to Senior Reviewer for FinCEN GoAML filing.
   - **Close as False Positive:** Closes case with mandatory disposition rationale.

---

## Chapter 6: Entity Registry — Customer Directory & 360° Profile

### 6.1 Customer Search & Filter Controls
The Customer Directory lists all 5,000 onboarded banking customers:
- **Search Bar:** Real-time lookup by Customer ID (`CUS-000001`), Full Name, or Home Country.
- **KYC Tier Filter:** Isolate customers by `STANDARD`, `ENHANCED`, or `HIGH_NET_WORTH`.
- **Sanctions Match Flag:** Highlights customers with fuzzy name matches against OFAC/PEP lists.

### 6.2 Customer 360° Inspection Drawer
Clicking any customer opens a comprehensive slide-over drawer:
- **KYC & Demographic Verification:** Employment, declared monthly income, risk rating, and onboarding timestamp.
- **Linked Banking Accounts:** Displays all active accounts, ledger balances, and currency types.
- **Hardware Device History:** Lists all mobile and web devices used to access the account, flagging emulator footprints or shared device fingerprints.
- **Geographic Corridor Exposure:** Calculates the percentage of funds routed to high-risk offshore jurisdictions.
- **Chronological Activity Timeline:** A temporal ledger detailing every login, device link, and transaction in chronological sequence.

---

## Chapter 7: Account Management & Burst Activity Profiling

### 7.1 Account Registry
The Account Directory catalogs all 7,000 checking, savings, and business accounts:
- **Account Identification:** Structured account numbers (`ACC-CUS-000001-01`).
- **Balance Monitoring:** Current balance, allowed overdraft limits, and account status (`ACTIVE`, `DORMANT`, `FROZEN`, `CLOSED`).

### 7.2 Burst Profiling & Velocity Diagnostics
For any selected account, the system computes **Burst Activity Metrics**:
- **Sliding Velocity Window:** Measures transactions executed within any 60-minute interval. Accounts executing $\ge 5$ debits within 1 hour trigger `RULE-001`.
- **Dormancy Reactivation:** Detects accounts inactive for $\ge 90$ days that suddenly execute transfers $\ge \$3,000.00$ within 48 hours of waking (`RULE-004`).
- **Transfer Link Matrix:** Outlines all inbound and outbound counterparty account linkages with net dollar volumes.

---

## Chapter 8: Transaction Monitoring & Live Rule Evaluation Engine

### 8.1 The 8 Behavioral Risk Rules
The transaction engine evaluates every ledger entry against 8 deterministic, observable rules:

| Rule ID | Rule Name | Mathematical Trigger Condition | Default Weight |
| :--- | :--- | :--- | :--- |
| **RULE-001** | Rapid Velocity Debit Spike | $\ge 5$ debit transactions within a sliding 60-minute window. | 20 pts |
| **RULE-002** | New Device High-Value Outflow | Outbound transfer $\ge \$1,500.00$ within 24h of first device registration. | 22 pts |
| **RULE-003** | Circular Transfer Loop | Multi-hop transfer ring ($A \to B \dots \to A$) returning $\ge 75\%$ funds within 48h. | 25 pts |
| **RULE-004** | Dormant Account Sudden Reactivation | Prior dormant state ($\ge 90$ days) followed by transaction $\ge \$3,000.00$ within 48h. | 25 pts |
| **RULE-005** | High-Risk Cross-Border Merchant | Merchant purchase $\ge \$1,000.00$ in high-risk jurisdiction or foreign country. | 18 pts |
| **RULE-006** | Smurfing / Split Structuring | Outbound transfers between $\$1,800.00$ and $\$2,999.99$ within 24h (just below reporting threshold). | 20 pts |
| **RULE-007** | Shared Multi-Customer Device | Single hardware device or emulator associated with $\ge 3$ unrelated customer IDs. | 22 pts |
| **RULE-008** | Declared Income Deviation | Single transaction $\ge 50\%$ of customer's declared monthly income on Standard KYC. | 16 pts |

### 8.2 Live Transaction Simulator
The workbench allows operators to simulate and test transactions in real time:
- **Option A (Custom Transaction Simulation):** Input Source Account, Amount, Channel (`WIRE_OUT`, `ACH`, `POS`), Destination Country, and Device ID. Click **Evaluate Rules & Compute Scores** to see exact rule hits and the resulting composite risk score without mutating the database.
- **Option B (Evaluate Stored Transaction by ID):** Enter an existing transaction ID (e.g., `TXN-2026-00009996`) to inspect historic rule triggers and score breakdown.

---

## Chapter 9: Financial Network Intelligence & Money Flow Graph

The **Network Intelligence Workspace** provides interactive graph-based visual forensic exploration:

```
    [Customer Node] ──(Ownership)──> [Account Node] ──(Origin)──> [Transaction Node]
           │                                                              │
      (Registered)                                                   (Destination)
           ▼                                                              ▼
     [Device Node]                                                 [Counterparty Account]
```

### 9.1 Visual Language & Node Signifiers
- **Customer Nodes (Blue):** Represent individuals or corporate entities.
- **Account Nodes (Cyan):** Represent bank accounts holding balances.
- **Merchant Nodes (Purple):** Commercial counterparties and point-of-sale terminals.
- **Device Nodes (Orange):** Mobile phones, laptops, and emulators.
- **Transaction Nodes (Light Blue):** Specific ledger transfer events.
- **Risk Indicator Rings:** Red glowing halos signify `HIGH` risk entities; amber signifies `MEDIUM` risk.

### 9.2 Graph Interactivity & Navigation Controls
- **Zoom & Pan:** Scroll to zoom in/out; click and drag empty space to pan across the canvas.
- **Physics Layout:** Nodes dynamically repel each other while edges act as springs, untangling complex clusters automatically.
- **Entity Selection:** Click any node to highlight its direct 1st- and 2nd-degree connections while applying a subtle transradiant dimming mask across unrelated entities.
- **Inspection Drawer:** Clicking a node automatically populates the right-hand panel with node metadata, incoming/outgoing volume, and direct action triggers.
- **Network Expansion:** Click **Expand (+1 Hop)** to fetch and render connected entities dynamically.
- **Focus & Isolate:** Isolates the active subnetwork, hiding background clutter.
- **Reset View:** Re-centers and fits the entire graph into the viewport.

---

## Chapter 10: Behavioral Alerts Management & Co-Occurrence Matrix

### 10.1 Alerts Management
The Alerts Workspace lists all 923 individual behavioral alerts:
- **Filtering by Rule:** Isolate alerts triggered by specific typologies (e.g. `RULE-003` Circular Loops).
- **Alert Dispositioning:** Assign alert status (`TRIAGED`, `INVESTIGATING`, `DISMISSED`).
- **Alert Fatigue Diagnostic:** Tracks the ratio of investigated alerts to total generated alerts, highlighting over-sensitive rules that require calibration.

### 10.2 Rule Co-Occurrence Matrix
Visual heat map displaying how frequently rules trigger simultaneously on the same transaction or account. For example, `RULE-002` (New Device) and `RULE-006` (Structuring) frequently co-occur during credential stuffing and account takeover attacks.

---

## Chapter 11: Case Dossiers, GoAML XML & Cryptographic Evidence Sealing

### 11.1 The Investigation Dossier
Every case consolidates complete forensic evidence into a unified dossier:
- **Executive Summary:** Overview of flagged entities, aggregate amount at risk, and rule hits.
- **Audit Chronology:** Immutable timeline of all operator actions, notes, and state changes.
- **Counterparty Breakdown:** List of all external recipients and sending accounts.

### 11.2 Regulatory GoAML XML Generation
With one click, operators can generate compliant **GoAML XML** (v4.0.2 Schema) for direct filing with financial intelligence units (FinCEN, FIU):
- Conforms to standard SAR/STR data structures.
- Embeds reporting entity details, transaction amounts, foreign exchange rates, counterparty account identifiers, and narrative descriptions.

### 11.3 Cryptographic SHA-256 Evidence Sealing
To ensure chain-of-custody admissibility in criminal court:
- Clicking **Seal Evidence** computes a canonical SHA-256 digital fingerprint over the entire case dossier, including all linked transaction records, operator notes, and timestamps.
- The seal is stored in `evidence_seals.json` and permanently displayed on the case header. Any subsequent tampering with the database will break the cryptographic hash, alerting compliance auditors.

---

## Chapter 12: 9-Check Ledger Validator & Exception Quarantine Queue

### 12.1 The 9-Check Ledger Integrity Engine
Before financial data enters the analytical stream, the **9-Check Validator** scans for fundamental corruption:
1. `CLOSED_ACCOUNT_TXN`: Transactions attempted against closed accounts.
2. `NEGATIVE_BALANCE_NO_OD`: Balances dropping below $\$0.00$ without overdraft protection.
3. `MISMATCHED_TRANSFER_AMOUNTS`: Discrepancy between debit and credit transfer legs.
4. `ORPHAN_OR_MISSING_TXN_REF`: Transfer links referencing nonexistent transaction IDs.
5. `FUTURE_TIMESTAMP_ANOMALY`: Transactions with timestamps exceeding current wall-clock time.
6. `DUPLICATE_TXN_FINGERPRINT`: Redundant transaction hashes within 1 second.
7. `INVALID_CURRENCY_CODE`: ISO 4217 currency mismatches.
8. `UNBALANCED_JOURNAL_ENTRY`: Double-entry accounting violations.
9. `CORRUPT_METADATA_PAYLOAD`: Malformed JSON or unparseable fields.

### 12.2 Quarantine Operations
- When a check fails, the record is immediately diverted into the **Quarantine Queue**.
- Quarantined records are isolated from active alert generation, ensuring dirty data never distorts machine learning scores or analyst workflows.
- Operators can inspect the exact rejection reason, review raw payloads, and execute corrective repairs or purge actions.

---

## Chapter 13: Model Evaluation Harness, Lift Curves & Population Stability Index

### 13.1 Benchmarking Metrics & Lift Curves
The Evaluation Workspace measures the objective performance of the prioritization engine:
- **Top-50 Precision:** Measures the fraction of true criminal cases in the top 50 ranked items (**`100.0%`** vs. `50.0%` FIFO baseline — $2.0\times$ Lift).
- **Recall@20%:** Fraction of total syndicate crime discovered within the first 20% of queue capacity (**`34.1%`** vs. `16.2%` FIFO).
- **NDCG@50 (Normalized Discounted Cumulative Gain):** **`1.0000`** vs. `0.6305` FIFO baseline.
- **10-Decile Lift Curve:** Shows how crime concentration drops exponentially across deciles, proving that analysts do not need to sift through bottom deciles.

### 13.2 Population Stability Index (PSI) & Drift Monitoring
Monitors data distribution drift across quarters to detect model degradation:
- $\text{PSI} < 0.1$: No significant drift; engine calibration is stable.
- $0.1 \le \text{PSI} < 0.25$: Moderate drift; warning flag raised for rule tuning.
- $\text{PSI} \ge 0.25$: Significant population drift; mandates re-weighting.

---

## Chapter 14: Compliance Governance, QA Grading & Regulatory Exam Readiness

### 14.1 Four-Eyes Maker-Checker Controls
For critical case actions (e.g. SAR filing, account freezing):
- **Maker:** The investigating analyst prepares the dossier and initiates the handoff.
- **Checker:** A senior reviewer independently examines the evidence and either approves or rejects the action with feedback.

### 14.2 Blind QA Sampling & Grading
Quality Assurance managers can pull random or stratified samples of closed cases:
- Evaluates investigation thoroughness across a standardized 100-point rubric.
- Records grading notes and maintains an auditor-accessible QA history.

### 14.3 Regulatory Exam Readiness Checklist
Automated self-audit scoring module that validates whether the institution meets regulatory examination standards (audit trail integrity, model governance documentation, data retention compliance).

---

## Chapter 15: Yotta Bot Conversational AI Assistant & Command Palette

### 15.1 Yotta Bot Conversational AI Assistant
Floating in the bottom-right corner of every screen is **Yotta Bot**, an embedded conversational AI assistant:
- **Natural Language Entity Lookup:** Type `"Explain why ACC-CUS-000001-01 was flagged"` or `"Summarize CASE-2026-000017"`.
- **Typology Guidance:** Ask `"What is smurfing structuring?"` or `"Explain Rule 003"`.
- **SQL-Safe Architecture:** Operates over sandboxed, parameterized read-only queries with strict access control.

### 15.2 Command Palette & Keyboard Shortcuts
Press **`Cmd + K`** (macOS) or **`Ctrl + K`** (Windows/Linux) from anywhere in the application to open the global Command Palette:
- Instant fuzzy navigation to any customer, account, or case ID.
- Quick shortcuts:
  - `g o`: Go to Overview
  - `g q`: Go to Queue
  - `g n`: Go to Network Flow Graph
  - `g a`: Go to Alerts
  - `t t`: Toggle Dark / Light Theme

---

## Chapter 16: Synthetic Banking Universe & Deterministic Seeding Engine

### 16.1 Deterministic Seed `20261022`
The entire banking universe is generated from a single integer seed (`20261022`):
- Guarantees 100% bit-for-bit identical outputs across any operating system (macOS, Linux, Windows).
- SHA-256 hashes of generated CSVs and SQL tables match exactly across independent test runs.

### 16.2 Realistic Behavioral Distributions
- **Customer Incomes:** Modeled using heavy-tailed Zipfian/Pareto distributions matching real-world OECD demographics.
- **Transaction Channels:** Realistic transaction mix (45% POS purchases, 30% ACH transfers, 15% Wire Transfers, 10% ATM cash movements).
- **Planted Criminal Typologies:** Injected smurfing rings, circular round-tripping networks, and shared emulator device syndicates.

---

## Chapter 17: Immutable Audit Trail & Cryptographic Chain of Custody

### 17.1 Tamper-Evident SHA-256 Audit Chain
Every database mutation (case status update, note attachment, rule re-weighting) is written to an append-only audit ledger:
- Each log entry stores `timestamp`, `operator_id`, `action_type`, `entity_id`, and `previous_hash`.
- The `previous_hash` chains each entry to the preceding one, creating a cryptographic Merkle-style audit log.
- System administrators can click **Verify Audit Chain** to mathematically prove that no historical records have been modified or deleted.

---

## Chapter 18: System Diagnostics, Troubleshooting & Administration

### 18.1 System Diagnostic Matrix

| Symptom / Diagnostic Code | Root Cause | Resolution / Remedy |
| :--- | :--- | :--- |
| **Port 8080 Busy (`Errno 48`)** | Another process is holding port 8080. | Launch server with `--port 8090` or terminate the occupying process with `lsof -ti :8080 \| xargs kill -9`. |
| **Database Locked Error** | Abnormal shutdown left stale SQLite WAL lock. | Run `rm -f yottaflex.db-wal yottaflex.db-shm` and restart the server. |
| **Theme Toggle Not Sliding** | Browser cached old JavaScript bundle. | Hard-refresh with `Cmd + Shift + R` (macOS) or `Ctrl + F5` (Windows). |
| **Graph Right Drawer Not Pinned** | Drag tolerance exceeded. | Click firmly on the node center ($< 4\text{px}$ movement) to pin selection. |
| **Node.js Build Failure** | Node version $< 18$. | Update Node.js via `nvm install 20 && nvm use 20`. |

### 18.2 System Administration CLI Reference
```bash
# Re-generate synthetic banking universe
python3 -m yottaflex.cli generate --seed 20261022 --scale full

# Run 9-check ledger validator
python3 -m yottaflex.cli validate --strict

# Run model evaluation benchmark
python3 -m yottaflex.cli eval --top-k 50

# Run complete automated test suite
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

---

*End of RiskOS System & Operational Reference Manual — Enterprise Edition v1.0.0.*
