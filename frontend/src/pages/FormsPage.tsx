import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  archiveForm,
  deleteForm,
  listForms,
  publishForm,
  type Form,
  type FormStatus,
} from '../lib/api'

function statusBadgeClass(status: FormStatus) {
  if (status === 'published') return 'bg-emerald-100 text-emerald-700'
  if (status === 'archived') return 'bg-slate-200 text-slate-600'
  return 'bg-slate-100 text-slate-600'
}

export function FormsPage() {
  const navigate = useNavigate()
  const [forms, setForms] = useState<Form[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const reload = useCallback(async () => {
    try {
      setForms(await listForms())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadForms() {
      try {
        const data = await listForms()
        if (!cancelled) setForms(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadForms()
    return () => {
      cancelled = true
    }
  }, [])

  async function runAction(action: () => Promise<unknown>, formId: number, message: string) {
    setError(null)
    setNotice(null)
    setBusyId(formId)
    try {
      await action()
      setNotice(message)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyId(null)
    }
  }

  async function handlePublish(form: Form) {
    await runAction(() => publishForm(form.id), form.id, `"${form.name}" published.`)
  }

  async function handleArchive(form: Form) {
    await runAction(() => archiveForm(form.id), form.id, `"${form.name}" archived.`)
  }

  async function handleDelete(form: Form) {
    if (!window.confirm(`Delete draft "${form.name}"? This cannot be undone.`)) return
    await runAction(() => deleteForm(form.id), form.id, `"${form.name}" deleted.`)
  }

  const fieldCount = (form: Form) => form.fields.length

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Forms</h2>
          <p className="mt-1 text-sm text-slate-600">
            Admin-only. Design reusable forms in drafts, then publish them.
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate('/forms/new')}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          + New form
        </button>
      </header>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {notice && (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>
      )}

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
              <th className="px-4 py-3 font-medium">Form</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Fields</th>
              <th className="px-4 py-3 font-medium">Updated</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  Loading forms…
                </td>
              </tr>
            ) : forms.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  No forms yet. Create your first one.
                </td>
              </tr>
            ) : (
              forms.map((form) => (
                <tr key={form.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => navigate(`/forms/${form.id}/edit`)}
                      className="text-left font-medium text-slate-900 hover:underline"
                    >
                      {form.name}
                    </button>
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
                  <td className="px-4 py-3 text-slate-600">{fieldCount(form)}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {new Date(form.updated_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        disabled={busyId === form.id}
                        onClick={() => navigate(`/forms/${form.id}/edit`)}
                        className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        {form.status === 'draft' ? 'Design' : 'View'}
                      </button>
                      {form.status === 'draft' && (
                        <button
                          type="button"
                          disabled={busyId === form.id || fieldCount(form) === 0}
                          onClick={() => handlePublish(form)}
                          className="rounded-lg border border-emerald-300 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                        >
                          Publish
                        </button>
                      )}
                      {form.status === 'published' && (
                        <button
                          type="button"
                          onClick={() => navigate(`/forms/${form.id}/submit`)}
                          className="rounded-lg border border-slate-900 px-2.5 py-1 text-xs font-medium text-slate-900 hover:bg-slate-100"
                        >
                          Enter data
                        </button>
                      )}
                      {(form.status === 'published' || form.status === 'archived') && (
                        <button
                          type="button"
                          onClick={() => navigate(`/forms/${form.id}/records`)}
                          className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          View records
                        </button>
                      )}
                      {(form.status === 'draft' || form.status === 'published') && (
                        <button
                          type="button"
                          disabled={busyId === form.id}
                          onClick={() => handleArchive(form)}
                          className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                        >
                          Archive
                        </button>
                      )}
                      {form.status === 'draft' && (
                        <button
                          type="button"
                          disabled={busyId === form.id}
                          onClick={() => handleDelete(form)}
                          className="rounded-lg border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                        >
                          Delete
                        </button>
                      )}
                    </div>
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