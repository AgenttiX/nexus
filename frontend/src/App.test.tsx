import { createMemoryHistory } from '@tanstack/react-router'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from './App'
import { createAppRouter } from './router'
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
