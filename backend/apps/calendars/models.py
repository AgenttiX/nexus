"""Calendars and their events."""

from typing import ClassVar

from django.core.validators import RegexValidator
from django.db import models
from encrypted_fields.fields import EncryptedTextField

from apps.core.models import OwnedManager, OwnedModel


class Calendar(OwnedModel):
    """A calendar that Nexus reads from an iCalendar address.

    The address of a private calendar is a secret that gives read access to
    it, so it is stored encrypted and never returned by the API.
    """

    name = models.CharField(max_length=100)
    url = EncryptedTextField(help_text="Secret iCalendar address (https).")
    color = models.CharField(
        max_length=7, default="#3b82f6", validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$")]
    )
    is_sleep = models.BooleanField(default=False, help_text="Events of this calendar are periods of sleep.")
    sleep_as_android = models.BooleanField(
        default=False,
        help_text="The sleep calendar is written by Sleep as Android, whose events carry extra data.",
    )
    synced_at = models.DateTimeField(null=True, blank=True, editable=False)
    sync_error = models.TextField(blank=True, editable=False)

    objects: ClassVar[OwnedManager[Calendar]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(fields=("user", "name"), name="unique_calendar_name"),
            models.UniqueConstraint(
                fields=("user",),
                condition=models.Q(is_sleep=True),
                name="one_sleep_calendar_per_user",
            ),
        )

    def __str__(self) -> str:
        """Return the calendar's name."""
        return self.name


class Event(models.Model):
    """One occurrence of a calendar event. Recurring events are stored once per occurrence."""

    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE, related_name="events")
    uid = models.CharField(max_length=500)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    title = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("start", "end")
        indexes = (models.Index(fields=("calendar", "start")),)

    def __str__(self) -> str:
        """Return the event's title."""
        return self.title
