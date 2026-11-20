import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { api, unwrap, type Digest, type NewsProfile, type NewsSource } from '../../api/client'
import { formatDate } from '../../dates'

/** How often a digest that is still being written is checked, in milliseconds. */
const POLL_INTERVAL = 5000

function DigestView({ digest, sources }: { digest: Digest; sources: NewsSource[] }) {
  const names = new Map(sources.map((source) => [source.key as string, source.name]))
  if (digest.status === 'pending') {
    return <p className="mt-4">The digest is being written. This can take a few minutes.</p>
  }
  if (digest.status === 'failed') {
    return (
      <p role="alert" className="mt-4">
        The digest could not be written: {digest.error}
      </p>
    )
  }
  return (
    <>
      <p className="mt-4 max-w-3xl leading-relaxed whitespace-pre-wrap">{digest.summary}</p>
      {digest.selected.length > 0 && (
        <section className="mt-6">
          <h2 className="font-semibold">Articles</h2>
          <ul className="mt-1 space-y-1">
            {digest.selected.map(({ article }) => (
              <li key={article.id}>
                <a className="underline" href={article.url} target="_blank" rel="noreferrer">
                  {article.title}
                </a>
                <span className="ml-2 text-sm text-slate-500">{names.get(article.source)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}

function Settings({ profile, sources }: { profile: NewsProfile; sources: NewsSource[] }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState(profile)
  const set = (changes: Partial<NewsProfile>) => setDraft({ ...draft, ...changes })

  const save = useMutation({
    mutationFn: async () => unwrap(await api.PATCH('/api/news/profile/', { body: draft })),
    onSuccess: (saved) => queryClient.setQueryData(['news', 'profile'], saved),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate()
  }

  function toggleSource(key: NewsProfile['sources'][number], checked: boolean) {
    set({ sources: checked ? [...draft.sources, key] : draft.sources.filter((source) => source !== key) })
  }

  return (
    <form className="mt-8 grid max-w-2xl gap-4 border-t border-slate-200 pt-4" onSubmit={submit}>
      <h2 className="text-lg font-semibold">Settings</h2>
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={draft.enabled} onChange={(event) => set({ enabled: event.target.checked })} />
        Write a digest every day
      </label>
      <label className="grid gap-1 text-sm">
        Hour of the day (0–23)
        <input
          className="w-24 rounded border px-2 py-1"
          type="number"
          min={0}
          max={23}
          value={draft.digest_hour}
          onChange={(event) => set({ digest_hour: Number(event.target.value) })}
        />
      </label>
      <fieldset>
        <legend className="text-sm">Sources</legend>
        {sources.map((source) => (
          <label key={source.key} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={draft.sources.includes(source.key as NewsProfile['sources'][number])}
              onChange={(event) =>
                toggleSource(source.key as NewsProfile['sources'][number], event.target.checked)
              }
            />
            {source.name}
            {!source.full_text && <span className="text-sm text-slate-500">titles and leads only</span>}
          </label>
        ))}
      </fieldset>
      <label className="grid gap-1 text-sm">
        Which articles are worth reading
        <textarea
          className="rounded border px-2 py-1"
          rows={4}
          value={draft.criteria}
          onChange={(event) => set({ criteria: event.target.value })}
        />
      </label>
      <label className="grid gap-1 text-sm">
        Most articles per digest
        <input
          className="w-24 rounded border px-2 py-1"
          type="number"
          min={1}
          max={100}
          value={draft.max_articles}
          onChange={(event) => set({ max_articles: Number(event.target.value) })}
        />
      </label>
      <fieldset>
        <legend className="text-sm">How the digest is written</legend>
        <label className="flex items-center gap-2">
          <input type="radio" checked={draft.mode === 'parallel'} onChange={() => set({ mode: 'parallel' })} />
          One session per article, then a summary of the summaries (local models)
        </label>
        <label className="flex items-center gap-2">
          <input type="radio" checked={draft.mode === 'single'} onChange={() => set({ mode: 'single' })} />
          All articles in one context (models with very large context windows)
        </label>
      </fieldset>
      <label className="grid gap-1 text-sm">
        Model for choosing articles (empty for the default)
        <input
          className="rounded border px-2 py-1"
          value={draft.selection_model}
          onChange={(event) => set({ selection_model: event.target.value })}
        />
      </label>
      <label className="grid gap-1 text-sm">
        Model for writing summaries (empty for the default)
        <input
          className="rounded border px-2 py-1"
          value={draft.summary_model}
          onChange={(event) => set({ summary_model: event.target.value })}
        />
      </label>
      <label className="grid gap-1 text-sm">
        Language of the digest
        <input
          className="rounded border px-2 py-1"
          value={draft.language}
          onChange={(event) => set({ language: event.target.value })}
        />
      </label>
      <button type="submit" className="justify-self-start rounded bg-slate-800 px-4 py-2 text-white">
        Save settings
      </button>
      {save.isSuccess && <p role="status">Settings saved.</p>}
      {save.isError && <p role="alert">The settings could not be saved. Choose at least one source.</p>}
    </form>
  )
}

export function NewsPage() {
  const queryClient = useQueryClient()
  const [chosen, setChosen] = useState<number | null>(null)

  const digests = useQuery({
    queryKey: ['news', 'digests'],
    queryFn: async () => unwrap(await api.GET('/api/news/digests/')),
    refetchInterval: (query) => (query.state.data?.some((digest) => digest.status === 'pending') ? POLL_INTERVAL : false),
  })
  const profile = useQuery({
    queryKey: ['news', 'profile'],
    queryFn: async () => unwrap(await api.GET('/api/news/profile/')),
  })
  const sources = useQuery({
    queryKey: ['news', 'sources'],
    queryFn: async () => unwrap(await api.GET('/api/news/sources/')),
  })
  const generate = useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/news/digests/generate/')),
    onSuccess: () => setChosen(null),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['news', 'digests'] }),
  })

  const list = digests.data ?? []
  const digest = list.find((item) => item.id === chosen) ?? list[0]

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-xl font-semibold">{digest ? `News of ${formatDate(digest.date)}` : 'News'}</h1>
        {list.length > 1 && (
          <label className="flex items-center gap-2 text-sm">
            Day
            <select
              className="rounded border px-2 py-1"
              value={digest.id}
              onChange={(event) => setChosen(Number(event.target.value))}
            >
              {list.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.date}
                </option>
              ))}
            </select>
          </label>
        )}
        <button type="button" className="rounded border px-3 py-1" onClick={() => generate.mutate()}>
          Write today’s digest now
        </button>
      </div>

      {digests.isPending && <p className="mt-4">Loading…</p>}
      {(digests.isError || profile.isError || sources.isError) && <p className="mt-4">News could not be loaded.</p>}
      {generate.isError && <p className="mt-4">The digest could not be started.</p>}
      {digests.isSuccess && !digest && (
        <p className="mt-4">No digest has been written yet. Write one now, or turn on the daily digest below.</p>
      )}
      {digest && sources.data && <DigestView digest={digest} sources={sources.data} />}
      {profile.data && sources.data && <Settings profile={profile.data as NewsProfile} sources={sources.data} />}
    </div>
  )
}
