/**
 * Signing in from the Android app: OpenID Connect authorization code flow with PKCE,
 * through the system browser, so that passkeys work as they do in Chrome and the app
 * never sees a credential (RFC 8252).
 *
 * This file is the glue between the oauth4webapi library and the device, and can only
 * run on a device against a real identity provider, so it is not unit-tested.
 */
import { App } from '@capacitor/app'
import { Browser } from '@capacitor/browser'
import { CapacitorHttp } from '@capacitor/core'
import * as oauth from 'oauth4webapi'

import type { Tokens } from './session'

/** Where Authentik sends the browser back to. Registered in AndroidManifest.xml and in the blueprint. */
export const REDIRECT_URI = 'fi.agx.nexus://oauth/callback'
const SCOPE = 'openid profile email offline_access'

/**
 * Requests to the identity provider go through the device's own HTTP stack. The page
 * inside the app has the origin https://localhost, which the provider's endpoints do
 * not accept as a cross-origin caller.
 */
async function nativeFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
  const headers: Record<string, string> = {}
  new Headers(init?.headers).forEach((value, name) => (headers[name] = value))
  const answer = await CapacitorHttp.request({
    url: String(input instanceof Request ? input.url : input),
    method: init?.method ?? 'GET',
    headers,
    data: init?.body ? String(init.body) : undefined,
  })
  const body = typeof answer.data === 'string' ? answer.data : JSON.stringify(answer.data)
  return new Response(body, { status: answer.status, headers: answer.headers })
}

const options = { [oauth.customFetch]: nativeFetch }

async function discover(issuer: string): Promise<oauth.AuthorizationServer> {
  const url = new URL(issuer)
  return oauth.processDiscoveryResponse(url, await oauth.discoveryRequest(url, { ...options, algorithm: 'oidc' }))
}

function toTokens(answer: oauth.TokenEndpointResponse, previousRefreshToken: string | null = null): Tokens {
  return {
    accessToken: answer.access_token,
    refreshToken: answer.refresh_token ?? previousRefreshToken,
    expiresAt: Date.now() + (answer.expires_in ?? 300) * 1000,
  }
}

/** Opens the system browser on the provider's login page and waits for it to return to the app. */
function authorize(url: URL): Promise<URL> {
  return new Promise((resolve) => {
    const listening = App.addListener('appUrlOpen', (event) => {
      if (event.url.startsWith(REDIRECT_URI)) {
        void listening.then((listener) => listener.remove())
        void Browser.close().catch(() => undefined)
        resolve(new URL(event.url))
      }
    })
    void Browser.open({ url: url.href })
  })
}

/** Signs the user in and returns their tokens. */
export async function signIn(issuer: string, clientId: string): Promise<Tokens> {
  const server = await discover(issuer)
  const client: oauth.Client = { client_id: clientId }
  const verifier = oauth.generateRandomCodeVerifier()
  const state = oauth.generateRandomState()

  const url = new URL(server.authorization_endpoint!)
  url.search = new URLSearchParams({
    client_id: clientId,
    redirect_uri: REDIRECT_URI,
    response_type: 'code',
    scope: SCOPE,
    code_challenge: await oauth.calculatePKCECodeChallenge(verifier),
    code_challenge_method: 'S256',
    state,
  }).toString()

  const parameters = oauth.validateAuthResponse(server, client, await authorize(url), state)
  const response = await oauth.authorizationCodeGrantRequest(
    server,
    client,
    oauth.None(),
    parameters,
    REDIRECT_URI,
    verifier,
    options,
  )
  return toTokens(await oauth.processAuthorizationCodeResponse(server, client, response))
}

/** Exchanges a refresh token for new tokens. Throws when the refresh token no longer works. */
export async function refresh(issuer: string, clientId: string, refreshToken: string): Promise<Tokens> {
  const server = await discover(issuer)
  const client: oauth.Client = { client_id: clientId }
  const response = await oauth.refreshTokenGrantRequest(server, client, oauth.None(), refreshToken, options)
  return toTokens(await oauth.processRefreshTokenResponse(server, client, response), refreshToken)
}
