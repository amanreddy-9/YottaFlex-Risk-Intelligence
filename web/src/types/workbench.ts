export type PriorityTier = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type UserRole = "OPS_ANALYST" | "RISK_REVIEWER" | "SYSTEM_ADMIN";

export interface WatchlistTagItem {
  tag_id: string;
  entity_type: "CUSTOMER" | "ACCOUNT";
  entity_id: string;
  tag: string;
  note: string;
  actor_id: string;
  created_at: string;
}

export interface AlertAuditEvent {
  event_id: string;
  alert_id: string;
  actor_id: string;
  event_type: string;
  prev_status: string | null;
  new_status: string | null;
  detail: string;
  created_at: string;
}

export interface CaseEvidenceChecklist {
  case_id: string;
  rules_reviewed: boolean;
  ledger_reconciled: boolean;
  network_verified: boolean;
  kyc_corroborated: boolean;
  notes: string;
  updated_by: string | null;
  updated_at: string | null;
}

export interface AuthUser {
  user_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  analyst_code: string;
  department: string;
  title: string;
  phone: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  permissions: string[];
  current_session_id?: string;
}

export interface AuthSessionItem {
  session_id: string;
  user_id: string;
  email: string;
  role: UserRole;
  client_ip: string;
  user_agent: string;
  created_at: string;
  expires_at: string;
  revoked: number;
}

export interface LoginHistoryItem {
  log_id: string;
  user_id: string | null;
  email: string;
  event_type: string;
  status: string;
  client_ip: string;
  user_agent: string;
  detail: string;
  occurred_at: string;
}

export interface OverviewData {
  seed: number;
  scale: string;
  schema_version: string;
  counts: {
    customers: number;
    accounts: number;
    merchants: number;
    devices: number;
    transactions: number;
    transfer_links: number;
    alerts: number;
    cases: number;
    pure_open_cases: number;
    under_investigation_cases: number;
    escalated_cases: number;
    open_cases: number;
    closed_cases: number;
    total_case_exposure: number;
  };
  alert_to_case_compression: number;
  tier_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  quarantine_count: number;
}

export interface DashboardData {
  filters: {
    start_date: string | null;
    end_date: string | null;
    period: string;
    risk_level: string;
    txn_type: string;
    status: string;
  };
  summary: {
    customers: number;
    accounts: number;
    merchants: number;
    devices: number;
    transactions: number;
    total_volume_usd: number;
    alerts: number;
    cases: number;
    high_risk_txns: number;
    medium_risk_txns: number;
    low_risk_txns: number;
    open_cases: number;
    under_investigation_cases: number;
    escalated_cases: number;
    closed_cases: number;
  };
  case_tier_distribution: Record<string, number>;
  volume_series: Array<{
    label: string;
    start_day: string;
    end_day: string;
    txn_count: number;
    volume_usd: number;
    suspicious_count: number;
  }>;
  rule_distribution: Array<{
    rule_id: string;
    rule_name: string;
    category: string;
    severity: PriorityTier;
    alert_count: number;
    avg_score: number;
  }>;
  recent_suspicious_txns: Array<{
    transaction_id: string;
    account_id: string;
    customer_id: string;
    customer_name: string;
    txn_type: string;
    direction: string;
    amount: number;
    channel: string;
    occurred_at: string;
    risk_score: number;
    risk_level: string;
    rule_id: string | null;
  }>;
  recent_alerts: Array<{
    alert_id: string;
    rule_id: string;
    rule_name: string;
    account_id: string;
    customer_id: string;
    severity: PriorityTier;
    risk_score: number;
    trigger_total_amount: number;
    created_at: string;
    status: string;
  }>;
  recent_case_events: Array<{
    id: string;
    case_id: string;
    prev_status: string | null;
    new_status: string;
    occurred_at: string;
    analyst_id: string | null;
    action_type: string | null;
    rationale: string | null;
  }>;
  top_risk_customers: Array<{
    customer_id: string;
    full_name: string;
    email: string;
    kyc_tier: string;
    risk_rating: string;
    case_count: number;
    max_priority_score: number;
    total_exposure: number;
  }>;
  top_risk_accounts: Array<{
    account_id: string;
    customer_id: string;
    customer_name: string;
    account_type: string;
    status: string;
    current_balance: number;
    alert_count: number;
    max_risk_score: number;
    alert_exposure: number;
  }>;
}

export interface CustomerListItem {
  customer_id: string;
  full_name: string;
  email: string;
  phone: string;
  segment: string;
  kyc_tier: string;
  kyc_verified_at: string;
  declared_annual_income: number;
  home_country: string;
  risk_rating: string;
  status: string;
  created_at: string;
  account_count: number;
  suspicious_account_count: number;
  total_balance: number;
  alert_count: number;
  case_count: number;
  max_case_score: number;
}

