"""Sphinx configuration for the Nexus documentation."""  # noqa: INP001

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus.settings.dev")
django.setup()

project = "Nexus"
author = "Mika Mäki"
project_copyright = "2025-2026, Mika Mäki"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
]
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "django": ("https://docs.djangoproject.com/en/6.1/", "https://docs.djangoproject.com/en/6.1/_objects/"),
}
exclude_patterns = ["_build"]
html_theme = "furo"
nitpicky = False
