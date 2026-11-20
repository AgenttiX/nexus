import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Data } from 'plotly.js'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import type { TimeSummary } from '../../api/client'
import { mockApi, renderWithQuery } from '../../test-utils'
import { TimePage } from './TimePage'

vi.mock('../../components/Plot', () => ({
  default: ({ data, label }: { data: Data[]; label: string }) => (
    <figure aria-label={label}>{JSON.stringify(data)}</figure>
  ),
}))

const summary: TimeSummary = {
  first: '2026-11-10',
  last: '2026-11-16',
  total: 7,
  by_day: [
    { date: '2026-11-15', hours: 2.5 },
    { date: '2026-11-16', hours: 4.5 },
  ],
  by_app: [
    { name: 'Editor', hours: 5 },
    { name: 'Browser', hours: 2 },
  ],
  by_device: [{ name: 'laptop', hours: 7 }],
}
const imported = new Date(2026, 10, 16, 12, 5).toISOString()
const buckets = [
  { id: 1, name: 'aw-watcher-window_laptop', type: 'currentwindow', client: '', hostname: 'laptop', imported_until: imported },
  { id: 2, name: 'aw-watcher-afk_laptop', type: 'afkstatus', client: '', hostname: 'laptop', imported_until: null },
]
const week = '?start=2026-11-10&end=2026-11-16'
const month = '?start=2026-10-18&end=2026-11-16'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 10, 16, 12))
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('shows active time, the chart, apps, devices and what was imported', async () => {
  mockApi({
    [`GET /api/timetracking/summary/${week}`]: { body: summary },
    'GET /api/timetracking/buckets/': { body: buckets },
  })
  renderWithQuery(<TimePage />)

  expect((await screen.findByRole('heading', { name: 'Active time' })).closest('section')).toHaveTextContent('7:00')
  expect(screen.getByRole('heading', { name: 'Average per day' }).closest('section')).toHaveTextContent('3:30')
  expect(screen.getByRole('rowheader', { name: 'Editor' }).closest('tr')).toHaveTextContent('5:00')
  expect(screen.getByRole('rowheader', { name: 'laptop' }).closest('tr')).toHaveTextContent('7:00')

  const chart = await screen.findByRole('figure', { name: 'Bar chart of active hours per day' })
  const [bars] = JSON.parse(chart.textContent)
  expect(bars.x).toEqual(['2026-11-15', '2026-11-16'])
  expect(bars.y).toEqual([2.5, 4.5])

  expect(screen.getByText(`until ${imported.slice(0, 10)} 12:05`)).toBeInTheDocument()
  expect(screen.getByText('no events')).toBeInTheDocument()
})

test('switches the period and explains a period without activity', async () => {
  const calls = mockApi({
    [`GET /api/timetracking/summary/${week}`]: { body: summary },
    [`GET /api/timetracking/summary/${month}`]: { body: { ...summary, total: 0 } },
    'GET /api/timetracking/buckets/': { body: buckets },
  })
  renderWithQuery(<TimePage />)

  await userEvent.click(screen.getByRole('button', { name: '30 days' }))
  expect(await screen.findByText('No activity was recorded in this period.')).toBeInTheDocument()
  expect(calls).toContain(`GET /api/timetracking/summary/${month}`)
})

test('explains how to get data when nothing has been imported', async () => {
  mockApi({
    [`GET /api/timetracking/summary/${week}`]: { body: { ...summary, total: 0 } },
    'GET /api/timetracking/buckets/': { body: [] },
  })
  renderWithQuery(<TimePage />)
  expect(await screen.findByText(/No ActivityWatch data has been imported yet/)).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Imported data' })).toBeNull()
})

test('reports when time tracking cannot be loaded', async () => {
  mockApi({})
  renderWithQuery(<TimePage />)
  expect(await screen.findByText('Time tracking could not be loaded.')).toBeInTheDocument()
})
