/** Minimal fetch wrapper for the Nexus REST API. Replaced by the generated OpenAPI client as features land. */

export const LOGIN_URL = '/accounts/oidc/authentik/login/'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`API request failed with status ${status}`)
    this.status = status
  }
}

export interface CurrentUser {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new ApiError(response.status)
  }
  return (await response.json()) as T
}

/** Returns the signed-in user, or null when there is no session. */
export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await apiGet<CurrentUser>('me/')
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null
    }
    throw error
  }
}
