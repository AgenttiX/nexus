# MCP server

```{note}
The MCP server is designed but not implemented yet.
```

The MCP server gives AI agents access to a user's data. It targets Open WebUI,
OpenCode and Claude Code, and local models with context windows of
60 000–140 000 tokens.

- **Transport**: Streamable HTTP at `/mcp`.
- **Authentication**: a static bearer token in the `Authorization` header, the
  one method all three clients support.
- **Access**: a token belongs to one user and has a scope of none, read or
  write for each feature. Tools outside a token's scopes are not listed at all,
  which also keeps the tool list short.
- **Context use**: a small number of tools with one-line descriptions and
  compact text results. Longer guidance lives in the Agent Skills under
  `skills/`, which clients load only when needed.
