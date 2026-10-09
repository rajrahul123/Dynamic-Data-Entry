import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { AuthShell } from '../components/AuthShell'
import { PasswordField } from '../components/PasswordField'
import { ApiError, forgotPassword, resetPassword } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { useToast } from '../lib/toast-context'

interface FieldErrors {
  otp?: string
  newPassword?: string
  confirmPassword?: string
}

function ResetPasswordPage() {
  const { user } = useAuth()
  const { toast } = useToast()
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
      toast('success', 'Password reset. Please sign in with your new password.')
      navigate('/login', { replace: true, state: { reset: true } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <div className="card p-8 shadow-xl ring-1 ring-white/10">
        {!codeSent ? (
          <form onSubmit={handleRequestCode} noValidate>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Reset your password
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Enter your account email and we will send you a 6-digit code.
            </p>

            <label className="label mt-6" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="input"
            />

            {error && <p className="banner-error mt-4">{error}</p>}

            <button
              type="submit"
              disabled={submitting || !email.trim()}
              className="btn btn-primary btn-lg mt-6 w-full"
            >
              {submitting ? 'Sending…' : 'Send code'}
            </button>

            <p className="mt-6 text-center text-sm text-slate-500">
              Remembered it?{' '}
              <Link to="/login" className="link">
                Sign in
              </Link>
            </p>
          </form>
        ) : (
          <form onSubmit={handleSubmit} noValidate>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Enter your code</h1>
            <p className="mt-1 text-sm text-slate-500">
              We sent a 6-digit code to <span className="font-medium text-slate-700">{email}</span>{' '}
              (valid for 10 minutes). Enter it below with a new password.
            </p>

            <label className="label mt-6" htmlFor="otp">
              Verification code
            </label>
            <input
              id="otp"
              type="text"
              required
              maxLength={6}
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="••••••"
              value={otp}
              onChange={(event) => setOtp(event.target.value.replace(/\D/g, '').slice(0, 6))}
              className={errors.otp ? 'input border-red-400' : 'input'}
            />
            {errors.otp && <p className="field-error">{errors.otp}</p>}

            <label className="label mt-4" htmlFor="newPassword">
              New password
            </label>
            <PasswordField
              id="newPassword"
              required
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className={errors.newPassword ? 'input border-red-400' : 'input'}
            />
            {errors.newPassword && <p className="field-error">{errors.newPassword}</p>}

            <label className="label mt-4" htmlFor="confirmPassword">
              Confirm new password
            </label>
            <PasswordField
              id="confirmPassword"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className={errors.confirmPassword ? 'input border-red-400' : 'input'}
            />
            {errors.confirmPassword && (
              <p className="field-error">{errors.confirmPassword}</p>
            )}

            {error && <p className="banner-error mt-4">{error}</p>}

            <button type="submit" disabled={submitting} className="btn btn-primary btn-lg mt-6 w-full">
              {submitting ? 'Resetting…' : 'Reset password'}
            </button>

            <p className="mt-6 text-center text-sm text-slate-500">
              <button
                type="button"
                onClick={() => {
                  setCodeSent(false)
                  setOtp('')
                  setError(null)
                }}
                className="link"
              >
                Use a different email
              </button>
            </p>
          </form>
        )}
      </div>
    </AuthShell>
  )
}

export default ResetPasswordPage