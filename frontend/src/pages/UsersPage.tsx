import { useCallback, useEffect, useState, type FormEvent } from 'react'

import {
  createUser,
  listUsers,
  updateUser,
  type Role,
  type User,
} from '../lib/api'

const ROLES: Role[] = ['admin', 'operator', 'viewer']

const EMPTY_FORM = {
  username: '',
  email: '',
  full_name: '',
  password: '',
  role: 'viewer' as Role,
}

function roleBadgeClass(role: Role) {
  if (role === 'admin') return 'bg-slate-900 text-white'
  if (role === 'operator') return 'bg-slate-600 text-white'
  return 'bg-slate-200 text-slate-700'
}

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setUsers(await listUsers())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadUsers() {
      try {
        const data = await listUsers()
        if (!cancelled) setUsers(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadUsers()
    return () => {
      cancelled = true
    }
  }, [])

  function setField(field: keyof typeof EMPTY_FORM, value: string) {
    setForm((previous) => ({ ...previous, [field]: value }))
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setCreating(true)
    setError(null)
    setNotice(null)
    try {
      await createUser({
        username: form.username,
        email: form.email,
        password: form.password,
        full_name: form.full_name || null,
        role: form.role,
      })
      setForm(EMPTY_FORM)
      setNotice(`User ${form.username} created.`)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setCreating(false)
    }
  }

  async function handleChangeRole(userId: number, role: Role) {
    setError(null)
    setNotice(null)
    try {
      await updateUser(userId, { role })
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleToggleActive(user: User) {
    setError(null)
    setNotice(null)
    try {
      await updateUser(user.id, { is_active: !user.is_active })
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">User management</h2>
        <p className="mt-1 text-sm text-slate-600">
          Admin-only. Create accounts and manage roles and status.
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-900">Create user</h3>
        <form onSubmit={handleCreate} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-5">
          <input
            type="text"
            required
            minLength={3}
            placeholder="Username"
            value={form.username}
            onChange={(event) => setField('username', event.target.value)}
            className="col-span-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
          <input
            type="email"
            required
            placeholder="Email"
            value={form.email}
            onChange={(event) => setField('email', event.target.value)}
            className="col-span-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
          <input
            type="text"
            placeholder="Full name (optional)"
            value={form.full_name}
            onChange={(event) => setField('full_name', event.target.value)}
            className="col-span-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
          <input
            type="password"
            required
            minLength={8}
            placeholder="Password"
            value={form.password}
            onChange={(event) => setField('password', event.target.value)}
            className="col-span-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
          <div className="col-span-1 flex items-center gap-2">
            <select
              value={form.role}
              onChange={(event) => setForm((previous) => ({ ...previous, role: event.target.value as Role }))}
              className="rounded-lg border border-slate-300 px-2 py-2 text-sm focus:border-slate-500 focus:outline-none"
            >
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={creating}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {creating ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </section>

      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}
      {notice && (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>
      )}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
              <th className="px-4 py-3 font-medium">User</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  Loading users…
                </td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{user.username}</div>
                    <div className="text-xs text-slate-500">{user.full_name || '—'}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{user.email}</td>
                  <td className="px-4 py-3">
                    <select
                      value={user.role}
                      onChange={(event) => handleChangeRole(user.id, event.target.value as Role)}
                      className={`rounded-lg px-2 py-1 text-xs font-medium ${roleBadgeClass(user.role)}`}
                    >
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        user.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {user.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleToggleActive(user)}
                      className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      {user.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  )
}