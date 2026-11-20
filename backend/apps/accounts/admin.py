"""Admin registrations for accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpRequest

from apps.accounts.models import AgentToken, User

admin.site.register(User, UserAdmin)


@admin.register(AgentToken)
class AgentTokenAdmin(admin.ModelAdmin):
    """Inspect and revoke agent tokens. They are created through the API, which shows the secret once."""

    list_display = ("name", "user", "hint", "scopes", "expires_at", "last_used_at")
    list_filter = ("user",)
    readonly_fields = ("user", "hint", "created_at", "last_used_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Disallow adding here, as the admin could not show the generated secret."""
        return False
