# KI Integration Smoke Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End-to-end smoke test that uses `monday_rotocon` v0.2.1 to read the "KI Integration" board, builds an Obsidian-flavored Markdown + HTML email (with QuickChart bar chart), and delivers the email through an n8n workflow that sends via Microsoft 365 Outlook.

**Architecture:** A Python script in `scripts/` uses `MondayClient` to fetch board metadata and items; pure rendering helpers produce two artifacts (local `.md` for Obsidian + HTML email body); the script POSTs a JSON payload (HTML body + base64-encoded `.md` attachment) to an n8n webhook authenticated via header token; the n8n workflow forwards through Microsoft Outlook. A second tiny n8n workflow returning 200-OK is used by the integration test, so CI never sends mail. The library is extended additively (new `Group` model, `Item.group` field, augmented queries) to expose group titles needed for the report — backwards-compatible and consistent with the library's read-only invariant.

**Tech Stack:** Python 3.12, `monday_rotocon` (library under development), `httpx`, `pydantic` v2, `respx` (test mocking), `pytest`, n8n (self-hosted at `https://n8n.rotocon.world`), `mcp__n8n-mcp__*` MCP tools, QuickChart.io (URL-based chart rendering).

**Spec:** `docs/superpowers/specs/2026-06-06-ki-integration-smoke-report-design.md`

**Conventions:**
- Every code-changing task ends with running tests + a git commit.
- Commit messages follow the project convention seen in `git log` (`type(scope): subject`).
- Library changes use TDD: failing test → minimal impl → green → commit.
- `uv run` prefix for every Python / pytest / mypy / ruff invocation.

---

## File Map

**Library (extended additively):**
- Modify `src/monday_rotocon/models.py`: add `Group` model, add `group: Group | None = None` field on `Item`.
- Modify `src/monday_rotocon/queries.py`: augment `Q_ITEMS_PAGE` and `Q_NEXT_ITEMS_PAGE` with `group { id title }`.
- Modify `src/monday_rotocon/__init__.py`: export `Group`.

**Smoke script (new):**
- Create `scripts/smoke_ki_integration_report.py`: env-driven, importable module with pure helpers and a `main()` entry point.

**Tests (new):**
- Create `tests/test_smoke_report.py`: unit tests for `group_items_by_title`, `render_markdown`, `render_html`, `build_payload`, `post_to_n8n` (mocked).
- Create `tests/integration/test_smoke_report_live.py`: opt-in live test under the `integration` marker.

**Config / repo housekeeping:**
- Modify `.gitignore`: add `reports/`.
- Create `.env.example` (currently deleted per git status): repopulate with all env vars including the new ones.
- Modify `pyproject.toml`: add `pythonpath = ["scripts"]` to `[tool.pytest.ini_options]` so tests can import `smoke_ki_integration_report`.

**n8n (created via MCP, not as files in the repo):**
- Credential `Smoke Report Webhook Token` (`httpHeaderAuth`, header `X-Smoke-Token`, value = generated secret).
- Workflow `monday-smoke-report-email`: Webhook (`/webhook/monday-smoke-report`) → Microsoft Outlook → Respond to Webhook.
- Workflow `monday-smoke-report-test-echo`: Webhook (`/webhook/monday-smoke-report-test`) → Respond to Webhook (200).

---

## Task 1: Repo housekeeping — gitignore, .env.example, pyproject pythonpath

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`
- Modify: `pyproject.toml:37-43`

- [ ] **Step 1: Add `reports/` to `.gitignore`**

Append at the end of `.gitignore`:

```
# Smoke report local copies
reports/
```

- [ ] **Step 2: Recreate `.env.example` with current + new variables**

Write the following to `.env.example`:

```
# monday.com personal API token (required by the library + smoke script)
MONDAY_API_TOKEN=your-monday-api-token-here

# n8n smoke-report webhook (used only by scripts/smoke_ki_integration_report.py)
N8N_WEBHOOK_URL=https://n8n.rotocon.world/webhook/monday-smoke-report
N8N_WEBHOOK_TOKEN=<64-char hex string, 32 random bytes>

# Recipient of the smoke-report email
REPORT_RECIPIENT=george@rotocon.world
```

- [ ] **Step 3: Add `pythonpath` to `pyproject.toml` pytest config**

Edit `pyproject.toml` `[tool.pytest.ini_options]` (lines 37–43). Replace:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
markers = [
    "integration: tests that hit the real monday.com API (opt-in)",
]
asyncio_mode = "auto"
```

with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["scripts"]
addopts = "-ra --strict-markers --strict-config"
markers = [
    "integration: tests that hit the real monday.com API or n8n webhook (opt-in)",
]
asyncio_mode = "auto"
```

- [ ] **Step 4: Verify pytest still discovers tests**

Run: `uv run pytest --collect-only -q`
Expected: existing tests still listed; no collection errors.

- [ ] **Step 5: Commit**

```bash
git add .gitignore .env.example pyproject.toml
git commit -m "chore: prep repo for smoke report (gitignore, .env.example, pytest pythonpath)"
```

---

## Task 2: Library extension — `Group` model + `Item.group` field + queries

**Files:**
- Modify: `src/monday_rotocon/models.py`
- Modify: `src/monday_rotocon/queries.py`
- Modify: `src/monday_rotocon/__init__.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Write a failing test for `Group` model**

Append to `tests/test_models.py`:

