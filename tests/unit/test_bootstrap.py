"""Unit tests for `scripts/bootstrap_ki_integration.py`.

Focus on the risky, decision-making logic — `find_existing_board` and the
duplicate-board guard in `main` — which protects against creating a second
"KI Integration" board. The monday-mutating happy path is intentionally not
exercised here (it does real writes); only the guard short-circuit is.
"""

from __future__ import annotations

import bootstrap_ki_integration as boot
import pytest


def test_find_existing_board_returns_id_on_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        boot,
        "gql",
        lambda *a, **k: {"boards": [{"id": "42", "name": "KI Integration"}]},
    )
    assert boot.find_existing_board("tok", "KI Integration", 5528271) == 42


def test_find_existing_board_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        boot,
        "gql",
        lambda *a, **k: {"boards": [{"id": "1", "name": "Some Other Board"}]},
    )
    assert boot.find_existing_board("tok", "KI Integration", 5528271) is None


def test_main_aborts_when_board_already_exists(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(boot, "load_token", lambda: "tok")
    monkeypatch.setattr(boot, "find_existing_board", lambda *a, **k: 999)

    # If the guard fails to short-circuit, this would blow up loudly.
    def _explode(*_a: object, **_k: object) -> dict:
        raise AssertionError("gql must not be called once the board exists")

    monkeypatch.setattr(boot, "gql", _explode)

    assert boot.main() == 1
    out = capsys.readouterr().out
    assert "already exists" in out


def test_main_creates_board_when_absent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(boot, "load_token", lambda: "tok")
    monkeypatch.setattr(boot, "find_existing_board", lambda *a, **k: None)
    monkeypatch.setattr(boot.time, "sleep", lambda _s: None)

    calls: list[str] = []

    def fake_gql(token: str, query: str, variables: dict | None = None) -> dict:
        calls.append(query)
        if "create_board" in query:
            return {
                "create_board": {
                    "id": "777",
                    "name": "KI Integration",
                    "groups": [{"id": "g0", "title": "Group Title"}],
                }
            }
        if "update_group" in query:
            return {"update_group": {"id": "g0"}}
        if "create_group" in query:
            return {"create_group": {"id": "gN", "title": "x"}}
        if "create_item" in query:
            return {"create_item": {"id": "i1"}}
        raise AssertionError(f"unexpected query: {query[:40]}")

    monkeypatch.setattr(boot, "gql", fake_gql)

    assert boot.main() == 0
    out = capsys.readouterr().out
    assert "Board created" in out
    assert any("create_item" in q for q in calls)
