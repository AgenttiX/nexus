import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api, unwrap, type Dish, type Restaurant } from '../../api/client'
import { formatDate, shiftDate, today } from '../../dates'

function DishRow({ dish }: { dish: Dish }) {
  const price = dish.prices.student
  return (
    <li className="flex items-baseline justify-between gap-4 py-1">
      <span>
        {dish.name}
        {dish.diets.length > 0 && <span className="ml-2 text-xs text-slate-500">{dish.diets.join(' · ')}</span>}
      </span>
      {price && <span className="shrink-0 text-sm text-slate-600 tabular-nums">{price} €</span>}
    </li>
  )
}

function RestaurantCard({
  restaurant,
  dishes,
  onToggle,
}: {
  restaurant: Restaurant
  dishes: Dish[]
  onToggle: () => void
}) {
  return (
    <section className="rounded-lg border border-slate-200 p-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">{restaurant.name}</h2>
          <p className="text-sm text-slate-500">
            {[restaurant.campus, restaurant.lunch_hours].filter(Boolean).join(' · ')}
          </p>
        </div>
        <button
          type="button"
          className="text-xl leading-none"
          aria-pressed={restaurant.is_favourite}
          aria-label={restaurant.is_favourite ? `Remove ${restaurant.name} from favourites` : `Add ${restaurant.name} to favourites`}
          onClick={onToggle}
        >
          {restaurant.is_favourite ? '★' : '☆'}
        </button>
      </header>
      {dishes.length > 0 ? (
        <ul className="mt-2 divide-y divide-slate-100">
          {dishes.map((dish) => (
            <DishRow key={dish.id} dish={dish} />
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-500">No menu for this day.</p>
      )}
    </section>
  )
}

export function FoodPage() {
  const [date, setDate] = useState(today)
  const [showAll, setShowAll] = useState(false)
  const queryClient = useQueryClient()

  const restaurants = useQuery({
    queryKey: ['food', 'restaurants'],
    queryFn: async () => unwrap(await api.GET('/api/food/restaurants/')),
  })
  const dishes = useQuery({
    queryKey: ['food', 'dishes', date],
    queryFn: async () => unwrap(await api.GET('/api/food/dishes/', { params: { query: { date } } })),
  })
  const toggleFavourite = useMutation({
    mutationFn: async (restaurant: Restaurant) => {
      const options = { params: { path: { id: restaurant.id } } }
      const url = '/api/food/restaurants/{id}/favourite/'
      unwrap(restaurant.is_favourite ? await api.DELETE(url, options) : await api.PUT(url, options))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['food', 'restaurants'] }),
  })

  const all = restaurants.data ?? []
  const favourites = all.filter((restaurant) => restaurant.is_favourite)
  const visible = showAll || favourites.length === 0 ? all : favourites

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="rounded border px-3 py-1" onClick={() => setDate(shiftDate(date, -1))}>
          Previous day
        </button>
        <h1 className="min-w-56 text-center text-xl font-semibold">{formatDate(date)}</h1>
        <button type="button" className="rounded border px-3 py-1" onClick={() => setDate(shiftDate(date, 1))}>
          Next day
        </button>
        {favourites.length > 0 && (
          <label className="ml-auto flex items-center gap-2 text-sm">
            <input type="checkbox" checked={showAll} onChange={(event) => setShowAll(event.target.checked)} />
            Show all restaurants
          </label>
        )}
      </div>

      {(restaurants.isPending || dishes.isPending) && <p className="mt-4">Loading…</p>}
      {(restaurants.isError || dishes.isError) && <p className="mt-4">The menus could not be loaded.</p>}
      {toggleFavourite.isError && <p className="mt-4">The favourite could not be saved.</p>}
      {restaurants.isSuccess && all.length === 0 && (
        <p className="mt-4">No menus have been fetched yet. They are updated every three hours.</p>
      )}

      {dishes.isSuccess && (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {visible.map((restaurant) => (
            <RestaurantCard
              key={restaurant.id}
              restaurant={restaurant}
              dishes={dishes.data.filter((dish) => dish.restaurant === restaurant.id)}
              onToggle={() => toggleFavourite.mutate(restaurant)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
