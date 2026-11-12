# YottaFlex Risk Intelligence — Comprehensive Software & Dependencies Manifest

> **System:** YottaFlex Risk Intelligence — YottaFlex RiskOS  
> **Repository:** `https://github.com/amanreddy-9/YottaFlex-Risk-Intelligence`  
> **Author:** Aman Reddy J (`amanreddy-9`, `amanreddyjukonti@gmail.com`)  
> **Classification:** Production-Grade Risk Engineering Documentation  

---

## 1. Architectural Philosophy: The Zero-Bloat Invariant

A central engineering principle of **YottaFlex RiskOS** is **radical dependency minimalism**. In mission-critical financial crime compliance and regulatory reporting environments (e.g., FinCEN, FCA, BaFin), external dependency bloat introduces severe liabilities:
1. **Supply-Chain Attack Surface:** Every third-party library is an unvetted entry point for malicious code.
2. **Dependency Drift & Version Rot:** Python packages like Pandas, SciPy, or PyTorch frequently break across minor version updates or Python runtime bumps.
3. **Air-Gapped Deployment Friction:** Banking server enclaves often lack public PyPI or npm access; installing dozens of C-extension wheels requires complex offline mirror configurations.

To eliminate these vulnerabilities, **YottaFlex RiskOS achieves a 100% Python Standard Library backend** (0 external wheel dependencies) coupled with a **lean, strictly audited React 18 TypeScript frontend bundle**.

---

## 2. All-in-One Installation Commands

Install all required system runtimes and build tools in a single command for your operating system:

### macOS (Apple Silicon / Intel via Homebrew)
```bash
brew update && brew install python@3.11 node git sqlite3 make curl
```

### Ubuntu / Debian (APT)
```bash
sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip nodejs npm git sqlite3 make curl
```

### Fedora / RHEL / CentOS Stream (DNF)
```bash
sudo dnf update -y && sudo dnf install -y python3 python3-devel nodejs npm git sqlite make curl
```

### Arch Linux (Pacman)
```bash
sudo pacman -Syu --noconfirm python nodejs npm git sqlite make curl
```

### Windows 10/11 WSL2 (Ubuntu Environment)
```bash
sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip nodejs npm git sqlite3 make curl
```

### Single-Command Frontend Dependency Installation & Build
```bash
cd web && npm ci && npm run build && cd ..
```

---

## 3. Backend Runtime & Python Module Inventory

The backend runs entirely on **Python 3.10+ Standard Library**. Below is the exhaustive inventory of all internal modules utilized across the engine, server, validation harness, and CLI:

| Standard Library Module | File / Component Usage | Operational Purpose |
| :--- | :--- | :--- |
| `sqlite3` | `db.py`, `server.py`, `services/*.py` | Embedded transactional and analytical OLTP/OLAP database engine with WAL mode and foreign key enforcement. |
| `http.server` | `server.py` | Multi-threaded HTTP/1.1 REST API server and static asset file provider. |
| `hashlib` | `engine/*.py`, `services/evidence.py` | SHA-256 cryptographic hashing for evidence seals, tamper-evident audit logs, and seed determinism. |
| `json` | `server.py`, `assistant/*.py`, `cli.py` | High-speed serialization and deserialization of API payloads, dossiers, and configuration files. |
| `csv` | `core/generator.py`, `cli.py` | High-throughput streaming export of synthetic customers, accounts, and 100,000 ledger transactions. |
| `math` | `engine/scoring.py`, `validation/eval.py` | Exponential decay calculation, standard deviations, log-odds scoring, and Population Stability Index (PSI). |
| `datetime` / `time` | `core/generator.py`, `services/triage.py` | ISO 8601 timestamp generation, sliding 24h/48h velocity window calculations, and SLA breach timers. |
| `random` | `core/generator.py` | Seed-pinned pseudo-random number generator (`seed: 20261022`) guaranteeing 100% bit-for-bit reproducibility. |
| `typing` / `dataclasses` | `core/models.py`, `services/*.py` | Strongly typed domain entities (`Customer`, `Account`, `Transaction`, `Alert`, `Case`, `NetworkNode`). |
| `urllib.parse` | `server.py` | Robust parsing of query parameters, URL encodings, pagination limits, and search filter strings. |
| `ast` | `tests/test_zero_leakage_ast_guard.py` | Abstract Syntax Tree static analysis ensuring zero ground-truth label leakage into scoring logic. |
| `unittest` | `tests/*.py` | Automated test runner executing 46 end-to-end unit, integration, and scenario test suites. |
| `re` | `assistant/engine.py`, `services/*.py` | Regular expression pattern matching for identifier resolution (`TXN-*`, `CUS-*`, `ACC-*`) and fuzzy search. |
| `os` / `sys` / `pathlib` | `cli.py`, `server.py` | Cross-platform filesystem navigation, directory creation, and environment variable resolution. |

