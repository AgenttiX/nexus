import { afterEach, expect, test, vi } from 'vitest'

import { setNative } from '../test-native'
import { refresh } from './oidc'
import { getSession, saveSession, type Session } from './session'
import { apiFetch } from './transport'

const fresh = { accessToken: 'access-1', refreshToken: 'refresh-1', expiresAt: Date.now() + 600_000 }
const session: Session = { serverUrl: 'https://nexus.test', issuer: 'https://auth.test/o/', clientId: 'app', tokens: fresh }
const renewed = { accessToken: 'access-2', refreshToken: 'refresh-2', expiresAt: Date.now() + 600_000 }

/** Answers 200 to requests carrying one of the accepted tokens and 403 to the rest; records what it saw. */
function server(accepted: string[]) {
  const seen: { url: string; authorization: string | null; credentials: string; body: string }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const authorization = request.headers.get('Authorization')
      seen.push({ url: request.url, authorization, credentials: request.credentials, body: await request.text() })
      return new Response(null, { status: accepted.includes(authorization ?? '') ? 200 : 403 })
    }),
  )
  return seen
}

const get = () => apiFetch(new Request('http://localhost:3000/api/me/?x=1'))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(refresh).mockReset()
})

test('in a browser the request is sent unchanged', async () => {
  const seen = server([''])
  await saveSession(session)
  expect((await get()).status).toBe(200)
  expect(seen).toEqual([{ url: 'http://localhost:3000/api/me/?x=1', authorization: null, credentials: 'same-origin', body: '' }])
})

test('the app answers 401 itself until a server is chosen', async () => {
  setNative(true)
  const seen = server([])
  expect((await get()).status).toBe(401)
  expect(seen).toEqual([])
})

test('the app sends requests to its server with the access token and without cookies', async () => {
  setNative(true)
  const seen = server(['Bearer access-1'])
  await saveSession(session)

  expect((await get()).status).toBe(200)
  const post = new Request('http://localhost:3000/api/x/', { method: 'POST', body: '{"a":1}' })
  expect((await apiFetch(post)).status).toBe(200)

  expect(seen).toEqual([
    { url: 'https://nexus.test/api/me/?x=1', authorization: 'Bearer access-1', credentials: 'omit', body: '' },
    { url: 'https://nexus.test/api/x/', authorization: 'Bearer access-1', credentials: 'omit', body: '{"a":1}' },
  ])
  expect(refresh).not.toHaveBeenCalled()
})

test('an expired token is renewed before the request', async () => {
  setNative(true)
  const seen = server(['Bearer access-2'])
  await saveSession({ ...session, tokens: { ...fresh, expiresAt: Date.now() + 1000 } })
  vi.mocked(refresh).mockResolvedValue(renewed)

  expect((await get()).status).toBe(200)
  expect(seen.map((request) => request.authorization)).toEqual(['Bearer access-2'])
  expect(refresh).toHaveBeenCalledWith('https://auth.test/o/', 'app', 'refresh-1')
  expect(getSession()?.tokens).toEqual(renewed)
})

test('a refused token is renewed and the request sent again', async () => {
  setNative(true)
  const seen = server(['Bearer access-2'])
  await saveSession(session)
  vi.mocked(refresh).mockResolvedValue(renewed)

  expect((await get()).status).toBe(200)
  expect(seen.map((request) => request.authorization)).toEqual(['Bearer access-1', 'Bearer access-2'])
})

test('when renewing fails the tokens are dropped, so that the user signs in again', async () => {
  setNative(true)
  server([])
  await saveSession(session)
  vi.mocked(refresh).mockRejectedValue(new Error('invalid_grant'))

  expect((await get()).status).toBe(403)
  expect(getSession()?.tokens).toBeNull()
})

test('without a refresh token a refusal is final', async () => {
  setNative(true)
  server([])
  await saveSession({ ...session, tokens: { ...fresh, refreshToken: null } })
  expect((await get()).status).toBe(403)
  expect(refresh).not.toHaveBeenCalled()
})

test('before signing in, requests go out without a token', async () => {
  setNative(true)
  const seen = server([])
  await saveSession({ ...session, tokens: null })
  expect((await get()).status).toBe(403)
  expect(seen.map((request) => request.authorization)).toEqual([null])
})
