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
      <div className="space-y-4">
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          Could not create the form: {error}
        </p>
        <button
          type="button"
          onClick={() => navigate('/forms')}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          ← Back to forms
        </button>
      </div>
    )
  }

  return <p className="text-sm text-slate-500">Creating form…</p>
}

export default FormCreatePage