### Optional Backend Extensions (Defined in `pyproject.toml`)
- `fastapi` (`>= 0.115`): Optional ASGI wrapper for enterprise deployments requiring OpenAPI Swagger docs.
- `uvicorn` (`>= 0.30`): Optional high-concurrency ASGI server.
- `pytest` (`>= 8.0`): Optional alternative test runner (system fully supports native `unittest`).

---

## 4. Frontend Runtime & npm Package Manifest

The frontend is a single-page application built with **React 18**, **TypeScript**, and **Tailwind CSS**, bundled into optimized static assets via **Vite 5**.

### Production Dependencies (`web/package.json`)

| Package Name | Exact Version | Purpose & Technical Function |
| :--- | :--- | :--- |
| **`react`** | `^18.3.1` | Core declarative UI library. Manages component lifecycles, virtual DOM reconciliation, and state. |
| **`react-dom`** | `^18.3.1` | DOM renderer for React. Handles browser mounting, portal rendering, and event dispatching. |
| **`lucide-react`** | `^0.454.0` | Comprehensive, ultra-clean SVG icon suite. Renders over 100 custom risk, graph, banking, and UI icons with zero runtime overhead. |

### Development & Build Tooling (`web/devDependencies`)

| Package Name | Exact Version | Purpose & Technical Function |
| :--- | :--- | :--- |
| **`typescript`** | `^5.6.3` | Static type checker. Enforces strict compile-time types across all 10 views, API clients, and network graph components. |
| **`vite`** | `^5.4.10` | Next-generation frontend build tool. Provides Rollup-based production minification, asset hashing, and instant Hot Module Replacement (HMR). |
| **`@vitejs/plugin-react`**| `^4.3.3` | Official Vite plugin for React. Enables Fast Refresh and optimized JSX transformation. |
| **`tailwindcss`** | `^3.4.14` | Utility-first CSS framework. Configured with custom design tokens for Liquid Glassmorphism, backdrop blurs, and specular reflections. |
| **`postcss`** | `^8.4.47` | CSS transformation engine used by Tailwind CSS. |
| **`autoprefixer`** | `^10.4.20` | Automatically appends vendor prefixes (WebKit, Moz) for cross-browser liquid glass filter support. |
| **`@types/react`** | `^18.3.12` | TypeScript type declarations for React core. |
| **`@types/react-dom`** | `^18.3.1` | TypeScript type declarations for React DOM. |

---

## 5. System Utilities & CLI Tooling

The application relies on standard Unix tools found natively on macOS and Linux systems:

| Utility | Recommended Version | Operational Role in YottaFlex |
| :--- | :--- | :--- |
| **`sqlite3` CLI** | `>= 3.35.0` | Direct command-line SQL queries, inspecting tables, executing `data/sql/seed.sql`, and running WAL checkpoints. |
| **`make`** | GNU Make `>= 3.81` | Automation runner executing targets in `Makefile` (`make setup`, `make serve`, `make test`, `make build`). |
| **`git`** | `>= 2.30.0` | Source control management and version tracking. |
| **`curl`** | `>= 7.68.0` | Command-line HTTP utility for API health checks and integration testing. |
| **`bash`** | `>= 4.0` | Shell environment executing `setup.sh` and build automation. |

---

## 6. Dependency Footprint & Security Auditing

### Zero Known Vulnerabilities (0 CVEs)
- **Backend:** Because the backend has **0 external pip packages**, it has **0 external CVE vulnerabilities** from third-party Python code.
- **Frontend:** Audited via `npm audit`:
  ```bash
  cd web && npm audit
  # Output: found 0 vulnerabilities
  ```

### Build Footprint
- **Total Frontend Production Bundle (Gzipped):** `~170 kB`
  - JavaScript bundle: `~153 kB` (gzip)
  - CSS stylesheet: `~16 kB` (gzip)
  - HTML shell: `0.49 kB` (gzip)
- **Time to Compile:** `~1.0 second` using Vite and TypeScript.
- **Memory Footprint:** Running server consumes `< 45 MB` of RAM on idle; peak under full 100k query load is `< 120 MB`.
