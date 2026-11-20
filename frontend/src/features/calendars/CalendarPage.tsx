import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { api, unwrap, type Calendar, type CalendarEvent } from '../../api/client'
import { formatDate, formatTime, shiftDate, startOfWeek, toIsoDate, toTimestamp, today } from '../../dates'

function eventDay(event: CalendarEvent): string {
  return toIsoDate(new Date(event.start))
}

function Agenda({ events, calendars }: { events: CalendarEvent[]; calendars: Calendar[] }) {
  const colors = new Map(calendars.map((calendar) => [calendar.id, calendar.color]))
  const days = [...new Set(events.map(eventDay))]
  if (days.length === 0) {
    return <p className="mt-4 text-slate-500">No events this week.</p>
  }
  return (
    <div className="mt-4 space-y-4">
      {days.map((day) => (
        <section key={day}>
          <h2 className="font-semibold">{formatDate(day)}</h2>
          <ul className="mt-1 divide-y divide-slate-100">
            {events
              .filter((event) => eventDay(event) === day)
              .map((event) => (
                <li key={event.id} className="flex items-baseline gap-3 py-1">
                  <span
                    aria-hidden="true"
                    className="inline-block size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: colors.get(event.calendar) }}
                  />
                  <span className="w-28 shrink-0 text-sm text-slate-600 tabular-nums">
                    {event.all_day ? 'All day' : `${formatTime(event.start)}–${formatTime(event.end)}`}
                  </span>
                  <span>
                    {event.title || '(no title)'}
                    {event.location && <span className="ml-2 text-sm text-slate-500">{event.location}</span>}
                  </span>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function CalendarSettings({ calendars }: { calendars: Calendar[] }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [isSleep, setIsSleep] = useState(false)
  const [sleepAsAndroid, setSleepAsAndroid] = useState(false)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['calendars'] })

  const add = useMutation({
    mutationFn: async () => {
      const body = { name, url, is_sleep: isSleep, sleep_as_android: isSleep && sleepAsAndroid }
      unwrap(await api.POST('/api/calendars/calendars/', { body: body as Calendar }))
    },
    onSuccess: () => {
      setName('')
      setUrl('')
      setIsSleep(false)
      setSleepAsAndroid(false)
    },
    onSettled: refresh,
  })
  const remove = useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.DELETE('/api/calendars/calendars/{id}/', { params: { path: { id } } })),
    onSettled: refresh,
  })
  const sync = useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.POST('/api/calendars/calendars/{id}/sync/', { params: { path: { id } } })),
    onSettled: refresh,
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    add.mutate()
  }

  return (
    <section className="mt-8 border-t border-slate-200 pt-4">
      <h2 className="text-lg font-semibold">Calendars</h2>
      <ul className="mt-2 divide-y divide-slate-100">
        {calendars.map((calendar) => (
          <li key={calendar.id} className="flex flex-wrap items-baseline gap-3 py-2">
            <span
              aria-hidden="true"
              className="inline-block size-2.5 rounded-full"
              style={{ backgroundColor: calendar.color }}
            />
            <span className="font-medium">{calendar.name}</span>
            {calendar.is_sleep && <span className="rounded bg-slate-100 px-2 text-xs">Sleep calendar</span>}
            <span className="mr-auto text-sm text-slate-500">
              {calendar.sync_error
                ? `Could not be read (${calendar.sync_error})`
                : calendar.synced_at
                  ? `Updated ${formatTime(calendar.synced_at)}`
                  : 'Not read yet'}
            </span>
            <button type="button" className="text-sm underline" onClick={() => sync.mutate(calendar.id)}>
              Update {calendar.name}
            </button>
            <button type="button" className="text-sm underline" onClick={() => remove.mutate(calendar.id)}>
              Remove {calendar.name}
            </button>
          </li>
        ))}
      </ul>

      <form className="mt-4 grid max-w-xl gap-3" onSubmit={submit}>
        <h3 className="font-semibold">Add a calendar</h3>
        <label className="grid gap-1 text-sm">
          Name
          <input
            className="rounded border px-2 py-1"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="grid gap-1 text-sm">
          Secret address in iCal format
          <input
            className="rounded border px-2 py-1"
            required
            type="url"
            placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isSleep} onChange={(event) => setIsSleep(event.target.checked)} />
          This is my sleep calendar
        </label>
        {isSleep && (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sleepAsAndroid}
              onChange={(event) => setSleepAsAndroid(event.target.checked)}
            />
            It is written by Sleep as Android
          </label>
        )}
        <button type="submit" className="justify-self-start rounded bg-slate-800 px-4 py-2 text-white">
          Add calendar
        </button>
        {add.isError && (
          <p role="alert" className="text-sm">
            The calendar could not be added. Check the name and the address.
          </p>
        )}
      </form>
    </section>
  )
}

export function CalendarPage() {
  const [monday, setMonday] = useState(() => startOfWeek(today()))
  const sunday = shiftDate(monday, 6)

  const calendars = useQuery({
    queryKey: ['calendars', 'calendars'],
    queryFn: async () => unwrap(await api.GET('/api/calendars/calendars/')),
  })
  const events = useQuery({
    queryKey: ['calendars', 'events', monday],
    queryFn: async () => {
      const query = { start: toTimestamp(monday), end: toTimestamp(shiftDate(monday, 7)) }
      return unwrap(await api.GET('/api/calendars/events/', { params: { query } }))
    },
  })

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="rounded border px-3 py-1" onClick={() => setMonday(shiftDate(monday, -7))}>
          Previous week
        </button>
        <h1 className="min-w-72 text-center text-xl font-semibold">
          {formatDate(monday)} – {formatDate(sunday)}
        </h1>
        <button type="button" className="rounded border px-3 py-1" onClick={() => setMonday(shiftDate(monday, 7))}>
          Next week
        </button>
      </div>

      {(calendars.isPending || events.isPending) && <p className="mt-4">Loading…</p>}
      {(calendars.isError || events.isError) && <p className="mt-4">The calendar could not be loaded.</p>}
      {calendars.data && events.data && <Agenda events={events.data} calendars={calendars.data} />}
      {calendars.data && <CalendarSettings calendars={calendars.data} />}
    </div>
  )
}
