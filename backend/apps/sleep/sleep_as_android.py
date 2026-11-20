"""Reading the extra data that Sleep as Android writes into its calendar events.

PLACEHOLDER. The format of those events is not documented, so the parser will
be written against an example calendar. Until then :func:`parse` finds
nothing, and sleep records get their times from the events alone.

The fields to read from each event:

- rating (0-5 stars)
- location (coordinates)
- duration, which overrides the duration computed from the start and end time
- deep sleep (percentage)
- cycles (integer)
- noise (percentage)
- snoring (duration)
- comment (free text that may contain hashtags)

Hashtags in the comment become tags of the record; that part does not depend
on the event format and is implemented in :func:`extract_tags`.
"""

import datetime as dt
import re
from dataclasses import dataclass

from apps.calendars.models import Event

TAG_PATTERN = re.compile(r"#(\w+)")


@dataclass(frozen=True)
class SleepDetails:
    """What Sleep as Android recorded about one period of sleep. ``None`` means not reported."""

    duration: dt.timedelta | None = None
    rating: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    deep_sleep: float | None = None
    cycles: int | None = None
    noise: float | None = None
    snoring: dt.timedelta | None = None
    comment: str = ""


def parse(event: Event) -> SleepDetails:  # noqa: ARG001 - used once the format is known
    """Return the details in a Sleep as Android event. Not implemented yet: returns no details."""
    return SleepDetails()


def extract_tags(comment: str) -> list[str]:
    """Return the distinct hashtags of a comment in lower case, without the hash sign."""
    return sorted({tag.lower() for tag in TAG_PATTERN.findall(comment)})
