"""Database connection handling outside Django's request cycle."""

import functools
from collections.abc import Callable

from django.db import close_old_connections


def with_fresh_connection[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Drop stale database connections around a tool call, as Django does around a request."""

    @functools.wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        close_old_connections()
        try:
            return function(*args, **kwargs)
        finally:
            close_old_connections()

    return wrapper
