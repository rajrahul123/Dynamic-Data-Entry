import type { ReactNode } from 'react'

import type { FormField } from '../../lib/api'

interface FieldRendererProps {
  field: FormField
}

const inputClasses =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none'

function Options({ field }: FieldRendererProps) {
  const options = field.settings?.options ?? []
  return (
    <select className={inputClasses} defaultValue={field.default_value ?? undefined}>
      {field.settings?.options === null || !options.length ? (
        <option value="">— no options —</option>
      ) : (
        options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))
      )}
    </select>
  )
}

function RadioGroup({ field }: FieldRendererProps) {
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
            name={field.field_key}
            value={option.value}
            defaultChecked={field.default_value === option.value}
            className="accent-slate-900"
          />
          {option.label}
        </label>
      ))}
    </div>
  )
}

export function FieldRenderer({ field }: FieldRendererProps) {
  const { settings } = field

  if (field.field_type === 'checkbox') {
    return (
      <label className="flex items-start gap-2 text-sm text-slate-700">
        <input type="checkbox" className="mt-0.5 accent-slate-900" />
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
          defaultValue={field.default_value ?? undefined}
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
          defaultValue={field.default_value ?? undefined}
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
          defaultValue={field.default_value ?? undefined}
        />
      )
      break
    case 'select':
      control = <Options field={field} />
      break
    case 'radio':
      return (
        <div>
          <span className="mb-1 flex text-sm font-medium text-slate-800">
            {field.label}
            {field.required && <span className="ml-0.5 text-red-600">*</span>}
          </span>
          <RadioGroup field={field} />
        </div>
      )
    default:
      control = <input type="text" className={inputClasses} placeholder={field.placeholder ?? undefined} />
  }

  return (
    <div>
      <label
        htmlFor={`preview-${field.field_key}`}
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