import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { vi } from 'vitest'

type Reply = { status?: number; body?: unknown }
type Handler = Reply | ((request: Request) => Reply)

/** Replaces `fetch` with canned replies keyed by "METHOD /path?query". Unknown requests answer 500. */
export function mockApi(routes: Record<string, Handler>) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: Request) => {
      const url = new URL(input.url)
      const key = `${input.method} ${url.pathname}${url.search}`
      calls.push(key)
      const handler = routes[key]
      const reply = typeof handler === 'function' ? handler(input) : (handler ?? { status: 500 })
      const status = reply.status ?? 200
      const body = status === 204 || status === 202 ? null : JSON.stringify(reply.body ?? {})
      return new Response(body, { status, headers: { 'Content-Type': 'application/json' } })
    }),
  )
  return calls
}

export function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}
