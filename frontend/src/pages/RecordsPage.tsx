import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../lib/auth-context'
import {
  type Form,
  type FormField,
  type FormStatus,
  type SubmissionListItem,
  deleteSubmission,
  fetchFormDefinition,
  listSubmissions,
} from '../lib/api'
import { formatRecordValue } from '../lib/recordFormat'
import { ExportMenu } from '../components/records/ExportMenu'
import { type AppliedQuery, QueryToolbar } from '../components/records/QueryToolbar'

// Records are rendered entirely from the form definition. At most this many
// leading fields (sorted by sort_order) become table columns; the complete
// record remains available on the detail page. The subset is deterministic.
const MAX_TABLE_COLUMNS = 4
const PAGE_SIZE = 10

function statusBadgeClass(status: FormStatus) {
  if (status === 'published') return 'bg-emerald-100 text-emerald-700'
  if (status === 'archived') return 'bg-slate-200 text-slate-600'
  return 'bg-slate-100 text-slate-600'
}

export function RecordsPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const formId = Number(id)

  const [form, setForm] = useState<Form | null>(null)
  const [records, setRecords] = useState<SubmissionListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [query, setQuery] = useState<AppliedQuery>({ search: undefined, sortOrder: 'desc' })

  const canMutate = user?.role === 'admin' || user?.role === 'operator'
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const tableColumns = useMemo(() => {
    if (!form) return []
    return [...form.fields]
      .sort((a, b) => a.sort_order - b.sort_order)
      .slice(0, MAX_TABLE_COLUMNS)
  }, [form])

  const load = useCallback(
    async (targetPage: number, currentQuery: AppliedQuery) => {
      setError(null)
      try {
        const [formData, list] = await Promise.all([
          fetchFormDefinition(formId),
          listSubmissions(formId, {
            limit: PAGE_SIZE,
            offset: (targetPage - 1) * PAGE_SIZE,
            search: currentQuery.search,
            filters: currentQuery.filters,
            sortBy: currentQuery.sortBy,
            sortOrder: currentQuery.sortOrder,
          }),
        ])
        setForm(formData)
        setRecords(list.items)
        setTotal(list.total)
        setPage(targetPage)
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setLoading(false)
      }
    },
    [formId],
  )

  useEffect(() => {
    let cancelled = false
    async function initialLoad() {
      try {
        const [formData, list] = await Promise.all([
          fetchFormDefinition(formId),
          listSubmissions(formId, { limit: PAGE_SIZE, offset: 0 }),
        ])
        if (cancelled) return
        setForm(formData)
        setRecords(list.items)
        setTotal(list.total)
        setPage(1)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void initialLoad()
    return () => {
      cancelled = true
    }
  }, [formId])

  function applyQuery(next: AppliedQuery) {
    setQuery(next)
    setPage(1)
    setLoading(true)
    void load(1, next)
  }

  async function turnPage(nextPage: number) {
    if (nextPage < 1 || nextPage > totalPages) return
    setLoading(true)
    await load(nextPage, query)
    setLoading(false)
  }

  async function handleDelete(record: SubmissionListItem) {
    if (!window.confirm('Delete this record? This action cannot be undone.')) return
    setDeletingId(record.id)
    setError(null)
    setNotice(null)
    try {
      await deleteSubmission(formId, record.id)
      const deletionChangedPage = records.length === 1 && page > 1
      const targetPage = deletionChangedPage ? page - 1 : page
      if (deletionChangedPage) {
        await load(targetPage, query)
      } else {
        await load(page, query)
      }
      setNotice(`Record #${record.id} deleted.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setDeletingId(null)
    }
  }

  function cellValue(field: FormField, record: SubmissionListItem) {
    return formatRecordValue(field, record.data[field.field_key])
  }

  if (loading && !form) {
    return <p className="text-sm text-slate-500">Loading records…</p>
  }

  if (error && !form) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error ?? 'This form is not available.'}
        </div>
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Back to dashboard
        </button>
      </div>
    )
  }

  if (!form) return null

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">{form.name}</h2>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(form.status)}`}>
              {form.status}
            </span>
          </div>
          {form.description && <p className="mt-1 text-sm text-slate-600">{form.description}</p>}
          <p className="mt-2 text-sm text-slate-600">
            {total} {total === 1 ? 'record' : 'records'}
            {tableColumns.length < form.fields.length &&
              ` · showing the first ${tableColumns.length} columns`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ExportMenu
            formId={formId}
            query={query}
            disabled={loading}
            onError={setError}
            onNotice={setNotice}
          />
          <Link
            to="/records"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            All records
          </Link>
          {form.status === 'published' && (
            <Link
              to={`/forms/${formId}/submit`}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
            >
              + Enter data
            </Link>
          )}
        </div>
      </header>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {notice && (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>
      )}

      <QueryToolbar form={form} query={query} onApply={applyQuery} />

      {loading && <p className="text-xs text-slate-400">Loading…</p>}

      <section className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
              {tableColumns.map((field) => (
                <th key={field.id} className="px-4 py-3 font-medium">
                  {field.label}
                </th>
              ))}
              <th className="px-4 py-3 font-medium">Submitted</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 ? (
              <tr>
                <td colSpan={tableColumns.length + 2} className="px-4 py-8 text-center text-slate-400">
                  {query.search || (query.filters?.length ?? 0) > 0
                    ? 'No records match your search or filters.'
                    : 'No records yet.'}
                </td>
              </tr>
            ) : (
              records.map((record) => (
                <tr key={record.id} className="border-b border-slate-100 last:border-0">
                  {tableColumns.map((field) => (
                    <td key={field.id} className="max-w-56 truncate px-4 py-3 text-slate-800">
                      {cellValue(field, record)}
                    </td>
                  ))}
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                    {new Date(record.submitted_at).toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => navigate(`/forms/${formId}/records/${record.id}`)}
                        className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        View
                      </button>
                      {canMutate && (
                        <>
                          <button
                            type="button"
                            onClick={() => navigate(`/forms/${formId}/records/${record.id}/edit`)}
                            className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            disabled={deletingId === record.id}
                            onClick={() => void handleDelete(record)}
                            className="rounded-lg border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <div className="flex items-center justify-between text-sm text-slate-600">
        <p>
          Showing {records.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–
          {Math.min(page * PAGE_SIZE, total)} of {total}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => void turnPage(page - 1)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => void turnPage(page + 1)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}