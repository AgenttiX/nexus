import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import type { Calendar, CalendarEvent } from '../../api/client'
import { mockApi, renderWithQuery } from '../../test-utils'
import { CalendarPage } from './CalendarPage'

const work: Calendar = {
  id: 1,
  name: 'Work',
  url: '',
  color: '#3b82f6',
  is_sleep: false,
  sleep_as_android: false,
  synced_at: new Date(2026, 10, 18, 9, 30).toISOString(),
  sync_error: '',
}
const sleep: Calendar = { ...work, id: 2, name: 'Sleep', is_sleep: true, synced_at: null }
const broken: Calendar = { ...work, id: 3, name: 'Broken', sync_error: 'HTTPStatusError' }

function event(id: number, title: string, start: Date, end: Date, extra: Partial<CalendarEvent> = {}): CalendarEvent {
  return {
    id,
    calendar: 1,
    start: start.toISOString(),
    end: end.toISOString(),
    all_day: false,
    title,
    description: '',
    location: '',
    ...extra,
  }
}

const events = [
  event(1, 'Planning', new Date(2026, 10, 16, 10), new Date(2026, 10, 16, 11), { location: 'Room 1' }),
  event(2, '', new Date(2026, 10, 16, 13), new Date(2026, 10, 16, 14)),
  event(3, 'Holiday', new Date(2026, 10, 19), new Date(2026, 10, 20), { all_day: true }),
]

const week = (monday: Date) => {
  const end = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 7)
  const query = new URLSearchParams({ start: monday.toISOString(), end: end.toISOString() })
  return `GET /api/calendars/events/?${query}`
}
const thisWeek = week(new Date(2026, 10, 16))

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 10, 18, 12))
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('shows the events of the current week by day', async () => {
  mockApi({
    'GET /api/calendars/calendars/': { body: [work, sleep, broken] },
    [thisWeek]: { body: events },
  })
  renderWithQuery(<CalendarPage />)

  const monday = (await screen.findByRole('heading', { name: 'Monday 16 November' })).closest('section')!
  expect(screen.getByRole('heading', { name: 'Monday 16 November – Sunday 22 November' })).toBeInTheDocument()
  expect(within(monday).getByText('10:00–11:00')).toBeInTheDocument()
  expect(within(monday).getByText('Planning')).toBeInTheDocument()
  expect(within(monday).getByText('Room 1')).toBeInTheDocument()
  expect(within(monday).getByText('(no title)')).toBeInTheDocument()
  const thursday = screen.getByRole('heading', { name: 'Thursday 19 November' }).closest('section')!
  expect(within(thursday).getByText('All day')).toBeInTheDocument()

  expect(screen.getByText('Updated 09:30')).toBeInTheDocument()
  expect(screen.getByText('Not read yet')).toBeInTheDocument()
  expect(screen.getByText('Could not be read (HTTPStatusError)')).toBeInTheDocument()
  expect(screen.getByText('Sleep calendar')).toBeInTheDocument()
})

test('moves between weeks', async () => {
  const calls = mockApi({
    'GET /api/calendars/calendars/': { body: [work] },
    [thisWeek]: { body: [] },
    [week(new Date(2026, 10, 23))]: { body: [] },
    [week(new Date(2026, 10, 9))]: { body: [] },
  })
  renderWithQuery(<CalendarPage />)

  expect(await screen.findByText('No events this week.')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Next week' }))
  expect(await screen.findByRole('heading', { name: /Monday 23 November/ })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Previous week' }))
  await userEvent.click(screen.getByRole('button', { name: 'Previous week' }))
  expect(await screen.findByRole('heading', { name: /Monday 9 November/ })).toBeInTheDocument()
  expect(await screen.findByText('No events this week.')).toBeInTheDocument()
  expect(calls).toContain(week(new Date(2026, 10, 9)))
})

test('adds a sleep calendar', async () => {
  let posted: unknown
  let calendars: Calendar[] = []
  mockApi({
    'GET /api/calendars/calendars/': () => ({ body: calendars }),
    [thisWeek]: { body: [] },
    'POST /api/calendars/calendars/': () => {
      calendars = [sleep]
      return { status: 201, body: sleep }
    },
  })
  const fetchMock = vi.mocked(globalThis.fetch)
  renderWithQuery(<CalendarPage />)

  await userEvent.type(await screen.findByLabelText('Name'), 'Sleep')
  await userEvent.type(screen.getByLabelText('Secret address in iCal format'), 'https://example.com/sleep.ics')
  expect(screen.queryByLabelText('It is written by Sleep as Android')).toBeNull()
  await userEvent.click(screen.getByLabelText('This is my sleep calendar'))
  await userEvent.click(screen.getByLabelText('It is written by Sleep as Android'))
  fetchMock.mockImplementationOnce(async (input) => {
    posted = await (input as Request).clone().json()
    calendars = [sleep]
    return new Response(JSON.stringify(sleep), { status: 201, headers: { 'Content-Type': 'application/json' } })
  })
  await userEvent.click(screen.getByRole('button', { name: 'Add calendar' }))

  expect(await screen.findByText('Sleep calendar')).toBeInTheDocument()
  expect(posted).toEqual({
    name: 'Sleep',
    url: 'https://example.com/sleep.ics',
    is_sleep: true,
    sleep_as_android: true,
  })
  expect(screen.getByLabelText('Name')).toHaveValue('')
  expect(screen.getByLabelText('This is my sleep calendar')).not.toBeChecked()
})

test('reports when a calendar cannot be added', async () => {
  mockApi({
    'GET /api/calendars/calendars/': { body: [] },
    [thisWeek]: { body: [] },
    'POST /api/calendars/calendars/': { status: 400, body: { url: ['bad'] } },
  })
  renderWithQuery(<CalendarPage />)

  await userEvent.type(await screen.findByLabelText('Name'), 'Work')
  await userEvent.type(screen.getByLabelText('Secret address in iCal format'), 'https://example.com/a.ics')
  await userEvent.click(screen.getByRole('button', { name: 'Add calendar' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('The calendar could not be added.')
  expect(screen.getByLabelText('Name')).toHaveValue('Work')
})

test('updates and removes calendars', async () => {
  let calendars = [work]
  const calls = mockApi({
    'GET /api/calendars/calendars/': () => ({ body: calendars }),
    [thisWeek]: { body: [] },
    'POST /api/calendars/calendars/1/sync/': { status: 202 },
    'DELETE /api/calendars/calendars/1/': () => {
      calendars = []
      return { status: 204 }
    },
  })
  renderWithQuery(<CalendarPage />)

  await userEvent.click(await screen.findByRole('button', { name: 'Update Work' }))
  await userEvent.click(screen.getByRole('button', { name: 'Remove Work' }))

  expect(calls).toContain('POST /api/calendars/calendars/1/sync/')
  await vi.waitFor(() => expect(screen.queryByRole('button', { name: 'Remove Work' })).toBeNull())
})

test('reports when the calendar cannot be loaded', async () => {
  mockApi({})
  renderWithQuery(<CalendarPage />)
  expect(await screen.findByText('The calendar could not be loaded.')).toBeInTheDocument()
})
