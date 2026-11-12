# YottaFlex Risk Intelligence — Reviewer Setup Guide & Operational Manual

> **Document Type:** Institutional Setup & Operational Manual  
> **Target Audience:** Reviewers, Compliance Engineers, Risk Examiners, and Evaluators  
> **System Name:** YottaFlex Risk Intelligence — YottaFlex RiskOS  
> **Repository:** `https://github.com/amanreddy-9/YottaFlex-Risk-Intelligence`  
> **Primary Author:** Aman Reddy J (`amanreddy-9`, `amanreddyjukonti@gmail.com`)  
> **Evaluation Reference Seed:** `20261022`

---

## 1. Executive Summary & Fast Track

**YottaFlex RiskOS** is an institutional financial network intelligence, transaction monitoring, and AML risk triage workbench. It pairs a **100% Python standard library backend** (zero third-party wheel bloat, zero dependency drift) with an **iOS-inspired Liquid Glassmorphic React 18 + TypeScript frontend**, backed by an embedded SQLite analytical engine.

### The 60-Second Reviewer Fast Track

If your system already has **Python 3.10+** and **Node.js 18+** installed:

```bash
# 1. Clone repository
git clone https://github.com/amanreddy-9/YottaFlex-Risk-Intelligence.git
cd YottaFlex-Risk-Intelligence

# 2. Run automated setup script
chmod +x setup.sh
./setup.sh

# 3. Launch unified server (Serves both REST APIs and Liquid Glass UI)
make serve
# Or: PYTHONPATH=src python3 -m yottaflex.cli serve --scale full --port 8080
```

Now open **`http://localhost:8080`** in Google Chrome, Safari, or Microsoft Edge.

---

## 2. System Prerequisites & Hardware Specifications

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Operating System** | macOS 12+ (Apple Silicon or Intel), Ubuntu 20.04+, Debian 11+, Fedora 36+, Windows 10/11 (WSL2) | macOS Sonoma 14+ / Ubuntu 22.04 LTS |
| **Python Runtime** | Python 3.10.x | Python 3.11.x or Python 3.12.x |
| **Node.js Runtime** | Node.js 18.x LTS | Node.js 20.x LTS or 22.x LTS |
| **Package Manager** | npm 9.x+ | npm 10.x+ |
| **Memory (RAM)** | 4 GB | 8 GB or 16 GB |
| **Disk Space** | 500 MB (includes 100k synthetic dataset & node_modules) | 1 GB SSD |
| **Network** | None required during runtime (100% air-gapped capable) | Internet required only for initial `npm install` |

---

## 3. OS-Specific Prerequisites Installation

Install Python, Node.js, and build essentials in a single command for your platform:

### macOS (Homebrew)
```bash
brew update
brew install python@3.11 node git sqlite3 make
```

### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nodejs npm git sqlite3 make curl
```

### Fedora / RHEL / CentOS Stream
```bash
sudo dnf install -y python3 python3-devel nodejs npm git sqlite make curl
```

### Windows 11 / 10 via WSL2
Open PowerShell as Administrator, launch WSL (`wsl`), and run:
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nodejs npm git sqlite3 make curl
```

---

## 4. Manual Step-by-Step Setup Guide

For reviewers who prefer complete manual control over each environment step:

### Step 4.1: Clone the Repository
```bash
git clone https://github.com/amanreddy-9/YottaFlex-Risk-Intelligence.git
cd YottaFlex-Risk-Intelligence
```

### Step 4.2: Python Virtual Environment Initialization
```bash
# Create isolated virtual environment
python3 -m venv .venv

# Activate virtual environment
# macOS / Linux / WSL:
source .venv/bin/activate
# Windows PowerShell (native):
# .venv\Scripts\Activate.ps1
```

> [!NOTE]
> **Zero External Python Dependencies:** The Python backend is engineered to run exclusively on the **Python Standard Library** (`sqlite3`, `http.server`, `hashlib`, `json`, `csv`, `math`, `typing`, `dataclasses`, `datetime`). You do **not** need to install heavy wheels like Pandas, NumPy, or Torch. This eliminates compilation errors, C-extension mismatches, and CVE supply-chain risks.

