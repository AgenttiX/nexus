"""Background tasks for news."""

from celery import shared_task
from django.utils import timezone

from apps.news import services
from apps.news.models import Digest, NewsProfile


@shared_task
def fetch_articles() -> int:
    """Read all news feeds. Returns the number of new articles."""
    return services.fetch_articles()


@shared_task
def write_digest(digest_id: int, *, fetch_first: bool = False) -> str:
    """Write one digest, optionally reading the feeds first so that it covers the latest news.

    Returns the digest's final status; a deleted digest counts as failed.
    """
    digest = Digest.objects.filter(pk=digest_id).first()
    if digest is None:
        return "failed"
    if fetch_first:
        services.fetch_articles()
    services.write_digest(digest)
    return digest.status


@shared_task
def write_due_digests() -> int:
    """Start today's digest for every user whose chosen hour is now. Runs once an hour."""
    now = timezone.localtime()
    started = 0
    for profile in NewsProfile.objects.filter(enabled=True, digest_hour=now.hour).select_related("user"):
        if Digest.objects.for_user(profile.user).filter(date=now.date()).exists():
            continue
        if started == 0:
            services.fetch_articles()
        write_digest.delay(services.start_digest(profile.user).pk)
        started += 1
    return started
