import type { ReactNode } from 'react'

import type { FormField } from '../../lib/api'

interface FieldRendererProps {
  field: FormField
  value?: unknown
  onChange?: (value: unknown) => void
  disabled?: boolean
}

const inputClasses =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500'

function stringify(value: unknown): string {
  return typeof value === 'string' ? value : value === undefined || value === null ? '' : String(value)
}

function Options({ field, value, onChange, disabled }: FieldRendererProps & { value: unknown }) {
  const options = field.settings?.options ?? []
  if (!options.length) {
    return <p className="text-sm text-slate-400">No options configured.</p>
  }
  return (
    <select
      className={inputClasses}
      value={stringify(value)}
      disabled={disabled}
      onChange={(event) => onChange?.(event.target.value)}
    >
      <option value="">Please select…</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

function RadioGroup({ field, value, onChange, disabled }: FieldRendererProps & { value: unknown }) {
  const options = field.settings?.options ?? []
  if (!options.length) {
    return <p className="text-sm text-slate-400">No options configured.</p>
  }
  return (
    <div className="space-y-1.5">
      {options.map((option) => (
        <label key={option.value} className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="radio"
            name={`entry-${field.field_key}`}
            value={option.value}
            checked={stringify(value) === option.value}
            disabled={disabled}
            onChange={(event) => onChange?.(event.target.value)}
            className="accent-slate-900"
          />
          {option.label}
        </label>
      ))}
    </div>
  )
}

export function FieldRenderer({ field, value, onChange, disabled }: FieldRendererProps) {
  const { settings } = field
  const controlled = onChange !== undefined

  if (field.field_type === 'checkbox') {
    const checked = value === true
    return (
      <label className="flex items-start gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={controlled ? checked : undefined}
          defaultChecked={controlled ? undefined : field.default_value === 'true'}
          disabled={disabled}
          onChange={(event) => onChange?.(event.target.checked)}
          className="mt-0.5 accent-slate-900"
        />
        <span>
          {settings?.checkbox_label ?? field.label}
          {field.required && <span className="ml-0.5 text-red-600">*</span>}
        </span>
      </label>
    )
  }

  let control: ReactNode
  switch (field.field_type) {
    case 'textarea':
      control = (
        <textarea
          className={inputClasses}
          placeholder={field.placeholder ?? undefined}
          rows={4}
          minLength={settings?.min_length ?? undefined}
          maxLength={settings?.max_length ?? undefined}
          value={controlled ? stringify(value) : undefined}
          defaultValue={controlled ? undefined : field.default_value ?? undefined}
          disabled={disabled}
          onChange={(event) => onChange?.(event.target.value)}
        />
      )
      break
    case 'number':
      control = (
        <input
          type="number"
          className={inputClasses}
          placeholder={field.placeholder ?? undefined}
          min={settings?.min ?? undefined}
          max={settings?.max ?? undefined}
          step={settings?.step ?? undefined}
          value={controlled ? stringify(value) : undefined}
          defaultValue={controlled ? undefined : field.default_value ?? undefined}
          disabled={disabled}
          onChange={(event) => onChange?.(event.target.value)}
        />
      )
      break
    case 'email':
    case 'phone':
    case 'text':
    case 'date':
    case 'time':
    case 'datetime':
      control = (
        <input
          type={
            field.field_type === 'email'
              ? 'email'
              : field.field_type === 'phone'
                ? 'tel'
                : field.field_type === 'datetime'
                  ? 'datetime-local'
                  : field.field_type
          }
          className={inputClasses}
          placeholder={field.placeholder ?? undefined}
          minLength={settings?.min_length ?? undefined}
          maxLength={settings?.max_length ?? undefined}
          value={controlled ? stringify(value) : undefined}
          defaultValue={controlled ? undefined : field.default_value ?? undefined}
          disabled={disabled}
          onChange={(event) => onChange?.(event.target.value)}
        />
      )
      break
    case 'select':
      control = <Options field={field} value={value} onChange={onChange} disabled={disabled} />
      break
    case 'radio':
      return (
        <div>
          <span className="mb-1 flex text-sm font-medium text-slate-800">
            {field.label}
            {field.required && <span className="ml-0.5 text-red-600">*</span>}
          </span>
          <RadioGroup field={field} value={value} onChange={onChange} disabled={disabled} />
        </div>
      )
    default:
      control = (
        <input
          type="text"
          className={inputClasses}
          placeholder={field.placeholder ?? undefined}
          value={controlled ? stringify(value) : undefined}
          defaultValue={controlled ? undefined : field.default_value ?? undefined}
          disabled={disabled}
          onChange={(event) => onChange?.(event.target.value)}
        />
      )
  }

  return (
    <div>
      <label
        htmlFor={`entry-${field.field_key}`}
        className="mb-1 flex text-sm font-medium text-slate-800"
      >
        {field.label}
        {field.required && <span className="ml-0.5 text-red-600">*</span>}
      </label>
      <div>{control}</div>
      {field.description && <p className="mt-1 text-xs text-slate-500">{field.description}</p>}
    </div>
  )
}