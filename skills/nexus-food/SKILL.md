---
name: nexus-food
description: Look up UniCafe student restaurant lunch menus through the Nexus MCP server. Use when the user asks what is for lunch, what a UniCafe restaurant serves on some day, or where to eat on campus.
---

# UniCafe menus with Nexus

Use the `food_menu` tool of the Nexus MCP server. If the tool is not listed,
the agent's token lacks the `food` scope: tell the user, and do not guess a menu.

## Calling the tool

- `food_menu()` gives today's menus of the user's favourite restaurants.
- `food_menu(date="2026-11-23")` gives another day. Dates are `YYYY-MM-DD`.
  Work out the date yourself for "tomorrow" or "on Friday".
- `food_menu(restaurant="exactum")` gives one restaurant. Part of the name is
  enough and case does not matter.

Menus are available for roughly the current and the next week. Weekends
usually have no menu.

## Reading the result

```text
Mon 2026-11-16
Exactum (Kumpula), lunch Mon–Fri 11.00-14.00, Sat–Sun Closed
- Chipotle sweet potato soup & avocado foam [Vegaanilounas, G KELA Veg Ilmastovalinta] 3.10 €
```

- The first line is the date. Each restaurant starts with its name, campus
  and lunch hours.
- In the brackets: the lunch type in Finnish (`Vegaanilounas` vegan lunch,
  `Lounas` lunch, `Keitto` soup, `Jälkiruoka` dessert, `Lisäke` side dish,
  `Päivän erikoinen` special of the day, `Tiedote` a notice rather than a
  dish), then diet codes.
- Diet codes: `G` gluten-free, `L` lactose-free, `VL` low lactose, `M`
  milk-free, `Veg` vegan, `KELA` meal eligible for the student meal subsidy,
  `Ilmastovalinta` climate-friendly choice.
- The price is the student price in euros.

## If there are no favourites

The tool answers with the list of restaurant names instead of menus. Ask the
user which restaurant they mean, or pick the one they named, and call the tool
again with `restaurant`. Favourites are chosen in the Nexus web interface on
the Food page.

## Answering

Keep the answer short: restaurant, then dishes with prices. Mention diet codes
only when the user asked about a diet or allergy. Do not state allergens
beyond what the tool returned.
