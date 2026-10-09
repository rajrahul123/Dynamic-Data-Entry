import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createForm } from '../lib/api'

export function FormCreatePage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function create() {
      try {
        const form = await createForm({ name: 'Untitled form' })
        if (!cancelled) navigate(`/forms/${form.id}/edit`, { replace: true })
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      }
    }

    void create()
    return () => {
      cancelled = true
    }
  }, [navigate])

  if (error) {
    return (
      <div className="page">
        <p className="banner-error">Could not create the form: {error}</p>
        <button
          type="button"
          onClick={() => navigate('/forms')}
          className="btn btn-secondary"
        >
          ← Back to forms
        </button>
      </div>
    )
  }

  return (
    <div className="page flex items-center gap-3 text-sm text-slate-500">
      <span className="skeleton h-5 w-5 shrink-0 rounded-full" aria-hidden />
      Creating form…
    </div>
  )
}

export default FormCreatePage