export interface HealthResponse {
  status: string
  api_version: string
  environment: string
  database: 'connected' | 'unavailable' | 'not_configured'
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/health', {
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }

  return (await response.json()) as HealthResponse
}