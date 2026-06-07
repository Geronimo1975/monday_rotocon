"""Unit tests for the idempotency logic in
`scripts/extend_ki_integration_columns.py`.

The script lives outside the package; we import it via sys.path
gymnastics so pytest can exercise the pure functions inside.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "extend_ki_integration_columns.py"
)


@pytest.fixture(scope="module")
def script_module():
    spec = importlib.util.spec_from_file_location("extend_cols", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_compute_missing_columns_empty_board(script_module):
    existing: list[dict] = []
    desired = [
        {"title": "Status", "type": "status", "defaults": "{}"},
        {"title": "Owner", "type": "people", "defaults": "{}"},
    ]
    missing = script_module.compute_missing_columns(existing, desired)
    assert [c["title"] for c in missing] == ["Status", "Owner"]


def test_compute_missing_columns_partial_overlap(script_module):
    existing = [
        {"id": "name", "title": "Name", "type": "name"},
        {"id": "status_x", "title": "Status", "type": "status"},
    ]
    desired = [
        {"title": "Status", "type": "status", "defaults": "{}"},
        {"title": "Owner", "type": "people", "defaults": "{}"},
    ]
    missing = script_module.compute_missing_columns(existing, desired)
    assert [c["title"] for c in missing] == ["Owner"]


def test_compute_missing_columns_full_overlap(script_module):
    existing = [
        {"id": "name", "title": "Name", "type": "name"},
        {"id": "s", "title": "Status", "type": "status"},
        {"id": "p", "title": "Owner", "type": "people"},
    ]
    desired = [
        {"title": "Status", "type": "status", "defaults": "{}"},
        {"title": "Owner", "type": "people", "defaults": "{}"},
    ]
    missing = script_module.compute_missing_columns(existing, desired)
    assert missing == []


def test_columns_plan_has_twelve_specs(script_module):
    # The roadmap page depends on exactly these 12 columns existing.
    assert len(script_module.COLUMNS_PLAN) == 12
    assert all({"title", "type", "defaults"} <= set(c) for c in script_module.COLUMNS_PLAN)


def test_fetch_existing_columns_unwraps_board(script_module, monkeypatch):
    monkeypatch.setattr(
        script_module,
        "gql",
        lambda *a, **k: {"boards": [{"columns": [{"id": "c1", "title": "Status", "type": "status"}]}]},
    )
    cols = script_module.fetch_existing_columns("tok", 5096182046)
    assert cols == [{"id": "c1", "title": "Status", "type": "status"}]


def test_create_column_returns_new_id(script_module, monkeypatch):
    captured: dict = {}

    def fake_gql(token, query, variables=None):
        captured["variables"] = variables
        return {"create_column": {"id": "new123", "title": "Owner", "type": "people"}}

    monkeypatch.setattr(script_module, "gql", fake_gql)
    spec = {"title": "Owner", "type": "people", "defaults": "{}"}
    new_id = script_module.create_column("tok", 5096182046, spec)
    assert new_id == "new123"
    assert captured["variables"]["title"] == "Owner"
    assert captured["variables"]["type"] == "people"


def test_main_nothing_to_do_when_all_present(script_module, monkeypatch, capsys):
    monkeypatch.setattr(script_module, "load_token", lambda: "tok")
    full = [{"id": str(i), "title": c["title"], "type": c["type"]}
            for i, c in enumerate(script_module.COLUMNS_PLAN)]
    monkeypatch.setattr(script_module, "fetch_existing_columns", lambda *a, **k: full)

    def _explode(*_a, **_k):
        raise AssertionError("create_column must not be called when nothing is missing")

    monkeypatch.setattr(script_module, "create_column", _explode)
    assert script_module.main() == 0
    assert "nothing to do" in capsys.readouterr().out


def test_main_creates_missing_columns(script_module, monkeypatch, capsys):
    monkeypatch.setattr(script_module, "load_token", lambda: "tok")
    monkeypatch.setattr(script_module, "fetch_existing_columns", lambda *a, **k: [])
    monkeypatch.setattr(script_module.time, "sleep", lambda _s: None)

    created: list[str] = []

    def fake_create(token, board_id, spec):
        created.append(spec["title"])
        return f"id-{spec['title']}"

    monkeypatch.setattr(script_module, "create_column", fake_create)
    assert script_module.main() == 0
    assert len(created) == 12  # all twelve created on an empty board
    assert "Done" in capsys.readouterr().out
