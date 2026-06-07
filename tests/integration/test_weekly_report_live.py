"""Live integration test for the weekly machine report.

Hits the real monday.com API and renders a real PDF locally. Does NOT POST to
n8n (so no email is sent). Opt-in via the `integration` marker.

Required env: MONDAY_API_TOKEN. (N8N_* / REPORT_RECIPIENT may be dummy values.)
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def test_weekly_report_renders_real_board_to_pdf(tmp_path, monkeypatch) -> None:
    pytest.importorskip("weasyprint")
    if not os.environ.get("MONDAY_API_TOKEN"):
        pytest.skip("missing MONDAY_API_TOKEN")

    from weekly_machine_report import (
        build_exceptions,
        compute_summary,
        fetch_current_machines,
        render_pdf,
        render_report_html,
    )

    from monday_rotocon import MondayClient

    monkeypatch.chdir(tmp_path)
    from datetime import UTC, datetime

    with MondayClient(api_token=os.environ["MONDAY_API_TOKEN"]) as client:
        machines = fetch_current_machines(client)

    assert machines, "expected at least one machine in the Current Machines group"
    now = datetime.now(tz=UTC)
    summary = compute_summary(machines, generated_at=now)
    exceptions = build_exceptions(machines, generated_at=now)
    pdf = render_pdf(render_report_html(summary, exceptions, machines))
    assert pdf[:5] == b"%PDF-"
    (tmp_path / "out.pdf").write_bytes(pdf)
