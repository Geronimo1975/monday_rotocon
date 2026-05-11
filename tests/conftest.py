"""Shared pytest fixtures for monday_rotocon tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_loader():
    """Return a callable that loads a JSON fixture by stem name."""
    def _load(name: str) -> dict:
        path = FIXTURES_DIR / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def dummy_token() -> str:
    return "dummy.test.token"
