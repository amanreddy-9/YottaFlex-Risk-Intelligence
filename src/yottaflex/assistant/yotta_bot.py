"""Yotta Bot — Project-aware + live SQLite assistant for the YottaFlex Workbench.

100% self-contained with zero external API keys so any reviewer cloning the
repository from GitHub gets full live chatbot functionality immediately.
"""

from __future__ import annotations

import re
from typing import Any

from yottaflex.api.service import WorkbenchService

ENTITY_PATTERNS = {
    "case": re.compile(r"\b(CASE-\d{4}-\d+)\b", re.IGNORECASE),
    "alert": re.compile(r"\b(ALT-\d{4}-\d+)\b", re.IGNORECASE),
    "txn": re.compile(r"\b(TXN-\d{4}-\d+)\b", re.IGNORECASE),
    "account": re.compile(r"\b(ACC-CUS-\d+-\d+)\b", re.IGNORECASE),
    "customer": re.compile(r"\b(CUS-\d+)\b", re.IGNORECASE),
    "rule": re.compile(r"\bRULE[- ]?0*([1-8])\b", re.IGNORECASE),
    "email": re.compile(r"\b([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})\b", re.IGNORECASE),
}

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "get", "how", "i", "in", "into", "is", "it", "me", "my", "of", "on",
    "or", "our", "please", "see", "show", "tell", "that", "the", "this", "to",
    "what", "where", "which", "who", "why", "with", "you", "your",
}

_NAME_FILLER = _STOP_WORDS | {
    "about", "account", "accounts", "alert", "alerts", "case", "cases", "check",
    "customer", "customers", "detail", "details", "explain", "find", "flagged",
    "high", "info", "information", "inspect", "look", "lookup", "person",
    "profile", "risk", "risky", "search", "suspicious", "transaction",
    "transactions", "user", "why",
}


def _stem(word: str) -> str:
    w = word.lower().strip("_")
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("ed") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _tokenize(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9_]+", text.lower())
    out: set[str] = set()
    for tok in raw:
        if tok in _STOP_WORDS:
            continue
        out.add(tok)
        out.add(_stem(tok))
    return out


