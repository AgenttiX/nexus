import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'

import type { Digest, NewsProfile, NewsSource } from '../../api/client'
import { mockApi, renderWithQuery } from '../../test-utils'
import { NewsPage } from './NewsPage'

const sources: NewsSource[] = [
  { key: 'yle', name: 'Yle', language: 'fi', full_text: true },
  { key: 'hs', name: 'Helsingin Sanomat', language: 'fi', full_text: false },
]
const profile: NewsProfile = {
  enabled: false,
  digest_hour: 18,
  sources: ['yle'],
  criteria: 'Politics and science.',
  max_articles: 20,
  mode: 'parallel',
  selection_model: '',
  summary_model: '',
  language: 'English',
}
const today: Digest = {
  id: 2,
  date: '2026-11-21',
  status: 'done',
  mode: 'parallel',
  summary: 'Budget passed.\nMarkets calm.',
  error: '',
  created_at: '2026-11-21T16:00:00Z',
  selected: [
    {
      article: {
        id: 7,
        source: 'yle',
        url: 'https://yle.fi/a/7',
        title: 'Parliament passes the budget',
        lead: '',
        published_at: '2026-11-21T10:00:00Z',
      },
      summary: '',
    },
  ],
}
const yesterday: Digest = { ...today, id: 1, date: '2026-11-20', summary: 'A quiet day.', selected: [] }

const base = {
  'GET /api/news/profile/': { body: profile },
  'GET /api/news/sources/': { body: sources },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('shows the newest digest with its articles', async () => {
  mockApi({ ...base, 'GET /api/news/digests/': { body: [today, yesterday] } })
  renderWithQuery(<NewsPage />)

  expect(await screen.findByRole('heading', { name: 'News of Saturday 21 November' })).toBeInTheDocument()
  expect(screen.getByText(/Budget passed\.\s+Markets calm\./)).toBeInTheDocument()
  const link = await screen.findByRole('link', { name: 'Parliament passes the budget' })
  expect(link).toHaveAttribute('href', 'https://yle.fi/a/7')
  expect(await within(link.closest('li')!).findByText('Yle')).toBeInTheDocument()
})

test('switches to an earlier digest', async () => {
  mockApi({ ...base, 'GET /api/news/digests/': { body: [today, yesterday] } })
  renderWithQuery(<NewsPage />)

  await userEvent.selectOptions(await screen.findByLabelText('Day'), '2026-11-20')
  expect(screen.getByText('A quiet day.')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Articles' })).toBeNull()
})

test('explains pending and failed digests', async () => {
  mockApi({ ...base, 'GET /api/news/digests/': { body: [{ ...today, status: 'pending' }] } })
  const { unmount } = renderWithQuery(<NewsPage />)
  expect(await screen.findByText(/The digest is being written/)).toBeInTheDocument()
  expect(screen.queryByLabelText('Day')).toBeNull()
  unmount()

  mockApi({ ...base, 'GET /api/news/digests/': { body: [{ ...today, status: 'failed', error: 'No model' }] } })
  renderWithQuery(<NewsPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('The digest could not be written: No model')
})

test('starts a digest and then shows it', async () => {
  let digests: Digest[] = []
  const calls = mockApi({
    ...base,
    'GET /api/news/digests/': () => ({ body: digests }),
    'POST /api/news/digests/generate/': () => {
      digests = [today]
      return { status: 202, body: { ...today, status: 'pending' } }
    },
  })
  renderWithQuery(<NewsPage />)

  expect(await screen.findByText(/No digest has been written yet/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'News' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Write today’s digest now' }))
  expect(await screen.findByText(/Budget passed/)).toBeInTheDocument()
  expect(calls).toContain('POST /api/news/digests/generate/')
})

test('reports when a digest cannot be started', async () => {
  mockApi({ ...base, 'GET /api/news/digests/': { body: [] }, 'POST /api/news/digests/generate/': { status: 500 } })
  renderWithQuery(<NewsPage />)
  await userEvent.click(await screen.findByRole('button', { name: 'Write today’s digest now' }))
  expect(await screen.findByText('The digest could not be started.')).toBeInTheDocument()
})

test('saves changed settings', async () => {
  let saved: unknown
  mockApi({
    ...base,
    'GET /api/news/digests/': { body: [] },
    'PATCH /api/news/profile/': (request) => {
      void request
        .clone()
        .json()
        .then((body) => (saved = body))
      return { body: profile }
    },
  })
  renderWithQuery(<NewsPage />)

  await userEvent.click(await screen.findByLabelText('Write a digest every day'))
  await userEvent.clear(screen.getByLabelText('Hour of the day (0–23)'))
  await userEvent.type(screen.getByLabelText('Hour of the day (0–23)'), '7')
  await userEvent.click(screen.getByLabelText(/Helsingin Sanomat/))
  expect(screen.getByText('titles and leads only')).toBeInTheDocument()
  await userEvent.click(screen.getByLabelText('Yle'))
  await userEvent.clear(screen.getByLabelText('Which articles are worth reading'))
  await userEvent.type(screen.getByLabelText('Which articles are worth reading'), 'Science.')
  await userEvent.clear(screen.getByLabelText('Most articles per digest'))
  await userEvent.type(screen.getByLabelText('Most articles per digest'), '5')
  await userEvent.click(screen.getByLabelText(/All articles in one context/))
  await userEvent.click(screen.getByLabelText(/One session per article/))
  await userEvent.click(screen.getByLabelText(/All articles in one context/))
  await userEvent.type(screen.getByLabelText(/Model for choosing articles/), 'small')
  await userEvent.type(screen.getByLabelText(/Model for writing summaries/), 'large')
  await userEvent.clear(screen.getByLabelText('Language of the digest'))
  await userEvent.type(screen.getByLabelText('Language of the digest'), 'Finnish')
  await userEvent.click(screen.getByRole('button', { name: 'Save settings' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Settings saved.')
  expect(saved).toEqual({
    enabled: true,
    digest_hour: 7,
    sources: ['hs'],
    criteria: 'Science.',
    max_articles: 5,
    mode: 'single',
    selection_model: 'small',
    summary_model: 'large',
    language: 'Finnish',
  })
})

test('reports when settings cannot be saved', async () => {
  mockApi({ ...base, 'GET /api/news/digests/': { body: [] }, 'PATCH /api/news/profile/': { status: 400 } })
  renderWithQuery(<NewsPage />)
  await userEvent.click(await screen.findByRole('button', { name: 'Save settings' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The settings could not be saved.')
})

test('reports when news cannot be loaded', async () => {
  mockApi({})
  renderWithQuery(<NewsPage />)
  expect(await screen.findByText('News could not be loaded.')).toBeInTheDocument()
})