### Step 4.3: Build the Frontend Production Bundle
```bash
cd web
npm install
npm run build
cd ..
```
*The compiled assets will be written to `web/dist/`, which the Python server serves directly.*

### Step 4.4: Synthetic Banking Dataset Initialization
The application ships with deterministic synthetic seed data (`seed: 20261022`). You can bootstrap SQLite from the pre-bundled SQL seed or re-generate from scratch:

**Option A: Instant SQL Bootstrap (< 1 second):**
```bash
sqlite3 yottaflex.db < data/sql/seed.sql
```

**Option B: Deterministic Full-Scale Generation:**
```bash
PYTHONPATH=src python3 -m yottaflex.cli generate --seed 20261022 --scale full
```
This generates:
- 5,000 Verified KYC Customers
- 7,000 Linked Checking & Business Accounts
- 100,000 Reconciled Double-Entry Ledger Transactions ($124.4M volume)
- 4,640 Inter-Account Transfer Links
- 923 Behavioral AML Alerts across 8 rules
- 284 Consolidated Investigation Cases (3.25x triage compression)

---

## 5. Starting the Application

### Mode A: Production Unified Server (Recommended)
This runs the Python multi-threaded REST API server and simultaneously serves the Liquid Glass frontend bundle from `web/dist/` on port 8080:

```bash
source .venv/bin/activate
PYTHONPATH=src python3 -m yottaflex.cli serve --scale full --port 8080
```
*Or using the Makefile shortcut:*
```bash
make serve
```

Access the UI at: **`http://localhost:8080`**

### Mode B: Decoupled Development Mode
For reviewers who wish to inspect hot-reloading frontend code:

**Terminal 1 (Backend API Server on port 8080):**
```bash
source .venv/bin/activate
PYTHONPATH=src python3 -m yottaflex.cli serve --scale full --port 8080
```

**Terminal 2 (Vite Hot-Reload Server on port 5173):**
```bash
cd web
npm run dev
```
Access the Vite dev server at: **`http://localhost:5173`** (Vite automatically proxies `/api/*` to `http://localhost:8080`).

---

## 6. Pre-Configured Reviewer Credentials

The platform enforces strict **Role-Based Access Control (RBAC)**. Test accounts for all three organizational personas are provisioned out-of-the-box:

| Role | Username / Email | Password | Allowed Capabilities |
| :--- | :--- | :--- | :--- |
| **Risk Analyst** | `demo_analyst@yottaflex.ai` | `DemoAnalyst2026!` | Case triage, alert dispositioning, entity search, network graph exploration, GoAML XML export, Yotta Bot queries. |
| **Senior Reviewer** | `demo_reviewer@yottaflex.ai` | `DemoAnalyst2026!` | All Analyst permissions + 4-eyes Maker-Checker sign-off, reopening closed cases, QA grading, regulatory dossier approval. |
| **System Administrator** | `demo_admin@yottaflex.ai` | `DemoAnalyst2026!` | All Reviewer permissions + Risk Rule weight reconfiguration, threshold calibration proposals, audit chain verification, data retention execution. |

*You can also click the quick-login pills on the authentication drawer to switch roles with a single click.*

---

## 7. Verification Checklist & Health Checks

Confirm that all system components are operational using `curl` or your browser:

### 1. System Health & Overview KPI
```bash
curl -s http://localhost:8080/api/overview | python3 -m json.tool | head -n 25
```
*Expected Output:* JSON response containing `total_transactions: 100000`, `high_risk_txns: 92`, `open_cases: 244`, and ledger balance reconciliations.

### 2. Quarantine Queue Health (9-Check Validator)
```bash
curl -s http://localhost:8080/api/quarantine | python3 -m json.tool | head -n 20
```
*Expected Output:* 10 quarantined exceptions across 5 failure categories (closed accounts, overdraft violations, mismatched transfers).

### 3. Financial Network Intelligence Endpoint
```bash
curl -s "http://localhost:8080/api/network/entity-graph?entity_id=ACC-CUS-000001-01&depth=2" | python3 -m json.tool | head -n 30
```
*Expected Output:* Graph JSON structure with nodes (Customer, Account, Device, Transaction) and directed money flow edges.

