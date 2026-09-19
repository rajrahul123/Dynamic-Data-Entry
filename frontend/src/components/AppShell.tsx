import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../lib/auth-context'

function navLinkClass({ isActive }: { isActive: boolean }) {
  return [
    'rounded-lg px-3 py-2 text-sm font-medium transition-colors',
    isActive ? 'bg-white text-slate-900' : 'text-slate-300 hover:bg-slate-700 hover:text-white',
  ].join(' ')
}

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

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
    </div>
  )
}