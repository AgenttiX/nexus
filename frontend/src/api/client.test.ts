import { afterEach, expect, test, vi } from 'vitest'

import { mockApi } from '../test-utils'
import { api, csrfToken } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

test('finds the CSRF token among cookies', () => {
  expect(csrfToken('sessionid=abc; csrftoken=secret; other=1')).toBe('secret')
  expect(csrfToken('sessionid=abc')).toBeUndefined()
})

test('sends the CSRF token only with requests that change data', async () => {
  document.cookie = 'csrftoken=secret'
  const seen: Record<string, string | null> = {}
  const record = (request: Request) => {
    seen[request.method] = request.headers.get('X-CSRFToken')
    return { status: 204 }
  }
  mockApi({ 'GET /api/me/': record, 'PUT /api/food/restaurants/1/favourite/': record })

  await api.GET('/api/me/')
  await api.PUT('/api/food/restaurants/{id}/favourite/', { params: { path: { id: 1 } } })

  expect(seen).toEqual({ GET: null, PUT: 'secret' })
})

test('sends no CSRF header when there is no cookie', async () => {
  let header: string | null = 'unset'
  mockApi({
    'DELETE /api/food/restaurants/1/favourite/': (request) => {
      header = request.headers.get('X-CSRFToken')
      return { status: 204 }
    },
  })
  await api.DELETE('/api/food/restaurants/{id}/favourite/', { params: { path: { id: 1 } } })
  expect(header).toBeNull()
})
