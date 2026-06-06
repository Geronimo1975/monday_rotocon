"""Unit tests for scripts/smoke_ki_integration_report.py."""

from __future__ import annotations

import os

import pytest


def test_load_env_raises_on_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from smoke_ki_integration_report import RequiredEnv, load_env

    for var in ("MONDAY_API_TOKEN", "N8N_WEBHOOK_URL", "N8N_WEBHOOK_TOKEN", "REPORT_RECIPIENT"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        load_env()
    assert excinfo.value.code == 1


def test_load_env_returns_typed_struct(monkeypatch: pytest.MonkeyPatch) -> None:
    from smoke_ki_integration_report import RequiredEnv, load_env

    monkeypatch.setenv("MONDAY_API_TOKEN", "tok")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://example.org/webhook/x")
    monkeypatch.setenv("N8N_WEBHOOK_TOKEN", "secret")
    monkeypatch.setenv("REPORT_RECIPIENT", "a@b.c")

    env = load_env()
    assert isinstance(env, RequiredEnv)
    assert env.monday_token == "tok"
    assert env.webhook_url == "https://example.org/webhook/x"
    assert env.webhook_token == "secret"
    assert env.recipient == "a@b.c"


def test_group_items_by_title_preserves_first_seen_order() -> None:
    from smoke_ki_integration_report import group_items_by_title

    from monday_rotocon import Group, Item

    g1 = Group(id="g1", title="Onboarding (Tag 1)")
    g2 = Group(id="g2", title="Onboarding (Tag 2)")
    items = [
        Item(id="1", name="a", group=g1),
        Item(id="2", name="b", group=g2),
        Item(id="3", name="c", group=g1),
        Item(id="4", name="d", group=g2),
        Item(id="5", name="e", group=g1),
    ]
    result = group_items_by_title(items)
    assert result == [("Onboarding (Tag 1)", 3), ("Onboarding (Tag 2)", 2)]


def test_group_items_by_title_handles_missing_group_as_ungrouped() -> None:
    from smoke_ki_integration_report import group_items_by_title

    from monday_rotocon import Item

    items = [Item(id="1", name="a"), Item(id="2", name="b")]
    result = group_items_by_title(items)
    assert result == [("(ungrouped)", 2)]
