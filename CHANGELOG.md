# Changelog

All notable changes to this package are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## 0.1.0 (2026-10-18)

First release.

- One MCP tool per operation of the ESGO API v1, built at start-up from the live
  OpenAPI spec; bundled copy as fallback.
- Read-only and data-changing tools marked from the API scopes.
- API errors returned as tool errors with code, field and Retry-After.
- Configuration via `ESGO_API_KEY` and `ESGO_BASE_URL`.
