/** Typed client for the Nexus REST API. The types in `schema.d.ts` are generated with `npm run gen:api`. */
import createClient, { type Middleware } from 'openapi-fetch'

import type { components, paths } from './schema'

export type CurrentUser = components['schemas']['CurrentUser']
export type Restaurant = components['schemas']['Restaurant']
export type Dish = components['schemas']['Dish']
export type Calendar = components['schemas']['Calendar']
export type CalendarEvent = components['schemas']['Event']
export type SleepRecord = components['schemas']['SleepRecord']
export type SleepStats = components['schemas']['Stats']
export type Digest = components['schemas']['Digest']
export type NewsProfile = Required<components['schemas']['NewsProfile']>
export type NewsSource = components['schemas']['Source']
export type BankAccount = components['schemas']['BankAccount']
export type Category = components['schemas']['Category']
export type Transaction = components['schemas']['Transaction']
export type FinanceSummary = components['schemas']['FinanceSummary']
export type ImportBatch = components['schemas']['ImportBatch']
export type Holding = components['schemas']['Holding']
export type Portfolio = components['schemas']['Portfolio']
export type TimeSummary = components['schemas']['TimeSummary']

export const LOGIN_URL = '/accounts/oidc/authentik/login/'

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export function csrfToken(cookies: string): string | undefined {
  return cookies
    .split('; ')
    .find((cookie) => cookie.startsWith('csrftoken='))
    ?.slice('csrftoken='.length)
}

/** Django rejects requests that change data unless they echo the CSRF cookie in a header. */
const csrf: Middleware = {
  onRequest({ request }) {
    const token = csrfToken(document.cookie)
    if (!SAFE_METHODS.has(request.method) && token) {
      request.headers.set('X-CSRFToken', token)
    }
    return request
  },
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: 'same-origin',
  // Looked up on every call, so that tests can replace the global fetch.
  fetch: (request) => globalThis.fetch(request),
})
api.use(csrf)

export class ApiError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`API request failed with status ${status}`)
    this.status = status
  }
}

/** Unwraps an openapi-fetch result, turning error responses into exceptions for TanStack Query. */
export function unwrap<T>(result: { data?: T; response: Response }): T {
  if (!result.response.ok) {
    throw new ApiError(result.response.status)
  }
  return result.data as T
}

/** Returns the signed-in user, or null when there is no session. */
export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const result = await api.GET('/api/me/')
  if (result.response.status === 401 || result.response.status === 403) {
    return null
  }
  return unwrap(result)
}

/**
 * Uploads a file as a multipart form to `path` and returns the decoded answer.
 * The typed client is made for JSON, so files are sent with a plain request.
 */
export async function uploadFile<T>(path: string, file: File): Promise<T> {
  const body = new FormData()
  body.append('file', file)
  const response = await globalThis.fetch(
    new Request(new URL(path, window.location.origin), {
      method: 'POST',
      body,
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken(document.cookie) ?? '' },
    }),
  )
  if (!response.ok) {
    throw new ApiError(response.status)
  }
  return (await response.json()) as T
}
