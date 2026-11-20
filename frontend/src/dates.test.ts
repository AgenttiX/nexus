import { afterEach, expect, test, vi } from 'vitest'

import {
  formatClock,
  formatDate,
  formatSpan,
  formatTime,
  shiftDate,
  startOfWeek,
  toIsoDate,
  toTimestamp,
  today,
} from './dates'

afterEach(() => {
  vi.useRealTimers()
})

test('formats local dates as ISO strings', () => {
  expect(toIsoDate(new Date(2026, 0, 5))).toBe('2026-01-05')
})

test('today is the local date', () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 10, 20, 23, 30))
  expect(today()).toBe('2026-11-20')
})

test('shifts dates across month and year boundaries', () => {
  expect(shiftDate('2026-11-30', 1)).toBe('2026-12-01')
  expect(shiftDate('2027-01-01', -1)).toBe('2026-12-31')
})

test('formats dates for headings', () => {
  expect(formatDate('2026-11-16')).toBe('Monday 16 November')
})

test('finds the Monday of a week', () => {
  expect(startOfWeek('2026-11-16')).toBe('2026-11-16')
  expect(startOfWeek('2026-11-22')).toBe('2026-11-16')
  expect(startOfWeek('2026-12-02')).toBe('2026-11-30')
})

test('converts dates and timestamps in local time', () => {
  expect(new Date(toTimestamp('2026-11-16')).getTime()).toBe(new Date(2026, 10, 16).getTime())
  expect(formatTime(new Date(2026, 10, 16, 7, 5).toISOString())).toBe('07:05')
})

test('formats clock times and spans', () => {
  expect(formatClock(23.5)).toBe('23:30')
  expect(formatClock(-1)).toBe('23:00')
  expect(formatClock(24)).toBe('00:00')
  expect(formatSpan(7.5)).toBe('7:30')
  expect(formatSpan(-0.25)).toBe('0:15')
})
