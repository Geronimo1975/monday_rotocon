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


def _item(**overrides):
    """Build a monday Item with the columns the report reads."""
    from monday_rotocon import Item

    cols = {
        "text_mkxvf3xh": overrides.get("machine_type", "RDF340"),
        "text_mkxvxap2": overrides.get("client", "Valley Co"),
        "country_mkxvqhys": overrides.get("country", "Germany"),
        "person": overrides.get("responsible", "Metin Ertem"),
        "status": overrides.get("phase", "Production"),
        "color_mm06k0h1": overrides.get("project_status", "ok"),
        "color_mm06wr1p": overrides.get("procurement", "All on Order"),
        "numeric_mm3xhrbf": overrides.get("phase_pct", "40"),
        "numeric_mm3xgyyw": overrides.get("subtask_pct", "30"),
        "numeric_mm3x30na": overrides.get("overall", "36"),
        "formula_mkxw3x4k": overrides.get("deliver", "15-Aug-2026"),
        "date_mky7mk4f": overrides.get("fat", ""),
        "date_mky785fe": overrides.get("sat", ""),
    }
    column_values = [
        {"id": cid, "type": "text", "text": val, "value": None} for cid, val in cols.items()
    ]
    group = overrides.get("group", {"id": "topics", "title": "Current Machines"})
    return Item.model_validate(
        {
            "id": overrides.get("id", "1"),
            "name": overrides.get("name", "ROT200E"),
            "state": "active",
            "group": group,
            "column_values": column_values,
        }
    )


def test_machine_row_from_item_maps_all_fields() -> None:
    from weekly_machine_report import MachineRow

    row = MachineRow.from_item(_item(name="ROT201E", overall="55", phase="FAT"))
    assert row.machine_no == "ROT201E"
    assert row.client == "Valley Co"
    assert row.phase == "FAT"
    assert row.overall == 55.0
    assert row.phase_pct == 40.0
    assert row.subtask_pct == 30.0


def test_fetch_current_machines_filters_to_topics_group() -> None:
    from weekly_machine_report import fetch_current_machines

    class FakeClient:
        def items_for_board(self, *, board_id: str):
            yield _item(id="1", name="A", group={"id": "topics", "title": "Current Machines"})
            yield _item(id="2", name="B", group={"id": "group_demo", "title": "Demo Machine"})
            yield _item(id="3", name="C", group={"id": "topics", "title": "Current Machines"})

    rows = fetch_current_machines(FakeClient())  # type: ignore[arg-type]
    assert [r.machine_no for r in rows] == ["A", "C"]
