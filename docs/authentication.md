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

The app is the web interface packaged with Capacitor, so it cannot use the
browser's session cookie. It signs in with OpenID Connect instead:

1. On first start the app asks for the address of the Nexus server and reads
   `/api/config/` from it, which names the Authentik issuer and the app's
   client id. One build of the app therefore works with any deployment.
2. "Sign in with a passkey" opens Authentik in the system browser
   (authorization code flow with PKCE, RFC 8252). The login flow is the same
   passkey-only flow as in the browser, and the app never sees a credential.
3. Authentik returns to the app through the address
   `fi.agx.nexus://oauth/callback`, and the app exchanges the code for an
   access token and a refresh token. They are kept in the device's secure
   storage, encrypted with a key in the Android Keystore, and are excluded
   from backups.
4. The app sends the access token with every API request. Django checks its
   signature against Authentik's published keys, and its issuer, audience and
   expiry, so a token issued for another application is refused. Access tokens
   last ten minutes and are renewed with the refresh token, which lasts 30 days.

In Authentik the app is its own public client, `Nexus Android`, created by
`authentik/blueprints/nexus-providers.yaml`. Its id is `OIDC_MOBILE_CLIENT_ID`
(default `nexus-android`). A person is the same Nexus user in the browser and
in the app, as both logins are matched by Authentik's subject identifier.

The app's pages are served from inside the app at the origin
`https://localhost`, so the API allows that origin for cross-origin requests
(`/api/` only, without cookies).

The app reaches the server like any other client, so with the default Nginx
configuration the phone must be on an allowed network, for example through a
VPN.

## Agents

Each agent gets its own bearer token, bound to one user, with read or write
access per feature. See {doc}`mcp`.
