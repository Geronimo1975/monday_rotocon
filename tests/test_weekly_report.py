"""Unit tests for scripts/weekly_machine_report.py."""

from __future__ import annotations

import pytest


def test_load_env_raises_on_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from weekly_machine_report import load_env

    for var in ("MONDAY_API_TOKEN", "N8N_WEBHOOK_URL", "N8N_WEBHOOK_TOKEN", "REPORT_RECIPIENT"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(SystemExit) as excinfo:
        load_env()
    assert excinfo.value.code == 1


def test_load_env_returns_typed_struct(monkeypatch: pytest.MonkeyPatch) -> None:
    from weekly_machine_report import RequiredEnv, load_env

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


def test_col_text_and_col_number_read_column_values() -> None:
    from monday_rotocon import Item
    from weekly_machine_report import col_number, col_text

    item = Item.model_validate(
        {
            "id": "1",
            "name": "ROT200E",
            "state": "active",
            "column_values": [
                {"id": "text_mkxvxap2", "type": "text", "text": "Valley Co", "value": None},
                {"id": "numeric_mm3x30na", "type": "numbers", "text": "45", "value": "45"},
                {"id": "numeric_mm3xhrbf", "type": "numbers", "text": "", "value": None},
            ],
        }
    )
    assert col_text(item, "text_mkxvxap2") == "Valley Co"
    assert col_number(item, "numeric_mm3x30na") == 45.0
    assert col_number(item, "numeric_mm3xhrbf") is None   # empty text
    assert col_number(item, "does_not_exist") is None
    assert col_text(item, "does_not_exist") is None
