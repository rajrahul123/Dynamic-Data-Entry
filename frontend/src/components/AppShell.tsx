import { useState, type FormEvent } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { ApiError, changePassword } from '../lib/api'
import { useAuth } from '../lib/auth-context'

function navLinkClass({ isActive }: { isActive: boolean }) {
  return [
    'rounded-lg px-3 py-2 text-sm font-medium transition-colors',
    isActive ? 'bg-white text-slate-900' : 'text-slate-300 hover:bg-slate-700 hover:text-white',
  ].join(' ')
}

interface PasswordFieldErrors {
  currentPassword?: string
  newPassword?: string
  confirmPassword?: string
}

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordErrors, setPasswordErrors] = useState<PasswordFieldErrors>({})
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordSaved, setPasswordSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (!user) return null

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  function validatePasswordForm(): PasswordFieldErrors {
    const next: PasswordFieldErrors = {}
    if (!currentPassword) next.currentPassword = 'Current password is required.'
    if (newPassword.length < 8) {
      next.newPassword = 'New password must be at least 8 characters long.'
    }
    if (confirmPassword !== newPassword) {
      next.confirmPassword = 'Passwords do not match.'
    }
    return next
  }

  async function handleChangePassword(event: FormEvent) {
    event.preventDefault()
    const next = validatePasswordForm()
    setPasswordErrors(next)
    if (Object.values(next).some(Boolean)) return

    setSubmitting(true)
    setPasswordError(null)
    setPasswordSaved(false)
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setPasswordSaved(true)
      window.setTimeout(() => setPasswordModalOpen(false), 1200)
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  function closePasswordModal() {
    if (submitting) return
    setPasswordModalOpen(false)
    setPasswordError(null)
    setPasswordSaved(false)
  }

  const passwordInputClass =
    'mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none'

  return (
    <div className="min-h-screen">
      <nav className="bg-slate-800 text-slate-100">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-6 py-3">
          <span className="text-sm font-semibold tracking-tight">
            Dynamic Data Entry Platform
          </span>
          <div className="flex flex-1 items-center gap-1">
            <NavLink to="/dashboard" className={navLinkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/records" className={navLinkClass}>
              Records
            </NavLink>
            {user.role === 'admin' && (
              <>
                <NavLink to="/forms" className={navLinkClass}>
                  Forms
                </NavLink>
                <NavLink to="/users" className={navLinkClass}>
                  Users
                </NavLink>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400">
              {user.full_name || user.username}
              <span className="ml-1 rounded bg-slate-700 px-1.5 py-0.5 text-[10px] uppercase text-slate-200">
                {user.role}
              </span>
            </span>
            <button
              type="button"
              onClick={() => setPasswordModalOpen(true)}
              className="rounded-lg bg-slate-700 px-3 py-1.5 text-sm font-medium text-slate-100 hover:bg-slate-600"
            >
              Change Password
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg bg-slate-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-500"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>

      {passwordModalOpen && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/50 px-6"
          onClick={closePasswordModal}
        >
          <form
            onSubmit={handleChangePassword}
            noValidate
            className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-lg"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="text-lg font-bold tracking-tight text-slate-900">Change password</h2>
            <p className="mt-1 text-sm text-slate-500">Update the password for {user.username}.</p>

            <label className="mt-5 block text-xs font-medium text-slate-600" htmlFor="currentPassword">
              Current password
            </label>
            <input
              id="currentPassword"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              className={passwordInputClass}
            />
            {passwordErrors.currentPassword && (
              <p className="mt-1 text-xs text-red-600">{passwordErrors.currentPassword}</p>
            )}

            <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="newPassword">
              New password
            </label>
            <input
              id="newPassword"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className={passwordInputClass}
            />
            {passwordErrors.newPassword && (
              <p className="mt-1 text-xs text-red-600">{passwordErrors.newPassword}</p>
            )}

            <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="confirmPassword">
              Confirm new password
            </label>
            <input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className={passwordInputClass}
            />
            {passwordErrors.confirmPassword && (
              <p className="mt-1 text-xs text-red-600">{passwordErrors.confirmPassword}</p>
            )}

            {passwordError && (
              <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {passwordError}
              </p>
            )}
            {passwordSaved && (
              <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                Password updated successfully.
              </p>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={closePasswordModal}
                disabled={submitting}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
              >
                {submitting ? 'Updating…' : 'Update Password'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}