"""Real MCP round trips (in-process client) against a mock ESGO API."""

import json

import httpx2
import pytest
from mcp import Client

from esgo_mcp.server import create_server
from esgo_mcp.spec import bundled_spec

pytestmark = pytest.mark.anyio

MATCH = {
    "object": "match", "route_id": "r_1", "origin_area": "Duisburg", "destination_area": "München",
    "departure_window": {"start": "2026-10-20T08:00:00", "end": "2026-10-20T12:00:00"},
    "free_capacity_kg": 8000, "free_capacity_ldm": 6.2, "instant_bookable": False,
    "match_score": 87.5, "booking_url": "https://es-go.de/booking_request/r_1",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeApi:
    def __init__(self, answer):
        self.answer = answer
        self.seen = []

    def __call__(self, request):
        self.seen.append(request)
        return self.answer(request)


def _server(answer, api_key="esgo_live_test"):
    api = FakeApi(answer)
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(api))
    server = create_server(bundled_spec(), api_key=api_key, base_url="https://api.es-go.de", http=http)
    return server, api


async def test_lists_one_tool_per_operation_with_annotations():
    server, _ = _server(lambda r: httpx2.Response(500))
    async with Client(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == {"me_retrieve", "matches_search", "open_requests_create", "open_requests_list_matches"}
    assert tools["matches_search"].annotations.read_only_hint is True
    assert tools["open_requests_create"].annotations.read_only_hint is False
    assert tools["open_requests_create"].annotations.destructive_hint is False
    assert "weight_kg" in tools["matches_search"].input_schema["required"]


async def test_search_sends_body_and_key_and_returns_structured_result():
    body = {"object": "match_search", "distance_km": 612.4, "match_count": 1, "data": [MATCH]}
    server, api = _server(lambda r: httpx2.Response(200, json=body))
    async with Client(server) as client:
        result = await client.call_tool("matches_search", {
            "origin": "47057 Duisburg", "destination": "80331 München", "weight_kg": 12000})

    assert result.is_error is False
    assert result.structured_content == body
    assert json.loads(result.content[0].text)["match_count"] == 1
    request = api.seen[0]
    assert (request.method, str(request.url)) == ("POST", "https://api.es-go.de/v1/matches/search")
    assert request.headers["Authorization"] == "Bearer esgo_live_test"
    assert request.headers["User-Agent"].startswith("esgo-mcp/")
    assert json.loads(request.content) == {
        "origin": "47057 Duisburg", "destination": "80331 München", "weight_kg": 12000}


async def test_path_parameter_goes_into_the_url_escaped():
    server, api = _server(lambda r: httpx2.Response(200, json={"object": "list", "data": [MATCH]}))
    async with Client(server) as client:
        result = await client.call_tool("open_requests_list_matches", {"request_id": "or/1"})

    assert result.is_error is False
    assert api.seen[0].url.raw_path == b"/v1/open-requests/or%2F1/matches"
    assert api.seen[0].content == b""


async def test_api_error_is_a_tool_error_the_assistant_can_act_on():
    def answer(request):
        return httpx2.Response(
            429, headers={"Retry-After": "3600", "X-Request-Id": "req_1"},
            json={"error": {"type": "rate_limit_error", "code": "daily_quota_exceeded",
                            "message": "Daily quota reached", "param": None}})

    server, _ = _server(answer)
    async with Client(server) as client:
        result = await client.call_tool("me_retrieve", {})

    assert result.is_error is True
    text = result.content[0].text
    assert "[429] daily_quota_exceeded" in text
    assert "3600" in text and "req_1" in text


async def test_validation_error_names_the_field():
    server, _ = _server(lambda r: httpx2.Response(422, json={"error": {
        "type": "invalid_request_error", "code": "invalid_parameter",
        "message": "End must be after start.", "param": "time_windows.0.end"}}))
    async with Client(server) as client:
        result = await client.call_tool("matches_search", {
            "origin": "A", "destination": "B", "weight_kg": 1})

    assert result.is_error is True
    assert "(param: time_windows.0.end)" in result.content[0].text


async def test_without_api_key_tools_are_listed_but_calls_explain_the_key():
    server, api = _server(lambda r: httpx2.Response(200, json={}), api_key=None)
    async with Client(server) as client:
        assert len((await client.list_tools()).tools) == 4
        result = await client.call_tool("me_retrieve", {})

    assert result.is_error is True
    assert "ESGO_API_KEY" in result.content[0].text
    assert api.seen == []


async def test_unknown_argument_fails_before_any_request():
    server, api = _server(lambda r: httpx2.Response(200, json={}))
    async with Client(server) as client:
        result = await client.call_tool("open_requests_list_matches", {"request_id": "x", "foo": 1})

    assert result.is_error is True
    assert "foo" in result.content[0].text
    assert api.seen == []


async def test_network_error_is_a_tool_error():
    def boom(request):
        raise httpx2.ConnectError("refused", request=request)

    server, _ = _server(boom)
    async with Client(server) as client:
        result = await client.call_tool("me_retrieve", {})

    assert result.is_error is True
    assert "Could not reach" in result.content[0].text


async def test_api_key_never_appears_in_results():
    server, _ = _server(lambda r: httpx2.Response(401, json={"error": {
        "type": "authentication_error", "code": "invalid_api_key", "message": "Unknown key", "param": None}}),
        api_key="esgo_live_secret123")
    async with Client(server) as client:
        result = await client.call_tool("me_retrieve", {})

    assert "esgo_live_secret123" not in result.content[0].text
