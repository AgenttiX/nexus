"""The news sites that Nexus reads, and how each is read.

Every site is read through its RSS feed, which gives titles and leads. The full
text is fetched only from sites whose articles are free to read. The sites of
Sanoma (HS, Aamulehti) and Alma Media (Kauppalehti) are for subscribers, and
Kauppalehti reserves text and data mining rights, so those contribute titles
and leads only.
"""

import calendar
import datetime as dt
import html
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import feedparser
import httpx
import trafilatura
from django.utils.html import strip_tags

TIMEOUT_SECONDS = 30
USER_AGENT = "Mozilla/5.0 (compatible; Nexus news reader)"
MAX_TEXT_CHARS = 40_000


@dataclass(frozen=True)
class Source:
    """A news site."""

    key: str
    name: str
    feed_url: str
    domain: str
    language: str
    full_text: bool


SOURCES: dict[str, Source] = {
    source.key: source
    for source in (
        Source("yle", "Yle", "https://yle.fi/rss/uutiset/paauutiset", "yle.fi", "fi", full_text=True),
        Source(
            "hs", "Helsingin Sanomat", "https://www.hs.fi/rss/tuoreimmat.xml", "hs.fi", "fi", full_text=False
        ),
        Source(
            "aamulehti",
            "Aamulehti",
            "https://www.aamulehti.fi/rss/uutiset.xml",
            "aamulehti.fi",
            "fi",
            full_text=False,
        ),
        Source(
            "kauppalehti",
            "Kauppalehti",
            "https://feeds.kauppalehti.fi/rss/main",
            "kauppalehti.fi",
            "fi",
            full_text=False,
        ),
        Source(
            "guardian",
            "The Guardian",
            "https://www.theguardian.com/world/rss",
            "theguardian.com",
            "en",
            full_text=True,
        ),
    )
}


@dataclass(frozen=True)
class Entry:
    """An article as its feed describes it."""

    url: str
    title: str
    lead: str
    published_at: dt.datetime


def _get(url: str) -> httpx.Response:
    response = httpx.get(
        url, timeout=TIMEOUT_SECONDS, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    return response


def belongs_to(source: Source, url: str) -> bool:
    """Whether ``url`` is an https address on the site of ``source``."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    return parts.scheme == "https" and (host == source.domain or host.endswith("." + source.domain))


def fetch_entries(source: Source) -> list[Entry]:
    """Download the feed of ``source`` and return its usable entries."""
    return parse_feed(source, _get(source.feed_url).content)


def parse_feed(source: Source, data: bytes) -> list[Entry]:
    """Return the entries of a feed that have a title, a date and a link to the source's own site."""
    entries: list[Entry] = []
    for item in feedparser.parse(data).entries:
        url, title = str(item.get("link", "")), str(item.get("title", "")).strip()
        published = item.get("published_parsed")
        if not (title and isinstance(published, time.struct_time) and belongs_to(source, url)):
            continue
        entries.append(
            Entry(
                url=url,
                title=title,
                lead=html.unescape(strip_tags(str(item.get("summary", "")))).strip(),
                published_at=dt.datetime.fromtimestamp(calendar.timegm(published), tz=dt.UTC),
            ),
        )
    return entries


def fetch_text(source: Source, url: str) -> str:
    """Return the text of an article, or nothing for sites whose text Nexus does not read."""
    if not source.full_text or not belongs_to(source, url):
        return ""
    return extract_text(_get(url).text)


def extract_text(page: str) -> str:
    """Return the main text of an article page."""
    text = trafilatura.extract(page, include_comments=False, include_tables=False) or ""
    return text[:MAX_TEXT_CHARS]