export interface CustomerProfile {
  customer: Omit<
    CustomerListItem,
    "account_count" | "suspicious_account_count" | "total_balance" | "alert_count" | "case_count" | "max_case_score"
  >;
  kyc_summary: {
    kyc_tier: string;
    kyc_verified_at: string;
    declared_annual_income: number;
    risk_rating: string;
    status: string;
  };
  customer_risk_score: number;
  customer_risk_level: string;
  suspicious_account_count: number;
  has_multiple_suspicious_accounts: boolean;
  risk_factors: Array<{ factor: string; points: number; detail: string }>;
  risk_level_timeline: Array<{
    timestamp: string;
    event: string;
    risk_score: number;
    risk_level: string;
    detail: string;
  }>;
  accounts: Array<{
    account_id: string;
    account_type: string;
    currency: string;
    status: string;
    overdraft_allowed: number;
    overdraft_limit: number;
    opening_balance: number;
    current_balance: number;
    opened_at: string;
    closed_at: string | null;
    ownership_role: string;
    ownership_pct: number;
    effective_from: string;
    last_activity_at: string | null;
    alert_count: number;
  }>;
  transactions: Array<{
    transaction_id: string;
    account_id: string;
    txn_type: string;
    direction: "DEBIT" | "CREDIT";
    amount: number;
    balance_before: number;
    balance_after: number;
    channel: string;
    merchant_id: string | null;
    merchant_name: string | null;
    device_id: string | null;
    occurred_at: string;
    status: string;
    reference_note: string;
    txn_risk_score: number;
  }>;
  alerts: Array<{
    alert_id: string;
    account_id: string;
    rule_id: string;
    rule_name: string;
    severity: PriorityTier;
    risk_score: number;
    explanation_summary: string;
    created_at: string;
    status: string;
  }>;
  cases: Array<{
    case_id: string;
    priority_score: number;
    priority_tier: PriorityTier;
    status: string;
    total_exposure_amount: number;
    created_at: string;
  }>;
  devices: Array<{
    device_id: string;
    os_family: string;
    is_emulator: number;
    ip_country: string;
    risk_tier: string;
    is_trusted: number;
    first_seen_at: string;
    last_seen_at: string;
    account_id: string;
  }>;
  watchlist_tags?: WatchlistTagItem[];
}

export interface AccountListItem {
  account_id: string;
  primary_customer_id: string;
  customer_name: string;
  kyc_tier: string;
  account_type: string;
  currency: string;
  status: string;
  overdraft_allowed: number;
  overdraft_limit: number;
  opening_balance: number;
  current_balance: number;
  opened_at: string;
  closed_at: string | null;
  last_activity_at: string | null;
  txn_count: number;
  alert_count: number;
  account_risk_score: number;
  is_dormant_reactivated: number;
}

export interface AccountDetail {
  account: {
    account_id: string;
    primary_customer_id: string;
    account_type: string;
    currency: string;
    status: string;
    overdraft_allowed: number;
    overdraft_limit: number;
    opening_balance: number;
    current_balance: number;
    opened_at: string;
    closed_at: string | null;
  };
  last_activity_at: string | null;
  account_risk_score: number;
  is_dormant_reactivated: boolean;
  holders: Array<{
    customer_id: string;
    full_name: string;
    email: string;
    phone: string;
    kyc_tier: string;
    segment: string;
    risk_rating: string;
    home_country: string;
    ownership_role: string;
    ownership_pct: number;
  }>;
  transactions: CustomerProfile["transactions"];
  total_transactions: number;
  transfers: Array<{
    transfer_id: string;
    debit_txn_id: string;
    credit_txn_id: string | null;
    source_account_id: string;
    dest_account_id: string;
    transfer_amount: number;
    status: string;
    initiated_at: string;
    settled_at: string | null;
    transfer_direction: "INCOMING" | "OUTGOING";
    counterparty_account_id: string;
  }>;
  linked_accounts: Array<{
    account_id: string;
    primary_customer_id: string;
    owner_name: string;
    account_type: string;
    status: string;
    current_balance: number;
    link_relation: string;
  }>;
  alerts: CustomerProfile["alerts"];
  lifecycle_events: Array<{
    event_id: string;
    prev_status: string | null;
    new_status: string;
    effective_at: string;
    reason: string;
    actor_id: string;
  }>;
}

export interface TransactionItem {
  transaction_id: string;
  account_id: string;
  customer_id: string;
  customer_name: string;
  txn_type: string;
  direction: "DEBIT" | "CREDIT";
  amount: number;
  currency: string;
  balance_before: number;
  balance_after: number;
  channel: string;
  merchant_id: string | null;
  merchant_name: string | null;
  merchant_category: string | null;
  device_id: string | null;
  counterparty_country: string;
  status: string;
  occurred_at: string;
  reference_note: string;
  risk_score: number;
  top_rule_id: string | null;
  triggered_rules: string[];
  pattern_flags: string[];
  has_validation_exception: boolean;
  risk_level: "HIGH" | "MEDIUM" | "LOW";
}

export interface RuleEvaluationItem {
  rule_id: string;
  rule_name: string;
  category: string;
  severity: PriorityTier;
  base_weight: number;
  threshold_desc: string;
  status: "TRIGGERED" | "PASSED" | "DISABLED";
  observed_metric: string;
  points_awarded: number;
}

