import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError, resetPassword } from '../lib/api'
import { useAuth } from '../lib/auth-context'

interface FieldErrors {
  newPassword?: string
  confirmPassword?: string
}

function ResetPasswordPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) {
    return <Navigate to="/dashboard" replace />
  }

  function validate(): FieldErrors {
    const next: FieldErrors = {}
    if (newPassword.length < 8) {
      next.newPassword = 'Password must be at least 8 characters long.'
    }
    if (confirmPassword !== newPassword) {
      next.confirmPassword = 'Passwords do not match.'
    }
    return next
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const next = validate()
    setErrors(next)
    if (Object.values(next).some(Boolean)) return

    setSubmitting(true)
    setError(null)
    try {
      await resetPassword(token, newPassword)
      setNewPassword('')
      setConfirmPassword('')
      navigate('/login', { replace: true, state: { reset: true } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const inputClass =
    'mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none'

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      {!token ? (
        <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Reset password</h1>
          <p className="mt-3 text-sm text-slate-600">
            This reset link is missing its token. Use the link from your email, or request a new
            one.
          </p>
          <Link
            to="/login"
            className="mt-6 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Back to Sign in
          </Link>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit}
          noValidate
          className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
        >
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Set a new password</h1>
          <p className="mt-1 text-sm text-slate-500">
            Choose a new password for your account.
          </p>

          <label className="mt-6 block text-xs font-medium text-slate-600" htmlFor="newPassword">
            New password
          </label>
          <input
            id="newPassword"
            type="password"
            required
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-slate-500">At least 8 characters.</p>
          {errors.newPassword && <p className="mt-1 text-xs text-red-600">{errors.newPassword}</p>}

          <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="confirmPassword">
            Confirm new password
          </label>
          <input
            id="confirmPassword"
            type="password"
            required
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            className={inputClass}
          />
          {errors.confirmPassword && (
            <p className="mt-1 text-xs text-red-600">{errors.confirmPassword}</p>
          )}

          {error && (
            <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? 'Resetting…' : 'Reset Password'}
          </button>

          <p className="mt-4 text-center text-sm text-slate-500">
            Remembered it?{' '}
            <Link
              to="/login"
              className="font-medium text-slate-900 underline-offset-4 hover:underline"
            >
              Sign in
            </Link>
          </p>
        </form>
      )}
    </main>
  )
}

export default ResetPasswordPage