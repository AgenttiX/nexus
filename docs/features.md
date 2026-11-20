# Features

```{note}
This page describes the design. The feature apps are implemented one at a time.
```

## News

Nexus reads the RSS feeds of five news sites every 30 minutes and writes each
user a daily digest with a language model.

| Source | Read from it |
|---|---|
| Yle | Titles, leads and full text |
| The Guardian | Titles, leads and full text |
| Helsingin Sanomat | Titles and leads |
| Aamulehti | Titles and leads |
| Kauppalehti | Titles and leads |

The three Finnish newspapers are for subscribers, and Kauppalehti reserves
text and data mining rights, so their articles are not fetched. Full text is
fetched only for the articles chosen for a digest, and only from the source's
own site.

A digest covers the last 24 hours and is written in three steps:

1. **Selection.** The model gets the numbered headlines and the user's criteria
   and answers with the numbers to read. The default criteria keep politics
   (global and Finnish), the economy, technology and science, and skip
   celebrities and sports.
2. **Reading.** The full text of the chosen articles is fetched where allowed.
3. **Summary**, in the mode the user chose:
   - *All articles in one context*, for cloud models with very large context
     windows.
   - *One session per article, then a summary of the summaries*, for local
     models. `NEWS_PARALLEL_SESSIONS` sets how many sessions run at once.

Models are reached through a LiteLLM proxy (`LITELLM_BASE_URL`,
`LITELLM_API_KEY`). Each user can choose a model for selection and one for
summaries; `LLM_DEFAULT_MODEL` is used otherwise.

- **Web interface**: the News page shows digests and the settings (daily
  digest and its hour, sources, criteria, mode, models, language).
- **REST API**: `/api/news/profile/`, `/api/news/sources/`, `/api/news/digests/`
  and `POST /api/news/digests/generate/`.
- **MCP**: the `news_digest` tool (scope `news`).
- **Skill**: `skills/nexus-news/`.

## Finance

Bank accounts and their transactions. A user can have several accounts in
several banks; each has a name and an IBAN, which is validated.

Transactions come from files that the user exports from their online bank and
uploads on the Finances page. An import skips the entries that are already
stored, so overlapping exports can be imported safely. Each transaction can be
given one of the user's own categories.

```{warning}
**Bank formats are not implemented yet.** Each bank has its own CSV dialect,
and the importers will be written against example files. Until then only a
generic format exists: a comma-separated file with a header row and the
columns `date` (YYYY-MM-DD) and `amount` (negative for money leaving the
account), and optionally `counterparty`, `message` and `reference`. See
`apps/finance/importers.py` for how a bank is added.
```

- **Web interface**: the Finances page shows income, expenses and net for the
  last 30, 90 or 365 days, a chart by month, expenses by category, and the
  transactions with their categories. Accounts, categories and imports are
  managed there too.
- **REST API**: `/api/finance/accounts/` (with `POST …/{id}/import/`),
  `/api/finance/categories/`, `/api/finance/transactions/` and
  `/api/finance/summary/`.
- **MCP**: the `finance_summary` and `transactions` tools (scope `finance`).
- **Skill**: `skills/nexus-finance/`.

## Investments

Holdings of stocks, funds and cryptocurrencies, valued with fetched prices.
Assets, price histories and exchange rates are shared by all users, so the
history of an asset is stored once however many users hold it; only the
holdings belong to a user.

| Prices of | Source | Notes |
|---|---|---|
| Stocks, ETFs, funds | Yahoo Finance, through `yfinance` | Includes Nasdaq Helsinki (`.HE`). Unofficial; Yahoo's terms allow personal use. |
| Cryptocurrencies | CoinGecko | In euros. At most one year of history without a paid plan. `COINGECKO_API_KEY` is optional. |
| Exchange rates | Frankfurter | The European Central Bank's reference rates. |

