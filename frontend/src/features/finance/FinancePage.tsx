import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Suspense, lazy, useState, type FormEvent } from 'react'

import {
  api,
  unwrap,
  uploadFile,
  type BankAccount,
  type Category,
  type FinanceSummary,
  type ImportBatch,
  type Transaction,
} from '../../api/client'
import { SERIES_COLORS } from '../../components/colors'
import { shiftDate, today } from '../../dates'
import { formatEuros } from '../../money'

const Plot = lazy(() => import('../../components/Plot'))
const PERIODS = [30, 90, 365]

function Totals({ summary }: { summary: FinanceSummary }) {
  const tiles = [
    ['Income', summary.income],
    ['Expenses', summary.expenses],
    ['Net', summary.net],
  ]
  return (
    <div className="mt-4 grid gap-4 sm:grid-cols-3">
      {tiles.map(([title, amount]) => (
        <section key={title} className="rounded-lg border border-slate-200 p-4">
          <h2 className="text-sm text-slate-500">{title}</h2>
          <p className="text-3xl font-semibold tabular-nums">{formatEuros(amount)}</p>
        </section>
      ))}
    </div>
  )
}

function MonthChart({ summary }: { summary: FinanceSummary }) {
  const months = summary.by_month.map((month) => month.month)
  const series = (name: string, values: string[], color: string) => ({
    type: 'bar' as const,
    name,
    x: months,
    y: values.map(Number),
    hovertemplate: `%{x|%B %Y}: %{y:.2f} €<extra>${name}</extra>`,
    marker: { color },
  })
  return (
    <section className="mt-6">
      <h2 className="font-semibold">Income and expenses by month</h2>
      <Suspense fallback={<p>Loading chart…</p>}>
        <Plot
          label="Bar chart of income and expenses by month"
          data={[
            series('Income', summary.by_month.map((month) => month.income), SERIES_COLORS[0]),
            series('Expenses', summary.by_month.map((month) => month.expenses), SERIES_COLORS[1]),
          ]}
          layout={{ barmode: 'group', xaxis: { tickformat: '%b %Y', dtick: 'M1' }, yaxis: { title: { text: '€' } } }}
        />
      </Suspense>
    </section>
  )
}

