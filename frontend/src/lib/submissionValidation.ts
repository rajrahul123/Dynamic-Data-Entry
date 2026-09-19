import type { FormField } from './api'

export function fieldError(field: FormField, value: unknown): string | null {
  const isEmpty = value === undefined || value === null || value === '' || value === false

  if (field.required && isEmpty) {
    return 'This field is required.'
  }
  if (isEmpty) return null

  const settings = field.settings ?? {}
  const stringOrEmpty = (v: unknown): string =>
    typeof v === 'string' ? v : v === undefined || v === null ? '' : String(v)

  switch (field.field_type) {
    case 'text':
    case 'textarea': {
      const text = stringOrEmpty(value)
      const min = settings.min_length
      const max = settings.max_length
      if (min !== undefined && min !== null && text.length < min) {
        return `Must be at least ${min} characters`
      }
      if (max !== undefined && max !== null && text.length > max) {
        return `Must be at most ${max} characters`
      }
      return null
    }
    case 'number': {
      const raw = stringOrEmpty(value)
      if (raw.trim() === '' || Number.isNaN(Number(raw))) {
        return 'Must be a valid number'
      }
      const num = Number(raw)
      const min = settings.min !== undefined && settings.min !== null ? Number(settings.min) : null
      const max = settings.max !== undefined && settings.max !== null ? Number(settings.max) : null
      const step = settings.step !== undefined && settings.step !== null ? Number(settings.step) : null
      if (min !== null && num < min) return `Must be at least ${min}`
      if (max !== null && num > max) return `Must be at most ${max}`
      if (step !== null && step > 0) {
        const base = min ?? 0
        const quotient = (num - base) / step
        if (Math.abs(quotient - Math.round(quotient)) > 1e-6) {
          return `Must be a multiple of ${step}`
        }
      }
      return null
    }
    case 'email':
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(stringOrEmpty(value))) {
        return 'Enter a valid email address'
      }
      return null
    case 'phone':
      if (!/^\+?[0-9][0-9 ()+-]{5,19}$/.test(stringOrEmpty(value))) {
        return 'Enter a valid phone number'
      }
      return null
    case 'date':
      if (!/^\d{4}-\d{2}-\d{2}$/.test(stringOrEmpty(value))) {
        return 'Enter a valid date'
      }
      return null
    case 'time': {
      const time = stringOrEmpty(value)
      if (!/^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/.test(time)) {
        return 'Enter a valid time'
      }
      return null
    }
    case 'datetime':
      if (!/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$/.test(stringOrEmpty(value))) {
        return 'Enter a valid date and time'
      }
      return null
    case 'select':
    case 'radio': {
      const raw = stringOrEmpty(value)
      const options = settings.options ?? []
      const accepted = options.some((o) => o.value === raw || o.label === raw)
      if (!accepted) return 'Choose a valid option'
      return null
    }
    case 'checkbox':
      if (typeof value !== 'boolean') return 'Must be true or false'
      return null
    default:
      return null
  }
}

export function validateSubmission(
  fields: FormField[],
  data: Record<string, unknown>,
): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const field of fields) {
    const message = fieldError(field, data[field.field_key])
    if (message) errors[field.field_key] = message
  }
  return errors
}