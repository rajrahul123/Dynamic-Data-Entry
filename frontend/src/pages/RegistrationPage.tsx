import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { ApiError, register } from '../lib/api'
import { useAuth } from '../lib/auth-context'

const USERNAME_PATTERN = /^[a-zA-Z0-9_.-]{3,50}$/
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface FieldErrors {
  fullName?: string
  username?: string
  email?: string
  password?: string
  confirmPassword?: string
}

function RegistrationPage() {
  const { user } = useAuth()
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

    if (password.length < 8) {
      next.password = 'Password must be at least 8 characters long.'
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

  const inputClass =
    'mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none'

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <form
        onSubmit={handleSubmit}
        noValidate
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <h1 className="text-xl font-bold tracking-tight text-slate-900">
          Dynamic Data Entry Platform
        </h1>
        <p className="mt-1 text-sm text-slate-500">Create your account</p>

        <label className="mt-6 block text-xs font-medium text-slate-600" htmlFor="fullName">
          Full name
        </label>
        <input
          id="fullName"
          type="text"
          required
          autoComplete="name"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          className={inputClass}
        />
        {errors.fullName && <p className="mt-1 text-xs text-red-600">{errors.fullName}</p>}

        <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="username">
          Username
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
        {errors.username && <p className="mt-1 text-xs text-red-600">{errors.username}</p>}

        <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="email">
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
        {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email}</p>}

        <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          required
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className={inputClass}
        />
        <p className="mt-1 text-xs text-slate-500">At least 8 characters.</p>
        {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password}</p>}

        <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="confirmPassword">
          Confirm password
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

        <p className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
          New accounts are created with Viewer access.
        </p>

        {error && (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {submitting ? 'Creating account…' : 'Create Account'}
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account?{' '}
          <Link
            to="/login"
            className="font-medium text-slate-900 underline-offset-4 hover:underline"
          >
            Login
          </Link>
        </p>
      </form>
    </main>
  )
}

export default RegistrationPage