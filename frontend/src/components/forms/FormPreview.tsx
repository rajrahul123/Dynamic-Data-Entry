import type { FormField } from '../../lib/api'
import { FieldRenderer } from './FieldRenderer'

interface FormPreviewProps {
  fields: FormField[]
}

export function FormPreview({ fields }: FormPreviewProps) {
  return (
    <div className="space-y-4">
      {fields.length === 0 ? (
        <p className="text-sm text-slate-400">No fields yet — add one from the palette.</p>
      ) : (
        fields.map((field) => <FieldRenderer key={field.id} field={field} />)
      )}
    </div>
  )
}