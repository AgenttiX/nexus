"""Admin registrations for news."""

from django.contrib import admin

from apps.news.models import Article, Digest


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Articles, as read from the feeds."""

    list_display = ("title", "source", "published_at")
    list_filter = ("source",)
    search_fields = ("title",)


@admin.register(Digest)
class DigestAdmin(admin.ModelAdmin):
    """Digests and whether writing them succeeded."""

    list_display = ("date", "user", "status", "mode", "error")
    list_filter = ("status", "user")
