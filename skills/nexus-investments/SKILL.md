---
name: nexus-investments
description: Look up the user's investment holdings and asset prices through the Nexus MCP server. Use when the user asks what their portfolio is worth, how a holding has done, or for the recent prices of an asset they hold.
---

# Investments with Nexus

Two tools of the Nexus MCP server read the user's holdings. If they are not
listed, the agent's token lacks the `investments` scope: say so, and do not
guess values.

- `portfolio()` lists every holding with its latest price, its value in euros
  and its gain, and the total.
- `asset_prices(symbol, days)` gives the daily closing prices of one asset for
  the last `days` (default 30, at most 365). Use the symbol exactly as
  `portfolio` shows it.

## Reading `portfolio`

```text
Portfolio total 750.00 EUR
quantity symbol (name): price, value EUR, gain EUR
100 NOKIA.HE (Nokia Corporation): 7.5 EUR on 2026-11-20, 750.00, +250.00
```

- The price is in the asset's own currency, with the day it is from. Prices
  are daily closes fetched a few times a day, not live quotes: mention the
  date when it matters.
- The value is converted to euros with the European Central Bank's rate.
- The gain is the value minus what the user said the holding cost. `-` means
  the user gave no cost; `?` means no price or exchange rate is known yet.

## Limits

- Holdings are quantities that the user entered; trades and dividends are not
  recorded, so returns over time cannot be computed exactly.
- Only assets that some user holds have prices. `asset_prices` names the known
  assets when asked for an unknown one.
- The tools are read-only.

State facts from the data. Do not recommend buying or selling: say that you
are not a licensed financial adviser if asked for advice.
