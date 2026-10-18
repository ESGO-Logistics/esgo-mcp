"""Tools come from the spec alone: names, schemas, read/write."""

import json

import httpx2
import pytest

from esgo_mcp.spec import bundled_spec, load_spec, operations, resolve

SPEC = bundled_spec()


def _op(name):
    return next(op for op in operations(SPEC) if op.name == name)


def _all_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_keys(item)


def test_one_tool_per_operation_id():
    ids = {op["operationId"] for item in SPEC["paths"].values()
           for op in item.values() if isinstance(op, dict) and "operationId" in op}
    assert {op.name for op in operations(SPEC)} == ids


def test_input_schemas_are_self_contained_json_schema():
    for op in operations(SPEC):
        keys = set(_all_keys(op.input_schema))
        assert "$ref" not in keys, op.name
        assert "nullable" not in keys, op.name
        assert op.input_schema["type"] == "object"
        assert op.input_schema["additionalProperties"] is False


def test_body_fields_and_required_come_from_the_request_schema():
    search = _op("matches_search")
    request = SPEC["components"]["schemas"]["MatchSearchRequest"]
    assert set(search.body_fields) == set(request["properties"])
    assert search.input_schema["required"] == sorted(request["required"])
    assert search.path_params == ()


def test_path_parameter_becomes_a_required_argument():
    list_matches = _op("open_requests_list_matches")
    assert list_matches.path_params == ("request_id",)
    assert "request_id" in list_matches.input_schema["required"]
    assert list_matches.input_schema["properties"]["request_id"]["description"]
    assert list_matches.body_fields is None


def test_read_or_write_follows_the_api_scope():
    assert _op("me_retrieve").read_only                 # GET without scope
    assert _op("matches_search").read_only              # POST, but scope matches:read
    assert _op("open_requests_list_matches").read_only  # open_requests:read
    assert not _op("open_requests_create").read_only    # open_requests:write


def test_descriptions_name_the_scope():
    assert "matches:read" in _op("matches_search").description


def test_nested_refs_are_inlined_and_nullable_becomes_json_schema():
    create = _op("open_requests_create")
    windows = create.input_schema["properties"]["time_windows"]
    assert windows["items"]["properties"]["start"]["format"] == "date-time"
    target_price = create.input_schema["properties"]["target_price_eur"]
    assert target_price["type"] == ["number", "null"]


def test_recursive_schemas_do_not_loop():
    schemas = {"Node": {"type": "object", "properties": {"child": {"$ref": "#/components/schemas/Node"}}}}
    resolved = resolve({"$ref": "#/components/schemas/Node"}, schemas)
    # Node is inlined once; its self-reference stops right there instead of recursing.
    assert resolved["type"] == "object"
    assert resolved["properties"]["child"] == {"type": "object"}


def test_unsupported_operations_are_skipped_not_fatal():
    spec = json.loads(json.dumps(SPEC))
    spec["paths"]["/v1/upload"] = {"post": {
        "operationId": "files_upload",
        "requestBody": {"content": {"multipart/form-data": {"schema": {"type": "object"}}}},
        "responses": {"200": {"description": "ok"}},
    }}
    names = {op.name for op in operations(spec)}
    assert "files_upload" not in names
    assert "matches_search" in names


def test_live_spec_is_preferred():
    live = {"openapi": "3.0.3", "paths": {}, "info": {"title": "live"}}
    transport = httpx2.MockTransport(lambda request: httpx2.Response(200, json=live))
    spec, source = load_spec("https://api.example", transport=transport)
    assert source == "live"
    assert spec["info"]["title"] == "live"


@pytest.mark.parametrize("answer", [
    lambda request: httpx2.Response(503, json={"error": {}}),
    lambda request: httpx2.Response(200, text="<html>maintenance</html>"),
    lambda request: httpx2.Response(200, json={"not": "a spec"}),
])
def test_falls_back_to_the_bundled_spec(answer):
    spec, source = load_spec("https://api.example", transport=httpx2.MockTransport(answer))
    assert source == "bundled"
    assert spec == SPEC


def test_falls_back_when_the_api_is_unreachable():
    def boom(request):
        raise httpx2.ConnectError("refused", request=request)

    spec, source = load_spec("https://api.example", transport=httpx2.MockTransport(boom))
    assert source == "bundled"
