import React from "react";
import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { AlertQueuePage } from "./pages/AlertQueuePage";
import { AlertDetailPage } from "./pages/AlertDetailPage";
import { CaseListPage } from "./pages/CaseListPage";
import { CaseNewPage } from "./pages/CaseNewPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { TransactionsPage } from "./pages/TransactionsPage";
import { TransactionDetailPage } from "./pages/TransactionDetailPage";
import { ReportsPage } from "./pages/ReportsPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { AdminSettingsPage } from "./pages/AdminSettingsPage";
import { AdminModelsPage } from "./pages/AdminModelsPage";
import { AdminAuditPage } from "./pages/AdminAuditPage";
import { AccountPage } from "./pages/AccountPage";
import { NotFoundPage, ForbiddenPage } from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<OverviewPage />} />
        <Route
          path="/alerts"
          element={
            <ProtectedRoute roles={["analyst", "supervisor"]}>
              <AlertQueuePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/alerts/:id"
          element={
            <ProtectedRoute roles={["analyst", "supervisor"]}>
              <AlertDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cases"
          element={
            <ProtectedRoute roles={["analyst", "supervisor", "admin"]}>
              <CaseListPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cases/new"
          element={
            <ProtectedRoute roles={["analyst", "supervisor"]}>
              <CaseNewPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/cases/:id"
          element={
            <ProtectedRoute roles={["analyst", "supervisor", "admin"]}>
              <CaseDetailPage />
            </ProtectedRoute>
          }
        />
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        <Route
          path="/reports"
          element={
            <ProtectedRoute roles={["supervisor", "admin"]}>
              <ReportsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminUsersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/settings"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminSettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/models"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminModelsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/audit"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminAuditPage />
            </ProtectedRoute>
          }
        />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/forbidden" element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
