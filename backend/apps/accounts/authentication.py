"""Authentication of the Android app by tokens that Authentik issued."""

from functools import lru_cache

import jwt
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.db import transaction
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.accounts.models import User

ALGORITHMS = ["RS256", "ES256"]
LEEWAY_SECONDS = 30


@lru_cache(maxsize=4)
def jwks_client(url: str) -> jwt.PyJWKClient:
    """Return a client that fetches and caches the signing keys published at ``url``."""
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=10)


class OIDCBearerAuthentication(BaseAuthentication):
    """Accept an access token that Authentik issued to the Nexus mobile client.

    The browser uses a session cookie instead; this is for the Android app,
    which signs in through the system browser and then holds tokens. The token
    is a signed JWT: its signature, issuer, audience and expiry are all
    checked, so a token made for another application is refused.

    A refused token answers 403, like a missing session does, because the
    session authentication is listed first. The app treats that as the signal
    to refresh its token or to sign in again.
    """

    keyword = b"bearer"

    def authenticate(self, request: Request) -> tuple[User, dict[str, object]] | None:
        """Return the user of a valid bearer token, or ``None`` when the request carries none."""
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != self.keyword:  # noqa: PLR2004
            return None
        if not settings.OIDC_MOBILE_CLIENT_ID:
            msg = "The mobile app is not enabled on this server."
            raise AuthenticationFailed(msg)
        token = parts[1].decode("ascii", errors="replace")
        try:
            key = jwks_client(settings.OIDC_MOBILE_ISSUER + "jwks/").get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=ALGORITHMS,
                audience=settings.OIDC_MOBILE_CLIENT_ID,
                issuer=settings.OIDC_MOBILE_ISSUER,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as error:
            msg = "The access token is not valid."
            raise AuthenticationFailed(msg) from error
        user = user_for_claims(claims)
        if not user.is_active:
            msg = "This user is not active."
            raise AuthenticationFailed(msg)
        return user, claims


@transaction.atomic
def user_for_claims(claims: dict[str, object]) -> User:
    """Return the Nexus user of an Authentik identity, creating one on first sight.

    Users are matched by Authentik's subject identifier, the same one that the
    browser login stores, so a person is one user however they sign in.
    """
    subject = str(claims["sub"])
    account = (
        SocialAccount.objects.filter(provider=settings.OIDC_PROVIDER_ID, uid=subject)
        .select_related("user")
        .first()
    )
    if account:
        return account.user
    base = str(claims.get("preferred_username") or subject)[:140]
    username, suffix = base, 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base}-{suffix}"
    user = User.objects.create_user(username=username, email=str(claims.get("email") or ""))
    SocialAccount.objects.create(user=user, provider=settings.OIDC_PROVIDER_ID, uid=subject, extra_data={})
    return user


class OIDCBearerScheme(OpenApiAuthenticationExtension):
    """Describes the bearer authentication in the OpenAPI schema."""

    target_class = OIDCBearerAuthentication
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        """Return the security scheme."""
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
