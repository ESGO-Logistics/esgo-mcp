"""OpenAPI spec -> MCP tools.

The spec is loaded live from the API; if that fails, the copy shipped with the
package is used (kept current by .github/workflows/regenerate.yml). Nothing
here knows individual endpoints: whatever the spec describes becomes a tool.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from importlib import resources
from typing import Any

import httpx2

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.es-go.de"
SPEC_PATH = "/v1/openapi.json"
_METHODS = ("get", "post", "put", "patch", "delete")
_SCHEMA_REF = "#/components/schemas/"


@dataclass(frozen=True)
class Operation:
    """One API operation, ready to be offered as an MCP tool."""

    name: str
    method: str
    path: str
    title: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool
    path_params: tuple[str, ...]
    query_params: tuple[str, ...]
    body_fields: tuple[str, ...] | None  # None: the operation takes no JSON body


def bundled_spec() -> dict[str, Any]:
    text = resources.files("esgo_mcp").joinpath("openapi.json").read_text(encoding="utf-8")
    return json.loads(text)


def load_spec(base_url: str = DEFAULT_BASE_URL, *, timeout: float = 5.0,
              transport: httpx2.BaseTransport | None = None) -> tuple[dict[str, Any], str]:
    """Live spec from the API, else the bundled copy. Returns (spec, "live" | "bundled")."""
    try:
        with httpx2.Client(timeout=timeout, transport=transport) as http:
            response = http.get(base_url.rstrip("/") + SPEC_PATH)
            response.raise_for_status()
            spec = response.json()
        if _looks_like_spec(spec):
            return spec, "live"
        logger.warning("Live spec from %s is not an OpenAPI document; using the bundled copy.", base_url)
    except (httpx2.HTTPError, ValueError) as exc:
        logger.warning("Could not load the live spec from %s (%s); using the bundled copy.", base_url, exc)
    return bundled_spec(), "bundled"


def _looks_like_spec(spec: Any) -> bool:
    return isinstance(spec, dict) and "openapi" in spec and isinstance(spec.get("paths"), dict)


def operations(spec: dict[str, Any]) -> list[Operation]:
    """Every operation with an operationId, sorted by name."""
    schemas = spec.get("components", {}).get("schemas", {})
    result = []
    for path, item in spec.get("paths", {}).items():
        shared_params = item.get("parameters", [])
        for method in _METHODS:
            op = item.get(method)
            if not isinstance(op, dict) or "operationId" not in op:
                continue
            try:
                result.append(_operation(path, method, op, shared_params, schemas))
            except ValueError as exc:
                logger.warning("Skipping %s %s: %s", method.upper(), path, exc)
    return sorted(result, key=lambda o: o.name)


def _operation(path: str, method: str, op: dict[str, Any], shared_params: list[dict[str, Any]],
               schemas: dict[str, Any]) -> Operation:
    properties: dict[str, Any] = {}
    required: set[str] = set()
    path_params, query_params = [], []

    for param in [*shared_params, *op.get("parameters", [])]:
        where, name = param.get("in"), param.get("name")
        if where not in ("path", "query") or not name:
            continue  # headers and cookies are not tool arguments
        schema = resolve(param.get("schema", {"type": "string"}), schemas)
        if param.get("description"):
            schema = {**schema, "description": param["description"]}
        properties[name] = schema
        if where == "path":
            path_params.append(name)
            required.add(name)
        else:
            query_params.append(name)
            if param.get("required"):
                required.add(name)

    body_fields: tuple[str, ...] | None = None
    body = op.get("requestBody", {}).get("content", {})
    if body:
        if "application/json" not in body:
            raise ValueError("only JSON request bodies are supported")
        schema = resolve(body["application/json"].get("schema", {}), schemas)
        body_props = schema.get("properties", {})
        clash = set(body_props) & set(properties)
        if clash:
            raise ValueError(f"body fields clash with parameters: {sorted(clash)}")
        properties.update(body_props)
        required.update(schema.get("required", []))
        body_fields = tuple(body_props)

    scope = op.get("x-esgo-scope")
    title = op.get("summary") or op["operationId"]
    description = "\n\n".join(p for p in (op.get("summary"), op.get("description")) if p)
    if scope:
        description += f"\n\nRequired API key scope: {scope}."

    return Operation(
        name=op["operationId"],
        method=method.upper(),
        path=path,
        title=title,
        description=description,
        input_schema={
            "type": "object",
            "properties": properties,
            "required": sorted(required),
            "additionalProperties": False,
        },
        read_only=_is_read_only(method, scope),
        path_params=tuple(path_params),
        query_params=tuple(query_params),
        body_fields=body_fields,
    )


def _is_read_only(method: str, scope: str | None) -> bool:
    """The API's scopes say what a call does: "...:read" reads, "...:write" changes data."""
    if scope:
        return scope.endswith(":read")
    return method == "get"


def resolve(node: Any, schemas: dict[str, Any], _seen: tuple[str, ...] = ()) -> Any:
    """Inline every $ref to components/schemas (MCP clients expect self-contained schemas).

    Also turns OpenAPI 3.0 `nullable: true` into JSON Schema (`type: [..., "null"]`).
    """
    if isinstance(node, list):
        return [resolve(item, schemas, _seen) for item in node]
    if not isinstance(node, dict):
        return node

    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith(_SCHEMA_REF):
        name = ref[len(_SCHEMA_REF):]
        if name in _seen:  # recursive schema: stop instead of looping
            return {"type": "object"}
        extra = {k: v for k, v in node.items() if k != "$ref"}
        return {**resolve(copy.deepcopy(schemas.get(name, {})), schemas, (*_seen, name)), **extra}

    out = {key: resolve(value, schemas, _seen) for key, value in node.items()}
    if out.pop("nullable", False) and isinstance(out.get("type"), str):
        out["type"] = [out["type"], "null"]
    return out