export interface TransactionDetail {
  transaction: TransactionItem & {
    signed_amount: number;
    balance_delta: number;
    balance_reconciled: boolean;
    is_cross_border: boolean;
  };
  account: AccountDetail["account"];
  customer: CustomerListItem;
  merchant: {
    merchant_id: string;
    merchant_name: string;
    category: string;
    country: string;
    risk_tier: string;
    txn_count: number;
    avg_amount: number;
  } | null;
  device: {
    device_id: string;
    device_fingerprint: string;
    os_family: string;
    is_emulator: number;
    ip_country: string;
    risk_tier: string;
    first_observed_at: string;
    first_seen_at?: string;
    last_seen_at?: string;
    is_trusted?: number;
    shared_customer_count: number;
  } | null;
  transfer_link: {
    transfer_id: string;
    debit_txn_id: string;
    credit_txn_id: string | null;
    source_account_id: string;
    dest_account_id: string;
    source_owner_name: string;
    dest_owner_name: string;
    transfer_amount: number;
    is_same_customer: number;
    status: string;
    initiated_at: string;
    settled_at: string | null;
    debit_txn?: TransactionItem | null;
    credit_txn?: TransactionItem | null;
  } | null;
  linked_transfers: Array<{
    transfer_id: string;
    debit_txn_id: string;
    credit_txn_id: string | null;
    source_account_id: string;
    dest_account_id: string;
    source_owner_name: string;
    dest_owner_name: string;
    transfer_amount: number;
    status: string;
    initiated_at: string;
  }>;
  triggered_alerts: Array<{
    alert_id: string;
    rule_id: string;
    rule_name: string;
    category: string;
    severity: PriorityTier;
    base_weight: number;
    risk_score: number;
    threshold_desc: string;
    metric_name: string;
    observed_value: string;
    threshold_value: string;
    explanation_summary: string;
    created_at: string;
    status: string;
  }>;
  rule_evaluations: RuleEvaluationItem[];
  flag_reasons: string[];
  account_risk: {
    account_id: string;
    risk_score: number;
    risk_level: "HIGH" | "MEDIUM" | "LOW";
    alert_count: number;
    is_dormant_reactivated: boolean;
    factors: Array<{ factor: string; points: number }>;
  };
  customer_risk: {
    customer_id: string;
    risk_score: number;
    risk_level: "HIGH" | "MEDIUM" | "LOW";
    case_count: number;
    suspicious_account_count: number;
    factors: Array<{ factor: string; points: number }>;
  };
  related_transactions: Array<
    TransactionItem & {
      merchant_name: string | null;
    }
  >;
  validation_exceptions: QuarantineData["exceptions"];
}

export interface RiskScoringOverview {
  thresholds: { HIGH: string; MEDIUM: string; LOW: string };
  transaction_risk_distribution: Record<
    "HIGH" | "MEDIUM" | "LOW",
    { count: number; avg_score: number; max_score: number }
  >;
  account_risk_distribution: Record<"HIGH" | "MEDIUM" | "LOW", number>;
  customer_risk_distribution: Record<"HIGH" | "MEDIUM" | "LOW", number>;
  top_risk_accounts: Array<{
    account_id: string;
    primary_customer_id: string;
    customer_name: string;
    status: string;
    alert_count: number;
    account_risk_score: number;
    risk_level: "HIGH" | "MEDIUM" | "LOW";
  }>;
  top_risk_customers: Array<{
    customer_id: string;
    full_name: string;
    kyc_tier: string;
    suspicious_accts: number;
    customer_risk_score: number;
    risk_level: "HIGH" | "MEDIUM" | "LOW";
  }>;
  rules_summary: Array<{
    rule_id: string;
    rule_name: string;
    category: string;
    severity: PriorityTier;
    base_weight: number;
    threshold_desc: string;
    is_active: number;
    hit_count: number;
    avg_score: number;
  }>;
  anomaly_detectors?: Array<{
    key: string;
    function_num: number;
    name: string;
    rules: string[];
    alert_count: number;
    extra_metric?: string;
    description: string;
  }>;
  integrity_detectors?: {
    closed_account_txns: { count: number; items: Array<Record<string, unknown>> };
    negative_balance_no_overdraft: { count: number; items: Array<Record<string, unknown>> };
    mismatched_transfer_amounts: { count: number; items: Array<Record<string, unknown>> };
    missing_or_inconsistent_references: { count: number; items: Array<Record<string, unknown>> };
  };
  execution_runs?: RuleExecutionRun[];
  score_history?: RiskScoreHistoryItem[];
}

export interface RuleExecutionRun {
  run_id: string;
  trigger_source: string;
  rule_id: string | null;
  txns_evaluated: number;
  alerts_affected: number;
  avg_score: number;
  executed_by: string;
  executed_at: string;
  summary: string;
}

