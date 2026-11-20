/** Helpers for calendar dates as ISO strings (YYYY-MM-DD) in the browser's time zone. */

export function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function today(): string {
  return toIsoDate(new Date())
}

export function shiftDate(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return toIsoDate(new Date(year, month - 1, day + days))
}

export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}

/** The Monday of the week that contains the date. */
export function startOfWeek(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  const weekday = (new Date(year, month - 1, day).getDay() + 6) % 7
  return shiftDate(isoDate, -weekday)
}

/** Local midnight at the start of the date, as a full timestamp for the API. */
export function toTimestamp(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Date(year, month - 1, day).toISOString()
}

/** The local time of day of a timestamp, as HH:MM. */
export function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

/** Hours after midnight as a clock time, e.g. 23.5 → 23:30. */
export function formatClock(hours: number): string {
  const minutes = ((Math.round(hours * 60) % 1440) + 1440) % 1440
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

/** A length of time in hours as h:mm, e.g. 7.5 → 7:30. */
export function formatSpan(hours: number): string {
  const minutes = Math.round(Math.abs(hours) * 60)
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`
}
