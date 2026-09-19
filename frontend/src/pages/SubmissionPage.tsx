import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { FieldRenderer } from '../components/forms/FieldRenderer'
import {
  ApiError,
  type Form,
  type SubmissionResponse,
  fetchPublishedForm,
  submitSubmission,
  type ValidationErrorDetail,
} from '../lib/api'
import { validateSubmission } from '../lib/submissionValidation'

export function SubmissionPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const formId = Number(id)

  const [form, setForm] = useState<Form | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submission, setSubmission] = useState<SubmissionResponse | null>(null)

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

    async function loadForm() {
      try {
        const data = await fetchPublishedForm(formId)
        if (cancelled) return
        setForm(data)
        const initial: Record<string, unknown> = {}
        for (const field of data.fields) {
          if (field.default_value !== null && field.default_value !== '') {
            initial[field.field_key] =
              field.field_type === 'checkbox'
                ? field.default_value === 'true'
                : field.default_value
          }
        }
        setValues(initial)
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadForm()
    return () => {
      cancelled = true
    }
  }, [formId])

  function handleChange(key: string) {
    return (value: unknown) => {
      setValues((prev) => ({ ...prev, [key]: value }))
      setFieldError(key)
    }
  }

  async function handleSubmit() {
    setFormError(null)
    const errors = validateSubmission(fields, values)
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setSubmitting(true)
    try {
      const result = await submitSubmission(formId, values)
      setSubmission(result)
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
      setSubmitting(false)
    }
  }

  if (submission) {
    return (
      <div className="mx-auto max-w-xl space-y-6">
        <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center shadow-sm">
          <h2 className="text-2xl font-bold text-emerald-800">Submission received</h2>
          <p className="mt-2 text-sm text-emerald-700">
            Your response to "{form?.name ?? 'this form'}" was recorded (submission #
            {submission.id}) on {new Date(submission.submitted_at).toLocaleString()}.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => {
                setSubmission(null)
                setFieldErrors({})
                setFormError(null)
              }}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600"
            >
              Submit another response
            </button>
            <Link
              to="/dashboard"
              className="rounded-lg border border-emerald-300 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-100"
            >
              Back to dashboard
            </Link>
          </div>
        </section>
      </div>
    )
  }

  if (loading) {
    return <p className="text-sm text-slate-500">Loading form…</p>
  }

  if (loadError || !form) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {loadError ?? 'This form is not available.'}
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

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <header>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">{form.name}</h2>
        {form.description && <p className="mt-1 text-sm text-slate-600">{form.description}</p>}
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
              disabled={submitting}
            />
            {fieldErrors[field.field_key] && (
              <p className="mt-1 text-xs font-medium text-red-600">
                {fieldErrors[field.field_key]}
              </p>
            )}
          </div>
        ))}

        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-slate-500">Fields marked * are required.</p>
          <button
            type="button"
            disabled={submitting}
            onClick={() => void handleSubmit()}
            className="rounded-lg bg-slate-900 px-5 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? 'Submitting…' : 'Submit'}
          </button>
        </div>
      </section>
    </div>
  )
}