export interface RiskScoreHistoryItem {
  history_id: string;
  entity_type: string;
  entity_id: string;
  prev_score: number;
  new_score: number;
  prev_level: string;
  new_level: string;
  reason: string;
  rule_id: string | null;
  recorded_at: string;
  actor_id: string;
}

export interface AlertListItem {
  alert_id: string;
  rule_id: string;
  rule_name: string;
  rule_category: string;
  base_weight: number;
  threshold_desc: string;
  account_id: string;
  customer_id: string;
  customer_name: string;
  primary_txn_id: string | null;
  severity: PriorityTier;
  risk_score: number;
  trigger_txn_count: number;
  trigger_total_amount: number;
  explanation_summary: string;
  status: string;
  created_at: string;
  case_id: string | null;
  case_priority_score: number | null;
  case_priority_tier: PriorityTier | null;
  priority_score_effective: number;
  owner_analyst_id?: string | null;
  disposition?: string | null;
  suppression_reason?: string | null;
  sla_hours?: number;
  age_hours?: number;
  sla_breached?: boolean;
}

export interface AlertDetail {
  alert: AlertListItem;
  rule: RiskRuleItem | null;
  customer: CustomerListItem;
  account: AccountDetail["account"];
  primary_transaction: (TransactionItem & { merchant_name?: string | null; merchant_category?: string | null }) | null;
  trigger_facts: Array<{
    fact_id: string;
    alert_id: string;
    transaction_id: string;
    transfer_id: string | null;
    rule_id: string;
    metric_name: string;
    observed_value: string;
    threshold_value: string;
    recorded_at: string;
    txn_type?: string;
    direction?: "DEBIT" | "CREDIT";
    amount?: number;
    occurred_at?: string;
    channel?: string;
    device_id?: string | null;
    counterparty_country?: string;
  }>;
  linked_cases: Array<{
    case_id: string;
    priority_score: number;
    priority_tier: PriorityTier;
    status: string;
    linkage_reason: string;
    linkage_key: string;
    linked_at: string;
  }>;
  supporting_transactions: Array<TransactionItem & { merchant_name?: string | null }>;
  sibling_alerts: Array<AlertListItem>;
  risk_contributions: Array<{ component: string; points: number; detail: string }>;
  score_history: RiskScoreHistoryItem[];
  triage_meta?: {
    alert_id: string;
    owner_analyst_id: string | null;
    disposition: string | null;
    suppression_reason: string | null;
    sla_hours: number;
    updated_at: string | null;
  };
  audit_events?: AlertAuditEvent[];
  watchlist_tags?: WatchlistTagItem[];
}

export interface RiskEvaluationResult {
  evaluated_at: string;
  transaction: TransactionItem;
  transaction_risk_score: number;
  transaction_risk_level: "HIGH" | "MEDIUM" | "LOW";
  account_risk: TransactionDetail["account_risk"];
  customer_risk: TransactionDetail["customer_risk"];
  triggered_rule_count: number;
  rule_evaluations: RuleEvaluationItem[];
  flag_reasons: string[];
}

export interface CaseListItem {
  queue_rank: number;
  case_id: string;
  primary_account_id: string;
  primary_customer_id: string;
  customer_name: string;
  kyc_tier: string;
  segment: string;
  home_country: string;
  linkage_summary: string;
  linked_account_count: number;
  alert_count: number;
  total_exposure_amount: number;
  priority_score: number;
  priority_tier: PriorityTier;
  status: string;
  created_at: string;
  updated_at: string;
  rules_triggered: string[];
  assigned_analyst_id?: string | null;
  priority_override_tier?: PriorityTier | null;
  priority_override_score?: number | null;
  override_reason?: string | null;
  effective_priority_tier?: PriorityTier;
  effective_priority_score?: number;
  priority_rank?: number;
  fifo_rank?: number;
  rank_delta?: number;
  age_hours?: number;
  sla_breached?: boolean;
  requires_reviewer_signoff?: boolean;
}

export interface GraphNode {
  id: string;
  type: "CUSTOMER" | "ACCOUNT" | "DEVICE" | "MERCHANT";
  label: string;
  sublabel: string;
  risk: string;
  is_primary?: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: "OWNS" | "USES_DEVICE" | "TRANSFER" | "MERCHANT_TXN";
  label: string;
  amount?: number;
  status?: string;
}

export interface Waterfall {
  rule_severity: number;
  network_blast_radius: number;
  financial_exposure: number;
  entity_lifecycle_context: number;
  benign_mitigators: number;
  rules_triggered: string[];
}