```python
def test_group_model_parses_id_and_title():
    from monday_rotocon import Group

    g = Group.model_validate({"id": "topics", "title": "Onboarding (Tag 1)"})
    assert g.id == "topics"
    assert g.title == "Onboarding (Tag 1)"


def test_item_group_field_optional_and_parses_when_present():
    from monday_rotocon import Item

    item_no_group = Item.model_validate(
        {"id": "1", "name": "x", "state": "active", "column_values": []}
    )
    assert item_no_group.group is None

    item_with_group = Item.model_validate(
        {
            "id": "2",
            "name": "y",
            "state": "active",
            "column_values": [],
            "group": {"id": "topics", "title": "Onboarding (Tag 1)"},
        }
    )
    assert item_with_group.group is not None
    assert item_with_group.group.title == "Onboarding (Tag 1)"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: ImportError or AttributeError — `Group` not yet exported, `Item` has no `group` field.

- [ ] **Step 3: Implement `Group` model and add `group` field to `Item`**

Edit `src/monday_rotocon/models.py`. The full file becomes:

```python
"""Typed Pydantic models for monday.com API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Column(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    title: str
    type: str
    settings_str: str = ""


class ColumnValue(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    column_id: str = Field(alias="id")
    type: str
    value: str | None = None
    text: str | None = None


class Group(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    title: str


class Item(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    name: str
    state: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    column_values: list[ColumnValue] = Field(default_factory=list)
    group: Group | None = None


class Board(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    name: str
    workspace_id: str = ""
    columns: list[Column] = Field(default_factory=list)
```

- [ ] **Step 4: Export `Group` from the package**

Edit `src/monday_rotocon/__init__.py`. The full file becomes:

```python
"""monday_rotocon — typed monday.com client + CLI for Rotocon."""

from monday_rotocon.models import Board, Column, ColumnValue, Group, Item
from monday_rotocon.transport import MondayAPIError, MondayClient

__all__ = [
    "Board",
    "Column",
    "ColumnValue",
    "Group",
    "Item",
    "MondayAPIError",
    "MondayClient",
]
__version__ = "0.2.1"
```

- [ ] **Step 5: Run model tests — expect green**

Run: `uv run pytest tests/test_models.py -v`
Expected: all model tests pass, including the two new ones.

- [ ] **Step 6: Augment queries with `group { id title }`**

Edit `src/monday_rotocon/queries.py`. The full file becomes:

```python
"""GraphQL query strings for monday.com API v2.

