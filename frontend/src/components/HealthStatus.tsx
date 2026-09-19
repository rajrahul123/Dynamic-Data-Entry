import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResponse } from '../lib/api'

type HealthState =
  | { phase: 'loading' }
  | { phase: 'ok'; data: HealthResponse }
  | { phase: 'error'; message: string }

export function HealthStatus() {
  const [state, setState] = useState<HealthState>({ phase: 'loading' })

  useEffect(() => {
    let cancelled = false

    fetchHealth()
      .then((data) => {
        if (!cancelled) setState({ phase: 'ok', data })
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            phase: 'error',
            message: error instanceof Error ? error.message : String(error),
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-900">Backend health</h2>

      {state.phase === 'loading' && (
        <p className="mt-2 text-sm text-slate-500">Checking /api/health…</p>
      )}

      {state.phase === 'error' && (
        <p className="mt-2 text-sm text-red-600">
          Cannot reach the backend: {state.message}
        </p>
      )}

      {state.phase === 'ok' && (
        <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2">
            <dt className="text-slate-500">Status</dt>
            <dd className="font-medium text-slate-900">{state.data.status}</dd>
          </div>
          <div className="flex justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2">
            <dt className="text-slate-500">API version</dt>
            <dd className="font-medium text-slate-900">
              {state.data.api_version}
            </dd>
          </div>
          <div className="flex justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2">
            <dt className="text-slate-500">Environment</dt>
            <dd className="font-medium text-slate-900">{state.data.environment}</dd>
          </div>
          <div className="flex justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2">
            <dt className="text-slate-500">Database</dt>
            <dd className="font-medium text-slate-900">{state.data.database}</dd>
          </div>
        </dl>
      )}
    </div>
  )
}