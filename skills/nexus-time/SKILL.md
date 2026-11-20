---
name: nexus-time
description: Analyse how the user spends time on their computers and phones through the Nexus MCP server, from ActivityWatch data. Use when the user asks how much time they spent on a device, in an app, or on a given day or week.
---

# Time use with Nexus

Use the `time_summary` tool of the Nexus MCP server. If it is not listed, the
agent's token lacks the `timetracking` scope: say so, and do not estimate.

## Calling the tool

- `time_summary()` covers the last 7 days.
- `time_summary(start="2026-11-01", end="2026-11-30")` covers a period. Dates
  are `YYYY-MM-DD`, both ends included, at most 92 days.

To compare two periods, call the tool once for each.

## Reading the result

```text
Active time 2026-11-16..2026-11-17: 2:30 total, 1:15 per day
devices: laptop 2:30, phone 1:00
apps: Editor 1:30, Browser 1:00
days: Mon 11-16 2:30, Tue 11-17 0:00
```

- Times are hours:minutes.
- **Active** means an app had the focus while the user was at the device.
  Time away from the keyboard is left out on computers. Phones have no such
  detection, so their screen time counts in full.
- `per day` divides by every day of the period, including days without
  activity.
- The `devices` line appears only when there is more than one device.
- At most 15 apps are listed, most used first; the rest are counted in the
  total.
- An app is whatever the device reported, often the program's name. Time is
  not broken down by window title, website or project.

## Limits

- Data arrives when the user's devices synchronise, so the most recent hours
  may be missing. A device that has not synchronised is simply absent.
- The tool is read-only.

Report what the numbers show. Avoid judging the user's habits unless they ask
for an opinion.
