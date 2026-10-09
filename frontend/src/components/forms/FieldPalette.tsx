import { FIELD_TYPES, type FieldType } from '../../lib/api'

interface FieldPaletteProps {
  onAddField: (type: FieldType) => void
  busy: boolean
}

export function FieldPalette({ onAddField, busy }: FieldPaletteProps) {
  return (
    <section className="card">
      <h3 className="text-sm font-semibold text-slate-900">Field types</h3>
      <p className="mt-0.5 text-xs text-slate-500">Click a type to add it to the form.</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {FIELD_TYPES.map(({ type, label }) => (
          <button
            key={type}
            type="button"
            disabled={busy}
            onClick={() => onAddField(type)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-left text-xs font-medium text-slate-700 transition-colors hover:border-slate-400 hover:bg-white disabled:opacity-50"
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  )
}