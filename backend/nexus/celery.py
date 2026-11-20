"""Celery application for background tasks."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus.settings.prod")

app = Celery("nexus")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