Cursor-based pagination via items_page / next_items_page (post-2024 API).
"""

Q_BOARDS = """
query Boards($board_ids: [ID!]!) {
  boards(ids: $board_ids) {
    id
    name
    workspace_id
    columns {
      id
      title
      type
      settings_str
    }
  }
}
""".strip()

Q_ITEMS_PAGE = """
query ItemsPage($board_id: ID!, $limit: Int!, $cursor: String) {
  boards(ids: [$board_id]) {
    items_page(limit: $limit, cursor: $cursor) {
      cursor
      items {
        id
        name
        state
        created_at
        updated_at
        group {
          id
          title
        }
        column_values {
          id
          type
          value
          text
        }
      }
    }
  }
}
""".strip()

Q_NEXT_ITEMS_PAGE = """
query NextItemsPage($cursor: String!, $limit: Int!) {
  next_items_page(cursor: $cursor, limit: $limit) {
    cursor
    items {
      id
      name
      state
      created_at
      updated_at
      group {
        id
        title
      }
      column_values {
        id
        type
        value
        text
      }
    }
  }
}
""".strip()
```

- [ ] **Step 7: Update `tests/test_client.py` items-pagination fixture to include `group`**

Locate the `page1` and `page2` dicts in `tests/test_client.py` (lines 36–73 currently). Add a `"group": {"id": "topics", "title": "Onboarding (Tag 1)"}` field to each item dict (inside each `"items": [...]` list), e.g.:

```python
            "items": [
                {
                    "id": "1",
                    "name": "Lead A",
                    "state": "active",
                    "created_at": "2026-05-01T10:00:00Z",
                    "updated_at": "2026-05-02T10:00:00Z",
                    "group": {"id": "topics", "title": "Onboarding (Tag 1)"},
                    "column_values": [],
                },
            ],
```

Apply the same addition to the `page2` item (with the same group, since group identity is incidental to the test). Then append after the existing assertions in `test_items_for_board_paginates_through_cursor`:

```python
        assert all(i.group is not None for i in items)
        assert items[0].group.title == "Onboarding (Tag 1)"
```

- [ ] **Step 8: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests green (existing + new model tests + augmented client test).

- [ ] **Step 9: Run mypy strict**

Run: `uv run mypy src`
Expected: success, no errors.

- [ ] **Step 10: Commit**

```bash
git add src/monday_rotocon/models.py src/monday_rotocon/queries.py src/monday_rotocon/__init__.py tests/test_models.py tests/test_client.py
git commit -m "feat(models): add Group model and Item.group field; queries fetch group"
```

---

## Task 3: Generate webhook token + create n8n credential, smoke workflow, test-echo workflow

**Tools used:** `mcp__n8n-mcp__n8n_manage_credentials`, `mcp__n8n-mcp__n8n_create_workflow`, `mcp__n8n-mcp__n8n_validate_workflow`, `mcp__n8n-mcp__get_node`, `mcp__n8n-mcp__search_nodes`.

**No files in this task — work happens in n8n via MCP.**

- [ ] **Step 1: Generate `N8N_WEBHOOK_TOKEN` and add it to local `.env`**

Run locally (do NOT commit the value):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the printed 64-char hex string. Add to local `.env`:

```
N8N_WEBHOOK_URL=https://n8n.rotocon.world/webhook/monday-smoke-report
N8N_WEBHOOK_TOKEN=<paste the 64-char hex here>
REPORT_RECIPIENT=george@rotocon.world
```

Keep the token also available for Step 3.

- [ ] **Step 2: Discover the `httpHeaderAuth` credential schema**

Use the MCP tool:

```
mcp__n8n-mcp__n8n_manage_credentials(action="getSchema", type="httpHeaderAuth")
```

Expected: schema with `name` and `value` string fields.

- [ ] **Step 3: Create the credential**

```
mcp__n8n-mcp__n8n_manage_credentials(
    action="create",
    type="httpHeaderAuth",
    name="Smoke Report Webhook Token",
    data={"name": "X-Smoke-Token", "value": "<paste the same 64-char hex from Step 1>"},
)
```

Expected: response includes `id`. Record this credential ID (call it `<CRED_ID>` below).

- [ ] **Step 4: Look up node schemas for Webhook, Microsoft Outlook, Respond to Webhook**

Run each:

```
mcp__n8n-mcp__get_node(nodeType="nodes-base.webhook")
mcp__n8n-mcp__search_nodes(query="microsoft outlook send")
mcp__n8n-mcp__get_node(nodeType="nodes-base.respondToWebhook")
```

For the Microsoft Outlook node, use the `search_nodes` result to confirm the exact `nodeType` string (commonly `nodes-base.microsoftOutlook`). Note the exact parameter names for `operation`, `to`, `subject`, `bodyContent`, `attachments`, and which credential field name it expects (likely `microsoftOutlookOAuth2Api`).

- [ ] **Step 5: Create the smoke email workflow**

Call `mcp__n8n-mcp__n8n_create_workflow` with a workflow JSON like the following (adjust node-specific parameter names per Step 4 if they differ — but the structure is fixed):

```json
{
  "name": "monday-smoke-report-email",
  "nodes": [
    {
      "id": "node-webhook",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [200, 200],
      "parameters": {
        "httpMethod": "POST",
        "path": "monday-smoke-report",
        "authentication": "headerAuth",
        "responseMode": "responseNode",
        "options": {}
      },
      "credentials": {
        "httpHeaderAuth": {
          "id": "<CRED_ID>",
          "name": "Smoke Report Webhook Token"
        }
      }
    },
    {
      "id": "node-send",
      "name": "Send Email",
      "type": "n8n-nodes-base.microsoftOutlook",
      "typeVersion": 2,
      "position": [500, 200],
      "parameters": {
        "resource": "message",
        "operation": "send",
        "subject": "={{ $json.body.subject }}",
        "bodyContent": "={{ $json.body.html_body }}",
        "bodyContentType": "html",
        "toRecipients": "={{ $json.body.recipient }}",
        "additionalFields": {
          "attachmentsUi": {
            "attachmentsBinary": []
          }
        }
      },
      "credentials": {
        "microsoftOutlookOAuth2Api": {
          "id": "7JEAzAMCDjKqDX3F",
          "name": "Microsoft Outlook account"
        }
      }
    },
    {
      "id": "node-respond",
      "name": "Respond",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [800, 200],
      "parameters": {
        "respondWith": "json",
        "responseBody": "={ \"status\": \"sent\", \"messageId\": $json.id }"
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{ "node": "Send Email", "type": "main", "index": 0 }]]
    },
    "Send Email": {
      "main": [[{ "node": "Respond", "type": "main", "index": 0 }]]
    }
  },
  "settings": {}
}
```

Note: the attachment requires the Markdown to be converted to binary first. If the `microsoftOutlook` send node doesn't accept attachments inline as base64 in the JSON, insert a `Convert to File` (`n8n-nodes-base.convertToFile`) node between Webhook and Send Email, mapping `body.markdown_attachment.content_base64` (base64 decode) to a binary property called `attachment`, then reference it in `attachmentsBinary` as `attachment`. Discover this in Step 4 and adapt the workflow accordingly before submitting to `n8n_create_workflow`.

- [ ] **Step 6: Validate the workflow**

```
mcp__n8n-mcp__n8n_validate_workflow(<workflow ID returned from Step 5>)
```

Expected: no errors. If errors appear, fix by adjusting parameter names per the schemas from Step 4, then re-validate. Do not proceed until validation is clean.

- [ ] **Step 7: Activate the workflow**

n8n_create_workflow returns the workflow with `active: false` by default. Activate via:

```
mcp__n8n-mcp__n8n_update_partial_workflow(
    id="<workflow id>",
    operations=[{"type": "updateSettings", "settings": {"active": true}}]
)
```

(Adjust the operation per the actual partial-update schema discovered via `mcp__n8n-mcp__tools_documentation(topic="n8n_update_partial_workflow")` if needed.)

Expected: response shows `active: true`.

- [ ] **Step 8: Create the test-echo workflow**

```
mcp__n8n-mcp__n8n_create_workflow(...)
```

with this JSON:

```json
{
  "name": "monday-smoke-report-test-echo",
  "nodes": [
    {
      "id": "node-webhook-test",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [200, 200],
      "parameters": {
        "httpMethod": "POST",
        "path": "monday-smoke-report-test",
        "authentication": "headerAuth",
        "responseMode": "responseNode",
        "options": {}
      },
      "credentials": {
        "httpHeaderAuth": {
          "id": "<CRED_ID>",
          "name": "Smoke Report Webhook Token"
        }
      }
    },
    {
      "id": "node-respond-test",
      "name": "Respond",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [500, 200],
      "parameters": {
        "respondWith": "json",
        "responseBody": "={ \"status\": \"ok-echo\", \"received_subject\": $json.body.subject }"
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{ "node": "Respond", "type": "main", "index": 0 }]]
    }
  },
  "settings": {}
}
```

Validate (as in Step 6), then activate (as in Step 7).

- [ ] **Step 9: Manual sanity-check both webhooks with curl**

```bash
TOKEN="<paste the 64-char hex>"

# Smoke workflow — expect 200 if M365 send succeeds; or a non-2xx telling us
# the body is misshapen. Either way, the webhook auth worked.
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "https://n8n.rotocon.world/webhook/monday-smoke-report" \
  -H "X-Smoke-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subject":"hello","html_body":"<p>hi</p>","recipient":"george@rotocon.world","markdown_attachment":{"filename":"x.md","content_base64":"aGk=","mime_type":"text/markdown"}}'

# Wrong token — expect 401/403
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "https://n8n.rotocon.world/webhook/monday-smoke-report" \
  -H "X-Smoke-Token: wrong" \
  -H "Content-Type: application/json" \
  -d '{}'

# Echo workflow — expect 200 with JSON echo
curl -s -X POST "https://n8n.rotocon.world/webhook/monday-smoke-report-test" \
  -H "X-Smoke-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":{"subject":"echo me"}}'
```

Expected: smoke webhook either returns 200 (and an email lands in Outlook) OR a 5xx if the JSON shape doesn't yet match the Outlook node's expectations. Either way, the wrong-token call must NOT return 200.

- [ ] **Step 10: No git commit (no files changed in this task)**

Move on to Task 4. Record the credential ID and workflow IDs in a scratch note for your own reference (do NOT commit them — credential IDs are not secrets but they are noise in the repo).

---

## Task 4: Script skeleton — env loader, types, dry-run skeleton

**Files:**
- Create: `scripts/smoke_ki_integration_report.py`
- Create: `tests/test_smoke_report.py`

- [ ] **Step 1: Write a failing test for required-env validation**

Create `tests/test_smoke_report.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: `ModuleNotFoundError: No module named 'smoke_ki_integration_report'`.

- [ ] **Step 3: Create the script skeleton with env loader**

Create `scripts/smoke_ki_integration_report.py`:

```python
"""End-to-end smoke test for monday_rotocon v0.2.1.