export interface CaseDossier {
  case: {
    case_id: string;
    primary_account_id: string;
    primary_customer_id: string;
    linkage_summary: string;
    linked_account_count: number;
    alert_count: number;
    total_exposure_amount: number;
    priority_score: number;
    priority_tier: PriorityTier;
    status: string;
    created_at: string;
    updated_at: string;
    assigned_analyst_id?: string | null;
    effective_priority_tier?: PriorityTier;
    effective_priority_score?: number;
    age_hours?: number;
    sla_breached?: boolean;
    requires_reviewer_signoff?: boolean;
  };
  waterfall: Waterfall;
  alerts: Array<{
    alert_id: string;
    rule_id: string;
    rule_name: string;
    category: string;
    account_id: string;
    severity: PriorityTier;
    risk_score: number;
    explanation_summary: string;
    created_at: string;
    status: string;
  }>;
  trigger_facts: Array<{
    fact_id: string;
    alert_id: string;
    transaction_id: string;
    transfer_id: string | null;
    rule_id: string;
    metric_name: string;
    observed_value: string;
    threshold_value: string;
  }>;
  accounts: Array<{
    account_id: string;
    account_type: string;
    status: string;
    current_balance: number;
  }>;
  account_state_events: Array<{
    event_id: string;
    account_id: string;
    prev_status: string | null;
    new_status: string;
    effective_at: string;
    reason: string;
    actor_id: string;
  }>;
  transactions: Array<{
    transaction_id: string;
    account_id: string;
    txn_type: string;
    direction: "DEBIT" | "CREDIT";
    amount: number;
    balance_before: number;
    balance_after: number;
    channel: string;
    merchant_name: string | null;
    merchant_category: string | null;
    occurred_at: string;
    reference_note: string;
    reconciled_ok: boolean;
  }>;
  total_ledger_txns: number;
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  analyst_actions: Array<{
    action_id: string;
    analyst_id: string;
    analyst_role: string;
    action_type: string;
    rationale: string;
    acted_at: string;
  }>;
  case_state_events: Array<{
    case_event_id: string;
    prev_status: string | null;
    new_status: string;
    analyst_action_id: string | null;
    effective_at: string;
  }>;
  triage_meta?: {
    case_id: string;
    assigned_analyst_id: string | null;
    priority_override_tier: PriorityTier | null;
    priority_override_score: number | null;
    override_reason: string | null;
    override_by: string | null;
    override_at: string | null;
    sla_hours: number;
    sar_draft: string | null;
    sar_updated_at: string | null;
  };
  checklist?: CaseEvidenceChecklist;
  watchlist_tags?: WatchlistTagItem[];
}

export interface QuarantineExceptionItem {
  exception_id: string;
  issue_type: string;
  severity: PriorityTier;
  entity_type: string;
  entity_id: string;
  account_id: string;
  violated_invariant: string;
  evidence: string;
  remediation: string;
  review_status?: "PENDING" | "ACKNOWLEDGED" | "REMEDIATED" | "WAIVED";
  reviewer_id?: string | null;
  remediation_note?: string | null;
  action_taken?: string | null;
  updated_at?: string | null;
  estimated_exposure?: number;
}

export interface QuarantineData {
  total_exceptions: number;
  filtered_total?: number;
  counts_by_issue_type: Record<string, number>;
  counts_by_review_status?: Record<string, number>;
  quarantined_exposure?: number;
  pending_exposure?: number;
  exceptions: QuarantineExceptionItem[];
}

export interface QuarantineDetail {
  exception: QuarantineExceptionItem;
  events: Array<{
    event_id: string;
    exception_id: string;
    actor_id: string;
    prev_status: string | null;
    new_status: string;
    note: string;
    action_taken: string | null;
    created_at: string;
  }>;
}

export interface IntegrityCheckReport {
  validated_at: string;
  passed_checks: number;
  total_checks: number;
  quarantine_isolated_total: number;
  checks: Array<{
    check_id: string;
    name: string;
    description: string;
    violations_found: number;
    status: "PASS" | "WARN_ISOLATED";
  }>;
}

export interface RiskRuleItem {
  rule_id: string;
  rule_name: string;
  category: string;
  severity: PriorityTier;
  base_weight: number;
  threshold_desc: string;
  is_active?: number;
  version?: string;
  effective_from?: string;
  hit_count: number;
  avg_alert_score: number;
}

export interface EvaluationData {
  total_cases: number;
  true_positive_cases: number;
  false_positive_cases: number;
  priority_top20: { k: number; tp: number; precision: number; recall: number; ndcg?: number };
  fifo_top20: { k: number; tp: number; precision: number; recall: number; ndcg?: number };
  priority_top50_cases: { tp: number; precision: number; ndcg?: number };
  lift_curve: Array<{
    queue_pct: number;
    priority_recall: number;
    priority_precision: number;
    fifo_recall: number;
    fifo_precision: number;
  }>;
  typology_stats: Array<{
    typology: string;
    case_count: number;
    avg_priority_score: number;
    min_score: number;
    max_score: number;
    p25_score?: number;
    p50_score?: number;
    p75_score?: number;
    p90_score?: number;
    is_risk_typology: boolean;
  }>;
  score_separation?: {
    tp_mean_score: number;
    fp_mean_score: number;
    separation_gap: number;
  };
  negative_edge_catch_rate: {
    injected_count: number;
    caught_count: number;
    expected_issue_types: string[];
    caught_issue_types: string[];
    all_types_caught: boolean;
  };
  manifest: {
    seed?: number;
    scale?: string;
    generator_command?: string;
    sha256_checksums?: Record<string, string>;
  };
}

