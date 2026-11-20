"""Periods of sleep."""

from typing import ClassVar

from django.db import models
from django.utils import timezone

from apps.core.models import OwnedManager, OwnedModel


class Tag(OwnedModel):
    """A hashtag that a user wrote in the comment of a sleep record."""

    name = models.CharField(max_length=100)

    objects: ClassVar[OwnedManager[Tag]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        ordering = ("name",)
        constraints = (models.UniqueConstraint(fields=("user", "name"), name="unique_sleep_tag"),)

    def __str__(self) -> str:
        """Return the tag with its hash sign."""
        return f"#{self.name}"


class SleepRecord(OwnedModel):
    """One period of sleep, taken from an event of the user's sleep calendar.

    Records are rebuilt from the calendar on every synchronisation, so they
    are never edited here. The optional fields are filled only for calendars
    written by Sleep as Android.
    """

    start = models.DateTimeField()
    end = models.DateTimeField()
    duration = models.DurationField(
        help_text="Time asleep. From the app when it reports one, else end minus start."
    )
    rating = models.FloatField(null=True, blank=True, help_text="0-5 stars.")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    deep_sleep = models.FloatField(null=True, blank=True, help_text="Share of deep sleep, 0-1.")
    cycles = models.PositiveSmallIntegerField(null=True, blank=True)
    noise = models.FloatField(null=True, blank=True, help_text="Noise level, 0-1.")
    snoring = models.DurationField(null=True, blank=True)
    comment = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="records")

    objects: ClassVar[OwnedManager[SleepRecord]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        ordering = ("start",)
        indexes = (models.Index(fields=("user", "end")),)

    def __str__(self) -> str:
        """Return the period of the record in local time."""
        return f"{timezone.localtime(self.start):%Y-%m-%d %H:%M} - {timezone.localtime(self.end):%H:%M}"