Reads the "KI Integration" board via the library, builds an
Obsidian-flavored Markdown report + an HTML email (with a QuickChart
bar chart), saves the Markdown locally to `reports/`, and POSTs to an
n8n webhook that fans out via M365 Outlook.

Unlike `bootstrap_ki_integration.py`, this script DOES import
`monday_rotocon` — that's the whole point. Run it with `uv run`
so the venv is active:

    uv run python scripts/smoke_ki_integration_report.py [--dry-run]

The script never mutates monday state; the read-only invariant of
the library still holds.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class RequiredEnv:
    monday_token: str
    webhook_url: str
    webhook_token: str
    recipient: str


def load_env() -> RequiredEnv:
    """Read required env vars. Exits the process with code 1 if any are missing."""
    required = {
        "MONDAY_API_TOKEN": "monday_token",
        "N8N_WEBHOOK_URL": "webhook_url",
        "N8N_WEBHOOK_TOKEN": "webhook_token",
        "REPORT_RECIPIENT": "recipient",
    }
    values: dict[str, str] = {}
    missing: list[str] = []
    for env_name, attr_name in required.items():
        v = os.environ.get(env_name, "").strip()
        if not v:
            missing.append(env_name)
        else:
            values[attr_name] = v
    if missing:
        print(f"Missing required env: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(1)
    return RequiredEnv(**values)


def main() -> int:
    parser = argparse.ArgumentParser(description="KI Integration smoke report")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch + render + save Markdown locally; do not POST to n8n.")
    args = parser.parse_args()
    _ = load_env()
    # The rest of main() is implemented in Task 10.
    raise SystemExit(0 if args.dry_run else 0)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the env tests — expect green**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: both `test_load_env_*` pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_ki_integration_report.py tests/test_smoke_report.py
git commit -m "feat(smoke): script skeleton with env loader"
```

---

## Task 5: `group_items_by_title()`

**Files:**
- Modify: `scripts/smoke_ki_integration_report.py`
- Modify: `tests/test_smoke_report.py`

- [ ] **Step 1: Write a failing test**

Append to `tests/test_smoke_report.py`:

```python
def test_group_items_by_title_preserves_first_seen_order() -> None:
    from monday_rotocon import Group, Item
    from smoke_ki_integration_report import group_items_by_title

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
    from monday_rotocon import Item
    from smoke_ki_integration_report import group_items_by_title

    items = [Item(id="1", name="a"), Item(id="2", name="b")]
    result = group_items_by_title(items)
    assert result == [("(ungrouped)", 2)]
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_smoke_report.py::test_group_items_by_title_preserves_first_seen_order -v`
Expected: ImportError on `group_items_by_title`.

- [ ] **Step 3: Implement `group_items_by_title`**

Add to `scripts/smoke_ki_integration_report.py` (just below `load_env`):

```python
from collections import OrderedDict

from monday_rotocon import Item


def group_items_by_title(items: list[Item]) -> list[tuple[str, int]]:
    """Count items per group title, preserving first-seen order.

    Items without a group are bucketed under "(ungrouped)".
    """
    counts: OrderedDict[str, int] = OrderedDict()
    for item in items:
        title = item.group.title if item.group is not None else "(ungrouped)"
        counts[title] = counts.get(title, 0) + 1
    return list(counts.items())
```

- [ ] **Step 4: Re-run the tests — expect green**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: all four tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_ki_integration_report.py tests/test_smoke_report.py
git commit -m "feat(smoke): group_items_by_title helper"
```

---

## Task 6: `render_markdown()` (Obsidian-flavored)

**Files:**
- Modify: `scripts/smoke_ki_integration_report.py`
- Modify: `tests/test_smoke_report.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_smoke_report.py`:

```python
def _sample_report() -> "ReportData":
    from datetime import datetime, timezone

    from smoke_ki_integration_report import ReportData

    return ReportData(
        board_id="111",
        board_name="KI Integration",
        workspace_id="5528271",
        generated_at=datetime(2026, 6, 6, 14, 32, 0, tzinfo=timezone.utc),
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
```

- [ ] **Step 2: Run them — expect failures on missing `ReportData` / `render_markdown`**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: ImportError on `ReportData` and `render_markdown`.

- [ ] **Step 3: Implement `ReportData` dataclass and `render_markdown`**

Append to `scripts/smoke_ki_integration_report.py` (after `group_items_by_title`):

```python
from datetime import datetime


@dataclass(frozen=True)
class ReportData:
    board_id: str
    board_name: str
    workspace_id: str
    generated_at: datetime
    client_version: str
    run_id: str
    group_counts: list[tuple[str, int]]
    total_items: int


def _percent(part: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{round(100 * part / total)}%"


def render_markdown(report: ReportData) -> str:
    ts = report.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    date_only = report.generated_at.strftime("%Y-%m-%d")

    frontmatter = (
        "---\n"
        f"title: {report.board_name} — Smoke Test Report\n"
        f"date: {date_only}\n"
        f"client: {report.client_version}\n"
        f"board_id: {report.board_id}\n"
        "tags: [smoke-test, monday, ki-integration]\n"
        "---\n\n"
    )

    callout = (
        "> [!info] Smoke Test Run\n"
        f"> **Board:** {report.board_name} (`{report.board_id}`)\n"
        f"> **Workspace:** ROTOCON EU SERVICE (`{report.workspace_id}`)\n"
        f"> **Generated:** {ts}\n"
        f"> **Total items:** {report.total_items} — peste "
        f"{len(report.group_counts)} grupuri\n"
        f"> **Transport:** `{report.client_version}`\n\n"
    )

    pie_lines = [f'    "{title}" : {count}' for title, count in report.group_counts]
    mermaid = (
        "## Distribuție itemi per grup\n\n"
        "```mermaid\n"
        "pie title Itemi per grup\n"
        + "\n".join(pie_lines)
        + "\n```\n\n"
    )

    table_rows = [
        f"| {title} | {count} | {_percent(count, report.total_items)} |"
        for title, count in report.group_counts
    ]
    table = (
        "| Grup | Itemi | % din total |\n"
        "|---|---:|---:|\n"
        + "\n".join(table_rows)
        + f"\n| **Total** | **{report.total_items}** | **100%** |\n\n"
    )

    checklist = (
        "## Verificări end-to-end\n\n"
        "- [x] `MondayClient.boards()` — board găsit după nume\n"
        "- [x] `MondayClient.items_for_board()` — paginare cursor completă\n"
        "- [x] Parsare Pydantic (`extra=\"ignore\"`)\n"
        "- [x] Webhook n8n acceptat (HTTP 200)\n"
        "- [x] M365 Outlook — email livrat\n\n"
    )

    footer = (
        "---\n"
        f"*Generated by `scripts/smoke_ki_integration_report.py` · "
        f"run id `{report.run_id}`*\n"
    )

    return frontmatter + callout + mermaid + table + checklist + footer
