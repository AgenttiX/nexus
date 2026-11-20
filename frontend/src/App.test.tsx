import { createMemoryHistory } from '@tanstack/react-router'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from './App'
import { signIn } from './native/oidc'
import { getSession, saveSession, type Session } from './native/session'
import { createAppRouter } from './router'
import { setNative } from './test-native'
import { mockApi, renderWithQuery } from './test-utils'

const alice = { id: 1, username: 'alice', first_name: '', last_name: '', email: '' }

afterEach(() => {
  vi.unstubAllGlobals()
})

test('shows the application to a signed-in user', async () => {
  mockApi({ 'GET /api/me/': { body: alice } })
  renderWithQuery(<App />)
  expect(await screen.findByText('Choose a section above.')).toBeInTheDocument()
})

test('navigates to the food page', async () => {
  mockApi({
    'GET /api/me/': { body: alice },
    'GET /api/food/restaurants/': { body: [] },
  })
  const router = createAppRouter(createMemoryHistory({ initialEntries: ['/'] }))
  renderWithQuery(<App router={router} />)
  await userEvent.click(await screen.findByRole('link', { name: 'Food' }))
  expect(await screen.findByText(/No menus have been fetched yet/)).toBeInTheDocument()
})

test('offers passkey sign-in when there is no session', async () => {
  mockApi({ 'GET /api/me/': { status: 403 } })
  renderWithQuery(<App />)
  const link = await screen.findByRole('link', { name: 'Sign in with a passkey' })
  expect(link).toHaveAttribute('href', '/accounts/oidc/authentik/login/')
})

test('reports when the server cannot be reached', async () => {
  mockApi({})
  renderWithQuery(<App />)
  expect(await screen.findByText(/could not be reached/)).toBeInTheDocument()
})

test('offers to sign out in a browser', async () => {
  mockApi({ 'GET /api/me/': { body: alice } })
  renderWithQuery(<App />)
  expect(await screen.findByRole('link', { name: 'Sign out' })).toHaveAttribute('href', '/accounts/logout/')
})

// The Android app

const session: Session = { serverUrl: 'https://nexus.test', issuer: 'https://auth.test/o/', clientId: 'app', tokens: null }
const tokens = { accessToken: 'access-1', refreshToken: 'refresh-1', expiresAt: Date.now() + 600_000 }

/** A server that knows alice by her access token. */
function nexusServer() {
  return mockApi({
    'GET /api/config/': { body: { oidc_issuer: 'https://auth.test/o/', oidc_client_id: 'app' } },
    'GET /api/me/': (request) =>
      request.headers.get('Authorization') === 'Bearer access-1' ? { body: alice } : { status: 403 },
  })
}

test('the app asks for its server first, then offers to sign in', async () => {
  setNative(true)
  nexusServer()
  renderWithQuery(<App />)

  const input = await screen.findByLabelText('Address of your Nexus server')
  await userEvent.clear(input)
  await userEvent.type(input, 'https://nexus.test')
  await userEvent.click(screen.getByRole('button', { name: 'Connect' }))

  expect(await screen.findByRole('button', { name: 'Sign in with a passkey' })).toBeInTheDocument()
  expect(screen.getByText(/Server: https:\/\/nexus\.test/)).toBeInTheDocument()
})

test('the app signs in through the system browser and can sign out', async () => {
  setNative(true)
  nexusServer()
  await saveSession(session)
  vi.mocked(signIn).mockResolvedValue(tokens)
  renderWithQuery(<App />)

  await userEvent.click(await screen.findByRole('button', { name: 'Sign in with a passkey' }))
  expect(await screen.findByText('Choose a section above.')).toBeInTheDocument()
  expect(signIn).toHaveBeenCalledWith('https://auth.test/o/', 'app')
  expect(getSession()?.tokens).toEqual(tokens)

  await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))
  expect(await screen.findByRole('button', { name: 'Sign in with a passkey' })).toBeInTheDocument()
  expect(getSession()?.tokens).toBeNull()
})

test('the app reports a failed sign-in and can switch servers', async () => {
  setNative(true)
  nexusServer()
  await saveSession(session)
  vi.mocked(signIn).mockRejectedValue(new Error('cancelled'))
  renderWithQuery(<App />)

  await userEvent.click(await screen.findByRole('button', { name: 'Sign in with a passkey' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Signing in did not succeed.')

  await userEvent.click(screen.getByRole('button', { name: 'Use another server' }))
  expect(await screen.findByLabelText('Address of your Nexus server')).toBeInTheDocument()
  expect(getSession()).toBeNull()
})
