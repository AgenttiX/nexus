import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { App } from './App'

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

function mockFetch(status: number, body: unknown = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('shows the signed-in user', async () => {
  mockFetch(200, { id: 1, username: 'alice', first_name: '', last_name: '', email: '' })
  renderApp()
  expect(await screen.findByText('Signed in as alice.')).toBeInTheDocument()
})

test('offers passkey sign-in when there is no session', async () => {
  mockFetch(403)
  renderApp()
  const link = await screen.findByRole('link', { name: 'Sign in with a passkey' })
  expect(link).toHaveAttribute('href', '/accounts/oidc/authentik/login/')
})

test('reports when the server cannot be reached', async () => {
  mockFetch(500)
  renderApp()
  expect(await screen.findByText(/could not be reached/)).toBeInTheDocument()
})
