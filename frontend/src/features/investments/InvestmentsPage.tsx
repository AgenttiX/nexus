import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Suspense, lazy, useState, type FormEvent } from 'react'

import { api, unwrap, type Holding, type Portfolio } from '../../api/client'
import { SERIES_COLORS } from '../../components/colors'
import { formatEuros } from '../../money'

const Plot = lazy(() => import('../../components/Plot'))

type Provider = NonNullable<Holding['provider']>

/** Removes the trailing zeros of the eight-decimal numbers that the API sends. */
function plain(decimal: string): string {
  return String(Number(decimal))
}

function Positions({ portfolio, onRemove }: { portfolio: Portfolio; onRemove: (id: number) => void }) {
  return (
    <table className="mt-4 w-full text-sm">
      <thead>
        <tr className="text-left text-slate-500">
          <th className="font-normal">Asset</th>
          <th className="text-right font-normal">Quantity</th>
          <th className="text-right font-normal">Price</th>
          <th className="text-right font-normal">Value</th>
          <th className="text-right font-normal">Gain</th>
          <th />
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {portfolio.positions.map(({ holding, price, price_date, value_eur, gain_eur }) => (
          <tr key={holding.id}>
            <th scope="row" className="py-1 text-left font-normal">
              <span className="font-medium">{holding.asset.symbol}</span>{' '}
              <span className="text-slate-500">{holding.asset.name}</span>
              {holding.note && <span className="ml-2 text-xs text-slate-500">{holding.note}</span>}
            </th>
            <td className="text-right tabular-nums">{plain(holding.quantity)}</td>
            <td className="text-right tabular-nums" title={price_date ? `Price of ${price_date}` : undefined}>
              {price ? `${plain(price)} ${holding.asset.currency}` : 'No price yet'}
            </td>
            <td className="text-right tabular-nums">{value_eur ? formatEuros(value_eur) : '–'}</td>
            <td className="text-right tabular-nums">{gain_eur ? formatEuros(gain_eur) : '–'}</td>
            <td className="pl-4 text-right">
              <button type="button" className="underline" onClick={() => onRemove(holding.id)}>
                Remove {holding.asset.symbol}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function AddHolding({ onAdded }: { onAdded: () => void }) {
  const [provider, setProvider] = useState<Provider>('yahoo')
  const [symbol, setSymbol] = useState('')
  const [quantity, setQuantity] = useState('')
  const [cost, setCost] = useState('')
  const [note, setNote] = useState('')

  const add = useMutation({
    mutationFn: async () => {
      const body = { provider, symbol, quantity, cost: cost || null, note }
      return unwrap(await api.POST('/api/investments/holdings/', { body: body as Holding }))
    },
    onSuccess: () => {
      setSymbol('')
      setQuantity('')
      setCost('')
      setNote('')
      onAdded()
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    add.mutate()
  }

  return (
    <form className="mt-8 grid max-w-xl gap-3 border-t border-slate-200 pt-4" onSubmit={submit}>
      <h2 className="text-lg font-semibold">Add a holding</h2>
      <label className="grid gap-1 text-sm">
        Price source
        <select
          className="rounded border px-2 py-1"
          value={provider}
          onChange={(event) => setProvider(event.target.value as Provider)}
        >
          <option value="yahoo">Yahoo Finance (stocks, ETFs and funds)</option>
          <option value="coingecko">CoinGecko (cryptocurrencies)</option>
        </select>
      </label>
      <label className="grid gap-1 text-sm">
        {provider === 'yahoo' ? 'Ticker, for example NOKIA.HE' : 'CoinGecko id, for example bitcoin'}
        <input className="rounded border px-2 py-1" required value={symbol} onChange={(e) => setSymbol(e.target.value)} />
      </label>
      <label className="grid gap-1 text-sm">
        Quantity
        <input
          className="rounded border px-2 py-1"
          required
          inputMode="decimal"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
      </label>
      <label className="grid gap-1 text-sm">
        Total cost in euros (optional)
        <input
          className="rounded border px-2 py-1"
          inputMode="decimal"
          value={cost}
          onChange={(e) => setCost(e.target.value)}
        />
      </label>
      <label className="grid gap-1 text-sm">
        Note (optional)
        <input className="rounded border px-2 py-1" value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <button type="submit" className="justify-self-start rounded bg-slate-800 px-4 py-2 text-white">
        Add holding
      </button>
      {add.isPending && <p role="status">Fetching prices…</p>}
      {add.isError && (
        <p role="alert">The holding could not be added. Check the symbol and the numbers.</p>
      )}
    </form>
  )
}

export function InvestmentsPage() {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['investments'] })
  const portfolio = useQuery({
    queryKey: ['investments', 'portfolio'],
    queryFn: async () => unwrap(await api.GET('/api/investments/portfolio/')),
  })
  const remove = useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.DELETE('/api/investments/holdings/{id}/', { params: { path: { id } } })),
    onSettled: refresh,
  })

  return (
    <div>
      <h1 className="text-xl font-semibold">Investments</h1>
      {portfolio.isPending && <p className="mt-4">Loading…</p>}
      {portfolio.isError && <p className="mt-4">Investments could not be loaded.</p>}
      {portfolio.data && portfolio.data.positions.length === 0 && (
        <p className="mt-4">No holdings yet. Add your first one below.</p>
      )}
      {portfolio.data && portfolio.data.positions.length > 0 && (
        <>
          <section className="mt-4 max-w-xs rounded-lg border border-slate-200 p-4">
            <h2 className="text-sm text-slate-500">Total value</h2>
            <p className="text-3xl font-semibold tabular-nums">{formatEuros(portfolio.data.total_eur)}</p>
          </section>
          <Positions portfolio={portfolio.data} onRemove={(id) => remove.mutate(id)} />
          {portfolio.data.history.length > 1 && (
            <section className="mt-6">
              <h2 className="font-semibold">Value of the current holdings over the last year</h2>
              <Suspense fallback={<p>Loading chart…</p>}>
                <Plot
                  label="Line chart of the value of the current holdings over the last year"
                  data={[
                    {
                      type: 'scatter',
                      mode: 'lines',
                      x: portfolio.data.history.map((point) => point.date),
                      y: portfolio.data.history.map((point) => Number(point.value_eur)),
                      hovertemplate: '%{x|%-d %b %Y}: %{y:,.2f} €<extra></extra>',
                      line: { color: SERIES_COLORS[0], width: 2 },
                    },
                  ]}
                  layout={{ yaxis: { title: { text: '€' } } }}
                />
              </Suspense>
            </section>
          )}
        </>
      )}
      <AddHolding onAdded={refresh} />
    </div>
  )
}
