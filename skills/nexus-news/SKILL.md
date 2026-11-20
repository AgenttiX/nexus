---
name: nexus-news
description: Read the user's daily news digest through the Nexus MCP server. Use when the user asks what is in the news, what happened today or on a given day, or wants a briefing or the sources behind a news story.
---

# News digests with Nexus

Nexus writes the user a digest of each day's news, chosen by the user's own
criteria from Yle, Helsingin Sanomat, Aamulehti, Kauppalehti and The Guardian.
Use the `news_digest` tool of the Nexus MCP server to read it. If the tool is
not listed, the agent's token lacks the `news` scope: say so, and do not make
up news.

## Calling the tool

- `news_digest()` gives the newest digest.
- `news_digest(date="2026-11-20")` gives the digest of a day (`YYYY-MM-DD`).
- `news_digest(articles=true)` adds the list of articles behind the digest,
  with their sources and links. Ask for it only when the user wants sources
  or links, as it makes the answer longer.

## Reading the result

The first line is `News digest <date>`; check that it is the day the user
means, as the newest digest may be yesterday's. The rest is the briefing, with
the source of each story in brackets.

The tool reads what has already been written; it cannot write a new digest or
search for other news. If there is no digest for a day, say so. The user can
start one on the News page of the Nexus web interface.

## Answering

Answer the question from the digest. For "what's in the news", give the main
points in a few lines rather than repeating the whole text. Keep the source
names. Do not add facts that are not in the digest.

Helsingin Sanomat, Aamulehti and Kauppalehti contribute only headlines and
leads, so stories from them carry less detail.
