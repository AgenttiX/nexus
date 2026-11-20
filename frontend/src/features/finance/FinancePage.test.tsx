import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Data } from 'plotly.js'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import type { BankAccount, Category, FinanceSummary, Transaction } from '../../api/client'
import { mockApi, renderWithQuery } from '../../test-utils'
import { FinancePage } from './FinancePage'

vi.mock('../../components/Plot', () => ({
  default: ({ data, label }: { data: Data[]; label: string }) => (
    <figure aria-label={label}>{JSON.stringify(data)}</figure>
  ),
}))

const account: BankAccount = { id: 1, name: 'Everyday', iban: 'FI2112345600000785', bank: 'generic', currency: 'EUR' }
const housing: Category = { id: 5, name: 'Housing' }
const rent: Transaction = {
  id: 10,
  account: 1,
  date: '2026-10-15',
  amount: '-800.00',
  counterparty: 'Landlord',
  message: 'Rent October',
  reference: '',
  category: 5,
}
const fee: Transaction = { ...rent, id: 11, amount: '-2.00', counterparty: '', message: '', category: null }
const summary: FinanceSummary = {
  first: '2026-08-19',
  last: '2026-11-16',
  income: '2500.00',
  expenses: '904.30',
  net: '1595.70',
  by_category: [{ category: 'Housing', total: '800.00' }],
  by_month: [
    { month: '2026-10-01', income: '2500.00', expenses: '891.80' },
    { month: '2026-11-01', income: '0.00', expenses: '12.50' },
  ],
}
const empty: FinanceSummary = { ...summary, income: '0.00', expenses: '0.00', net: '0.00', by_category: [], by_month: [] }
const quarter = '?start=2026-08-19&end=2026-11-16'
const month = '?start=2026-10-18&end=2026-11-16'

function routes(overrides: Parameters<typeof mockApi>[0] = {}) {
  return mockApi({
    [`GET /api/finance/summary/${quarter}`]: { body: summary },
    [`GET /api/finance/transactions/${quarter}`]: { body: [rent, fee] },
    'GET /api/finance/accounts/': { body: [account] },
    'GET /api/finance/categories/': { body: [housing] },
    ...overrides,
  })
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 10, 16, 12))
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('shows totals, the chart, categories and transactions', async () => {
  routes()
  renderWithQuery(<FinancePage />)

  const income = (await screen.findByRole('heading', { name: 'Income' })).closest('section')!
  expect(within(income).getByText('€2,500.00')).toBeInTheDocument()
  expect(within(screen.getByRole('heading', { name: 'Net' }).closest('section')!).getByText('€1,595.70')).toBeInTheDocument()

  const chart = await screen.findByRole('figure', { name: 'Bar chart of income and expenses by month' })
  const [incomeBars, expenseBars] = JSON.parse(chart.textContent)
  expect(incomeBars.x).toEqual(['2026-10-01', '2026-11-01'])
  expect(incomeBars.y).toEqual([2500, 0])
  expect(expenseBars.y).toEqual([891.8, 12.5])

  expect(screen.getByRole('rowheader', { name: 'Housing' }).closest('tr')).toHaveTextContent('€800.00')
  const row = screen.getByText('Landlord').closest('tr')!
  expect(row).toHaveTextContent('Rent October')
  expect(row).toHaveTextContent('-€800.00')
  expect(screen.getByLabelText('Category of Landlord on 2026-10-15')).toHaveValue('5')
  expect(screen.getByLabelText('Category of transaction on 2026-10-15')).toHaveValue('')
  expect(screen.getByText('FI2112345600000785')).toBeInTheDocument()
})

test('shows an empty period without chart or categories, and switches the period', async () => {
  const calls = routes({
    [`GET /api/finance/summary/${month}`]: { body: empty },
    [`GET /api/finance/transactions/${month}`]: { body: [] },
  })
  renderWithQuery(<FinancePage />)

  await userEvent.click(screen.getByRole('button', { name: '30 days' }))
  expect(await screen.findByText('No transactions in this period.')).toBeInTheDocument()
  expect(screen.queryByRole('figure')).toBeNull()
  expect(screen.queryByRole('heading', { name: 'Expenses by category' })).toBeNull()
  expect(calls).toContain(`GET /api/finance/summary/${month}`)
})

