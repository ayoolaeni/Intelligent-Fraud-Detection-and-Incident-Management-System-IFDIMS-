export type Role = "analyst" | "supervisor" | "admin";

export interface User {
  user_id: string;
  full_name: string;
  email: string;
  role: Role;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface TopFactor {
  feature: string;
  label: string;
  raw_value: number | string;
  contribution: number;
  description: string;
}

export interface TransactionOut {
  txn_id: string;
  txn_ref: string;
  account_number_masked: string;
  amount: string;
  channel: string;
  txn_type: string;
  txn_time: string;
  location: string;
  status: string;
  fraud_score: number | null;
  risk_band: "low" | "medium" | "high" | null;
}

export interface CustomerSummary {
  customer_id: string;
  full_name: string;
  phone_masked: string;
  risk_profile: string;
  account_age_days: number;
}

export interface TransactionDetail {
  txn: TransactionOut;
  prediction: { fraud_score: number; risk_band: string; top_factors: TopFactor[]; features: Record<string, number> } | null;
  alert_id: string | null;
  case_id: string | null;
  case_number: string | null;
  customer: CustomerSummary | null;
  recent_transactions: TransactionOut[];
}

export interface AlertOut {
  alert_id: string;
  txn_id: string;
  account_number_masked: string;
  channel: string;
  amount: string;
  fraud_score: number;
  risk_band: "low" | "medium" | "high";
  severity: "medium" | "high";
  status: "OPEN" | "DISMISSED" | "CASE_OPENED";
  created_at: string;
  case_id: string | null;
}

export interface AlertDetail {
  alert: AlertOut;
  txn: TransactionOut;
  top_factors: TopFactor[];
  customer: CustomerSummary | null;
  recent_transactions: TransactionOut[];
}

export type CaseStatus = "NEW" | "ASSIGNED" | "UNDER_INVESTIGATION" | "ESCALATED" | "RESOLVED" | "CLOSED";
export type CasePriority = "critical" | "high" | "medium" | "low";

export interface CaseOut {
  case_id: string;
  case_number: string;
  title: string;
  source: string;
  priority: CasePriority;
  status: CaseStatus;
  outcome: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  amount_at_risk: string;
  amount_recovered: string;
  opened_at: string;
  ack_due_at: string;
  resolve_due_at: string;
  closed_at: string | null;
  sla_state: "ok" | "due_soon" | "breached";
}

export interface CaseNoteOut {
  note_id: string;
  user_id: string | null;
  user_name: string | null;
  note: string;
  note_type: string;
  created_at: string;
}

export interface CaseAttachmentOut {
  attachment_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: string | null;
  created_at: string;
}

export interface CaseDetail {
  case: CaseOut;
  description: string;
  alert_id: string | null;
  txn_id: string | null;
  account_number_masked: string | null;
  fraud_type: string | null;
  notes: CaseNoteOut[];
  attachments: CaseAttachmentOut[];
  allowed_transitions: string[];
  can_assign: boolean;
  can_release_decline: boolean;
}

export interface DashboardSummary {
  open_alerts: Record<string, number>;
  open_cases_by_priority: Record<string, number>;
  cases_breaching_sla: number;
  cases_due_soon: number;
  transactions_today: number;
  held_transactions: number;
  confirmed_fraud_value_30d: string;
  false_positive_rate_30d: number;
  avg_resolution_hours_30d: number;
}

export interface TrendPoint {
  date: string;
  transactions_scored: number;
  alerts_medium: number;
  alerts_high: number;
  cases_opened: number;
  confirmed_fraud_count: number;
  confirmed_fraud_value: string;
}

export interface DashboardTrends {
  daily: TrendPoint[];
  by_channel: Record<string, Record<string, number>>;
  top_fraud_types: { fraud_type: string; count: number }[];
}

export interface NotificationOut {
  notification_id: string;
  message: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AdminUserOut {
  user_id: string;
  full_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface SlaSetting {
  ack_minutes: number;
  resolve_minutes: number;
}

export interface SettingsOut {
  risk_threshold_medium: number;
  risk_threshold_high: number;
  critical_amount_ngn: number;
  sla: Record<string, SlaSetting>;
  auto_assign: boolean;
  hold_high_risk: boolean;
}

export interface ModelVersionOut {
  model_id: string;
  algorithm: string;
  version: string;
  metrics: Record<string, any>;
  deployed_on: string | null;
  is_active: boolean;
}

export interface AuditLogOut {
  log_id: string;
  user_id: string | null;
  actor: string;
  action: string;
  entity: string;
  entity_id: string;
  details: Record<string, any>;
  ip_address: string | null;
  timestamp: string;
}
