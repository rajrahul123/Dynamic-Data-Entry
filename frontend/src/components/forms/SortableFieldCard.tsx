import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

import { FIELD_TYPES, type FormField } from '../../lib/api'

interface SortableFieldCardProps {
  field: FormField
  selected: boolean
  onSelect: (field: FormField) => void
}

const typeTypeBadge = (field: FormField) =>
  FIELD_TYPES.find(({ type }) => type === field.field_type)?.label ?? field.field_type

export function SortableFieldCard({ field, selected, onSelect }: SortableFieldCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: field.id,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={() => onSelect(field)}
      className={`flex cursor-pointer items-center gap-3 rounded-xl border bg-white p-3 shadow-sm transition-colors ${
        isDragging ? 'border-slate-400 opacity-70' : selected ? 'border-slate-600 ring-1 ring-slate-600' : 'border-slate-200'
      }`}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        aria-label={`Drag ${field.label}`}
        className="rounded px-1.5 py-1 text-slate-300 hover:bg-slate-100 hover:text-slate-500"
      >
        ⠿
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-slate-900">{field.label}</span>
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-slate-500">
            {typeTypeBadge(field)}
          </span>
          {field.required && <span className="text-xs text-red-600">required</span>}
        </div>
        <div className="truncate font-mono text-xs text-slate-400">{field.field_key}</div>
      </div>
    </div>
  )
}