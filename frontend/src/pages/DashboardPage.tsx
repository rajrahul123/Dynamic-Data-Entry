import { useAuth } from '../lib/auth-context'
import { HealthStatus } from '../components/HealthStatus'

function DashboardPage() {
  const { user } = useAuth()

  if (!user) return null

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Welcome, {user.full_name || user.username}
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Signed in as <span className="font-medium">{user.username}</span> · {user.email}
        </p>
      </header>

      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Name</dt>
          <dd className="mt-1 text-sm font-medium text-slate-900">{user.full_name || '—'}</dd>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Role</dt>
          <dd className="mt-1 text-sm font-medium capitalize text-slate-900">{user.role}</dd>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Account</dt>
          <dd className="mt-1 text-sm font-medium text-slate-900">
            {user.is_active ? 'Active' : 'Disabled'}
          </dd>
        </div>
      </dl>

      <HealthStatus />
    </div>
  )
}

export default DashboardPage