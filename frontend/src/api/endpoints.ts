import { apiClient } from "./client";
import type {
  AdminUserOut,
  AlertDetail,
  AlertOut,
  AuditLogOut,
  CaseDetail,
  CaseOut,
  DashboardSummary,
  DashboardTrends,
  ModelVersionOut,
  NotificationOut,
  Page,
  SettingsOut,
  TransactionDetail,
  TransactionOut,
  User,
} from "./types";

// --- Auth ---
export async function login(email: string, password: string) {
  const { data } = await apiClient.post<{ access_token: string; expires_in: number; user: User }>("/auth/login", {
    email,
    password,
  });
  return data;
}
export async function me() {
  const { data } = await apiClient.get<User>("/auth/me");
  return data;
}
export async function changePassword(current_password: string, new_password: string) {
  await apiClient.post("/auth/change-password", { current_password, new_password });
}

// --- Dashboard ---
export async function getDashboardSummary() {
  const { data } = await apiClient.get<DashboardSummary>("/dashboard/summary");
  return data;
}
export async function getDashboardTrends(days = 30) {
  const { data } = await apiClient.get<DashboardTrends>("/dashboard/trends", { params: { days } });
  return data;
}

// --- Alerts ---
export async function listAlerts(params: Record<string, any>) {
  const { data } = await apiClient.get<Page<AlertOut>>("/alerts", { params });
  return data;
}
export async function getAlert(id: string) {
  const { data } = await apiClient.get<AlertDetail>(`/alerts/${id}`);
  return data;
}
export async function dismissAlert(id: string, reason: string) {
  await apiClient.post(`/alerts/${id}/dismiss`, { reason });
}
export async function openCaseFromAlert(id: string) {
  const { data } = await apiClient.post<{ case_id: string; case_number: string }>(`/alerts/${id}/open-case`);
  return data;
}

// --- Cases ---
export async function listCases(params: Record<string, any>) {
  const { data } = await apiClient.get<Page<CaseOut>>("/cases", { params });
  return data;
}
export async function getCase(id: string) {
  const { data } = await apiClient.get<CaseDetail>(`/cases/${id}`);
  return data;
}
export async function createCase(payload: Record<string, any>) {
  const { data } = await apiClient.post<CaseOut>("/cases", payload);
  return data;
}
export async function assignCase(id: string, user_id: string) {
  const { data } = await apiClient.post<CaseOut>(`/cases/${id}/assign`, { user_id });
  return data;
}
export async function transitionCase(id: string, payload: Record<string, any>) {
  const { data } = await apiClient.post<CaseOut>(`/cases/${id}/transition`, payload);
  return data;
}
export async function addCaseNote(id: string, note: string) {
  await apiClient.post(`/cases/${id}/notes`, { note });
}
export async function uploadAttachment(id: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  await apiClient.post(`/cases/${id}/attachments`, form, { headers: { "Content-Type": "multipart/form-data" } });
}
export function attachmentDownloadUrl(caseId: string, attachmentId: string) {
  return `/cases/${caseId}/attachments/${attachmentId}`;
}
export async function listAssignableUsers() {
  const { data } = await apiClient.get<{ user_id: string; full_name: string; role: string }[]>(
    "/cases/meta/assignable-users"
  );
  return data;
}
export async function getCaseHistory(id: string) {
  const { data } = await apiClient.get<any[]>(`/cases/${id}/history`);
  return data;
}

// --- Transactions ---
export async function listTransactions(params: Record<string, any>) {
  const { data } = await apiClient.get<Page<TransactionOut>>("/transactions", { params });
  return data;
}
export async function getTransaction(id: string) {
  const { data } = await apiClient.get<TransactionDetail>(`/transactions/${id}`);
  return data;
}
export async function releaseTransaction(id: string, reason: string) {
  await apiClient.post(`/transactions/${id}/release`, { reason });
}
export async function declineTransaction(id: string, reason: string) {
  await apiClient.post(`/transactions/${id}/decline`, { reason });
}

// --- Notifications ---
export async function listNotifications(unread = false) {
  const { data } = await apiClient.get<NotificationOut[]>("/notifications", { params: { unread } });
  return data;
}
export async function markNotificationRead(id: string) {
  await apiClient.post(`/notifications/${id}/read`);
}
export async function markAllNotificationsRead() {
  await apiClient.post("/notifications/read-all");
}

// --- Admin ---
export async function listUsers(params: Record<string, any> = {}) {
  const { data } = await apiClient.get<Page<AdminUserOut>>("/admin/users", { params });
  return data;
}
export async function createUser(payload: Record<string, any>) {
  const { data } = await apiClient.post<AdminUserOut>("/admin/users", payload);
  return data;
}
export async function updateUser(id: string, payload: Record<string, any>) {
  const { data } = await apiClient.patch<AdminUserOut>(`/admin/users/${id}`, payload);
  return data;
}
export async function resetUserPassword(id: string) {
  const { data } = await apiClient.post<{ temporary_password: string }>(`/admin/users/${id}/reset-password`);
  return data;
}
export async function getSettings() {
  const { data } = await apiClient.get<SettingsOut>("/admin/settings");
  return data;
}
export async function updateSettings(payload: Partial<SettingsOut>) {
  const { data } = await apiClient.put<SettingsOut>("/admin/settings", payload);
  return data;
}
export async function listModels() {
  const { data } = await apiClient.get<ModelVersionOut[]>("/admin/models");
  return data;
}
export async function activateModel(id: string) {
  await apiClient.post(`/admin/models/${id}/activate`);
}
export async function listAuditLogs(params: Record<string, any>) {
  const { data } = await apiClient.get<Page<AuditLogOut>>("/admin/audit-logs", { params });
  return data;
}

// --- Reports ---
export function reportUrl(kind: "cases" | "alerts" | "fraud-summary" | "nibss-incidents", params: Record<string, any>) {
  const search = new URLSearchParams(params as any).toString();
  return `/reports/${kind}${search ? `?${search}` : ""}`;
}
