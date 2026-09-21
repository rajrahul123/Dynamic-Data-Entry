import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { PasswordField } from '../components/PasswordField'
import { ApiError, forgotPassword, resetPassword } from '../lib/api'
import { useAuth } from '../lib/auth-context'

interface FieldErrors {
  otp?: string
  newPassword?: string
  confirmPassword?: string
}

function ResetPasswordPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const prefilledEmail = searchParams.get('email') ?? ''

  const [email, setEmail] = useState(prefilledEmail)
  const [codeSent, setCodeSent] = useState(false)
  const [otp, setOtp] = useState('')
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
    if (!/^\d{6}$/.test(otp)) {
      next.otp = 'Enter the 6-digit code from your email.'
    }
    if (newPassword.length < 8) {
      next.newPassword = 'Password must be at least 8 characters long.'
    }
    if (confirmPassword !== newPassword) {
      next.confirmPassword = 'Passwords do not match.'
    }
    return next
  }

  async function handleRequestCode(event: FormEvent) {
    event.preventDefault()
    if (!email.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await forgotPassword(email.trim())
      setCodeSent(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const next = validate()
    setErrors(next)
    if (Object.values(next).some(Boolean)) return

    setSubmitting(true)
    setError(null)
    try {
      await resetPassword(email.trim(), otp, newPassword)
      setOtp('')
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
      {!codeSent ? (
        <form
          onSubmit={handleRequestCode}
          noValidate
          className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
        >
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Reset your password</h1>
          <p className="mt-1 text-sm text-slate-500">
            Enter your account email and we will send you a 6-digit code.
          </p>

          <label className="mt-6 block text-xs font-medium text-slate-600" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className={inputClass}
          />

          {error && (
            <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting || !email.trim()}
            className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? 'Sending…' : 'Send code'}
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
      ) : (
        <form
          onSubmit={handleSubmit}
          noValidate
          className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
        >
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Enter your code</h1>
          <p className="mt-1 text-sm text-slate-500">
            We sent a 6-digit code to <span className="font-medium text-slate-700">{email}</span>{' '}
            (valid for 10 minutes). Enter it below with a new password.
          </p>

          <label className="mt-6 block text-xs font-medium text-slate-600" htmlFor="otp">
            Verification code
          </label>
          <input
            id="otp"
            type="text"
            required
            maxLength={6}
            inputMode="numeric"
            autoComplete="one-time-code"
            value={otp}
            onChange={(event) => setOtp(event.target.value.replace(/\D/g, '').slice(0, 6))}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-slate-500">6 digits — XXXXXX.</p>
          {errors.otp && <p className="mt-1 text-xs text-red-600">{errors.otp}</p>}

          <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="newPassword">
            New password
          </label>
          <PasswordField
            id="newPassword"
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
          <PasswordField
            id="confirmPassword"
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
            <button
              type="button"
              onClick={() => {
                setCodeSent(false)
                setOtp('')
                setError(null)
              }}
              className="font-medium text-slate-700 underline-offset-4 hover:underline"
            >
              Use a different email
            </button>
          </p>
        </form>
      )}
    </main>
  )
}

export default ResetPasswordPage