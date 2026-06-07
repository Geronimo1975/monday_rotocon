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


def _summary(**overrides):
    from datetime import UTC, datetime

    from weekly_machine_report import PortfolioSummary

    defaults = dict(
        total=3, avg_overall=42.0, critical_count=1, late_count=1,
        discrepancy_count=1, delivery_30d_count=0, week=23,
        generated_at=datetime(2026, 6, 7, 5, 0, tzinfo=UTC),
        by_phase={"Production": 2, "FAT": 1},
    )
    defaults.update(overrides)
    return PortfolioSummary(**defaults)


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


def test_build_exceptions_flags_each_rule() -> None:
    from datetime import UTC, datetime

    from weekly_machine_report import build_exceptions

    rows = [
        _row(machine_no="OK", overall=80, project_status="ok", phase_pct=80, subtask_pct=78),
        _row(machine_no="CRIT", overall=30, project_status="critical"),
        _row(machine_no="LATE", overall=40, project_status="late delivery"),
        _row(machine_no="GAP", overall=50, project_status="ok", phase_pct=70, subtask_pct=10),
        _row(machine_no="SOON", overall=60, project_status="ok", phase_pct=60,
             subtask_pct=55, deliver_text="20-Jun-2026"),
    ]
    now = datetime(2026, 6, 7, 5, 0, tzinfo=UTC)
    exceptions = build_exceptions(rows, generated_at=now)

    flagged = {e.machine_no for e in exceptions}
    assert "OK" not in flagged
    assert {"CRIT", "LATE", "GAP", "SOON"} <= flagged
    crit = next(e for e in exceptions if e.machine_no == "CRIT")
    assert "critical" in crit.why.lower()


def test_build_exceptions_sorts_critical_first() -> None:
    from datetime import UTC, datetime

    from weekly_machine_report import build_exceptions

    rows = [
        _row(machine_no="LATE", project_status="late delivery", overall=40),
        _row(machine_no="CRIT", project_status="critical", overall=30),
    ]
    now = datetime(2026, 6, 7, 5, 0, tzinfo=UTC)
    exceptions = build_exceptions(rows, generated_at=now)
    assert exceptions[0].machine_no == "CRIT"


def test_render_report_html_has_kpis_and_sections() -> None:
    from weekly_machine_report import render_report_html

    rows = [_row(machine_no="ROT200E", overall=80)]
    excs = []
    html = render_report_html(_summary(), excs, rows)
    assert "Rotocon" in html
    assert "KW23" in html
    assert "Total machines" in html
    assert "ROT200E" in html
    assert "No exceptions this week" in html  # empty exception list message


def test_render_report_html_renders_dashes_for_missing_overall() -> None:
    from weekly_machine_report import render_report_html

    rows = [_row(machine_no="NEW", overall=None, responsible=None)]
    html = render_report_html(_summary(total=1), [], rows)
    assert "NEW" in html
    assert "—" in html  # null overall / responsible shown as em dash


def test_render_report_html_lists_exceptions_when_present() -> None:
    from weekly_machine_report import ExceptionRow, render_report_html

    excs = [ExceptionRow(machine_no="CRIT", client="ACME", phase="FAT",
                         overall=30.0, why="Project status critical", urgency=0)]
    html = render_report_html(_summary(), excs, [_row()])
    assert "CRIT" in html
    assert "Project status critical" in html
    assert "No exceptions this week" not in html


def test_render_pdf_produces_pdf_bytes() -> None:
    import pytest

    pytest.importorskip("weasyprint")  # skip if system libs absent
    from weekly_machine_report import render_pdf

    pdf = render_pdf("<html><body><h1>hi</h1></body></html>")
    assert isinstance(pdf, bytes)
    assert pdf[:5] == b"%PDF-"


