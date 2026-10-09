import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { listAvailableForms, type AvailableForm, type FormStatus } from '../lib/api'
import { IconChevronDown } from '../components/icons'

function statusBadgeClass(status: FormStatus) {
  if (status === 'published') return 'tag-emerald'
  if (status === 'archived') return 'tag-slate'
  return 'tag-amber'
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
    <div className="page">
      <header>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">Records</h2>
        <p className="mt-1 text-sm text-slate-600">
          Browse the records collected through published and archived forms.
        </p>
      </header>

      {error && <p className="banner-error">{error}</p>}

      {loading ? (
        <div className="card space-y-3 p-5">
          <span className="skeleton block h-12 w-full" />
          <span className="skeleton block h-12 w-full" />
          <span className="skeleton block h-12 w-full" />
        </div>
      ) : (
        <section className="table-wrap">
          <table className="table-sticky">
            <thead>
              <tr>
                <th>Form</th>
                <th>Status</th>
                <th>Updated</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {forms.length === 0 ? (
                <tr>
                  <td colSpan={4} className="table-empty">
                    No published or archived forms yet.
                  </td>
                </tr>
              ) : (
                forms.map((form) => (
                  <tr key={form.id} className="table-row-hover">
                    <td>
                      <div className="font-medium text-slate-900">{form.name}</div>
                      <div className="text-xs text-slate-500">
                        {form.description || 'No description'}
                      </div>
                    </td>
                    <td>
                      <span className={`tag ${statusBadgeClass(form.status)}`}>
                        {form.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap text-xs text-slate-500">
                      {new Date(form.updated_at).toLocaleString()}
                    </td>
                    <td>
                      <div className="flex justify-end">
                        <button
                          type="button"
                          onClick={() => navigate(`/forms/${form.id}/records`)}
                          className="btn btn-secondary btn-sm"
                        >
                          View records
                          <IconChevronDown className="h-3.5 w-3.5 -rotate-90" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}