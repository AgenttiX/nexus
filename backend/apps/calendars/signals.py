"""Signals of the calendars app."""

from django.dispatch import Signal

#: Sent after the events of a calendar have been replaced. Provides ``calendar``.
calendar_synced = Signal()