```

- [ ] **Step 4: Run the markdown tests — expect green**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: all `test_render_markdown_*` tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_ki_integration_report.py tests/test_smoke_report.py
git commit -m "feat(smoke): render_markdown (Obsidian-flavored report)"
```

---

## Task 7: `render_html()` + QuickChart URL builder

**Files:**
- Modify: `scripts/smoke_ki_integration_report.py`
- Modify: `tests/test_smoke_report.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_smoke_report.py`:

```python
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
```

- [ ] **Step 2: Run them — expect failures**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: ImportError on `quickchart_url` / `render_html`.

- [ ] **Step 3: Implement both**

Append to `scripts/smoke_ki_integration_report.py`:

```python
import json
from html import escape
from urllib.parse import quote


def quickchart_url(group_counts: list[tuple[str, int]], *, width: int = 600,
                   height: int = 300) -> str:
    """Build a QuickChart.io URL rendering a horizontal bar chart."""
    config = {
        "type": "horizontalBar",
        "data": {
            "labels": [title for title, _ in group_counts],
            "datasets": [
                {
                    "data": [count for _, count in group_counts],
                    "backgroundColor": "#2563eb",
                }
            ],
        },
        "options": {
            "legend": {"display": False},
            "title": {"display": True, "text": "Itemi per grup"},
        },
    }
    return (
        "https://quickchart.io/chart"
        f"?w={width}&h={height}&c={quote(json.dumps(config, separators=(',', ':')))}"
    )


def render_html(report: ReportData, *, recipient: str) -> str:
    ts = report.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    chart_src = quickchart_url(report.group_counts)
    rows_html = "".join(
        f"<tr><td>{escape(title)}</td>"
        f"<td style='text-align:right'>{count}</td></tr>"
        for title, count in report.group_counts
    )
    return f"""\
<!doctype html>
<html lang="ro">
<head><meta charset="utf-8"><title>{escape(report.board_name)} — Smoke Test Report</title></head>
<body style="font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; color:#111; max-width:680px; margin:0 auto; padding:24px;">
  <header style="background:#f4f4f5; padding:16px 20px; border-radius:8px; margin-bottom:20px;">
    <h1 style="margin:0 0 6px 0; font-size:20px;">{escape(report.board_name)} — Smoke Test Report</h1>
    <div style="color:#52525b; font-size:13px;">
      Board <code>{escape(report.board_id)}</code> · Generated {ts} · {escape(report.client_version)}
    </div>
  </header>

  <h2 style="font-size:16px; margin:24px 0 8px 0;">Itemi per grup</h2>
  <table cellpadding="6" cellspacing="0" border="0"
         style="border-collapse:collapse; width:100%; border:1px solid #e4e4e7; font-size:14px;">
    <thead style="background:#fafafa;">
      <tr><th style="text-align:left">Grup</th><th style="text-align:right">Itemi</th></tr>
    </thead>
    <tbody>
      {rows_html}
      <tr style="border-top:2px solid #e4e4e7; background:#fafafa;">
        <td><strong>Total</strong></td>
        <td style="text-align:right"><strong>{report.total_items}</strong></td>
      </tr>
    </tbody>
  </table>

  <div style="margin-top:24px;">
    <img src="{chart_src}" alt="Itemi per grup — bar chart"
         width="600" height="300" style="max-width:100%; height:auto; border:1px solid #e4e4e7; border-radius:6px;">
  </div>

  <footer style="margin-top:32px; padding-top:12px; border-top:1px solid #e4e4e7; color:#71717a; font-size:12px;">
    Smoke test rulat de {escape(report.client_version)} · run id <code>{escape(report.run_id)}</code><br>
    Destinatar: {escape(recipient)}
  </footer>
</body>
</html>
"""
```

