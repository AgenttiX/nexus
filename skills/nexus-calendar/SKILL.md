---
name: nexus-calendar
description: Read the user's calendar events through the Nexus MCP server. Use when the user asks what is on their calendar, when they are free or busy, or about upcoming or past events.
---

# Calendar events with Nexus

Use the `calendar_events` tool of the Nexus MCP server. If it is not listed,
the agent's token lacks the `calendars` scope: say so, and do not guess.

## Calling the tool

- `calendar_events()` gives today and the six days after it.
- `calendar_events(start="2026-11-16", end="2026-11-22")` gives a period.
  Dates are `YYYY-MM-DD`, both ends included, at most 62 days apart.

Ask for the shortest period that answers the question. Long results are cut
off after 100 events with a note; narrow the period if that happens.

## Reading the result

```text
Mon 2026-11-16
- 10:00-11:00 Planning meeting @ Room 1 [Work]
Thu 2026-11-19
- all day Holiday [Work]
```

Each day with events has a heading. An event line gives the local time,
title, place after `@` when there is one, and the calendar's name in brackets.
Days without events are not listed, so a missing day is a free day.

The tool is read-only: it cannot create or change events. Events of the sleep
calendar are not included; use the sleep tools for those.
