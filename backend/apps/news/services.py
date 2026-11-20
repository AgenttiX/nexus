"""Fetching news and writing digests of it."""

import asyncio
import datetime as dt
import json
import re

from django.conf import settings
from django.utils import timezone
from openai import AsyncOpenAI

from apps.accounts.models import User
from apps.llm import client as llm
from apps.news.models import Article, Digest, DigestArticle, Mode, NewsProfile, Status
from apps.news.sources import SOURCES, fetch_entries, fetch_text

WINDOW = dt.timedelta(hours=24)
#: Upper bound for the text sent in single mode, so that even a huge day fits a million-token context.
SINGLE_MODE_MAX_CHARS = 2_000_000
ERROR_MAX_CHARS = 300

SELECTION_SCHEMA = {
    "type": "object",
    "properties": {"selected": {"type": "array", "items": {"type": "integer"}}},
    "required": ["selected"],
    "additionalProperties": False,
}


def fetch_articles() -> int:
    """Read the feed of every source and store new articles. Returns how many were new.

    A source that cannot be read is skipped, so that one broken feed does not
    stop the others.
    """
    created = 0
    for source in SOURCES.values():
        try:
            entries = fetch_entries(source)
        except Exception:  # noqa: BLE001, S112 - the next run retries
            continue
        for entry in entries:
            _, is_new = Article.objects.get_or_create(
                url=entry.url,
                defaults={
                    "source": source.key,
                    "title": entry.title[:500],
                    "lead": entry.lead,
                    "published_at": entry.published_at,
                },
            )
            created += is_new
    return created


def profile_for(user: User) -> NewsProfile:
    """Return the news settings of ``user``, creating them with defaults on first use."""
    return NewsProfile.objects.get_or_create(user=user)[0]


def start_digest(user: User) -> Digest:
    """Create, or reset, today's digest of ``user`` so that it can be written."""
    profile = profile_for(user)
    digest, _ = Digest.objects.update_or_create(
        user=user,
        date=timezone.localdate(),
        defaults={"status": Status.PENDING, "mode": profile.mode, "summary": "", "error": ""},
    )
    digest.selected.all().delete()
    return digest


def write_digest(digest: Digest) -> None:
    """Select articles of the last 24 hours and summarise them. Failures are recorded on the digest."""
    try:
        _write_digest(digest)
    except Exception as error:  # noqa: BLE001 - shown to the user, who can try again
        digest.status = Status.FAILED
        digest.error = f"{type(error).__name__}: {error}"[:ERROR_MAX_CHARS]
        digest.save(update_fields=["status", "error"])


def _write_digest(digest: Digest) -> None:
    profile = profile_for(digest.user)
    now = timezone.now()
    candidates = list(
        Article.objects.filter(
            source__in=profile.sources, published_at__gt=now - WINDOW, published_at__lte=now
        ).order_by("published_at"),
    )
    if not candidates:
        _finish(digest, "No articles were published by the selected sources in the last 24 hours.")
        return

    selection_model = profile.selection_model or llm.default_model()
    summary_model = profile.summary_model or llm.default_model()
    api = llm.client()

    answer = asyncio.run(
        llm.complete(
            api, selection_model, _selection_prompt(profile), _headlines(candidates), SELECTION_SCHEMA
        )
    )
    chosen = [candidates[index] for index in parse_selection(answer, len(candidates))[: profile.max_articles]]
    if not chosen:
        _finish(digest, "None of the articles of the last 24 hours matched your criteria.")
        return

    for article in chosen:
        _ensure_text(article)
    selected = DigestArticle.objects.bulk_create(
        DigestArticle(digest=digest, article=article, position=position)
        for position, article in enumerate(chosen)
    )

    if digest.mode == Mode.SINGLE:
        summary = _ask(summary_model, _digest_prompt(profile), _full_texts(chosen))
    else:
        summaries = asyncio.run(_summarize_each(summary_model, profile, chosen))
        for item, text in zip(selected, summaries, strict=True):
            item.summary = text
        DigestArticle.objects.bulk_update(selected, ["summary"])
        combined = "\n\n".join(
            f"[{SOURCES[article.source].name}] {article.title}\n{text}"
            for article, text in zip(chosen, summaries, strict=True)
        )
        summary = _ask(summary_model, _digest_prompt(profile), combined)
    _finish(digest, summary.strip())


def _finish(digest: Digest, summary: str) -> None:
    digest.status = Status.DONE
    digest.summary = summary
    digest.save(update_fields=["status", "summary"])


