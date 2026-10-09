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
import { useToast } from '../lib/toast-context'
import { IconPencil, IconPlus } from '../components/icons'

type ViewMode = 'table' | 'card'

function statusBadgeClass(status: FormStatus) {
  if (status === 'published') return 'tag-emerald'
  if (status === 'archived') return 'tag-slate'
  return 'tag-amber'
}

const VIEW_OPTIONS: { value: ViewMode; label: string }[] = [
  { value: 'table', label: 'Table' },
  { value: 'card', label: 'Card' },
]

export function FormsPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [forms, setForms] = useState<Form[]>([])
  const [view, setView] = useState<ViewMode>('table')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
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

  async function runAction(action: () => Promise<unknown>, message: string) {
    setError(null)
    try {
      await action()
      toast('success', message)
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handlePublish(form: Form) {
    setBusyId(form.id)
    await runAction(
      () => publishForm(form.id),
      `"${form.name}" published.`,
    )
    setBusyId(null)
  }

  async function handleArchive(form: Form) {
    setBusyId(form.id)
    await runAction(
      () => archiveForm(form.id),
      `"${form.name}" archived.`,
    )
    setBusyId(null)
  }

  async function handleDelete(form: Form) {
    if (!window.confirm(`Delete draft "${form.name}"? This cannot be undone.`)) return
    setBusyId(form.id)
    await runAction(
      () => deleteForm(form.id),
      `"${form.name}" deleted.`,
    )
    setBusyId(null)
  }

  const fieldCount = (form: Form) => form.fields.length

  const editPath = (form: Form) => `/forms/${form.id}/edit`

  function renderActions(form: Form) {
    return (
      <div className="flex flex-wrap items-center justify-end gap-1.5">
        <button
          type="button"
          onClick={() => navigate(editPath(form))}
          className="btn btn-secondary btn-sm"
          title={`Edit "${form.name}"`}
        >
          <IconPencil className="h-3.5 w-3.5" />
          Edit
        </button>
        {form.status === 'draft' && (
          <button
            type="button"
            disabled={busyId === form.id || fieldCount(form) === 0}
            onClick={() => void handlePublish(form)}
            className="btn btn-sm border border-emerald-300 px-2.5 text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
            title={
              fieldCount(form) === 0
                ? 'Add at least one field before publishing.'
                : undefined
            }
          >
            Publish
          </button>
        )}
        {form.status === 'published' && (
          <button
            type="button"
            onClick={() => navigate(`/forms/${form.id}/submit`)}
            className="btn btn-primary btn-sm"
          >
            Enter data
          </button>
        )}
        {(form.status === 'published' || form.status === 'archived') && (
          <button
            type="button"
            onClick={() => navigate(`/forms/${form.id}/records`)}
            className="btn btn-secondary btn-sm"
          >
            View records
          </button>
        )}
        {(form.status === 'draft' || form.status === 'published') && (
          <button
            type="button"
            disabled={busyId === form.id}
            onClick={() => void handleArchive(form)}
            className="btn btn-secondary btn-sm"
          >
            Archive
          </button>
        )}
        {form.status === 'draft' && (
          <button
            type="button"
            disabled={busyId === form.id}
            onClick={() => void handleDelete(form)}
            className="btn btn-danger btn-sm"
          >
            Delete
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="page">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Forms</h2>
          <p className="mt-1 text-sm text-slate-600">
            Design reusable forms in drafts, then publish them for your team.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 self-start">
          <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
            {VIEW_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setView(option.value)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  view === option.value
                    ? 'bg-slate-900 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => navigate('/forms/new')}
            className="btn btn-primary"
          >
            <IconPlus className="h-4 w-4" />
            New form
          </button>
        </div>
      </header>

      {error && <p className="banner-error">{error}</p>}

      {loading ? (
        <div className="card space-y-3 p-5">
          <span className="skeleton block h-12 w-full" />
          <span className="skeleton block h-12 w-full" />
          <span className="skeleton block h-12 w-full" />
        </div>
      ) : forms.length === 0 ? (
        <section className="card flex flex-col items-center gap-3 py-16 text-center">
          <p className="text-sm text-slate-500">No forms yet.</p>
          <button
            type="button"
            onClick={() => navigate('/forms/new')}
            className="btn btn-primary btn-sm"
          >
            <IconPlus className="h-4 w-4" />
            Create your first form
          </button>
        </section>
      ) : view === 'table' ? (
        <section className="table-wrap">
          <table className="table-sticky">
            <thead>
              <tr>
                <th>Form</th>
                <th>Status</th>
                <th>Fields</th>
                <th>Updated</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {forms.map((form) => (
                <tr key={form.id} className="table-row-hover">
                  <td>
                    <button
                      type="button"
                      onClick={() => navigate(editPath(form))}
                      className="text-left font-medium text-slate-900 hover:text-indigo-600"
                    >
                      {form.name}
                    </button>
                    <div className="text-xs text-slate-500">
                      {form.description || 'No description'}
                    </div>
                  </td>
                  <td>
                    <span className={`tag ${statusBadgeClass(form.status)}`}>
                      {form.status}
                    </span>
                  </td>
                  <td className="text-slate-600">{fieldCount(form)}</td>
                  <td className="whitespace-nowrap text-xs text-slate-500">
                    {new Date(form.updated_at).toLocaleString()}
                  </td>
                  <td>{renderActions(form)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {forms.map((form) => (
            <div key={form.id} className="card card-hover flex flex-col gap-3">
              <div className="flex items-start justify-between gap-2">
                <button
                  type="button"
                  onClick={() => navigate(editPath(form))}
                  className="text-left"
                >
                  <div className="font-semibold text-slate-900 hover:text-indigo-600">
                    {form.name}
                  </div>
                </button>
                <span className={`tag shrink-0 ${statusBadgeClass(form.status)}`}>
                  {form.status}
                </span>
              </div>
              <p className="line-clamp-2 text-xs text-slate-500">
                {form.description || 'No description'}
              </p>
              <div className="mt-auto flex items-center justify-between text-xs text-slate-500">
                <span>{fieldCount(form)} {fieldCount(form) === 1 ? 'field' : 'fields'}</span>
                <span>Updated {new Date(form.updated_at).toLocaleDateString()}</span>
              </div>
              {renderActions(form)}
            </div>
          ))}
        </section>
      )}
    </div>
  )
}