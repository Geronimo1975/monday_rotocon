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


def _row(**overrides):
    from weekly_machine_report import MachineRow

    defaults = dict(
        machine_no="ROT200E", machine_type="RDF340", client="Valley Co",
        country="Germany", responsible="Metin Ertem", phase="Production",
        project_status="ok", procurement="All on Order",
        phase_pct=40.0, subtask_pct=30.0, overall=36.0,
        deliver_text="15-Aug-2026", fat_date=None, sat_date=None,
    )
    defaults.update(overrides)
    return MachineRow(**defaults)


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


def test_parse_deliver_date_handles_monday_formula_format() -> None:
    from datetime import date

    from weekly_machine_report import parse_deliver_date

    assert parse_deliver_date("15-Aug-2026") == date(2026, 8, 15)
    assert parse_deliver_date("") is None
    assert parse_deliver_date(None) is None
    assert parse_deliver_date("not a date") is None


def test_compute_summary_counts_kpis() -> None:
    from datetime import UTC, datetime

    from weekly_machine_report import compute_summary

    rows = [
        _row(overall=80, project_status="ok", phase_pct=80, subtask_pct=78),
        _row(overall=20, project_status="critical", phase_pct=60, subtask_pct=5),  # discrepancy 55
        _row(overall=50, project_status="late delivery", phase_pct=50, subtask_pct=50),
        _row(overall=None, project_status="on hold", phase_pct=None, subtask_pct=None),
    ]
    now = datetime(2026, 6, 7, 5, 0, tzinfo=UTC)
    summary = compute_summary(rows, generated_at=now)

    assert summary.total == 4
    assert summary.critical_count == 1
    assert summary.late_count == 1
    assert summary.discrepancy_count == 1            # the 60-vs-5 machine
    assert summary.avg_overall == 50.0               # mean of 80,20,50 (None excluded)
    assert summary.week == now.isocalendar().week
