"""Unit tests for scripts/smoke_ki_integration_report.py."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import httpx
import pytest
from smoke_ki_integration_report import ReportData


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


def _sample_report() -> ReportData:
    return ReportData(
        board_id="111",
        board_name="KI Integration",
        workspace_id="5528271",
        generated_at=datetime(2026, 6, 6, 14, 32, 0, tzinfo=UTC),
        client_version="monday_rotocon v0.2.1",
        run_id="abcdef0123456789",
        group_counts=[("Onboarding (Tag 1)", 3), ("Onboarding (Tag 2)", 2)],
        total_items=5,
    )


def test_render_markdown_has_yaml_frontmatter_and_meta() -> None:
    from smoke_ki_integration_report import render_markdown

    md = render_markdown(_sample_report())
    assert md.startswith("---\n")
    assert "title: KI Integration — Smoke Test Report" in md
    assert "board_id: 111" in md
    assert "tags:" in md


def test_render_markdown_contains_info_callout() -> None:
    from smoke_ki_integration_report import render_markdown

    md = render_markdown(_sample_report())
    assert "> [!info] Smoke Test Run" in md
    assert "**Total items:** 5" in md


def test_render_markdown_contains_mermaid_pie_block_per_group() -> None:
    from smoke_ki_integration_report import render_markdown

    md = render_markdown(_sample_report())
    assert "```mermaid" in md
    assert "pie title" in md
    assert '"Onboarding (Tag 1)" : 3' in md
    assert '"Onboarding (Tag 2)" : 2' in md


def test_render_markdown_table_has_total_row_with_correct_sum() -> None:
    from smoke_ki_integration_report import render_markdown

    md = render_markdown(_sample_report())
    assert "| **Total** | **5** | **100%** |" in md


def test_quickchart_url_encodes_horizontal_bar_with_group_counts() -> None:
    import json
    from urllib.parse import parse_qs, urlparse

    from smoke_ki_integration_report import quickchart_url

    url = quickchart_url([("A", 3), ("B", 2)])
    parsed = urlparse(url)
    assert parsed.netloc == "quickchart.io"
    assert parsed.path == "/chart"
    qs = parse_qs(parsed.query)
    config = json.loads(qs["c"][0])
    assert config["type"] == "horizontalBar"
    assert config["data"]["labels"] == ["A", "B"]
    assert config["data"]["datasets"][0]["data"] == [3, 2]
    assert qs["w"] == ["600"]
    assert qs["h"] == ["300"]


def test_render_html_contains_table_with_totals_and_quickchart_img() -> None:
    from smoke_ki_integration_report import render_html

    html = render_html(_sample_report(), recipient="george@rotocon.world")
    assert "<table" in html
    assert "<td>Onboarding (Tag 1)</td>" in html or "Onboarding (Tag 1)" in html
    assert "<strong>Total</strong>" in html
    assert "<strong>5</strong>" in html
    assert 'src="https://quickchart.io/chart?' in html
    assert "monday_rotocon v0.2.1" in html
    assert "abcdef0123456789" in html


def test_build_payload_roundtrips_markdown_attachment() -> None:
    import base64

    from smoke_ki_integration_report import build_payload

    report = _sample_report()
    md = "# hello\nworld"
    html = "<p>hello</p>"
    payload = build_payload(
        report=report,
        recipient="george@rotocon.world",
        markdown=md,
        html_body=html,
        markdown_filename="2026-06-06-test.md",
    )
    assert payload["recipient"] == "george@rotocon.world"
    assert payload["html_body"] == html
    assert "KI Integration" in payload["subject"]
    att = payload["markdown_attachment"]
    assert att["filename"] == "2026-06-06-test.md"
    assert att["mime_type"] == "text/markdown"
    assert base64.b64decode(att["content_base64"]).decode("utf-8") == md


def test_post_to_n8n_success_returns_response_json(monkeypatch) -> None:
    import respx
    from smoke_ki_integration_report import post_to_n8n

    monkeypatch.setattr("smoke_ki_integration_report._sleep", lambda _seconds: None)

    payload = {
        "subject": "hi",
        "recipient": "a@b.c",
        "html_body": "<p>hi</p>",
        "markdown_attachment": {
            "filename": "x.md",
            "content_base64": "aGk=",
            "mime_type": "text/markdown",
        },
    }
    with respx.mock(base_url="https://n8n.example") as router:
        router.post("/webhook/x").respond(200, json={"status": "sent", "messageId": "msg-1"})
        result = post_to_n8n(
            url="https://n8n.example/webhook/x",
            token="secret",
            payload=payload,
        )
        assert result == {"status": "sent", "messageId": "msg-1"}


def test_post_to_n8n_retries_three_times_on_transport_error(monkeypatch) -> None:
    import httpx
    import respx
    from smoke_ki_integration_report import N8nWebhookError, post_to_n8n

    sleeps: list[float] = []
    monkeypatch.setattr("smoke_ki_integration_report._sleep", lambda s: sleeps.append(s))

    payload = {
        "subject": "x",
        "recipient": "a@b.c",
        "html_body": "x",
        "markdown_attachment": {
            "filename": "x.md",
            "content_base64": "aA==",
            "mime_type": "text/markdown",
        },
    }
    with respx.mock(base_url="https://n8n.example") as router:
        route = router.post("/webhook/x").mock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(N8nWebhookError):
            post_to_n8n(
                url="https://n8n.example/webhook/x",
                token="secret",
                payload=payload,
            )
        assert route.call_count == 3
        assert sleeps == [1.0, 2.0]


def test_post_to_n8n_raises_on_non_2xx(monkeypatch) -> None:
    import respx
    from smoke_ki_integration_report import N8nWebhookError, post_to_n8n

    monkeypatch.setattr("smoke_ki_integration_report._sleep", lambda _s: None)

    payload = {
        "subject": "x",
        "recipient": "a@b.c",
        "html_body": "x",
        "markdown_attachment": {
            "filename": "x.md",
            "content_base64": "aA==",
            "mime_type": "text/markdown",
        },
    }
    with respx.mock(base_url="https://n8n.example") as router:
        router.post("/webhook/x").respond(500, text="boom")
        with pytest.raises(N8nWebhookError) as excinfo:
            post_to_n8n(
                url="https://n8n.example/webhook/x",
                token="secret",
                payload=payload,
            )
        assert "500" in str(excinfo.value)


def test_find_board_by_name_returns_matching_board() -> None:
    import respx
    from smoke_ki_integration_report import find_board_by_name

    from monday_rotocon import MondayClient

    data = {
        "data": {
            "boards": [
                {"id": "111", "name": "KI Integration", "workspace_id": "5528271", "columns": []},
            ]
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(json=data)
        client = MondayClient(api_token="t")
        board = find_board_by_name(client, name="KI Integration", workspace_id="5528271")
        assert board.id == "111"


def test_find_board_by_name_raises_when_missing() -> None:
    import respx
    from smoke_ki_integration_report import BoardNotFoundError, find_board_by_name

    from monday_rotocon import MondayClient

    data = {
        "data": {
            "boards": [
                {"id": "999", "name": "Other Board", "workspace_id": "5528271", "columns": []},
            ]
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(json=data)
        client = MondayClient(api_token="t")
        with pytest.raises(BoardNotFoundError) as excinfo:
            find_board_by_name(client, name="KI Integration", workspace_id="5528271")
        assert "KI Integration" in str(excinfo.value)
        assert "Other Board" in str(excinfo.value)  # hint shown


def test_main_dry_run_writes_markdown_and_skips_webhook(monkeypatch, tmp_path) -> None:
    import respx

    monkeypatch.setenv("MONDAY_API_TOKEN", "t")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example/webhook/x")
    monkeypatch.setenv("N8N_WEBHOOK_TOKEN", "secret")
    monkeypatch.setenv("REPORT_RECIPIENT", "a@b.c")
    monkeypatch.chdir(tmp_path)

    boards_data = {
        "data": {
            "boards": [
                {"id": "111", "name": "KI Integration", "workspace_id": "5528271", "columns": []},
            ]
        }
    }
    items_data = {
        "data": {
            "boards": [
                {
                    "items_page": {
                        "cursor": None,
                        "items": [
                            {
                                "id": "1",
                                "name": "A",
                                "state": "active",
                                "group": {"id": "g1", "title": "Onboarding (Tag 1)"},
                                "column_values": [],
                            },
                            {
                                "id": "2",
                                "name": "B",
                                "state": "active",
                                "group": {"id": "g1", "title": "Onboarding (Tag 1)"},
                                "column_values": [],
                            },
                        ],
                    }
                }
            ]
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").mock(
            side_effect=[
                httpx.Response(200, json=boards_data),
                httpx.Response(200, json=items_data),
            ]
        )
        import sys

        from smoke_ki_integration_report import main

        monkeypatch.setattr(sys, "argv", ["smoke", "--dry-run"])
        exit_code = main()
        assert exit_code == 0

    reports = list((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "KI Integration" in content
    assert "Onboarding (Tag 1)" in content