- [ ] **Step 4: Run the tests — expect green**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: both new tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_ki_integration_report.py tests/test_smoke_report.py
git commit -m "feat(smoke): render_html with QuickChart bar chart"
```

---

## Task 8: `build_payload()` (with base64-encoded `.md` attachment)

**Files:**
- Modify: `scripts/smoke_ki_integration_report.py`
- Modify: `tests/test_smoke_report.py`

- [ ] **Step 1: Write a failing test**

Append to `tests/test_smoke_report.py`:

```python
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
```

- [ ] **Step 2: Run it — expect ImportError**

Run: `uv run pytest tests/test_smoke_report.py::test_build_payload_roundtrips_markdown_attachment -v`
Expected: ImportError on `build_payload`.

- [ ] **Step 3: Implement `build_payload`**

Append to `scripts/smoke_ki_integration_report.py`:

```python
import base64
from typing import TypedDict


class MarkdownAttachment(TypedDict):
    filename: str
    content_base64: str
    mime_type: str


class WebhookPayload(TypedDict):
    subject: str
    recipient: str
    html_body: str
    markdown_attachment: MarkdownAttachment


def build_payload(
    *,
    report: ReportData,
    recipient: str,
    markdown: str,
    html_body: str,
    markdown_filename: str,
) -> WebhookPayload:
    date_only = report.generated_at.strftime("%Y-%m-%d")
    return WebhookPayload(
        subject=f"{report.board_name} smoke test — {date_only}",
        recipient=recipient,
        html_body=html_body,
        markdown_attachment=MarkdownAttachment(
            filename=markdown_filename,
            content_base64=base64.b64encode(markdown.encode("utf-8")).decode("ascii"),
            mime_type="text/markdown",
        ),
    )
```

- [ ] **Step 4: Re-run — expect green**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_ki_integration_report.py tests/test_smoke_report.py
git commit -m "feat(smoke): build_payload with base64 markdown attachment"
```

---

## Task 9: `post_to_n8n()` with local retry (3 attempts, 1s/2s/4s backoff)

**Files:**
- Modify: `scripts/smoke_ki_integration_report.py`
- Modify: `tests/test_smoke_report.py`

- [ ] **Step 1: Write a failing test for the success path**

Append to `tests/test_smoke_report.py`:

```python
def test_post_to_n8n_success_returns_response_json(monkeypatch) -> None:
    import httpx
    import respx

    from smoke_ki_integration_report import post_to_n8n

    monkeypatch.setattr("smoke_ki_integration_report._sleep", lambda _seconds: None)

    payload = {"subject": "hi", "recipient": "a@b.c", "html_body": "<p>hi</p>",
               "markdown_attachment": {"filename": "x.md", "content_base64": "aGk=",
                                       "mime_type": "text/markdown"}}
    with respx.mock(base_url="https://n8n.example") as router:
        router.post("/webhook/x").respond(
            200, json={"status": "sent", "messageId": "msg-1"}
        )
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

    payload = {"subject": "x", "recipient": "a@b.c", "html_body": "x",
               "markdown_attachment": {"filename": "x.md", "content_base64": "aA==",
                                       "mime_type": "text/markdown"}}
    with respx.mock(base_url="https://n8n.example") as router:
        route = router.post("/webhook/x").mock(
            side_effect=httpx.ConnectError("boom")
        )
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

    payload = {"subject": "x", "recipient": "a@b.c", "html_body": "x",
               "markdown_attachment": {"filename": "x.md", "content_base64": "aA==",
                                       "mime_type": "text/markdown"}}
    with respx.mock(base_url="https://n8n.example") as router:
        router.post("/webhook/x").respond(500, text="boom")
        with pytest.raises(N8nWebhookError) as excinfo:
            post_to_n8n(
                url="https://n8n.example/webhook/x",
                token="secret",
                payload=payload,
            )
        assert "500" in str(excinfo.value)
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: ImportError on `post_to_n8n` and `N8nWebhookError`.

- [ ] **Step 3: Implement `post_to_n8n` + `N8nWebhookError`**

Append to `scripts/smoke_ki_integration_report.py`:

```python
import time

import httpx


class N8nWebhookError(RuntimeError):
    """Raised when the n8n webhook fails after all retries."""


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def post_to_n8n(
    *,
    url: str,
    token: str,
    payload: WebhookPayload | dict,
    timeout: float = 30.0,
    max_attempts: int = 3,
) -> dict:
    """POST `payload` to the n8n webhook with header auth and bounded retry.

    Retries `max_attempts` times on `httpx.TransportError` with exponential
    backoff (1s, 2s, ...). A non-2xx response raises immediately without retry.
    """
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"X-Smoke-Token": token, "Content-Type": "application/json"},
                timeout=timeout,
            )
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                _sleep(1.0 * (2**attempt))
                continue
            raise N8nWebhookError(
                f"transport error after {max_attempts} attempts: {exc!r}"
            ) from exc

        if response.status_code // 100 != 2:
            raise N8nWebhookError(
                f"n8n webhook returned {response.status_code}: {response.text[:500]}"
            )
        try:
            return response.json()
        except ValueError:
            return {"status": "ok", "raw": response.text[:500]}
    # Defensive: loop should always either return or raise.
    raise N8nWebhookError(f"unreachable; last exc: {last_exc!r}")
```

- [ ] **Step 4: Re-run — expect green**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: all `test_post_to_n8n_*` pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_ki_integration_report.py tests/test_smoke_report.py
git commit -m "feat(smoke): post_to_n8n with 3-attempt retry"
```

---

## Task 10: `main()` orchestration + `--dry-run` + `find_board_by_name()`

**Files:**
- Modify: `scripts/smoke_ki_integration_report.py`
- Modify: `tests/test_smoke_report.py`

- [ ] **Step 1: Write failing tests for `find_board_by_name` and end-to-end dry-run**

Append to `tests/test_smoke_report.py`:

