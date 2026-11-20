import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Data } from 'plotly.js'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import type { SleepRecord, SleepStats } from '../../api/client'
import { mockApi, renderWithQuery } from '../../test-utils'
import { SleepPage } from './SleepPage'

// The real chart needs a browser canvas; show what it was given instead.
vi.mock('../../components/Plot', () => ({
  default: ({ data, label }: { data: Data[]; label: string }) => (
    <figure aria-label={label}>{JSON.stringify(data)}</figure>
  ),
}))

const stats = (mean: number): SleepStats => ({
  count: 2,
  minimum: mean - 1,
  maximum: mean + 1,
  mean,
  median: mean + 0.25,
  std: 0.5,
})

function night(id: number, start: Date, end: Date): SleepRecord {
  return {
    id,
    start: start.toISOString(),
    end: end.toISOString(),
    duration_hours: (end.getTime() - start.getTime()) / 3_600_000,
    rating: null,
    latitude: null,
    longitude: null,
    deep_sleep: null,
    cycles: null,
    noise: null,
    snoring: null,
    comment: '',
    tags: [],
  }
}

const records = [
  night(1, new Date(2026, 10, 14, 23, 30), new Date(2026, 10, 15, 7, 30)),
  night(2, new Date(2026, 10, 15, 14, 0), new Date(2026, 10, 15, 14, 30)),
  night(3, new Date(2026, 10, 16, 1, 0), new Date(2026, 10, 16, 9, 0)),
]
const summary = {
  first: '2026-10-18',
  last: '2026-11-16',
  nights: 2,
  bedtime: stats(0.25),
  wake_time: stats(8.25),
  duration: stats(8),
  jet_lag: stats(-1.5),
}
const month = '?start=2026-10-18&end=2026-11-16'

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 10, 16, 12))
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('shows statistics and charts for the last 30 days', async () => {
  mockApi({
    [`GET /api/sleep/summary/${month}`]: { body: summary },
    [`GET /api/sleep/records/${month}`]: { body: records },
  })
  renderWithQuery(<SleepPage />)

  const bedtime = (await screen.findByRole('heading', { name: 'Average bedtime' })).closest('section')!
  expect(within(bedtime).getByText('00:15')).toBeInTheDocument()
  expect(within(bedtime).getByText('23:15 to 01:15')).toBeInTheDocument()
  expect(within(bedtime).getByText('0:30')).toBeInTheDocument()
  const duration = screen.getByRole('heading', { name: 'Average time asleep' }).closest('section')!
  expect(within(duration).getByText('8:00')).toBeInTheDocument()
  const jetLag = screen.getByRole('heading', { name: 'Weekend jet lag' }).closest('section')!
  expect(within(jetLag).getByText('−1:30')).toBeInTheDocument()
  expect(within(jetLag).getByText('−2:30 to −0:30')).toBeInTheDocument()
  expect(screen.getByText('2 nights')).toBeInTheDocument()

  const bars = await screen.findByRole('figure', { name: 'Bar chart of hours asleep per night' })
  const bar = JSON.parse(bars.textContent)[0]
  expect(bar.x).toEqual(['2026-11-15', '2026-11-16'])
  expect(bar.y).toEqual([8, 8])

  const scatter = screen.getByRole('figure', { name: 'Scatter chart of bedtime and wake-up time per night' })
  const [asleep, awake] = JSON.parse(scatter.textContent)
  expect(asleep.y).toEqual([-0.5, 1])
  expect(asleep.text).toEqual(['23:30', '01:00'])
  expect(awake.y).toEqual([7.5, 9])
})

test('shows a positive jet lag with a plus sign and missing statistics as such', async () => {
  mockApi({
    [`GET /api/sleep/summary/${month}`]: { body: { ...summary, jet_lag: null, bedtime: null, duration: stats(2) } },
    [`GET /api/sleep/records/${month}`]: { body: records },
  })
  const { unmount } = renderWithQuery(<SleepPage />)
  const jetLag = (await screen.findByRole('heading', { name: 'Weekend jet lag' })).closest('section')!
  expect(within(jetLag).getByText('Not enough data.')).toBeInTheDocument()
  unmount()

  mockApi({
    [`GET /api/sleep/summary/${month}`]: { body: { ...summary, jet_lag: stats(1.5) } },
    [`GET /api/sleep/records/${month}`]: { body: records },
  })
  renderWithQuery(<SleepPage />)
  expect(await screen.findByText('+1:30')).toBeInTheDocument()
})

test('switches the period', async () => {
  const quarter = '?start=2026-08-19&end=2026-11-16'
  const calls = mockApi({
    [`GET /api/sleep/summary/${month}`]: { body: summary },
    [`GET /api/sleep/records/${month}`]: { body: records },
    [`GET /api/sleep/summary/${quarter}`]: { body: { ...summary, nights: 77 } },
    [`GET /api/sleep/records/${quarter}`]: { body: records },
  })
  renderWithQuery(<SleepPage />)

  expect(screen.getByRole('button', { name: '30 days' })).toHaveAttribute('aria-pressed', 'true')
  await userEvent.click(screen.getByRole('button', { name: '90 days' }))
  expect(await screen.findByText('77 nights')).toBeInTheDocument()
  expect(calls).toContain(`GET /api/sleep/records/${quarter}`)
})

test('explains how to get data when there are no nights', async () => {
  mockApi({
    [`GET /api/sleep/summary/${month}`]: { body: { ...summary, nights: 0 } },
    [`GET /api/sleep/records/${month}`]: { body: [] },
  })
  renderWithQuery(<SleepPage />)
  expect(await screen.findByText(/No nights in this period/)).toBeInTheDocument()
})

test('reports when sleep data cannot be loaded', async () => {
  mockApi({})
  renderWithQuery(<SleepPage />)
  expect(await screen.findByText('Sleep data could not be loaded.')).toBeInTheDocument()
})
