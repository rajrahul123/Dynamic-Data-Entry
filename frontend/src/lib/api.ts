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