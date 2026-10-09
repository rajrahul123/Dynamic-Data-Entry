import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  listAvailableForms,
  listForms,
  listSubmissions,
  type AvailableForm,
  type Form,
  type SubmissionListItem,
} from '../lib/api'
import { useAuth } from '../lib/auth-context'
import {
  IconActivity,
  IconDownload,
  IconLayers,
  IconPlus,
  IconRecords,
} from '../components/icons'

const RECENT_SUBMISSION_PAGE = 100
const ACTIVITY_WINDOW_DAYS = 7

function greetingText(date: Date): string {
  const hour = date.getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [forms, setForms] = useState<Form[]>([])
  const [availableForms, setAvailableForms] = useState<AvailableForm[]>([])
  const [recentSubmissions, setRecentSubmissions] = useState<SubmissionListItem[]>([])
  const [recordsTotal, setRecordsTotal] = useState(0)
  const [recentActivityCount, setRecentActivityCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadWork() {
      try {
        const formData = await listForms()
        if (cancelled) return
        setForms(formData)

        let available: AvailableForm[]
        try {
          available = await listAvailableForms()
        } catch {
          available = []
        }
        if (cancelled) return
        setAvailableForms(available)

        const pages = await Promise.all(
          available.map((form) =>
            listSubmissions(form.id, { limit: RECENT_SUBMISSION_PAGE }).catch(() => null),
          ),
        )
        if (cancelled) return

        let total = 0
        const recent: SubmissionListItem[] = []
        for (const page of pages) {
          if (!page) continue
          total += page.total
          recent.push(...page.items)
        }
        recent.sort((a, b) => Date.parse(b.submitted_at) - Date.parse(a.submitted_at))

        const threshold = Date.now() - ACTIVITY_WINDOW_DAYS * 24 * 60 * 60 * 1000
        const activityCount = recent.filter(
          (item) => Date.parse(item.submitted_at) >= threshold,
        ).length

        setRecordsTotal(total)
        setRecentSubmissions(recent)
        setRecentActivityCount(activityCount)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadWork()
    return () => {
      cancelled = true
    }
  }, [])

  const recentForms = useMemo(() => forms.slice(0, 5), [forms])

  const publishedCount = useMemo(
    () => availableForms.filter((form) => form.status === 'published').length,
    [availableForms],
  )

  const firstPublishedForm = useMemo(
    () => availableForms.find((form) => form.status === 'published') ?? null,
    [availableForms],
  )

  const formNameById = useMemo(() => {
    const map = new Map<number, string>()
    for (const form of forms) map.set(form.id, form.name)
    for (const form of availableForms) map.set(form.id, form.name)
    return map
  }, [forms, availableForms])

  if (!user) return null

  const displayName = user.full_name || user.username

  function openSubmitEntry() {
    if (firstPublishedForm) {
      navigate(`/forms/${firstPublishedForm.id}/submit`)
    } else {
      navigate('/forms')
    }
  }

  function openExport() {
    if (firstPublishedForm) {
      navigate(`/forms/${firstPublishedForm.id}/records`)
    } else {
      navigate('/records')
    }
  }

  const quickActions = [
    {
      label: 'Create New Form',
      hint: 'Design a reusable form with fields',
      icon: IconPlus,
      onClick: () => navigate('/forms/new'),
    },
    {
      label: 'Submit Entry',
      hint: firstPublishedForm
        ? `Enter data into "${firstPublishedForm.name}"`
        : 'No published forms yet',
      icon: IconRecords,
      onClick: openSubmitEntry,
    },
    {
      label: 'View Records',
      hint: `${recordsTotal} submissions across all forms`,
      icon: IconActivity,
      onClick: () => navigate('/records'),
    },
    {
      label: 'Export Data',
      hint: 'Download records as CSV, XLSX, or PDF',
      icon: IconDownload,
      onClick: openExport,
    },
  ]

  const metricCards = [
    {
      label: 'Total forms created',
      value: loading ? null : forms.length,
      hint: `${publishedCount} published`,
      icon: IconLayers,
      iconClass: 'bg-indigo-100 text-indigo-600',
    },
    {
      label: 'Published forms',
      value: loading ? null : publishedCount,
      hint: `${availableForms.length} available for records`,
      icon: IconActivity,
      iconClass: 'bg-sky-100 text-sky-600',
    },
    {
      label: 'Total submissions',
      value: loading ? null : recordsTotal,
      hint: `${recentActivityCount} in the last ${ACTIVITY_WINDOW_DAYS} days`,
      icon: IconRecords,
      iconClass: 'bg-emerald-100 text-emerald-600',
    },
  ]

  return (
    <div className="page">
      {/* Header / greeting */}
      <section className="relative overflow-hidden rounded-2xl bg-slate-900 text-white shadow-md">
        <div
          className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-indigo-500/30 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-24 right-32 h-48 w-48 rounded-full bg-emerald-500/20 blur-3xl"
          aria-hidden="true"
        />
        <div className="relative flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
              Workspace overview
            </p>
            <h2 className="mt-1 text-2xl font-bold tracking-tight">
              {greetingText(new Date())}, {displayName}
            </h2>
            <p className="mt-1 text-sm text-slate-300">{user.email}</p>
            <p className="mt-3 text-xs text-slate-400">
              Account status:{' '}
              <span
                className={`tag ${user.is_active ? 'bg-emerald-700 text-emerald-100' : 'bg-red-700 text-red-100'}`}
              >
                {user.is_active ? 'Active' : 'Disabled'}
              </span>
            </p>
          </div>
        </div>
      </section>

      {error && <p className="banner-error">{error}</p>}

      {/* Metric cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {metricCards.map(({ label, value, hint, icon: Icon, iconClass }) => (
          <div key={label} className="card card-hover p-5">
            <div className="flex items-start justify-between">
              <span
                className={`flex h-10 w-10 items-center justify-center rounded-lg ${iconClass}`}
              >
                <Icon className="h-5 w-5" />
              </span>
              {loading ? (
                <span className="skeleton h-5 w-12" />
              ) : (
                <span className="tag tag-slate">{hint}</span>
              )}
            </div>
            <p className="mt-4 text-3xl font-bold tracking-tight text-slate-900">
              {value === null ? '…' : value}
            </p>
            <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-slate-500">
              {label}
            </p>
          </div>
        ))}
      </section>

      {/* Quick actions */}
      <section>
        <h3 className="text-sm font-semibold text-slate-700">Quick actions</h3>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {quickActions.map(({ label, hint, icon: Icon, onClick }) => (
            <button
              key={label}
              type="button"
              onClick={onClick}
              className="card card-hover group cursor-pointer p-4 text-left"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-500 transition-colors group-hover:bg-indigo-100 group-hover:text-indigo-600">
                <Icon className="h-4.5 w-4.5" />
              </span>
              <span className="mt-3 block text-sm font-semibold text-slate-900">{label}</span>
              <span className="mt-0.5 block text-xs text-slate-500">{hint}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Recent work */}
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <h3 className="text-sm font-semibold text-slate-900">Recent forms</h3>
            <button
              type="button"
              onClick={() => navigate('/forms')}
              className="link text-xs"
            >
              View all
            </button>
          </div>
          {loading ? (
            <div className="space-y-3 p-5">
              <span className="skeleton block h-10 w-full" />
              <span className="skeleton block h-10 w-full" />
              <span className="skeleton block h-10 w-full" />
            </div>
          ) : recentForms.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <IconLayers className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-2 text-sm text-slate-500">No forms yet.</p>
              <button
                type="button"
                onClick={() => navigate('/forms/new')}
                className="link mt-3 inline-flex items-center gap-1 text-sm"
              >
                <IconPlus className="h-4 w-4" />
                Create your first form
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-sticky">
                <thead>
                  <tr>
                    <th>Form</th>
                    <th>Status</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {recentForms.map((form) => (
                    <tr
                      key={form.id}
                      className="table-row-hover cursor-pointer"
                      onClick={() => navigate(`/forms/${form.id}/edit`)}
                    >
                      <td className="max-w-40 truncate font-medium text-slate-900">
                        {form.name}
                      </td>
                      <td>
                        <span
                          className={`tag ${
                            form.status === 'published'
                              ? 'tag-emerald'
                              : form.status === 'archived'
                                ? 'tag-slate'
                                : 'tag-amber'
                          }`}
                        >
                          {form.status}
                        </span>
                      </td>
                      <td className="whitespace-nowrap text-xs text-slate-500">
                        {new Date(form.updated_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <h3 className="text-sm font-semibold text-slate-900">Recent submissions</h3>
            <button type="button" onClick={() => navigate('/records')} className="link text-xs">
              View all
            </button>
          </div>
          {loading ? (
            <div className="space-y-3 p-5">
              <span className="skeleton block h-10 w-full" />
              <span className="skeleton block h-10 w-full" />
              <span className="skeleton block h-10 w-full" />
            </div>
          ) : recentSubmissions.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <IconRecords className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-2 text-sm text-slate-500">No submissions yet.</p>
              <button
                type="button"
                onClick={openSubmitEntry}
                className="link mt-3 inline-flex items-center gap-1 text-sm"
              >
                <IconPlus className="h-4 w-4" />
                Enter your first entry
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-sticky">
                <thead>
                  <tr>
                    <th>Form</th>
                    <th>Submission</th>
                    <th>Submitted</th>
                  </tr>
                </thead>
                <tbody>
                  {recentSubmissions.slice(0, 5).map((item) => (
                    <tr
                      key={item.id}
                      className="table-row-hover cursor-pointer"
                      onClick={() => navigate(`/forms/${item.form_id}/records/${item.id}`)}
                    >
                      <td className="max-w-36 truncate font-medium text-slate-900">
                        {formNameById.get(item.form_id) ?? `Form #${item.form_id}`}
                      </td>
                      <td className="text-xs text-slate-500">#{item.id}</td>
                      <td className="whitespace-nowrap text-xs text-slate-500">
                        {new Date(item.submitted_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

export default DashboardPage
