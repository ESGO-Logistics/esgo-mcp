"""One generic call to the ESGO API, driven by an Operation from the spec."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx2

from ._version import __version__
from .spec import Operation


@dataclass(frozen=True)
class Outcome:
    ok: bool
    data: Any = None      # parsed JSON on success
    message: str = ""     # readable error for the assistant on failure


async def call(op: Operation, arguments: dict[str, Any] | None, *, api_key: str | None,
               base_url: str, http: httpx2.AsyncClient) -> Outcome:
    if not api_key:
        return Outcome(False, message=(
            "ESGO_API_KEY is not set. Add your ESGO API key to the MCP server configuration; "
            "keys are issued by ESGO, see https://es-go.de/developers."))

    args = dict(arguments or {})
    missing = [p for p in op.path_params if args.get(p) in (None, "")]
    if missing:
        return Outcome(False, message=f"Missing required argument(s): {', '.join(missing)}.")

    path = op.path
    for name in op.path_params:
        path = path.replace("{" + name + "}", quote(str(args.pop(name)), safe=""))
    query = {name: args.pop(name) for name in op.query_params if name in args}

    body = None
    if op.body_fields is not None:
        body = {name: value for name, value in args.items() if name in op.body_fields}
    unknown = sorted(set(args) - set(op.body_fields or ()))
    if unknown:
        return Outcome(False, message=f"Unknown argument(s) for {op.name}: {', '.join(unknown)}.")

    try:
        response = await http.request(
            op.method,
            base_url.rstrip("/") + path,
            params=query or None,
            json=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": f"esgo-mcp/{__version__}",
            },
        )
    except httpx2.HTTPError as exc:
        return Outcome(False, message=f"Could not reach {base_url}: {exc}")

    try:
        data = response.json()
    except ValueError:
        data = None

    if response.is_success:
        return Outcome(True, data=data)
    return Outcome(False, message=_error_text(response, data))


def _error_text(response: httpx2.Response, data: Any) -> str:
    """The ESGO error envelope as one line the assistant can act on."""
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return f"[{response.status_code}] {response.reason_phrase or 'Unexpected response'}"
    text = f"[{response.status_code}] {error.get('code') or 'error'}: {error.get('message') or ''}".rstrip()
    if error.get("param"):
        text += f" (param: {error['param']})"
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        text += f" Retry after {retry_after} seconds."
    request_id = response.headers.get("X-Request-Id")
    if request_id:
        text += f" Request id: {request_id}."
    return text