```python
def test_find_board_by_name_returns_matching_board() -> None:
    import respx
    from monday_rotocon import MondayClient

    from smoke_ki_integration_report import BoardNotFoundError, find_board_by_name

    data = {
        "data": {
            "boards": [
                {"id": "111", "name": "KI Integration", "workspace_id": "5528271",
                 "columns": []},
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
    from monday_rotocon import MondayClient

    from smoke_ki_integration_report import BoardNotFoundError, find_board_by_name

    data = {
        "data": {
            "boards": [
                {"id": "999", "name": "Other Board", "workspace_id": "5528271",
                 "columns": []},
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
                {"id": "111", "name": "KI Integration", "workspace_id": "5528271",
                 "columns": []},
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
                            {"id": "1", "name": "A", "state": "active",
                             "group": {"id": "g1", "title": "Onboarding (Tag 1)"},
                             "column_values": []},
                            {"id": "2", "name": "B", "state": "active",
                             "group": {"id": "g1", "title": "Onboarding (Tag 1)"},
                             "column_values": []},
                        ],
                    }
                }
            ]
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").mock(side_effect=[
            httpx.Response(200, json=boards_data),
            httpx.Response(200, json=items_data),
        ])
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
```

Also ensure the following imports are at the top of `tests/test_smoke_report.py` (next to the existing `import os`):

```python
import httpx
```

`respx` is imported per-test (already in the test bodies above).

- [ ] **Step 2: Run them — expect failures**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: ImportError on `find_board_by_name`, `BoardNotFoundError`, `Q_FIND_BOARDS`, and AssertionError on `main` dry-run because `main` still returns 0 without writing files.

- [ ] **Step 3: Implement `find_board_by_name`, `Q_FIND_BOARDS`, and wire up `main()`**

Replace the placeholder `main()` in `scripts/smoke_ki_integration_report.py` and add the new helpers. Final shape of the script:

```python
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from monday_rotocon import Board, MondayAPIError, MondayClient

# ----------------------------- queries / errors --------------------------------

Q_FIND_BOARDS = """
query FindBoards($workspace_ids: [ID!]!) {
  boards(workspace_ids: $workspace_ids, limit: 200, state: active) {
    id
    name
    workspace_id
  }
}
""".strip()

DEFAULT_WORKSPACE_ID = "5528271"
DEFAULT_BOARD_NAME = "KI Integration"


class BoardNotFoundError(RuntimeError):
    """Raised when the target board doesn't exist in the workspace."""


def find_board_by_name(
    client: MondayClient, *, name: str, workspace_id: str
) -> Board:
    """Look up a board by exact name within a workspace.

    Raises BoardNotFoundError with a list of board names as a hint if no
    match. Uses an ad-hoc query (not in the library) because the library's
    `boards()` is ID-based; this is the workspace-scoped variant the
    smoke test needs.
    """
    data = client.execute(Q_FIND_BOARDS, variables={"workspace_ids": [workspace_id]})
    boards = data.get("boards") or []
    matches = [b for b in boards if b.get("name") == name]
    if not matches:
        seen = ", ".join(sorted({b.get("name", "?") for b in boards})) or "<none>"
        raise BoardNotFoundError(
            f"Board {name!r} not found in workspace {workspace_id}. "
            f"Boards seen: {seen}"
        )
    # Fall back to library Board validation; columns aren't required here.
    return Board.model_validate(matches[0])


# ----------------------------- main orchestration ------------------------------


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="KI Integration smoke report")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch + render + save Markdown locally; do not POST to n8n.")
    parser.add_argument("--workspace-id", default=DEFAULT_WORKSPACE_ID,
                        help=f"Workspace ID (default: {DEFAULT_WORKSPACE_ID})")
    parser.add_argument("--board-name", default=DEFAULT_BOARD_NAME,
                        help=f"Board name (default: {DEFAULT_BOARD_NAME!r})")
    args = parser.parse_args()
    env = load_env()

    from monday_rotocon import __version__

    try:
        with MondayClient(api_token=env.monday_token) as client:
            board = find_board_by_name(
                client, name=args.board_name, workspace_id=args.workspace_id
            )
            items = list(client.items_for_board(board_id=board.id))
    except BoardNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except MondayAPIError as exc:
        print(f"monday API error: {exc!r}", file=sys.stderr)
        return 2

    group_counts = group_items_by_title(items)
    generated_at = _now_utc()
    run_id = uuid.uuid4().hex[:16]
    report = ReportData(
        board_id=str(board.id),
        board_name=board.name,
        workspace_id=args.workspace_id,
        generated_at=generated_at,
        client_version=f"monday_rotocon v{__version__}",
        run_id=run_id,
        group_counts=group_counts,
        total_items=len(items),
    )

    md = render_markdown(report)
    html = render_html(report, recipient=env.recipient)

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    stamp = generated_at.strftime("%Y-%m-%d-%H%M")
    md_filename = f"{stamp}-ki-integration-smoke.md"
    md_path = reports_dir / md_filename
    md_path.write_text(md, encoding="utf-8")
    print(f"Wrote {md_path}")

    if args.dry_run:
        print(f"--dry-run: skipping n8n POST (board_id={board.id}, items={len(items)})")
        return 0

    payload = build_payload(
        report=report,
        recipient=env.recipient,
        markdown=md,
        html_body=html,
        markdown_filename=md_filename,
    )
    try:
        response = post_to_n8n(
            url=env.webhook_url, token=env.webhook_token, payload=payload
        )
    except N8nWebhookError as exc:
        print(f"n8n webhook error: {exc!r}", file=sys.stderr)
        return 3

    print(
        f"OK board_id={board.id} items={len(items)} "
        f"n8n_messageId={response.get('messageId', '?')} markdown={md_path}"
    )
    return 0
```

(Make sure these imports are at the top of the file alongside the existing ones; remove duplicate imports.)

- [ ] **Step 4: Run the full smoke test file**

Run: `uv run pytest tests/test_smoke_report.py -v`
Expected: all tests pass, including the dry-run end-to-end test.

- [ ] **Step 5: Run the WHOLE suite + mypy + ruff**

Run:

```bash
uv run ruff format scripts tests
uv run ruff check scripts tests src
uv run pytest
```

