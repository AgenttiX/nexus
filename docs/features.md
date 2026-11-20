# Features

```{note}
This page describes the design. The feature apps are implemented one at a time.
```

## News

One parser per site reads its RSS feed. An LLM selects the articles to read
from their titles, using a per-user prompt. By default it keeps politics (global
and Finnish), economy, technology and science, and skips celebrities and
sports. The day's summary is then produced in one of two modes:

1. All selected articles in one context, for cloud models with very large
   context windows.
2. One parallel session per article, then a session that summarises the
   summaries, for local models.

Full text comes from The Guardian's Open Platform API and from Yle's pages. HS,
Aamulehti and Kauppalehti contribute titles and leads.

## Finance

`finance` holds bank accounts (each with an IBAN) and transactions imported
from the CSV exports of online banks. `investments` holds assets and price
histories, which are shared between users, and each user's holdings.
Prices come from Yahoo Finance (through yfinance), CoinGecko and the European
Central Bank's exchange rates.

The CSV parsers and the import of PDF reports wait for example files.

## Time management

`timetracking` reads the SQLite files that ActivityWatch's `aw-sync` writes to
a synced directory. `calendars` shows calendars from their secret iCal
addresses.

## Sleep

One calendar can be marked as the sleep calendar. The dashboard and the MCP
tools give the range, mean, median and standard deviation of bedtime, wake-up
time, sleep duration and the jet lag between weekdays and weekends.

Parsing of the extra data that Sleep as Android writes to its events (rating,
location, duration, deep sleep, cycles, noise, snoring, comment and tags)
waits for an example calendar.

## Food

UniCafe menus, from `https://unicafe.fi/wp-json/swiss/v1/restaurants/`.