KNOWLEDGE_CARDS: list[dict[str, Any]] = [
    {
        "id": "what_is_yottaflex",
        "keywords": {
            "yottaflex", "app", "application", "workbench", "platform", "system",
            "purpose", "do", "use", "start", "getting started", "begin", "guide",
            "overview", "aml", "fraud", "monitor", "monitoring", "triage",
            "what does yottaflex", "how to use", "explain this app",
        },
        "title": "What YottaFlex Does & How to Use It",
        "answer": (
            "**YottaFlex** is an **Explainable AML Risk & Transaction Prioritization Workbench** built to catch suspicious financial behavior and separate true risks from noisy false positives:\n"
            "• **1. Start at Overview:** Review portfolio KPIs, risk distributions, time-filtered charts (`7D / 30D / 90D / ALL`), and top high-risk customers/accounts.\n"
            "• **2. Triage the Queue:** Cases are ranked by composite **Priority Score** (not naive FIFO) so high-exposure circular rings, velocity bursts, and shared-device clusters surface first.\n"
            "• **3. Investigate in Dossier:** Inspect alert explainability waterfalls, entity network graphs, and submit audited actions (`CONFIRM_FRAUD`, `ESCALATE`, `FILE_SAR`, `FALSE_POSITIVE`).\n"
            "• **4. Explore Ledger & Rules:** Drill into **Customers**, **Accounts**, **Txns** (plus live Rule Engine simulator), **Alerts**, **Quarantine**, and **Evaluation**."
        ),
        "actions": [
            {"type": "tab", "id": "overview", "label": "Overview"},
            {"type": "tab", "id": "queue", "label": "Open Queue"},
        ],
    },
    {
        "id": "credentials",
        "keywords": {
            "login", "sign", "signin", "sign in", "log in", "password", "email",
            "credential", "credentials", "verifier", "role", "roles", "rbac",
            "locked", "permission", "permissions", "admin", "reviewer", "analyst",
            "session", "sessions", "logout", "forgot", "reset",
        },
        "title": "Sign-In Credentials & RBAC Roles",
        "answer": (
            "**Institutional Sign-In Accounts (all use password `YottaFlex#2026`):**\n"
            "• **Operations Analyst:** `analyst@yottaflex.com` (`OPS_ANALYST` — view ledger, triage cases, add notes, escalate/mark FP).\n"
            "• **Risk/Compliance Reviewer:** `reviewer@yottaflex.com` (`RISK_REVIEWER` — approve dispositions, file SARs via `FILE_SAR`, reopen closed cases).\n"
            "• **System Administrator:** `admin@yottaflex.com` (`SYSTEM_ADMIN` — full access including editing `RiskRule` weights & toggling rules).\n\n"
            "Sessions use PBKDF2-SHA256 salted password hashes, Bearer tokens + `HttpOnly` session cookies, and log every login/action to SQLite."
        ),
        "actions": [],
    },
    {
        "id": "investigation_workflow",
        "keywords": {
            "investigate", "investigation", "triage", "workflow", "dossier",
            "waterfall", "network", "graph", "action", "actions", "escalate",
            "sar", "file sar", "false positive", "benign", "reopen", "note",
            "audit", "rationale", "handle", "fraud", "review case",
        },
        "title": "Case Investigation, Dossier, SAR & Watchlist Workflow",
        "answer": (
            "**How to Investigate & Disposition a Case in YottaFlex (Functions 101–125):**\n"
            "1. Open **Queue** (filter by SLA, exposure, dates, assignee & compare **FIFO vs Priority Rank Δ**) or **Alerts** (assign, bulk triage, suppress FP, or escalate alerts into cases).\n"
            "2. Inspect the **Dossier**: review the **Explainability Waterfall**, **Entity Network Graph**, **Evidence Checklist**, link/unlink sibling alerts, and apply **Watchlist Tags** (`MULE_SUSPECT`, `PEP_WATCH`, etc.).\n"
            "3. Auto-generate a structured **SAR Narrative Draft**, export the **Investigation Packet** (JSON/Markdown), and record audited decisions (`REOPEN_CASE`, `FILE_SAR`, and high-exposure `>= $25k` closures require **Reviewer/Admin** sign-off)."
        ),
        "actions": [
            {"type": "tab", "id": "queue", "label": "Open Queue"},
            {"type": "tab", "id": "dossier", "label": "Open Dossier"},
        ],
    },
    {
        "id": "ui_and_theme",
        "keywords": {
            "dark", "light", "dark mode", "light mode", "theme", "appearance",
            "sidebar", "navbar", "glass", "glassmorphism", "slider", "yotta bot",
            "yottabot", "chatbot", "bot", "settings", "profile", "ui", "interface",
            "layout", "switch mode", "toggle",
        },
        "title": "Workbench Appearance, Dark/Light Mode & Navigation",
        "answer": (
            "**YottaFlex UI & Controls:**\n"
            "• **Default Dark Mode & Theme Toggle:** YottaFlex opens in **Pure-Black Liquid Glass Dark Mode** by default. Click the **Light Mode / Dark Mode** pill button in the top-right header anytime to switch themes.\n"
            "• **Overview Layout:** The Overview page features the crystal **Left Sidebar** (with cursor-tracking glass slider across all 9 modules, Settings, Help & Support, and your profile card) alongside a compact 4-option top bar (`Overview`, `Queue`, `Alerts`, `Txns`). Other pages use the full-width top dock.\n"
            "• **Yotta Bot:** Always available from the bottom-right glass icon or **Help & Support**."
        ),
        "actions": [{"type": "tab", "id": "overview", "label": "Go to Overview"}],
    },
    {
        "id": "architecture",
        "keywords": {
            "architecture", "tech", "stack", "project", "structure", "file",
            "files", "folder", "backend", "frontend", "react", "typescript",
            "tailwind", "python", "sqlite", "github", "design", "how it works",
        },
        "title": "YottaFlex System Architecture",
        "answer": (
            "**YottaFlex** is built cleanly with zero paid external runtime dependencies:\n"
            "• **Backend:** Zero-dependency Python 3.11+ HTTP REST server (`src/yottaflex/api/server.py`, `service.py`) + SQLite (`yottaflex.db`).\n"
            "• **Frontend:** React + TypeScript + Tailwind CSS (`web/src/components/`) styled with iOS Liquid Glass.\n"
            "• **Deterministic Generator (`src/yottaflex/generator/`):** Reproducibly generates synthetic entities, ledger txns, typologies, and 5 labeled negative edge cases from `--seed 20261022`.\n"
            "• **Integrity Validator (`src/yottaflex/validation/`):** Runs 9 automated reconciliation checks and routes anomalies to **Quarantine**.\n"
            "• **Rule & Scoring Engine (`src/yottaflex/engine/`):** Computes transaction, account, customer, and case scores with zero ground-truth leakage."
        ),
        "actions": [{"type": "tab", "id": "overview", "label": "Open Overview"}],
    },
    {
        "id": "cli_and_tests",
        "keywords": {
            "run", "cli", "command", "commands", "generate", "validate", "serve",
            "test", "tests", "unittest", "seed", "reproducible", "reproducibility",
            "port", "install", "setup", "starter", "full",
        },
        "title": "CLI Commands, Dataset Scales & Test Suite",
        "answer": (
            "**Key Project Commands (run from repo root):**\n"
            "• **Generate starter/full world:** `PYTHONPATH=src python3 -m yottaflex.cli generate --scale full --seed 20261022`\n"
            "• **Run 9-check validator:** `PYTHONPATH=src python3 -m yottaflex.cli validate --scale full`\n"
            "• **Run evaluation harness:** `PYTHONPATH=src python3 -m yottaflex.cli evaluate --scale full`\n"
            "• **Start Workbench server:** `PYTHONPATH=src python3 -m yottaflex.cli serve --scale full --port 8080`\n"
            "• **Build frontend:** `npm --prefix web run build`\n"
            "• **Run all 30 unit tests:** `python3 -m unittest discover -s tests -v`\n\n"
            "**Dataset Scales:** `starter` = 500 customers / 700 accounts / 10,000 txns; `full` = 5,000 customers / 7,000 accounts / 100,000 txns."
        ),
        "actions": [{"type": "tab", "id": "evaluation", "label": "Open Evaluation"}],
    },
    {
        "id": "navigation_tabs",
        "keywords": {
            "tab", "tabs", "navigate", "page", "pages", "menu", "customer",
            "customers", "account", "accounts", "txns", "where", "feature",
            "features", "functionality", "functionalities", "list tabs",
        },
        "title": "Workbench Tabs & Navigation Guide (Functions 1–275)",
        "answer": (
            "**10 Liquid Glass Workbench Views (+ `⌘K` Search, Bookmarks, Notifications & `?` Shortcuts):**\n"
            "1. **Overview:** Portfolio KPIs, interactive volume/risk charts, time duration pills (`7D/30D/90D/ALL`), CSV/JSON export.\n"
            "2. **Queue:** Prioritized case triage ranked by composite priority score vs FIFO, saved presets, bulk tag & batch actions.\n"
            "3. **Customers:** Directory of 5,000 customers, Sanctions/PEP screening, Unified Chronology, Corridor exposure & filtered CSV/JSON export.\n"
            "4. **Accounts:** Directory of 7,000 accounts, freeze/hold controls, Burst/Night profile, Transfer matrix & filtered CSV/JSON export.\n"
            "5. **Txns (Transactions & Risk Engine):** 100k ledger filters, Batch Simulation, Custom Rule Drafts, Pattern Sandbox & Calibration Approvals.\n"
            "6. **Alerts:** Generated alerts directory, Rule Co-Occurrence Matrix, Fatigue/Noise report, FP suppressions & Alert 360°.\n"
            "7. **Dossier:** Case investigation dossier with Entity Graph, SOP Playbooks, Pinboard, GoAML XML, Shift Handoffs, Evidence Seal & Reopen.\n"
            "8. **Quarantine:** Ledger invariant exceptions, Balance Continuity audit, Root-Cause Grouping & bulk remediation.\n"
            "9. **Evaluation:** `@K%` simulator, 10-Decile Lift Curve, TP/FP Histogram, Rule Marginal Ablation Lift, Feature PSI Drift & Zero-Leakage AST.\n"
            "10. **Governance & Ops:** Corridors, Mule Fan-In/Out Hubs, QA Sampling, Exam Readiness, Webhooks, Retention & Live API Telemetry."
        ),
        "actions": [
            {"type": "tab", "id": "overview", "label": "Overview"},
            {"type": "tab", "id": "transactions", "label": "Txns & Scoring"},
            {"type": "tab", "id": "alerts", "label": "Alerts"},
            {"type": "tab", "id": "queue", "label": "Triage Queue"},
        ],
    },
    {
        "id": "typologies",
        "keywords": {
            "typology", "typologies", "anomaly", "anomalies", "pattern", "patterns",
            "velocity", "circular", "ring", "layering", "dormant", "structuring",
            "smurfing", "device", "shared device", "suspicious", "burst",
        },
        "title": "Planted Behavioral Typologies & Anomaly Patterns",
        "answer": (
            "**Causal Behavioral Scenarios in the Synthetic World:**\n"
            "• **Velocity Spikes (`RULE-001`, `RULE-006`):** Rapid burst debits (`>=5` in `60m` >= `$2,500`) or split structuring outflows (`>=3` txns `$1,800–$2,999.99` in `24h`).\n"
            "• **New-Device High-Value Outflows (`RULE-002`):** Outbound txn `>= $1,500` from a device linked `<= 24h` earlier.\n"
            "• **Circular Transfer Rings (`RULE-003`):** Multi-hop `TransferLink` cycles (`A → B → C → A`) returning `>= 75%` within `48h`.\n"
            "• **Dormant Account Reactivation (`RULE-004`):** Accounts previously `DORMANT` suddenly transacting `>= $3,000` within `48h`.\n"
            "• **Shared Devices & Income Deviations (`RULE-007`, `RULE-005`, `RULE-008`):** Unrelated customers sharing a device or rapid income/geography outliers.\n"
            "• **Deliberate False Positives:** Legitimate salary bonuses, tuition/rent, authorized travel, and joint treasury sweeps so precision/suppression can be empirically measured."
        ),
        "actions": [{"type": "tab", "id": "transactions", "label": "Inspect Patterns in Txns"}],
    },
    {
        "id": "export_and_reports",
        "keywords": {"export", "download", "csv", "json", "report", "reports"},
        "title": "Authenticated CSV & JSON Exports",
        "answer": (
            "You can export filtered reports cleanly in **CSV** or **JSON** from:\n"
            "• **Overview:** **Export CSV / Export JSON** (exports filtered analytics, risk breakdown, rule distribution & top entities).\n"
            "• **Customers (Profile):** **Export CSV / Export JSON** (exports customer KYC, risk factors, accounts, alerts & cases).\n"
            "• **Txns (Transactions):** **Export Filtered CSV / Export JSON** (exports matching filtered/sorted transactions with rule & pattern tags)."
        ),
        "actions": [
            {"type": "tab", "id": "overview", "label": "Overview Exports"},
            {"type": "tab", "id": "transactions", "label": "Txn Exports"},
        ],
    },
    {
        "id": "zero_leakage",
        "keywords": {"leakage", "ground truth", "ground_truth", "ast", "isolated", "fair", "cheat", "data leak"},
        "title": "Zero Ground-Truth Leakage Guarantee",
        "answer": (
            "`ground_truth.json` / `ground_truth.csv` are stored strictly in isolation for empirical evaluation **only**.\n"
            "An automated AST guard (`verify_zero_leakage` in `src/yottaflex/evaluation/harness.py`, verified by `test_zero_leakage_ast_guard`) inspects every file in `src/yottaflex/engine/` and `src/yottaflex/validation/` to guarantee zero executable access to `ground_truth`."
        ),
        "actions": [{"type": "tab", "id": "evaluation", "label": "View Evaluation Proof"}],
    },
]


