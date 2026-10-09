import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { AuthShell } from '../components/AuthShell'
import { PasswordField } from '../components/PasswordField'
import { useAuth } from '../lib/auth-context'
import { useToast } from '../lib/toast-context'

function LoginPage() {
  const { user, login } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard'
  const registered = (location.state as { registered?: boolean } | null)?.registered ?? false
  const reset = (location.state as { reset?: boolean } | null)?.reset ?? false

  if (user) {
    return <Navigate to={from} replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!username.trim() || !password) return
    setSubmitting(true)
    setError(null)
    try {
      await login(username.trim(), password)
      toast('success', 'Signed in successfully.')
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <div className="card p-8 shadow-xl ring-1 ring-white/10">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Welcome back</h1>
        <p className="mt-1 text-sm text-slate-500">Sign in to continue to your workspace.</p>

        {registered && (
          <p className="banner-success mt-4">Account created. Please sign in.</p>
        )}
        {reset && (
          <p className="banner-success mt-4">Password reset. Please sign in.</p>
        )}

        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
          <div>
            <label className="label" htmlFor="username">
              Email or Username
            </label>
            <input
              id="username"
              type="text"
              required
              autoComplete="username"
              autoFocus
              placeholder="Email or Username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="input"
            />
          </div>

          <div>
            <div className="flex items-baseline justify-between">
              <label className="label" htmlFor="password">
                Password
              </label>
              <Link
                to="/reset-password"
                className="text-xs font-medium text-indigo-600 underline-offset-4 hover:text-indigo-500 hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <PasswordField
              id="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="input"
            />
          </div>

          {error && <p className="banner-error">{error}</p>}

          <button type="submit" disabled={submitting} className="btn btn-primary btn-lg w-full">
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          No account?{' '}
          <Link to="/register" className="link">
            Create Account
          </Link>
        </p>
      </div>
    </AuthShell>
  )
}

export default LoginPage