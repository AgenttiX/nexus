---
name: nexus-finance
description: Analyse the user's bank transactions through the Nexus MCP server. Use when the user asks about their spending, income, expenses by category or month, or about particular payments.
---

# Personal finances with Nexus

Two tools of the Nexus MCP server read the bank transactions that the user has
imported. If they are not listed, the agent's token lacks the `finance` scope:
say so, and do not estimate.

- `finance_summary(start, end)` gives totals for a period. Start here.
- `transactions(start, end, search)` lists individual transactions. Use it for
  questions about particular payments, with a `search` text whenever possible.

Dates are `YYYY-MM-DD`, both ends included. Without dates the tools cover the
last 30 days. Amounts are in euros.

## Reading `finance_summary`

```text
Finances 2026-10-01..2026-11-30 (EUR)
income 2500.00, expenses 904.30, net +1595.70
expenses by category: Housing 800.00, Uncategorised 104.30
month, income, expenses
2026-10 2500.00 891.80
2026-11 0.00 12.50
```

Expenses are shown as positive numbers. Categories are the user's own;
`Uncategorised` is everything the user has not classified, which can be most
of the spending, so do not read category shares as complete.

## Reading `transactions`

```text
date, amount EUR, counterparty, category, message
2026-10-15 -800.00 Landlord [Housing] Rent October
```

Money leaving the account is negative. At most the 50 newest matching
transactions are shown; narrow the dates or add a search text when the result
says it was cut. `search` matches the counterparty, the message and the
category name.

## Limits

- The data is only as recent as the user's latest import; there is no live
  connection to the bank and no account balance.
- For totals, use `finance_summary` rather than adding up transactions.
- The tools are read-only.

Give figures with their period. Describe what the data shows; do not give
investment or tax advice.