Expected: format clean, lint clean, all tests pass. (`mypy` only covers `src/`; the script's strict typing is not required by the project's mypy config.)

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke_ki_integration_report.py tests/test_smoke_report.py
git commit -m "feat(smoke): main() orchestration with --dry-run + board lookup"
```

---

## Task 11: Opt-in live integration test

**Files:**
- Create: `tests/integration/test_smoke_report_live.py`
- Verify: `tests/integration/__init__.py` exists (or create it as empty if not).

- [ ] **Step 1: Ensure `tests/integration/__init__.py` exists**

```bash
ls tests/integration/__init__.py 2>/dev/null || touch tests/integration/__init__.py
```

- [ ] **Step 2: Create the live integration test**

Create `tests/integration/test_smoke_report_live.py`:

```python
"""Live integration test for the KI Integration smoke report.

Hits the real monday.com API AND the dedicated n8n test-echo workflow.
Never sends mail. Opt-in via the `integration` marker.

Required env:
  MONDAY_API_TOKEN          — real token
  N8N_WEBHOOK_URL_TEST      — full URL of the test-echo workflow,
                              e.g. https://n8n.rotocon.world/webhook/monday-smoke-report-test
  N8N_WEBHOOK_TOKEN         — same token configured on the credential
  REPORT_RECIPIENT          — any address; the echo workflow does NOT send mail
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_smoke_report_against_real_monday_and_echo_webhook(tmp_path, monkeypatch) -> None:
    required = [
        "MONDAY_API_TOKEN",
        "N8N_WEBHOOK_URL_TEST",
        "N8N_WEBHOOK_TOKEN",
        "REPORT_RECIPIENT",
    ]
    for var in required:
        if not os.environ.get(var):
            pytest.skip(f"missing {var}")

    monkeypatch.chdir(tmp_path)
    env = os.environ.copy()
    # Point the script at the test-echo URL.
    env["N8N_WEBHOOK_URL"] = env["N8N_WEBHOOK_URL_TEST"]

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "smoke_ki_integration_report.py"
    assert script.exists()

    result = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )

    reports = list((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "KI Integration" in content
```

- [ ] **Step 3: Verify it's skipped without env (default unit run)**

Run: `uv run pytest tests/integration/test_smoke_report_live.py -v`
Expected: SKIPPED (no env or marker not selected). It will not run during the default `uv run pytest` either because the test sits behind the `integration` marker — but pytest still collects it. To confirm:

```bash
uv run pytest -v -m "not integration" tests/integration/test_smoke_report_live.py
```

Expected: `deselected` count = 1.

- [ ] **Step 4: Run the live integration test with env set**

Export the variables described in the test's docstring (use the test-echo URL, NOT the smoke email URL), then:

```bash
uv run pytest tests/integration/test_smoke_report_live.py -m integration -v
```

Expected: PASS. The echo workflow returns 200 without sending mail.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_smoke_report_live.py tests/integration/__init__.py
git commit -m "test(smoke): opt-in live integration test using n8n echo workflow"
```

---

## Task 12: Manual end-to-end + final quality gates

**No new files.** This task confirms the smoke test actually works by running it for real.

- [ ] **Step 1: Run a real dry-run**

Make sure `MONDAY_API_TOKEN`, `N8N_WEBHOOK_URL`, `N8N_WEBHOOK_TOKEN`, `REPORT_RECIPIENT` are set in `.env`. Then:

```bash
uv run python scripts/smoke_ki_integration_report.py --dry-run
```

Expected: stdout shows `Wrote reports/<timestamp>-ki-integration-smoke.md` and `--dry-run: skipping n8n POST (board_id=..., items=...)`. The Markdown file exists. Open it and skim for sanity (frontmatter, table, mermaid block).

- [ ] **Step 2: Run the full pipeline**

```bash
uv run python scripts/smoke_ki_integration_report.py
```

Expected: stdout ends with a line like `OK board_id=... items=... n8n_messageId=... markdown=reports/...md`. An email arrives in the Outlook mailbox of `REPORT_RECIPIENT` within ~30s. The email contains the header, the table, the QuickChart bar chart image (when rendered by Outlook web), and the `.md` attachment.

If the email does NOT arrive but the script returned 0:
- Check the n8n execution log for the `monday-smoke-report-email` workflow.
- Most likely cause: attachment shape mismatch with the Microsoft Outlook node. Re-discover the node's `additionalFields.attachmentsUi` shape via `mcp__n8n-mcp__get_node(nodeType="nodes-base.microsoftOutlook")` and adjust the workflow JSON. Re-validate, re-activate, re-run.

- [ ] **Step 3: Run full project quality gates**

```bash
uv run ruff format .
uv run ruff check .
uv run mypy src
uv run pytest
```

Expected: format clean, lint clean, mypy strict success, all default-marker tests pass.

- [ ] **Step 4: Commit any formatting fix-ups, then stop**

```bash
git status
# If anything is unstaged from `ruff format` or doc tweaks:
git add -A
git commit -m "style: post-implementation formatting pass"
```

Otherwise: done. Push the branch when ready.

---

## Summary of touched files (cross-check before final commit)

```
.env.example                                              (created)
.gitignore                                                (modified)
pyproject.toml                                            (modified)
src/monday_rotocon/__init__.py                            (modified)
src/monday_rotocon/models.py                              (modified)
src/monday_rotocon/queries.py                             (modified)
scripts/smoke_ki_integration_report.py                    (created)
tests/test_client.py                                      (modified)
tests/test_models.py                                      (modified)
tests/test_smoke_report.py                                (created)
tests/integration/__init__.py                             (verified/created)
tests/integration/test_smoke_report_live.py               (created)
reports/                                                  (gitignored at runtime)
```

n8n side (not in git):

```
Credential "Smoke Report Webhook Token"     (httpHeaderAuth, X-Smoke-Token)
Workflow  "monday-smoke-report-email"       (Webhook → Outlook → Respond)
Workflow  "monday-smoke-report-test-echo"   (Webhook → Respond)
```
