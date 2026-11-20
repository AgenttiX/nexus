# MCP server

The MCP server gives AI agents access to a user's data. It targets Open WebUI,
OpenCode and Claude Code, and local models with context windows of
60 000–140 000 tokens.

- **Transport**: Streamable HTTP at `https://<NEXUS_HOST>/mcp`, stateless.
- **Authentication**: a bearer token in the `Authorization` header, the one
  method all three clients support.
- **Access**: a token belongs to one user and has a scope of read or write for
  each feature it may use. Write includes read. Tools outside a token's scopes
  are not listed and cannot be called, which also keeps the tool list short.
- **Context use**: a small number of tools with one-line descriptions and
  compact text results. Longer guidance lives in the Agent Skills under
  `skills/`, which clients load only when needed.

## Tools

| Tool | Scope | Purpose |
|---|---|---|
| `whoami` | any token | Show the user and scopes of the connection |
| `news_digest` | `news:read` | The news digest of a day, optionally with article links |
| `finance_summary` | `finance:read` | Income and expenses by category and month for a period |
| `transactions` | `finance:read` | Bank transactions for a period, optionally matching a text |
| `portfolio` | `investments:read` | Holdings with latest prices, values and gains |
| `asset_prices` | `investments:read` | Recent daily closing prices of one asset |
| `food_menu` | `food:read` | UniCafe menus for a date, for favourites or a named restaurant |
| `calendar_events` | `calendars:read` | Events between two dates |
| `sleep_summary` | `sleep:read` | Bedtime, wake-up, duration and weekend jet lag statistics for a period |
| `sleep_nights` | `sleep:read` | Individual sleep records for a period |

## Skills

The directories under `skills/` are Agent Skills. Claude Code and OpenCode read
them from `.claude/skills/` (in a project or in the home directory), so copy or
symlink them there. In Open WebUI, import each `SKILL.md` under Workspace →
Skills.

## Agent tokens

Create one token per agent, so that each can be limited and revoked on its own:

```bash
docker compose exec web python manage.py create_agent_token alice assistant sleep=read finance=write
```

The command prints the token once. Only a hash of it is stored, so a lost
token cannot be recovered: delete it and create a new one. The features are
`news`, `finance`, `investments`, `timetracking`, `calendars`, `sleep` and
`food`; a feature that is not listed is denied.

Signed-in users can also manage their tokens through the REST API at
`/api/agent-tokens/` (list, create, delete). Tokens cannot be edited, so that a
change of access is never silent. Administrators can inspect and delete tokens
in the Django admin.

A token stops working when it is deleted, when it expires, or when its user is
deactivated.

## Connecting clients

Claude Code:

```bash
claude mcp add --transport http nexus https://nexus.example.com/mcp --header "Authorization: Bearer $NEXUS_TOKEN"
```

OpenCode (`opencode.json`):

```json
{
  "mcp": {
    "nexus": {
      "type": "remote",
      "url": "https://nexus.example.com/mcp",
      "oauth": false,
      "headers": { "Authorization": "Bearer {env:NEXUS_TOKEN}" }
    }
  }
}
```

Open WebUI: Admin Settings → External Tools → add a server of type
"MCP (Streamable HTTP)" with the URL above and Bearer authentication.

## Adding tools

A feature app registers its tools in its `mcp.py` module:

```python
from apps.accounts.models import Feature
from apps.mcp_server.auth import current_user
from apps.mcp_server.server import nexus_tool


@nexus_tool(Feature.SLEEP)
def sleep_summary(start: str, end: str) -> str:
    """Summarise sleep between two dates."""
    return services.summary(current_user(), start, end)
```

The docstring is the description that the model reads: keep it to one line.
Tools get their user only from `current_user()`, never from an argument.

## Code reference

```{eval-rst}
.. automodule:: apps.mcp_server.server
   :members: nexus_tool

.. automodule:: apps.mcp_server.auth
   :members:
```
