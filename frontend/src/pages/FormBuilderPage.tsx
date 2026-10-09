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
import { IconX } from '../components/icons'
import { FieldEditorPanel } from '../components/forms/FieldEditorPanel'
import { FieldPalette } from '../components/forms/FieldPalette'
import { FormPreview } from '../components/forms/FormPreview'
import { SortableFieldCard } from '../components/forms/SortableFieldCard'
import { useToast } from '../lib/toast-context'

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
  const { toast } = useToast()
  const formId = Number(id)

  const [form, setForm] = useState<Form | null>(null)
  const [nameInput, setNameInput] = useState('')
  const [descriptionInput, setDescriptionInput] = useState('')
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null)
  const [confirmDeleteField, setConfirmDeleteField] = useState<Form['fields'][number] | null>(null)
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

  const isLive = form !== null && form.status !== 'draft'

  async function run(action: () => Promise<unknown>, successMessage: string) {
    setError(null)
    setNotice(null)
    setExecuting(true)
    try {
      await action()
      setNotice(successMessage)
      toast('success', successMessage)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
      toast('error', message)
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
    }, 'Form updated successfully.')
  }

  async function handleSaveAndExit() {
    if (!form) return
    await run(async () => {
      await updateForm(form.id, {
        name: nameInput,
        description: descriptionInput || null,
      })
    }, 'Form updated successfully.')
    navigate('/forms')
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

  async function handleDeleteField(field: typeof selectedField) {
    if (!form || !field) return
    await run(async () => {
      await deleteField(form.id, field.id)
      setForm((previous) =>
        previous
          ? {
              ...previous,
              fields: previous.fields.filter((candidate) => candidate.id !== field.id),
            }
          : previous,
      )
      if (selectedFieldId === field.id) setSelectedFieldId(null)
    }, `Field "${field.label}" deleted.`)
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
      toast('success', 'Field order saved.')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
      toast('error', message)
      const data = await fetchForm(form.id)
      setForm(data)
    }
  }

  if (loading) {
    return (
      <div className="page space-y-3">
        <span className="skeleton block h-8 w-40" />
        <span className="skeleton block h-36 w-full" />
        <span className="skeleton block h-24 w-full" />
      </div>
    )
  }

  if (!form) {
    return (
      <div className="page">
        <p className="banner-error">{error ?? 'Could not load the form.'}</p>
        <button
          type="button"
          onClick={() => navigate('/forms')}
          className="btn btn-secondary"
        >
          ← Back to forms
        </button>
      </div>
    )
  }

  const statusClass =
    form.status === 'published'
      ? 'tag-emerald'
      : form.status === 'archived'
        ? 'tag-slate'
        : 'tag-amber'

  return (
    <div className="page">
      <header className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate('/forms')}
          className="btn btn-ghost btn-sm"
        >
          ← Back to forms
        </button>
        <span className={`tag ${statusClass}`}>{form.status}</span>
      </header>

      {isLive && (
        <p className="banner-info">
          Editing a {form.status} form will update the form template for future submissions.
          Existing records are preserved.
        </p>
      )}

      <section className="card">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="label">Form name</span>
            <input
              className="input"
              value={nameInput}
              onChange={(event) => setNameInput(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="label">Description (optional)</span>
            <input
              className="input"
              value={descriptionInput}
              onChange={(event) => setDescriptionInput(event.target.value)}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={executing}
            onClick={() => void handleSaveMeta()}
            className="btn btn-primary"
          >
            {executing ? 'Saving…' : 'Save Changes'}
          </button>

          <button
            type="button"
            disabled={executing}
            onClick={() => void handleSaveAndExit()}
            className="btn btn-secondary"
          >
            Save &amp; exit
          </button>

          {form.status === 'draft' && (
            <button
              type="button"
              disabled={executing || form.fields.length === 0}
              onClick={() => void handlePublish()}
              className="btn border border-emerald-300 text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
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
              onClick={() => void handleArchive()}
              className="btn btn-secondary"
            >
              Archive
            </button>
          )}
        </div>

        {error && <p className="mt-4 banner-error">{error}</p>}
        {notice && <p className="mt-4 banner-success">{notice}</p>}
      </section>

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
                onDelete={() => handleDeleteField(selectedField)}
              />
            ) : (
              <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
                Select a field to edit it, or add a new one from the palette.
              </p>
            )}
          </div>
        </div>

        <section className="card">
          <h3 className="text-sm font-semibold text-slate-900">Preview</h3>
          <p className="mb-4 mt-0.5 text-xs text-slate-500">
            How this form renders for a submitter. Required rules and per-type validation apply at
            submission and record edit time.
          </p>
          <FormPreview fields={form.fields} />
        </section>

      {confirmDeleteField && (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-field-title"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 id="delete-field-title" className="text-lg font-semibold text-slate-900">
                  Delete field
                </h3>
                <p className="mt-1 text-sm text-slate-600">
                  Delete "{confirmDeleteField.label}" from this form? This action cannot be
                  undone.
                </p>
              </div>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setConfirmDeleteField(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                <IconX className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteField(null)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={executing}
                onClick={() => {
                  void handleDeleteField(confirmDeleteField)
                  setConfirmDeleteField(null)
                }}
                className="btn btn-danger"
              >
                {executing ? 'Deleting…' : 'Delete field'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}