export interface UnifiedAuditEvent {
  event_id: string;
  source: "CASE" | "ALERT" | "QUARANTINE" | "RISK_ENGINE" | "AUTH";
  entity_type: string;
  entity_id: string;
  actor_id: string;
  action_type: string;
  severity: PriorityTier;
  detail: string;
  occurred_at: string;
  integrity_hash: string;
}

export interface UnifiedAuditResponse {
  total: number;
  all_total: number;
  counts_by_source: Record<string, number>;
  batch_digest: string;
  items: UnifiedAuditEvent[];
}

export interface AnalystStatsItem {
  analyst_id: string;
  full_name: string;
  role: string;
  assigned_cases: number;
  cases_resolved: number;
  sar_filed_cases: number;
  alerts_triaged: number;
  quarantine_reviews: number;
  watchlist_tags: number;
  actions_logged: number;
  total_throughput: number;
  resolution_rate: number;
}

export interface AdminUserItem extends AuthUser {
  active_sessions: number;
  last_login_at: string | null;
}

export interface SlaPolicyItem {
  policy_key: string;
  entity_scope: "CASE" | "ALERT";
  tier: PriorityTier;
  sla_hours: number;
  updated_by: string | null;
  updated_at: string;
}

export interface SlaPolicyResponse {
  items: SlaPolicyItem[];
  map: Record<string, Record<string, number>>;
}

export interface SavedViewItem {
  view_id: string;
  user_id: string;
  workspace: "queue" | "alerts" | "transactions" | "quarantine";
  name: string;
  filters: Record<string, string | boolean>;
  created_at: string;
}

export interface CutoffSimResult {
  k_pct: number;
  total_cases: number;
  total_true_positive: number;
  priority: { k: number; tp: number; fp: number; precision: number; recall: number; f1: number; ndcg: number; map: number; exposure_captured: number };
  fifo: { k: number; tp: number; fp: number; precision: number; recall: number; f1: number; ndcg: number; map: number; exposure_captured: number };
  recall_lift: number;
}

export interface RulePerformanceItem {
  rule_id: string;
  rule_name: string;
  category: string;
  severity: PriorityTier;
  base_weight: number;
  alerts_fired: number;
  linked_cases: number;
  tp_cases: number;
  fp_cases: number;
  precision: number;
  false_positive_rate: number;
  avg_alert_score: number;
  avg_case_score: number;
}

export interface WhatIfSimResult {
  k: number;
  k_pct: number;
  baseline: { tp: number; precision: number; recall: number; ndcg: number };
  simulated: { tp: number; precision: number; recall: number; ndcg: number };
  recall_delta: number;
  precision_delta: number;
  top_rank_shifts: Array<{ case_id: string; old_rank: number; new_rank: number; shift: number; baseline_score: number; simulated_score: number }>;
}

export interface ZeroLeakageReport {
  zero_leakage_verified: boolean;
  checked_at: string;
  file_count: number;
  files_inspected: string[];
  violations: string[];
}

export interface ManifestVerificationReport {
  verified: boolean;
  verified_at: string;
  matched_count: number;
  total_count: number;
  files: Array<{ file: string; expected: string; actual: string | null; status: "VERIFIED" | "MISMATCH" | "MISSING" }>;
}

export interface CollusionRingItem {
  ring_id: string;
  device_id: string;
  os_family: string;
  ip_country: string;
  is_emulator: boolean;
  device_risk_tier: string;
  customer_count: number;
  account_count: number;
  customer_ids: string[];
  account_ids: string[];
  alert_count: number;
  alert_exposure: number;
  max_alert_score: number;
}

export interface EntityNetworkResponse {
  root_id: string;
  root_type: string;
  root_label: string;
  node_count: number;
  edge_count: number;
  transfer_exposure: number;
  nodes: Array<{ id: string; type: string; label: string; risk: string; meta?: Record<string, unknown> }>;
  edges: Array<{ source: string; target: string; relation: string; exposure: number }>;
}

export interface SarRegistryItem {
  case_id: string;
  customer_id: string;
  customer_name: string;
  account_id: string;
  priority_tier: PriorityTier;
  priority_score: number;
  total_exposure_amount: number;
  case_status: string;
  assigned_analyst_id: string | null;
  sar_status: "DRAFT" | "READY_FOR_FILING" | "SUBMITTED";
  sar_updated_at: string | null;
  sar_excerpt: string;
  readiness: {
    readiness_score: number;
    passed_criteria: number;
    total_criteria: number;
    criteria: Record<string, boolean>;
  };
}

export interface SimilarCaseItem {
  case_id: string;
  customer_id: string;
  customer_name: string;
  priority_tier: PriorityTier;
  priority_score: number;
  total_exposure_amount: number;
  status: string;
  shared_rules: string[];
  similarity_pct: number;
}