def _has_phrase(text_lower: str, *phrases: str) -> bool:
    """Match whole words or whole multi-word phrases so 'count' never hits 'account'."""
    for ph in phrases:
        if re.search(r"\b" + re.escape(ph) + r"\b", text_lower):
            return True
    return False


_NON_PERSON_WORDS = _NAME_FILLER | {
    "yottaflex", "yottabot", "bot", "workbench", "app", "application", "platform",
    "system", "software", "project", "repo", "github", "python", "react", "sqlite",
    "overview", "queue", "dossier", "quarantine", "evaluation", "alerts", "txns",
    "dark", "light", "mode", "theme", "sidebar", "navbar", "glass", "ui",
    "sar", "rbac", "kyc", "aml", "fraud", "anomaly", "pattern", "typology",
    "scoring", "score", "rule", "rules", "weight", "threshold", "detector",
    "export", "csv", "json", "report", "cli", "command", "test", "tests",
    "seed", "leakage", "ground", "truth", "precision", "recall", "fifo", "lift",
    "governance", "audit", "ring", "rings", "digest", "health", "sla", "ndcg",
    "corridor", "corridors", "jurisdiction", "radar", "merge", "escalation", "siem",
    "sanctions", "pep", "goaml", "psi", "drift", "qa", "webhook", "telemetry", "continuity",
}


def _extract_name_candidate(q: str) -> str | None:
    """Extract a potential customer name from natural language without matching app/domain nouns."""
    m_cap = re.search(r"\b([A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20})\b", q)
    if m_cap:
        words_cap = m_cap.group(1).lower().split()
        if not any(w in _NON_PERSON_WORDS for w in words_cap):
            return m_cap.group(1)
    words = [w for w in re.findall(r"[A-Za-z0-9._+-]+", q) if w.lower() not in _NON_PERSON_WORDS]
    if 2 <= len(words) <= 3:
        return " ".join(words)
    return None


