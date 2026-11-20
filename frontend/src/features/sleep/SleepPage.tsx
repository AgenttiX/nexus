import { useQuery } from '@tanstack/react-query'
import { Suspense, lazy, useState } from 'react'

import { api, unwrap, type SleepRecord, type SleepStats } from '../../api/client'
import { SERIES_COLORS } from '../../components/colors'
import { formatClock, formatSpan, shiftDate, today } from '../../dates'

// The charting library is large, so it is loaded only when a chart is shown.
const Plot = lazy(() => import('../../components/Plot'))

const PERIODS = [30, 90, 365]
/** Shorter periods of sleep are naps and are left out of the charts of nights. */
const MIN_NIGHT_HOURS = 3

function signed(hours: number): string {
  return (Math.round(hours * 60) < 0 ? '−' : '+') + formatSpan(hours)
}

function StatTile({
  title,
  stats,
  format,
  note,
}: {
  title: string
  stats: SleepStats | null
  format: (hours: number) => string
  note?: string
}) {
  return (
    <section className="rounded-lg border border-slate-200 p-4">
      <h2 className="text-sm text-slate-500">{title}</h2>
      {stats ? (
        <>
          <p className="text-3xl font-semibold tabular-nums">{format(stats.mean)}</p>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 text-sm text-slate-600 tabular-nums">
            <dt>Median</dt>
            <dd>{format(stats.median)}</dd>
            <dt>Range</dt>
            <dd>
              {format(stats.minimum)} to {format(stats.maximum)}
            </dd>
            <dt>Std. deviation</dt>
            <dd>{formatSpan(stats.std)}</dd>
          </dl>
        </>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Not enough data.</p>
      )}
      {note && <p className="mt-2 text-xs text-slate-500">{note}</p>}
    </section>
  )
}

/** Hours after local midnight, with evening times as negative hours so that nights plot around midnight. */
function clockHours(timestamp: string): number {
  const date = new Date(timestamp)
  const hours = date.getHours() + date.getMinutes() / 60
  return hours >= 18 ? hours - 24 : hours
}

function wakeDate(record: SleepRecord): string {
  const date = new Date(record.end)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function Charts({ records }: { records: SleepRecord[] }) {
  const nights = records.filter((record) => record.duration_hours >= MIN_NIGHT_HOURS)
  const dates = nights.map(wakeDate)
  const ticks = [-6, -4, -2, 0, 2, 4, 6, 8, 10, 12]
  return (
    <Suspense fallback={<p className="mt-6">Loading charts…</p>}>
      <section className="mt-6">
        <h2 className="font-semibold">Time asleep per night</h2>
        <Plot
          label="Bar chart of hours asleep per night"
          data={[
            {
              type: 'bar',
              x: dates,
              y: nights.map((record) => record.duration_hours),
              text: nights.map((record) => formatSpan(record.duration_hours)),
              textposition: 'none',
              hovertemplate: '%{x|%a %-d %b}: %{text}<extra></extra>',
              marker: { color: SERIES_COLORS[0] },
            },
          ]}
          layout={{ yaxis: { title: { text: 'Hours' }, rangemode: 'tozero' } }}
        />
      </section>
      <section className="mt-6">
        <h2 className="font-semibold">Bedtime and wake-up</h2>
        <Plot
          label="Scatter chart of bedtime and wake-up time per night"
          data={[
            {
              type: 'scatter',
              mode: 'markers',
              name: 'Bedtime',
              x: dates,
              y: nights.map((record) => clockHours(record.start)),
              text: nights.map((record) => formatClock(clockHours(record.start))),
              hovertemplate: '%{x|%a %-d %b}: asleep %{text}<extra></extra>',
              marker: { color: SERIES_COLORS[0], size: 8 },
            },
            {
              type: 'scatter',
              mode: 'markers',
              name: 'Wake-up',
              x: dates,
              y: nights.map((record) => clockHours(record.end)),
              text: nights.map((record) => formatClock(clockHours(record.end))),
              hovertemplate: '%{x|%a %-d %b}: awake %{text}<extra></extra>',
              marker: { color: SERIES_COLORS[1], size: 8, symbol: 'diamond' },
            },
          ]}
          layout={{ yaxis: { tickvals: ticks, ticktext: ticks.map(formatClock), autorange: 'reversed' } }}
        />
      </section>
    </Suspense>
  )
}

export function SleepPage() {
  const [days, setDays] = useState(PERIODS[0])
  const end = today()
  const query = { start: shiftDate(end, -(days - 1)), end }

  const summary = useQuery({
    queryKey: ['sleep', 'summary', query],
    queryFn: async () => unwrap(await api.GET('/api/sleep/summary/', { params: { query } })),
  })
  const records = useQuery({
    queryKey: ['sleep', 'records', query],
    queryFn: async () => unwrap(await api.GET('/api/sleep/records/', { params: { query } })),
  })

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-semibold">Sleep</h1>
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

      {(summary.isPending || records.isPending) && <p className="mt-4">Loading…</p>}
      {(summary.isError || records.isError) && <p className="mt-4">Sleep data could not be loaded.</p>}

      {summary.data && records.data && summary.data.nights === 0 && (
        <p className="mt-4">
          No nights in this period. Add your sleep calendar on the Calendar page and mark it as the sleep calendar.
        </p>
      )}
      {summary.data && records.data && summary.data.nights > 0 && (
        <>
          <p className="mt-4 text-sm text-slate-600">{summary.data.nights} nights</p>
          <div className="mt-2 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile title="Average bedtime" stats={summary.data.bedtime} format={formatClock} />
            <StatTile title="Average wake-up" stats={summary.data.wake_time} format={formatClock} />
            <StatTile title="Average time asleep" stats={summary.data.duration} format={formatSpan} />
            <StatTile
              title="Weekend jet lag"
              stats={summary.data.jet_lag}
              format={signed}
              note="How much later the middle of sleep is at weekends than on weekdays."
            />
          </div>
          <Charts records={records.data} />
        </>
      )}
    </div>
  )
}