export interface ExecutiveDigestResponse {
  generated_at: string;
  scale?: string;
  seed?: number;
  pillars: {
    exposure_concentration: { total_case_exposure: number; high_critical_exposure: number; high_critical_share_pct: number };
    alert_compression: { alerts: number; cases: number; compression_ratio: number };
    case_resolution: { total_cases: number; resolved_cases: number; resolution_pct: number };
    quarantine_shield: { total_quarantined: number; pending_review: number; quarantined_exposure: number };
    sar_readiness: { total_sar_tracked: number; counts_by_status: Record<string, number>; shared_device_rings: number };
  };
}

export interface GlobalSearchResponse {
  query: string;
  total_hits: number;
  groups: Record<
    "cases" | "alerts" | "customers" | "accounts" | "transactions" | "quarantine",
    Array<{ id: string; title: string; subtitle: string; badge: string }>
  >;
}

export interface SystemHealthResponse {
  status: string;
  checked_at: string;
  scale: string;
  seed?: number;
  db_size_mb: number;
  sqlite_index_count: number;
  active_sessions: number;
  ledger_watermark: string | null;
  table_counts: Record<string, number>;
}

export interface WatchedCountryItem {
  country_code: string;
  country_name: string;
  risk_tier: "WATCH" | "RESTRICTED";
  multiplier: number;
  note: string | null;
  updated_by: string | null;
  updated_at: string;
}

export interface CorridorRiskItem {
  origin_country: string;
  counterparty_country: string;
  is_cross_border: boolean;
  jurisdiction_tier: string;
  jurisdiction_multiplier: number;
  txn_count: number;
  total_volume: number;
  high_value_txns: number;
  alert_count: number;
  alert_rate_pct: number;
  avg_alert_score: number;
}

export interface MerchantLeaderboardItem {
  merchant_id: string;
  merchant_name: string;
  mcc: string;
  category: string;
  country: string;
  risk_tier: string;
  is_high_risk_mcc: boolean;
  txn_count: number;
  total_volume: number;
  avg_ticket: number;
  customer_spread: number;
  alert_count: number;
  max_alert_score: number;
}

export interface StructuringClusterItem {
  account_id: string;
  primary_customer_id: string;
  customer_name: string;
  burst_count: number;
  total_structured_amount: number;
  first_at: string;
  last_at: string;
  avg_ticket: number;
}

export interface FlowChainResponse {
  root_account_id: string;
  total_inflow: number;
  total_outflow: number;
  pass_through_pct: number;
  edges: Array<{
    transfer_id: string;
    source_account_id: string;
    dest_account_id: string;
    transfer_amount: number;
    initiated_at: string;
  }>;
  pass_through_chains: Array<{
    path: string;
    in_amount: number;
    out_amount: number;
    retention_pct: number;
    lag_hours: number;
  }>;
}

export interface PeerBaselineResponse {
  customer_id: string;
  cohort: string;
  cohort_sample_size: number;
  customer_volume: number;
  cohort_mean_volume: number;
  cohort_p95_volume: number;
  volume_ratio_to_mean: number;
  customer_avg_ticket: number;
  cohort_mean_ticket: number;
  cross_border_pct: number;
}

export interface KycReviewItem {
  review_id: string;
  customer_id: string;
  outcome: "VERIFIED" | "EDD_REQUIRED" | "OVERDUE";
  risk_justification: string;
  reviewer_id: string;
  reviewed_at: string;
}

