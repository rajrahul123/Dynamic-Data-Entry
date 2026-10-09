import { useEffect, useRef, useState, type FormEvent } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { ApiError, changePassword } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { useToast } from '../lib/toast-context'
import { PasswordField } from './PasswordField'
import {
  IconChevronDown,
  IconDashboard,
  IconForms,
  IconLogout,
  IconMenu,
  IconRecords,
  IconSettings,
  IconX,
} from './icons'

function navLinkClass({ isActive }: { isActive: boolean }) {
  return `nav-item ${isActive ? 'nav-item-active' : 'nav-item-idle'}`
}

function pageSubtitle(pathname: string): string {
  if (pathname.startsWith('/records')) return 'Records'
  if (pathname.startsWith('/forms/new')) return 'New form'
  if (pathname.startsWith('/forms')) return 'Forms'
  if (pathname.startsWith('/dashboard')) return 'Overview'
  return 'Workspace'
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2)
  return parts.map((part) => part.charAt(0).toUpperCase()).join('') || '?'
}

interface PasswordFieldErrors {
  currentPassword?: string
  newPassword?: string
  confirmPassword?: string
}

export function AppShell() {
  const { user, logout } = useAuth()
  const { toast } = useToast()
  const location = useLocation()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement | null>(null)

  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordErrors, setPasswordErrors] = useState<PasswordFieldErrors>({})
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordSaved, setPasswordSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!userMenuOpen) return
    function onPointerDown(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setUserMenuOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [userMenuOpen])

  if (!user) return null

  function handleLogout() {
    logout()
    window.location.assign('/login')
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
      toast('success', 'Password updated successfully.')
      window.setTimeout(() => setPasswordModalOpen(false), 900)
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

  const displayName = user.full_name || user.username

  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: IconDashboard },
    { to: '/forms', label: 'Forms', icon: IconForms },
    { to: '/records', label: 'Records', icon: IconRecords },
  ]

  const closeSidebar = () => setSidebarOpen(false)

  const sidebarContent = (
    <>
      <div className="flex h-16 items-center gap-2 px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white shadow-sm">
          D
        </span>
        <span className="text-sm font-bold tracking-tight text-slate-900">
          DataEntry Pro
        </span>
      </div>

      <nav className="mt-4 flex-1 space-y-1 px-3">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={navLinkClass}
            end={to === '/dashboard'}
            onClick={closeSidebar}
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  )

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-slate-200/70 bg-white lg:flex">
        {sidebarContent}
      </aside>

      {/* Mobile sidebar */}
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-slate-900/50 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <aside className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-slate-200 bg-white lg:hidden">
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setSidebarOpen(false)}
              className="absolute right-3 top-4 rounded-lg p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            >
              <IconX className="h-5 w-5" />
            </button>
            {sidebarContent}
          </aside>
        </>
      )}

      <div className="lg:pl-60">
        {/* Header */}
        <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/85 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6">
            <div className="flex items-center gap-3">
              <button
                type="button"
                aria-label="Open menu"
                onClick={() => setSidebarOpen(true)}
                className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
              >
                <IconMenu className="h-5 w-5" />
              </button>
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  {pageSubtitle(location.pathname)}
                </p>
                <p className="text-xs text-slate-500">Dynamic Data Entry Platform</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="relative" ref={userMenuRef}>
                <button
                  type="button"
                  onClick={() => setUserMenuOpen((open) => !open)}
                  className="flex items-center gap-2 rounded-lg px-1.5 py-1.5 transition-colors hover:bg-slate-100"
                  aria-haspopup="menu"
                  aria-expanded={userMenuOpen}
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                    {initials(displayName)}
                  </span>
                  <span className="hidden text-left md:block">
                    <span className="block text-xs font-semibold text-slate-900">
                      {displayName}
                    </span>
                    <span className="block text-[11px] text-slate-500">{user.email}</span>
                  </span>
                  <IconChevronDown className="hidden h-4 w-4 text-slate-400 md:block" />
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 z-30 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg">
                    <div className="border-b border-slate-100 px-3 py-3">
                      <p className="text-sm font-semibold text-slate-900">{displayName}</p>
                      <p className="truncate text-xs text-slate-500">{user.email}</p>
                    </div>
                    <div className="p-1">
                      <button
                        type="button"
                        className="dropdown-item"
                        onClick={() => {
                          setUserMenuOpen(false)
                          setPasswordModalOpen(true)
                        }}
                      >
                        <IconSettings className="h-4 w-4 text-slate-500" />
                        Change password
                      </button>
                      <button
                        type="button"
                        className="dropdown-item text-red-600 hover:bg-red-50 hover:text-red-700"
                        onClick={handleLogout}
                      >
                        <IconLogout className="h-4 w-4" />
                        Log out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <Outlet />
        </main>
      </div>

      {passwordModalOpen && (
        <div className="modal-backdrop" onClick={closePasswordModal}>
          <form
            onSubmit={handleChangePassword}
            noValidate
            className="modal max-w-sm"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="text-lg font-bold tracking-tight text-slate-900">Change password</h2>
            <p className="mt-1 text-sm text-slate-500">Update the password for {user.username}.</p>

            <label className="label mt-5" htmlFor="currentPassword">
              Current password
            </label>
            <PasswordField
              id="currentPassword"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              className="input"
            />
            {passwordErrors.currentPassword && (
              <p className="field-error">{passwordErrors.currentPassword}</p>
            )}

            <label className="label mt-4" htmlFor="newPassword">
              New password
            </label>
            <PasswordField
              id="newPassword"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className="input"
            />
            {passwordErrors.newPassword && (
              <p className="field-error">{passwordErrors.newPassword}</p>
            )}

            <label className="label mt-4" htmlFor="confirmPassword">
              Confirm new password
            </label>
            <PasswordField
              id="confirmPassword"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="input"
            />
            {passwordErrors.confirmPassword && (
              <p className="field-error">{passwordErrors.confirmPassword}</p>
            )}

            {passwordError && <p className="banner-error mt-4">{passwordError}</p>}
            {passwordSaved && (
              <p className="banner-success mt-4">Password updated successfully.</p>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={closePasswordModal}
                disabled={submitting}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button type="submit" disabled={submitting} className="btn btn-primary">
                {submitting ? 'Updating…' : 'Update password'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}