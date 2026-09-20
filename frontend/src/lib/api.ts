export interface HealthResponse {
  status: string
  api_version: string
  environment: string
  database: 'connected' | 'unavailable' | 'not_configured'
}

export type Role = 'admin' | 'operator' | 'viewer'

export interface User {
  id: number
  username: string
  email: string
  full_name: string | null
  role: Role
  is_active: boolean
  created_at: string
  updated_at: string
  last_login_at: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface UserCreate {
  username: string
  email: string
  password: string
  full_name?: string | null
  role?: Role
}

export interface UserUpdate {
  email?: string
  full_name?: string | null
  password?: string
  role?: Role
  is_active?: boolean
}

export type FormStatus = 'draft' | 'published' | 'archived'

export type FieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'email'
  | 'phone'
  | 'date'
  | 'time'
  | 'datetime'
  | 'select'
  | 'radio'
  | 'checkbox'

export interface FieldOption {
  label: string
  value: string
}

export interface FieldSettings {
  min_length?: number | null
  max_length?: number | null
  min?: number | null
  max?: number | null
  step?: number | null
  options?: FieldOption[] | null
  checkbox_label?: string | null
}

export interface FormField {
  id: number
  form_id: number
  field_key: string
  label: string
  field_type: FieldType
  description: string | null
  placeholder: string | null
  required: boolean
  default_value: string | null
  sort_order: number
  settings: FieldSettings | null
  created_at: string
  updated_at: string
}

export interface Form {
  id: number
  name: string
  description: string | null
  status: FormStatus
  created_by: number
  created_at: string
  updated_at: string
  published_at: string | null
  fields: FormField[]
}

export interface FormCreate {
  name: string
  description?: string | null
}

export interface FormUpdate {
  name?: string
  description?: string | null
}

export interface FieldCreate {
  field_key: string
  label: string
  field_type: FieldType
  description?: string | null
  placeholder?: string | null
  required?: boolean
  default_value?: string | null
  sort_order?: number | null
  settings?: FieldSettings | null
}

export interface FieldUpdate {
  field_key?: string
  label?: string
  field_type?: FieldType
  description?: string | null
  placeholder?: string | null
  required?: boolean
  default_value?: string | null
  sort_order?: number | null
  settings?: FieldSettings | null
}

export interface FieldReorder {
  field_ids: number[]
}

export interface SubmissionCreate {
  data: Record<string, unknown>
}

export interface SubmissionUpdate {
  data: Record<string, unknown>
}

export interface SubmissionResponse {
  id: number
  form_id: number
  submitted_by: number
  data: Record<string, unknown>
  submitted_at: string
  updated_at: string
}

export interface SubmissionListItem {
  id: number
  form_id: number
  submitted_by: number
  submitted_by_username: string | null
  submitted_by_full_name: string | null
  data: Record<string, unknown>
  submitted_at: string
  updated_at: string
}

export interface SubmissionListResponse {
  items: SubmissionListItem[]
  total: number
  limit: number
  offset: number
}

export interface AvailableForm {
  id: number
  name: string
  description: string | null
  status: FormStatus
  updated_at: string
}

export interface ValidationErrorDetail {
  loc: (string | number)[]
  msg: string
  type: string
}

const TOKEN_KEY = 'ddep_access_token'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, message: string, detail: unknown = null) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token === null) {
    localStorage.removeItem(TOKEN_KEY)
  } else {
    localStorage.setItem(TOKEN_KEY, token)
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (authenticated) {
    const token = getToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(path, { ...options, headers })

  if (response.status === 204) {
    return undefined as T
  }

  if (response.status === 401 && authenticated) {
    setToken(null)
    window.dispatchEvent(new Event('auth:unauthorized'))
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    let detail: unknown = null
    try {
      const body: unknown = await response.json()
      if (
        typeof body === 'object' &&
        body !== null &&
        'detail' in body
      ) {
        const bodyDetail = (body as { detail: unknown }).detail
        if (typeof bodyDetail === 'string') {
          message = bodyDetail
        } else {
          detail = bodyDetail
        }
      }
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, message, detail)
  }

  return (await response.json()) as T
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health', { headers: { Accept: 'application/json' } }, false)
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>(
    '/api/auth/login',
    {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    },
    false,
  )
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  full_name?: string | null
}

export async function register(data: RegisterRequest): Promise<User> {
  return request<User>(
    '/api/auth/register',
    {
      method: 'POST',
      body: JSON.stringify(data),
    },
    false,
  )
}

export async function fetchMe(): Promise<User> {
  return request<User>('/api/auth/me')
}

export async function listUsers(): Promise<User[]> {
  return request<User[]>('/api/users')
}

export async function createUser(data: UserCreate): Promise<User> {
  return request<User>('/api/users', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateUser(id: number, patch: UserUpdate): Promise<User> {
  return request<User>(`/api/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function listForms(options?: { status?: FormStatus }): Promise<Form[]> {
  const query = options?.status ? `?status=${options.status}` : ''
  return request<Form[]>(`/api/forms${query}`)
}

export async function fetchForm(id: number): Promise<Form> {
  return request<Form>(`/api/forms/${id}`)
}

export async function createForm(data: FormCreate): Promise<Form> {
  return request<Form>('/api/forms', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateForm(id: number, patch: FormUpdate): Promise<Form> {
  return request<Form>(`/api/forms/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function deleteForm(id: number): Promise<void> {
  return request<void>(`/api/forms/${id}`, { method: 'DELETE' })
}

export async function publishForm(id: number): Promise<Form> {
  return request<Form>(`/api/forms/${id}/publish`, { method: 'POST' })
}

export async function archiveForm(id: number): Promise<Form> {
  return request<Form>(`/api/forms/${id}/archive`, { method: 'POST' })
}

export async function createField(formId: number, data: FieldCreate): Promise<FormField> {
  return request<FormField>(`/api/forms/${formId}/fields`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateField(
  formId: number,
  fieldId: number,
  patch: FieldUpdate,
): Promise<FormField> {
  return request<FormField>(`/api/forms/${formId}/fields/${fieldId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function deleteField(formId: number, fieldId: number): Promise<void> {
  return request<void>(`/api/forms/${formId}/fields/${fieldId}`, { method: 'DELETE' })
}

export async function reorderFields(formId: number, fieldIds: number[]): Promise<FormField[]> {
  return request<FormField[]>(`/api/forms/${formId}/fields/reorder`, {
    method: 'POST',
    body: JSON.stringify({ field_ids: fieldIds }),
  })
}

export async function fetchFormDefinition(id: number): Promise<Form> {
  return request<Form>(`/api/forms/${id}/definition`)
}

export async function listAvailableForms(): Promise<AvailableForm[]> {
  return request<AvailableForm[]>('/api/records/forms')
}

export interface RecordFilter {
  field: string
  operator: string
  value: unknown
}

export interface SubmissionQueryOptions {
  limit?: number
  offset?: number
  search?: string
  filters?: RecordFilter[]
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export type ExportFormat = 'csv' | 'xlsx' | 'pdf' | 'sql'

export interface ExportResult {
  blob: Blob
  filename: string
}

export function buildSubmissionQueryParams(
  options: SubmissionQueryOptions = {},
  withPagination = true,
): URLSearchParams {
  const params = new URLSearchParams()
  if (withPagination) {
    params.set('limit', String(options.limit ?? 20))
    params.set('offset', String(options.offset ?? 0))
  }
  const fields: [string, string | number | undefined][] = [
    ['search', options.search],
    ['sort_by', options.sortBy],
    ['sort_order', options.sortOrder],
  ]
  for (const [key, value] of fields) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  if (options.filters && options.filters.length > 0) {
    params.set('filters', JSON.stringify(options.filters))
  }
  return params
}

export async function listSubmissions(
  formId: number,
  options: SubmissionQueryOptions = {},
): Promise<SubmissionListResponse> {
  return request<SubmissionListResponse>(
    `/api/forms/${formId}/submissions?${buildSubmissionQueryParams(options).toString()}`,
  )
}

export async function exportSubmissions(
  formId: number,
  format: ExportFormat,
  options: Omit<SubmissionQueryOptions, 'limit' | 'offset'> = {},
): Promise<ExportResult> {
  const params = buildSubmissionQueryParams(options, false)
  params.set('format', format)
  const token = getToken()
  const response = await fetch(
    `/api/forms/${formId}/submissions/export?${params.toString()}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  )

  if (response.status === 401) {
    setToken(null)
    window.dispatchEvent(new Event('auth:unauthorized'))
  }

  if (!response.ok) {
    let message = `Export failed with status ${response.status}`
    try {
      const body: unknown = await response.json()
      if (
        typeof body === 'object' &&
        body !== null &&
        'detail' in body &&
        typeof (body as { detail: unknown }).detail === 'string'
      ) {
        message = (body as { detail: string }).detail
      }
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, message)
  }

  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = /filename="([^"]+)"/.exec(disposition)
  const filename = match ? match[1] : `records.${format}`
  return { blob: await response.blob(), filename }
}

export async function fetchSubmission(
  formId: number,
  submissionId: number,
): Promise<SubmissionListItem> {
  return request<SubmissionListItem>(`/api/forms/${formId}/submissions/${submissionId}`)
}

export async function updateSubmission(
  formId: number,
  submissionId: number,
  data: Record<string, unknown>,
): Promise<SubmissionListItem> {
  return request<SubmissionListItem>(`/api/forms/${formId}/submissions/${submissionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ data } satisfies SubmissionUpdate),
  })
}

export async function deleteSubmission(formId: number, submissionId: number): Promise<void> {
  return request<void>(`/api/forms/${formId}/submissions/${submissionId}`, { method: 'DELETE' })
}

export async function submitSubmission(
  formId: number,
  data: Record<string, unknown>,
): Promise<SubmissionResponse> {
  return request<SubmissionResponse>(`/api/forms/${formId}/submissions`, {
    method: 'POST',
    body: JSON.stringify({ data }),
  })
}

export const FIELD_TYPES: { type: FieldType; label: string }[] = [
  { type: 'text', label: 'Short text' },
  { type: 'textarea', label: 'Long text' },
  { type: 'number', label: 'Number' },
  { type: 'email', label: 'Email' },
  { type: 'phone', label: 'Phone' },
  { type: 'date', label: 'Date' },
  { type: 'time', label: 'Time' },
  { type: 'datetime', label: 'Date & time' },
  { type: 'select', label: 'Dropdown' },
  { type: 'radio', label: 'Choice group' },
  { type: 'checkbox', label: 'Checkbox' },
]