### 4. Running the Complete Automated Test Harness
Execute all 46 unit, system, and regression tests:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
*Expected Result:* **`Ran 46 tests in ~10.5s — OK`** (100% passing).

---

## 8. Directory & File Structure Map

```text
YottaFlex-Risk-Intelligence/
├── Makefile                       # Developer shortcuts (make setup, make serve, make test)
├── setup.sh                       # 1-click automated setup script for reviewers
├── SETUP_GUIDE.md                 # This comprehensive setup manual
├── DEPENDENCIES.md                # Exhaustive software & library inventory
├── TESTING_AND_VALIDATION_REPORT.md # Verification metrics, AST guards & test suite results
├── UI_UX_DESIGN_SPECIFICATION.md  # Liquid glassmorphism design system & prompting methodology
├── USER_MANUAL.md                 # Complete 18-chapter operational & system reference manual
├── ARCHITECTURE_AND_PROVENANCE.md # Architectural decisions, tradeoffs & technical rationale
├── docs/
│   ├── AI_DEVELOPMENT_AND_PROMPT_HISTORY.md # AI acceleration narrative & full prompt history
│   ├── ARCHITECTURE_AND_REASONING.md        # Initial design reasoning & assumptions
│   └── data_dictionary.md                   # Column-by-column schema documentation
├── data/
│   ├── synthetic/                 # Raw CSV/JSON generated tables (customers, txns, etc.)
│   └── sql/seed.sql               # Full deterministic SQLite bootstrap seed
├── schema/
│   └── sqlite_schema.sql          # DDL table definitions and indexes
├── src/yottaflex/                 # Python Backend (100% Standard Library)
│   ├── cli.py                     # CLI entrypoint (generate, serve, validate, eval)
│   ├── server.py                  # Multi-threaded HTTP REST API & static asset server
│   ├── db.py                      # SQLite database connector & foreign key pragma
│   ├── core/                      # Data models, seed config, and constants
│   ├── engine/                    # Behavioral rule engine & case clustering (BFS)
│   ├── services/                  # Business logic (network intelligence, triage, GoAML)
│   ├── assistant/                 # Yotta Bot conversational risk engine
│   └── validation/                # 9-check ledger validator & evaluation harness
├── tests/                         # Comprehensive 46-test automated test harness
└── web/                           # Frontend (React 18 + TypeScript + Vite + Tailwind)
    ├── package.json               # Frontend package manifest
    ├── vite.config.ts             # Vite configuration with API reverse proxy
    ├── tailwind.config.js         # Custom liquid glass styling tokens
    ├── src/
    │   ├── App.tsx                # Main application coordinator & route manager
    │   ├── components/            # Reusable UI widgets (LiquidGlass, NetworkGraph, etc.)
    │   └── views/                 # 10 dedicated analytical workspaces
    └── dist/                      # Production-compiled static assets
```

---

## 9. Troubleshooting & FAQ

### Issue: Port 8080 is already in use
**Symptom:** `OSError: [Errno 48] Address already in use`  
**Solution:** Specify an alternative port using the `--port` flag:
```bash
PYTHONPATH=src python3 -m yottaflex.cli serve --scale full --port 8090
```
Then visit `http://localhost:8090`.

### Issue: Node.js version is too old (< 18.x)
**Symptom:** `SyntaxError: Unexpected token '?'` or Vite build failure.  
**Solution:** Upgrade Node.js via [nvm](https://github.com/nvm-sh/nvm) or Homebrew:
```bash
nvm install 20
nvm use 20
```

### Issue: SQLite database is locked
**Symptom:** `sqlite3.OperationalError: database is locked`  
**Solution:** The system configures SQLite in `WAL` (Write-Ahead Logging) mode automatically. If a stale lock occurs after an abnormal termination:
```bash
rm -f yottaflex.db-wal yottaflex.db-shm
```

### Issue: Changes to frontend code are not reflecting
**Symptom:** Browser shows older assets when running `make serve`.  
**Solution:** Rebuild the static bundle with `cd web && npm run build && cd ..`, or hard-refresh the browser (`Cmd + Shift + R` or `Ctrl + F5`) to bypass browser caching.