def test_render_email_summary_is_short_and_mentions_attachment() -> None:
    from weekly_machine_report import render_email_summary_html

    html = render_email_summary_html(_summary(critical_count=2, total=10))
    assert "KW23" in html
    assert "10" in html           # total
    assert "2" in html            # critical
    assert "attached" in html.lower()
    assert "<table" not in html   # body stays short, no full table


def test_build_payload_embeds_pdf_and_stats() -> None:
    import base64

    from weekly_machine_report import build_payload

    summary = _summary(total=12, avg_overall=44.0, critical_count=2, late_count=3)
    payload = build_payload(
        summary=summary,
        recipient="george@rotocon.world",
        html_summary="<div>hi</div>",
        pdf_bytes=b"%PDF-1.7 fake",
        pdf_filename="2026-06-07-weekly.pdf",
    )
    assert payload["recipient"] == "george@rotocon.world"
    assert payload["html_summary"] == "<div>hi</div>"
    assert "KW23" in payload["subject"]
    assert "2 critical" in payload["subject"]
    assert payload["pdf"]["filename"] == "2026-06-07-weekly.pdf"
    assert payload["pdf"]["mime_type"] == "application/pdf"
    assert base64.b64decode(payload["pdf"]["content_base64"]) == b"%PDF-1.7 fake"
    assert payload["stats"]["machine_count"] == 12
    assert payload["stats"]["avg_overall"] == 44.0
    assert payload["stats"]["critical_n"] == 2
    assert payload["stats"]["late_n"] == 3
    assert payload["stats"]["board_id"] == "5086438002"
    assert payload["stats"]["pdf_size_kb"] == 1


def test_post_to_n8n_success_returns_json(monkeypatch) -> None:
    import respx

    from weekly_machine_report import post_to_n8n

    monkeypatch.setattr("weekly_machine_report._sleep", lambda _s: None)
    payload = {"subject": "x", "recipient": "a@b.c", "html_summary": "<p>x</p>",
               "pdf": {"filename": "x.pdf", "content_base64": "JVBERg==",
                       "mime_type": "application/pdf"}, "stats": {}}
    with respx.mock(base_url="https://n8n.example") as router:
        router.post("/webhook/x").respond(200, json={"status": "sent", "messageId": "m1"})
        result = post_to_n8n(url="https://n8n.example/webhook/x", token="t", payload=payload)
        assert result == {"status": "sent", "messageId": "m1"}


def test_post_to_n8n_retries_then_raises(monkeypatch) -> None:
    import httpx
    import pytest
    import respx

    from weekly_machine_report import N8nWebhookError, post_to_n8n

    sleeps: list[float] = []
    monkeypatch.setattr("weekly_machine_report._sleep", lambda s: sleeps.append(s))
    payload = {"subject": "x", "recipient": "a@b.c", "html_summary": "x",
               "pdf": {"filename": "x.pdf", "content_base64": "JQ==",
                       "mime_type": "application/pdf"}, "stats": {}}
    with respx.mock(base_url="https://n8n.example") as router:
        route = router.post("/webhook/x").mock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(N8nWebhookError):
            post_to_n8n(url="https://n8n.example/webhook/x", token="t", payload=payload)
        assert route.call_count == 3
        assert sleeps == [1.0, 2.0]


def test_post_to_n8n_raises_on_non_2xx(monkeypatch) -> None:
    import pytest
    import respx

    from weekly_machine_report import N8nWebhookError, post_to_n8n

    monkeypatch.setattr("weekly_machine_report._sleep", lambda _s: None)
    payload = {"subject": "x", "recipient": "a@b.c", "html_summary": "x",
               "pdf": {"filename": "x.pdf", "content_base64": "JQ==",
                       "mime_type": "application/pdf"}, "stats": {}}
    with respx.mock(base_url="https://n8n.example") as router:
        router.post("/webhook/x").respond(500, text="boom")
        with pytest.raises(N8nWebhookError) as excinfo:
            post_to_n8n(url="https://n8n.example/webhook/x", token="t", payload=payload)
        assert "500" in str(excinfo.value)
