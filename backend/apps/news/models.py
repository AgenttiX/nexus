"""News articles, each user's news settings, and their daily digests."""

from typing import ClassVar

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import OwnedManager, OwnedModel
from apps.news.sources import SOURCES

DEFAULT_CRITERIA = (
    "Select articles that matter for politics (both global geopolitics and Finnish politics), "
    "the economy, technology and science. Skip articles about celebrities and sports."
)


def all_source_keys() -> list[str]:
    """Return the keys of every news source, the default selection for a new profile."""
    return list(SOURCES)


class Article(models.Model):
    """An article of a news site. Articles are public and shared by all users."""

    source = models.CharField(max_length=20, choices=[(key, source.name) for key, source in SOURCES.items()])
    url = models.URLField(max_length=1000, unique=True)
    title = models.CharField(max_length=500)
    lead = models.TextField(blank=True)
    text = models.TextField(blank=True, help_text="Full text, fetched only when a digest needs it.")
    published_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("-published_at",)

    def __str__(self) -> str:
        """Return the article's title."""
        return self.title

    @property
    def content(self) -> str:
        """The most complete text available: the full text, or else the lead."""
        return self.text or self.lead


class Mode(models.TextChoices):
    """How a digest is written."""

    SINGLE = "single", "All articles in one context (for models with very large context windows)"
    PARALLEL = "parallel", "One session per article, then a summary of the summaries (for local models)"


class NewsProfile(OwnedModel):
    """A user's settings for their news digest."""

    enabled = models.BooleanField(default=False, help_text="Write a digest every day at the chosen hour.")
    digest_hour = models.PositiveSmallIntegerField(default=18, validators=[MaxValueValidator(23)])
    sources = models.JSONField(default=all_source_keys)
    criteria = models.TextField(
        default=DEFAULT_CRITERIA, help_text="How to recognise the articles worth reading."
    )
    max_articles = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.PARALLEL)
    selection_model = models.CharField(
        max_length=200, blank=True, help_text="Empty: the deployment's default model."
    )
    summary_model = models.CharField(
        max_length=200, blank=True, help_text="Empty: the deployment's default model."
    )
    language = models.CharField(max_length=50, default="English", help_text="Language of the digest.")

    objects: ClassVar[OwnedManager[NewsProfile]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        constraints = (models.UniqueConstraint(fields=("user",), name="one_news_profile_per_user"),)

    def __str__(self) -> str:
        """Return whose profile this is."""
        return f"News profile of {self.user}"


class Status(models.TextChoices):
    """Progress of a digest."""

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class Digest(OwnedModel):
    """A summary of one day's news for one user."""

    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    mode = models.CharField(max_length=10, choices=Mode.choices)
    summary = models.TextField(blank=True)
    error = models.TextField(blank=True)
    articles = models.ManyToManyField(Article, through="DigestArticle", related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    objects: ClassVar[OwnedManager[Digest]] = OwnedManager()

    class Meta(OwnedModel.Meta):
        ordering = ("-date",)
        constraints = (models.UniqueConstraint(fields=("user", "date"), name="one_digest_per_user_and_day"),)

    def __str__(self) -> str:
        """Return the day of the digest."""
        return f"News digest {self.date}"


class DigestArticle(models.Model):
    """An article that was selected for a digest, with its own summary in parallel mode."""

    digest = models.ForeignKey(Digest, on_delete=models.CASCADE, related_name="selected")
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="+")
    position = models.PositiveSmallIntegerField()
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ("position",)
        constraints = (models.UniqueConstraint(fields=("digest", "article"), name="unique_digest_article"),)

    def __str__(self) -> str:
        """Return the article's title."""
        return str(self.article)
