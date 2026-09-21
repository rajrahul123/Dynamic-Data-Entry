import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError, forgotPassword } from '../lib/api'
import { useAuth } from '../lib/auth-context'

function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [forgotOpen, setForgotOpen] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [forgotSubmitting, setForgotSubmitting] = useState(false)
  const [forgotError, setForgotError] = useState<string | null>(null)
  const [forgotSent, setForgotSent] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard'
  const registered = (location.state as { registered?: boolean } | null)?.registered ?? false
  const reset = (location.state as { reset?: boolean } | null)?.reset ?? false

  if (user) {
    return <Navigate to={from} replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  function openForgotModal() {
    setForgotEmail('')
    setForgotError(null)
    setForgotSent(false)
    setForgotOpen(true)
  }

  function closeForgotModal() {
    if (forgotSubmitting) return
    setForgotOpen(false)
  }

  async function handleForgotSubmit(event: FormEvent) {
    event.preventDefault()
    setForgotSubmitting(true)
    setForgotError(null)
    try {
      await forgotPassword(forgotEmail.trim())
      setForgotSent(true)
    } catch (err) {
      setForgotError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : String(err))
    } finally {
      setForgotSubmitting(false)
    }
  }

  const inputClass =
    'mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none'

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Dynamic Data Entry Platform
        </h1>
        <p className="mt-1 text-sm text-slate-500">Sign in to continue</p>

        {registered && (
          <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            Account created successfully. Please sign in with your new account.
          </p>
        )}
        {reset && (
          <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            Password reset successfully. Please sign in with your new password.
          </p>
        )}

        <label className="mt-6 block text-xs font-medium text-slate-600" htmlFor="username">
          Username or email
        </label>
        <input
          id="username"
          type="text"
          required
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          className={inputClass}
        />

        <div className="mt-4 flex items-baseline justify-between">
          <label className="block text-xs font-medium text-slate-600" htmlFor="password">
            Password
          </label>
          <button
            type="button"
            onClick={openForgotModal}
            className="text-xs font-medium text-slate-500 underline-offset-4 hover:text-slate-900 hover:underline"
          >
            Forgot password?
          </button>
        </div>
        <input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className={inputClass}
        />

        {error && (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          No account?{' '}
          <Link
            to="/register"
            className="font-medium text-slate-900 underline-offset-4 hover:underline"
          >
            Create Account
          </Link>
        </p>
      </form>

      {forgotOpen && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/50 px-6"
          onClick={closeForgotModal}
        >
          <form
            onSubmit={handleForgotSubmit}
            noValidate
            className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-lg"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="text-lg font-bold tracking-tight text-slate-900">Forgot password</h2>
            <p className="mt-1 text-sm text-slate-500">
              Enter your account email and we will send you a reset link.
            </p>

            {!forgotSent ? (
              <>
                <label className="mt-5 block text-xs font-medium text-slate-600" htmlFor="forgotEmail">
                  Email
                </label>
                <input
                  id="forgotEmail"
                  type="email"
                  required
                  autoComplete="email"
                  value={forgotEmail}
                  onChange={(event) => setForgotEmail(event.target.value)}
                  className={inputClass}
                />

                {forgotError && (
                  <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                    {forgotError}
                  </p>
                )}

                <div className="mt-6 flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={closeForgotModal}
                    disabled={forgotSubmitting}
                    className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={forgotSubmitting}
                    className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                  >
                    {forgotSubmitting ? 'Sending…' : 'Send Reset Link'}
                  </button>
                </div>
              </>
            ) : (
              <p className="mt-5 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                If an account exists for that email, a password reset link has been sent.
              </p>
            )}
          </form>
        </div>
      )}
    </main>
  )
}

export default LoginPage