import { type JSX, useState } from 'react'

import {
  type AppliedQuery,
} from './QueryToolbar'
import { exportSubmissions, type ExportFormat } from '../../lib/api'

const FORMATS: { format: ExportFormat; label: string; description: string }[] = [
  { format: 'csv', label: 'CSV', description: 'Spreadsheet compatible' },
  { format: 'xlsx', label: 'Excel (.xlsx)', description: 'Formatted workbook' },
  { format: 'pdf', label: 'PDF', description: 'Printable table' },
  { format: 'sql', label: 'SQL', description: 'Raw INSERT statements' },
]

interface ExportMenuProps {
  formId: number
  query: AppliedQuery
  disabled?: boolean
  onError: (message: string) => void
  onNotice: (message: string) => void
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export function ExportMenu({ formId, query, disabled = false, onError, onNotice }: ExportMenuProps): JSX.Element {
  const [open, setOpen] = useState(false)
  const [busyFormat, setBusyFormat] = useState<ExportFormat | null>(null)

  async function handleExport(format: ExportFormat) {
    setBusyFormat(format)
    setOpen(false)
    try {
      const { blob, filename } = await exportSubmissions(formId, format, {
        search: query.search,
        filters: query.filters,
        sortBy: query.sortBy,
        sortOrder: query.sortOrder,
      })
      triggerDownload(blob, filename)
      onNotice(`${format.toUpperCase()} export downloaded as ${filename}.`)
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyFormat(null)
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled || busyFormat !== null}
        onClick={() => setOpen((current) => !current)}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
      >
        {busyFormat !== null ? 'Exporting…' : 'Export'}
      </button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close export menu"
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-10 cursor-default"
          />
          <div className="absolute right-0 z-20 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
            <p className="px-2 pb-1 pt-1 text-xs font-medium uppercase tracking-wide text-slate-500">
              Export records
            </p>
            {FORMATS.map(({ format, label, description }) => (
              <button
                key={format}
                type="button"
                disabled={busyFormat !== null}
                onClick={() => void handleExport(format)}
                className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left hover:bg-slate-50 disabled:opacity-50"
              >
                <span className="text-sm font-medium text-slate-800">{label}</span>
                <span className="text-xs text-slate-400">{description}</span>
              </button>
            ))}
            <p className="mt-1 border-t border-slate-100 px-2 pb-1 pt-2 text-xs text-slate-400">
              Applies current search, filters, and sort. All matching records are included.
            </p>
          </div>
        </>
      )}
    </div>
  )
}