"""Serializers for news."""

from rest_framework import serializers

from apps.news.models import Article, Digest, DigestArticle, NewsProfile
from apps.news.sources import SOURCES


class NewsProfileSerializer(serializers.ModelSerializer[NewsProfile]):
    """A user's news settings."""

    sources = serializers.ListField(child=serializers.ChoiceField(choices=list(SOURCES)), allow_empty=False)

    class Meta:
        model = NewsProfile
        fields = (
            "enabled",
            "digest_hour",
            "sources",
            "criteria",
            "max_articles",
            "mode",
            "selection_model",
            "summary_model",
            "language",
        )


class SourceSerializer(serializers.Serializer[object]):
    """A news site that can be chosen as a source."""

    key = serializers.CharField()
    name = serializers.CharField()
    language = serializers.CharField()
    full_text = serializers.BooleanField()


class ArticleSerializer(serializers.ModelSerializer[Article]):
    """A news article, without its text."""

    class Meta:
        model = Article
        fields = ("id", "source", "url", "title", "lead", "published_at")


class DigestArticleSerializer(serializers.ModelSerializer[DigestArticle]):
    """An article of a digest, with its own summary when one was written."""

    article = ArticleSerializer()

    class Meta:
        model = DigestArticle
        fields = ("article", "summary")


class DigestSerializer(serializers.ModelSerializer[Digest]):
    """A news digest with the articles it was written from."""

    selected = DigestArticleSerializer(many=True)

    class Meta:
        model = Digest
        fields = ("id", "date", "status", "mode", "summary", "error", "created_at", "selected")
