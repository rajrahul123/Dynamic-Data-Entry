import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { SortableContext, arrayMove, verticalListSortingStrategy } from '@dnd-kit/sortable'

import {
  archiveForm,
  createField,
  deleteField,
  fetchForm,
  publishForm,
  reorderFields,
  updateField,
  updateForm,
  type FieldCreate,
  type FieldType,
  type FieldUpdate,
  type Form,
} from '../lib/api'
import { FieldEditorPanel } from '../components/forms/FieldEditorPanel'
import { FieldPalette } from '../components/forms/FieldPalette'
import { FormPreview } from '../components/forms/FormPreview'
import { SortableFieldCard } from '../components/forms/SortableFieldCard'

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function uniqueKey(existing: string[], base: string): string {
  const wanted = slugify(base) || 'field'
  if (!existing.includes(wanted)) return wanted
  let index = 2
  while (existing.includes(`${wanted}_${index}`)) index += 1
  return `${wanted}_${index}`
}

export function FormBuilderPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const formId = Number(id)

  const [form, setForm] = useState<Form | null>(null)
  const [nameInput, setNameInput] = useState('')
  const [descriptionInput, setDescriptionInput] = useState('')
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const sensors = useSensors(useSensor(PointerSensor))

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await fetchForm(formId)
        if (!cancelled) {
          setForm(data)
          setNameInput(data.name)
          setDescriptionInput(data.description ?? '')
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [formId])

  const selectedField = useMemo(
    () => form?.fields.find((field) => field.id === selectedFieldId) ?? null,
    [form, selectedFieldId],
  )

  const readonly = form !== null && form.status !== 'draft'

  async function run(action: () => Promise<unknown>, successMessage: string) {
    setError(null)
    setNotice(null)
    setExecuting(true)
    try {
      await action()
      setNotice(successMessage)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setExecuting(false)
    }
  }

  async function handleSaveMeta() {
    if (!form) return
    await run(async () => {
      const updated = await updateForm(form.id, {
        name: nameInput,
        description: descriptionInput || null,
      })
      setForm(updated)
      setNameInput(updated.name)
      setDescriptionInput(updated.description ?? '')
    }, 'Form details saved.')
  }

  async function handleAddField(type: FieldType) {
    if (!form) return
    await run(async () => {
      const existing = form.fields.map((field) => field.field_key)
      const field = await createField(form.id, {
        field_key: uniqueKey(existing, type),
        label: type,
        field_type: type,
      } satisfies FieldCreate)
      setForm((previous) =>
        previous
          ? { ...previous, fields: [...previous.fields, field] }
          : previous,
      )
      setSelectedFieldId(field.id)
    }, 'Field added.')
  }

  async function handleSaveField(patch: FieldUpdate) {
    if (!form || !selectedField) return
    await run(async () => {
      const updated = await updateField(form.id, selectedField.id, patch)
      setForm((previous) =>
        previous
          ? {
              ...previous,
              fields: previous.fields.map((field) =>
                field.id === updated.id ? updated : field,
              ),
            }
          : previous,
      )
    }, 'Field updated.')
  }

  async function handleDeleteField() {
    if (!form || !selectedField) return
    if (!window.confirm(`Delete field "${selectedField.label}"?`)) return
    await run(async () => {
      await deleteField(form.id, selectedField.id)
      setForm((previous) =>
        previous
          ? {
              ...previous,
              fields: previous.fields.filter((field) => field.id !== selectedField.id),
            }
          : previous,
      )
      setSelectedFieldId(null)
    }, 'Field deleted.')
  }

  async function handlePublish() {
    if (!form) return
    await run(async () => {
      const updated = await publishForm(form.id)
      setForm(updated)
    }, 'Form published. It is now read-only.')
  }

  async function handleArchive() {
    if (!form) return
    await run(async () => {
      const updated = await archiveForm(form.id)
      setForm(updated)
    }, 'Form archived.')
  }

  async function handleDragEnd(event: DragEndEvent) {
    if (!form || !event.over || event.active.id === event.over.id) return
    const activeId = Number(event.active.id)
    const overId = Number(event.over.id)
    const oldIndex = form.fields.findIndex((field) => field.id === activeId)
    const newIndex = form.fields.findIndex((field) => field.id === overId)
    if (oldIndex < 0 || newIndex < 0) return

    const reordered = arrayMove(form.fields, oldIndex, newIndex)
    const orderedFields = reordered.map((field, index) => ({ ...field, sort_order: index }))
    setForm((previous) => (previous ? { ...previous, fields: orderedFields } : previous))

    setError(null)
    setNotice(null)
    try {
      await reorderFields(form.id, orderedFields.map((field) => field.id))
      setNotice('Field order saved.')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      const data = await fetchForm(form.id)
      setForm(data)
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-500">Loading form…</p>
  }

  if (!form) {
    return (
      <div className="space-y-4">
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error ?? 'Could not load the form.'}
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate('/forms')}
          className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        >
          ← Back to forms
        </button>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            form.status === 'published'
              ? 'bg-emerald-100 text-emerald-700'
              : form.status === 'archived'
                ? 'bg-slate-200 text-slate-600'
                : 'bg-slate-100 text-slate-600'
          }`}
        >
          {form.status}
        </span>
      </div>

      {readonly && (
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
          This form is {form.status}. Its definition is locked and cannot be changed. To modify
          it, create a new form or repurpose a draft.
        </p>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Form name</span>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500"
              value={nameInput}
              disabled={readonly}
              onChange={(event) => setNameInput(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Description (optional)</span>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500"
              value={descriptionInput}
              disabled={readonly}
              onChange={(event) => setDescriptionInput(event.target.value)}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={readonly || executing}
            onClick={handleSaveMeta}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {executing ? 'Saving…' : 'Save details'}
          </button>

          {form.status === 'draft' && (
            <button
              type="button"
              disabled={executing || form.fields.length === 0}
              onClick={handlePublish}
              className="rounded-lg border border-emerald-300 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
              title={
                form.fields.length === 0
                  ? 'Add at least one field before publishing.'
                  : undefined
              }
            >
              Publish
            </button>
          )}

          {form.status !== 'archived' && (
            <button
              type="button"
              disabled={executing}
              onClick={handleArchive}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              Archive
            </button>
          )}
        </div>

        {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {notice && (
          <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {notice}
          </p>
        )}
      </section>

      {!readonly && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-4">
            <FieldPalette onAddField={handleAddField} busy={executing} />
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-900">Fields</h3>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                  {form.fields.length}
                </span>
              </div>
              {form.fields.length === 0 ? (
                <p className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-400">
                  No fields yet. Pick a type from the palette to start.
                </p>
              ) : (
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                  <SortableContext
                    items={form.fields.map((field) => field.id)}
                    strategy={verticalListSortingStrategy}
                  >
                    <div className="space-y-2">
                      {form.fields.map((field) => (
                        <SortableFieldCard
                          key={field.id}
                          field={field}
                          selected={field.id === selectedFieldId}
                          onSelect={(selected) => setSelectedFieldId(selected.id)}
                        />
                      ))}
                    </div>
                  </SortableContext>
                </DndContext>
              )}
            </div>
          </div>

          <div className="lg:col-span-2">
            {selectedField ? (
              <FieldEditorPanel
                key={selectedField.id}
                field={selectedField}
                busy={executing}
                onSave={handleSaveField}
                onDelete={handleDeleteField}
              />
            ) : (
              <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
                Select a field to edit it, or add a new one from the palette.
              </p>
            )}
          </div>
        </div>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-900">Preview</h3>
        <p className="mb-4 mt-0.5 text-xs text-slate-500">
          How this form renders for a submitter. Validation and submission come in a later phase.
        </p>
        <FormPreview fields={form.fields} />
      </section>
    </div>
  )
}