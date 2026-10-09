import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../lib/auth-context'

const FEATURES = [
  {
    title: 'Build forms in minutes',
    description:
      'A drag-free dynamic builder lets you define text, numbers, dates, dropdowns and more with live validation rules — no code.',
  },
  {
    title: 'Collect & manage records',
    description:
      'Publish a form and staff enter data. Every record is validated field-by-field and stored as clean, exportable JSON.',
  },
  {
    title: 'Multi-tenant isolation',
    description:
      'Every signup gets its own organization with hard data isolation — your forms, users and records live in a private workspace.',
  },
  {
    title: 'Powerful querying',
    description:
      'Search, filter and sort records with per-type operators, then export rich tables to CSV, XLSX, PDF or SQL.',
  },
]

export function LandingPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  function handleCta() {
    navigate(user ? '/dashboard' : '/register')
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <span className="text-base font-bold tracking-tight">
            Dynamic Data Entry Platform
          </span>
          <div className="flex items-center gap-3">
            {user ? (
              <button
                type="button"
                onClick={() => navigate('/dashboard')}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
              >
                Open Dashboard
              </button>
            ) : (
              <>
                <Link
                  to="/login"
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
                >
                  Get started free
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-5xl px-6 pb-16 pt-20 text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
          Multi-tenant data entry for teams
        </p>
        <h1 className="mx-auto mt-4 max-w-3xl text-4xl font-extrabold tracking-tight sm:text-5xl">
          Capture structured data, in your own private workspace.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
          Design dynamic forms, validate every field, manage records, and export
          to CSV, XLSX or PDF — with role-based access and per-organization data
          isolation.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={handleCta}
            className="rounded-lg bg-slate-900 px-6 py-3 text-sm font-semibold text-white hover:bg-slate-700"
          >
            {user ? 'Go to your dashboard' : 'Create your free workspace'}
          </button>
          <Link
            to="/login"
            className="rounded-lg border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Sign in
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-16">
        <h2 className="text-center text-2xl font-bold tracking-tight">Everything you need to run forms</h2>
        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border border-slate-200 bg-white p-6"
            >
              <h3 className="text-base font-semibold">{feature.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-6 py-6 text-center text-xs text-slate-500">
          Dynamic Data Entry Platform — generic, dynamic, and yours.
        </div>
      </footer>
    </div>
  )
}

export default LandingPage