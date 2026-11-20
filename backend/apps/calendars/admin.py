"""Admin registrations for calendars."""

from django.contrib import admin

from apps.calendars.models import Calendar


@admin.register(Calendar)
class CalendarAdmin(admin.ModelAdmin):
    """Calendars and the state of their synchronisation. The secret address is not shown."""

    list_display = ("name", "user", "is_sleep", "synced_at", "sync_error")
    list_filter = ("user",)
    exclude = ("url",)
    readonly_fields = ("synced_at", "sync_error")
