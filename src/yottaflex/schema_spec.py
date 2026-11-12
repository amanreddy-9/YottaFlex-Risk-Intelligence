"""Single source of truth for the YottaFlex relational schema and data dictionary.

Generates:
  - schema/schema.sql
  - schema/data_dictionary.json
  - docs/data_dictionary.md
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    name: str
    logical_type: str
    sql_type: str
    required: bool
    allowed_values: str
    units: str
    uniqueness: str
    validation_rule: str
    description: str
    fk: str | None = None


@dataclass(frozen=True)
class TableSpec:
    entity_name: str
    table_name: str
    category: str
    primary_key: str
    id_pattern: str
    relationships: list[str]
    lifecycle_states: str
    effective_date_fields: str
    description: str
    fields: list[FieldSpec] = field(default_factory=list)


SCHEMA_VERSION = "1.0.0"

ENUMS: dict[str, list[str]] = {
    "kyc_tier": ["LOW", "STANDARD", "ENHANCED"],
    "customer_risk_rating": ["LOW", "MEDIUM", "HIGH"],
    "customer_status": ["ACTIVE", "RESTRICTED", "OFFBOARDED"],
    "account_type": ["CHECKING", "SAVINGS", "BUSINESS"],
    "account_status": ["ACTIVE", "DORMANT", "FROZEN", "CLOSED"],
    "ownership_role": ["PRIMARY", "JOINT", "AUTHORIZED_SIGNER"],
    "device_os": ["iOS", "Android", "Windows", "macOS", "Linux"],
    "device_risk_tier": ["LOW", "MEDIUM", "HIGH"],
    "merchant_risk_tier": ["LOW", "MEDIUM", "HIGH"],
    "txn_type": [
        "PAYROLL_CREDIT",
        "MERCHANT_PURCHASE",
        "ATM_WITHDRAWAL",
        "INTERNAL_TRANSFER_OUT",
        "INTERNAL_TRANSFER_IN",
        "P2P_TRANSFER_OUT",
        "P2P_TRANSFER_IN",
        "WIRE_OUT",
        "WIRE_IN",
        "FEE",
    ],
    "txn_direction": ["DEBIT", "CREDIT"],
    "txn_channel": ["MOBILE_APP", "WEB", "POS", "ATM", "WIRE", "ACH"],
    "txn_status": ["POSTED", "REVERSED", "FAILED"],
    "transfer_status": ["SETTLED", "MISMATCHED", "INCOMPLETE"],
    "rule_category": ["VELOCITY", "DEVICE", "NETWORK", "LIFECYCLE", "GEO_MERCHANT", "STRUCTURING", "KYC_DEVIATION"],
    "severity": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
    "alert_status": ["OPEN", "GROUPED", "RESOLVED", "DISMISSED"],
    "case_status": [
        "OPEN",
        "IN_REVIEW",
        "ESCALATED",
        "SAR_FILED",
        "CLOSED_CONFIRMED_FRAUD",
        "CLOSED_FALSE_POSITIVE",
    ],
    "analyst_action_type": [
        "CLAIM_REVIEW",
        "ESCALATE",
        "FILE_SAR",
        "CONFIRM_FRAUD",
        "MARK_FALSE_POSITIVE",
        "ADD_NOTE",
    ],
    "linkage_reason": [
        "SINGLE_ACCOUNT_BURST",
        "TRANSFER_RING",
        "SHARED_DEVICE",
        "SHARED_OWNERSHIP",
        "MULTI_RULE_ACCOUNT",
    ],
}


TABLES: list[TableSpec] = [
    TableSpec(
        entity_name="Customer",
        table_name="customers",
        category="Master",
        primary_key="customer_id",
        id_pattern=r"^CUS-\d{6}$",
        relationships=[
            "Customer N:M Account via AccountOwnership (1 customer owns >=1 accounts; joint accounts link >=2 customers)",
            "Customer 1:N Alert (optional direct attribution via primary owner)",
        ],
        lifecycle_states="ACTIVE -> RESTRICTED -> OFFBOARDED",
        effective_date_fields="kyc_verified_at, created_at",
        description="Registered account holder and KYC profile master table.",
        fields=[
            FieldSpec("customer_id", "string", "TEXT PRIMARY KEY", True, "CUS-000001 .. CUS-999999", "none", "PRIMARY KEY", "Matches ^CUS-\\d{6}$", "Immutable deterministic customer identifier."),
            FieldSpec("full_name", "string", "TEXT NOT NULL", True, "Non-empty synthetic full name", "none", "NON-UNIQUE", "Length 3..120", "Synthetic customer full name."),
            FieldSpec("email", "string", "TEXT NOT NULL", True, "Synthetic email address", "none", "UNIQUE", "Valid email format", "Synthetic customer email address."),
            FieldSpec("phone", "string", "TEXT NOT NULL", True, "Synthetic E.164 phone", "none", "NON-UNIQUE", "Matches ^\\+1-555-\\d{3}-\\d{4}$", "Synthetic customer contact phone number."),
            FieldSpec("segment", "enum", "TEXT NOT NULL", True, "RETAIL | AFFLUENT | SMB", "none", "NON-UNIQUE", "In allowed segment enum", "Customer banking segment."),
            FieldSpec("kyc_tier", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["kyc_tier"]), "none", "NON-UNIQUE", "In allowed kyc_tier enum", "Identity verification level."),
            FieldSpec("kyc_verified_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "kyc_verified_at >= created_at", "Timestamp when KYC profile was verified."),
            FieldSpec("declared_annual_income", "decimal(14,2)", "REAL NOT NULL", True, ">= 12000.00", "USD", "NON-UNIQUE", "declared_annual_income > 0", "Self-declared annual income used for deviation rules."),
            FieldSpec("home_country", "string", "TEXT NOT NULL", True, "ISO-3166 alpha-2 (US, CA, GB, DE, SG, IN, BR, MX, AE)", "country code", "NON-UNIQUE", "2 uppercase ASCII letters", "Primary tax/residency country."),
            FieldSpec("risk_rating", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["customer_risk_rating"]), "none", "NON-UNIQUE", "In allowed risk_rating enum", "Baseline onboarding KYC risk rating."),
            FieldSpec("status", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["customer_status"]), "none", "NON-UNIQUE", "In allowed customer_status enum", "Current customer relationship status."),
            FieldSpec("created_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Valid ISO-8601 <= 2026-10-28T23:59:59Z", "Customer onboarding timestamp."),
        ],
    ),
    TableSpec(
        entity_name="Account",
        table_name="accounts",
        category="Master",
        primary_key="account_id",
        id_pattern=r"^ACC-CUS-\d{6}-\d{2}$",
        relationships=[
            "Account N:1 primary Customer (primary_customer_id)",
            "Account N:M Customer via AccountOwnership (supports joint accounts)",
            "Account 1:N AccountStateEvent (append-only lifecycle history)",
            "Account 1:N Transaction (ordered financial ledger)",
            "Account N:M Device via AccountDeviceLink",
        ],
        lifecycle_states="ACTIVE <-> DORMANT -> FROZEN -> CLOSED",
        effective_date_fields="opened_at, closed_at (optional)",
        description="Financial ledger account with ownership, overdraft policy, and derived reconciled balance.",
        fields=[
            FieldSpec("account_id", "string", "TEXT PRIMARY KEY", True, "ACC-CUS-000001-01", "none", "PRIMARY KEY", "Matches ^ACC-CUS-\\d{6}-\\d{2}$", "Immutable deterministic account identifier."),
            FieldSpec("primary_customer_id", "string", "TEXT NOT NULL", True, "Existing CUS-XXXXXX", "none", "NON-UNIQUE", "FK -> customers.customer_id", "Primary owning customer ID.", fk="customers.customer_id"),
            FieldSpec("account_type", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["account_type"]), "none", "NON-UNIQUE", "In allowed account_type enum", "Account product category."),
            FieldSpec("currency", "string", "TEXT NOT NULL", True, "USD", "ISO-4217", "NON-UNIQUE", "Equals 'USD'", "Account settlement currency."),
            FieldSpec("status", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["account_status"]), "none", "NON-UNIQUE", "Matches latest AccountStateEvent.new_status", "Latest derived account lifecycle state."),
            FieldSpec("overdraft_allowed", "boolean", "INTEGER NOT NULL", True, "0 | 1", "flag (0/1)", "NON-UNIQUE", "In {0, 1}", "Whether negative balance up to overdraft_limit is permitted."),
            FieldSpec("overdraft_limit", "decimal(14,2)", "REAL NOT NULL", True, ">= 0.00", "USD", "NON-UNIQUE", "0.00 if overdraft_allowed=0 else > 0", "Maximum permitted negative balance."),
            FieldSpec("opening_balance", "decimal(14,2)", "REAL NOT NULL", True, ">= 0.00", "USD", "NON-UNIQUE", "opening_balance >= 0", "Initial funded balance at account opening."),
            FieldSpec("current_balance", "decimal(14,2)", "REAL NOT NULL", True, "Derived from ledger", "USD", "NON-UNIQUE", "Equals opening_balance + sum(posted signed txns)", "Reconciled ending balance."),
            FieldSpec("opened_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "opened_at >= primary customer created_at", "Account opening timestamp."),
            FieldSpec("closed_at", "datetime", "TEXT", False, "UTC ISO-8601 or NULL", "UTC ISO-8601", "NON-UNIQUE", "NULL unless status='CLOSED'; closed_at >= opened_at", "Optional closure timestamp."),
        ],
    ),
    TableSpec(
        entity_name="AccountOwnership",
        table_name="account_ownerships",
        category="Bridge",
        primary_key="ownership_id",
        id_pattern=r"^OWN-\d{6}$",
        relationships=[
            "Bridge resolving N:M Customer <-> Account ownership with effective date range",
        ],
        lifecycle_states="Effective interval [effective_from, effective_to]",
        effective_date_fields="effective_from, effective_to (optional)",
        description="Many-to-many bridge linking customers to primary and joint accounts.",
        fields=[
            FieldSpec("ownership_id", "string", "TEXT PRIMARY KEY", True, "OWN-000001 ..", "none", "PRIMARY KEY", "Matches ^OWN-\\d{6}$", "Bridge primary key."),
            FieldSpec("account_id", "string", "TEXT NOT NULL", True, "Existing ACC-...", "none", "NON-UNIQUE", "FK -> accounts.account_id", "Owned account.", fk="accounts.account_id"),
            FieldSpec("customer_id", "string", "TEXT NOT NULL", True, "Existing CUS-...", "none", "NON-UNIQUE", "FK -> customers.customer_id", "Owning customer.", fk="customers.customer_id"),
            FieldSpec("ownership_role", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["ownership_role"]), "none", "NON-UNIQUE", "In allowed ownership_role enum", "Role of customer on the account."),
            FieldSpec("ownership_pct", "decimal(5,2)", "REAL NOT NULL", True, "0.00 .. 100.00", "percent", "NON-UNIQUE", "0 < ownership_pct <= 100", "Ownership share percentage."),
            FieldSpec("effective_from", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "effective_from >= account.opened_at", "Start of ownership relationship."),
            FieldSpec("effective_to", "datetime", "TEXT", False, "UTC ISO-8601 or NULL", "UTC ISO-8601", "NON-UNIQUE", "NULL or effective_to >= effective_from", "Optional end of ownership relationship."),
        ],
    ),
    TableSpec(
        entity_name="Merchant",
        table_name="merchants",
        category="Master",
        primary_key="merchant_id",
        id_pattern=r"^MER-\d{6}$",
        relationships=[
            "Merchant 1:N Transaction (optional; only merchant-facing purchases)",
        ],
        lifecycle_states="Static master reference with risk_tier",
        effective_date_fields="registered_at",
        description="Synthetic merchant directory with MCC codes, geography, and risk tiers.",
        fields=[
            FieldSpec("merchant_id", "string", "TEXT PRIMARY KEY", True, "MER-000001 ..", "none", "PRIMARY KEY", "Matches ^MER-\\d{6}$", "Immutable deterministic merchant identifier."),
            FieldSpec("merchant_name", "string", "TEXT NOT NULL", True, "Non-empty synthetic name", "none", "NON-UNIQUE", "Length 2..120", "Synthetic merchant DBA name."),
            FieldSpec("mcc", "string", "TEXT NOT NULL", True, "4-digit MCC string", "MCC", "NON-UNIQUE", "Matches ^\\d{4}$", "Merchant Category Code."),
            FieldSpec("category", "string", "TEXT NOT NULL", True, "GROCERY | UTILITIES | TRAVEL | RETAIL | ELECTRONICS | CRYPTO_EXCHANGE | GAMING | LUXURY | EDUCATION | HEALTHCARE", "none", "NON-UNIQUE", "Non-empty category", "Human-readable merchant sector."),
            FieldSpec("country", "string", "TEXT NOT NULL", True, "ISO-3166 alpha-2", "country code", "NON-UNIQUE", "2 uppercase ASCII letters", "Merchant settlement jurisdiction."),
            FieldSpec("risk_tier", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["merchant_risk_tier"]), "none", "NON-UNIQUE", "In allowed merchant_risk_tier enum", "Inherent merchant AML/fraud risk tier."),
            FieldSpec("is_high_risk_mcc", "boolean", "INTEGER NOT NULL", True, "0 | 1", "flag (0/1)", "NON-UNIQUE", "In {0, 1}", "Flag for elevated-risk MCC sectors (crypto, gaming, luxury)."),
            FieldSpec("registered_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Valid ISO-8601", "Merchant onboarding timestamp."),
        ],
    ),
    TableSpec(
        entity_name="Device",
        table_name="devices",
        category="Master",
        primary_key="device_id",
        id_pattern=r"^DEV-\d{6}$",
        relationships=[
            "Device N:M Account via AccountDeviceLink",
            "Device 1:N Transaction (optional; digital channel transactions)",
        ],
        lifecycle_states="Active fingerprint with emulator/VPN risk attributes",
        effective_date_fields="first_observed_at",
        description="Endpoint device fingerprint catalog used to detect new-device and shared-mule-device rings.",
        fields=[
            FieldSpec("device_id", "string", "TEXT PRIMARY KEY", True, "DEV-000001 ..", "none", "PRIMARY KEY", "Matches ^DEV-\\d{6}$", "Immutable deterministic device identifier."),
            FieldSpec("device_fingerprint", "string", "TEXT NOT NULL", True, "32-char hex digest", "none", "UNIQUE", "Matches ^[a-f0-9]{32}$", "Unique deterministic hardware/browser fingerprint."),
            FieldSpec("os_family", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["device_os"]), "none", "NON-UNIQUE", "In allowed device_os enum", "Operating system family."),
            FieldSpec("is_emulator", "boolean", "INTEGER NOT NULL", True, "0 | 1", "flag (0/1)", "NON-UNIQUE", "In {0, 1}", "True if virtualized/emulator environment detected."),
            FieldSpec("ip_country", "string", "TEXT NOT NULL", True, "ISO-3166 alpha-2", "country code", "NON-UNIQUE", "2 uppercase ASCII letters", "Primary observed IP country."),
            FieldSpec("risk_tier", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["device_risk_tier"]), "none", "NON-UNIQUE", "In allowed device_risk_tier enum", "Baseline device risk classification."),
            FieldSpec("first_observed_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Valid ISO-8601", "First global sighting of device."),
        ],
    ),
    TableSpec(
        entity_name="AccountDeviceLink",
        table_name="account_device_links",
        category="Bridge",
        primary_key="link_id",
        id_pattern=r"^ADL-\d{6}$",
        relationships=[
            "Bridge resolving N:M Account <-> Device bindings",
        ],
        lifecycle_states="TRUSTED | UNVERIFIED | FLAGGED_SHARED",
        effective_date_fields="first_seen_at, last_seen_at",
        description="Many-to-many association tracking when each device was bound to or used on each account.",
        fields=[
            FieldSpec("link_id", "string", "TEXT PRIMARY KEY", True, "ADL-000001 ..", "none", "PRIMARY KEY", "Matches ^ADL-\\d{6}$", "Bridge primary key."),
            FieldSpec("account_id", "string", "TEXT NOT NULL", True, "Existing ACC-...", "none", "NON-UNIQUE", "FK -> accounts.account_id", "Associated account.", fk="accounts.account_id"),
            FieldSpec("device_id", "string", "TEXT NOT NULL", True, "Existing DEV-...", "none", "NON-UNIQUE", "FK -> devices.device_id", "Associated device.", fk="devices.device_id"),
            FieldSpec("first_seen_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "first_seen_at >= account.opened_at", "First usage timestamp on this account."),
            FieldSpec("last_seen_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "last_seen_at >= first_seen_at", "Most recent usage timestamp on this account."),
            FieldSpec("is_trusted", "boolean", "INTEGER NOT NULL", True, "0 | 1", "flag (0/1)", "NON-UNIQUE", "In {0, 1}", "Whether device completed MFA / long-standing trust."),
        ],
    ),
    TableSpec(
        entity_name="AccountStateEvent",
        table_name="account_state_events",
        category="History",
        primary_key="event_id",
        id_pattern=r"^ASE-2026-\d{6}$",
        relationships=[
            "Account 1:N AccountStateEvent (append-only state transitions)",
        ],
        lifecycle_states="OPENED(NULL)->ACTIVE, ACTIVE->DORMANT, DORMANT->ACTIVE, ACTIVE->CLOSED",
        effective_date_fields="effective_at",
        description="Immutable append-only audit log of account lifecycle state changes.",
        fields=[
            FieldSpec("event_id", "string", "TEXT PRIMARY KEY", True, "ASE-2026-000001 ..", "none", "PRIMARY KEY", "Matches ^ASE-2026-\\d{6}$", "Immutable state event ID."),
            FieldSpec("account_id", "string", "TEXT NOT NULL", True, "Existing ACC-...", "none", "NON-UNIQUE", "FK -> accounts.account_id", "Target account.", fk="accounts.account_id"),
            FieldSpec("prev_status", "enum", "TEXT", False, "NULL | " + " | ".join(ENUMS["account_status"]), "none", "NON-UNIQUE", "NULL on initial opening else valid account_status", "Status prior to transition."),
            FieldSpec("new_status", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["account_status"]), "none", "NON-UNIQUE", "In allowed account_status enum", "Status after transition."),
            FieldSpec("effective_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Monotonic per account", "Timestamp transition became effective."),
            FieldSpec("reason", "string", "TEXT NOT NULL", True, "ACCOUNT_OPENING | INACTIVITY_90D | REACTIVATION_ACTIVITY | CUSTOMER_CLOSURE | RISK_FREEZE", "none", "NON-UNIQUE", "Non-empty reason code", "Business reason for transition."),
            FieldSpec("actor_id", "string", "TEXT NOT NULL", True, "SYSTEM | CUS-... | ADM-...", "none", "NON-UNIQUE", "Non-empty actor", "System or user executing transition."),
        ],
    ),
    TableSpec(
        entity_name="Transaction",
        table_name="transactions",
        category="Ledger",
        primary_key="transaction_id",
        id_pattern=r"^TXN-2026-\d{8}$",
        relationships=[
            "Transaction N:1 Account (mandatory)",
            "Transaction N:1 Merchant (optional; NULL for transfers/ATM/payroll)",
            "Transaction N:1 Device (optional; NULL for branch/ATM/ACH batch)",
            "Transaction 1:1 TransferLink leg (optional; for paired transfers)",
            "Transaction N:M Alert via AlertTriggerFact",
        ],
        lifecycle_states="POSTED | REVERSED | FAILED",
        effective_date_fields="occurred_at",
        description="Timestamped financial ledger event with reconciled before/after balances.",
        fields=[
            FieldSpec("transaction_id", "string", "TEXT PRIMARY KEY", True, "TXN-2026-00000001 ..", "none", "PRIMARY KEY", "Matches ^TXN-2026-\\d{8}$", "Immutable deterministic transaction identifier."),
            FieldSpec("account_id", "string", "TEXT NOT NULL", True, "Existing ACC-...", "none", "NON-UNIQUE", "FK -> accounts.account_id", "Ledger account impacted.", fk="accounts.account_id"),
            FieldSpec("txn_type", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["txn_type"]), "none", "NON-UNIQUE", "In allowed txn_type enum", "Transaction classification."),
            FieldSpec("direction", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["txn_direction"]), "none", "NON-UNIQUE", "DEBIT or CREDIT", "Balance direction."),
            FieldSpec("amount", "decimal(14,2)", "REAL NOT NULL", True, "> 0.00", "USD", "NON-UNIQUE", "amount > 0", "Unsigned transaction amount."),
            FieldSpec("currency", "string", "TEXT NOT NULL", True, "USD", "ISO-4217", "NON-UNIQUE", "Equals 'USD'", "Transaction currency."),
            FieldSpec("balance_before", "decimal(14,2)", "REAL NOT NULL", True, "Derived running balance", "USD", "NON-UNIQUE", "Matches prior transaction balance_after", "Account balance immediately before transaction."),
            FieldSpec("balance_after", "decimal(14,2)", "REAL NOT NULL", True, "Derived running balance", "USD", "NON-UNIQUE", "balance_before + signed_amount (if POSTED)", "Account balance immediately after transaction."),
            FieldSpec("channel", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["txn_channel"]), "none", "NON-UNIQUE", "In allowed txn_channel enum", "Origination channel."),
            FieldSpec("merchant_id", "string", "TEXT", False, "Existing MER-... or NULL", "none", "NON-UNIQUE", "NULL or FK -> merchants.merchant_id", "Optional counterparty merchant.", fk="merchants.merchant_id"),
            FieldSpec("device_id", "string", "TEXT", False, "Existing DEV-... or NULL", "none", "NON-UNIQUE", "NULL or FK -> devices.device_id", "Optional originating device.", fk="devices.device_id"),
            FieldSpec("counterparty_country", "string", "TEXT NOT NULL", True, "ISO-3166 alpha-2", "country code", "NON-UNIQUE", "2 uppercase ASCII letters", "Jurisdiction of counterparty/terminal."),
            FieldSpec("status", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["txn_status"]), "none", "NON-UNIQUE", "In allowed txn_status enum", "Posting status."),
            FieldSpec("occurred_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "occurred_at >= account.opened_at", "Exact transaction UTC timestamp."),
            FieldSpec("reference_note", "string", "TEXT NOT NULL", True, "Descriptive synthetic memo", "none", "NON-UNIQUE", "Non-empty memo", "Transaction memo / narrative."),
        ],
    ),
    TableSpec(
        entity_name="TransferLink",
        table_name="transfer_links",
        category="Ledger",
        primary_key="transfer_id",
        id_pattern=r"^TRL-2026-\d{6}$",
        relationships=[
            "TransferLink N:1 source Account & debit Transaction",
            "TransferLink N:1 dest Account & optional credit Transaction (NULL only on injected incomplete-leg exception)",
        ],
        lifecycle_states="SETTLED | MISMATCHED | INCOMPLETE",
        effective_date_fields="initiated_at, settled_at (optional)",
        description="Explicit double-entry transfer bridge pairing outbound debit and inbound credit legs.",
        fields=[
            FieldSpec("transfer_id", "string", "TEXT PRIMARY KEY", True, "TRL-2026-000001 ..", "none", "PRIMARY KEY", "Matches ^TRL-2026-\\d{6}$", "Immutable transfer link ID."),
            FieldSpec("debit_txn_id", "string", "TEXT NOT NULL", True, "Existing TXN-...", "none", "UNIQUE", "FK -> transactions.transaction_id (DEBIT)", "Outbound debit transaction leg.", fk="transactions.transaction_id"),
            FieldSpec("credit_txn_id", "string", "TEXT", False, "Existing TXN-... or NULL", "none", "NON-UNIQUE", "NULL only on INCOMPLETE exception; else FK -> transactions.transaction_id (CREDIT)", "Inbound credit transaction leg.", fk="transactions.transaction_id"),
            FieldSpec("source_account_id", "string", "TEXT NOT NULL", True, "Existing ACC-...", "none", "NON-UNIQUE", "FK -> accounts.account_id", "Originating account.", fk="accounts.account_id"),
            FieldSpec("dest_account_id", "string", "TEXT NOT NULL", True, "Existing ACC-...", "none", "NON-UNIQUE", "FK -> accounts.account_id; != source_account_id", "Receiving account.", fk="accounts.account_id"),
            FieldSpec("transfer_amount", "decimal(14,2)", "REAL NOT NULL", True, "> 0.00", "USD", "NON-UNIQUE", "Equals debit_txn.amount and credit_txn.amount when SETTLED", "Expected transfer principal."),
            FieldSpec("is_same_customer", "boolean", "INTEGER NOT NULL", True, "0 | 1", "flag (0/1)", "NON-UNIQUE", "In {0, 1}", "Derived indicator: source and dest share an owner."),
            FieldSpec("status", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["transfer_status"]), "none", "NON-UNIQUE", "In allowed transfer_status enum", "Reconciliation status of transfer pair."),
            FieldSpec("initiated_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Equals debit_txn.occurred_at", "Transfer initiation timestamp."),
            FieldSpec("settled_at", "datetime", "TEXT", False, "UTC ISO-8601 or NULL", "UTC ISO-8601", "NON-UNIQUE", "settled_at >= initiated_at when present", "Transfer settlement timestamp."),
        ],
    ),
    TableSpec(
        entity_name="RiskRule",
        table_name="risk_rules",
        category="Rule",
        primary_key="rule_id",
        id_pattern=r"^RULE-\d{3}$",
        relationships=[
            "RiskRule 1:N Alert (transparent rule definition powering each alert)",
            "RiskRule 1:N AlertTriggerFact",
        ],
        lifecycle_states="ACTIVE | RETIRED (versioned)",
        effective_date_fields="effective_from",
        description="Transparent, versioned AML/fraud detection rules with explicit thresholds and priority weights.",
        fields=[
            FieldSpec("rule_id", "string", "TEXT PRIMARY KEY", True, "RULE-001 .. RULE-999", "none", "PRIMARY KEY", "Matches ^RULE-\\d{3}$", "Rule identifier."),
            FieldSpec("rule_name", "string", "TEXT NOT NULL", True, "Non-empty name", "none", "UNIQUE", "Length 3..100", "Human-readable rule title."),
            FieldSpec("category", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["rule_category"]), "none", "NON-UNIQUE", "In allowed rule_category enum", "Detection typology family."),
            FieldSpec("severity", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["severity"]), "none", "NON-UNIQUE", "In allowed severity enum", "Default severity tier."),
            FieldSpec("base_weight", "integer", "INTEGER NOT NULL", True, "1 .. 100", "points", "NON-UNIQUE", "1 <= base_weight <= 100", "Base priority score weight."),
            FieldSpec("threshold_desc", "string", "TEXT NOT NULL", True, "Explicit formula/threshold", "none", "NON-UNIQUE", "Non-empty", "Transparent threshold specification."),
            FieldSpec("is_active", "boolean", "INTEGER NOT NULL", True, "0 | 1", "flag (0/1)", "NON-UNIQUE", "In {0, 1}", "Whether rule is active."),
            FieldSpec("version", "string", "TEXT NOT NULL", True, "v1.0 ..", "none", "NON-UNIQUE", "Semver-like string", "Rule version."),
            FieldSpec("effective_from", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Valid ISO-8601", "Rule activation timestamp."),
        ],
    ),
    TableSpec(
        entity_name="Alert",
        table_name="alerts",
        category="Detection",
        primary_key="alert_id",
        id_pattern=r"^ALT-2026-\d{6}$",
        relationships=[
            "Alert N:1 RiskRule",
            "Alert N:1 Account & N:1 Customer",
            "Alert N:1 triggering Transaction (optional ONLY for injected orphan-alert edge case)",
            "Alert N:M Transaction/TransferLink via AlertTriggerFact",
            "Alert N:M Case via CaseAlertLink",
        ],
        lifecycle_states="OPEN -> GROUPED -> RESOLVED | DISMISSED",
        effective_date_fields="created_at",
        description="Rule-generated risk alert with explainable score and traceability to triggering facts.",
        fields=[
            FieldSpec("alert_id", "string", "TEXT PRIMARY KEY", True, "ALT-2026-000001 ..", "none", "PRIMARY KEY", "Matches ^ALT-2026-\\d{6}$", "Immutable deterministic alert identifier."),
            FieldSpec("rule_id", "string", "TEXT NOT NULL", True, "Existing RULE-XXX", "none", "NON-UNIQUE", "FK -> risk_rules.rule_id", "Rule that fired.", fk="risk_rules.rule_id"),
            FieldSpec("account_id", "string", "TEXT NOT NULL", True, "Existing ACC-...", "none", "NON-UNIQUE", "FK -> accounts.account_id", "Subject account.", fk="accounts.account_id"),
            FieldSpec("customer_id", "string", "TEXT NOT NULL", True, "Existing CUS-...", "none", "NON-UNIQUE", "FK -> customers.customer_id", "Primary subject customer.", fk="customers.customer_id"),
            FieldSpec("primary_txn_id", "string", "TEXT", False, "Existing TXN-... or NULL", "none", "NON-UNIQUE", "NULL only on ORPHAN_ALERT_NO_TRIGGER exception; else FK -> transactions.transaction_id", "Anchor triggering transaction.", fk="transactions.transaction_id"),
            FieldSpec("severity", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["severity"]), "none", "NON-UNIQUE", "In allowed severity enum", "Alert severity level."),
            FieldSpec("risk_score", "decimal(5,2)", "REAL NOT NULL", True, "0.00 .. 100.00", "points (0-100)", "NON-UNIQUE", "0 <= risk_score <= 100", "Derived explainable alert score."),
            FieldSpec("trigger_txn_count", "integer", "INTEGER NOT NULL", True, ">= 0", "count", "NON-UNIQUE", "Matches count of AlertTriggerFact rows", "Number of supporting transactions."),
            FieldSpec("trigger_total_amount", "decimal(14,2)", "REAL NOT NULL", True, ">= 0.00", "USD", "NON-UNIQUE", "Derived sum of triggering exposure", "Total dollar volume tied to alert."),
            FieldSpec("explanation_summary", "string", "TEXT NOT NULL", True, "Transparent reason string", "none", "NON-UNIQUE", "Non-empty explanation", "Human-readable explanation of rule trigger."),
            FieldSpec("status", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["alert_status"]), "none", "NON-UNIQUE", "In allowed alert_status enum", "Current alert lifecycle state."),
            FieldSpec("created_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "created_at >= primary_txn.occurred_at when present", "Timestamp alert was generated."),
        ],
    ),
    TableSpec(
        entity_name="AlertTriggerFact",
        table_name="alert_trigger_facts",
        category="Bridge",
        primary_key="fact_id",
        id_pattern=r"^ATF-2026-\d{6}$",
        relationships=[
            "Bridge resolving N:M Alert <-> Transaction (and optional TransferLink) with exact metrics",
        ],
        lifecycle_states="Immutable evidence record",
        effective_date_fields="recorded_at",
        description="Fact-level audit bridge linking every alert to the exact transactions and quantitative thresholds that triggered it.",
        fields=[
            FieldSpec("fact_id", "string", "TEXT PRIMARY KEY", True, "ATF-2026-000001 ..", "none", "PRIMARY KEY", "Matches ^ATF-2026-\\d{6}$", "Bridge primary key."),
            FieldSpec("alert_id", "string", "TEXT NOT NULL", True, "Existing ALT-...", "none", "NON-UNIQUE", "FK -> alerts.alert_id", "Parent alert.", fk="alerts.alert_id"),
            FieldSpec("transaction_id", "string", "TEXT NOT NULL", True, "Existing TXN-...", "none", "NON-UNIQUE", "FK -> transactions.transaction_id", "Supporting transaction.", fk="transactions.transaction_id"),
            FieldSpec("transfer_id", "string", "TEXT", False, "Existing TRL-... or NULL", "none", "NON-UNIQUE", "NULL or FK -> transfer_links.transfer_id", "Optional supporting transfer link.", fk="transfer_links.transfer_id"),
            FieldSpec("rule_id", "string", "TEXT NOT NULL", True, "Existing RULE-...", "none", "NON-UNIQUE", "FK -> risk_rules.rule_id", "Rule evaluated.", fk="risk_rules.rule_id"),
            FieldSpec("metric_name", "string", "TEXT NOT NULL", True, "window_txn_count | device_age_hours | cycle_return_ratio | dormancy_days | ...", "none", "NON-UNIQUE", "Non-empty", "Quantitative indicator measured."),
            FieldSpec("observed_value", "string", "TEXT NOT NULL", True, "Numeric or descriptor", "mixed", "NON-UNIQUE", "Non-empty", "Measured value that breached threshold."),
            FieldSpec("threshold_value", "string", "TEXT NOT NULL", True, "Numeric or descriptor", "mixed", "NON-UNIQUE", "Non-empty", "Rule threshold exceeded."),
            FieldSpec("recorded_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Equals alert.created_at", "Fact capture timestamp."),
        ],
    ),
    TableSpec(
        entity_name="Case",
        table_name="cases",
        category="Triage",
        primary_key="case_id",
        id_pattern=r"^CASE-2026-\d{6}$",
        relationships=[
            "Case N:M Alert via CaseAlertLink",
            "Case 1:N CaseStateEvent (append-only lifecycle history)",
            "Case 1:N AnalystAction (append-only analyst decisions)",
        ],
        lifecycle_states="OPEN -> IN_REVIEW -> ESCALATED | SAR_FILED | CLOSED_CONFIRMED_FRAUD | CLOSED_FALSE_POSITIVE",
        effective_date_fields="created_at, updated_at",
        description="Grouped investigation dossier aggregating linked alerts, accounts, and explainable priority score.",
        fields=[
            FieldSpec("case_id", "string", "TEXT PRIMARY KEY", True, "CASE-2026-000001 ..", "none", "PRIMARY KEY", "Matches ^CASE-2026-\\d{6}$", "Immutable deterministic case identifier."),
            FieldSpec("primary_account_id", "string", "TEXT NOT NULL", True, "Existing ACC-...", "none", "NON-UNIQUE", "FK -> accounts.account_id", "Highest-exposure anchor account.", fk="accounts.account_id"),
            FieldSpec("primary_customer_id", "string", "TEXT NOT NULL", True, "Existing CUS-...", "none", "NON-UNIQUE", "FK -> customers.customer_id", "Anchor customer.", fk="customers.customer_id"),
            FieldSpec("linkage_summary", "string", "TEXT NOT NULL", True, " | ".join(ENUMS["linkage_reason"]), "none", "NON-UNIQUE", "Non-empty linkage descriptor", "Primary graph reason alerts were clustered."),
            FieldSpec("linked_account_count", "integer", "INTEGER NOT NULL", True, ">= 1", "count", "NON-UNIQUE", "Derived distinct accounts in linked alerts/transfers", "Blast-radius account count."),
            FieldSpec("alert_count", "integer", "INTEGER NOT NULL", True, ">= 1", "count", "NON-UNIQUE", "Equals count of CaseAlertLink rows", "Number of alerts grouped into case."),
            FieldSpec("total_exposure_amount", "decimal(14,2)", "REAL NOT NULL", True, ">= 0.00", "USD", "NON-UNIQUE", "Derived exposure across linked alerts", "Total dollar exposure under review."),
            FieldSpec("priority_score", "decimal(5,2)", "REAL NOT NULL", True, "0.00 .. 100.00", "points (0-100)", "NON-UNIQUE", "0 <= priority_score <= 100", "Transparent composite priority score."),
            FieldSpec("priority_tier", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["severity"]), "none", "NON-UNIQUE", "CRITICAL>=80, HIGH>=60, MEDIUM>=40, LOW<40", "Derived queue priority tier."),
            FieldSpec("status", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["case_status"]), "none", "NON-UNIQUE", "Matches latest CaseStateEvent.new_status", "Current case workflow status."),
            FieldSpec("created_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Equals min(linked alert created_at)", "Case opening timestamp."),
            FieldSpec("updated_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "updated_at >= created_at", "Latest event timestamp."),
        ],
    ),
    TableSpec(
        entity_name="CaseAlertLink",
        table_name="case_alert_links",
        category="Bridge",
        primary_key="case_alert_id",
        id_pattern=r"^CAL-2026-\d{6}$",
        relationships=[
            "Bridge resolving N:M Case <-> Alert clustering",
        ],
        lifecycle_states="Immutable clustering link",
        effective_date_fields="linked_at",
        description="Bridge linking individual alerts into multi-account or multi-rule investigation cases.",
        fields=[
            FieldSpec("case_alert_id", "string", "TEXT PRIMARY KEY", True, "CAL-2026-000001 ..", "none", "PRIMARY KEY", "Matches ^CAL-2026-\\d{6}$", "Bridge primary key."),
            FieldSpec("case_id", "string", "TEXT NOT NULL", True, "Existing CASE-...", "none", "NON-UNIQUE", "FK -> cases.case_id", "Parent case.", fk="cases.case_id"),
            FieldSpec("alert_id", "string", "TEXT NOT NULL", True, "Existing ALT-...", "none", "UNIQUE", "FK -> alerts.alert_id", "Grouped alert.", fk="alerts.alert_id"),
            FieldSpec("linkage_reason", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["linkage_reason"]), "none", "NON-UNIQUE", "In allowed linkage_reason enum", "Reason alert belongs to this case."),
            FieldSpec("linkage_key", "string", "TEXT NOT NULL", True, "Account/Device/Ring ID", "none", "NON-UNIQUE", "Non-empty", "Graph key connecting the alert."),
            FieldSpec("linked_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "linked_at >= alert.created_at", "Timestamp alert was linked to case."),
        ],
    ),
    TableSpec(
        entity_name="AnalystAction",
        table_name="analyst_actions",
        category="Workflow",
        primary_key="action_id",
        id_pattern=r"^ACT-2026-\d{6}$",
        relationships=[
            "AnalystAction N:1 Case",
            "AnalystAction 1:0..1 CaseStateEvent",
        ],
        lifecycle_states="Append-only immutable action log",
        effective_date_fields="acted_at",
        description="Immutable record of operations analyst and compliance reviewer triage actions and dispositions.",
        fields=[
            FieldSpec("action_id", "string", "TEXT PRIMARY KEY", True, "ACT-2026-000001 ..", "none", "PRIMARY KEY", "Matches ^ACT-2026-\\d{6}$", "Immutable action identifier."),
            FieldSpec("case_id", "string", "TEXT NOT NULL", True, "Existing CASE-...", "none", "NON-UNIQUE", "FK -> cases.case_id", "Reviewed case.", fk="cases.case_id"),
            FieldSpec("analyst_id", "string", "TEXT NOT NULL", True, "ANL-001 .. ANL-999", "none", "NON-UNIQUE", "Matches ^ANL-\\d{3}$", "Reviewer identifier."),
            FieldSpec("analyst_role", "enum", "TEXT NOT NULL", True, "OPS_ANALYST | RISK_REVIEWER | COMPLIANCE_OFFICER", "none", "NON-UNIQUE", "In allowed analyst role enum", "Actor role."),
            FieldSpec("action_type", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["analyst_action_type"]), "none", "NON-UNIQUE", "In allowed analyst_action_type enum", "Action or disposition executed."),
            FieldSpec("rationale", "string", "TEXT NOT NULL", True, "Structured review note", "none", "NON-UNIQUE", "Non-empty rationale", "Documented analyst justification."),
            FieldSpec("acted_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "acted_at >= max(linked alert created_at) unless negative edge case", "Timestamp analyst submitted action."),
        ],
    ),
    TableSpec(
        entity_name="CaseStateEvent",
        table_name="case_state_events",
        category="History",
        primary_key="case_event_id",
        id_pattern=r"^CSE-2026-\d{6}$",
        relationships=[
            "Case 1:N CaseStateEvent (append-only status transition audit log)",
            "CaseStateEvent N:0..1 AnalystAction",
        ],
        lifecycle_states="OPEN -> IN_REVIEW -> ESCALATED | SAR_FILED | CLOSED_*",
        effective_date_fields="effective_at",
        description="Immutable append-only audit trail of every case status transition.",
        fields=[
            FieldSpec("case_event_id", "string", "TEXT PRIMARY KEY", True, "CSE-2026-000001 ..", "none", "PRIMARY KEY", "Matches ^CSE-2026-\\d{6}$", "Immutable case state event ID."),
            FieldSpec("case_id", "string", "TEXT NOT NULL", True, "Existing CASE-...", "none", "NON-UNIQUE", "FK -> cases.case_id", "Target case.", fk="cases.case_id"),
            FieldSpec("prev_status", "enum", "TEXT", False, "NULL | " + " | ".join(ENUMS["case_status"]), "none", "NON-UNIQUE", "NULL on case creation else valid case_status", "Prior case status."),
            FieldSpec("new_status", "enum", "TEXT NOT NULL", True, " | ".join(ENUMS["case_status"]), "none", "NON-UNIQUE", "In allowed case_status enum", "Resulting case status."),
            FieldSpec("analyst_action_id", "string", "TEXT", False, "Existing ACT-... or NULL", "none", "NON-UNIQUE", "NULL on system open else FK -> analyst_actions.action_id", "Triggering analyst action.", fk="analyst_actions.action_id"),
            FieldSpec("effective_at", "datetime", "TEXT NOT NULL", True, "UTC ISO-8601", "UTC ISO-8601", "NON-UNIQUE", "Monotonic per case", "Transition timestamp."),
        ],
    ),
]


def build_schema_sql() -> str:
    """Render DDL for SQLite/ANSI-compatible relational schema."""
    lines = [
        "-- YottaFlex Relational Schema (v1.0.0)",
        "-- Enforces primary keys, foreign keys, and structural integrity.",
        "PRAGMA foreign_keys = ON;",
        "",
    ]
    for tbl in TABLES:
        lines.append(f"DROP TABLE IF EXISTS {tbl.table_name};")
    lines.append("")

    for tbl in TABLES:
        lines.append(f"-- {tbl.entity_name}: {tbl.description}")
        lines.append(f"CREATE TABLE {tbl.table_name} (")
        col_defs: list[str] = []
        fks: list[str] = []
        for f in tbl.fields:
            col_defs.append(f"    {f.name} {f.sql_type}")
            if f.fk:
                ref_table, ref_col = f.fk.split(".")
                fks.append(f"    FOREIGN KEY ({f.name}) REFERENCES {ref_table}({ref_col})")
        lines.append(",\n".join(col_defs + fks))
        lines.append(");")
        lines.append("")

    # Useful analytical indexes
    lines.extend([
        "CREATE INDEX idx_transactions_account_time ON transactions(account_id, occurred_at);",
        "CREATE INDEX idx_transactions_device ON transactions(device_id);",
        "CREATE INDEX idx_transfer_links_src_dst ON transfer_links(source_account_id, dest_account_id);",
        "CREATE INDEX idx_alerts_account ON alerts(account_id);",
        "CREATE INDEX idx_alert_facts_alert ON alert_trigger_facts(alert_id);",
        "CREATE INDEX idx_case_alerts_case ON case_alert_links(case_id);",
        "CREATE INDEX idx_analyst_actions_case ON analyst_actions(case_id);",
        "",
    ])
    return "\n".join(lines)


def build_data_dictionary_json() -> dict[str, Any]:
    """Return structured JSON representation of the complete data dictionary."""
    return {
        "schema_version": SCHEMA_VERSION,
        "enums": ENUMS,
        "entities": [
            {
                "entity_name": t.entity_name,
                "table_name": t.table_name,
                "category": t.category,
                "primary_key": t.primary_key,
                "id_pattern": t.id_pattern,
                "relationships": t.relationships,
                "lifecycle_states": t.lifecycle_states,
                "effective_date_fields": t.effective_date_fields,
                "description": t.description,
                "fields": [asdict(f) for f in t.fields],
            }
            for t in TABLES
        ],
        "ground_truth_isolation_policy": {
            "files": ["ground_truth.csv", "ground_truth.json"],
            "rule": "Strictly isolated from model/rule scoring inputs; used solely by the evaluation harness and integrity audit comparison.",
            "fields": [
                {"name": "scenario_id", "type": "string", "description": "Unique planted scenario or edge-case identifier"},
                {"name": "entity_type", "type": "string", "description": "Primary entity type (CASE, ALERT, TRANSACTION, TRANSFER_LINK)"},
                {"name": "entity_id", "type": "string", "description": "ID of affected entity"},
                {"name": "typology", "type": "string", "description": "Planted pattern: NORMAL | VELOCITY_SPIKE | NEW_DEVICE | CIRCULAR_TRANSFER | DORMANT_REACTIVATION | FALSE_POSITIVE | NEGATIVE_EDGE_CASE"},
                {"name": "issue_type", "type": "string", "description": "NONE or exact negative scenario code (TXN_ON_CLOSED_ACCOUNT, NEGATIVE_BALANCE_NO_OVERDRAFT, UNRECONCILED_TRANSFER_LEG, ORPHAN_ALERT_NO_TRIGGER, DISPOSITION_PRECEDES_ALERT)"},
                {"name": "is_true_positive_risk", "type": "boolean", "description": "True if genuinely suspicious risk scenario, False for normal/false-positive"},
                {"name": "expected_decision", "type": "string", "description": "Expected analyst disposition or QUARANTINE_EXCEPTION"},
                {"name": "notes", "type": "string", "description": "Human-readable audit provenance"},
            ],
        },
    }


def build_data_dictionary_markdown() -> str:
    """Render comprehensive Markdown Data Dictionary with ER diagram and field specs."""
    lines = [
        "# YottaFlex Relational Schema & Data Dictionary",
        "",
        f"**Schema Version:** `{SCHEMA_VERSION}`  ",
        "**Core Entities:** `Customer`, `Account`, `Merchant`, `Device`, `Transaction`, `TransferLink`, `RiskRule`, `Alert`, `Case`, `AnalystAction`  ",
        "**Bridge & Event History Tables:** `AccountOwnership`, `AccountDeviceLink`, `AccountStateEvent`, `AlertTriggerFact`, `CaseAlertLink`, `CaseStateEvent`  ",
        "",
        "## 1. Entity-Relationship Overview",
        "",
        "```mermaid",
        "erDiagram",
        "    CUSTOMER ||--o{ ACCOUNT_OWNERSHIP : holds",
        "    ACCOUNT ||--o{ ACCOUNT_OWNERSHIP : owned_via",
        "    ACCOUNT ||--o{ ACCOUNT_STATE_EVENT : transitions",
        "    ACCOUNT ||--o{ ACCOUNT_DEVICE_LINK : binds",
        "    DEVICE ||--o{ ACCOUNT_DEVICE_LINK : linked_to",
        "    ACCOUNT ||--o{ TRANSACTION : posts",
        "    MERCHANT ||--o{ TRANSACTION : settles",
        "    DEVICE ||--o{ TRANSACTION : originates",
        "    TRANSACTION ||--o| TRANSFER_LINK : debit_or_credit_leg",
        "    RISK_RULE ||--o{ ALERT : triggers",
        "    ACCOUNT ||--o{ ALERT : subject_of",
        "    ALERT ||--o{ ALERT_TRIGGER_FACT : evidenced_by",
        "    TRANSACTION ||--o{ ALERT_TRIGGER_FACT : cited_in",
        "    CASE ||--o{ CASE_ALERT_LINK : groups",
        "    ALERT ||--o| CASE_ALERT_LINK : assigned_to",
        "    CASE ||--o{ CASE_STATE_EVENT : history",
        "    CASE ||--o{ ANALYST_ACTION : reviewed_via",
        "```",
        "",
        "## 2. ID & Nomenclature Conventions",
        "",
        "| Entity | Pattern | Example |",
        "| :--- | :--- | :--- |",
        "| Customer | `CUS-000001` | `CUS-000042` |",
        "| Account | `ACC-<customer-id>-01` | `ACC-CUS-000042-01` |",
        "| Transaction | `TXN-2026-00000001` | `TXN-2026-00014250` |",
        "| TransferLink | `TRL-2026-000001` | `TRL-2026-000812` |",
        "| Alert | `ALT-2026-000001` | `ALT-2026-000319` |",
        "| Case | `CASE-2026-000001` | `CASE-2026-000105` |",
        "| AnalystAction | `ACT-2026-000001` | `ACT-2026-000088` |",
        "| Bridge / Events | `OWN-`, `ADL-`, `ASE-2026-`, `ATF-2026-`, `CAL-2026-`, `CSE-2026-` | `ASE-2026-000001` |",
        "",
        "## 3. Lifecycle State Machines",
        "",
        "- **Account:** `ACTIVE <-> DORMANT -> FROZEN -> CLOSED` (recorded immutably in `account_state_events`).",
        "- **Case:** `OPEN -> IN_REVIEW -> ESCALATED | SAR_FILED | CLOSED_CONFIRMED_FRAUD | CLOSED_FALSE_POSITIVE` (recorded immutably in `case_state_events`).",
        "",
        "## 4. Table-by-Table Data Dictionary",
        "",
    ]

    for tbl in TABLES:
        lines.append(f"### {tbl.entity_name} (`{tbl.table_name}`) — *{tbl.category}*")
        lines.append("")
        lines.append(f"{tbl.description}")
        lines.append("")
        lines.append(f"- **Primary Key:** `{tbl.primary_key}` (`{tbl.id_pattern}`)")
        lines.append(f"- **Lifecycle:** {tbl.lifecycle_states}")
        lines.append(f"- **Effective Dates:** `{tbl.effective_date_fields}`")
        lines.append("- **Relationships & Cardinality:**")
        for rel in tbl.relationships:
            lines.append(f"  - {rel}")
        lines.append("")
        lines.append("| Field | Type | Req | Allowed Values / Domain | Units | Uniqueness | Validation Rule | Description |")
        lines.append("| :--- | :--- | :---: | :--- | :--- | :--- | :--- | :--- |")
        for f in tbl.fields:
            req = "Yes" if f.required else "No"
            allowed = f.allowed_values.replace("|", "\\|")
            val = f.validation_rule.replace("|", "\\|")
            lines.append(
                f"| `{f.name}` | `{f.logical_type}` | {req} | {allowed} | {f.units} | {f.uniqueness} | {val} | {f.description} |"
            )
        lines.append("")

    lines.extend([
        "## 5. Isolated Ground Truth Specification (`ground_truth.csv` / `ground_truth.json`)",
        "",
        "> **Zero-Leakage Guarantee:** Ground truth files are stored outside the feature/scoring tables and are never read by the prioritization engine.",
        "",
        "| Field | Type | Description |",
        "| :--- | :--- | :--- |",
        "| `scenario_id` | `string` | Unique identifier for planted typology or negative edge scenario |",
        "| `entity_type` | `string` | `CASE`, `ALERT`, `TRANSACTION`, or `TRANSFER_LINK` |",
        "| `entity_id` | `string` | Exact immutable ID of the labeled entity |",
        "| `typology` | `string` | `NORMAL`, `VELOCITY_SPIKE`, `NEW_DEVICE`, `CIRCULAR_TRANSFER`, `DORMANT_REACTIVATION`, `FALSE_POSITIVE`, `NEGATIVE_EDGE_CASE` |",
        "| `issue_type` | `string` | `NONE` or `TXN_ON_CLOSED_ACCOUNT`, `NEGATIVE_BALANCE_NO_OVERDRAFT`, `UNRECONCILED_TRANSFER_LEG`, `ORPHAN_ALERT_NO_TRIGGER`, `DISPOSITION_PRECEDES_ALERT` |",
        "| `is_true_positive_risk` | `boolean` | `true` for planted true risk patterns, `false` for normal/false positives |",
        "| `expected_decision` | `string` | Expected analyst outcome or `QUARANTINE_EXCEPTION` |",
        "| `notes` | `string` | Detailed explanation of planted pattern or injected violation |",
        "",
    ])
    return "\n".join(lines)


def write_schema_artifacts(root_dir: Path) -> dict[str, Path]:
    """Write schema.sql, data_dictionary.json, and docs/data_dictionary.md."""
    schema_dir = root_dir / "schema"
    docs_dir = root_dir / "docs"
    schema_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    sql_path = schema_dir / "schema.sql"
    json_path = schema_dir / "data_dictionary.json"
    md_path = docs_dir / "data_dictionary.md"

    sql_path.write_text(build_schema_sql(), encoding="utf-8")
    json_path.write_text(json.dumps(build_data_dictionary_json(), indent=2) + "\n", encoding="utf-8")
    md_path.write_text(build_data_dictionary_markdown(), encoding="utf-8")

    return {"schema_sql": sql_path, "data_dictionary_json": json_path, "data_dictionary_md": md_path}
