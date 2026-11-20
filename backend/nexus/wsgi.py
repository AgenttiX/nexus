"""WSGI entry point, served by Gunicorn."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus.settings.prod")

application = get_wsgi_application()
