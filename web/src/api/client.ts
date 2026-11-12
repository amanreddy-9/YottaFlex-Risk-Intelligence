import type {
  AccountDetail,
  AccountListItem,
  AdminUserItem,
  AnalystStatsItem,
  AuthSessionItem,
  AuthUser,
  CaseDossier,
  CaseListItem,
  CollusionRingItem,
  CustomerListItem,
  CustomerProfile,
  CutoffSimResult,
  DashboardData,
  EntityNetworkResponse,
  EvaluationData,
  ExecutiveDigestResponse,
  GlobalSearchResponse,
  IntegrityCheckReport,
  LoginHistoryItem,
  ManifestVerificationReport,
  OverviewData,
  QuarantineData,
  QuarantineDetail,
  QuarantineExceptionItem,
  RiskRuleItem,
  RulePerformanceItem,
  SarRegistryItem,
  SavedViewItem,
  SimilarCaseItem,
  SlaPolicyResponse,
  SystemHealthResponse,
  TransactionItem,
  UnifiedAuditResponse,
  WatchlistTagItem,
  WhatIfSimResult,
  ZeroLeakageReport,
} from "../types/workbench";

const TOKEN_KEY = "yottaflex_auth_token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...options, headers });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error || `HTTP ${res.status}`);
  }
  return data as T;
}

function buildQS(params: Record<string, string | number | undefined | null>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  });
  return qs.toString();
}

