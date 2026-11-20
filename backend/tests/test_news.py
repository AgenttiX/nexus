"""Tests for the news app."""

import datetime as dt
import json
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import httpx2
import pytest
import respx
from django.conf import settings as django_settings
from django.utils import timezone
from openai import AsyncOpenAI
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient
from starlette.testclient import TestClient

from apps.accounts.models import AgentToken, User
from apps.llm import client as llm
from apps.news import services, sources, tasks
from apps.news.models import DEFAULT_CRITERIA, Article, Digest, DigestArticle, Mode, NewsProfile, Status
from apps.news.sources import SOURCES
from tests.mcp_helpers import call, text, tool_names

FEED = (Path(__file__).parent / "data" / "news_feed.xml").read_bytes()
PAGE = (
    "<html><body><article><h1>Parliament passes the budget</h1>"
    + "<p>The full story of the budget vote, told at length for the reader.</p>" * 8
    + "</article></body></html>"
)
YLE = SOURCES["yle"]

Reply = Callable[[dict[str, object]], str]


def article(number: int, source: str = "yle", **fields: object) -> Article:
    defaults: dict[str, object] = {
        "source": source,
        "url": f"https://{SOURCES[source].domain}/a/{number}",
        "title": f"Headline {number}",
        "lead": f"Lead {number}.",
        "published_at": timezone.now() - dt.timedelta(hours=number),
    }
    return Article.objects.create(**{**defaults, **fields})


def fake_llm(monkeypatch: pytest.MonkeyPatch, respond: Callable[[httpx2.Request], httpx2.Response]) -> None:
    """Route the calls of the OpenAI client to ``respond`` instead of a LiteLLM proxy."""

    def client() -> AsyncOpenAI:
        transport = httpx2.MockTransport(respond)
        return AsyncOpenAI(
            base_url="http://litellm.test/v1",
            api_key="test",
            http_client=httpx2.AsyncClient(transport=transport),
            max_retries=0,
        )

    monkeypatch.setattr(llm, "client", client)


def answer(content: str | None) -> httpx2.Response:
    return httpx2.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


@pytest.fixture
def chat(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, object]]]:
    """A fake LiteLLM proxy. Selects headlines 1 and 3, and echoes what it was asked to summarise.

    Yields the requests it received. The feed and the article pages of yle.fi are served too.
    """
    requests: list[dict[str, object]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        requests.append(body)
        system, user = (message["content"] for message in body["messages"])
        if "choose which news articles" in system:
            return answer('{"selected": [1, 3]}')
        if "Summarise the news article" in system:
            return answer(f" Summary of: {user.splitlines()[0]} ")
        return answer(f"BRIEFING\n{user}")

    fake_llm(monkeypatch, respond)
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith="https://yle.fi/a/").mock(return_value=httpx.Response(200, text=PAGE))
        router.get(YLE.feed_url).mock(return_value=httpx.Response(200, content=FEED))
        yield requests


# Sources


def test_feed_entries_are_cleaned_and_filtered() -> None:
    entries = sources.parse_feed(YLE, FEED)
    assert [(entry.url, entry.title) for entry in entries] == [
        ("https://yle.fi/a/74-1", "Parliament passes the budget"),
        ("https://yle.fi/a/74-2", "Singer announces a tour"),
    ]
    assert entries[0].lead == "The vote was close & late."
    assert entries[0].published_at == dt.datetime(2026, 11, 20, 14, 28, 1, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://yle.fi/a/1", True),
        ("https://www.yle.fi/a/1", True),
        ("http://yle.fi/a/1", False),
        ("https://notyle.fi/a/1", False),
        ("https://yle.fi.example.com/a/1", False),
    ],
)
def test_links_must_stay_on_the_source_site(url: str, expected: bool) -> None:  # noqa: FBT001
    assert sources.belongs_to(YLE, url) is expected


@respx.mock
def test_text_is_fetched_only_where_allowed() -> None:
    route = respx.get("https://yle.fi/a/1").mock(return_value=httpx.Response(200, text=PAGE))
    assert "full story of the budget vote" in sources.fetch_text(YLE, "https://yle.fi/a/1")
    assert sources.fetch_text(SOURCES["hs"], "https://www.hs.fi/a/1") == ""
    assert sources.fetch_text(YLE, "https://elsewhere.example.com/a/1") == ""
    assert route.call_count == 1
    assert sources.extract_text("<html><body></body></html>") == ""