export interface AccountControlItem {
  account_id: string;
  control_status: "NONE" | "DEBIT_HOLD" | "POST_NO_DEBITS" | "FULL_FREEZE";
  reason: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

export interface AccountVelocityResponse {
  account_id: string;
  buckets: Array<{ day: string; txn_count: number; credits: number; debits: number }>;
}

export interface CasePinItem {
  pin_id: string;
  case_id: string;
  entity_type: string;
  entity_id: string;
  pin_type: "PINNED_PROOF" | "CORROBORATING" | "EXCULPATORY";
  note: string | null;
  actor_id: string;
  created_at: string;
}

export interface CaseCommentItem {
  comment_id: string;
  case_id: string;
  actor_id: string;
  actor_role: string;
  visibility: "INTERNAL" | "COMPLIANCE";
  body: string;
  created_at: string;
}

export interface PlaybookItem {
  playbook_id: string;
  title: string;
  typology: string;
  checklist_updates: Record<string, boolean>;
  steps: string[];
}

export interface SlaRadarResponse {
  breached_count: number;
  at_risk_count: number;
  breached: Array<{
    case_id: string;
    customer_name: string;
    priority_tier: PriorityTier;
    priority_score: number;
    status: string;
    assigned_analyst_id: string | null;
    sla_target_hours: number;
    age_hours: number;
    hours_remaining: number;
  }>;
  at_risk: Array<{
    case_id: string;
    customer_name: string;
    priority_tier: PriorityTier;
    priority_score: number;
    status: string;
    assigned_analyst_id: string | null;
    sla_target_hours: number;
    age_hours: number;
    hours_remaining: number;
  }>;
}

export interface SuppressionRuleItem {
  suppression_id: string;
  account_id: string;
  rule_id: string;
  max_amount: number;
  reason: string;
  expires_at: string;
  created_by: string;
  created_at: string;
  is_active: number;
}

export interface CapacityForecastResponse {
  baseline: { alerts: number; cases: number; open_cases: number; compression_ratio: number };
  parameters: { growth_factor: number; hours_per_case: number; analysts_available: number };
  projection: {
    projected_alerts: number;
    projected_open_cases: number;
    required_hours: number;
    team_weekly_capacity_hours: number;
    utilization_pct: number;
  };
  scenarios: Array<{
    growth_factor: number;
    projected_alerts: number;
    projected_open_cases: number;
    required_hours: number;
    recommended_analysts: number;
  }>;
}

export interface ThresholdSweepResponse {
  rule_id: string;
  total_rule_alerts: number;
  points: Array<{
    multiplier: number;
    score_cutoff: number;
    alerts_retained: number;
    tp_cases: number;
    fp_cases: number;
    precision: number;
    recall: number;
    f1: number;
  }>;
}

export interface TemporalDriftResponse {
  buckets: Array<{
    cohort_index: number;
    window_start: string;
    window_end: string;
    case_count: number;
    avg_priority_score: number;
    high_critical_share: number;
    tp_rate: number;
    ndcg_top20: number;
  }>;
}

export interface CalibrationProposalItem {
  proposal_id: string;
  title: string;
  weights: Record<string, number>;
  simulation_summary: Record<string, unknown>;
  status: "PENDING_APPROVAL" | "APPROVED" | "REJECTED";
  created_by: string;
  approved_by: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface MergeCandidateItem {
  primary_case_id: string;
  secondary_case_id: string;
  customer_id: string;
  customer_name: string;
  score_1: number;
  score_2: number;
  exp_1: number;
  exp_2: number;
  overlap_reason: string;
}

export interface NotificationItem {
  notif_id: string;
  user_id: string;
  category: string;
  severity: string;
  title: string;
  body: string;
  entity_type: string | null;
  entity_id: string | null;
  is_read: number;
  created_at: string;
}

export interface SiemOutboxItem {
  outbox_id: string;
  event_type: string;
  severity: string;
  entity_id: string;
  payload: Record<string, unknown>;
  delivery_status: string;
  created_at: string;
  dispatched_at: string | null;
}

export interface PipelineRunItem {
  job_id: string;
  job_type: string;
  status: string;
  summary: string;
  duration_ms: number;
  triggered_by: string;
  started_at: string;
  finished_at: string;
}

export interface UserPreferences {
  user_id: string;
  default_tab: string;
  default_page_size: number;
  sla_lead_hours: number;
  compact_mode: boolean;
  updated_at: string;
}

// Batch 10 & 11: Enterprise Intelligence, QA, Deep Evaluation & Telemetry (Functions 226-275)
export interface SanctionsScreeningItem {
  screening_id: string;
  entity_type: string;
  entity_id: string;
  query_name: string;
  match_score: number;
  matched_list_id: string | null;
  matched_program: string | null;
  disposition: "CLEAR" | "REVIEW_RECOMMENDED" | "POTENTIAL_MATCH";
  screened_by: string;
  screened_at: string;
}

export interface FanHubItem {
  account_id: string;
  primary_customer_id: string;
  customer_name: string;
  fan_in_sources: number;
  fan_out_dests: number;
  in_volume: number;
  out_volume: number;
  total_degree: number;
  hub_pattern: string;
}

export interface CustomerChronologyItem {
  event_type: string;
  ref_id: string;
  timestamp: string;
  summary: string;
  severity: string;
}

export interface AccountBurstProfile {
  account_id: string;
  total_txns: number;
  rapid_under_15m: number;
  rapid_under_60m: number;
  night_window_txns: number;
  night_window_pct: number;
  round_dollar_txns: number;
  round_dollar_pct: number;
}

export interface QaSampleItem {
  case_id: string;
  priority_tier: PriorityTier;
  priority_score: number;
  status: string;
  total_exposure_amount: number;
  customer_name: string;
  grade: string | null;
  qa_score: number | null;
  feedback: string | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
}

export interface WebhookEndpointItem {
  webhook_id: string;
  name: string;
  target_url: string;
  secret_hint: string;
  is_active: number;
  last_status: string | null;
  last_tested_at: string | null;
  created_by: string;
  created_at: string;
}

export interface ExamControlItem {
  control_id: string;
  domain: string;
  title: string;
  status: "VERIFIED" | "IN_PROGRESS" | "ACTION_REQUIRED";
  owner_id: string;
  note: string;
  updated_at: string;
}

export interface LiftCurveDecile {
  k_pct: number;
  cases_reviewed: number;
  priority_tp: number;
  fifo_tp: number;
  priority_recall: number;
  fifo_recall: number;
  lift_ratio: number;
}

export interface FeaturePsiItem {
  feature: string;
  psi: number;
  status: "STABLE" | "MONITOR" | "DRIFT";
}

export interface WorkspacePinItem {
  pin_id: string;
  user_id: string;
  entity_type: string;
  entity_id: string;
  label: string;
  pinned_at: string;
}