def _ensure_text(article: Article) -> None:
    """Fetch the full text of an article once, where the source allows it. Failures leave the lead."""
    if article.text:
        return
    try:
        article.text = fetch_text(SOURCES[article.source], article.url)
    except Exception:  # noqa: BLE001 - the lead is used instead
        return
    if article.text:
        article.save(update_fields=["text"])


def _ask(model: str, system: str, user: str, json_schema: dict[str, object] | None = None) -> str:
    """Ask a model one question and wait for the answer."""

    async def ask() -> str:
        # A client belongs to the event loop it was created in, so each run gets its own.
        async with llm.client() as api:
            return await llm.complete(api, model, system, user, json_schema)

    return asyncio.run(ask())


async def _summarize_each(model: str, profile: NewsProfile, articles: list[Article]) -> list[str]:
    """Summarise each article in its own session, a few at a time."""
    limit = asyncio.Semaphore(settings.NEWS_PARALLEL_SESSIONS)

    async def one(api: AsyncOpenAI, article: Article) -> str:
        async with limit:
            text = await llm.complete(
                api, model, _article_prompt(profile), f"{article.title}\n\n{article.content}"
            )
        return text.strip()

    async with llm.client() as api:
        return list(await asyncio.gather(*(one(api, article) for article in articles)))


def parse_selection(answer: str, count: int) -> list[int]:
    """Return the zero-based indices that a model selected from ``count`` numbered headlines.

    The model is asked for JSON, but small models do not always comply, so any
    numbers in the answer are accepted. Invalid and repeated numbers are dropped.
    """
    numbers: list[int] = []
    match = re.search(r"\{.*\}", answer, re.DOTALL)
    if match:
        try:
            selected = json.loads(match.group(0)).get("selected", [])
        except ValueError, AttributeError:
            selected = []
        if isinstance(selected, list):
            numbers = [number for number in selected if isinstance(number, int)]
    if not numbers:
        numbers = [int(number) for number in re.findall(r"\d+", answer)]
    return list(dict.fromkeys(number - 1 for number in numbers if 1 <= number <= count))


def _headlines(articles: list[Article]) -> str:
    return "\n".join(
        f"{number}. [{SOURCES[article.source].name}] {article.title}"
        for number, article in enumerate(articles, 1)
    )


def _full_texts(articles: list[Article]) -> str:
    parts: list[str] = []
    used = 0
    for article in articles:
        part = f"## [{SOURCES[article.source].name}] {article.title}\n{article.content}"
        if used + len(part) > SINGLE_MODE_MAX_CHARS:
            break
        parts.append(part)
        used += len(part)
    return "\n\n".join(parts)


def _selection_prompt(profile: NewsProfile) -> str:
    return (
        "You choose which news articles a reader should read today, from a numbered list of headlines.\n"
        f"The reader's criteria: {profile.criteria}\n"
        f"Choose at most {profile.max_articles} articles. When several headlines cover the same event, "
        "choose the most informative one.\n"
        'Answer only with JSON of the form {"selected": [numbers]}.'
    )


def _article_prompt(profile: NewsProfile) -> str:
    return (
        f"Summarise the news article in {profile.language} in at most five sentences. "
        "State the facts and figures that matter and leave out everything else. "
        "Use only what the article says."
    )


def _digest_prompt(profile: NewsProfile) -> str:
    return (
        f"Write a briefing of today's news in {profile.language} from the material below. "
        "Group related stories under short plain-text headings, most important first. "
        "Be concise and factual, use only what the material says, and name the source in brackets "
        "after each story. Do not use Markdown formatting."
    )


def latest_digest(user: User, date: dt.date | None = None) -> Digest | None:
    """Return the finished digest of ``user`` for ``date``, or their newest one."""
    digests = Digest.objects.for_user(user).filter(status=Status.DONE)
    if date is not None:
        digests = digests.filter(date=date)
    return digests.order_by("-date").first()


def digest_text(user: User, date: dt.date | None = None, *, with_articles: bool = False) -> str:
    """Return a digest as text for an AI agent, optionally with the list of its articles."""
    digest = latest_digest(user, date)
    if digest is None:
        return f"No news digest for {date}." if date else "No news digest has been written yet."
    lines = [f"News digest {digest.date}", digest.summary]
    if with_articles:
        lines.append("\nArticles:")
        lines += [
            f"- [{SOURCES[item.article.source].name}] {item.article.title} {item.article.url}"
            for item in digest.selected.select_related("article")
        ]
    return "\n".join(lines)