def answer_user_query(
    service: WorkbenchService,
    query: str,
    *,
    authenticated_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Answer user questions about the YottaFlex project or live database entities accurately."""
    q = (query or "").strip()
    if not q:
        return {
            "reply": "Ask me anything about YottaFlex — sign-in credentials, how any tab or feature works, the 8 risk rules, live metrics, evaluation lift, or paste any ID like `CASE-2026-000017`, `ALT-2026-000001`, `CUS-000001`, `ACC-CUS-000001-01`, or `TXN-2026-00000001`.",
            "actions": [
                {"type": "tab", "id": "overview", "label": "Overview"},
                {"type": "tab", "id": "transactions", "label": "Txns & Scoring"},
                {"type": "tab", "id": "alerts", "label": "Alerts"},
            ],
            "source": "Yotta Bot Guide",
        }

    q_lower = q.lower()
    q_clean = re.sub(r"[^\w\s]", "", q_lower).strip()
    is_authed = authenticated_user is not None

    # 0. Friendly conversational greetings, identity & gratitude
    if q_clean in {"hi", "hello", "hey", "yo", "hola", "hii", "helo", "good morning", "good afternoon", "good evening"} or q_clean.startswith(("hi ", "hello ", "hey ")):
        ov = service.get_overview()
        c = ov["counts"]
        return {
            "reply": (
                f"Hello! I'm **Yotta Bot** — ready to help with the YottaFlex Workbench "
                f"({c.get('customers', 0):,} customers, {c.get('transactions', 0):,} txns, {c.get('cases', 0):,} cases loaded).\n\n"
                "Try asking me:\n"
                "• *\"What does YottaFlex do?\"* or *\"How do I sign in?\"*\n"
                "• *\"Show open cases\"*, *\"Explain all 8 risk rules\"*, or *\"Show quarantine exceptions\"*\n"
                "• *\"Inspect CASE-2026-000017\"* or *\"Why is Samuel Walker risky?\"*"
            ),
            "actions": [
                {"type": "tab", "id": "overview", "label": "Overview"},
                {"type": "tab", "id": "queue", "label": "Triage Queue"},
            ],
            "source": "Yotta Bot Greeting",
        }

    if q_clean in {"thanks", "thank you", "thx", "ty", "awesome", "great", "cool", "ok", "okay", "nice"}:
        return {
            "reply": "You're welcome! Let me know if you want to look up any `CASE`, `ALT`, `CUS`, `ACC`, or `TXN` ID, inspect risk rules, or check evaluation metrics.",
            "actions": [],
            "source": "Yotta Bot Assistant",
        }

    if _has_phrase(q_lower, "who are you", "what are you", "what can you do", "introduce yourself"):
        return {
            "reply": (
                "I'm **Yotta Bot**, the self-contained assistant built into **YottaFlex**.\n"
                "• **Live Ledger & Risk Lookups:** Inspect any customer (by ID or name), account, transaction, alert, rule, or case dossier directly from SQLite.\n"
                "• **Portfolio & Evaluation Insights:** Query live dataset counts, top priority/open cases, quarantine exceptions, and Priority vs. FIFO lift.\n"
                "• **Project & UI Guide:** Explain sign-in credentials, RBAC permissions, the 8 risk rules, behavioral typologies, CLI commands, and Dark/Light mode."
            ),
            "actions": [
                {"type": "tab", "id": "overview", "label": "Overview"},
                {"type": "tab", "id": "transactions", "label": "Risk Engine"},
                {"type": "tab", "id": "evaluation", "label": "Evaluation"},
            ],
            "source": "Yotta Bot Identity",
        }

    # 1. Exact Rule ID lookup (RULE-001 .. RULE-008 or "rule 3") — safe for all users
    m_rule = ENTITY_PATTERNS["rule"].search(q)
    if m_rule:
        rid = f"RULE-00{m_rule.group(1)}"
        rules = {r["rule_id"]: r for r in service.list_rules()}
        r = rules.get(rid)
        if r:
            return {
                "reply": (
                    f"**{r['rule_id']} — {r['rule_name']}**\n"
                    f"• **Category / Severity:** {r['category']} / {r['severity']}\n"
                    f"• **Base Weight:** {r['base_weight']} pts | **Active:** {'Yes' if r.get('is_active', 1) else 'No'}\n"
                    f"• **Condition:** {r['threshold_desc']}\n"
                    f"• **Live Hits:** {r['hit_count']:,} alerts (avg score {r['avg_alert_score']})"
                ),
                "actions": [{"type": "tab", "id": "transactions", "label": "Inspect Rules & Scoring"}],
                "source": "Live RiskRule Catalog",
            }

    # 2. Exact Entity ID lookups (Case, Alert, Transaction, Account, Customer)
    for kind, pattern in (
        ("case", ENTITY_PATTERNS["case"]),
        ("alert", ENTITY_PATTERNS["alert"]),
        ("txn", ENTITY_PATTERNS["txn"]),
        ("account", ENTITY_PATTERNS["account"]),
        ("customer", ENTITY_PATTERNS["customer"]),
    ):
        m = pattern.search(q)
        if not m:
            continue
        eid = m.group(1).upper()
        if not is_authed:
            return {
                "reply": (
                    f"I detected entity ID **`{eid}`**. To protect customer and ledger data, please **sign in first** "
                    f"(sample Analyst: `analyst@yottaflex.com` / `YottaFlex#2026`), and then ask me again to inspect `{eid}` directly!"
                ),
                "actions": [],
                "source": "RBAC Security Guard",
            }
        if kind == "case":
            dos = service.get_case_dossier(eid)
            if not dos:
                return {"reply": f"Case **`{eid}`** was not found in the active dataset.", "actions": [], "source": "Live DB"}
            c = dos["case"]
            return {
                "reply": (
                    f"**{c['case_id']}** ({c['priority_tier']} Priority — Score **{c['priority_score']}**)\n"
                    f"• **Status:** `{c['status']}` | **Primary Account:** `{c['primary_account_id']}`\n"
                    f"• **Exposure:** ${float(c['total_exposure_amount']):,.2f} across {c['alert_count']} alert(s) and {c['linked_account_count']} account(s)\n"
                    f"• **Linkage:** {c['linkage_summary']}"
                ),
                "actions": [{"type": "case", "id": c["case_id"], "label": f"Open {c['case_id']}"}],
                "source": "Live Case Dossier DB",
            }
        if kind == "alert":
            det = service.get_alert_detail(eid)
            if not det:
                return {"reply": f"Alert **`{eid}`** was not found in the active dataset.", "actions": [], "source": "Live DB"}
            al = det["alert"]
            return {
                "reply": (
                    f"**{al['alert_id']}** ({al['severity']} — Score **{al['risk_score']}**)\n"
                    f"• **Rule:** `{al['rule_id']}` ({det['rule']['rule_name'] if det['rule'] else ''}) | **Status:** `{al['status']}`\n"
                    f"• **Customer / Account:** {det['customer']['full_name']} (`{al['customer_id']}`) / `{al['account_id']}`\n"
                    f"• **Summary:** {al['explanation_summary']}"
                ),
                "actions": [{"type": "alert", "id": al["alert_id"], "label": f"Inspect {al['alert_id']}"}],
                "source": "Live Alert DB",
            }
        if kind == "txn":
            det = service.get_transaction_detail(eid)
            if not det:
                return {"reply": f"Transaction **`{eid}`** was not found in the active dataset.", "actions": [], "source": "Live DB"}
            tx = det["transaction"]
            return {
                "reply": (
                    f"**{tx['transaction_id']}** ({tx['txn_type']} • {tx['direction']})\n"
                    f"• **Amount:** ${float(tx['amount']):,.2f} | **Balance:** ${float(tx['balance_before']):,.2f} → ${float(tx['balance_after']):,.2f}\n"
                    f"• **Risk:** **{tx['risk_level']}** ({tx['risk_score']}) | **Country:** {tx['counterparty_country']} | **Occurred:** {tx['occurred_at']}\n"
                    f"• **Customer / Account:** {det['customer']['full_name']} (`{tx['account_id']}`)"
                ),
                "actions": [{"type": "txn", "id": tx["transaction_id"], "label": f"Open {tx['transaction_id']}"}],
                "source": "Live Ledger DB",
            }
        if kind == "account":
            det = service.get_account_detail(eid)
            if not det:
                return {"reply": f"Account **`{eid}`** was not found in the active dataset.", "actions": [], "source": "Live DB"}
            a = det["account"]
            return {
                "reply": (
                    f"**{a['account_id']}** ({a['account_type']} • `{a['status']}`)\n"
                    f"• **Balance:** ${float(a['current_balance']):,.2f} | **Risk Score:** **{det['account_risk_score']}**\n"
                    f"• **Primary Holder:** {det['holders'][0]['full_name'] if det['holders'] else a['primary_customer_id']}\n"
                    f"• **Transactions:** {det['total_transactions']:,} | **Alerts:** {len(det['alerts'])} | **Dormant Reactivated:** {'Yes' if det['is_dormant_reactivated'] else 'No'}"
                ),
                "actions": [{"type": "account", "id": a["account_id"], "label": f"Open {a['account_id']}"}],
                "source": "Live Account DB",
            }
        if kind == "customer":
            prof = service.get_customer_profile(eid)
            if not prof:
                return {"reply": f"Customer **`{eid}`** was not found in the active dataset.", "actions": [], "source": "Live DB"}
            cu = prof["customer"]
            return {
                "reply": (
                    f"**{cu['full_name']}** (`{cu['customer_id']}` — {cu['segment']})\n"
                    f"• **KYC / Risk:** `{cu['kyc_tier']}` / **{prof['customer_risk_level']}** (Score **{prof['customer_risk_score']}**)\n"
                    f"• **Accounts:** {len(prof['accounts'])} ({prof['suspicious_account_count']} suspicious) | **Alerts:** {len(prof['alerts'])} | **Cases:** {len(prof['cases'])}\n"
                    f"• **Email:** `{cu['email']}` • **Country:** `{cu['home_country']}`"
                ),
                "actions": [{"type": "customer", "id": cu["customer_id"], "label": f"Open {cu['customer_id']}"}],
                "source": "Live Customer 360 DB",
            }

    # 3. Email lookup (authenticated)
    m_email = ENTITY_PATTERNS["email"].search(q)
    if m_email:
        email = m_email.group(1)
        if not is_authed:
            return {
                "reply": f"Please **sign in first** (`analyst@yottaflex.com` / `YottaFlex#2026`) so I can safely look up `{email}`.",
                "actions": [],
                "source": "RBAC Security Guard",
            }
        res_cust = service.list_customers(search=email, limit=3)
        if res_cust["items"]:
            top = res_cust["items"][0]
            prof = service.get_customer_profile(top["customer_id"])
            if prof:
                cu = prof["customer"]
                return {
                    "reply": (
                        f"**{cu['full_name']}** (`{cu['customer_id']}` • `{cu['email']}`)\n"
                        f"• **KYC / Risk:** `{cu['kyc_tier']}` / **{prof['customer_risk_level']}** (Score **{prof['customer_risk_score']}**)\n"
                        f"• **Accounts:** {len(prof['accounts'])} ({prof['suspicious_account_count']} suspicious) | **Alerts:** {len(prof['alerts'])} | **Cases:** {len(prof['cases'])}"
                    ),
                    "actions": [{"type": "customer", "id": cu["customer_id"], "label": f"Open {cu['customer_id']}"}],
                    "source": "Live Customer 360 DB",
                }
        return {"reply": f"No customer matched email `{email}` in the active dataset.", "actions": [], "source": "Live Customer DB"}

    # 4. Live Portfolio / Rules / Detectors / Quarantine / Evaluation / Cases / Alerts Intents
    if _has_phrase(q_lower, "rule", "rules", "risk score", "scoring", "weight", "weights", "threshold", "thresholds", "detector", "detectors", "re-evaluate", "reevaluate", "simulator"):
        rules = service.list_rules()
        detectors = service.get_integrity_detectors()["detectors"]
        lines = [
            f"• **`{r['rule_id']}` ({r['base_weight']} pts, {r['severity']}):** {r['rule_name']} — {r['hit_count']:,} hits"
            for r in rules
        ]
        return {
            "reply": (
                "**All 8 Active YottaFlex RiskRules & Scoring Thresholds (`HIGH >= 60`, `MEDIUM 20–59.9`, `LOW < 20`):**\n"
                + "\n".join(lines)
                + f"\n\n**Integrity Detectors Active:** {len(detectors)} detectors monitoring closed accounts, negative balances, orphaned links & duplicates. Admins (`admin@yottaflex.com`) can tune weights & re-evaluate inside **Txns → Risk Engine**."
            ),
            "actions": [
                {"type": "tab", "id": "transactions", "label": "Open Risk Engine"},
                {"type": "tab", "id": "alerts", "label": "View Alerts"},
            ],
            "source": "Live RiskRules & Scoring",
        }

    if _has_phrase(q_lower, "quarantine", "exception", "exceptions", "edge case", "edge cases", "integrity", "invariant", "closed account", "negative balance", "orphan", "orphaned"):
        q_data = service.get_quarantine_exceptions()
        breakdown = "\n".join(
            f"• **`{issue}`:** {cnt} caught" for issue, cnt in q_data["counts_by_issue_type"].items()
        )
        return {
            "reply": (
                f"**Quarantine & Integrity Guard ({q_data['total_exceptions']} total isolated exceptions):**\n"
                f"{breakdown}\n\nAll 5 labeled negative scenario categories are detected automatically by the 9-check validator and isolated from risk scoring."
            ),
            "actions": [{"type": "tab", "id": "quarantine", "label": "Open Quarantine"}],
            "source": "Live Validator Quarantine",
        }

    if _has_phrase(q_lower, "precision", "recall", "lift", "fifo", "evaluation", "metric", "metrics", "performance", "f1", "catch rate", "benchmark"):
        ev = service.get_evaluation()
        p20 = ev["priority_top20"]
        f20 = ev["fifo_top20"]
        return {
            "reply": (
                "**Live Priority vs. FIFO Evaluation Metrics:**\n"
                f"• **Priority Top-20% Recall:** **{round(p20['recall'] * 100, 1)}%** (Precision **{round(p20['precision'] * 100, 1)}%**, {p20['tp']} TP in top {p20['k']} cases)\n"
                f"• **FIFO Baseline Top-20% Recall:** **{round(f20['recall'] * 100, 1)}%** (Precision **{round(f20['precision'] * 100, 1)}%**, {f20['tp']} TP)\n"
                f"• **Negative Edge Catch Rate:** {ev['negative_edge_catch_rate']['caught_count']}/{ev['negative_edge_catch_rate']['injected_count']} caught (All types caught: `{ev['negative_edge_catch_rate']['all_types_caught']}`)"
            ),
            "actions": [{"type": "tab", "id": "evaluation", "label": "Open Evaluation"}],
            "source": "Live Evaluation Harness",
        }

    if _has_phrase(q_lower, "how many", "count", "counts", "stats", "summary", "dataset", "volume", "total", "how big", "records"):
        ov = service.get_overview()
        c = ov["counts"]
        return {
            "reply": (
                f"**Active Dataset Summary (Seed `{ov['seed']}`, Scale `{ov.get('scale', 'full')}`):**\n"
                f"• **Customers:** {c.get('customers', 0):,} | **Accounts:** {c.get('accounts', 0):,} | **Merchants:** {c.get('merchants', 0):,} | **Devices:** {c.get('devices', 0):,}\n"
                f"• **Transactions:** {c.get('transactions', 0):,} | **Transfer Links:** {c.get('transfer_links', 0):,}\n"
                f"• **Alerts:** {c.get('alerts', 0):,} | **Cases:** {c.get('cases', 0):,} (**{c.get('open_cases', 0):,} open**) | **Quarantined:** {ov.get('quarantine_count', 0)}"
            ),
            "actions": [{"type": "tab", "id": "overview", "label": "Open Overview"}],
            "source": "Live Dataset Overview",
        }

    if _has_phrase(q_lower, "open case", "open cases", "top case", "top cases", "highest case", "top risk case", "worst case", "escalated case", "escalated cases", "priority case", "priority cases", "show case", "show cases", "list cases", "show queue", "top priority"):
        ov = service.get_overview()
        c = ov["counts"]
        if not is_authed:
            return {
                "reply": (
                    f"**Queue Snapshot:** There are **{c.get('open_cases', 0):,} open cases** out of **{c.get('cases', 0):,} total** "
                    f"({c.get('escalated_cases', 0)} escalated, total exposure **${float(c.get('total_case_exposure', 0)):,.2f}**).\n\n"
                    "Sign in (e.g. `analyst@yottaflex.com` / `YottaFlex#2026`) and ask again to list specific top cases and open their dossiers."
                ),
                "actions": [],
                "source": "Live Queue Summary",
            }
        status_filter = "ESCALATED" if "escalat" in q_lower else ("OPEN" if "open" in q_lower else None)
        top_cases = service.list_cases(sort="priority", status=status_filter, limit=4)["items"]
        label = f"{status_filter} Priority" if status_filter else "Top Priority"
        lines = [
            f"• **`{cs['case_id']}`:** Priority **{cs['priority_score']}** ({cs['priority_tier']}, `{cs['status']}`) • {cs['customer_name']} • ${float(cs['total_exposure_amount']):,.2f}"
            for cs in top_cases
        ]
        actions = [{"type": "case", "id": cs["case_id"], "label": cs["case_id"]} for cs in top_cases]
        return {
            "reply": f"**{label} Investigation Cases ({c.get('open_cases', 0):,} open total):**\n" + "\n".join(lines),
            "actions": actions or [{"type": "tab", "id": "queue", "label": "Open Queue"}],
            "source": "Live Triage Queue",
        }

    if _has_phrase(q_lower, "high risk customer", "high risk customers", "top customer", "top customers", "risky customer", "risky customers", "multi suspicious", "top account", "top accounts", "high risk account", "high risk accounts", "show customer", "show customers", "show account", "show accounts"):
        if not is_authed:
            return {
                "reply": "Please **sign in first** (`analyst@yottaflex.com` / `YottaFlex#2026`) so I can list top high-risk customers and accounts.",
                "actions": [],
                "source": "RBAC Security Guard",
            }
        dash = service.get_dashboard()
        if "account" in q_lower and "multi suspicious" not in q_lower:
            accts = dash.get("top_risk_accounts", [])[:4]
            lines = [
                f"• **`{a['account_id']}`** ({a['status']}) • Holder: {a['customer_name']} • Balance: ${float(a['current_balance']):,.2f} • Max Alert: **{a['max_risk_score']}**"
                for a in accts
            ]
            actions = [{"type": "account", "id": a["account_id"], "label": a["account_id"]} for a in accts]
            return {
                "reply": "**Top High-Risk Accounts Right Now:**\n" + "\n".join(lines),
                "actions": actions or [{"type": "tab", "id": "accounts", "label": "Open Accounts"}],
                "source": "Live High-Risk Accounts",
            }
        custs = dash.get("top_risk_customers", [])[:4]
        lines = [
            f"• **`{cu['customer_id']}` — {cu['full_name']}** ({cu['kyc_tier']}) • {cu['case_count']} case(s) • Exposure ${float(cu['total_exposure']):,.2f} • Max Score **{cu['max_priority_score']}**"
            for cu in custs
        ]
        actions = [{"type": "customer", "id": cu["customer_id"], "label": cu["customer_id"]} for cu in custs]
        return {
            "reply": "**Top High-Risk Customers Right Now:**\n" + "\n".join(lines),
            "actions": actions or [{"type": "tab", "id": "customers", "label": "Open Customers"}],
            "source": "Live High-Risk Customers",
        }

    if _has_phrase(q_lower, "show alert", "show alerts", "critical alert", "critical alerts", "high risk alert", "high risk alerts", "list alert", "list alerts", "top alert", "top alerts", "recent alert", "recent alerts"):
        if not is_authed:
            return {
                "reply": "Please **sign in first** (`analyst@yottaflex.com` / `YottaFlex#2026`) to inspect individual live alerts.",
                "actions": [],
                "source": "RBAC Security Guard",
            }
        sev = "CRITICAL" if "critical" in q_lower else None
        als = service.list_alerts(severity=sev, sort_by="risk_score", sort_dir="desc", limit=4)["items"]
        lines = [
            f"• **`{a['alert_id']}`** ({a['severity']}, Score **{a['risk_score']}**) • `{a['rule_id']}` • {a['customer_name']} (`{a['account_id']}`)"
            for a in als
        ]
        actions = [{"type": "alert", "id": a["alert_id"], "label": a["alert_id"]} for a in als]
        return {
            "reply": f"**Top {'Critical ' if sev else ''}Alerts Right Now:**\n" + "\n".join(lines),
            "actions": actions or [{"type": "tab", "id": "alerts", "label": "Open Alerts"}],
            "source": "Live Alerts DB",
        }

    if _has_phrase(q_lower, "collusion", "ring", "rings", "shared device", "shared devices", "network ring"):
        if not is_authed:
            return {
                "reply": "Please **sign in first** (`analyst@yottaflex.com` / `YottaFlex#2026`) to inspect shared-device collusion rings.",
                "actions": [],
                "source": "RBAC Security Guard",
            }
        rings = service.detect_collusion_rings(limit=4)
        if not rings["rings"]:
            return {"reply": "No multi-customer shared-device collusion rings are currently detected.", "actions": [{"type": "tab", "id": "governance", "label": "Open Governance"}], "source": "Live Ring Detector"}
        lines = [
            f"• **`{r['ring_id']}` (`{r['device_id']}`):** **{r['customer_count']} customers** / {r['account_count']} accounts • Alerts: {r['alert_count']} (${float(r['alert_exposure']):,.2f})"
            for r in rings["rings"]
        ]
        return {
            "reply": f"**Shared-Device Collusion Rings ({rings['total_rings']} detected):**\n" + "\n".join(lines),
            "actions": [{"type": "tab", "id": "governance", "label": "Inspect Rings in Governance"}],
            "source": "Live Ring Detector",
        }

    if _has_phrase(q_lower, "sar registry", "sar drafts", "sar readiness", "executive digest", "audit ledger", "audit trail", "system health", "governance"):
        if not is_authed:
            return {
                "reply": "Please **sign in first** (`analyst@yottaflex.com` / `YottaFlex#2026`) to inspect SAR Registry, Unified Audit Ledger & Executive Digest.",
                "actions": [],
                "source": "RBAC Security Guard",
            }
        digest = service.get_executive_digest()
        p = digest["pillars"]
        health = service.get_system_health()
        return {
            "reply": (
                "**Governance, Compliance & Executive Digest Snapshot:**\n"
                f"• **Exposure Coverage:** ${p['exposure_concentration']['total_case_exposure']:,.2f} ({p['exposure_concentration']['high_critical_share_pct']}% High/Critical)\n"
                f"• **SAR Tracked Cases:** {p['sar_readiness']['total_sar_tracked']} | **Shared-Device Rings:** {p['sar_readiness']['shared_device_rings']}\n"
                f"• **Quarantine Shield:** {p['quarantine_shield']['total_quarantined']} isolated (${p['quarantine_shield']['quarantined_exposure']:,.2f})\n"
                f"• **Engine Health:** `{health['status']}` • DB `{health['db_size_mb']} MB` • {health['sqlite_index_count']} indexes"
            ),
            "actions": [{"type": "tab", "id": "governance", "label": "Open Governance Hub"}],
            "source": "Live Governance & Digest",
        }

    if _has_phrase(q_lower, "corridor", "corridors", "cross border", "jurisdiction", "structuring", "sla radar", "merge candidate", "pending escalation", "four eyes"):
        if not is_authed:
            return {
                "reply": "Please **sign in first** (`analyst@yottaflex.com` / `YottaFlex#2026`) to inspect forensic corridors, structuring bursts, SLA radar & merge candidates.",
                "actions": [],
                "source": "RBAC Security Guard",
            }
        cor = service.get_corridor_risk_matrix(limit=3)
        st_res = service.detect_structuring_clusters(limit=3)
        radar = service.get_sla_radar()
        mc = service.find_case_merge_candidates(limit=3)
        top_cor = cor["items"][0] if cor["items"] else None
        cor_txt = f"{top_cor['origin_country']}→{top_cor['counterparty_country']} (${top_cor['total_volume']:,.0f}, {top_cor['alert_count']} alerts)" if top_cor else "N/A"
        return {
            "reply": (
                "**Forensics & Escalation Radar Snapshot:**\n"
                f"• **Top Risk Corridor:** {cor_txt}\n"
                f"• **Sub-Threshold Structuring Bursts:** {st_res['total']} account clusters\n"
                f"• **SLA Radar:** {radar['breached_count']} breached • {radar['at_risk_count']} at-risk (<8h)\n"
                f"• **Case Merge Candidates:** {mc['total']} overlapping customer pairs"
            ),
            "actions": [
                {"type": "tab", "id": "governance", "label": "Open Forensics & Governance"},
                {"type": "tab", "id": "queue", "label": "Open Triage Queue"},
            ],
            "source": "Live Forensics & SLA Radar",
        }

    if _has_phrase(q_lower, "sanctions", "pep", "fan hub", "mule hub", "psi", "drift", "qa", "exam", "goaml", "continuity", "scorecard", "webhook"):
        if not is_authed:
            return {
                "reply": "Please **sign in first** (`analyst@yottaflex.com` / `YottaFlex#2026`) to query live Sanctions/PEP screening, Mule Hubs, PSI Drift & QA controls.",
                "actions": [],
                "source": "RBAC Security Guard",
            }
        hubs = service.get_fan_in_out_hubs(limit=3)
        psi = service.get_evaluation_feature_psi()
        chain = service.verify_audit_chain()
        exam = service.list_exam_readiness()
        verified_exam = sum(1 for c in exam if c["status"] == "VERIFIED")
        top_psi = psi["features"][0] if psi["features"] else {"feature": "Amount", "psi": 0.0, "status": "STABLE"}
        return {
            "reply": (
                "**Enterprise Intelligence, QA & Model Drift (Functions 226–275):**\n"
                f"• **Mule Fan-In/Out Hubs:** {hubs['total']} active hub accounts tracked\n"
                f"• **Feature Drift PSI:** `{top_psi['feature']}` = `{top_psi['psi']}` (`{top_psi['status']}`)\n"
                f"• **Audit SHA-256 Chain:** `{'VERIFIED' if chain['verified'] else 'CHECK'}` ({chain['events_checked']} events)\n"
                f"• **Exam Readiness Controls:** {verified_exam}/{len(exam)} controls verified"
            ),
            "actions": [
                {"type": "tab", "id": "governance", "label": "Open Intelligence & QA"},
                {"type": "tab", "id": "evaluation", "label": "Open PSI & Lift Curve"},
            ],
            "source": "Live Enterprise Telemetry & Evaluation",
        }

    # 5. Live Customer Name Search (e.g. "why is Samuel Walker risky", "check Noah Perez")
    name_candidate = _extract_name_candidate(q)
    if name_candidate:
        matches = service.list_customers(search=name_candidate, limit=4)
        if matches["items"]:
            if not is_authed:
                return {
                    "reply": (
                        f"I found **{matches['total']}** matching customer record(s) for `{name_candidate}`. "
                        "Please **sign in first** (`analyst@yottaflex.com` / `YottaFlex#2026`) to view customer profiles and risk breakdowns."
                    ),
                    "actions": [],
                    "source": "RBAC Security Guard",
                }
            top = matches["items"][0]
            prof = service.get_customer_profile(top["customer_id"])
            if prof:
                cu = prof["customer"]
                others = [f"`{m['customer_id']}` ({m['full_name']})" for m in matches["items"][1:3]]
                other_note = f"\n• **Other matches:** {', '.join(others)}" if others else ""
                case_note = (
                    f"Top Case: `{prof['cases'][0]['case_id']}` (Score **{prof['cases'][0]['priority_score']}**)"
                    if prof["cases"]
                    else "No active cases"
                )
                return {
                    "reply": (
                        f"**{cu['full_name']}** (`{cu['customer_id']}` — {cu['segment']})\n"
                        f"• **KYC / Risk:** `{cu['kyc_tier']}` / **{prof['customer_risk_level']}** (Score **{prof['customer_risk_score']}**)\n"
                        f"• **Exposure:** {len(prof['accounts'])} account(s) ({prof['suspicious_account_count']} suspicious) | {len(prof['alerts'])} alert(s) | {case_note}\n"
                        f"• **Email:** `{cu['email']}` • **Country:** `{cu['home_country']}`{other_note}"
                    ),
                    "actions": [{"type": "customer", "id": cu["customer_id"], "label": f"Open {cu['customer_id']}"}],
                    "source": "Live Customer Search",
                }

    # 6. Stemmed + Phrase-Weighted Knowledge Card Retrieval across entire project
    q_tokens = _tokenize(q)
    best_card = None
    best_score = 0
    for card in KNOWLEDGE_CARDS:
        card_tokens = set()
        for kw in card["keywords"]:
            if " " not in kw:
                card_tokens.add(kw)
                card_tokens.add(_stem(kw))
        overlap = len(q_tokens & card_tokens)
        phrase_hit = sum(3 for kw in card["keywords"] if " " in kw and kw in q_lower)
        score = overlap + phrase_hit
        if score > best_score:
            best_score = score
            best_card = card

    if best_card and best_score >= 1:
        return {
            "reply": f"**{best_card['title']}**\n{best_card['answer']}",
            "actions": best_card["actions"],
            "source": "YottaFlex Project Knowledge",
        }

    # 7. Contextual Guided Fallback including live snapshot
    ov = service.get_overview()
    c = ov["counts"]
    return {
        "reply": (
            f"I didn't find a direct match for *\"{q[:60]}\"*, so here's what I can answer right away "
            f"(live dataset: **{c.get('customers', 0):,} customers**, **{c.get('transactions', 0):,} txns**, **{c.get('open_cases', 0):,} open cases**):\n"
            "• **Project & UI:** *\"What does YottaFlex do?\"*, *\"How do I sign in?\"*, *\"How does dark mode work?\"*\n"
            "• **Live Queue & Risk:** *\"Show open cases\"*, *\"Top high-risk customers\"*, *\"Explain all 8 risk rules\"*\n"
            "• **Metrics & Integrity:** *\"Show quarantine exceptions\"*, *\"What is Priority vs FIFO recall?\"*\n"
            "• **Entity Lookup:** Ask by customer name (*\"Why is Samuel Walker risky?\"*) or ID (`CASE-2026-000017`, `ALT-2026-000001`, `CUS-000001`, `ACC-CUS-000001-01`, `TXN-2026-00000001`, `RULE-003`)."
        ),
        "actions": [
            {"type": "tab", "id": "overview", "label": "Overview"},
            {"type": "tab", "id": "transactions", "label": "Txns & Scoring"},
            {"type": "tab", "id": "alerts", "label": "Alerts"},
            {"type": "tab", "id": "queue", "label": "Queue"},
        ],
        "source": "Yotta Bot Assistant",
    }