export async function downloadExport(url: string, filename: string): Promise<void> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Export failed (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objUrl);
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{ token: string; session_id: string; expires_at: string; user: AuthUser }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    logout: () => request<{ status: string }>("/api/auth/logout", { method: "POST" }),
    me: () => request<{ user: AuthUser }>("/api/auth/me"),
    updateProfile: (payload: { full_name: string; phone: string; department: string; title: string }) =>
      request<{ user: AuthUser }>("/api/auth/profile", {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    forgotPassword: (email: string) =>
      request<{ reset_id: string; email: string; expires_at: string; demo_reset_code: string }>(
        "/api/auth/forgot-password",
        { method: "POST", body: JSON.stringify({ email }) }
      ),
    resetPassword: (payload: { email: string; reset_code: string; new_password: string }) =>
      request<{ email: string; status: string }>("/api/auth/reset-password", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    sessions: () => request<{ sessions: AuthSessionItem[]; login_history: LoginHistoryItem[] }>("/api/auth/sessions"),
    revokeSession: (session_id: string) =>
      request<{ status: string }>("/api/auth/sessions/revoke", {
        method: "POST",
        body: JSON.stringify({ session_id }),
      }),
  },
  overview: () => request<OverviewData>("/api/overview"),
  dashboard: (params: Record<string, string | undefined>) =>
    request<DashboardData>(`/api/dashboard?${buildQS(params)}`),
  dashboardExportUrl: (fmt: "csv" | "json", params: Record<string, string | undefined>) =>
    `/api/dashboard/export?${buildQS({ ...params, format: fmt })}`,
  customers: (params: Record<string, string | number | undefined>) =>
    request<{ total: number; items: CustomerListItem[] }>(`/api/customers?${buildQS(params)}`),
  customerProfile: (customerId: string) =>
    request<CustomerProfile>(`/api/customers/${encodeURIComponent(customerId)}`),
  customerExportUrl: (customerId: string, fmt: "csv" | "json") =>
    `/api/customers/${encodeURIComponent(customerId)}/export?format=${fmt}`,
  accounts: (params: Record<string, string | number | undefined>) =>
    request<{ total: number; items: AccountListItem[] }>(`/api/accounts?${buildQS(params)}`),
  accountDetail: (accountId: string) =>
    request<AccountDetail>(`/api/accounts/${encodeURIComponent(accountId)}`),
  transactions: (params: Record<string, string | number | undefined>) =>
    request<{ total: number; items: TransactionItem[] }>(`/api/transactions?${buildQS(params)}`),
  transactionDetail: (transactionId: string) =>
    request<import("../types/workbench").TransactionDetail>(
      `/api/transactions/${encodeURIComponent(transactionId)}`
    ),
  transactionsExportUrl: (fmt: "csv" | "json", params: Record<string, string | number | undefined>) =>
    `/api/transactions/export?${buildQS({ ...params, format: fmt })}`,
  riskScoring: () =>
    request<import("../types/workbench").RiskScoringOverview>("/api/risk/scoring"),
  riskExecutions: (entityId?: string) =>
    request<{
      execution_runs: import("../types/workbench").RuleExecutionRun[];
      score_history: import("../types/workbench").RiskScoreHistoryItem[];
    }>(`/api/risk/executions?${buildQS({ entity_id: entityId })}`),
  reevaluateRisk: (ruleId?: string) =>
    request<{
      execution_run: import("../types/workbench").RuleExecutionRun;
      alerts_evaluated: number;
      scores_changed: number;
    }>("/api/risk/re-evaluate", {
      method: "POST",
      body: JSON.stringify({ rule_id: ruleId || "ALL" }),
    }),
  updateRiskRule: (
    ruleId: string,
    payload: { base_weight?: number; is_active?: boolean; threshold_desc?: string }
  ) =>
    request<{
      execution_run: import("../types/workbench").RuleExecutionRun;
      updated_rule: RiskRuleItem;
      alerts_evaluated: number;
      scores_changed: number;
    }>(`/api/risk/rules/${encodeURIComponent(ruleId)}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  alerts: (params: Record<string, string | number | undefined>) =>
    request<{ total: number; items: import("../types/workbench").AlertListItem[] }>(`/api/alerts?${buildQS(params)}`),
  alertsExportUrl: (fmt: "csv" | "json", params: Record<string, string | number | undefined>) =>
    `/api/alerts/export?${buildQS({ ...params, format: fmt })}`,
  alertDetail: (alertId: string) =>
    request<import("../types/workbench").AlertDetail>(`/api/alerts/${encodeURIComponent(alertId)}`),
  triageAlert: (
    alertId: string,
    payload: {
      owner_analyst_id?: string;
      status?: string;
      disposition?: string;
      suppression_reason?: string;
      note?: string;
    }
  ) =>
    request<Record<string, unknown>>(`/api/alerts/${encodeURIComponent(alertId)}/triage`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  escalateAlert: (alertId: string, payload: { target_case_id?: string; rationale?: string }) =>
    request<{ alert_id: string; case_id: string; created_new_case: boolean; status: string }>(
      `/api/alerts/${encodeURIComponent(alertId)}/escalate`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  bulkTriageAlerts: (payload: {
    alert_ids: string[];
    action: string;
    owner_analyst_id?: string;
    suppression_reason?: string;
    rationale?: string;
  }) =>
    request<{ action: string; updated_count: number; updated: string[]; skipped: Array<{ alert_id: string; reason: string }> }>(
      "/api/alerts/bulk-triage",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  evaluateRisk: (payload: { transaction_id?: string; payload?: Record<string, unknown> }) =>
    request<import("../types/workbench").RiskEvaluationResult>("/api/risk/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cases: (params: Record<string, string | number | undefined>) =>
    request<{ total: number; sort: string; items: CaseListItem[] }>(`/api/cases?${buildQS(params)}`),
  casesExportUrl: (fmt: "csv" | "json", params: Record<string, string | number | undefined>) =>
    `/api/cases/export?${buildQS({ ...params, format: fmt })}`,
  bulkTriageCases: (payload: {
    case_ids: string[];
    action: string;
    assigned_analyst_id?: string;
    rationale?: string;
  }) =>
    request<{ action: string; updated_count: number; updated: string[]; skipped: Array<{ case_id: string; reason: string }> }>(
      "/api/cases/bulk",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  dossier: (caseId: string) => request<CaseDossier>(`/api/cases/${encodeURIComponent(caseId)}`),
  caseExportUrl: (caseId: string, fmt: "json" | "md") =>
    `/api/cases/${encodeURIComponent(caseId)}/export?format=${fmt}`,
  triageCase: (
    caseId: string,
    payload: {
      assigned_analyst_id?: string;
      override_tier?: string;
      override_score?: number;
      override_reason?: string;
    }
  ) =>
    request<Record<string, unknown>>(`/api/cases/${encodeURIComponent(caseId)}/triage`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  linkCaseAlert: (
    caseId: string,
    payload: { alert_id: string; mode: "link" | "unlink"; linkage_reason?: string; rationale?: string }
  ) =>
    request<Record<string, unknown>>(`/api/cases/${encodeURIComponent(caseId)}/alerts`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateChecklist: (
    caseId: string,
    payload: {
      rules_reviewed?: boolean;
      ledger_reconciled?: boolean;
      network_verified?: boolean;
      kyc_corroborated?: boolean;
      notes?: string;
    }
  ) =>
    request<import("../types/workbench").CaseEvidenceChecklist>(`/api/cases/${encodeURIComponent(caseId)}/checklist`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  sarDraft: (caseId: string, payload: { sar_draft?: string }) =>
    request<{ case_id: string; sar_draft: string; sar_updated_at: string }>(
      `/api/cases/${encodeURIComponent(caseId)}/sar-draft`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  manageWatchlistTag: (payload: {
    entity_type: "CUSTOMER" | "ACCOUNT";
    entity_id: string;
    tag: string;
    note?: string;
    remove?: boolean;
  }) =>
    request<{ entity_type: string; entity_id: string; tags: import("../types/workbench").WatchlistTagItem[] }>(
      "/api/watchlist-tags",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  submitAction: (
    caseId: string,
    payload: { analyst_id: string; action_type: string; rationale: string }
  ) =>
    request<{ action: { action_id: string }; new_status: string }>(
      `/api/cases/${encodeURIComponent(caseId)}/actions`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  quarantine: (params?: Record<string, string | number | undefined>) =>
    request<QuarantineData>(params ? `/api/quarantine?${buildQS(params)}` : "/api/quarantine"),
  quarantineDetail: (exceptionId: string) =>
    request<QuarantineDetail>(`/api/quarantine/${encodeURIComponent(exceptionId)}`),
  reviewQuarantine: (
    exceptionId: string,
    payload: { review_status: string; note?: string; action_taken?: string }
  ) =>
    request<QuarantineDetail>(`/api/quarantine/${encodeURIComponent(exceptionId)}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  bulkReviewQuarantine: (payload: {
    exception_ids: string[];
    review_status: string;
    note?: string;
    action_taken?: string;
  }) =>
    request<{ updated_count: number; items: QuarantineExceptionItem[] }>("/api/quarantine/bulk-review", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  validateIntegrity: () => request<IntegrityCheckReport>("/api/quarantine/validate", { method: "POST", body: "{}" }),
  quarantineExportUrl: (fmt: "csv" | "json", params?: Record<string, string | number | undefined>) =>
    `/api/quarantine/export?${buildQS({ ...(params || {}), format: fmt })}`,

  auditEvents: (params: Record<string, string | number | undefined>) =>
    request<UnifiedAuditResponse>(`/api/audit/events?${buildQS(params)}`),
  auditExportUrl: (fmt: "csv" | "json", params?: Record<string, string | number | undefined>) =>
    `/api/audit/export?${buildQS({ ...(params || {}), format: fmt })}`,
  analystStats: () => request<{ analysts: AnalystStatsItem[] }>("/api/audit/analyst-stats"),
  adminUsers: () => request<{ users: AdminUserItem[] }>("/api/admin/users"),
  updateAdminUser: (userId: string, payload: { role?: string; is_active?: boolean }) =>
    request<{ user: AuthUser }>(`/api/admin/users/${encodeURIComponent(userId)}/role`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  slaPolicies: () => request<SlaPolicyResponse>("/api/admin/sla-policies"),
  updateSlaPolicies: (updates: Array<{ entity_scope: "CASE" | "ALERT"; tier: string; sla_hours: number }>) =>
    request<SlaPolicyResponse>("/api/admin/sla-policies", {
      method: "POST",
      body: JSON.stringify({ updates }),
    }),
  watchlistTags: (params?: Record<string, string | number | undefined>) =>
    request<{ total: number; counts_by_tag: Record<string, number>; items: WatchlistTagItem[] }>(
      `/api/watchlist-tags?${buildQS(params || {})}`
    ),
  savedViews: (workspace = "ALL") =>
    request<{ items: SavedViewItem[] }>(`/api/saved-views?${buildQS({ workspace })}`),
  createSavedView: (payload: { workspace: string; name: string; filters: Record<string, unknown> }) =>
    request<SavedViewItem>("/api/saved-views", { method: "POST", body: JSON.stringify(payload) }),
  deleteSavedView: (viewId: string) =>
    request<{ deleted: boolean; view_id: string }>(`/api/saved-views/${encodeURIComponent(viewId)}`, {
      method: "DELETE",
    }),

  rules: () => request<{ rules: RiskRuleItem[] }>("/api/rules"),
  evaluation: () => request<EvaluationData>("/api/evaluation"),
  simulateCutoff: (kPct: number) =>
    request<CutoffSimResult>(`/api/evaluation/simulate-k?k_pct=${encodeURIComponent(kPct)}`),
  rulePerformance: () => request<{ rules: RulePerformanceItem[] }>("/api/evaluation/rule-performance"),
  whatIfSimulation: (payload: { weight_overrides: Record<string, number>; k_pct: number }) =>
    request<WhatIfSimResult>("/api/evaluation/what-if", { method: "POST", body: JSON.stringify(payload) }),
  zeroLeakageCheck: () => request<ZeroLeakageReport>("/api/evaluation/zero-leakage"),
  verifyManifest: () =>
    request<ManifestVerificationReport>("/api/evaluation/verify-manifest", { method: "POST", body: "{}" }),
  evaluationExportUrl: (fmt: "json" | "csv") => `/api/evaluation/export?format=${fmt}`,

  networkRings: (minAccounts = 2) =>
    request<{ total_rings: number; rings: CollusionRingItem[] }>(`/api/network/rings?min_accounts=${minAccounts}`),
  entityNetwork: (entityId: string) =>
    request<EntityNetworkResponse>(`/api/network/entity/${encodeURIComponent(entityId)}`),
  sarRegistry: (status = "ALL") =>
    request<{ total: number; counts_by_status: Record<string, number>; items: SarRegistryItem[] }>(
      `/api/sar/registry?status=${encodeURIComponent(status)}`
    ),
  transitionSarStatus: (caseId: string, payload: { sar_status: string; note?: string }) =>
    request<{ case_id: string; sar_status: string; sar_updated_at: string }>(
      `/api/sar/${encodeURIComponent(caseId)}/status`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  similarCases: (caseId: string) =>
    request<{ case_id: string; items: SimilarCaseItem[] }>(`/api/cases/${encodeURIComponent(caseId)}/similar`),
  executiveDigest: () => request<ExecutiveDigestResponse>("/api/reports/executive-digest"),
  executiveDigestExportUrl: (fmt: "md" | "json") => `/api/reports/executive-digest/export?format=${fmt}`,
  globalSearch: (q: string) => request<GlobalSearchResponse>(`/api/search/global?q=${encodeURIComponent(q)}`),
  systemHealth: () => request<SystemHealthResponse>("/api/system/health"),

  // Batch 8 & 9: Forensics, Controls, Playbooks, Calibration, Merge & Automation
  corridors: () =>
    request<{
      watched_countries: import("../types/workbench").WatchedCountryItem[];
      items: import("../types/workbench").CorridorRiskItem[];
    }>("/api/analytics/corridors"),
  upsertHighRiskCountry: (payload: {
    country_code: string;
    country_name: string;
    risk_tier: "WATCH" | "RESTRICTED";
    multiplier: number;
    note?: string;
  }) =>
    request<import("../types/workbench").WatchedCountryItem>("/api/analytics/high-risk-countries", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteHighRiskCountry: (code: string) =>
    request<{ deleted: boolean }>(`/api/analytics/high-risk-countries/${encodeURIComponent(code)}`, {
      method: "DELETE",
    }),
  merchants: (search = "") =>
    request<{ total: number; items: import("../types/workbench").MerchantLeaderboardItem[] }>(
      `/api/analytics/merchants?${buildQS({ search })}`
    ),
  merchantDetail: (merchantId: string) =>
    request<Record<string, unknown>>(`/api/analytics/merchants/${encodeURIComponent(merchantId)}`),
  flowChains: (accountId: string) =>
    request<import("../types/workbench").FlowChainResponse>(
      `/api/network/flow-chains/${encodeURIComponent(accountId)}`
    ),
  structuringClusters: () =>
    request<{ total: number; items: import("../types/workbench").StructuringClusterItem[] }>(
      "/api/analytics/structuring"
    ),
  customerPeerBaseline: (customerId: string) =>
    request<import("../types/workbench").PeerBaselineResponse>(
      `/api/customers/${encodeURIComponent(customerId)}/peer-baseline`
    ),
  kycReviews: (customerId: string) =>
    request<{ customer_id: string; reviews: import("../types/workbench").KycReviewItem[] }>(
      `/api/customers/${encodeURIComponent(customerId)}/kyc-reviews`
    ),
  submitKycReview: (
    customerId: string,
    payload: { outcome: "VERIFIED" | "EDD_REQUIRED" | "OVERDUE"; risk_justification: string }
  ) =>
    request<import("../types/workbench").KycReviewItem>(
      `/api/customers/${encodeURIComponent(customerId)}/kyc-review`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  accountControl: (accountId: string) =>
    request<import("../types/workbench").AccountControlItem>(
      `/api/accounts/${encodeURIComponent(accountId)}/control`
    ),
  setAccountControl: (
    accountId: string,
    payload: { control_status: "NONE" | "DEBIT_HOLD" | "POST_NO_DEBITS" | "FULL_FREEZE"; reason: string }
  ) =>
    request<import("../types/workbench").AccountControlItem>(
      `/api/accounts/${encodeURIComponent(accountId)}/control`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  accountVelocity: (accountId: string) =>
    request<import("../types/workbench").AccountVelocityResponse>(
      `/api/accounts/${encodeURIComponent(accountId)}/velocity`
    ),
  casePins: (caseId: string) =>
    request<{ case_id: string; items: import("../types/workbench").CasePinItem[] }>(
      `/api/cases/${encodeURIComponent(caseId)}/pins`
    ),
  addCasePin: (
    caseId: string,
    payload: { entity_type: string; entity_id: string; pin_type: string; note?: string }
  ) =>
    request<import("../types/workbench").CasePinItem>(`/api/cases/${encodeURIComponent(caseId)}/pins`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteCasePin: (caseId: string, pinId: string) =>
    request<{ deleted: boolean }>(
      `/api/cases/${encodeURIComponent(caseId)}/pins/${encodeURIComponent(pinId)}`,
      { method: "DELETE" }
    ),
  caseComments: (caseId: string) =>
    request<{ case_id: string; items: import("../types/workbench").CaseCommentItem[] }>(
      `/api/cases/${encodeURIComponent(caseId)}/comments`
    ),
  addCaseComment: (caseId: string, payload: { body: string; visibility?: "INTERNAL" | "COMPLIANCE" }) =>
    request<import("../types/workbench").CaseCommentItem>(
      `/api/cases/${encodeURIComponent(caseId)}/comments`,
      { method: "POST", body: JSON.stringify(payload) }
    ),
  playbooks: () => request<{ items: import("../types/workbench").PlaybookItem[] }>("/api/playbooks"),
  applyPlaybook: (caseId: string, playbookId: string) =>
    request<{ case_id: string; playbook: import("../types/workbench").PlaybookItem; applied_at: string }>(
      `/api/cases/${encodeURIComponent(caseId)}/apply-playbook`,
      { method: "POST", body: JSON.stringify({ playbook_id: playbookId }) }
    ),
  generateRfi: (caseId: string) =>
    request<{ case_id: string; corridors: string[]; markdown: string; generated_at: string }>(
      `/api/cases/${encodeURIComponent(caseId)}/rfi-packet`,
      { method: "POST", body: "{}" }
    ),
  pendingEscalations: () =>
    request<{ total: number; items: Array<Record<string, unknown>> }>("/api/cases/escalations/pending"),
  slaRadar: (warningHours = 8) =>
    request<import("../types/workbench").SlaRadarResponse>(`/api/cases/sla-radar?warning_hours=${warningHours}`),
  rebalanceQueue: (limit = 30) =>
    request<{ reassigned_count: number; analysts_pool: string[] }>("/api/cases/rebalance", {
      method: "POST",
      body: JSON.stringify({ limit }),
    }),
  suppressionRules: () =>
    request<{ items: import("../types/workbench").SuppressionRuleItem[] }>("/api/alerts/suppressions"),
  createSuppressionRule: (payload: {
    account_id: string;
    rule_id: string;
    max_amount: number;
    reason: string;
    days_valid?: number;
  }) =>
    request<import("../types/workbench").SuppressionRuleItem>("/api/alerts/suppressions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deactivateSuppressionRule: (id: string) =>
    request<{ deactivated: boolean }>(`/api/alerts/suppressions/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  capacityForecast: (payload: { growth_factor: number; hours_per_case: number; analysts_available: number }) =>
    request<import("../types/workbench").CapacityForecastResponse>("/api/analytics/capacity-forecast", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  thresholdSweep: (ruleId: string) =>
    request<import("../types/workbench").ThresholdSweepResponse>(
      `/api/evaluation/threshold-sweep?rule_id=${encodeURIComponent(ruleId)}`
    ),
  temporalDrift: (buckets = 6) =>
    request<import("../types/workbench").TemporalDriftResponse>(`/api/evaluation/temporal-drift?buckets=${buckets}`),
  calibrationProposals: () =>
    request<{ items: import("../types/workbench").CalibrationProposalItem[] }>("/api/risk/calibration-proposals"),
  createCalibrationProposal: (payload: {
    title: string;
    weights: Record<string, number>;
    simulation_summary: Record<string, unknown>;
  }) =>
    request<import("../types/workbench").CalibrationProposalItem>("/api/risk/calibration-proposal", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  approveCalibrationProposal: (proposalId: string, decision: "APPROVED" | "REJECTED") =>
    request<import("../types/workbench").CalibrationProposalItem>(
      `/api/risk/calibration-proposal/${encodeURIComponent(proposalId)}/approve`,
      { method: "POST", body: JSON.stringify({ decision }) }
    ),
  sandboxPattern: (payload: {
    min_amount?: number;
    max_amount?: number;
    channel?: string;
    txn_type?: string;
    country?: string;
    limit?: number;
  }) =>
    request<{ matched_txns: number; matched_volume: number; distinct_accounts: number; items: Array<Record<string, unknown>> }>(
      "/api/risk/sandbox-pattern",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  mergeCandidates: () =>
    request<{ total: number; items: import("../types/workbench").MergeCandidateItem[] }>("/api/cases/merge-candidates"),
  mergeCases: (payload: { primary_case_id: string; secondary_case_id: string; rationale?: string }) =>
    request<{ primary_case_id: string; secondary_case_id: string; migrated_alerts: number }>(
      "/api/cases/merge",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  notifications: () =>
    request<{ unread_count: number; items: import("../types/workbench").NotificationItem[] }>("/api/notifications"),
  markNotificationsRead: (notifId?: string) =>
    request<{ updated: number }>("/api/notifications/read", {
      method: "POST",
      body: JSON.stringify(notifId ? { notif_id: notifId } : {}),
    }),
  siemOutbox: () =>
    request<{ total: number; items: import("../types/workbench").SiemOutboxItem[] }>("/api/integrations/siem"),
  triggerSiemEvent: (payload: { event_type: string; severity: string; entity_id: string; payload?: Record<string, unknown> }) =>
    request<import("../types/workbench").SiemOutboxItem>("/api/integrations/siem", {
      method: "POST",
      body: JSON.stringify({ ...payload, dispatch_now: true }),
    }),
  pipelineJobs: () => request<{ items: import("../types/workbench").PipelineRunItem[] }>("/api/system/jobs"),
  runPipelineJob: (jobType: string) =>
    request<import("../types/workbench").PipelineRunItem>("/api/system/jobs", {
      method: "POST",
      body: JSON.stringify({ job_type: jobType }),
    }),
  complianceBundleUrl: () => "/api/reports/compliance-bundle",
  preferences: () => request<import("../types/workbench").UserPreferences>("/api/auth/preferences"),
  updatePreferences: (payload: Partial<import("../types/workbench").UserPreferences>) =>
    request<import("../types/workbench").UserPreferences>("/api/auth/preferences", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  assistantChat: (query: string) =>
    request<{
      reply: string;
      actions: Array<{ type: "tab" | "case" | "alert" | "txn" | "account" | "customer"; id: string; label: string }>;
      source: string;
    }>("/api/assistant/chat", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
  // Batch 10 & 11: Functions 226-275
  runSanctionsScreening: (payload: { entity_type?: string; entity_id?: string; query_name: string; country_code?: string }) =>
    request<import("../types/workbench").SanctionsScreeningItem>("/api/screening/sanctions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  screeningHistory: (entityId?: string) =>
    request<{ items: import("../types/workbench").SanctionsScreeningItem[] }>(
      `/api/screening/history?${buildQS({ entity_id: entityId })}`
    ),
  fanHubs: () => request<{ total: number; items: import("../types/workbench").FanHubItem[] }>("/api/network/fan-hubs"),
  customerChronology: (customerId: string) =>
    request<{ customer_id: string; items: import("../types/workbench").CustomerChronologyItem[] }>(
      `/api/customers/${encodeURIComponent(customerId)}/chronology`
    ),
  customerCorridorExposure: (customerId: string) =>
    request<{ customer_id: string; total_volume: number; corridors: Array<{ country: string; txn_count: number; volume: number; share_pct: number }> }>(
      `/api/customers/${encodeURIComponent(customerId)}/corridor-exposure`
    ),
  accountBurstProfile: (accountId: string) =>
    request<import("../types/workbench").AccountBurstProfile>(`/api/accounts/${encodeURIComponent(accountId)}/burst-profile`),
  accountTransferMatrix: (accountId: string) =>
    request<{ account_id: string; counterparties: Array<Record<string, unknown>> }>(
      `/api/accounts/${encodeURIComponent(accountId)}/transfer-matrix`
    ),
  generateGoamlXml: (caseId: string) =>
    request<{ case_id: string; xml: string; indicator_count: number }>(`/api/cases/${encodeURIComponent(caseId)}/goaml-xml`, {
      method: "POST",
      body: "{}",
    }),
  caseHandoffs: (caseId: string) =>
    request<{ case_id: string; items: Array<Record<string, unknown>> }>(`/api/cases/${encodeURIComponent(caseId)}/handoffs`),
  addCaseHandoff: (caseId: string, payload: { to_analyst: string; summary: string; pending_actions?: string }) =>
    request<Record<string, unknown>>(`/api/cases/${encodeURIComponent(caseId)}/handoff`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  sealCaseEvidence: (caseId: string) =>
    request<Record<string, unknown>>(`/api/cases/${encodeURIComponent(caseId)}/evidence-seal`, {
      method: "POST",
      body: "{}",
    }),
  caseSeals: (caseId: string) =>
    request<{ case_id: string; items: Array<Record<string, unknown>> }>(`/api/cases/${encodeURIComponent(caseId)}/seals`),
  bulkTagCases: (payload: { case_ids: string[]; tag: string; note?: string }) =>
    request<{ updated_count: number; tag: string }>("/api/cases/bulk-tag", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  reopenCase: (caseId: string, rationale: string) =>
    request<{ case_id: string; prev_status: string; new_status: string }>(`/api/cases/${encodeURIComponent(caseId)}/reopen`, {
      method: "POST",
      body: JSON.stringify({ rationale }),
    }),
  whatIfCaseScore: (caseId: string, waivedAlertIds: string[]) =>
    request<{ original_score: number; original_tier: string; projected_score: number; projected_tier: string; waived_count: number }>(
      `/api/cases/${encodeURIComponent(caseId)}/what-if-score`,
      { method: "POST", body: JSON.stringify({ waived_alert_ids: waivedAlertIds }) }
    ),
  compareCases: (caseIdA: string, caseIdB: string) =>
    request<Record<string, unknown>>(`/api/cases/${encodeURIComponent(caseIdA)}/compare/${encodeURIComponent(caseIdB)}`),
  alertCoOccurrence: () => request<{ pairs: Array<{ rule_a: string; rule_b: string; co_customer_count: number }> }>("/api/alerts/co-occurrence"),
  alertFatigue: () => request<{ items: Array<Record<string, unknown>> }>("/api/alerts/fatigue-report"),
  sharedPiiClusters: () => request<{ total: number; items: Array<Record<string, unknown>> }>("/api/customers/shared-pii"),
  mccOutliers: () => request<{ total: number; items: Array<Record<string, unknown>> }>("/api/analytics/mcc-outliers"),
  balanceContinuity: () => request<{ total_breaks: number; items: Array<Record<string, unknown>> }>("/api/quarantine/balance-continuity"),
  quarantineGrouped: () => request<{ total_groups: number; items: Array<Record<string, unknown>> }>("/api/quarantine/grouped"),
  deviceVelocity: () => request<{ total: number; items: Array<Record<string, unknown>> }>("/api/network/device-velocity"),
  customRules: () => request<{ items: Array<Record<string, unknown>> }>("/api/risk/custom-rules"),
  createCustomRule: (payload: { name: string; min_amount: number; channel: string; country_code: string; description: string }) =>
    request<Record<string, unknown>>("/api/risk/custom-rules", { method: "POST", body: JSON.stringify(payload) }),
  qaSamples: () => request<{ items: import("../types/workbench").QaSampleItem[] }>("/api/governance/qa-samples"),
  submitQaGrade: (caseId: string, payload: { grade: string; score: number; feedback: string }) =>
    request<Record<string, unknown>>(`/api/governance/qa-samples/${encodeURIComponent(caseId)}/grade`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runSlaAutoEscalate: (maxEscalations = 10) =>
    request<{ escalated_count: number; case_ids: string[] }>("/api/cases/sla-auto-escalate", {
      method: "POST",
      body: JSON.stringify({ max_escalations: maxEscalations }),
    }),
  webhooks: () => request<{ items: import("../types/workbench").WebhookEndpointItem[] }>("/api/integrations/webhooks"),
  createWebhook: (payload: { name: string; target_url: string }) =>
    request<import("../types/workbench").WebhookEndpointItem>("/api/integrations/webhooks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  testWebhook: (webhookId: string) =>
    request<import("../types/workbench").WebhookEndpointItem>(`/api/integrations/webhooks/${encodeURIComponent(webhookId)}/test`, {
      method: "POST",
      body: "{}",
    }),
  deleteWebhook: (webhookId: string) =>
    request<{ deleted: boolean }>(`/api/integrations/webhooks/${encodeURIComponent(webhookId)}`, { method: "DELETE" }),
  verifyAuditChain: () =>
    request<{ verified: boolean; events_checked: number; monotonic_timestamps: boolean; chain_sha256: string; checked_at: string }>(
      "/api/audit/verify-chain"
    ),
  evaluationLiftCurve: () =>
    request<{ total_cases: number; total_tp: number; deciles: import("../types/workbench").LiftCurveDecile[] }>("/api/evaluation/lift-curve"),
  evaluationScoreHistogram: () =>
    request<{ bins: Array<{ range: string; tp: number; fp: number }> }>("/api/evaluation/score-histogram"),
  evaluationTypologySeverityMatrix: () =>
    request<{ rows: Array<Record<string, unknown>> }>("/api/evaluation/typology-severity-matrix"),
  evaluationRuleMarginalLift: () =>
    request<{ total_tp_cases: number; items: Array<Record<string, unknown>> }>("/api/evaluation/rule-marginal-lift"),
  evaluationFeaturePsi: () =>
    request<{ features: import("../types/workbench").FeaturePsiItem[] }>("/api/evaluation/feature-psi"),
  dataScorecard: () =>
    request<{ tables: Array<{ table: string; row_count: number; status: string }>; sqlite_index_count: number; overall_health: string }>(
      "/api/system/data-scorecard"
    ),
  systemTelemetry: () =>
    request<{ routes: Array<{ route: string; hits: number; errors: number; avg_ms: number; max_ms: number }> }>("/api/system/telemetry"),
  retentionStatus: () =>
    request<{ policy: Record<string, unknown>; dry_run_eligible_alerts: number; dry_run_eligible_sessions: number }>("/api/system/retention"),
  updateRetention: (payload: { alerts_days: number; sessions_days: number; exports_days: number }) =>
    request<Record<string, unknown>>("/api/system/retention", { method: "POST", body: JSON.stringify(payload) }),
  examReadiness: () => request<{ items: import("../types/workbench").ExamControlItem[] }>("/api/governance/exam-readiness"),
  updateExamControl: (payload: { control_id: string; status: string; note: string }) =>
    request<import("../types/workbench").ExamControlItem>("/api/governance/exam-readiness", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  workspacePins: () => request<{ items: import("../types/workbench").WorkspacePinItem[] }>("/api/workspace/pinned-entities"),
  addWorkspacePin: (payload: { entity_type: string; entity_id: string; label: string }) =>
    request<import("../types/workbench").WorkspacePinItem>("/api/workspace/pinned-entities", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteWorkspacePin: (pinId: string) =>
    request<{ deleted: boolean }>(`/api/workspace/pinned-entities/${encodeURIComponent(pinId)}`, { method: "DELETE" }),
  customersExportUrl: (fmt: "csv" | "json", params: Record<string, string | undefined>) =>
    `/api/customers/export?${buildQS({ ...params, format: fmt })}`,
  accountsExportUrl: (fmt: "csv" | "json", params: Record<string, string | undefined>) =>
    `/api/accounts/export?${buildQS({ ...params, format: fmt })}`,
};
