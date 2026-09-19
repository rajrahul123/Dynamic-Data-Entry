import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { FieldRenderer } from '../components/forms/FieldRenderer'
import {
  ApiError,
  type Form,
  type SubmissionListItem,
  fetchFormDefinition,
  fetchSubmission,
  type ValidationErrorDetail,
  updateSubmission,
} from '../lib/api'
import { validateSubmission } from '../lib/submissionValidation'

export function RecordEditPage() {
  const { id, submissionId } = useParams<{ id: string; submissionId: string }>()
  const navigate = useNavigate()
  const formId = Number(id)
  const recordId = Number(submissionId)

  const [form, setForm] = useState<Form | null>(null)
  const [record, setRecord] = useState<SubmissionListItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const fields = useMemo(
    () => (form ? [...form.fields].sort((a, b) => a.sort_order - b.sort_order) : []),
    [form],
  )

  const setFieldError = useCallback((key: string, message?: string) => {
    setFieldErrors((prev) => {
      if (message === undefined) {
        if (!(key in prev)) return prev
        const next = { ...prev }
        delete next[key]
        return next
      }
      return { ...prev, [key]: message }
    })
  }, [])

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
        // Only keys present in the stored record are edited; current field
        // definitions stay authoritative on the server.
        const initial: Record<string, unknown> = {}
        for (const key of Object.keys(recordData.data)) {
          initial[key] = recordData.data[key]
        }
        setValues(initial)
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [formId, recordId])

  function handleChange(key: string) {
    return (value: unknown) => {
      setValues((prev) => ({ ...prev, [key]: value }))
      setFieldError(key)
    }
  }

  async function handleSave() {
    setFormError(null)
    const errors = validateSubmission(fields, values)
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setSaving(true)
    try {
      await updateSubmission(formId, recordId, values)
      navigate(`/forms/${formId}/records/${recordId}`)
    } catch (err) {
      if (err instanceof ApiError && Array.isArray(err.detail)) {
        const serverErrors: Record<string, string> = {}
        for (const detail of err.detail as ValidationErrorDetail[]) {
          const key = String(detail.loc[detail.loc.length - 1])
          serverErrors[key] = detail.msg
        }
        setFieldErrors(serverErrors)
      }
      setFormError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-500">Loading record…</p>
  }

  if (loadError || !form || !record) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {loadError ?? 'This record is not available.'}
        </div>
        <Link
          to={`/forms/${formId}/records`}
          className="inline-block rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Back to records
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <header>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">
          Edit record #{record.id}
        </h2>
        <p className="mt-1 text-sm text-slate-600">{form.name}</p>
      </header>

      {formError && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{formError}</div>
      )}

      <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        {fields.map((field) => (
          <div key={field.id}>
            <FieldRenderer
              field={field}
              value={values[field.field_key]}
              onChange={handleChange(field.field_key)}
              disabled={saving}
            />
            {fieldErrors[field.field_key] && (
              <p className="mt-1 text-xs font-medium text-red-600">
                {fieldErrors[field.field_key]}
              </p>
            )}
          </div>
        ))}

        <div className="flex items-center justify-between pt-2">
          <Link
            to={`/forms/${formId}/records/${recordId}`}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </Link>
          <button
            type="button"
            disabled={saving}
            onClick={() => void handleSave()}
            className="rounded-lg bg-slate-900 px-5 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </section>
    </div>
  )
}