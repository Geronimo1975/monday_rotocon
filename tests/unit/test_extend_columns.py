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