@respx.mock
def test_fetch_stores_new_articles_and_survives_a_broken_feed(db: None) -> None:
    respx.get(YLE.feed_url).mock(return_value=httpx.Response(200, content=FEED))
    for key, source in SOURCES.items():
        if key != "yle":
            respx.get(source.feed_url).mock(return_value=httpx.Response(503))
    assert services.fetch_articles() == 2
    assert services.fetch_articles() == 0
    stored = Article.objects.get(url="https://yle.fi/a/74-1")
    assert (stored.source, str(stored), stored.content) == (
        "yle",
        "Parliament passes the budget",
        stored.lead,
    )
    assert tasks.fetch_articles.apply().get() == 0


# Selection parsing


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ('{"selected": [1, 3]}', [0, 2]),
        ('Sure! ```json\n{"selected": [3, 3, 9, 0, 2]}\n```', [2, 1]),
        ("I would read 2 and 4.", [1, 3]),
        ('{"selected": "all"} 1', [0]),
        ('{"selected": [oops]} 2', [1]),
        ("[1] {broken", [0]),
        ("none", []),
    ],
)
def test_selection_answers_are_read_leniently(answer: str, expected: list[int]) -> None:
    assert services.parse_selection(answer, 4) == expected


# Digests


def test_parallel_digest_summarises_each_article_then_all(user: User, chat: list[dict[str, object]]) -> None:
    first, _, third = article(3), article(2), article(1, source="hs")
    article(30)
    digest = services.start_digest(user)
    services.write_digest(digest)

    assert (digest.status, digest.error, digest.mode) == (Status.DONE, "", Mode.PARALLEL)
    selected = list(digest.selected.all())
    assert [item.article for item in selected] == [first, third]
    assert [item.summary for item in selected] == ["Summary of: Headline 3", "Summary of: Headline 1"]
    assert str(selected[0]) == "Headline 3"
    assert digest.summary == (
        "BRIEFING\n[Yle] Headline 3\nSummary of: Headline 3\n\n"
        "[Helsingin Sanomat] Headline 1\nSummary of: Headline 1"
    )
    first.refresh_from_db()
    third.refresh_from_db()
    assert "full story of the budget vote" in first.text
    assert third.text == ""

    selection = chat[0]
    assert selection["model"] == "test-model"
    assert selection["response_format"]["type"] == "json_schema"  # type: ignore[index]
    system, headlines = (message["content"] for message in selection["messages"])  # type: ignore[union-attr]
    assert DEFAULT_CRITERIA in system
    assert headlines == "1. [Yle] Headline 3\n2. [Yle] Headline 2\n3. [Helsingin Sanomat] Headline 1"
    assert len(chat) == 4


def test_single_digest_sends_all_texts_at_once(user: User, chat: list[dict[str, object]]) -> None:
    NewsProfile.objects.create(user=user, mode=Mode.SINGLE, summary_model="big-model", language="Finnish")
    article(3, text="Stored text.")
    article(2)
    article(1, source="hs")
    digest = services.start_digest(user)
    services.write_digest(digest)

    assert digest.status == Status.DONE
    assert digest.summary == (
        "BRIEFING\n## [Yle] Headline 3\nStored text.\n\n## [Helsingin Sanomat] Headline 1\nLead 1."
    )
    assert len(chat) == 2
    assert (chat[0]["model"], chat[1]["model"]) == ("test-model", "big-model")
    assert "in Finnish" in chat[1]["messages"][0]["content"]  # type: ignore[index]
    assert not DigestArticle.objects.exclude(summary="").exists()


