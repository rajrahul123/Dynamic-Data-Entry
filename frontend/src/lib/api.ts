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

const TOKEN_KEY = 'ddep_access_token'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
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