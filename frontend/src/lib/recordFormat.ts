import type { FormField } from './api'

const EMPTY = '—'

export function formatRecordValue(field: FormField, value: unknown): string {
  if (value === undefined || value === null) {
    return EMPTY
  }
  if (typeof value === 'string' && value.trim() === '') {
    return EMPTY
  }

  switch (field.field_type) {
    case 'checkbox':
      return value === true ? 'Yes' : 'No'
    case 'select':
    case 'radio': {
      const raw = String(value)
      const options = field.settings?.options ?? []
      const option = options.find((o) => o.value === raw || o.label === raw)
      return option ? option.label : raw
    }
    case 'number':
      return String(value)
    default:
      return String(value)
  }
}