def test_single_digest_stops_before_the_context_overflows(
    user: User,
    chat: list[dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    NewsProfile.objects.create(user=user, mode=Mode.SINGLE)
    article(3, text="x" * 50)
    article(2)
    article(1, text="y" * 50)
    monkeypatch.setattr(services, "SINGLE_MODE_MAX_CHARS", 100)
    digest = services.start_digest(user)
    services.write_digest(digest)
    assert digest.summary == "BRIEFING\n## [Yle] Headline 3\n" + "x" * 50


def test_digest_respects_sources_limits_and_the_time_window(
    user: User, chat: list[dict[str, object]]
) -> None:
    NewsProfile.objects.create(user=user, sources=["hs"], max_articles=1)
    article(1)
    kept = article(2, source="hs")
    article(3, source="hs")
    article(4, source="hs")
    article(30, source="hs")
    digest = services.start_digest(user)
    services.write_digest(digest)
    assert chat[0]["messages"][1]["content"].count("\n") == 2  # type: ignore[index]
    assert [item.article for item in digest.selected.all()] == [Article.objects.get(title="Headline 4")]
    assert kept not in digest.articles.all()


def test_digest_explains_days_without_news_or_matches(
    user: User,
    chat: list[dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    digest = services.start_digest(user)
    services.write_digest(digest)
    assert (digest.status, digest.summary) == (
        Status.DONE,
        "No articles were published by the selected sources in the last 24 hours.",
    )
    assert chat == []

    article(1)
    digest = services.start_digest(user)
    fake_llm(monkeypatch, lambda request: answer(None))
    services.write_digest(digest)
    assert digest.summary == "None of the articles of the last 24 hours matched your criteria."


def test_article_without_readable_page_falls_back_to_its_lead(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    article(1)

    def respond(request: httpx2.Request) -> httpx2.Response:
        user_message = json.loads(request.content)["messages"][1]["content"]
        return answer('{"selected": [1]}' if user_message.startswith("1. ") else user_message)

    fake_llm(monkeypatch, respond)
    with respx.mock:
        respx.get("https://yle.fi/a/1").mock(return_value=httpx.Response(500))
        digest = services.start_digest(user)
        services.write_digest(digest)
    assert digest.selected.get().summary == "Headline 1\n\nLead 1."

    with respx.mock:
        respx.get("https://yle.fi/a/1").mock(return_value=httpx.Response(200, text="<html></html>"))
        digest = services.start_digest(user)
        services.write_digest(digest)
    assert Article.objects.get().text == ""


def test_failed_digest_records_the_reason(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    article(1)
    fake_llm(monkeypatch, lambda request: httpx2.Response(401, json={"error": {"message": "bad key"}}))
    digest = services.start_digest(user)
    services.write_digest(digest)
    assert digest.status == Status.FAILED
    assert digest.error.startswith("AuthenticationError")
    assert len(digest.error) <= services.ERROR_MAX_CHARS


def test_missing_llm_configuration_is_reported(user: User, settings: Settings) -> None:
    article(1)
    settings.LLM_DEFAULT_MODEL = ""
    digest = services.start_digest(user)
    services.write_digest(digest)
    assert (digest.status, digest.error.split(":")[0]) == (Status.FAILED, "LLMNotConfiguredError")

    settings.LLM_DEFAULT_MODEL = "test-model"
    settings.LITELLM_BASE_URL = ""
    with pytest.raises(llm.LLMNotConfiguredError):
        llm.client()
    settings.LITELLM_BASE_URL = "http://litellm.test/v1"
    assert str(llm.client().base_url) == "http://litellm.test/v1/"
    assert django_settings.NEWS_PARALLEL_SESSIONS == 4


def test_starting_again_replaces_todays_digest(user: User, chat: list[dict[str, object]]) -> None:
    article(1)
    first = services.start_digest(user)
    services.write_digest(first)
    second = services.start_digest(user)
    assert second.pk == first.pk
    assert (second.status, second.summary, second.selected.count()) == (Status.PENDING, "", 0)
    assert str(second) == f"News digest {timezone.localdate()}"
    assert str(services.profile_for(user)) == "News profile of alice"


# Tasks


def test_digest_task_can_fetch_first(user: User, chat: list[dict[str, object]]) -> None:
    digest = services.start_digest(user)
    assert tasks.write_digest.apply(args=(digest.pk,), kwargs={"fetch_first": True}).get() == "done"
    assert Article.objects.count() == 2
    assert tasks.write_digest.apply(args=(0,)).get() == "failed"


def test_due_digests_are_started_once_at_the_chosen_hour(
    user: User,
    other_user: User,
    chat: list[dict[str, object]],
) -> None:
    hour = timezone.localtime().hour
    NewsProfile.objects.create(user=user, enabled=True, digest_hour=hour)
    NewsProfile.objects.create(user=other_user, enabled=True, digest_hour=(hour + 1) % 24)
    carol = User.objects.create_user("carol")
    NewsProfile.objects.create(user=carol, enabled=True, digest_hour=hour)
    NewsProfile.objects.create(user=User.objects.create_user("dave"), enabled=False, digest_hour=hour)

    assert tasks.write_due_digests.apply().get() == 2
    assert tasks.write_due_digests.apply().get() == 0
    assert set(Digest.objects.values_list("user__username", flat=True)) == {"alice", "carol"}


# REST API


def test_news_api_requires_login(api_client: APIClient) -> None:
    for path in ("profile", "sources", "digests"):
        assert api_client.get(f"/api/news/{path}/").status_code == 403


def test_profile_has_defaults_and_can_be_changed(user_client: APIClient, other_client: APIClient) -> None:
    profile = user_client.get("/api/news/profile/").json()
    assert (profile["enabled"], profile["mode"], profile["criteria"]) == (False, "parallel", DEFAULT_CRITERIA)
    assert profile["sources"] == ["yle", "hs", "aamulehti", "kauppalehti", "guardian"]

    changed = user_client.patch("/api/news/profile/", {"sources": ["yle"], "mode": "single"}, format="json")
    assert (changed.status_code, changed.json()["sources"]) == (200, ["yle"])
    assert other_client.get("/api/news/profile/").json()["mode"] == "parallel"

    for bad in ({"sources": ["tabloid"]}, {"sources": []}, {"digest_hour": 24}, {"max_articles": 0}):
        assert user_client.patch("/api/news/profile/", bad, format="json").status_code == 400


def test_sources_are_listed(user_client: APIClient) -> None:
    listed = user_client.get("/api/news/sources/").json()
    assert listed[0] == {"key": "yle", "name": "Yle", "language": "fi", "full_text": True}
    assert {item["key"] for item in listed if not item["full_text"]} == {"hs", "aamulehti", "kauppalehti"}


def test_digest_can_be_generated_and_read(user_client: APIClient, chat: list[dict[str, object]]) -> None:
    Article.objects.create(source="yle", url="https://yle.fi/a/9", title="Now", published_at=timezone.now())

    started = user_client.post("/api/news/digests/generate/")
    assert (started.status_code, started.json()["status"]) == (202, "pending")

    digest = user_client.get(f"/api/news/digests/{started.json()['id']}/").json()
    assert (digest["status"], digest["mode"]) == ("done", "parallel")
    # The fixture feed has fixed dates, so only the article created above is certain to be recent.
    summaries = {item["article"]["title"]: item["summary"] for item in digest["selected"]}
    assert summaries["Now"] == "Summary of: Now"
    assert len(user_client.get("/api/news/digests/").json()) == 1


def test_digests_are_hidden_from_other_users(user: User, other_client: APIClient) -> None:
    digest = Digest.objects.create(user=user, date=timezone.localdate(), mode=Mode.SINGLE, status=Status.DONE)
    assert other_client.get("/api/news/digests/").json() == []
    assert other_client.get(f"/api/news/digests/{digest.pk}/").status_code == 404


# MCP


def test_digest_text(user: User, other_user: User) -> None:
    assert services.digest_text(user) == "No news digest has been written yet."
    day = dt.date(2026, 11, 20)
    digest = Digest.objects.create(
        user=user, date=day, mode=Mode.SINGLE, status=Status.DONE, summary="All calm."
    )
    Digest.objects.create(user=user, date=dt.date(2026, 11, 21), mode=Mode.SINGLE, status=Status.FAILED)
    DigestArticle.objects.create(digest=digest, article=article(1), position=0)

    assert services.digest_text(user) == "News digest 2026-11-20\nAll calm."
    assert services.digest_text(user, day, with_articles=True) == (
        "News digest 2026-11-20\nAll calm.\n\nArticles:\n- [Yle] Headline 1 https://yle.fi/a/1"
    )
    assert services.digest_text(user, dt.date(2026, 11, 19)) == "No news digest for 2026-11-19."
    assert services.digest_text(other_user) == "No news digest has been written yet."


@pytest.mark.django_db(transaction=True)
def test_news_tool(server: TestClient, user: User) -> None:
    Digest.objects.create(
        user=user,
        date=dt.date(2026, 11, 20),
        mode=Mode.SINGLE,
        status=Status.DONE,
        summary="All calm.",
    )
    assert "news_digest" not in tool_names(
        server, AgentToken.objects.create_token(user, "other", {"food": "read"})[1]
    )
    token = AgentToken.objects.create_token(user, "news agent", {"news": "read"})[1]
    assert text(call(server, token, "news_digest")) == "News digest 2026-11-20\nAll calm."
    assert text(call(server, token, "news_digest", {"date": "2026-11-20", "articles": True})).endswith(
        "Articles:"
    )
    assert (
        text(call(server, token, "news_digest", {"date": "today"})) == "Invalid date 'today'. Use YYYY-MM-DD."
    )
