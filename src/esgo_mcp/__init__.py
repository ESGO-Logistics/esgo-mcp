"""MCP server for the ESGO API.

Every operation of the public API v1 becomes an MCP tool. The tools are built
at start-up from the live OpenAPI spec (https://api.es-go.de/v1/openapi.json),
so a new API endpoint is available without a new release of this package.
"""

from ._version import __version__

__all__ = ["__version__"]
