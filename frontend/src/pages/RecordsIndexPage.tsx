import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { AvailableForm, FormStatus } from '../lib/api'
import { listAvailableForms } from '../lib/api'

function statusBadgeClass(status: FormStatus) {
  if (status === 'published') return 'bg-emerald-100 text-emerald-700'
  if (status === 'archived') return 'bg-slate-200 text-slate-600'
  return 'bg-slate-100 text-slate-600'
}

export function RecordsIndexPage() {
  const navigate = useNavigate()
  const [forms, setForms] = useState<AvailableForm[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await listAvailableForms()
        if (!cancelled) setForms(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">Records</h2>
        <p className="mt-1 text-sm text-slate-600">
          Browse the records collected through published and archived forms.
        </p>
      </header>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
              <th className="px-4 py-3 font-medium">Form</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Updated</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                  Loading forms…
                </td>
              </tr>
            ) : forms.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                  No published or archived forms yet.
                </td>
              </tr>
            ) : (
              forms.map((form) => (
                <tr key={form.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{form.name}</div>
                    <div className="text-xs text-slate-500">
                      {form.description || 'No description'}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(form.status)}`}
                    >
                      {form.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {new Date(form.updated_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => navigate(`/forms/${form.id}/records`)}
                      className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      View records
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