test('changes and clears the category of a transaction', async () => {
  const bodies: unknown[] = []
  routes({
    'PATCH /api/finance/transactions/10/': (request) => {
      void request.clone().json().then((body) => bodies.push(body))
      return { body: rent }
    },
    'PATCH /api/finance/transactions/11/': (request) => {
      void request.clone().json().then((body) => bodies.push(body))
      return { body: fee }
    },
  })
  renderWithQuery(<FinancePage />)

  await userEvent.selectOptions(await screen.findByLabelText('Category of Landlord on 2026-10-15'), 'Uncategorised')
  await userEvent.selectOptions(screen.getByLabelText('Category of transaction on 2026-10-15'), 'Housing')
  await vi.waitFor(() => expect(bodies).toEqual([{ category: null }, { category: 5 }]))
})

test('imports a transaction file', async () => {
  let contentType: string | null = null
  routes({
    'POST /api/finance/accounts/1/import/': (request) => {
      contentType = request.headers.get('Content-Type')
      return { status: 201, body: { id: 1, account: 1, filename: 'october.csv', created_at: '', imported: 4, duplicates: 1 } }
    },
  })
  renderWithQuery(<FinancePage />)

  const input = await screen.findByLabelText('Import transactions to Everyday')
  fireEvent.change(input, { target: { files: [] } })
  await userEvent.upload(input, new File(['date,amount\n'], 'october.csv', { type: 'text/csv' }))

  expect(await screen.findByRole('status')).toHaveTextContent(
    'Imported 4 transactions from october.csv; 1 were already there.',
  )
  // The test environment cannot parse multipart bodies; the upload itself is checked in a real browser.
  expect(contentType).toMatch(/^multipart\/form-data/)
})

test('reports a file that cannot be imported', async () => {
  routes({ 'POST /api/finance/accounts/1/import/': { status: 400, body: { file: 'bad' } } })
  renderWithQuery(<FinancePage />)
  await userEvent.upload(
    await screen.findByLabelText('Import transactions to Everyday'),
    new File(['x'], 'x.csv', { type: 'text/csv' }),
  )
  expect(await screen.findByRole('alert')).toHaveTextContent('The file could not be imported.')
})

test('adds an account and a category', async () => {
  const bodies: Record<string, unknown> = {}
  const record = (key: string) => (request: Request) => {
    void request.clone().json().then((body) => (bodies[key] = body))
    return { status: 201, body: {} }
  }
  routes({
    'POST /api/finance/accounts/': record('account'),
    'POST /api/finance/categories/': record('category'),
  })
  renderWithQuery(<FinancePage />)

  await userEvent.type(await screen.findByLabelText('Account name'), 'Savings')
  await userEvent.type(screen.getByLabelText('IBAN'), 'DE89 3704 0044 0532 0130 00')
  await userEvent.click(screen.getByRole('button', { name: 'Add account' }))
  await userEvent.type(screen.getByLabelText('New category'), 'Food')
  await userEvent.click(screen.getByRole('button', { name: 'Add category' }))

  await vi.waitFor(() =>
    expect(bodies).toEqual({
      account: { name: 'Savings', iban: 'DE89 3704 0044 0532 0130 00' },
      category: { name: 'Food' },
    }),
  )
  await vi.waitFor(() => expect(screen.getByLabelText('Account name')).toHaveValue(''))
  await vi.waitFor(() => expect(screen.getByLabelText('New category')).toHaveValue(''))
})

test('reports accounts and categories that cannot be added', async () => {
  routes({
    'POST /api/finance/accounts/': { status: 400 },
    'POST /api/finance/categories/': { status: 400 },
  })
  renderWithQuery(<FinancePage />)

  await userEvent.type(await screen.findByLabelText('Account name'), 'Bad')
  await userEvent.type(screen.getByLabelText('IBAN'), 'FI00')
  await userEvent.click(screen.getByRole('button', { name: 'Add account' }))
  expect(await screen.findByText('The account could not be added. Check the IBAN.')).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText('New category'), 'Housing')
  await userEvent.click(screen.getByRole('button', { name: 'Add category' }))
  expect(await screen.findByText('The category could not be added.')).toBeInTheDocument()
})

test('reports when finances cannot be loaded', async () => {
  mockApi({})
  renderWithQuery(<FinancePage />)
  expect(await screen.findByText('Finances could not be loaded.')).toBeInTheDocument()
})
