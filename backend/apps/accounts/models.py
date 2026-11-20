"""Users and the tokens that give AI agents access to their data."""

import hashlib
import secrets
from datetime import timedelta
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import OwnedManager, OwnedModel

TOKEN_PREFIX = "nxs_"  # noqa: S105 - a marker that makes leaked tokens recognisable, not a secret
LAST_USED_RESOLUTION = timedelta(minutes=1)


class User(AbstractUser):
    """A person using this Nexus deployment.

    A custom model from the first migration, so that fields can be added later
    without the pain of swapping the user model.
    """


class Feature(models.TextChoices):
    """The parts of Nexus that an agent can be given access to separately."""

    NEWS = "news"
    FINANCE = "finance"
    INVESTMENTS = "investments"
    TIMETRACKING = "timetracking"
    CALENDARS = "calendars"
    SLEEP = "sleep"
    FOOD = "food"


class Access(models.TextChoices):
    """What an agent may do within one feature. Write access includes read access."""

    READ = "read"
    WRITE = "write"


def scope(feature: Feature, access: Access) -> str:
    """Return the scope string for one feature and access level, e.g. ``sleep:read``."""
    return f"{feature.value}:{access.value}"


def validate_scopes(value: object) -> None:
    """Check that ``value`` maps known features to known access levels."""
    if not isinstance(value, dict):
        msg = "Scopes must be an object mapping features to access levels."
        raise ValidationError(msg)
    for feature, access in value.items():
        if feature not in Feature.values:
            msg = f"Unknown feature: {feature!r}."
            raise ValidationError(msg)
        if access not in Access.values:
            msg = f"Unknown access level for {feature}: {access!r}."
            raise ValidationError(msg)


def hash_token(plaintext: str) -> str:
    """Return the digest under which a token is stored.

    Tokens are 256 random bits, so a plain SHA-256 is enough: there is nothing
    to brute-force, and lookups stay a single indexed query.
    """
    return hashlib.sha256(plaintext.encode()).hexdigest()


class AgentTokenManager(OwnedManager["AgentToken"]):
    """Creation and verification of agent tokens."""

    def create_token(
        self,
        user: User,
        name: str,
        scopes: dict[str, str],
        expires_at: timezone.datetime | None = None,
    ) -> tuple[AgentToken, str]:
        """Create a token and return it with its plaintext, which is never stored."""
        plaintext = TOKEN_PREFIX + secrets.token_urlsafe(32)
        token = self.model(
            user=user,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            token_hash=hash_token(plaintext),
            hint=plaintext[-4:],
        )
        token.full_clean()
        token.save()
        return token, plaintext

    def authenticate(self, plaintext: str) -> AgentToken | None:
        """Return the valid token matching ``plaintext``, recording that it was used."""
        token = self.select_related("user").filter(token_hash=hash_token(plaintext)).first()
        if token is None or not token.is_valid:
            return None
        now = timezone.now()
        if token.last_used_at is None or now - token.last_used_at > LAST_USED_RESOLUTION:
            token.last_used_at = now
            token.save(update_fields=["last_used_at"])
        return token


class AgentToken(OwnedModel):
    """A bearer token for one AI agent, limited to one user's data and to chosen features."""

    name = models.CharField(max_length=100, help_text="The agent this is for.")
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    hint = models.CharField(max_length=4, editable=False, help_text="Last characters of the token.")
    scopes = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_scopes],
        help_text='Access per feature, e.g. {"sleep": "read"}. Unlisted features are denied.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects: ClassVar[AgentTokenManager] = AgentTokenManager()

    class Meta(OwnedModel.Meta):
        ordering = ("name",)
        constraints = (models.UniqueConstraint(fields=("user", "name"), name="unique_agent_token_name"),)

    def __str__(self) -> str:
        """Return the agent's name."""
        return self.name

    @property
    def is_valid(self) -> bool:
        """Whether the token can be used: its owner is active and it has not expired."""
        return self.user.is_active and (self.expires_at is None or self.expires_at > timezone.now())

    @property
    def scope_strings(self) -> list[str]:
        """Scopes in ``feature:access`` form, with write access expanded to include read."""
        result: list[str] = []
        for feature in Feature:
            access = self.scopes.get(feature.value)
            if access in Access.values:
                result.append(scope(feature, Access.READ))
            if access == Access.WRITE:
                result.append(scope(feature, Access.WRITE))
        return result
