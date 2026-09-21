import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../lib/auth-context'
import {
  type Form,
  type SubmissionListItem,
  exportSingleRecordPdf,
  fetchFormDefinition,
  fetchSubmission,
} from '../lib/api'
import { formatRecordValue } from '../lib/recordFormat'

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export function RecordDetailPage() {
  const { id, submissionId } = useParams<{ id: string; submissionId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const formId = Number(id)
  const recordId = Number(submissionId)

  const [form, setForm] = useState<Form | null>(null)
  const [record, setRecord] = useState<SubmissionListItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [exportBusy, setExportBusy] = useState(false)

  const canMutate = user?.role === 'admin' || user?.role === 'operator'

  const fields = useMemo(
    () => (form ? [...form.fields].sort((a, b) => a.sort_order - b.sort_order) : []),
    [form],
  )

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [formData, recordData] = await Promise.all([
          fetchFormDefinition(formId),
          fetchSubmission(formId, recordId),
        ])
        if (cancelled) return
        setForm(formData)
        setRecord(recordData)
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
  }, [formId, recordId])

  async function handlePdfExport() {
    if (!form || !record) return
    setExportBusy(true)
    setError(null)
    setNotice(null)
    try {
      const { blob, filename } = await exportSingleRecordPdf(formId, record.id)
      triggerDownload(blob, filename)
      setNotice(`Form PDF downloaded as ${filename}.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setExportBusy(false)
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-500">Loading record…</p>
  }

  if (error || !form || !record) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error ?? 'This record is not available.'}
        </div>
        <button
          type="button"
          onClick={() => navigate(`/forms/${formId}/records`)}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Back to records
        </button>
      </div>
    )
  }

  const submitter =
    record.submitted_by_full_name ?? record.submitted_by_username ?? `user #${record.submitted_by}`

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">{form.name}</h2>
          <p className="mt-1 text-sm text-slate-600">Record #{record.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={`/forms/${formId}/records`}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Back to records
          </Link>
          <button
            type="button"
            disabled={exportBusy}
            onClick={() => void handlePdfExport()}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {exportBusy ? 'Exporting…' : 'Form PDF'}
          </button>
          {canMutate && (
            <Link
              to={`/forms/${formId}/records/${record.id}/edit`}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
            >
              Edit
            </Link>
          )}
        </div>
      </header>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {notice && (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>
      )}

      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        {fields.map((field) => (
          <div key={field.id} className="border-b border-slate-100 pb-3 last:border-0 last:pb-0">
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {field.label}
            </dt>
            <dd className="mt-1 text-sm text-slate-900">
              {formatRecordValue(field, record.data[field.field_key])}
            </dd>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Submitted</dt>
          <dd className="mt-1 text-sm text-slate-900">
            {new Date(record.submitted_at).toLocaleString()}
          </dd>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Updated</dt>
          <dd className="mt-1 text-sm text-slate-900">
            {new Date(record.updated_at).toLocaleString()}
          </dd>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Submitted by</dt>
          <dd className="mt-1 text-sm text-slate-900">{submitter}</dd>
        </div>
      </section>
    </div>
  )
}