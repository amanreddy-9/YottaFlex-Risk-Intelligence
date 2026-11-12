-- YottaFlex Relational Schema (v1.0.0)
-- Enforces primary keys, foreign keys, and structural integrity.
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS account_ownerships;
DROP TABLE IF EXISTS merchants;
DROP TABLE IF EXISTS devices;
DROP TABLE IF EXISTS account_device_links;
DROP TABLE IF EXISTS account_state_events;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS transfer_links;
DROP TABLE IF EXISTS risk_rules;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS alert_trigger_facts;
DROP TABLE IF EXISTS cases;
DROP TABLE IF EXISTS case_alert_links;
DROP TABLE IF EXISTS analyst_actions;
DROP TABLE IF EXISTS case_state_events;

-- Customer: Registered account holder and KYC profile master table.
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    segment TEXT NOT NULL,
    kyc_tier TEXT NOT NULL,
    kyc_verified_at TEXT NOT NULL,
    declared_annual_income REAL NOT NULL,
    home_country TEXT NOT NULL,
    risk_rating TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Account: Financial ledger account with ownership, overdraft policy, and derived reconciled balance.
CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    primary_customer_id TEXT NOT NULL,
    account_type TEXT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    overdraft_allowed INTEGER NOT NULL,
    overdraft_limit REAL NOT NULL,
    opening_balance REAL NOT NULL,
    current_balance REAL NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    FOREIGN KEY (primary_customer_id) REFERENCES customers(customer_id)
);

-- AccountOwnership: Many-to-many bridge linking customers to primary and joint accounts.
CREATE TABLE account_ownerships (
    ownership_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    ownership_role TEXT NOT NULL,
    ownership_pct REAL NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- Merchant: Synthetic merchant directory with MCC codes, geography, and risk tiers.
CREATE TABLE merchants (
    merchant_id TEXT PRIMARY KEY,
    merchant_name TEXT NOT NULL,
    mcc TEXT NOT NULL,
    category TEXT NOT NULL,
    country TEXT NOT NULL,
    risk_tier TEXT NOT NULL,
    is_high_risk_mcc INTEGER NOT NULL,
    registered_at TEXT NOT NULL
);

-- Device: Endpoint device fingerprint catalog used to detect new-device and shared-mule-device rings.
CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    device_fingerprint TEXT NOT NULL,
    os_family TEXT NOT NULL,
    is_emulator INTEGER NOT NULL,
    ip_country TEXT NOT NULL,
    risk_tier TEXT NOT NULL,
    first_observed_at TEXT NOT NULL
);

-- AccountDeviceLink: Many-to-many association tracking when each device was bound to or used on each account.
CREATE TABLE account_device_links (
    link_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_trusted INTEGER NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

-- AccountStateEvent: Immutable append-only audit log of account lifecycle state changes.
CREATE TABLE account_state_events (
    event_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    prev_status TEXT,
    new_status TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

-- Transaction: Timestamped financial ledger event with reconciled before/after balances.
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    txn_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    balance_before REAL NOT NULL,
    balance_after REAL NOT NULL,
    channel TEXT NOT NULL,
    merchant_id TEXT,
    device_id TEXT,
    counterparty_country TEXT NOT NULL,
    status TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    reference_note TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id),
    FOREIGN KEY (device_id) REFERENCES devices(device_id)
);

-- TransferLink: Explicit double-entry transfer bridge pairing outbound debit and inbound credit legs.
CREATE TABLE transfer_links (
    transfer_id TEXT PRIMARY KEY,
    debit_txn_id TEXT NOT NULL,
    credit_txn_id TEXT,
    source_account_id TEXT NOT NULL,
    dest_account_id TEXT NOT NULL,
    transfer_amount REAL NOT NULL,
    is_same_customer INTEGER NOT NULL,
    status TEXT NOT NULL,
    initiated_at TEXT NOT NULL,
    settled_at TEXT,
    FOREIGN KEY (debit_txn_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (credit_txn_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (source_account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (dest_account_id) REFERENCES accounts(account_id)
);

-- RiskRule: Transparent, versioned AML/fraud detection rules with explicit thresholds and priority weights.
CREATE TABLE risk_rules (
    rule_id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    base_weight INTEGER NOT NULL,
    threshold_desc TEXT NOT NULL,
    is_active INTEGER NOT NULL,
    version TEXT NOT NULL,
    effective_from TEXT NOT NULL
);

-- Alert: Rule-generated risk alert with explainable score and traceability to triggering facts.
CREATE TABLE alerts (
    alert_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    primary_txn_id TEXT,
    severity TEXT NOT NULL,
    risk_score REAL NOT NULL,
    trigger_txn_count INTEGER NOT NULL,
    trigger_total_amount REAL NOT NULL,
    explanation_summary TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (rule_id) REFERENCES risk_rules(rule_id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (primary_txn_id) REFERENCES transactions(transaction_id)
);

-- AlertTriggerFact: Fact-level audit bridge linking every alert to the exact transactions and quantitative thresholds that triggered it.
CREATE TABLE alert_trigger_facts (
    fact_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    transfer_id TEXT,
    rule_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    observed_value TEXT NOT NULL,
    threshold_value TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (alert_id) REFERENCES alerts(alert_id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (transfer_id) REFERENCES transfer_links(transfer_id),
    FOREIGN KEY (rule_id) REFERENCES risk_rules(rule_id)
);

-- Case: Grouped investigation dossier aggregating linked alerts, accounts, and explainable priority score.
CREATE TABLE cases (
    case_id TEXT PRIMARY KEY,
    primary_account_id TEXT NOT NULL,
    primary_customer_id TEXT NOT NULL,
    linkage_summary TEXT NOT NULL,
    linked_account_count INTEGER NOT NULL,
    alert_count INTEGER NOT NULL,
    total_exposure_amount REAL NOT NULL,
    priority_score REAL NOT NULL,
    priority_tier TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (primary_account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (primary_customer_id) REFERENCES customers(customer_id)
);

-- CaseAlertLink: Bridge linking individual alerts into multi-account or multi-rule investigation cases.
CREATE TABLE case_alert_links (
    case_alert_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    linkage_reason TEXT NOT NULL,
    linkage_key TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    FOREIGN KEY (alert_id) REFERENCES alerts(alert_id)
);

-- AnalystAction: Immutable record of operations analyst and compliance reviewer triage actions and dispositions.
CREATE TABLE analyst_actions (
    action_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    analyst_id TEXT NOT NULL,
    analyst_role TEXT NOT NULL,
    action_type TEXT NOT NULL,
    rationale TEXT NOT NULL,
    acted_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
);

-- CaseStateEvent: Immutable append-only audit trail of every case status transition.
CREATE TABLE case_state_events (
    case_event_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    prev_status TEXT,
    new_status TEXT NOT NULL,
    analyst_action_id TEXT,
    effective_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    FOREIGN KEY (analyst_action_id) REFERENCES analyst_actions(action_id)
);

CREATE INDEX idx_transactions_account_time ON transactions(account_id, occurred_at);
CREATE INDEX idx_transactions_device ON transactions(device_id);
CREATE INDEX idx_transfer_links_src_dst ON transfer_links(source_account_id, dest_account_id);
CREATE INDEX idx_alerts_account ON alerts(account_id);
CREATE INDEX idx_alert_facts_alert ON alert_trigger_facts(alert_id);
CREATE INDEX idx_case_alerts_case ON case_alert_links(case_id);
CREATE INDEX idx_analyst_actions_case ON analyst_actions(case_id);
