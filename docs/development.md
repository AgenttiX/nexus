# Development

## Setup

```bash
docker compose -f compose.dev.yaml up -d   # PostgreSQL and Redis
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

```bash
cd frontend
npm ci
npm run dev
```

The Vite development server proxies `/api`, `/accounts` and `/admin` to Django.

Install the Git hooks once with `prek install`.

## Checks

| Check | Command (in `backend/`) |
|---|---|
| Lint and format | `uv run ruff check .` and `uv run ruff format .` |
| Types | `uv run pyrefly check` |
| Tests, with 100 % coverage required | `uv run pytest` |
| API schema | `uv run python manage.py spectacular --validate --fail-on-warn` |
| Documentation | `uv run sphinx-build -W ../docs ../docs/_build` |

| Check | Command (in `frontend/`) |
|---|---|
| Lint | `npm run lint` |
| Tests, with 100 % coverage required | `npm test` |
| Types and build | `npm run build` |

After changing the REST API, regenerate the TypeScript types with
`npm run gen:api` (in `frontend/`).

## Rules

- Type annotations and tests are required for all code. Exclusions are listed
  in `backend/pyproject.toml`.
- Before writing new functionality, look for a maintained library with a
  licence compatible with MIT.
- The repository is public. Keep hostnames, secrets and personal data in
  `.env`, never in committed files.

## Android

The Android project is in `frontend/android/`. It needs JDK 21 and the Android
SDK (platform 37).

```bash
cd frontend
npm run android:sync      # build the web interface and copy it into the Android project
cd android
./gradlew assembleDebug   # the APK is written to app/build/outputs/apk/debug/
```

Code that runs only in the app is in `frontend/src/native/`. Tests replace the
device with fakes (`frontend/src/test-native.ts`); the login through the system
browser (`oidc.ts`) can only be tried on a device.

### Releases

Pushing a tag `v*.*.*` builds a signed APK and attaches it to the GitHub
release. The signing key is read from these repository secrets, and is never
stored in the repository:

| Secret | Content |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | The keystore file, base64-encoded |
| `ANDROID_KEYSTORE_PASSWORD` | Password of the keystore |
| `ANDROID_KEY_ALIAS` | Alias of the key |
| `ANDROID_KEY_PASSWORD` | Password of the key |

Create the keystore once with `keytool -genkeypair -v -keystore release.jks
-keyalg RSA -keysize 4096 -validity 10000 -alias nexus` and keep a copy: an
app can only be updated by an APK signed with the same key.
