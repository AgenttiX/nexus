"""Tests for the time tracking app."""

import datetime as dt
import json
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient
from starlette.testclient import TestClient

from apps.accounts.models import AgentToken, User
from apps.timetracking import activitywatch, services, tasks
from apps.timetracking.models import Bucket, Event
from tests.mcp_helpers import call, text, tool_names

HELSINKI = ZoneInfo("Europe/Helsinki")
MONDAY, TUESDAY = dt.date(2026, 11, 16), dt.date(2026, 11, 17)

# The tables of aw-server-rust's datastore, as created by its migrations.
SCHEMA = """
CREATE TABLE buckets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, type TEXT NOT NULL,
    client TEXT NOT NULL, hostname TEXT NOT NULL, created TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, bucketrow INTEGER NOT NULL, starttime INTEGER NOT NULL,
    endtime INTEGER NOT NULL, data TEXT NOT NULL, FOREIGN KEY (bucketrow) REFERENCES buckets(id)
);
"""


def at(day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 11, day, hour, minute, tzinfo=HELSINKI)


def nanoseconds(moment: dt.datetime) -> int:
    return int(moment.timestamp()) * 1_000_000_000


class Device:
    """A device's ActivityWatch database on disk."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as connection:
            connection.executescript(SCHEMA)

    def bucket(self, name: str, kind: str, hostname: str) -> int:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "INSERT INTO buckets (name, type, client, hostname, created) "
                "VALUES (?, ?, 'aw-watcher', ?, '')",
                (name, kind, hostname),
            )
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def event(self, bucket: int, start: dt.datetime, end: dt.datetime, data: object) -> int:
        payload = data if isinstance(data, str) else json.dumps(data)
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "INSERT INTO events (bucketrow, starttime, endtime, data) VALUES (?, ?, ?, ?)",
                (bucket, nanoseconds(start), nanoseconds(end), payload),
            )
            assert cursor.lastrowid is not None
            return cursor.lastrowid

    def extend(self, event: int, end: dt.datetime) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE events SET endtime = ? WHERE id = ?", (nanoseconds(end), event))


@pytest.fixture
def sync_dir(tmp_path: Path, settings: Settings) -> Path:
    settings.AW_SYNC_DIR = str(tmp_path)
    return tmp_path


@pytest.fixture
def laptop(sync_dir: Path, user: User) -> Device:
    """A laptop of ``user`` with a morning of window and away-from-keyboard events on Monday.

    Present 09:00-10:00 and 10:30-12:00; editor 09:00-11:00, browser 11:00-12:00.
    """
    device = Device(sync_dir / "alice" / "laptop" / "abc" / "sync.db")
    afk = device.bucket("aw-watcher-afk_laptop", "afkstatus", "laptop")
    device.event(afk, at(16, 9), at(16, 10), {"status": "not-afk"})
    device.event(afk, at(16, 10), at(16, 10, 30), {"status": "afk"})
    device.event(afk, at(16, 10, 30), at(16, 12), {"status": "not-afk"})
    window = device.bucket("aw-watcher-window_laptop", "currentwindow", "laptop")
    device.event(window, at(16, 9), at(16, 11), {"app": "Editor", "title": "notes"})
    device.event(window, at(16, 11), at(16, 12), {"app": "Browser", "title": "news"})
    return device


# Reading databases


def test_databases_are_found_recursively(tmp_path: Path) -> None:
    Device(tmp_path / "b" / "sync.db")
    Device(tmp_path / "a" / "deep" / "sync.db")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "folder.db").mkdir()
    assert activitywatch.find_databases(tmp_path) == [
        tmp_path / "a" / "deep" / "sync.db",
        tmp_path / "b" / "sync.db",
    ]
    assert activitywatch.find_databases(tmp_path / "missing") == []


def test_databases_are_opened_read_only(tmp_path: Path) -> None:
    device = Device(tmp_path / "sync.db")
    connection = activitywatch.connect(device.path)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        connection.execute("DELETE FROM buckets")
    connection.close()


def test_write_ahead_log_databases_are_read_from_read_only_directories(tmp_path: Path) -> None:
    path = tmp_path / "mounted" / "sync.db"
    path.parent.mkdir()
    # Closed properly, as a device does: the helper files are gone and only the database remains.
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT INTO buckets (name, type, client, hostname, created) VALUES ('window', 't', '', '', '')"
    )
    connection.commit()
    connection.close()
    assert [item.name for item in path.parent.iterdir()] == ["sync.db"]
    path.chmod(0o444)
    path.parent.chmod(0o555)
    try:
        connection = activitywatch.connect(path)
        assert [bucket.name for bucket in activitywatch.read_buckets(connection)] == ["window"]
        connection.close()
    finally:
        path.parent.chmod(0o755)


def test_events_are_read_with_times_and_unreadable_ones_skipped(tmp_path: Path) -> None:
    device = Device(tmp_path / "sync.db")
    row = device.bucket("window", "currentwindow", "laptop")
    device.event(row, at(16, 9), at(16, 10), {"app": "Editor"})
    device.event(row, at(16, 10), at(16, 11), "not json")
    device.event(row, at(16, 11), at(16, 12), [1, 2])
    connection = activitywatch.connect(device.path)
    (bucket,) = activitywatch.read_buckets(connection)
    assert (bucket.name, bucket.type, bucket.client, bucket.hostname) == (
        "window",
        "currentwindow",
        "aw-watcher",
        "laptop",
    )
    events = list(activitywatch.read_events(connection, bucket, None))
    assert [(event.start, event.end, event.data) for event in events] == [
        (at(16, 9), at(16, 10), {"app": "Editor"})
    ]
    assert list(activitywatch.read_events(connection, bucket, at(16, 10, 30))) == []
    connection.close()


# Import


def test_import_reads_each_users_own_directory(
    laptop: Device, sync_dir: Path, user: User, other_user: User
) -> None:
    other = Device(sync_dir / "bob" / "sync.db")
    other.event(
        other.bucket("aw-watcher-window_pc", "currentwindow", "pc"), at(16, 9), at(16, 10), {"app": "Game"}
    )

    assert tasks.import_activitywatch.apply().get() == 6
    assert sorted(Bucket.objects.for_user(user).values_list("name", "type", "hostname")) == [
        ("aw-watcher-afk_laptop", "afkstatus", "laptop"),
        ("aw-watcher-window_laptop", "currentwindow", "laptop"),
    ]
    assert Bucket.objects.for_user(other_user).get().name == "aw-watcher-window_pc"
    window = Bucket.objects.get(name="aw-watcher-window_laptop")
    assert window.imported_until == at(16, 12)
    assert (str(window), str(window.events.first())) == (
        "aw-watcher-window_laptop",
        "2026-11-16 07:00:00 - 09:00:00",
    )


def test_import_is_incremental_and_updates_the_growing_event(
    laptop: Device, user: User, sync_dir: Path
) -> None:
    services.import_all()
    assert Event.objects.count() == 5

    with sqlite3.connect(laptop.path) as connection:
        (window, last) = connection.execute(
            "SELECT bucketrow, max(id) FROM events WHERE bucketrow = 2"
        ).fetchone()
    laptop.extend(last, at(16, 12, 30))
    laptop.event(window, at(16, 12, 30), at(16, 13), {"app": "Terminal"})

    # Only the grown event and the new one of that bucket, plus the last event of the other bucket, are read.
    assert services.import_all() == 3
    assert Event.objects.count() == 6
    assert Event.objects.get(data__app="Browser").end == at(16, 12, 30)


def test_import_is_done_in_batches(laptop: Device, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "BATCH_SIZE", 2)
    assert services.import_all() == 5
    assert Event.objects.count() == 5


def test_unreadable_files_are_skipped(laptop: Device, sync_dir: Path, user: User) -> None:
    (sync_dir / "alice" / "broken.db").write_bytes(b"this is not a database")
    with sqlite3.connect(sync_dir / "alice" / "other.db") as connection:
        connection.execute("CREATE TABLE unrelated (x)")
    assert services.import_all() == 5


def test_users_without_data_are_fine(sync_dir: Path, user: User) -> None:
    assert services.import_all() == 0
    assert not Bucket.objects.exists()


# Summary


def test_summary_counts_only_time_at_the_device(laptop: Device, user: User, other_user: User) -> None:
    services.import_all()
    result = services.summary(user, MONDAY, TUESDAY)
    assert result.by_day == {MONDAY: pytest.approx(2.5), TUESDAY: 0}
    assert dict(result.by_app) == {"Editor": pytest.approx(1.5), "Browser": pytest.approx(1.0)}
    assert dict(result.by_device) == {"laptop": pytest.approx(2.5)}
    assert result.total == pytest.approx(2.5)
    assert services.summary(other_user, MONDAY, TUESDAY).total == 0


def test_device_without_afk_watcher_counts_in_full_and_days_split_at_midnight(
    sync_dir: Path, user: User
) -> None:
    phone = Device(sync_dir / "alice" / "phone.db")
    bucket = phone.bucket("aw-watcher-android-test", "currentwindow", "")
    phone.event(bucket, at(16, 23), at(17, 1), {"app": "Reader"})
    phone.event(bucket, at(17, 8), at(17, 8, 30), {"classname": "x"})
    services.import_all()

    result = services.summary(user, MONDAY, TUESDAY)
    assert result.by_day == {MONDAY: pytest.approx(1.0), TUESDAY: pytest.approx(1.5)}
    assert dict(result.by_app) == {"Reader": pytest.approx(2.0), "(unknown)": pytest.approx(0.5)}
    assert dict(result.by_device) == {"(unknown)": pytest.approx(2.5)}
    assert services.summary(user, TUESDAY, TUESDAY).by_day == {TUESDAY: pytest.approx(1.5)}


def test_overlapping_presence_is_not_counted_twice(sync_dir: Path, user: User) -> None:
    device = Device(sync_dir / "alice" / "sync.db")
    afk = device.bucket("afk", "afkstatus", "laptop")
    device.event(afk, at(16, 9), at(16, 10), {"status": "not-afk"})
    device.event(afk, at(16, 9, 30), at(16, 11), {"status": "not-afk"})
    device.event(device.bucket("window", "currentwindow", "laptop"), at(16, 8), at(16, 12), {"app": "Editor"})
    services.import_all()
    assert services.summary(user, MONDAY, MONDAY).total == pytest.approx(2.0)


def test_summary_text(laptop: Device, sync_dir: Path, user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    services.import_all()
    assert services.summary_text(user, MONDAY, TUESDAY) == (
        "Active time 2026-11-16..2026-11-17: 2:30 total, 1:15 per day\n"
        "apps: Editor 1:30, Browser 1:00\n"
        "days: Mon 11-16 2:30, Tue 11-17 0:00"
    )
    assert (
        services.summary_text(user, TUESDAY, TUESDAY) == "No activity recorded from 2026-11-17 to 2026-11-17."
    )

    phone = Device(sync_dir / "alice" / "phone.db")
    phone.event(phone.bucket("android", "currentwindow", "phone"), at(16, 20), at(16, 21), {"app": "Reader"})
    services.import_all()
    monkeypatch.setattr(services, "MAX_TEXT_APPS", 2)
    assert services.summary_text(user, MONDAY, MONDAY).splitlines()[1:4] == [
        "devices: laptop 2:30, phone 1:00",
        "apps: Editor 1:30, Browser 1:00",
        "(1 more apps not shown)",
    ]


# REST API


def test_timetracking_api_requires_login(api_client: APIClient) -> None:
    assert api_client.get("/api/timetracking/buckets/").status_code == 403
    assert api_client.get("/api/timetracking/summary/").status_code == 403


def test_summary_and_buckets_api(laptop: Device, user_client: APIClient, other_client: APIClient) -> None:
    services.import_all()
    period = {"start": "2026-11-16", "end": "2026-11-17"}
    body = user_client.get("/api/timetracking/summary/", period).json()
    assert body == {
        "first": "2026-11-16",
        "last": "2026-11-17",
        "total": 2.5,
        "by_day": [{"date": "2026-11-16", "hours": 2.5}, {"date": "2026-11-17", "hours": 0.0}],
        "by_app": [{"name": "Editor", "hours": 1.5}, {"name": "Browser", "hours": 1.0}],
        "by_device": [{"name": "laptop", "hours": 2.5}],
    }
    assert other_client.get("/api/timetracking/summary/", period).json()["total"] == 0

    buckets = user_client.get("/api/timetracking/buckets/").json()
    assert [(bucket["name"], bucket["hostname"]) for bucket in buckets] == [
        ("aw-watcher-afk_laptop", "laptop"),
        ("aw-watcher-window_laptop", "laptop"),
    ]
    assert other_client.get("/api/timetracking/buckets/").json() == []


@pytest.mark.parametrize(
    "period",
    [{}, {"start": "2026-11-17", "end": "2026-11-16"}, {"start": "2026-01-01", "end": "2026-11-16"}],
)
def test_summary_api_needs_a_valid_short_period(user_client: APIClient, period: dict[str, str]) -> None:
    assert user_client.get("/api/timetracking/summary/", period).status_code == 400


# MCP


@pytest.mark.django_db(transaction=True)
def test_time_tool(server: TestClient, user: User, tmp_path: Path, settings: Settings) -> None:
    settings.AW_SYNC_DIR = str(tmp_path)
    device = Device(tmp_path / "alice" / "sync.db")
    device.event(device.bucket("window", "currentwindow", "laptop"), at(16, 9), at(16, 10), {"app": "Editor"})
    services.import_all()

    outsider = AgentToken.objects.create_token(user, "sleep agent", {"sleep": "read"})[1]
    assert "time_summary" not in tool_names(server, outsider)
    token = AgentToken.objects.create_token(user, "time agent", {"timetracking": "read"})[1]
    period = {"start": "2026-11-16", "end": "2026-11-16"}
    assert text(call(server, token, "time_summary", period)).startswith(
        "Active time 2026-11-16..2026-11-16: 1:00 total"
    )
    assert text(call(server, token, "time_summary")).startswith(("Active time", "No activity"))
    assert text(call(server, token, "time_summary", {"start": "Monday"})) == "Invalid date. Use YYYY-MM-DD."
    for bad in ({"start": "2026-11-17", "end": "2026-11-16"}, {"start": "2026-01-01", "end": "2026-11-16"}):
        assert text(call(server, token, "time_summary", bad)).startswith(
            "The start must not be after the end"
        )
