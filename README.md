# ESGO MCP server

<!-- mcp-name: io.github.ESGO-Logistics/esgo-mcp -->

*[Deutsche Version weiter unten](#esgo-mcp-server-deutsch)*

Lets AI assistants (Claude, Cursor, VS Code, Windsurf and others that speak the
[Model Context Protocol](https://modelcontextprotocol.io)) use the
[ESGO API](https://es-go.de/developers): search for matching empty-run capacity
in road freight and publish open transport requests, in plain language.

> "Find free capacity from 47057 Duisburg to 80331 München for 12 t next week."

> **Alpha.** The tools follow the ESGO API v1 automatically (see below).

## How it works

Every operation of the ESGO API becomes one tool, built at start-up from the
live OpenAPI spec at [api.es-go.de/v1/openapi.json](https://api.es-go.de/v1/openapi.json).
When ESGO adds an endpoint, it is available as a tool the next time the server
starts, without updating this package. If the API cannot be reached at
start-up, the server uses the copy of the spec it ships with.

Tools that only read (`me_retrieve`, `matches_search`, `open_requests_list_matches`)
are marked read-only; tools that create data (`open_requests_create`) are not, so
your assistant asks before calling them.

## Access

You need an ESGO API key; there is no self-service sign-up yet. Request access
at [es-go.de/developers](https://es-go.de/developers). The key stays on your
machine and is only sent to the ESGO API.

## Installation

The server runs locally and is started by your AI app. You need
[uv](https://docs.astral.sh/uv/); `uvx` downloads and runs the package on demand.

**Claude Desktop** (`claude_desktop_config.json`), **Cursor** (`.cursor/mcp.json`),
**Windsurf** and others with the same format:

```json
{
  "mcpServers": {
    "esgo": {
      "command": "uvx",
      "args": ["esgo-mcp"],
      "env": { "ESGO_API_KEY": "esgo_live_..." }
    }
  }
}
```

**Claude Code:**

```sh
claude mcp add esgo -e ESGO_API_KEY=esgo_live_... -- uvx esgo-mcp
```

**VS Code** (`.vscode/mcp.json`):

```json
{
  "servers": {
    "esgo": {
      "command": "uvx",
      "args": ["esgo-mcp"],
      "env": { "ESGO_API_KEY": "esgo_live_..." }
    }
  }
}
```

Without uv: `pip install esgo-mcp`, then use `esgo-mcp` as the command.

| Variable | Meaning |
|---|---|
| `ESGO_API_KEY` | your ESGO API key (required for calls) |
| `ESGO_BASE_URL` | optional, default `https://api.es-go.de` |

## Tools (as of October 2026)

The list comes from the API itself, so it may already be longer when you read this.

| Tool | Endpoint | Changes data |
|---|---|---|
| `me_retrieve` | `GET /v1/me` | no |
| `matches_search` | `POST /v1/matches/search` | no |
| `open_requests_create` | `POST /v1/open-requests` | yes |
| `open_requests_list_matches` | `GET /v1/open-requests/{request_id}/matches` | no |

Errors of the API (for example `[429] daily_quota_exceeded` or
`[422] invalid_parameter (param: weight_kg)`) are returned to the assistant as
tool errors, so it can correct the input or tell you.

## Related

- Python SDK: [pypi.org/project/esgo](https://pypi.org/project/esgo/)
- .NET SDK: [nuget.org/packages/Esgo](https://www.nuget.org/packages/Esgo)
- API reference: [api.es-go.de/v1/docs](https://api.es-go.de/v1/docs)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## License

MIT, see [LICENSE](LICENSE).

---

# ESGO MCP server (Deutsch)

Damit können KI-Assistenten (Claude, Cursor, VS Code, Windsurf und andere, die
das Model Context Protocol sprechen) die [ESGO API](https://es-go.de/developers)
nutzen: passende Leerfahrten im Straßengüterverkehr suchen und offene
Transportanfragen einstellen, in normaler Sprache.

**So funktioniert es:** Jeder Endpunkt der ESGO API wird zu einem Werkzeug. Der
Server baut die Werkzeuge beim Start aus der aktuellen OpenAPI-Spezifikation.
Neue Endpunkte sind damit beim nächsten Start da, ohne Update dieses Pakets. Ist
die API beim Start nicht erreichbar, nimmt der Server die mitgelieferte Kopie.
Werkzeuge, die Daten anlegen, sind entsprechend markiert; der Assistent fragt
vorher nach.

**Zugang:** Du brauchst einen API-Schlüssel von ESGO, anzufragen unter
[es-go.de/developers](https://es-go.de/developers). Der Schlüssel bleibt auf
deinem Rechner und geht nur an die ESGO API.

**Einrichtung:** siehe die Konfigurationsbeispiele oben. Benötigt wird
[uv](https://docs.astral.sh/uv/); `uvx esgo-mcp` lädt und startet das Paket.

**Lizenz:** MIT, siehe [LICENSE](LICENSE).
