"""server.json (MCP Registry) must agree with the package, or the registry rejects it."""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = json.loads((ROOT / "server.json").read_text("utf-8"))
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]


def test_versions_match_the_package():
    assert SERVER["version"] == PROJECT["version"]
    (package,) = SERVER["packages"]
    assert package["version"] == PROJECT["version"]
    assert package["identifier"] == PROJECT["name"]
    assert package["registryType"] == "pypi"
    assert package["transport"] == {"type": "stdio"}


def test_readme_proves_ownership_with_the_server_name():
    # The registry looks for "mcp-name: <name>" in the README that PyPI shows.
    names = re.findall(r"mcp-name: (\S+)", (ROOT / "README.md").read_text("utf-8"))
    assert names == [SERVER["name"]]


def test_name_is_in_the_github_namespace_of_the_repository():
    assert SERVER["name"] == "io.github.ESGO-Logistics/esgo-mcp"
    assert SERVER["repository"]["url"] == "https://github.com/ESGO-Logistics/esgo-mcp"


def test_api_key_is_declared_as_required_secret():
    variables = {v["name"]: v for v in SERVER["packages"][0]["environmentVariables"]}
    assert variables["ESGO_API_KEY"]["isRequired"] is True
    assert variables["ESGO_API_KEY"]["isSecret"] is True
    assert variables["ESGO_BASE_URL"]["isRequired"] is False
