---
name: nexus-sleep
description: Analyse the user's sleep through the Nexus MCP server. Use when the user asks how they have slept, about bedtimes, wake-up times, sleep duration, sleep regularity or weekend jet lag, or wants sleep compared between periods.
---

# Sleep analysis with Nexus

Two tools of the Nexus MCP server read the user's sleep calendar. If they are
not listed, the agent's token lacks the `sleep` scope: say so, and do not
estimate.

- `sleep_summary(start, end, tag)` gives statistics for a period. Start here.
- `sleep_nights(start, end, tag)` lists the individual records. Use it only
  when the user asks about particular nights or you need to see outliers; it
  costs one line per night.

All arguments are optional. Dates are `YYYY-MM-DD` and mean **wake-up dates**:
the night from Sunday to Monday belongs to Monday. Without dates the tools
cover the last 30 days. `tag` keeps only records with that hashtag.

## Reading `sleep_summary`

```text
Sleep 2026-10-23..2026-11-21: 30 nights
bedtime: mean 23:44, median 23:50, range 22:48 to 00:53, sd 0:36
wake-up: mean 07:14, median 07:02, range 05:08 to 10:40, sd 1:14
duration: mean 7:33, median 7:29, range 5:56 to 9:52, sd 0:54
weekend jet lag (5 weeks): mean +1:37, median +1:46, range +0:45 to +2:29, sd 0:48
```

- Bedtime and wake-up are clock times, averaged correctly across midnight.
  `sd` is the standard deviation as hours:minutes; a smaller value means a
  more regular rhythm.
- Duration is time asleep as hours:minutes.
- Weekend jet lag is how much later the middle of sleep falls on nights ending
  on Saturday or Sunday than on other nights of the same week. `+1:37` means
  about an hour and a half later at weekends. It needs at least one week with
  both kinds of nights.
- Periods of sleep shorter than three hours are naps. They appear in
  `sleep_nights` but are left out of these statistics.

## Comparing periods

Call `sleep_summary` once per period and compare the lines, for example this
month against the previous one. Do not fetch all nights to compute statistics
yourself.

## Answering

Lead with the answer to the question asked, with the numbers that support it.
Describe patterns; do not diagnose. For health concerns, suggest talking to a
professional.
