"""Reading the SQLite databases of ActivityWatch (``aw-server-rust``).

Devices write their databases into a directory that the user synchronises to
the server, for example with ``aw-sync`` and Syncthing. This module only ever
reads those files: they are opened read-only, and a file that is being
written or is damaged is skipped until the next run.

The tables it relies on, from ``aw-datastore`` of ``aw-server-rust``::

    buckets(id, name, type, client, hostname, ...)
    events(id, bucketrow, starttime, endtime, data)

``starttime`` and ``endtime`` are nanoseconds since the Unix epoch, and
``data`` is a JSON object.
"""

import datetime as dt
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

NANOSECONDS = 1_000_000_000
EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)


@dataclass(frozen=True)
class SourceBucket:
    """A bucket in a device's database."""

    row: int
    name: str
    type: str
    client: str
    hostname: str


@dataclass(frozen=True)
class SourceEvent:
    """An event in a device's database."""

    id: int
    start: dt.datetime
    end: dt.datetime
    data: dict[str, object]


def find_databases(directory: Path) -> list[Path]:
    """Return the SQLite databases below ``directory``, in a stable order."""
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.rglob("*.db") if path.is_file())


def connect(path: Path) -> sqlite3.Connection:
    """Open a database strictly read-only.

    ActivityWatch keeps its databases in write-ahead-log mode, which SQLite
    cannot open from a read-only directory, as it wants to create helper files
    there. Such a database is opened as immutable instead: it is read as it
    is on disk, without any helper files. Changes still waiting in the
    device's write-ahead log are then picked up by a later import.
    """
    uri = path.resolve().as_uri()
    connection = sqlite3.connect(f"{uri}?mode=ro", uri=True, timeout=5)
    try:
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite3.OperationalError:
        connection.close()
        return sqlite3.connect(f"{uri}?immutable=1", uri=True, timeout=5)
    return connection


def read_buckets(connection: sqlite3.Connection) -> list[SourceBucket]:
    """Return the buckets of a database."""
    with closing(connection.execute("SELECT id, name, type, client, hostname FROM buckets")) as cursor:
        return [SourceBucket(*row) for row in cursor]


def read_events(
    connection: sqlite3.Connection,
    bucket: SourceBucket,
    since: dt.datetime | None,
) -> Iterator[SourceEvent]:
    """Yield the events of a bucket that ended at or after ``since``, oldest first.

    The event that was being recorded when the previous import ran has grown
    since, so events are selected by their end, and the last one is read again.
    """
    since_nanoseconds = _to_nanoseconds(since) if since else -(2**63)
    query = (
        "SELECT id, starttime, endtime, data FROM events "
        "WHERE bucketrow = ? AND endtime >= ? ORDER BY endtime"
    )
    with closing(connection.execute(query, (bucket.row, since_nanoseconds))) as cursor:
        for event_id, start, end, data in cursor:
            try:
                decoded = json.loads(data)
            except ValueError:
                continue
            if not isinstance(decoded, dict):
                continue
            yield SourceEvent(event_id, _from_nanoseconds(start), _from_nanoseconds(end), decoded)


def _to_nanoseconds(moment: dt.datetime) -> int:
    delta = moment - EPOCH
    return (delta.days * 86400 + delta.seconds) * NANOSECONDS + delta.microseconds * 1000


def _from_nanoseconds(value: int) -> dt.datetime:
    return EPOCH + dt.timedelta(microseconds=value // 1000)