Adding a holding of a new asset fetches up to two years of its daily closing
prices. After that, prices of all held assets are updated every four hours.

A holding is a quantity with an optional total cost. Trades are not recorded,
so the value chart applies today's quantities to past prices: it shows how
the present portfolio would have developed.

```{warning}
**Importing PDF reports is not implemented yet.** The readers will be written
against example reports; `apps/investments/pdf_import.py` describes the plan.
```

- **Web interface**: the Investments page shows the total value, the
  positions with price, value and gain, and the value chart.
- **REST API**: `/api/investments/holdings/` and `/api/investments/portfolio/`.
- **MCP**: the `portfolio` and `asset_prices` tools (scope `investments`).
- **Skill**: `skills/nexus-investments/`.

## Time management

### Calendars

Each user adds calendars by their secret iCalendar address (in Google Calendar:
Settings → the calendar → Integrate calendar → Secret address in iCal format).
Nexus reads every calendar every 30 minutes, expands recurring events, and
keeps events from the past 20 years to one year ahead.

- The address gives read access to the calendar, so it is stored encrypted and
  never returned by the API.
- The server fetches the address itself, so only `https` addresses that
  resolve to public servers are accepted, and redirects are not followed.
- **Web interface**: the Calendar page shows a week's events and manages the
  calendars.
- **REST API**: `/api/calendars/calendars/` and
  `/api/calendars/events/?start=…&end=…`.
- **MCP**: the `calendar_events` tool (scope `calendars`).
- **Skill**: `skills/nexus-calendar/`.

### ActivityWatch

Planned: `timetracking` reads the SQLite files that ActivityWatch's `aw-sync`
writes to a synced directory.

## Sleep

One calendar per user can be marked as the sleep calendar. Its timed events
become sleep records, rebuilt on every synchronisation. Its events are not
shown among ordinary calendar events.

For a period of wake-up dates, Nexus gives the range, mean, median and
standard deviation of:

- **Bedtime and wake-up time.** Clock times are averaged on the 24-hour circle,
  so that 23:00 and 01:00 average to midnight.
- **Sleep duration.**
- **Weekend jet lag**: per calendar week, the mean middle of sleep of nights
  ending on Saturday or Sunday minus that of the other nights.

Periods shorter than three hours are stored but counted as naps and left out
of the statistics.

- **Web interface**: the Sleep page shows the statistics and two charts for
  the last 30, 90 or 365 days.
- **REST API**: `/api/sleep/summary/` and `/api/sleep/records/`, both with
  `start`, `end` and an optional `tag`.
- **MCP**: the `sleep_summary` and `sleep_nights` tools (scope `sleep`).
- **Skill**: `skills/nexus-sleep/`.

### Sleep as Android

A sleep calendar can be marked as written by Sleep as Android. The record
fields for its extra data exist (rating, location, duration, deep sleep,
cycles, noise, snoring, comment and tags), and hashtags in a comment become
tags that records can be filtered by. **Reading that data from the events is
not implemented yet**: `apps/sleep/sleep_as_android.py` is a placeholder until
an example calendar shows the format.

## Food

Menus of the UniCafe student restaurants, read every three hours from the JSON
feed that UniCafe's own website uses
(`https://unicafe.fi/wp-json/swiss/v1/restaurants/`). The feed is undocumented,
so everything read from it is validated and entries that cannot be understood
are skipped.

- **Web interface**: the Food page shows a day's menus, the user's favourite
  restaurants first. Favourites are per user.
- **REST API**: `/api/food/restaurants/` and `/api/food/dishes/?date=YYYY-MM-DD`.
- **MCP**: the `food_menu` tool (scope `food`) returns a day's menus for the
  user's favourites or for a named restaurant.
- **Skill**: `skills/nexus-food/`.

To fetch menus right away instead of waiting for the schedule:

```bash
docker compose exec worker celery --app nexus call apps.food.tasks.fetch_menus
```
