import { useState } from 'react'

import type {
  FieldOption,
  FieldSettings,
  FieldType,
  FieldUpdate,
  FormField,
} from '../../lib/api'
import { FIELD_TYPES } from '../../lib/api'

interface FieldEditorPanelProps {
  field: FormField
  busy: boolean
  onSave: (patch: FieldUpdate) => Promise<void>
  onDelete: () => Promise<void>
}

const KEY_PATTERN = /^[a-z][a-z0-9_]*$/

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

interface DraftField {
  label: string
  field_key: string
  field_type: FieldType
  description: string
  placeholder: string
  required: boolean
  default_value: string
}

function emptySettings(): FieldSettings {
  return { min_length: null, max_length: null, min: null, max: null, step: null, options: null, checkbox_label: null }
}

function initialDraft(field: FormField): DraftField {
  return {
    label: field.label,
    field_key: field.field_key,
    field_type: field.field_type,
    description: field.description ?? '',
    placeholder: field.placeholder ?? '',
    required: field.required,
    default_value: field.default_value ?? '',
  }
}

function initialSettings(field: FormField): FieldSettings {
  return field.settings ? { ...emptySettings(), ...field.settings } : emptySettings()
}

const panelInput =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none'

export function FieldEditorPanel({ field, busy, onSave, onDelete }: FieldEditorPanelProps) {
  // The parent remounts this panel with `key={field.id}`, so state below is
  // initialized fresh whenever a different field is selected.
  const [draft, setDraft] = useState<DraftField>(() => initialDraft(field))
  const [settings, setSettings] = useState<FieldSettings>(() => initialSettings(field))
  const [keyTouched, setKeyTouched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function setFieldDraft<K extends keyof DraftField>(key: K, value: DraftField[K]) {
    setDraft((previous) => {
      const next = { ...previous, [key]: value }
      if (key === 'label' && !keyTouched) {
        next.field_key = slugify(String(value))
      }
      return next
    })
  }

  function handleTypeChange(type: FieldType) {
    setDraft((previous) => ({ ...previous, field_type: type }))
    setSettings(() => {
      const next = emptySettings()
      if (type === 'select' || type === 'radio') {
        next.options =
          draft.field_type === 'select' || draft.field_type === 'radio'
            ? (settings.options?.map((o) => ({ ...o })) ?? [])
            : null
      }
      return next
    })
  }

  function patchSettings<P extends keyof FieldSettings>(key: P, value: FieldSettings[P]) {
    setSettings((previous) => ({ ...previous, [key]: value }))
  }

  function setOption(index: number, patch: Partial<FieldOption>) {
    setSettings((previous) => {
      const options = (previous.options ? [...previous.options] : []) as FieldOption[]
      options[index] = { ...options[index], ...patch }
      return { ...previous, options }
    })
  }

  function removeOption(index: number) {
    setSettings((previous) => {
      const options = (previous.options ? [...previous.options] : []).filter((_, i) => i !== index)
      return { ...previous, options }
    })
  }

  function addOption() {
    setSettings((previous) => {
      const options = previous.options ?? []
      const label = `Option ${options.length + 1}`
      return { ...previous, options: [...options, { label, value: slugify(label) }] }
    })
  }

  async function handleApply() {
    setError(null)

    if (!draft.label.trim()) {
      setError('Label is required.')
      return
    }
    if (!KEY_PATTERN.test(draft.field_key)) {
      setError('Field key must be lowercase letters/digits/underscores and start with a letter.')
      return
    }
    if (
      draft.field_type === 'select' ||
      draft.field_type === 'radio'
    ) {
      const options = settings.options ?? []
      if (!options.length || options.some((o) => !o.label.trim() || !o.value.trim())) {
        setError('Add at least one option with a label and value.')
        return
      }
      if (new Set(options.map((o) => o.value)).size !== options.length) {
        setError('Option values must be unique.')
        return
      }
    }

    const clean = (settings.options ?? [])
      .map((o) => ({ label: o.label.trim(), value: o.value.trim() }))
      .filter((o) => o.label && o.value)

    const settingsPayload: FieldSettings = { ...emptySettings() }
    if (draft.field_type === 'select' || draft.field_type === 'radio') {
      settingsPayload.options = clean.length ? clean : null
    } else if (draft.field_type === 'checkbox') {
      settingsPayload.checkbox_label = settings.checkbox_label?.trim() || null
    } else if (draft.field_type === 'number') {
      settingsPayload.min = settings.min
      settingsPayload.max = settings.max
      settingsPayload.step = settings.step
    } else {
      settingsPayload.min_length = settings.min_length
      settingsPayload.max_length = settings.max_length
    }

    setSaving(true)
    try {
      await onSave({
        label: draft.label.trim(),
        field_key: draft.field_key,
        field_type: draft.field_type,
        description: draft.description.trim() || null,
        placeholder: draft.placeholder.trim() || null,
        required: draft.required,
        default_value: draft.default_value || null,
        settings: settingsPayload,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setSaving(false)
    }
  }

  const isSelectLike = draft.field_type === 'select' || draft.field_type === 'radio'

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Edit field</h3>
        <button
          type="button"
          disabled={busy || saving}
          onClick={() => onDelete()}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
        >
          Delete
        </button>
      </div>

      <div className="mt-4 space-y-4">
        <label className="block">
          <span className="text-xs font-medium text-slate-600">Label</span>
          <input
            className={`mt-1 ${panelInput}`}
            value={draft.label}
            onChange={(event) => setFieldDraft('label', event.target.value)}
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-600">Field key</span>
          <input
            className={`mt-1 font-mono ${panelInput}`}
            value={draft.field_key}
            onChange={(event) => {
              setKeyTouched(true)
              setFieldDraft('field_key', event.target.value)
            }}
          />
          <span className="mt-1 block text-[11px] text-slate-400">
            Unique identifier, used in submissions (auto-suggested from the label).
          </span>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-600">Field type</span>
          <select
            className={`mt-1 ${panelInput}`}
            value={draft.field_type}
            onChange={(event) => handleTypeChange(event.target.value as FieldType)}
          >
            {FIELD_TYPES.map(({ type, label }) => (
              <option key={type} value={type}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-600">Description (optional)</span>
          <input
            className={`mt-1 ${panelInput}`}
            value={draft.description}
            onChange={(event) => setFieldDraft('description', event.target.value)}
          />
        </label>

        {isSelectLike && (
          <div>
            <span className="text-xs font-medium text-slate-600">Options</span>
            <div className="mt-2 space-y-2">
              {(settings.options ?? []).map((option, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input
                    className={`flex-1 ${panelInput}`}
                    placeholder="Label"
                    value={option.label}
                    onChange={(event) => setOption(index, { label: event.target.value })}
                  />
                  <input
                    className={`flex-1 font-mono ${panelInput}`}
                    placeholder="value"
                    value={option.value}
                    onChange={(event) => setOption(index, { value: event.target.value })}
                  />
                  <button
                    type="button"
                    onClick={() => removeOption(index)}
                    className="rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                    aria-label="Remove option"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={addOption}
              className="mt-2 rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
            >
              + Add option
            </button>
          </div>
        )}

        {draft.field_type === 'checkbox' && (
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Checkbox label</span>
            <input
              className={`mt-1 ${panelInput}`}
              value={settings.checkbox_label ?? ''}
              onChange={(event) => patchSettings('checkbox_label', event.target.value)}
            />
            <span className="mt-1 block text-[11px] text-slate-400">
              Shown next to the box. Defaults to the field label.
            </span>
          </label>
        )}

        {draft.field_type === 'number' && (
          <div className="grid grid-cols-3 gap-2">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Min</span>
              <input
                type="number"
                className={`mt-1 ${panelInput}`}
                value={settings.min ?? ''}
                onChange={(event) =>
                  patchSettings('min', event.target.value === '' ? null : Number(event.target.value))
                }
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Max</span>
              <input
                type="number"
                className={`mt-1 ${panelInput}`}
                value={settings.max ?? ''}
                onChange={(event) =>
                  patchSettings('max', event.target.value === '' ? null : Number(event.target.value))
                }
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Step</span>
              <input
                type="number"
                className={`mt-1 ${panelInput}`}
                value={settings.step ?? ''}
                onChange={(event) =>
                  patchSettings('step', event.target.value === '' ? null : Number(event.target.value))
                }
              />
            </label>
          </div>
        )}

        {(draft.field_type === 'text' ||
          draft.field_type === 'textarea' ||
          draft.field_type === 'email' ||
          draft.field_type === 'phone') && (
          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Min length</span>
              <input
                type="number"
                className={`mt-1 ${panelInput}`}
                value={settings.min_length ?? ''}
                onChange={(event) =>
                  patchSettings('min_length', event.target.value === '' ? null : Number(event.target.value))
                }
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Max length</span>
              <input
                type="number"
                className={`mt-1 ${panelInput}`}
                value={settings.max_length ?? ''}
                onChange={(event) =>
                  patchSettings('max_length', event.target.value === '' ? null : Number(event.target.value))
                }
              />
            </label>
          </div>
        )}

        <label className="block">
          <span className="text-xs font-medium text-slate-600">Placeholder (optional)</span>
          <input
            className={`mt-1 ${panelInput}`}
            value={draft.placeholder}
            onChange={(event) => setFieldDraft('placeholder', event.target.value)}
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-slate-600">Default value (optional)</span>
          <input
            className={`mt-1 font-mono ${panelInput}`}
            value={draft.default_value}
            onChange={(event) => setFieldDraft('default_value', event.target.value)}
          />
        </label>

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={draft.required}
            onChange={(event) => setFieldDraft('required', event.target.checked)}
            className="accent-slate-900"
          />
          Required field
        </label>

        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <button
          type="button"
          disabled={busy || saving}
          onClick={handleApply}
          className="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? 'Applying…' : 'Apply changes'}
        </button>
      </div>
    </section>
  )
}