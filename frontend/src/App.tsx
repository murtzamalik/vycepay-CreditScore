import { Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import AuthGuard from './guards/AuthGuard';
import RoleGuard from './guards/RoleGuard';
import LoginPage from './pages/auth/LoginPage';
import DashboardPage from './pages/dashboard/DashboardPage';
import ScoreLookupPage from './pages/scores/ScoreLookupPage';
import ScoreDetailPage from './pages/scores/ScoreDetailPage';
import CustomersPage from './pages/admin/CustomersPage';
import UsersPage from './pages/admin/UsersPage';
import AuditLogsPage from './pages/admin/AuditLogsPage';
import SettingsPage from './pages/settings/SettingsPage';
import PartnerDashboard from './pages/partner/PartnerDashboard';
import PartnerScoreLookup from './pages/partner/PartnerScoreLookup';
import PartnerUsagePage from './pages/partner/PartnerUsagePage';
import PartnerApiKeysPage from './pages/partner/PartnerApiKeysPage';
import PartnerEmbedConfigPage from './pages/partner/PartnerEmbedConfigPage';
import ErrorBoundary from './components/common/ErrorBoundary';
import NotFoundPage from './pages/errors/NotFoundPage';

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes */}
        <Route element={<AuthGuard />}>
          {/* Root redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<DashboardPage />} />

            {/* Score routes - accessible by Admin, Operator, Partner */}
            <Route
              element={<RoleGuard allowedRoles={['Admin', 'Operator', 'Partner']} />}
            >
              <Route path="/scores/lookup" element={<ScoreLookupPage />} />
              <Route path="/scores/detail/:nationalId" element={<ScoreDetailPage />} />
            </Route>

            {/* Partner routes - Partner role only */}
            <Route element={<RoleGuard allowedRoles={['Partner']} />}>
              <Route path="/partner/dashboard" element={<PartnerDashboard />} />
              <Route path="/partner/scores" element={<PartnerScoreLookup />} />
              <Route path="/partner/usage" element={<PartnerUsagePage />} />
              <Route path="/partner/api-keys" element={<PartnerApiKeysPage />} />
              <Route path="/partner/embed-config" element={<PartnerEmbedConfigPage />} />
            </Route>

            {/* Customer management - Admin and Operator */}
            <Route
              element={<RoleGuard allowedRoles={['Admin', 'Operator']} />}
            >
              <Route path="/admin/customers" element={<CustomersPage />} />
            </Route>

            {/* User management - Admin only */}
            <Route element={<RoleGuard allowedRoles={['Admin']} />}>
              <Route path="/admin/users" element={<UsersPage />} />
            </Route>

            {/* Audit logs - Admin and Operator */}
            <Route
              element={<RoleGuard allowedRoles={['Admin', 'Operator']} />}
            >
              <Route path="/admin/audit-logs" element={<AuditLogsPage />} />
            </Route>

            {/* Settings - Admin and Operator */}
            <Route
              element={<RoleGuard allowedRoles={['Admin', 'Operator']} />}
            >
              <Route path="/settings" element={<SettingsPage />} />
            </Route>

            {/* Catch-all: 404 (inside auth guard and app shell) */}
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
