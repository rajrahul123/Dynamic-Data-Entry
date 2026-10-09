import { useEffect, useMemo, useState } from 'react'

import {
  type FieldType,
  type Form,
  type FormField,
  type RecordFilter,
} from '../../lib/api'

export interface AppliedQuery {
  search?: string
  filters?: RecordFilter[]
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

interface QueryToolbarProps {
  form: Form
  query: AppliedQuery
  onApply: (next: AppliedQuery) => void
}

const inputClasses = 'input'

const OPERATOR_LABELS: Record<string, string> = {
  equals: 'equals',
  not_equals: 'not equals',
  contains: 'contains',
  starts_with: 'starts with',
  ends_with: 'ends with',
  greater_than: '>',
  greater_than_or_equal: '>=',
  less_than: '<',
  less_than_or_equal: '<=',
  between: 'between',
  before: 'before',
  after: 'after',
  on_or_before: 'on or before',
  on_or_after: 'on or after',
}

const OPERATORS_BY_TYPE: Record<FieldType, string[]> = {
  text: ['equals', 'contains', 'starts_with', 'ends_with'],
  textarea: ['equals', 'contains', 'starts_with', 'ends_with'],
  email: ['equals', 'contains', 'starts_with', 'ends_with'],
  phone: ['equals', 'contains', 'starts_with', 'ends_with'],
  number: [
    'equals',
    'not_equals',
    'greater_than',
    'greater_than_or_equal',
    'less_than',
    'less_than_or_equal',
    'between',
  ],
  date: ['equals', 'before', 'after', 'on_or_before', 'on_or_after', 'between'],
  time: ['equals', 'before', 'after', 'between'],
  datetime: ['equals', 'before', 'after', 'on_or_before', 'on_or_after', 'between'],
  select: ['equals', 'not_equals'],
  radio: ['equals', 'not_equals'],
  checkbox: ['equals'],
}

function valueInputType(field: FormField): string {
  switch (field.field_type) {
    case 'number':
      return 'number'
    case 'date':
      return 'date'
    case 'time':
      return 'time'
    case 'datetime':
      return 'datetime-local'
    default:
      return 'text'
  }
}

function parseFilterValue(field: FormField, operator: string, raw: { first: string; second: string }): unknown {
  if (operator === 'between') {
    return [raw.first, raw.second]
  }
  if (field.field_type === 'checkbox') {
    return raw.first === 'true'
  }
  if (field.field_type === 'number') {
    return raw.first === '' ? null : Number(raw.first)
  }
  return raw.first
}

export function QueryToolbar({ form, query, onApply }: QueryToolbarProps) {
  const [searchDraft, setSearchDraft] = useState(query.search ?? '')
  const [filterField, setFilterField] = useState('')
  const [filterOperator, setFilterOperator] = useState('equals')
  const [filterValue, setFilterValue] = useState('')
  const [filterSecondValue, setFilterSecondValue] = useState('')

  const fieldByKey = useMemo(() => {
    const map = new Map<string, FormField>()
    for (const field of form.fields) map.set(field.field_key, field)
    return map
  }, [form.fields])

  const selectedFilterField = fieldByKey.get(filterField)
  const availableOperators = selectedFilterField ? OPERATORS_BY_TYPE[selectedFilterField.field_type] : []
  const isBetween = selectedFilterField !== undefined && filterOperator === 'between'

  useEffect(() => {
    const timer = setTimeout(() => {
      onApply({
        ...query,
        search: searchDraft.trim() === '' ? undefined : searchDraft.trim(),
      })
    }, 350)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchDraft])

  function handleFilterFieldChange(fieldKey: string) {
    setFilterField(fieldKey)
    const field = fieldByKey.get(fieldKey)
    setFilterOperator(field ? OPERATORS_BY_TYPE[field.field_type][0] : 'equals')
    setFilterValue('')
    setFilterSecondValue('')
  }

  function addFilter() {
    const field = selectedFilterField
    if (!field || !isBetween && filterValue === '') return
    if (isBetween && (filterValue === '' || filterSecondValue === '')) return
    const value = parseFilterValue(field, filterOperator, {
      first: filterValue,
      second: filterSecondValue,
    })
    if (value === null) return
    onApply({
      ...query,
      filters: [
        ...(query.filters ?? []),
        { field: field.field_key, operator: filterOperator, value },
      ],
    })
    setFilterValue('')
    setFilterSecondValue('')
  }

  function removeFilter(index: number) {
    onApply({
      ...query,
      filters: (query.filters ?? []).filter((_, i) => i !== index),
    })
  }

  function updateSort(by: string, order: 'asc' | 'desc') {
    onApply({
      ...query,
      sortBy: by === '' ? undefined : by,
      sortOrder: order,
    })
  }

  const activeFilters = query.filters ?? []

  return (
    <section className="card space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="Search records…"
          className={`${inputClasses} w-64`}
        />
        <select
          value={query.sortBy ?? ''}
          onChange={(event) => updateSort(event.target.value, query.sortOrder ?? 'desc')}
          className={inputClasses}
        >
          <option value="">No sort</option>
          {form.fields
            .slice()
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((field) => (
              <option key={field.id} value={field.field_key}>
                Sort by {field.label}
              </option>
            ))}
        </select>
        <select
          value={query.sortOrder ?? 'desc'}
          onChange={(event) => updateSort(query.sortBy ?? '', event.target.value as 'asc' | 'desc')}
          className={inputClasses}
          disabled={(query.sortBy ?? '') === ''}
        >
          <option value="desc">Newest first</option>
          <option value="asc">Oldest first</option>
        </select>
        {(query.sortBy ?? '') !== '' && (
          <button
            type="button"
            onClick={() => updateSort('', 'desc')}
            className="btn btn-secondary btn-sm"
          >
            Clear sort
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          Filter field
          <select
            value={filterField}
            onChange={(event) => handleFilterFieldChange(event.target.value)}
            className={inputClasses}
          >
            <option value="">Select field…</option>
            {form.fields
              .slice()
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((field) => (
                <option key={field.id} value={field.field_key}>
                  {field.label}
                </option>
              ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          Operator
          <select
            value={filterOperator}
            onChange={(event) => setFilterOperator(event.target.value)}
            className={inputClasses}
            disabled={!selectedFilterField}
          >
            {availableOperators.map((operator) => (
              <option key={operator} value={operator}>
                {OPERATOR_LABELS[operator] ?? operator}
              </option>
            ))}
          </select>
        </label>
        {selectedFilterField && (
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isBetween ? `${selectedFilterField.label} low` : selectedFilterField.field_type === 'checkbox' ? 'Value' : 'Value'}
            {selectedFilterField.field_type === 'checkbox' ? (
              <select
                value={filterValue}
                onChange={(event) => setFilterValue(event.target.value)}
                className={inputClasses}
              >
                <option value="">Select…</option>
                <option value="true">Checked</option>
                <option value="false">Unchecked</option>
              </select>
            ) : selectedFilterField.field_type === 'select' ||
              selectedFilterField.field_type === 'radio' ? (
              <select
                value={filterValue}
                onChange={(event) => setFilterValue(event.target.value)}
                className={inputClasses}
              >
                <option value="">Select…</option>
                {(selectedFilterField.settings?.options ?? []).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={valueInputType(selectedFilterField)}
                value={filterValue}
                onChange={(event) => setFilterValue(event.target.value)}
                className={inputClasses}
              />
            )}
          </label>
        )}
        {selectedFilterField && isBetween && (
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {selectedFilterField.label} high
            <input
              type={valueInputType(selectedFilterField)}
              value={filterSecondValue}
              onChange={(event) => setFilterSecondValue(event.target.value)}
              className={inputClasses}
            />
          </label>
        )}
        <button
          type="button"
          onClick={addFilter}
          disabled={!selectedFilterField || (isBetween ? filterValue === '' || filterSecondValue === '' : filterValue === '')}
          className="btn btn-primary btn-sm"
        >
          Add filter
        </button>
      </div>

      {activeFilters.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500">Active filters:</span>
          {activeFilters.map((filter, index) => {
            const field = fieldByKey.get(filter.field)
            return (
              <span
                key={`${filter.field}-${filter.operator}-${index}`}
                className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700"
              >
                {field?.label ?? filter.field} {OPERATOR_LABELS[filter.operator] ?? filter.operator}{' '}
                {Array.isArray(filter.value)
                  ? `${String(filter.value[0])} – ${String(filter.value[1])}`
                  : String(filter.value)}
                <button
                  type="button"
                  onClick={() => removeFilter(index)}
                  className="ml-1 text-slate-400 hover:text-red-600"
                  aria-label={`Remove filter on ${field?.label ?? filter.field}`}
                >
                  ×
                </button>
              </span>
            )
          })}
        </div>
      )}
    </section>
  )
}