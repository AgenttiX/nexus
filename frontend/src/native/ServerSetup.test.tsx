import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'

import { renderWithQuery } from '../test-utils'
import { ServerSetup } from './ServerSetup'
import { getSession } from './session'

function answer(status: number, body: unknown) {
  const requested: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      requested.push(request.url)
      return new Response(JSON.stringify(body), { status })
    }),
  )
  return requested
}

async function connect(address: string) {
  const onDone = vi.fn()
  renderWithQuery(<ServerSetup onDone={onDone} />)
  const input = screen.getByLabelText('Address of your Nexus server')
  await userEvent.clear(input)
  await userEvent.type(input, address)
  await userEvent.click(screen.getByRole('button', { name: 'Connect' }))
  return onDone
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('remembers the server and what it says about signing in', async () => {
  const requested = answer(200, { oidc_issuer: 'https://auth.test/o/', oidc_client_id: 'nexus-android' })
  const onDone = await connect('https://nexus.test/some/page')

  await vi.waitFor(() => expect(onDone).toHaveBeenCalled())
  expect(requested).toEqual(['https://nexus.test/api/config/'])
  expect(getSession()).toEqual({
    serverUrl: 'https://nexus.test',
    issuer: 'https://auth.test/o/',
    clientId: 'nexus-android',
    tokens: null,
  })
})

test('refuses a server on which the app is not enabled', async () => {
  answer(200, { oidc_issuer: '', oidc_client_id: '' })
  const onDone = await connect('https://nexus.test')
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not connect.')
  expect(onDone).not.toHaveBeenCalled()
  expect(getSession()).toBeNull()
})

test('reports a server that answers with an error', async () => {
  answer(500, {})
  await connect('https://nexus.test')
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not connect.')
})
