# Authentication

## Browser

Nexus has no login form of its own. Django sends the browser to Authentik
(OpenID Connect) and keeps the session in an HttpOnly, Secure cookie, so the web
interface never handles a token.

The login flow that Authentik uses for Nexus is defined in
`authentik/blueprints/nexus-webauthn.yaml`:

- There is no password stage. Login needs a WebAuthn credential.
- User verification (PIN or biometrics) is required, which implies user
  presence.
- Resident (discoverable) keys are required when registering.
- Only these authenticator models can be registered or used: YubiKey 5 Series
  with NFC, Windows Hello, Google Password Manager and iCloud Keychain. The
  allowlist is the `allowed_aaguids` list at the top of the blueprint.

`authentik/blueprints/nexus-providers.yaml` creates the OIDC provider and the
Nexus application. Its client ID, secret and hostname come from `.env`, so
Django and Authentik always agree.

## First passkey for a user

A new user has no passkey and cannot sign in to register one. As the Authentik
administrator, create the user, then create a recovery link for them in the
Authentik admin interface (Directory → Users → the user → Create recovery
link). With that link the user signs in once and registers a passkey under
Settings → MFA Devices.

## Android

Planned: the app signs in with OIDC authorization code flow and PKCE through
the system browser, so passkeys work as they do in Chrome, and sends the
resulting token to the API.

## Agents

Planned: each agent gets its own bearer token, bound to one user, with a scope
of none, read or write per feature. See {doc}`mcp`.
