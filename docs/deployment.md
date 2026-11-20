# Deployment

## Requirements

- A host with Docker Compose.
- An Nginx set up as in [nginx-server](https://github.com/AgenttiX/nginx-server),
  on the same host or another one.
- Two hostnames with TLS certificates: one for Nexus and one for Authentik.

## Steps

1. Copy `.env.example` to `.env` and fill in every empty value. Generate
   secrets with for example `openssl rand -base64 48`. Never commit `.env`.
2. Start the stack:

   ```bash
   docker compose up -d
   ```

3. Set the hostnames, certificate paths and allowed networks in
   `nginx/nexus-servers.conf` and `nginx/nexus-settings.conf`, then install
   them on the Nginx host:

   ```bash
   sudo nginx/nginx.sh
   ```

4. Open `https://<AUTHENTIK_HOST>/if/flow/initial-setup/` once to create the
   Authentik administrator. Then follow {doc}`authentication` to create users
   and register passkeys.

## Secrets to keep

`DJANGO_SECRET_KEY` and `FIELD_ENCRYPTION_SALT` together encrypt the secrets
stored in the database, such as calendar addresses. Back them up with the
database: without them those values cannot be read. To change the secret key,
put the old one in `DJANGO_SECRET_KEY_FALLBACKS`.

## Published ports

`web`, `mcp` and `authentik-server` publish their ports on `BIND_ADDRESS`. Keep
it at `127.0.0.1` while Nginx runs on the same host. When Nginx moves to another
machine, set it to the Docker host's address on the network between the two,
and change the `upstream` addresses in `nginx/nexus-servers.conf` to match.

## Updates

Images are tagged with the version and published to GitHub Container Registry.
The backend containers carry the `wud.watch` label, so What's Up Docker
(`docker compose --profile wud up -d`) reports new versions.

## ActivityWatch data

Point `AW_SYNC_DIR` at the directory that your devices sync to the server (for
example with Syncthing). It is mounted read-only into the `worker` container.