function CategoryTotals({ summary }: { summary: FinanceSummary }) {
  return (
    <section className="mt-6">
      <h2 className="font-semibold">Expenses by category</h2>
      <table className="mt-1">
        <tbody>
          {summary.by_category.map((item) => (
            <tr key={item.category}>
              <th scope="row" className="pr-6 text-left font-normal">
                {item.category}
              </th>
              <td className="text-right tabular-nums">{formatEuros(item.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Transactions({ transactions, categories }: { transactions: Transaction[]; categories: Category[] }) {
  const queryClient = useQueryClient()
  const categorise = useMutation({
    mutationFn: async ({ id, category }: { id: number; category: number | null }) =>
      unwrap(await api.PATCH('/api/finance/transactions/{id}/', { params: { path: { id } }, body: { category } })),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['finance'] }),
  })
  return (
    <section className="mt-6">
      <h2 className="font-semibold">Transactions</h2>
      {transactions.length === 0 ? (
        <p className="mt-1 text-slate-500">No transactions in this period.</p>
      ) : (
        <table className="mt-1 w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500">
              <th className="font-normal">Date</th>
              <th className="font-normal">Counterparty</th>
              <th className="font-normal">Message</th>
              <th className="text-right font-normal">Amount</th>
              <th className="pl-4 font-normal">Category</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {transactions.map((transaction) => (
              <tr key={transaction.id}>
                <td className="py-1 tabular-nums">{transaction.date}</td>
                <td>{transaction.counterparty}</td>
                <td className="text-slate-600">{transaction.message}</td>
                <td className="text-right tabular-nums">{formatEuros(transaction.amount)}</td>
                <td className="pl-4">
                  <select
                    aria-label={`Category of ${transaction.counterparty || 'transaction'} on ${transaction.date}`}
                    className="rounded border px-1"
                    value={transaction.category ?? ''}
                    onChange={(event) =>
                      categorise.mutate({ id: transaction.id, category: Number(event.target.value) || null })
                    }
                  >
                    <option value="">Uncategorised</option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function Setup({ accounts }: { accounts: BankAccount[] }) {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['finance'] })
  const [name, setName] = useState('')
  const [iban, setIban] = useState('')
  const [category, setCategory] = useState('')

  const addAccount = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST('/api/finance/accounts/', { body: { name, iban } as BankAccount })),
    onSuccess: () => {
      setName('')
      setIban('')
    },
    onSettled: refresh,
  })
  const addCategory = useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/finance/categories/', { body: { name: category } as Category })),
    onSuccess: () => setCategory(''),
    onSettled: refresh,
  })
  const importFile = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) =>
      uploadFile<ImportBatch>(`/api/finance/accounts/${id}/import/`, file),
    onSettled: refresh,
  })

  function submit(mutate: () => void) {
    return (event: FormEvent) => {
      event.preventDefault()
      mutate()
    }
  }

  return (
    <section className="mt-8 border-t border-slate-200 pt-4">
      <h2 className="text-lg font-semibold">Accounts</h2>
      <ul className="mt-2 divide-y divide-slate-100">
        {accounts.map((account) => (
          <li key={account.id} className="flex flex-wrap items-baseline gap-3 py-2">
            <span className="font-medium">{account.name}</span>
            <span className="mr-auto text-sm text-slate-500 tabular-nums">{account.iban}</span>
            <label className="text-sm">
              Import transactions to {account.name}{' '}
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) {
                    importFile.mutate({ id: account.id, file })
                  }
                }}
              />
            </label>
          </li>
        ))}
      </ul>
      {importFile.data && (
        <p role="status" className="text-sm">
          Imported {importFile.data.imported} transactions from {importFile.data.filename};{' '}
          {importFile.data.duplicates} were already there.
        </p>
      )}
      {importFile.isError && (
        <p role="alert" className="text-sm">
          The file could not be imported. Check that it is in the format of the account’s bank.
        </p>
      )}

      <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={submit(() => addAccount.mutate())}>
        <label className="grid gap-1 text-sm">
          Account name
          <input className="rounded border px-2 py-1" required value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="grid gap-1 text-sm">
          IBAN
          <input className="rounded border px-2 py-1" required value={iban} onChange={(e) => setIban(e.target.value)} />
        </label>
        <button type="submit" className="rounded bg-slate-800 px-4 py-1.5 text-white">
          Add account
        </button>
        {addAccount.isError && <p role="alert">The account could not be added. Check the IBAN.</p>}
      </form>

      <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={submit(() => addCategory.mutate())}>
        <label className="grid gap-1 text-sm">
          New category
          <input
            className="rounded border px-2 py-1"
            required
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
        </label>
        <button type="submit" className="rounded bg-slate-800 px-4 py-1.5 text-white">
          Add category
        </button>
        {addCategory.isError && <p role="alert">The category could not be added.</p>}
      </form>
    </section>
  )
}

export function FinancePage() {
  const [days, setDays] = useState(PERIODS[1])
  const end = today()
  const query = { start: shiftDate(end, -(days - 1)), end }

  const summary = useQuery({
    queryKey: ['finance', 'summary', query],
    queryFn: async () => unwrap(await api.GET('/api/finance/summary/', { params: { query } })),
  })
  const transactions = useQuery({
    queryKey: ['finance', 'transactions', query],
    queryFn: async () => unwrap(await api.GET('/api/finance/transactions/', { params: { query } })),
  })
  const accounts = useQuery({
    queryKey: ['finance', 'accounts'],
    queryFn: async () => unwrap(await api.GET('/api/finance/accounts/')),
  })
  const categories = useQuery({
    queryKey: ['finance', 'categories'],
    queryFn: async () => unwrap(await api.GET('/api/finance/categories/')),
  })
  const queries = [summary, transactions, accounts, categories]

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-xl font-semibold">Finances</h1>
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

      {queries.some((item) => item.isPending) && <p className="mt-4">Loading…</p>}
      {queries.some((item) => item.isError) && <p className="mt-4">Finances could not be loaded.</p>}

      {summary.data && transactions.data && categories.data && (
        <>
          <Totals summary={summary.data} />
          {summary.data.by_month.length > 0 && <MonthChart summary={summary.data} />}
          {summary.data.by_category.length > 0 && <CategoryTotals summary={summary.data} />}
          <Transactions transactions={transactions.data} categories={categories.data} />
        </>
      )}
      {accounts.data && <Setup accounts={accounts.data} />}
    </div>
  )
}
