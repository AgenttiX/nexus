"""Statistics of sleep times.

Clock times need care: the mean of 23:00 and 01:00 is midnight, not noon. Times
of day are therefore averaged on the circle of the 24-hour clock, and the other
statistics are taken from each time's distance to that circular mean.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

HOURS_PER_DAY = 24.0


@dataclass(frozen=True)
class Stats:
    """Summary of a series of values, in hours. Clock times are hours after midnight."""

    count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    std: float


def summarize(values: Sequence[float]) -> Stats | None:
    """Summarise ordinary values such as durations. ``None`` when there are none."""
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    return Stats(
        count=len(values),
        minimum=float(array.min()),
        maximum=float(array.max()),
        mean=float(array.mean()),
        median=float(np.median(array)),
        std=_sample_std(array),
    )


def circular_mean(hours: Sequence[float]) -> float:
    """Return the mean time of day of ``hours``, as hours after midnight."""
    angles = np.asarray(hours, dtype=float) / HOURS_PER_DAY * 2 * math.pi
    mean_angle = math.atan2(float(np.sin(angles).mean()), float(np.cos(angles).mean()))
    return (mean_angle / (2 * math.pi) * HOURS_PER_DAY) % HOURS_PER_DAY


def clock_difference(later: float, earlier: float) -> float:
    """Return how many hours ``later`` is after ``earlier`` on the clock, between -12 and 12."""
    return (later - earlier + HOURS_PER_DAY / 2) % HOURS_PER_DAY - HOURS_PER_DAY / 2


def summarize_clock(hours: Sequence[float]) -> Stats | None:
    """Summarise times of day. The minimum is the earliest and the maximum the latest time around the mean."""
    if not hours:
        return None
    center = circular_mean(hours)
    offsets = np.asarray([clock_difference(hour, center) for hour in hours], dtype=float)
    return Stats(
        count=len(hours),
        minimum=float((center + offsets.min()) % HOURS_PER_DAY),
        maximum=float((center + offsets.max()) % HOURS_PER_DAY),
        mean=center,
        median=float((center + np.median(offsets)) % HOURS_PER_DAY),
        std=_sample_std(offsets),
    )


def _sample_std(array: np.ndarray) -> float:
    return float(array.std(ddof=1)) if len(array) > 1 else 0.0
