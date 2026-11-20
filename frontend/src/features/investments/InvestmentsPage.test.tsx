import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Data } from 'plotly.js'
import { afterEach, expect, test, vi } from 'vitest'

import type { Portfolio } from '../../api/client'
import { mockApi, renderWithQuery } from '../../test-utils'
import { InvestmentsPage } from './InvestmentsPage'

vi.mock('../../components/Plot', () => ({
  default: ({ data, label }: { data: Data[]; label: string }) => (
    <figure aria-label={label}>{JSON.stringify(data)}</figure>
  ),
}))

type Position = Portfolio['positions'][number]

const nokia: Position = {
  holding: {
    id: 1,
    asset: { id: 1, provider: 'yahoo', symbol: 'NOKIA.HE', name: 'Nokia Corporation', currency: 'EUR' },
    quantity: '100.00000000',
    cost: '500.00',
    note: 'Broker',
  },
  price: '7.50000000',
  price_date: '2026-11-20',
  value_eur: '750.00',
  gain_eur: '250.00',
}
const unpriced: Position = {
  holding: { ...nokia.holding, id: 2, asset: { ...nokia.holding.asset, id: 2, symbol: 'NEW', name: '' }, note: '' },
  price: null,
  price_date: null,
  value_eur: null,
  gain_eur: null,
}
const portfolio: Portfolio = {
  total_eur: '750.00',
  positions: [nokia, unpriced],
  history: [
    { date: '2026-11-19', value_eur: '700.00' },
    { date: '2026-11-20', value_eur: '750.00' },
  ],
}
const none: Portfolio = { total_eur: '0.00', positions: [], history: [] }

afterEach(() => {
  vi.unstubAllGlobals()
})

test('shows the total, the positions and the value chart', async () => {
  mockApi({ 'GET /api/investments/portfolio/': { body: portfolio } })
  renderWithQuery(<InvestmentsPage />)

  expect((await screen.findByRole('heading', { name: 'Total value' })).closest('section')).toHaveTextContent('€750.00')
  const row = screen.getByRole('rowheader', { name: /NOKIA\.HE/ }).closest('tr')!
  expect(row).toHaveTextContent('Nokia Corporation')
  expect(row).toHaveTextContent('Broker')
  expect(row).toHaveTextContent('100')
  expect(row).toHaveTextContent('7.5 EUR')
  expect(row).toHaveTextContent('€250.00')
  expect(screen.getByRole('rowheader', { name: /NEW/ }).closest('tr')).toHaveTextContent('No price yet')

  const chart = await screen.findByRole('figure', { name: /value of the current holdings/ })
  const [line] = JSON.parse(chart.textContent)
  expect(line.x).toEqual(['2026-11-19', '2026-11-20'])
  expect(line.y).toEqual([700, 750])
})

test('leaves the chart out when there is too little history', async () => {
  mockApi({ 'GET /api/investments/portfolio/': { body: { ...portfolio, history: portfolio.history.slice(0, 1) } } })
  renderWithQuery(<InvestmentsPage />)
  await screen.findByRole('heading', { name: 'Total value' })
  expect(screen.queryByRole('figure')).toBeNull()
})

test('adds a holding and refreshes the portfolio', async () => {
  let posted: unknown
  let current = none
  mockApi({
    'GET /api/investments/portfolio/': () => ({ body: current }),
  })
  renderWithQuery(<InvestmentsPage />)

  expect(await screen.findByText('No holdings yet. Add your first one below.')).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Price source'), 'coingecko')
  await userEvent.type(screen.getByLabelText('CoinGecko id, for example bitcoin'), 'bitcoin')
  await userEvent.type(screen.getByLabelText('Quantity'), '0.5')
  await userEvent.type(screen.getByLabelText('Note (optional)'), 'Wallet')
  // Hold the answer back, to see the message shown while prices are being fetched.
  let answer = () => {}
  vi.mocked(globalThis.fetch).mockImplementationOnce(async (input) => {
    posted = await (input as Request).clone().json()
    await new Promise<void>((resolve) => (answer = resolve))
    current = portfolio
    return new Response(JSON.stringify(nokia.holding), { status: 201, headers: { 'Content-Type': 'application/json' } })
  })
  await userEvent.click(screen.getByRole('button', { name: 'Add holding' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Fetching prices…')
  answer()

  expect(await screen.findByRole('heading', { name: 'Total value' })).toBeInTheDocument()
  expect(posted).toEqual({ provider: 'coingecko', symbol: 'bitcoin', quantity: '0.5', cost: null, note: 'Wallet' })
  expect(screen.getByLabelText('Quantity')).toHaveValue('')
})

test('sends the cost when one is given and reports failures', async () => {
  let posted: { cost?: string } = {}
  mockApi({
    'GET /api/investments/portfolio/': { body: none },
    'POST /api/investments/holdings/': (request) => {
      void request.clone().json().then((body) => (posted = body))
      return { status: 400, body: { symbol: ['unknown'] } }
    },
  })
  renderWithQuery(<InvestmentsPage />)

  await userEvent.type(await screen.findByLabelText('Ticker, for example NOKIA.HE'), 'NOSUCH')
  await userEvent.type(screen.getByLabelText('Quantity'), '1')
  await userEvent.type(screen.getByLabelText('Total cost in euros (optional)'), '12.50')
  await userEvent.click(screen.getByRole('button', { name: 'Add holding' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('The holding could not be added.')
  expect(posted.cost).toBe('12.50')
  expect(screen.getByLabelText('Ticker, for example NOKIA.HE')).toHaveValue('NOSUCH')
})

test('removes a holding', async () => {
  let current = portfolio
  const calls = mockApi({
    'GET /api/investments/portfolio/': () => ({ body: current }),
    'DELETE /api/investments/holdings/1/': () => {
      current = none
      return { status: 204 }
    },
  })
  renderWithQuery(<InvestmentsPage />)

  await userEvent.click(await screen.findByRole('button', { name: 'Remove NOKIA.HE' }))
  expect(await screen.findByText('No holdings yet. Add your first one below.')).toBeInTheDocument()
  expect(calls).toContain('DELETE /api/investments/holdings/1/')
})

test('reports when investments cannot be loaded', async () => {
  mockApi({})
  renderWithQuery(<InvestmentsPage />)
  expect(await screen.findByText('Investments could not be loaded.')).toBeInTheDocument()
})
