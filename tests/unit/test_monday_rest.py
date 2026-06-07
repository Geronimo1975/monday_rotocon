"""Unit tests for `scripts/_monday_rest.py` — the shared stdlib REST helpers.

These cover the token-loading and GraphQL-POST logic that both
`bootstrap_ki_integration.py` and `extend_ki_integration_columns.py` rely on,
including the failure paths (missing file, missing key, HTTP error, GraphQL
errors) that abort the process.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import _monday_rest as rest
import pytest


def test_load_token_reads_value(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("OTHER=x\nMONDAY_API_TOKEN=abc.def.ghi\nMORE=y\n", encoding="utf-8")
    assert rest.load_token(env) == "abc.def.ghi"


def test_load_token_strips_whitespace(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("MONDAY_API_TOKEN=   spaced-token   \n", encoding="utf-8")
    assert rest.load_token(env) == "spaced-token"


def test_load_token_missing_file_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        rest.load_token(tmp_path / "nope.env")
    assert "no .env" in str(excinfo.value)


def test_load_token_missing_key_exits(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SOMETHING_ELSE=1\n", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        rest.load_token(env)
    assert "MONDAY_API_TOKEN not found" in str(excinfo.value)


class _FakeResp:
    """Minimal context-manager stand-in for urlopen()'s return value."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_gql_returns_data_and_sends_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = req.headers
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp(json.dumps({"data": {"boards": []}}).encode())

    monkeypatch.setattr(rest.urllib.request, "urlopen", fake_urlopen)

    data = rest.gql("tok", "query { x }", {"v": 1}, user_agent="ua/1.0")
    assert data == {"boards": []}
    assert captured["url"] == rest.API_URL
    # urllib title-cases header keys.
    assert captured["headers"]["Authorization"] == "tok"
    assert captured["headers"]["Api-version"] == rest.API_VERSION
    assert captured["headers"]["User-agent"] == "ua/1.0"
    assert captured["body"] == {"query": "query { x }", "variables": {"v": 1}}


def test_gql_defaults_variables_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp(json.dumps({"data": {}}).encode())

    monkeypatch.setattr(rest.urllib.request, "urlopen", fake_urlopen)
    rest.gql("tok", "q")
    assert captured["body"]["variables"] == {}


def test_gql_http_error_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url=rest.API_URL,
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b"bad token"),
        )

    monkeypatch.setattr(rest.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as excinfo:
        rest.gql("tok", "q")
    assert "HTTP 401" in str(excinfo.value)
    assert "bad token" in str(excinfo.value)


def test_gql_graphql_errors_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req, timeout=None):
        return _FakeResp(json.dumps({"errors": [{"message": "boom"}]}).encode())

    monkeypatch.setattr(rest.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as excinfo:
        rest.gql("tok", "q")
    assert "GraphQL errors" in str(excinfo.value)
    assert "boom" in str(excinfo.value)
