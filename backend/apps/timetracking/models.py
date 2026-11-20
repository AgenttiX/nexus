"""Activity recorded by ActivityWatch."""

from typing import ClassVar

from django.db import models

from apps.core.models import OwnedManager, OwnedModel


class Bucket(OwnedModel):
    """One stream of events from one watcher on one device, such as the active window of a laptop."""

    name = models.CharField(max_length=300, help_text="The bucket's id in ActivityWatch.")
    type = models.CharField(max_length=100, help_text="For example currentwindow or afkstatus.")
    client = models.CharField(max_length=100, blank=True)
    hostname = models.CharField(max_length=200, blank=True)
    imported_until = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="End of the latest imported event; the next import continues from here.",
    )

    objects: ClassVar[OwnedManager[Bucket]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        ordering = ("hostname", "name")
        constraints = (models.UniqueConstraint(fields=("user", "name"), name="unique_bucket_name"),)

    def __str__(self) -> str:
        """Return the bucket's name."""
        return self.name


class Event(models.Model):
    """A period during which something was true, such as one window having the focus."""

    bucket = models.ForeignKey(Bucket, on_delete=models.CASCADE, related_name="events")
    source_id = models.BigIntegerField(help_text="The event's id in the device's database.")
    start = models.DateTimeField()
    end = models.DateTimeField()
    data = models.JSONField(default=dict)

    class Meta:
        ordering = ("start",)
        indexes = (models.Index(fields=("bucket", "end")),)
        constraints = (models.UniqueConstraint(fields=("bucket", "source_id"), name="unique_event_source"),)

    def __str__(self) -> str:
        """Return the period of the event."""
        return f"{self.start:%Y-%m-%d %H:%M:%S} - {self.end:%H:%M:%S}"
