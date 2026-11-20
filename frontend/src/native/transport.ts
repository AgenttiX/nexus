/**
 * How API requests leave the interface. In a browser they go to the page's own server with
 * the session cookie. In the Android app they go to the configured server with an access
 * token, which is renewed with the refresh token when it has expired or is refused.
 */
import { refresh } from './oidc'
import { isNative } from './platform'
import { getSession, saveTokens, type Session } from './session'

/** Renew a little before the token expires, so that a request does not fail on the way. */
const EXPIRY_MARGIN = 30_000

async function renew(session: Session): Promise<string | null> {
  const refreshToken = session.tokens?.refreshToken
  if (!refreshToken) {
    return null
  }
  try {
    const tokens = await refresh(session.issuer, session.clientId, refreshToken)
    await saveTokens(tokens)
    return tokens.accessToken
  } catch {
    // The refresh token is spent or revoked: the user has to sign in again.
    await saveTokens(null)
    return null
  }
}

export async function apiFetch(request: Request): Promise<Response> {
  if (!isNative()) {
    return globalThis.fetch(request)
  }
  const session = getSession()
  if (!session) {
    return new Response(null, { status: 401 })
  }

  const original = new URL(request.url)
  const target = new URL(original.pathname + original.search, session.serverUrl)
  const body = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer()
  const send = (accessToken: string | null) => {
    const headers = new Headers(request.headers)
    if (accessToken) {
      headers.set('Authorization', `Bearer ${accessToken}`)
    }
    return globalThis.fetch(new Request(target, { method: request.method, headers, body, credentials: 'omit' }))
  }

  let accessToken = session.tokens?.accessToken ?? null
  if (session.tokens && session.tokens.expiresAt - EXPIRY_MARGIN < Date.now()) {
    accessToken = await renew(session)
  }
  const response = await send(accessToken)
  if ((response.status === 401 || response.status === 403) && accessToken) {
    const renewed = await renew(session)
    if (renewed) {
      return send(renewed)
    }
  }
  return response
}
