import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { AuthShell } from '../components/AuthShell'
import { PasswordField } from '../components/PasswordField'
import { ApiError, register } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import { useToast } from '../lib/toast-context'

const USERNAME_PATTERN = /^[a-zA-Z0-9_.-]{3,50}$/
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PASSWORD_MIN_LENGTH = 8

interface FieldErrors {
  fullName?: string
  username?: string
  email?: string
  password?: string
  confirmPassword?: string
}

function RegistrationPage() {
  const { user } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) {
    return <Navigate to="/dashboard" replace />
  }

  function validate(): FieldErrors {
    const next: FieldErrors = {}

    if (!fullName.trim()) next.fullName = 'Full name is required.'

    if (!USERNAME_PATTERN.test(username.trim())) {
      next.username = 'Username must be 3-50 characters using letters, digits, . _ -'
    }

    if (!EMAIL_PATTERN.test(email.trim())) {
      next.email = 'Enter a valid email address.'
    }

    if (password.length < PASSWORD_MIN_LENGTH) {
      next.password = `Password must be at least ${PASSWORD_MIN_LENGTH} characters long.`
    }

    if (confirmPassword !== password) {
      next.confirmPassword = 'Passwords do not match.'
    }

    return next
  }

  function serverFieldMessage(detail: unknown): string | null {
    if (!Array.isArray(detail)) return null
    const entry = detail.find(
      (item): item is { loc?: (string | number)[]; msg?: string } =>
        typeof item === 'object' && item !== null,
    )
    const loc = entry?.loc
    if (Array.isArray(loc) && typeof loc[loc.length - 1] === 'string') {
      const field = loc[loc.length - 1]
      const message = entry?.msg ? String(entry.msg) : null
      if (typeof field === 'string' && message) {
        return `${field}: ${message}`
      }
    }
    return null
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const next = validate()
    setErrors(next)
    if (Object.values(next).some(Boolean)) return

    setSubmitting(true)
    setError(null)
    try {
      await register({
        full_name: fullName.trim() || null,
        username: username.trim(),
        email: email.trim(),
        password,
      })
      toast('success', 'Account created. Sign in to get started.')
      navigate('/login', { replace: true, state: { registered: true } })
    } catch (err) {
      if (err instanceof ApiError) {
        const fieldMessage = serverFieldMessage(err.detail)
        setError(fieldMessage ?? err.message)
      } else {
        setError(err instanceof Error ? err.message : String(err))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const passwordStrength =
    password.length === 0
      ? 0
      : password.length >= PASSWORD_MIN_LENGTH
        ? 100
        : password.length / PASSWORD_MIN_LENGTH

  return (
    <AuthShell>
      <div className="card p-8 shadow-xl ring-1 ring-white/10">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Create your account</h1>
        <p className="mt-1 text-sm text-slate-500">
          Start with a private workspace for your team.
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
          <div>
            <label className="label" htmlFor="fullName">
              Full name
            </label>
            <input
              id="fullName"
              type="text"
              required
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className={errors.fullName ? 'input border-red-400' : 'input'}
            />
            {errors.fullName && <p className="field-error">{errors.fullName}</p>}
          </div>

          <div>
            <label className="label" htmlFor="username">
              Username
            </label>
            <input
              id="username"
              type="text"
              required
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className={errors.username ? 'input border-red-400' : 'input'}
            />
            {errors.username && <p className="field-error">{errors.username}</p>}
          </div>

          <div>
            <label className="label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={errors.email ? 'input border-red-400' : 'input'}
            />
            {errors.email && <p className="field-error">{errors.email}</p>}
          </div>

          <div>
            <label className="label" htmlFor="password">
              Password
            </label>
            <PasswordField
              id="password"
              required
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={errors.password ? 'input border-red-400' : 'input'}
            />
            {password.length > 0 && (
              <div
                className="mt-2 h-1 overflow-hidden rounded-full bg-slate-100"
                aria-hidden="true"
              >
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    passwordStrength >= 100 ? 'bg-emerald-500' : 'bg-indigo-500'
                  }`}
                  style={{ width: `${passwordStrength}%` }}
                />
              </div>
            )}
            <p className="field-error">{errors.password}</p>
          </div>

          <div>
            <label className="label" htmlFor="confirmPassword">
              Confirm password
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
          </div>

          <p className="text-xs text-slate-500">
            You&apos;ll get your own private workspace when you sign up.
          </p>

          {error && <p className="banner-error">{error}</p>}

          <button type="submit" disabled={submitting} className="btn btn-primary btn-lg w-full">
            {submitting ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account?{' '}
          <Link to="/login" className="link">
            Login
          </Link>
        </p>
      </div>
    </AuthShell>
  )
}

export default RegistrationPage