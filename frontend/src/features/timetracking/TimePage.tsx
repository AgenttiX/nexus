import { useQuery } from '@tanstack/react-query'
import { Suspense, lazy, useState } from 'react'

import { api, unwrap, type TimeSummary } from '../../api/client'
import { SERIES_COLORS } from '../../components/colors'
import { formatSpan, formatTime, shiftDate, today } from '../../dates'

const Plot = lazy(() => import('../../components/Plot'))
const PERIODS = [7, 30, 90]
const TOP_APPS = 15

function HoursTable({ title, rows }: { title: string; rows: TimeSummary['by_app'] }) {
  return (
    <section>
      <h2 className="font-semibold">{title}</h2>
      <table className="mt-1">
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <th scope="row" className="pr-6 text-left font-normal">
                {row.name}
              </th>
              <td className="text-right tabular-nums">{formatSpan(row.hours)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Summary({ summary }: { summary: TimeSummary }) {
  return (
    <>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <section className="rounded-lg border border-slate-200 p-4">
          <h2 className="text-sm text-slate-500">Active time</h2>
          <p className="text-3xl font-semibold tabular-nums">{formatSpan(summary.total)}</p>
        </section>
        <section className="rounded-lg border border-slate-200 p-4">
          <h2 className="text-sm text-slate-500">Average per day</h2>
          <p className="text-3xl font-semibold tabular-nums">{formatSpan(summary.total / summary.by_day.length)}</p>
        </section>
      </div>
      <section className="mt-6">
        <h2 className="font-semibold">Active time per day</h2>
        <Suspense fallback={<p>Loading chart…</p>}>
          <Plot
            label="Bar chart of active hours per day"
            data={[
              {
                type: 'bar',
                x: summary.by_day.map((day) => day.date),
                y: summary.by_day.map((day) => day.hours),
                text: summary.by_day.map((day) => formatSpan(day.hours)),
                textposition: 'none',
                hovertemplate: '%{x|%a %-d %b}: %{text}<extra></extra>',
                marker: { color: SERIES_COLORS[0] },
              },
            ]}
            layout={{ yaxis: { title: { text: 'Hours' }, rangemode: 'tozero' } }}
          />
        </Suspense>
      </section>
      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <HoursTable title="Apps" rows={summary.by_app.slice(0, TOP_APPS)} />
        <HoursTable title="Devices" rows={summary.by_device} />
      </div>
    </>
  )
}

export function TimePage() {
  const [days, setDays] = useState(PERIODS[0])
  const end = today()
  const query = { start: shiftDate(end, -(days - 1)), end }

  const summary = useQuery({
    queryKey: ['timetracking', 'summary', query],
    queryFn: async () => unwrap(await api.GET('/api/timetracking/summary/', { params: { query } })),
  })
  const buckets = useQuery({
    queryKey: ['timetracking', 'buckets'],
    queryFn: async () => unwrap(await api.GET('/api/timetracking/buckets/')),
  })

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-semibold">Time</h1>
        {PERIODS.map((period) => (
          <button
            key={period}
            type="button"
            aria-pressed={period === days}
            className="rounded border px-3 py-1 aria-pressed:bg-slate-800 aria-pressed:text-white"
            onClick={() => setDays(period)}
          >
            {period} days
          </button>
        ))}
      </div>

      {(summary.isPending || buckets.isPending) && <p className="mt-4">Loading…</p>}
      {(summary.isError || buckets.isError) && <p className="mt-4">Time tracking could not be loaded.</p>}

      {buckets.data?.length === 0 && (
        <p className="mt-4 max-w-2xl">
          No ActivityWatch data has been imported yet. Synchronise the databases of your devices to a directory named
          after your username in the server’s ActivityWatch directory; they are read every 15 minutes.
        </p>
      )}
      {summary.data && buckets.data && buckets.data.length > 0 && (
        <>
          {summary.data.total > 0 ? (
            <Summary summary={summary.data} />
          ) : (
            <p className="mt-4">No activity was recorded in this period.</p>
          )}
          <section className="mt-8 border-t border-slate-200 pt-4">
            <h2 className="text-lg font-semibold">Imported data</h2>
            <ul className="mt-2 text-sm">
              {buckets.data.map((bucket) => (
                <li key={bucket.id}>
                  {bucket.name}{' '}
                  <span className="text-slate-500">
                    {bucket.imported_until
                      ? `until ${bucket.imported_until.slice(0, 10)} ${formatTime(bucket.imported_until)}`
                      : 'no events'}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}
