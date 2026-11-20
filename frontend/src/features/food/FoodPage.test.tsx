import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import type { Dish, Restaurant } from '../../api/client'
import { mockApi, renderWithQuery } from '../../test-utils'
import { FoodPage } from './FoodPage'

const exactum: Restaurant = {
  id: 1,
  name: 'Exactum',
  campus: 'Kumpula',
  address: '',
  lunch_hours: 'Mon–Fri 11.00-14.00',
  url: '',
  is_favourite: true,
}
const olivia: Restaurant = { ...exactum, id: 2, name: 'Olivia', campus: '', lunch_hours: '', is_favourite: false }

const soup: Dish = {
  id: 10,
  restaurant: 1,
  date: '2026-11-16',
  name: 'Sweet potato soup',
  category: 'Vegaanilounas',
  diets: ['G', 'Veg'],
  allergens: [],
  prices: { student: '3.10' },
}
const notice: Dish = { ...soup, id: 11, name: 'Closed for an event', diets: [], prices: {} }

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 10, 16, 12))
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

test('shows the dishes of favourite restaurants for today', async () => {
  mockApi({
    'GET /api/food/restaurants/': { body: [exactum, olivia] },
    'GET /api/food/dishes/?date=2026-11-16': { body: [soup, notice] },
  })
  renderWithQuery(<FoodPage />)

  expect(await screen.findByRole('heading', { name: 'Exactum' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Monday 16 November' })).toBeInTheDocument()
  expect(screen.getByText('Kumpula · Mon–Fri 11.00-14.00')).toBeInTheDocument()
  expect(screen.getByText('Sweet potato soup')).toBeInTheDocument()
  expect(screen.getByText('G · Veg')).toBeInTheDocument()
  expect(screen.getByText('3.10 €')).toBeInTheDocument()
  expect(within(screen.getByText('Closed for an event').closest('li')!).queryByText(/€/)).toBeNull()
  expect(screen.queryByRole('heading', { name: 'Olivia' })).toBeNull()
})

test('can show all restaurants', async () => {
  mockApi({
    'GET /api/food/restaurants/': { body: [exactum, olivia] },
    'GET /api/food/dishes/?date=2026-11-16': { body: [soup] },
  })
  renderWithQuery(<FoodPage />)

  await userEvent.click(await screen.findByRole('checkbox', { name: 'Show all restaurants' }))

  const card = screen.getByRole('heading', { name: 'Olivia' }).closest('section')!
  expect(within(card).getByText('No menu for this day.')).toBeInTheDocument()
})

test('shows every restaurant when there are no favourites', async () => {
  mockApi({
    'GET /api/food/restaurants/': { body: [olivia] },
    'GET /api/food/dishes/?date=2026-11-16': { body: [] },
  })
  renderWithQuery(<FoodPage />)

  expect(await screen.findByRole('heading', { name: 'Olivia' })).toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).toBeNull()
})

test('moves between days', async () => {
  const calls = mockApi({
    'GET /api/food/restaurants/': { body: [exactum] },
    'GET /api/food/dishes/?date=2026-11-16': { body: [] },
    'GET /api/food/dishes/?date=2026-11-17': { body: [] },
    'GET /api/food/dishes/?date=2026-11-15': { body: [] },
  })
  renderWithQuery(<FoodPage />)

  await userEvent.click(screen.getByRole('button', { name: 'Next day' }))
  expect(await screen.findByRole('heading', { name: 'Tuesday 17 November' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Previous day' }))
  await userEvent.click(screen.getByRole('button', { name: 'Previous day' }))
  expect(await screen.findByRole('heading', { name: 'Sunday 15 November' })).toBeInTheDocument()
  await screen.findByRole('heading', { name: 'Exactum' })
  expect(calls).toContain('GET /api/food/dishes/?date=2026-11-15')
})

test('adds and removes favourites', async () => {
  let favourite = false
  const calls = mockApi({
    'GET /api/food/restaurants/': () => ({ body: [{ ...olivia, is_favourite: favourite }] }),
    'GET /api/food/dishes/?date=2026-11-16': { body: [] },
    'PUT /api/food/restaurants/2/favourite/': () => {
      favourite = true
      return { status: 204 }
    },
    'DELETE /api/food/restaurants/2/favourite/': () => {
      favourite = false
      return { status: 204 }
    },
  })
  renderWithQuery(<FoodPage />)

  await userEvent.click(await screen.findByRole('button', { name: 'Add Olivia to favourites' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Remove Olivia from favourites' }))
  expect(await screen.findByRole('button', { name: 'Add Olivia to favourites' })).toBeInTheDocument()
  expect(calls).toContain('PUT /api/food/restaurants/2/favourite/')
  expect(calls).toContain('DELETE /api/food/restaurants/2/favourite/')
})

test('reports when a favourite cannot be saved', async () => {
  mockApi({
    'GET /api/food/restaurants/': { body: [olivia] },
    'GET /api/food/dishes/?date=2026-11-16': { body: [] },
    'PUT /api/food/restaurants/2/favourite/': { status: 403 },
  })
  renderWithQuery(<FoodPage />)

  await userEvent.click(await screen.findByRole('button', { name: 'Add Olivia to favourites' }))
  expect(await screen.findByText('The favourite could not be saved.')).toBeInTheDocument()
})

test('reports when menus cannot be loaded', async () => {
  mockApi({})
  renderWithQuery(<FoodPage />)
  expect(await screen.findByText('The menus could not be loaded.')).toBeInTheDocument()
})

test('explains an empty database', async () => {
  mockApi({
    'GET /api/food/restaurants/': { body: [] },
    'GET /api/food/dishes/?date=2026-11-16': { body: [] },
  })
  renderWithQuery(<FoodPage />)
  expect(await screen.findByText(/No menus have been fetched yet/)).toBeInTheDocument()
})
