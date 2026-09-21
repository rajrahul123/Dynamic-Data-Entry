import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AuthProvider } from './lib/auth'
import DashboardPage from './pages/DashboardPage'
import { FormBuilderPage } from './pages/FormBuilderPage'
import FormCreatePage from './pages/FormCreatePage'
import { FormsPage } from './pages/FormsPage'
import LoginPage from './pages/LoginPage'
import { RecordDetailPage } from './pages/RecordDetailPage'
import { RecordEditPage } from './pages/RecordEditPage'
import { RecordsIndexPage } from './pages/RecordsIndexPage'
import { RecordsPage } from './pages/RecordsPage'
import RegistrationPage from './pages/RegistrationPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import { SubmissionPage } from './pages/SubmissionPage'
import { UsersPage } from './pages/UsersPage'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegistrationPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route
              path="/users"
              element={
                <ProtectedRoute requireAdmin>
                  <UsersPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/forms"
              element={
                <ProtectedRoute requireAdmin>
                  <FormsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/forms/new"
              element={
                <ProtectedRoute requireAdmin>
                  <FormCreatePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/forms/:id/edit"
              element={
                <ProtectedRoute requireAdmin>
                  <FormBuilderPage />
                </ProtectedRoute>
              }
            />
            <Route path="/forms/:id/submit" element={<SubmissionPage />} />
            <Route path="/records" element={<RecordsIndexPage />} />
            <Route path="/forms/:id/records" element={<RecordsPage />} />
            <Route
              path="/forms/:id/records/:submissionId"
              element={<RecordDetailPage />}
            />
            <Route
              path="/forms/:id/records/:submissionId/edit"
              element={<RecordEditPage />}
            />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App