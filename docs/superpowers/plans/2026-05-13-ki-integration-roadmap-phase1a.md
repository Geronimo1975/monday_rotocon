# KI Integration Board ↔ /roadmap Page — Phase 1a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a daily-refreshed, read-only roadmap page at `https://george.rotocon.world/roadmap` that renders KPI strip + Gantt + Table from the KI Integration monday board.

**Architecture:** Three layers, executed bottom-up.
1. **Board enrichment** — a stdlib-only Python script mutates the KI Integration board to add 12 columns and 3 views. Idempotent.
2. **Python export tool** — a minimum slice of `monday_rotocon` package (settings, transport, client, models, CLI). Exposes `monday export roadmap` that produces a versioned `roadmap.json` matching the spec contract.
3. **Static frontend** — one self-contained `roadmap.html` that reads `roadmap.json` via `fetch()` and renders the page. No build step.

A daily GitHub Action ties them together: runs the exporter, commits `out/roadmap.json`. The site repo pulls the JSON.

**Tech Stack:**
- Python 3.12, uv, Typer (CLI), httpx (transport), Pydantic v2 (models + JSON schema)
- pytest, pytest-asyncio, respx (mocking httpx), pytest-cov
- Frontend: vanilla HTML + JS (DOM APIs, no innerHTML) + Tailwind via CDN + vendored frappe-gantt (MIT)
- GitHub Actions for daily cron

**Spec reference:** [`docs/superpowers/specs/2026-05-13-ki-integration-roadmap-design.md`](../specs/2026-05-13-ki-integration-roadmap-design.md)

**Dependencies:** This plan implements just enough of sub-project A (the `monday_rotocon` skeleton plan at `docs/superpowers/plans/2026-05-10-monday-core-skeleton.md`) to support `monday export roadmap`. The remainder of sub-project A (full async client, `boards.list`, `items.list` iterators, etc.) can be implemented separately later — Phase 1a does not require it.

---

## Plan structure

| Part | Tasks | Purpose |
|---|---|---|
| **0. Pre-flight** | 1 | Verify current state |
| **1. Board enrichment** | 2-6 | Add columns + views to KI Integration via stdlib script |
| **2. Python package — minimum slice** | 7-13 | Build settings, transport, models, client, CLI commands |
| **3. Static frontend** | 14-15 | Build the `roadmap.html` page |
| **4. Daily pipeline + handoff** | 16-21 | Cron job, integration docs, manual data-entry checklist |

---

## Part 0 — Pre-flight

### Task 1: Smoke-test current state

**Files:**
- Read-only: `scripts/bootstrap_ki_integration.py` (already exists)
- Read-only: `.env` (token must be present)

- [ ] **Step 1: Verify token loads and the API responds**

```bash
cd /Users/rotocondemo/monday_rotocon
set -a && source .env && set +a
curl -sS -X POST https://api.monday.com/v2 \
  -H "Authorization: $MONDAY_API_TOKEN" \
  -H "API-Version: 2024-10" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ me { id name email is_admin account { id name slug tier } } }"}'
```

Expected output contains:
```json
{"data":{"me":{"id":"103121773","name":"George Sebastian Cucuiet",...,"account":{"id":"31832272","name":"rotocons Team","slug":"rotocon-world","tier":"pro"}}}}
```

If the request fails: stop. Either the token expired or `.env` isn't loaded. Resolve before proceeding.

- [ ] **Step 2: Verify KI Integration board state**

```bash
curl -sS -X POST https://api.monday.com/v2 \
  -H "Authorization: $MONDAY_API_TOKEN" \
  -H "API-Version: 2024-10" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ boards(ids:[5096182046]) { id name columns { id title type } groups { id title } items_count } }"}' \
  | python3 -m json.tool
```

Expected: board exists, has exactly 1 column (`name` of type `name`), 5 groups, 29 items. If columns count > 1, this plan's column-creation script must be tested for idempotency — proceed anyway, the script is designed to handle this.

- [ ] **Step 3: Verify `uv` is available**

```bash
uv --version
```

Expected: prints a version (e.g., `uv 0.4.x`). If not installed, install per https://docs.astral.sh/uv/getting-started/installation/.

- [ ] **Step 4: No commit — this is pre-flight only.**

---

## Part 1 — Board enrichment (stdlib-only script)

### Task 2: Create `extend_ki_integration_columns.py` skeleton

**Why stdlib-only:** Mirrors the `bootstrap_ki_integration.py` precedent. The script must run before `uv sync` has been performed and must not depend on the package it's enriching.

**Files:**
- Create: `scripts/extend_ki_integration_columns.py`
- Reference: `scripts/bootstrap_ki_integration.py` (use as structural template)

- [ ] **Step 1: Create the file with the load_token / gql helpers ported from bootstrap script**

```python
#!/usr/bin/env python3
"""Idempotent enrichment: add the 12 columns + 3 views needed for the
roadmap page to the KI Integration board (id 5096182046).

This is operational tooling, NOT part of the monday_rotocon skeleton.
Runs anytime; safe to re-run — existing columns / views are detected
by title and skipped.

Uses only the Python stdlib so it works before `uv sync` has been run.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.monday.com/v2"
API_VERSION = "2024-10"
BOARD_ID = 5096182046
ACCOUNT_SLUG = "rotocon-world"


def load_token() -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        sys.exit(f"FATAL: no .env at {env_path}")
    for line in env_path.read_text().splitlines():
        if line.startswith("MONDAY_API_TOKEN="):
            return line.split("=", 1)[1].strip()
    sys.exit("FATAL: MONDAY_API_TOKEN not found in .env")


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "API-Version": API_VERSION,
            "User-Agent": "monday_rotocon-extend/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")
    if payload.get("errors"):
        sys.exit(f"GraphQL errors: {json.dumps(payload['errors'], indent=2)}")
    return payload["data"]


def main() -> int:
    token = load_token()
    print(f"📌 Extending KI Integration board (id={BOARD_ID})...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the skeleton to verify it loads and exits cleanly**

```bash
cd /Users/rotocondemo/monday_rotocon
python3 scripts/extend_ki_integration_columns.py
```

Expected output:
```
📌 Extending KI Integration board (id=5096182046)...
```
Exit code 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/extend_ki_integration_columns.py
git commit -m "feat(scripts): skeleton for extend_ki_integration_columns.py"
```

---

### Task 3: Add column specifications and idempotent creation

**Files:**
- Modify: `scripts/extend_ki_integration_columns.py`
- Create: `tests/unit/test_extend_columns.py`

- [ ] **Step 1: Add `COLUMNS_PLAN` and the idempotency helper to the script**

After the `gql` function in `scripts/extend_ki_integration_columns.py`, add:

```python
# Column specs from spec §4.1 — title, type, defaults (JSON string for monday)
COLUMNS_PLAN: list[dict] = [
    {
        "title": "Status",
        "type": "status",
        "defaults": json.dumps({
            "labels": {
                "0": "Not started",
                "1": "In progress",
                "2": "Blocked",
                "3": "Done",
                "4": "Deferred",
            }
        }),
    },
    {
        "title": "Phase",
        "type": "status",
        "defaults": json.dumps({
            "labels": {
                "0": "M1", "1": "M2", "2": "M3",
                "3": "M4", "4": "M5", "5": "M6",
                "6": "Onboarding", "7": "Ongoing",
            }
        }),
    },
    {"title": "Owner", "type": "people", "defaults": "{}"},
    {"title": "Timeline", "type": "timeline", "defaults": "{}"},
    {"title": "Due", "type": "date", "defaults": "{}"},
    {
        "title": "Priority",
        "type": "status",
        "defaults": json.dumps({
            "labels": {
                "0": "Critical", "1": "High", "2": "Medium", "3": "Low",
            }
        }),
    },
    {"title": "KPI link", "type": "link", "defaults": "{}"},
    {"title": "Dependency", "type": "dependency", "defaults": "{}"},
    {"title": "% Progress", "type": "numbers", "defaults": "{}"},
    {"title": "Notes", "type": "long_text", "defaults": "{}"},
    {"title": "KPI target", "type": "text", "defaults": "{}"},
    {"title": "KPI current", "type": "numbers", "defaults": "{}"},
]


def fetch_existing_columns(token: str, board_id: int) -> list[dict]:
    """Return the current `columns` of a board."""
    data = gql(
        token,
        "query($id: [ID!]) { boards(ids: $id) { columns { id title type } } }",
        {"id": [str(board_id)]},
    )
    return data["boards"][0]["columns"]


def compute_missing_columns(
    existing: list[dict],
    desired: list[dict],
) -> list[dict]:
    """Pure function: which desired columns are not yet on the board (by title)."""
    have = {c["title"] for c in existing}
    return [c for c in desired if c["title"] not in have]
```

- [ ] **Step 2: Write a failing unit test for `compute_missing_columns`**

Create `tests/unit/test_extend_columns.py`:

```python
"""Unit tests for the idempotency logic in
`scripts/extend_ki_integration_columns.py`.

The script lives outside the package; we import it via sys.path
gymnastics so pytest can exercise the pure functions inside.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts"
    / "extend_ki_integration_columns.py"
)


@pytest.fixture(scope="module")
def script_module():
    spec = importlib.util.spec_from_file_location("extend_cols", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_compute_missing_columns_empty_board(script_module):
    existing: list[dict] = []
    desired = [
        {"title": "Status", "type": "status", "defaults": "{}"},
        {"title": "Owner", "type": "people", "defaults": "{}"},
    ]
    missing = script_module.compute_missing_columns(existing, desired)
    assert [c["title"] for c in missing] == ["Status", "Owner"]


def test_compute_missing_columns_partial_overlap(script_module):
    existing = [
        {"id": "name", "title": "Name", "type": "name"},
        {"id": "status_x", "title": "Status", "type": "status"},
    ]
    desired = [
        {"title": "Status", "type": "status", "defaults": "{}"},
        {"title": "Owner", "type": "people", "defaults": "{}"},
    ]
    missing = script_module.compute_missing_columns(existing, desired)
    assert [c["title"] for c in missing] == ["Owner"]


def test_compute_missing_columns_full_overlap(script_module):
    existing = [
        {"id": "name", "title": "Name", "type": "name"},
        {"id": "s", "title": "Status", "type": "status"},
        {"id": "p", "title": "Owner", "type": "people"},
    ]
    desired = [
        {"title": "Status", "type": "status", "defaults": "{}"},
        {"title": "Owner", "type": "people", "defaults": "{}"},
    ]
    missing = script_module.compute_missing_columns(existing, desired)
    assert missing == []
```

- [ ] **Step 3: Run the tests and verify they pass**

```bash
cd /Users/rotocondemo/monday_rotocon
uv sync --all-extras
uv run pytest tests/unit/test_extend_columns.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Now wire `compute_missing_columns` into `main()`**

Replace `main()` in `scripts/extend_ki_integration_columns.py` with:

```python
def create_column(token: str, board_id: int, spec: dict) -> str:
    """Create one column on the board; return its new id."""
    data = gql(
        token,
        """
        mutation($board: ID!, $title: String!, $type: ColumnType!, $defaults: JSON) {
          create_column(board_id: $board, title: $title, column_type: $type, defaults: $defaults) {
            id title type
          }
        }
        """,
        {
            "board": str(board_id),
            "title": spec["title"],
            "type": spec["type"],
            "defaults": spec["defaults"],
        },
    )
    return data["create_column"]["id"]


def main() -> int:
    token = load_token()
    print(f"📌 Extending KI Integration board (id={BOARD_ID})...")

    existing = fetch_existing_columns(token, BOARD_ID)
    print(f"   {len(existing)} columns currently on board: {[c['title'] for c in existing]}")

    missing = compute_missing_columns(existing, COLUMNS_PLAN)
    if not missing:
        print("✅ All 12 columns already present — nothing to do.")
        return 0

    print(f"   {len(missing)} column(s) to create: {[c['title'] for c in missing]}")
    for spec in missing:
        new_id = create_column(token, BOARD_ID, spec)
        print(f"   + [{new_id}] {spec['title']} ({spec['type']})")
        time.sleep(0.15)  # be polite to monday rate limits

    print(f"\n🎉 Done. {len(missing)} column(s) created.")
    print(f"   Board URL: https://{ACCOUNT_SLUG}.monday.com/boards/{BOARD_ID}")
    return 0
```

- [ ] **Step 5: Re-run the unit tests to confirm nothing regressed**

```bash
uv run pytest tests/unit/test_extend_columns.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/extend_ki_integration_columns.py tests/unit/test_extend_columns.py
git commit -m "feat(scripts): idempotent column creation for KI Integration board"
```

---

### Task 4: Add manual-view-setup instructions

monday's GraphQL does not expose a reliable mutation for creating board views with configurable filters and column layouts; views are typically created via the UI. The script will instead print the manual instructions after creating columns.

**Files:**
- Modify: `scripts/extend_ki_integration_columns.py`

- [ ] **Step 1: Append a `print_view_setup_instructions()` function**

After `main()` in `scripts/extend_ki_integration_columns.py` (or before but called near the end of main), add:

```python
def print_view_setup_instructions() -> None:
    """View creation is manual via monday UI. Print the instructions."""
    print()
    print("📋 NEXT — create board views manually (monday UI):")
    print()
    print(f"   1. Open https://{ACCOUNT_SLUG}.monday.com/boards/{BOARD_ID}")
    print("   2. Click '+ Add view' in the top-right.")
    print()
    print("   View 1: 'Roadmap (Gantt)'")
    print("     - Type: Gantt")
    print("     - Date column: Timeline")
    print("     - Filter: Phase in {M1, M2, M3, M4, M5, M6}")
    print()
    print("   View 2: 'Table (full)'")
    print("     - Type: Table")
    print("     - All columns visible, default sort by Timeline.start")
    print()
    print("   View 3: 'KPI Cards'")
    print("     - Type: Cards")
    print("     - Filter: Phase = Ongoing")
    print()
```

Then call it at the end of `main()` (before `return 0`):

```python
    print(f"\n🎉 Done. {len(missing)} column(s) created.")
    print(f"   Board URL: https://{ACCOUNT_SLUG}.monday.com/boards/{BOARD_ID}")
    print_view_setup_instructions()
    return 0
```

- [ ] **Step 2: Smoke-test the function in isolation**

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('e', 'scripts/extend_ki_integration_columns.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.print_view_setup_instructions()
"
```

Expected: the instructions print without error.

- [ ] **Step 3: Commit**

```bash
git add scripts/extend_ki_integration_columns.py
git commit -m "feat(scripts): print manual view-setup instructions after column creation"
```

---

### Task 5: Run script against the live board

**Files:** (none modified — execution step)

- [ ] **Step 1: Ensure `.env` is loaded and run the script**

```bash
cd /Users/rotocondemo/monday_rotocon
set -a && source .env && set +a
python3 scripts/extend_ki_integration_columns.py
```

Expected output (first run):
```
📌 Extending KI Integration board (id=5096182046)...
   1 columns currently on board: ['Name']
   12 column(s) to create: ['Status', 'Phase', 'Owner', 'Timeline', 'Due', 'Priority', 'KPI link', 'Dependency', '% Progress', 'Notes', 'KPI target', 'KPI current']
   + [status] Status (status)
   + [status1] Phase (status)
   ... (10 more)

🎉 Done. 12 column(s) created.
   Board URL: https://rotocon-world.monday.com/boards/5096182046

📋 NEXT — create board views manually (monday UI):
   1. Open ...
   ...
```

- [ ] **Step 2: Verify in monday.com UI that all 12 columns appear**

Manually open `https://rotocon-world.monday.com/boards/5096182046` in a browser. Confirm: the board now has 13 columns total (the original `Name` plus the 12 new ones).

- [ ] **Step 3: Re-run the script to verify idempotency**

```bash
python3 scripts/extend_ki_integration_columns.py
```

Expected output:
```
📌 Extending KI Integration board (id=5096182046)...
   13 columns currently on board: ['Name', 'Status', 'Phase', ...]
✅ All 12 columns already present — nothing to do.
```

- [ ] **Step 4: Manually create the 3 views in monday UI** (per the printed instructions).

This is a checkpoint where George does the UI work. Verify each view loads without errors and shows expected data shape (even if empty — items don't have Timeline data yet).

- [ ] **Step 5: No commit — this is execution, not code.**

---

### Task 6: Smoke verification — query the enriched board

**Files:** (none modified — execution step)

- [ ] **Step 1: Confirm the enriched board structure via API**

```bash
cd /Users/rotocondemo/monday_rotocon
set -a && source .env && set +a
curl -sS -X POST https://api.monday.com/v2 \
  -H "Authorization: $MONDAY_API_TOKEN" \
  -H "API-Version: 2024-10" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ boards(ids:[5096182046]) { columns { id title type settings_str } groups { id title } items_count } }"}' \
  | python3 -m json.tool
```

Expected: 13 columns. Status/Phase/Priority columns have non-empty `settings_str` reflecting the labels.

- [ ] **Step 2: Add `out/` to `.gitignore`**

```bash
echo "out/" >> .gitignore
git add .gitignore
git commit -m "chore: gitignore the out/ directory"
```

Part 1 is complete.

---

## Part 2 — Python package, minimum slice

This part builds the smallest subset of the `monday_rotocon` package that supports `monday export roadmap`. Defer the full sub-project A surface (boards.list pagination, async client, all column-value subtypes) to a separate effort.

### Task 7: Settings + errors modules

**Files:**
- Create: `src/monday_rotocon/settings.py`
- Create: `src/monday_rotocon/_errors.py`
- Create: `tests/unit/test_settings.py`
- Create: `tests/unit/test_errors.py`

- [ ] **Step 1: Write failing test for `settings.py`**

Create `tests/unit/test_settings.py`:

```python
"""Tests for monday_rotocon.settings."""
from __future__ import annotations

import pytest


def test_settings_reads_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token-123")
    monkeypatch.delenv("MONDAY_API_VERSION", raising=False)

    from monday_rotocon.settings import Settings

    s = Settings()
    assert s.monday_api_token.get_secret_value() == "test-token-123"
    assert s.monday_api_version == "2024-10"  # default
    assert s.monday_api_url == "https://api.monday.com/v2"
    assert s.request_timeout_s == 30.0


def test_settings_token_is_secret_str(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONDAY_API_TOKEN", "test-token-123")
    from monday_rotocon.settings import Settings

    s = Settings()
    # Token must NOT leak into repr() or str()
    assert "test-token-123" not in repr(s)
    assert "test-token-123" not in str(s)


def test_settings_missing_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MONDAY_API_TOKEN", raising=False)
    from monday_rotocon.settings import Settings

    with pytest.raises(Exception):  # pydantic ValidationError
        Settings()
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/unit/test_settings.py -v
```

Expected: ImportError or ModuleNotFoundError for `monday_rotocon.settings`.

- [ ] **Step 3: Implement `settings.py`**

Create `src/monday_rotocon/settings.py`:

```python
"""Application configuration for monday_rotocon.

Reads from environment variables (`.env` file via pydantic-settings).
"""
from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    monday_api_token: SecretStr = Field(
        ...,
        description="JWT issued in monday.com Developer settings.",
    )
    monday_api_version: str = Field(
        default="2024-10",
        description="Sent as the `API-Version` header on every request.",
    )
    monday_api_url: str = Field(
        default="https://api.monday.com/v2",
        description="GraphQL endpoint; escape hatch for proxies/tests.",
    )
    monday_region: str = Field(
        default="euc1",
        description="Informational only; the API URL is region-independent.",
    )
    request_timeout_s: float = Field(
        default=30.0,
        description="Per-request timeout passed to httpx.",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_settings.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Write failing test for `_errors.py`**

Create `tests/unit/test_errors.py`:

```python
"""Tests for monday_rotocon._errors."""
from __future__ import annotations


def test_monday_error_hierarchy() -> None:
    from monday_rotocon._errors import (
        MondayError,
        MondayAPIError,
        RateLimited,
        ComplexityExhausted,
    )

    assert issubclass(MondayAPIError, MondayError)
    assert issubclass(RateLimited, MondayError)
    assert issubclass(ComplexityExhausted, MondayError)


def test_monday_api_error_carries_request_id() -> None:
    from monday_rotocon._errors import MondayAPIError

    err = MondayAPIError("boom", request_id="abc-123")
    assert "boom" in str(err)
    assert err.request_id == "abc-123"


def test_rate_limited_carries_retry_after() -> None:
    from monday_rotocon._errors import RateLimited

    err = RateLimited("slow down", retry_after_s=30, request_id="r1")
    assert err.retry_after_s == 30
    assert err.request_id == "r1"


def test_complexity_exhausted_carries_budget() -> None:
    from monday_rotocon._errors import ComplexityExhausted

    err = ComplexityExhausted(
        "budget gone",
        reset_in_s=42,
        budget_remaining=0,
        budget_total=10_000_000,
        request_id="r2",
    )
    assert err.reset_in_s == 42
    assert err.budget_remaining == 0
    assert err.budget_total == 10_000_000
```

- [ ] **Step 6: Run to verify it fails**

```bash
uv run pytest tests/unit/test_errors.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 7: Implement `_errors.py`**

Create `src/monday_rotocon/_errors.py`:

```python
"""Exception hierarchy for monday_rotocon."""
from __future__ import annotations


class MondayError(Exception):
    """Base class for every error this package raises."""

    def __init__(self, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id


class MondayAPIError(MondayError):
    """Raised when monday's API returns a GraphQL error or non-rate-limit 4xx."""


class RateLimited(MondayError):
    """Raised on 429 or `Minute_Limit_Exceeded` error_code."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_s: int,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id)
        self.retry_after_s = retry_after_s


class ComplexityExhausted(MondayError):
    """Raised on `ComplexityException` error_code."""

    def __init__(
        self,
        message: str,
        *,
        reset_in_s: int,
        budget_remaining: int,
        budget_total: int,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id)
        self.reset_in_s = reset_in_s
        self.budget_remaining = budget_remaining
        self.budget_total = budget_total
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_settings.py tests/unit/test_errors.py -v
```

Expected: 7 passed (3 settings + 4 errors).

- [ ] **Step 9: Commit**

```bash
git add src/monday_rotocon/settings.py src/monday_rotocon/_errors.py \
        tests/unit/test_settings.py tests/unit/test_errors.py
git commit -m "feat(core): settings + error hierarchy for monday_rotocon"
```

---

### Task 8: GraphQL transport

**Files:**
- Create: `src/monday_rotocon/_transport.py`
- Create: `tests/unit/test_transport.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_transport.py`:

```python
"""Tests for monday_rotocon._transport."""
from __future__ import annotations

import pytest
import respx

from monday_rotocon._errors import (
    ComplexityExhausted,
    MondayAPIError,
    RateLimited,
)


@pytest.fixture
def transport():
    from monday_rotocon._transport import Transport
    from monday_rotocon.settings import Settings

    settings = Settings(monday_api_token="test-token")  # type: ignore[arg-type]
    return Transport(settings)


@respx.mock
def test_transport_sends_correct_headers_and_body(transport) -> None:
    route = respx.post("https://api.monday.com/v2").respond(
        200, json={"data": {"me": {"id": "1"}}, "extensions": {"request_id": "r1"}}
    )

    result = transport.execute("query { me { id } }", variables={"x": 1})

    assert result == {"me": {"id": "1"}}
    req = route.calls.last.request
    assert req.headers["authorization"] == "test-token"  # no Bearer prefix
    assert req.headers["api-version"] == "2024-10"
    assert req.headers["content-type"] == "application/json"
    body = req.content.decode()
    assert '"query": "query { me { id } }"' in body
    assert '"variables": {"x": 1}' in body


@respx.mock
def test_transport_raises_monday_api_error_on_graphql_errors(transport) -> None:
    respx.post("https://api.monday.com/v2").respond(
        200,
        json={
            "errors": [{"message": "Field not found"}],
            "extensions": {"request_id": "rq-1"},
        },
    )
    with pytest.raises(MondayAPIError) as exc:
        transport.execute("query { broken }")
    assert "Field not found" in str(exc.value)
    assert exc.value.request_id == "rq-1"


@respx.mock
def test_transport_raises_rate_limited_on_429(transport) -> None:
    respx.post("https://api.monday.com/v2").respond(
        429,
        json={
            "error_code": "Minute_Limit_Exceeded",
            "error_message": "calm down",
        },
        headers={"Retry-After": "30"},
    )
    with pytest.raises(RateLimited) as exc:
        transport.execute("query { me { id } }")
    assert exc.value.retry_after_s == 30


@respx.mock
def test_transport_raises_complexity_exhausted(transport) -> None:
    respx.post("https://api.monday.com/v2").respond(
        200,
        json={
            "errors": [
                {
                    "message": "Complexity budget exhausted",
                    "extensions": {
                        "code": "ComplexityException",
                        "reset_in_x_seconds": 42,
                        "complexity": {
                            "after": 0,
                            "before": 5000,
                            "query": 5000,
                        },
                    },
                }
            ]
        },
    )
    with pytest.raises(ComplexityExhausted) as exc:
        transport.execute("query { boards { id } }")
    assert exc.value.reset_in_s == 42


@respx.mock
def test_transport_returns_data_field(transport) -> None:
    respx.post("https://api.monday.com/v2").respond(
        200,
        json={
            "data": {"me": {"id": "103121773", "name": "George"}},
            "extensions": {"complexity": {"after": 9_999_000, "before": 10_000_000, "query": 1000}},
        },
    )
    result = transport.execute("query { me { id name } }")
    assert result == {"me": {"id": "103121773", "name": "George"}}
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/unit/test_transport.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `_transport.py`**

Create `src/monday_rotocon/_transport.py`:

```python
"""GraphQL transport for monday_rotocon.

Sync-only for Phase 1a; an async sibling can be added later (sub-project B).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from monday_rotocon._errors import (
    ComplexityExhausted,
    MondayAPIError,
    RateLimited,
)
from monday_rotocon.settings import Settings

logger = logging.getLogger(__name__)


class Transport:
    """Thin wrapper around `httpx.Client` for monday's GraphQL endpoint."""

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.request_timeout_s,
            headers={
                "Authorization": settings.monday_api_token.get_secret_value(),
                "API-Version": settings.monday_api_version,
                "Content-Type": "application/json",
                "User-Agent": "monday_rotocon/0.1",
            },
        )

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one GraphQL request; return the `data` field."""
        payload = {"query": query, "variables": variables or {}}
        response = self._client.post(self._settings.monday_api_url, json=payload)
        request_id = self._extract_request_id(response)

        if response.status_code == 429:
            raise RateLimited(
                response.text,
                retry_after_s=int(response.headers.get("Retry-After", "30")),
                request_id=request_id,
            )

        if response.status_code >= 400:
            raise MondayAPIError(
                f"HTTP {response.status_code}: {response.text}",
                request_id=request_id,
            )

        body = response.json()

        if "errors" in body and body["errors"]:
            first = body["errors"][0]
            ext = first.get("extensions", {}) or {}
            if ext.get("code") == "ComplexityException":
                comp = ext.get("complexity", {}) or {}
                raise ComplexityExhausted(
                    first["message"],
                    reset_in_s=int(ext.get("reset_in_x_seconds", 0)),
                    budget_remaining=int(comp.get("after", 0)),
                    budget_total=10_000_000,
                    request_id=request_id,
                )
            raise MondayAPIError(
                "; ".join(e.get("message", "?") for e in body["errors"]),
                request_id=request_id,
            )

        if "data" not in body:
            raise MondayAPIError("response had no `data` field", request_id=request_id)

        complexity = (body.get("extensions") or {}).get("complexity")
        if complexity:
            remaining = complexity.get("after", -1)
            if 0 <= remaining < 1_000_000:
                logger.warning(
                    "complexity budget low: remaining=%d/10000000 request_id=%s",
                    remaining,
                    request_id,
                )

        return body["data"]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Transport":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @staticmethod
    def _extract_request_id(response: httpx.Response) -> str | None:
        try:
            body = response.json()
        except ValueError:
            return response.headers.get("x-request-id")
        ext = body.get("extensions") or {}
        return ext.get("request_id") or response.headers.get("x-request-id")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_transport.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/monday_rotocon/_transport.py tests/unit/test_transport.py
git commit -m "feat(core): GraphQL transport with rate-limit + complexity error mapping"
```

---

### Task 9: GraphQL query files + loader

**Files:**
- Create: `src/monday_rotocon/queries/__init__.py`
- Create: `src/monday_rotocon/queries/me.graphql`
- Create: `src/monday_rotocon/queries/roadmap.graphql`
- Create: `tests/unit/test_queries.py`

- [ ] **Step 1: Create the queries directory and files**

```bash
mkdir -p src/monday_rotocon/queries
```

Create `src/monday_rotocon/queries/me.graphql`:

```graphql
query Me {
  me {
    id
    name
    email
    is_admin
    account {
      id
      name
      slug
      tier
    }
  }
}
```

Create `src/monday_rotocon/queries/roadmap.graphql`:

```graphql
query Roadmap($boardId: [ID!]!, $cursor: String) {
  boards(ids: $boardId) {
    id
    name
    url
    workspace {
      id
      name
    }
    columns {
      id
      title
      type
      settings_str
    }
    groups {
      id
      title
      color
      position
    }
    items_page(limit: 100, cursor: $cursor) {
      cursor
      items {
        id
        name
        url
        created_at
        updated_at
        group {
          id
          title
        }
        column_values {
          id
          type
          text
          value
          column {
            id
            title
            type
          }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write failing test for the loader**

Create `tests/unit/test_queries.py`:

```python
"""Tests for the GraphQL query loader."""
from __future__ import annotations


def test_queries_dict_has_me() -> None:
    from monday_rotocon.queries import QUERIES

    assert "me" in QUERIES
    assert "query Me" in QUERIES["me"]


def test_queries_dict_has_roadmap() -> None:
    from monday_rotocon.queries import QUERIES

    assert "roadmap" in QUERIES
    assert "boards(ids: $boardId)" in QUERIES["roadmap"]


def test_queries_files_are_readable() -> None:
    from monday_rotocon.queries import QUERIES

    for name, body in QUERIES.items():
        assert body.strip(), f"query {name} is empty"
```

- [ ] **Step 3: Run to verify it fails**

```bash
uv run pytest tests/unit/test_queries.py -v
```

Expected: ImportError (no `monday_rotocon.queries`).

- [ ] **Step 4: Implement the loader**

Create `src/monday_rotocon/queries/__init__.py`:

```python
"""GraphQL operations as files.

Each `.graphql` in this directory is loaded into `QUERIES[<stem>]` at
import time.
"""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent
QUERIES: dict[str, str] = {
    path.stem: path.read_text(encoding="utf-8")
    for path in _DIR.glob("*.graphql")
}
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_queries.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Make sure the `.graphql` files get packaged**

Hatchling includes non-Python files inside the package by default. Verify:

```bash
uv build --wheel
unzip -l dist/monday_rotocon-0.1.0-py3-none-any.whl | grep graphql
```

Expected: both `me.graphql` and `roadmap.graphql` listed.

Then:
```bash
rm -rf dist
```

- [ ] **Step 7: Commit**

```bash
git add src/monday_rotocon/queries/ tests/unit/test_queries.py
git commit -m "feat(core): queries/ loader with me + roadmap GraphQL operations"
```

---

### Task 10: Domain models — input side (monday API → Python objects)

**Files:**
- Create: `src/monday_rotocon/models/__init__.py`
- Create: `src/monday_rotocon/models/_base.py`
- Create: `src/monday_rotocon/models/account.py`
- Create: `src/monday_rotocon/models/user.py`
- Create: `src/monday_rotocon/models/board.py`
- Create: `src/monday_rotocon/models/item.py`
- Create: `tests/unit/test_models.py`

- [ ] **Step 1: Create the package dir + base**

```bash
mkdir -p src/monday_rotocon/models
```

Create `src/monday_rotocon/models/__init__.py`:

```python
"""Pydantic models for monday API responses + roadmap export shape."""
from __future__ import annotations

from monday_rotocon.models.account import Account
from monday_rotocon.models.user import User
from monday_rotocon.models.board import Board, Column, Group, Workspace
from monday_rotocon.models.item import Item, ColumnValueRaw

__all__ = [
    "Account",
    "User",
    "Board",
    "Column",
    "Group",
    "Workspace",
    "Item",
    "ColumnValueRaw",
]
```

Create `src/monday_rotocon/models/_base.py`:

```python
"""Shared Pydantic configuration for all monday_rotocon models."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MondayBase(BaseModel):
    """Common config: ignore unknown fields, populate by name."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )
```

- [ ] **Step 2: Add Account + User**

Create `src/monday_rotocon/models/account.py`:

```python
from __future__ import annotations

from monday_rotocon.models._base import MondayBase


class Account(MondayBase):
    id: str
    name: str
    slug: str
    tier: str
```

Create `src/monday_rotocon/models/user.py`:

```python
from __future__ import annotations

from monday_rotocon.models._base import MondayBase
from monday_rotocon.models.account import Account


class User(MondayBase):
    id: str
    name: str
    email: str | None = None
    is_admin: bool = False
    account: Account | None = None
```

- [ ] **Step 3: Add Board / Group / Column**

Create `src/monday_rotocon/models/board.py`:

```python
from __future__ import annotations

from monday_rotocon.models._base import MondayBase


class Workspace(MondayBase):
    id: str
    name: str


class Column(MondayBase):
    id: str
    title: str
    type: str
    settings_str: str | None = None


class Group(MondayBase):
    id: str
    title: str
    color: str | None = None
    position: str | None = None


class Board(MondayBase):
    id: str
    name: str
    url: str | None = None
    workspace: Workspace | None = None
    columns: list[Column] = []
    groups: list[Group] = []
```

- [ ] **Step 4: Add Item + ColumnValueRaw**

For Phase 1a we don't need a discriminated-union over column-value types; we just store the raw text/value/type and parse them in the exporter. This is intentionally narrower than sub-project A's full spec (§5.6 of A) — keeps Phase 1a small.

Create `src/monday_rotocon/models/item.py`:

```python
from __future__ import annotations

from datetime import datetime

from monday_rotocon.models._base import MondayBase


class _ColumnRef(MondayBase):
    id: str
    title: str
    type: str


class ColumnValueRaw(MondayBase):
    """Untyped column value as returned by monday's GraphQL.

    `text` is monday's human-readable rendering; `value` is the raw JSON
    payload (already serialized as a string in monday's API). Both can
    be None for empty cells.
    """

    id: str
    type: str
    text: str | None = None
    value: str | None = None
    column: _ColumnRef


class _GroupRef(MondayBase):
    id: str
    title: str


class Item(MondayBase):
    id: str
    name: str
    url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    group: _GroupRef
    column_values: list[ColumnValueRaw] = []
```

- [ ] **Step 5: Write tests**

Create `tests/unit/test_models.py`:

```python
"""Tests for monday_rotocon.models — parsing real-shape API responses."""
from __future__ import annotations


def test_account_parses() -> None:
    from monday_rotocon.models import Account

    a = Account.model_validate(
        {"id": "31832272", "name": "rotocons Team", "slug": "rotocon-world", "tier": "pro"}
    )
    assert a.id == "31832272"
    assert a.tier == "pro"


def test_user_with_account_parses() -> None:
    from monday_rotocon.models import User

    u = User.model_validate({
        "id": "103121773",
        "name": "George",
        "email": "g@x",
        "is_admin": True,
        "account": {"id": "1", "name": "X", "slug": "x", "tier": "pro"},
    })
    assert u.is_admin is True
    assert u.account is not None
    assert u.account.slug == "x"


def test_board_with_columns_groups_parses() -> None:
    from monday_rotocon.models import Board

    b = Board.model_validate({
        "id": "5096182046",
        "name": "KI Integration",
        "url": "https://x/boards/5096182046",
        "workspace": {"id": "5528271", "name": "ROTOCON EU SERVICE"},
        "columns": [
            {"id": "name", "title": "Name", "type": "name", "settings_str": "{}"},
            {"id": "status", "title": "Status", "type": "status",
             "settings_str": '{"labels":{"0":"Not started"}}'},
        ],
        "groups": [
            {"id": "topics", "title": "Onboarding", "color": "#037f4c", "position": "65536"},
        ],
    })
    assert len(b.columns) == 2
    assert b.columns[1].title == "Status"
    assert len(b.groups) == 1


def test_item_with_column_values_parses() -> None:
    from monday_rotocon.models import Item

    raw = {
        "id": "2904971529",
        "name": "Leads-Board einrichten",
        "url": "https://x/pulses/2904971529",
        "created_at": "2026-05-10T20:33:05Z",
        "updated_at": "2026-05-10T20:33:05Z",
        "group": {"id": "g1", "title": "Operatives Setup"},
        "column_values": [
            {
                "id": "status",
                "type": "status",
                "text": "In progress",
                "value": '{"index":1}',
                "column": {"id": "status", "title": "Status", "type": "status"},
            },
        ],
    }
    item = Item.model_validate(raw)
    assert item.id == "2904971529"
    assert len(item.column_values) == 1
    assert item.column_values[0].text == "In progress"


def test_item_handles_null_columns() -> None:
    from monday_rotocon.models import Item

    raw = {
        "id": "1",
        "name": "x",
        "group": {"id": "g", "title": "g"},
        "column_values": [
            {
                "id": "status",
                "type": "status",
                "text": None,
                "value": None,
                "column": {"id": "status", "title": "Status", "type": "status"},
            },
        ],
    }
    item = Item.model_validate(raw)
    assert item.column_values[0].text is None
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/unit/test_models.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add src/monday_rotocon/models/ tests/unit/test_models.py
git commit -m "feat(core): minimum Pydantic models for board / item / column_value"
```

---

### Task 11: Domain models — output side (roadmap.json shape)

**Files:**
- Create: `src/monday_rotocon/models/roadmap.py`
- Modify: `src/monday_rotocon/models/__init__.py`
- Create: `tests/unit/test_roadmap_models.py`

These are the Pydantic models for the JSON contract from spec §5.1.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_roadmap_models.py`:

```python
"""Tests for monday_rotocon.models.roadmap — the JSON contract shape."""
from __future__ import annotations

import json
from datetime import datetime, timezone


def test_roadmap_doc_serializes_to_expected_shape() -> None:
    from monday_rotocon.models.roadmap import (
        RoadmapDoc,
        RoadmapSource,
        Phase,
        RoadmapItem,
        OwnerRef,
        Timeline,
        Kpi,
    )

    doc = RoadmapDoc(
        schema_version="1",
        generated_at=datetime(2026, 5, 13, 4, 0, tzinfo=timezone.utc),
        source=RoadmapSource(
            account_slug="rotocon-world",
            board_id="5096182046",
            board_name="KI Integration",
            monday_url="https://rotocon-world.monday.com/boards/5096182046",
        ),
        phases=[
            Phase(
                id="M1",
                label="Month 1 — Operatives Setup",
                items=[
                    RoadmapItem(
                        id="2904971529",
                        name="Leads-Board einrichten",
                        status="In progress",
                        owner=OwnerRef(id="103121773", name="George Sebastian Cucuiet"),
                        timeline=Timeline(start="2026-05-15", end="2026-05-30"),
                        due=None,
                        priority="High",
                        progress_pct=30,
                        dependencies=[],
                        kpi_link=None,
                        notes="",
                        monday_url="https://rotocon-world.monday.com/boards/5096182046/pulses/2904971529",
                    )
                ],
            )
        ],
        kpis=[
            Kpi(
                id="kpi-1",
                name="Leads pro Monat",
                target="60+",
                current=23,
                owner=OwnerRef(id="103121773", name="George Sebastian Cucuiet"),
                status="On track",
                link=None,
            )
        ],
    )

    blob = json.loads(doc.model_dump_json(exclude_none=False))
    assert blob["schema_version"] == "1"
    assert blob["source"]["board_id"] == "5096182046"
    assert blob["phases"][0]["items"][0]["timeline"]["start"] == "2026-05-15"
    assert blob["kpis"][0]["current"] == 23


def test_phase_id_must_be_known() -> None:
    """Allow M1..M6, Onboarding, Ongoing — reject random strings."""
    import pytest
    from monday_rotocon.models.roadmap import Phase

    Phase(id="M1", label="Month 1", items=[])
    Phase(id="Ongoing", label="Ongoing", items=[])
    with pytest.raises(Exception):
        Phase(id="M99", label="bogus", items=[])  # type: ignore[arg-type]
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/unit/test_roadmap_models.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `roadmap.py`**

Create `src/monday_rotocon/models/roadmap.py`:

```python
"""The roadmap.json output shape — spec §5.1."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from monday_rotocon.models._base import MondayBase

PhaseId = Literal["M1", "M2", "M3", "M4", "M5", "M6", "Onboarding", "Ongoing"]


class RoadmapSource(MondayBase):
    account_slug: str
    board_id: str
    board_name: str
    monday_url: str


class OwnerRef(MondayBase):
    id: str
    name: str


class Timeline(MondayBase):
    start: str  # ISO date (YYYY-MM-DD)
    end: str


class RoadmapItem(MondayBase):
    id: str
    name: str
    status: str | None
    owner: OwnerRef | None
    timeline: Timeline | None
    due: str | None
    priority: str | None
    progress_pct: int | None
    dependencies: list[str]
    kpi_link: str | None
    notes: str
    monday_url: str


class Phase(MondayBase):
    id: PhaseId
    label: str
    items: list[RoadmapItem]


class Kpi(MondayBase):
    id: str
    name: str
    target: str | None
    current: float | int | None
    owner: OwnerRef | None
    status: str | None
    link: str | None


class RoadmapDoc(MondayBase):
    schema_version: Literal["1"]
    generated_at: datetime
    source: RoadmapSource
    phases: list[Phase]
    kpis: list[Kpi]
```

- [ ] **Step 4: Re-export from package `__init__`**

Overwrite `src/monday_rotocon/models/__init__.py`:

```python
"""Pydantic models for monday API responses + roadmap export shape."""
from __future__ import annotations

from monday_rotocon.models.account import Account
from monday_rotocon.models.user import User
from monday_rotocon.models.board import Board, Column, Group, Workspace
from monday_rotocon.models.item import Item, ColumnValueRaw
from monday_rotocon.models.roadmap import (
    Kpi,
    OwnerRef,
    Phase,
    PhaseId,
    RoadmapDoc,
    RoadmapItem,
    RoadmapSource,
    Timeline,
)

__all__ = [
    "Account",
    "User",
    "Board",
    "Column",
    "Group",
    "Workspace",
    "Item",
    "ColumnValueRaw",
    "Kpi",
    "OwnerRef",
    "Phase",
    "PhaseId",
    "RoadmapDoc",
    "RoadmapItem",
    "RoadmapSource",
    "Timeline",
]
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_roadmap_models.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/monday_rotocon/models/roadmap.py src/monday_rotocon/models/__init__.py \
        tests/unit/test_roadmap_models.py
git commit -m "feat(core): Pydantic models for the roadmap.json output contract"
```

---

### Task 12: Client + roadmap export logic

**Files:**
- Create: `src/monday_rotocon/client.py`
- Create: `src/monday_rotocon/export_roadmap.py`
- Create: `tests/unit/test_client.py`
- Create: `tests/unit/test_export_roadmap.py`
- Create: `tests/fixtures/me_response.json`
- Create: `tests/fixtures/roadmap_response.json`

- [ ] **Step 1: Create the fixtures directory**

```bash
mkdir -p tests/fixtures
```

Create `tests/fixtures/me_response.json`:

```json
{
  "me": {
    "id": "103121773",
    "name": "George Sebastian Cucuiet",
    "email": "george@rotocon.world",
    "is_admin": true,
    "account": {
      "id": "31832272",
      "name": "rotocons Team",
      "slug": "rotocon-world",
      "tier": "pro"
    }
  }
}
```

Create `tests/fixtures/roadmap_response.json`:

```json
{
  "boards": [
    {
      "id": "5096182046",
      "name": "KI Integration",
      "url": "https://rotocon-world.monday.com/boards/5096182046",
      "workspace": {"id": "5528271", "name": "ROTOCON EU SERVICE"},
      "columns": [
        {"id": "name", "title": "Name", "type": "name", "settings_str": "{}"},
        {"id": "status", "title": "Status", "type": "status",
         "settings_str": "{\"labels\":{\"0\":\"Not started\",\"1\":\"In progress\",\"2\":\"Blocked\",\"3\":\"Done\",\"4\":\"Deferred\"}}"},
        {"id": "phase", "title": "Phase", "type": "status",
         "settings_str": "{\"labels\":{\"0\":\"M1\",\"1\":\"M2\",\"2\":\"M3\",\"3\":\"M4\",\"4\":\"M5\",\"5\":\"M6\",\"6\":\"Onboarding\",\"7\":\"Ongoing\"}}"},
        {"id": "owner", "title": "Owner", "type": "people", "settings_str": "{}"},
        {"id": "timeline", "title": "Timeline", "type": "timeline", "settings_str": "{}"},
        {"id": "priority", "title": "Priority", "type": "status",
         "settings_str": "{\"labels\":{\"0\":\"Critical\",\"1\":\"High\",\"2\":\"Medium\",\"3\":\"Low\"}}"},
        {"id": "progress", "title": "% Progress", "type": "numbers", "settings_str": "{}"},
        {"id": "notes", "title": "Notes", "type": "long_text", "settings_str": "{}"},
        {"id": "kpi_link", "title": "KPI link", "type": "link", "settings_str": "{}"},
        {"id": "dep", "title": "Dependency", "type": "dependency", "settings_str": "{}"},
        {"id": "kpi_target", "title": "KPI target", "type": "text", "settings_str": "{}"},
        {"id": "kpi_current", "title": "KPI current", "type": "numbers", "settings_str": "{}"},
        {"id": "due", "title": "Due", "type": "date", "settings_str": "{}"}
      ],
      "groups": [
        {"id": "group_mm37h7r6", "title": "AI Initiatives (M4-M6)", "color": "#00c875", "position": "4189.75"},
        {"id": "group_kpi", "title": "KPI Tracking", "color": "#579bfc", "position": "8279.5"}
      ],
      "items_page": {
        "cursor": null,
        "items": [
          {
            "id": "2904971529",
            "name": "AI Quotation Assistant (M4)",
            "url": "https://rotocon-world.monday.com/boards/5096182046/pulses/2904971529",
            "created_at": "2026-05-10T20:33:05Z",
            "updated_at": "2026-05-13T08:00:00Z",
            "group": {"id": "group_mm37h7r6", "title": "AI Initiatives (M4-M6)"},
            "column_values": [
              {"id": "status", "type": "status", "text": "In progress",
               "value": "{\"index\":1}",
               "column": {"id": "status", "title": "Status", "type": "status"}},
              {"id": "phase", "type": "status", "text": "M4",
               "value": "{\"index\":3}",
               "column": {"id": "phase", "title": "Phase", "type": "status"}},
              {"id": "owner", "type": "people", "text": "George Sebastian Cucuiet",
               "value": "{\"personsAndTeams\":[{\"id\":103121773,\"kind\":\"person\"}]}",
               "column": {"id": "owner", "title": "Owner", "type": "people"}},
              {"id": "timeline", "type": "timeline", "text": "2026-08-01 - 2026-08-31",
               "value": "{\"from\":\"2026-08-01\",\"to\":\"2026-08-31\"}",
               "column": {"id": "timeline", "title": "Timeline", "type": "timeline"}},
              {"id": "priority", "type": "status", "text": "High",
               "value": "{\"index\":1}",
               "column": {"id": "priority", "title": "Priority", "type": "status"}},
              {"id": "progress", "type": "numbers", "text": "25",
               "value": "\"25\"",
               "column": {"id": "progress", "title": "% Progress", "type": "numbers"}},
              {"id": "notes", "type": "long_text", "text": "Pilot phase",
               "value": "{\"text\":\"Pilot phase\"}",
               "column": {"id": "notes", "title": "Notes", "type": "long_text"}}
            ]
          },
          {
            "id": "kpi_item_1",
            "name": "Leads pro Monat (Ziel: 60+)",
            "url": "https://rotocon-world.monday.com/boards/5096182046/pulses/kpi_item_1",
            "created_at": "2026-05-10T20:33:05Z",
            "updated_at": "2026-05-13T08:00:00Z",
            "group": {"id": "group_kpi", "title": "KPI Tracking"},
            "column_values": [
              {"id": "phase", "type": "status", "text": "Ongoing",
               "value": "{\"index\":7}",
               "column": {"id": "phase", "title": "Phase", "type": "status"}},
              {"id": "kpi_target", "type": "text", "text": "60+",
               "value": "\"60+\"",
               "column": {"id": "kpi_target", "title": "KPI target", "type": "text"}},
              {"id": "kpi_current", "type": "numbers", "text": "23",
               "value": "\"23\"",
               "column": {"id": "kpi_current", "title": "KPI current", "type": "numbers"}},
              {"id": "status", "type": "status", "text": "On track",
               "value": "{\"index\":0}",
               "column": {"id": "status", "title": "Status", "type": "status"}}
            ]
          }
        ]
      }
    }
  ]
}
```

- [ ] **Step 2: Write failing tests for the client**

Create `tests/unit/test_client.py`:

```python
"""Tests for monday_rotocon.client."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def client():
    from monday_rotocon.client import MondayClient
    from monday_rotocon.settings import Settings

    settings = Settings(monday_api_token="test")  # type: ignore[arg-type]
    return MondayClient(settings=settings)


@respx.mock
def test_client_me(client) -> None:
    respx.post("https://api.monday.com/v2").respond(
        200,
        json={
            "data": json.loads((FIXTURES / "me_response.json").read_text()),
            "extensions": {"request_id": "r1"},
        },
    )
    me = client.me()
    assert me.id == "103121773"
    assert me.account is not None
    assert me.account.slug == "rotocon-world"


@respx.mock
def test_client_fetch_roadmap_board(client) -> None:
    respx.post("https://api.monday.com/v2").respond(
        200,
        json={
            "data": json.loads((FIXTURES / "roadmap_response.json").read_text()),
            "extensions": {"request_id": "r2"},
        },
    )
    board, items = client.fetch_roadmap(board_id=5096182046)
    assert board.id == "5096182046"
    assert board.name == "KI Integration"
    assert len(board.columns) == 13
    assert len(items) == 2
    assert items[0].id == "2904971529"
```

- [ ] **Step 3: Run to verify they fail**

```bash
uv run pytest tests/unit/test_client.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement `client.py`**

Create `src/monday_rotocon/client.py`:

```python
"""Public sync client for monday_rotocon.

Phase 1a deliberately exposes only the two methods Phase 1a needs:
`me()` (identity smoke test) and `fetch_roadmap(board_id)` (export source).

Sub-project A's full client surface (boards.list, items iterator, async
client) can be added later without breaking these signatures.
"""
from __future__ import annotations

from monday_rotocon._transport import Transport
from monday_rotocon.models import Board, Item, User
from monday_rotocon.queries import QUERIES
from monday_rotocon.settings import Settings


class MondayClient:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()  # type: ignore[call-arg]
        self._transport = Transport(self._settings)

    def me(self) -> User:
        data = self._transport.execute(QUERIES["me"])
        return User.model_validate(data["me"])

    def fetch_roadmap(self, board_id: int) -> tuple[Board, list[Item]]:
        """Fetch the board + all items via cursor pagination.

        Returns (board, items). `board` carries columns + groups; items
        are flattened across all pages.
        """
        items: list[Item] = []
        cursor: str | None = None
        board: Board | None = None

        while True:
            data = self._transport.execute(
                QUERIES["roadmap"],
                variables={"boardId": [str(board_id)], "cursor": cursor},
            )
            raw_board = data["boards"][0]
            if board is None:
                board = Board.model_validate(raw_board)
            page = raw_board["items_page"]
            items.extend(Item.model_validate(it) for it in page["items"])
            cursor = page.get("cursor")
            if not cursor:
                break

        assert board is not None
        return board, items

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "MondayClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
```

- [ ] **Step 5: Run client tests**

```bash
uv run pytest tests/unit/test_client.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Write failing tests for the exporter**

Create `tests/unit/test_export_roadmap.py`:

```python
"""Tests for monday_rotocon.export_roadmap."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_build_roadmap_doc_from_fixture() -> None:
    from monday_rotocon.export_roadmap import build_roadmap_doc
    from monday_rotocon.models import Board, Item

    raw = json.loads((FIXTURES / "roadmap_response.json").read_text())
    raw_board = raw["boards"][0]
    board = Board.model_validate(raw_board)
    items = [Item.model_validate(it) for it in raw_board["items_page"]["items"]]

    doc = build_roadmap_doc(
        board=board,
        items=items,
        account_slug="rotocon-world",
        generated_at=datetime(2026, 5, 13, 4, 0, tzinfo=timezone.utc),
    )

    assert doc.schema_version == "1"
    assert doc.source.board_id == "5096182046"

    m4 = next((p for p in doc.phases if p.id == "M4"), None)
    assert m4 is not None
    assert len(m4.items) == 1
    item = m4.items[0]
    assert item.name == "AI Quotation Assistant (M4)"
    assert item.status == "In progress"
    assert item.priority == "High"
    assert item.timeline is not None
    assert item.timeline.start == "2026-08-01"
    assert item.timeline.end == "2026-08-31"
    assert item.progress_pct == 25
    assert item.owner is not None
    assert item.owner.name == "George Sebastian Cucuiet"

    assert len(doc.kpis) == 1
    k = doc.kpis[0]
    assert k.name.startswith("Leads pro Monat")
    assert k.target == "60+"
    assert k.current == 23
    assert k.status == "On track"


def test_build_roadmap_doc_skips_items_without_phase() -> None:
    """Items where Phase column is empty should be dropped silently."""
    from monday_rotocon.export_roadmap import build_roadmap_doc
    from monday_rotocon.models import Board, Item

    board_raw = {
        "id": "1", "name": "X", "url": None,
        "workspace": None, "columns": [], "groups": [{"id": "g", "title": "G"}],
    }
    item_raw = {
        "id": "x", "name": "no phase", "url": None,
        "group": {"id": "g", "title": "G"},
        "column_values": [],
    }
    board = Board.model_validate(board_raw)
    items = [Item.model_validate(item_raw)]

    doc = build_roadmap_doc(
        board=board, items=items,
        account_slug="x",
        generated_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
    )
    total_items = sum(len(p.items) for p in doc.phases)
    assert total_items == 0
    assert doc.kpis == []
```

- [ ] **Step 7: Run to verify they fail**

```bash
uv run pytest tests/unit/test_export_roadmap.py -v
```

Expected: ImportError.

- [ ] **Step 8: Implement `export_roadmap.py`**

Create `src/monday_rotocon/export_roadmap.py`:

```python
"""Pure transformation: monday Board+Items -> RoadmapDoc (roadmap.json)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import get_args

from monday_rotocon.models import (
    Board,
    Item,
    Kpi,
    OwnerRef,
    Phase,
    PhaseId,
    RoadmapDoc,
    RoadmapItem,
    RoadmapSource,
    Timeline,
)

_PHASE_LABELS: dict[str, str] = {
    "M1": "Month 1 — Operatives Setup",
    "M2": "Month 2 — Integration",
    "M3": "Month 3 — Configurator MVP",
    "M4": "Month 4 — AI Initiatives",
    "M5": "Month 5 — Smart Machine",
    "M6": "Month 6 — Predictive Maintenance",
    "Onboarding": "Onboarding (Day 1)",
    "Ongoing": "Ongoing",
}
_VALID_PHASES: set[str] = set(get_args(PhaseId))


def _find_value(item: Item, column_title: str) -> str | None:
    for cv in item.column_values:
        if cv.column.title == column_title:
            return cv.text
    return None


def _find_value_json(item: Item, column_title: str) -> dict | str | None:
    """Return the parsed JSON in `value` for the given column, if any."""
    for cv in item.column_values:
        if cv.column.title == column_title:
            if cv.value is None:
                return None
            try:
                return json.loads(cv.value)
            except (ValueError, TypeError):
                return cv.value
    return None


def _parse_int_or_none(text: str | None) -> int | None:
    if text is None or text == "":
        return None
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None


def _extract_owner(item: Item) -> OwnerRef | None:
    name = _find_value(item, "Owner")
    if not name:
        return None
    raw = _find_value_json(item, "Owner")
    person_id: str | None = None
    if isinstance(raw, dict):
        persons = raw.get("personsAndTeams") or []
        if persons:
            person_id = str(persons[0].get("id"))
    return OwnerRef(id=person_id or "", name=name.split(",")[0].strip())


def _extract_timeline(item: Item) -> Timeline | None:
    raw = _find_value_json(item, "Timeline")
    if not isinstance(raw, dict):
        return None
    start = raw.get("from")
    end = raw.get("to")
    if not start or not end:
        return None
    return Timeline(start=start, end=end)


def _extract_dependencies(item: Item) -> list[str]:
    raw = _find_value_json(item, "Dependency")
    if not isinstance(raw, dict):
        return []
    linked = raw.get("linkedPulseIds") or []
    return [str(p["linkedPulseId"]) for p in linked if "linkedPulseId" in p]


def _build_roadmap_item(item: Item) -> RoadmapItem:
    return RoadmapItem(
        id=item.id,
        name=item.name,
        status=_find_value(item, "Status"),
        owner=_extract_owner(item),
        timeline=_extract_timeline(item),
        due=_find_value(item, "Due"),
        priority=_find_value(item, "Priority"),
        progress_pct=_parse_int_or_none(_find_value(item, "% Progress")),
        dependencies=_extract_dependencies(item),
        kpi_link=_find_value(item, "KPI link"),
        notes=_find_value(item, "Notes") or "",
        monday_url=item.url or "",
    )


def _build_kpi(item: Item) -> Kpi:
    return Kpi(
        id=item.id,
        name=item.name,
        target=_find_value(item, "KPI target"),
        current=_parse_int_or_none(_find_value(item, "KPI current")),
        owner=_extract_owner(item),
        status=_find_value(item, "Status"),
        link=_find_value(item, "KPI link"),
    )


def build_roadmap_doc(
    *,
    board: Board,
    items: list[Item],
    account_slug: str,
    generated_at: datetime,
) -> RoadmapDoc:
    """Transform a monday board+items into the roadmap.json doc."""
    phases_by_id: dict[str, list[RoadmapItem]] = {pid: [] for pid in _VALID_PHASES}
    kpis: list[Kpi] = []

    for item in items:
        phase_text = _find_value(item, "Phase")
        if phase_text is None or phase_text not in _VALID_PHASES:
            continue
        if phase_text == "Ongoing":
            kpis.append(_build_kpi(item))
        else:
            phases_by_id[phase_text].append(_build_roadmap_item(item))

    phases = [
        Phase(id=pid, label=_PHASE_LABELS[pid], items=phases_by_id[pid])  # type: ignore[arg-type]
        for pid in ("M1", "M2", "M3", "M4", "M5", "M6", "Onboarding")
        if phases_by_id[pid]
    ]

    return RoadmapDoc(
        schema_version="1",
        generated_at=generated_at,
        source=RoadmapSource(
            account_slug=account_slug,
            board_id=board.id,
            board_name=board.name,
            monday_url=board.url or f"https://{account_slug}.monday.com/boards/{board.id}",
        ),
        phases=phases,
        kpis=kpis,
    )
```

- [ ] **Step 9: Run all tests in Part 2**

```bash
uv run pytest tests/unit/ -v
```

Expected: all pass (settings 3 + errors 4 + queries 3 + models 5 + roadmap_models 2 + client 2 + export 2 = 21 passing).

- [ ] **Step 10: Commit**

```bash
git add src/monday_rotocon/client.py src/monday_rotocon/export_roadmap.py \
        tests/unit/test_client.py tests/unit/test_export_roadmap.py \
        tests/fixtures/me_response.json tests/fixtures/roadmap_response.json
git commit -m "feat(core): MondayClient + roadmap export transformation"
```

---

### Task 13: CLI commands — `ping` and `export roadmap`

**Files:**
- Modify: `src/monday_rotocon/cli.py`
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_cli.py`:

```python
"""Tests for monday_rotocon.cli."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_cli_ping_success(monkeypatch) -> None:
    monkeypatch.setenv("MONDAY_API_TOKEN", "test")
    from monday_rotocon.cli import app
    from monday_rotocon.models import User, Account

    fake_me = User(
        id="103121773",
        name="George",
        email="g@x",
        is_admin=True,
        account=Account(id="1", name="rotocons Team", slug="rotocon-world", tier="pro"),
    )

    with patch("monday_rotocon.client.MondayClient.me", return_value=fake_me):
        result = CliRunner().invoke(app, ["ping"])

    assert result.exit_code == 0, result.output
    assert "George" in result.output
    assert "rotocons Team" in result.output


def test_cli_export_roadmap_writes_valid_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MONDAY_API_TOKEN", "test")
    from monday_rotocon.cli import app
    from monday_rotocon.models import Board, Item, User, Account

    raw = json.loads((FIXTURES / "roadmap_response.json").read_text())
    raw_board = raw["boards"][0]
    board = Board.model_validate(raw_board)
    items = [Item.model_validate(it) for it in raw_board["items_page"]["items"]]

    out = tmp_path / "roadmap.json"

    with patch(
        "monday_rotocon.client.MondayClient.fetch_roadmap",
        return_value=(board, items),
    ), patch("monday_rotocon.client.MondayClient.me") as me_mock:
        me_mock.return_value = User(
            id="1", name="x",
            account=Account(id="31832272", name="rotocons Team",
                            slug="rotocon-world", tier="pro"),
        )
        result = CliRunner().invoke(
            app,
            ["export", "roadmap", "--board", "5096182046", "--out", str(out)],
        )

    assert result.exit_code == 0, result.output
    assert out.exists()
    blob = json.loads(out.read_text())
    assert blob["schema_version"] == "1"
    assert blob["source"]["board_id"] == "5096182046"
    assert blob["source"]["account_slug"] == "rotocon-world"
    m4 = next(p for p in blob["phases"] if p["id"] == "M4")
    assert len(m4["items"]) == 1
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/unit/test_cli.py -v
```

Expected: tests fail because `cli.py` doesn't have these subcommands.

- [ ] **Step 3: Replace `cli.py` with the real implementation**

Overwrite `src/monday_rotocon/cli.py`:

```python
"""Typer CLI for monday_rotocon."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer

from monday_rotocon.client import MondayClient
from monday_rotocon.export_roadmap import build_roadmap_doc

app = typer.Typer(no_args_is_help=True, help="monday_rotocon CLI")
export_app = typer.Typer(no_args_is_help=True, help="Data export commands")
app.add_typer(export_app, name="export")


@app.command()
def ping() -> None:
    """Verify token and print account/user identity."""
    with MondayClient() as client:
        me = client.me()
    account_name = me.account.name if me.account else "<unknown>"
    account_slug = me.account.slug if me.account else "<unknown>"
    typer.echo(
        f"✅ Connected as {me.name} ({me.email}) — "
        f"account: {account_name} (slug: {account_slug})"
    )


@export_app.command("roadmap")
def export_roadmap(
    board: int = typer.Option(..., "--board", help="Board ID to export."),
    out: Path = typer.Option(..., "--out", help="Path to write roadmap.json."),
) -> None:
    """Export a monday board into roadmap.json (consumed by /roadmap page)."""
    with MondayClient() as client:
        me = client.me()  # one extra round-trip to learn account_slug
        account_slug = me.account.slug if me.account else "unknown"
        board_obj, items = client.fetch_roadmap(board_id=board)

    doc = build_roadmap_doc(
        board=board_obj,
        items=items,
        account_slug=account_slug,
        generated_at=datetime.now(tz=timezone.utc),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc.model_dump_json(indent=2, exclude_none=False))
    typer.echo(
        f"✅ wrote {out} "
        f"({len(items)} items, {len(doc.phases)} phases, {len(doc.kpis)} KPIs)"
    )


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run CLI tests**

```bash
uv run pytest tests/unit/test_cli.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run all unit tests + mypy + ruff**

```bash
uv run pytest tests/unit/ -v
uv run mypy src/monday_rotocon/
uv run ruff check src/monday_rotocon/ tests/
```

Expected: pytest 23 passed; mypy clean; ruff clean. If ruff complains, fix the issues inline and re-run.

- [ ] **Step 6: Manual integration smoke**

```bash
set -a && source .env && set +a
uv run monday ping
```

Expected output:
```
✅ Connected as George Sebastian Cucuiet (george@rotocon.world) — account: rotocons Team (slug: rotocon-world)
```

```bash
mkdir -p out
uv run monday export roadmap --board 5096182046 --out out/roadmap.json
python3 -m json.tool out/roadmap.json | head -30
```

Expected: `out/roadmap.json` written. If board items don't have Phase set yet (likely, before Task 19's data entry), the JSON will have `phases: []` and `kpis: []` — schema still validates.

- [ ] **Step 7: Commit**

```bash
git add src/monday_rotocon/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): implement ping + export roadmap commands"
```

Part 2 is complete.

---

## Part 3 — Static frontend

### Task 14: `web/` directory + vendored frappe-gantt + HTML skeleton

**Files:**
- Create: `web/roadmap.html`
- Create: `web/vendor/frappe-gantt/frappe-gantt.umd.js`
- Create: `web/vendor/frappe-gantt/frappe-gantt.css`
- Create: `web/vendor/frappe-gantt/LICENSE`

- [ ] **Step 1: Create directories and vendor frappe-gantt**

```bash
mkdir -p web/vendor/frappe-gantt
cd /Users/rotocondemo/monday_rotocon
curl -fsSL https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.umd.js \
  -o web/vendor/frappe-gantt/frappe-gantt.umd.js
curl -fsSL https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.css \
  -o web/vendor/frappe-gantt/frappe-gantt.css
curl -fsSL https://raw.githubusercontent.com/frappe/gantt/v0.6.1/LICENSE \
  -o web/vendor/frappe-gantt/LICENSE
```

Verify sizes:
```bash
wc -c web/vendor/frappe-gantt/frappe-gantt.umd.js \
     web/vendor/frappe-gantt/frappe-gantt.css \
     web/vendor/frappe-gantt/LICENSE
```

Expected: `.umd.js` ~50-100 KB, `.css` ~5-15 KB, `LICENSE` ~1 KB. If any file is 0 bytes or contains HTML (a 404 page), bump to v0.7.0 or check jsdelivr for the current stable v0.x release.

- [ ] **Step 2: Create `web/roadmap.html`**

The file uses DOM APIs (`createElement` + `textContent`) instead of `innerHTML` for safety — monday names can contain arbitrary user-entered text and we want XSS-safe rendering by construction. Tailwind is loaded via CDN; frappe-gantt comes from the vendored copy.

Create `web/roadmap.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>ROTOCON Cockpit - Roadmap</title>
  <link rel="stylesheet" href="vendor/frappe-gantt/frappe-gantt.css" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="vendor/frappe-gantt/frappe-gantt.umd.js"></script>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }
    .gantt-container { overflow-x: auto; }
  </style>
</head>
<body class="bg-slate-50 text-slate-800">
  <header class="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between border-b border-slate-200">
    <h1 class="text-2xl font-semibold">ROTOCON Cockpit - Roadmap</h1>
    <div class="text-sm text-slate-500" id="last-updated">loading…</div>
  </header>

  <main class="max-w-7xl mx-auto px-6 py-6 space-y-8">
    <section id="kpi-strip" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"></section>
    <section>
      <h2 class="text-lg font-semibold mb-3">Timeline</h2>
      <div class="gantt-container bg-white rounded-lg shadow-sm p-4" id="gantt-host">
        <svg id="gantt"></svg>
      </div>
    </section>
    <section>
      <h2 class="text-lg font-semibold mb-3">All items</h2>
      <div class="bg-white rounded-lg shadow-sm overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-100 text-slate-700">
            <tr>
              <th class="text-left px-4 py-2">Phase</th>
              <th class="text-left px-4 py-2">Item</th>
              <th class="text-left px-4 py-2">Status</th>
              <th class="text-left px-4 py-2">Owner</th>
              <th class="text-left px-4 py-2">Timeline</th>
              <th class="text-right px-4 py-2">Progress</th>
            </tr>
          </thead>
          <tbody id="items-tbody"></tbody>
        </table>
      </div>
    </section>
  </main>

  <footer class="max-w-7xl mx-auto px-6 py-4 text-xs text-slate-400 border-t border-slate-200">
    Source: <a class="underline" id="source-link" href="#">monday.com</a>
  </footer>

  <script>
    const ROADMAP_URL =
      document.querySelector('meta[name="roadmap-url"]')?.content || './roadmap.json';

    async function load() {
      try {
        const resp = await fetch(ROADMAP_URL, { cache: 'no-cache' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const doc = await resp.json();
        if (doc.schema_version !== '1') {
          throw new Error('unsupported schema_version: ' + doc.schema_version);
        }
        document.getElementById('last-updated').textContent =
          'Last updated: ' + new Date(doc.generated_at).toLocaleString();
        document.getElementById('source-link').href = doc.source.monday_url;
        renderKpis(doc.kpis);
        renderGantt(doc.phases);
        renderTable(doc.phases);
      } catch (err) {
        document.getElementById('last-updated').textContent = 'error: ' + err.message;
        console.error(err);
      }
    }

    function clearChildren(el) {
      while (el.firstChild) el.removeChild(el.firstChild);
    }

    function makeDiv(className, text) {
      const d = document.createElement('div');
      if (className) d.className = className;
      if (text !== undefined && text !== null) d.textContent = String(text);
      return d;
    }

    function makeTd(className, text) {
      const td = document.createElement('td');
      if (className) td.className = className;
      if (text !== undefined && text !== null) td.textContent = String(text);
      return td;
    }

    function renderKpis(kpis) {
      const strip = document.getElementById('kpi-strip');
      clearChildren(strip);
      if (!kpis || kpis.length === 0) {
        strip.appendChild(makeDiv('text-slate-400 col-span-full', 'No KPIs yet.'));
        return;
      }
      for (const k of kpis) {
        const card = makeDiv('bg-white rounded-lg shadow-sm p-4');

        const label = makeDiv('text-xs uppercase tracking-wide text-slate-400', k.name);
        card.appendChild(label);

        const value = makeDiv('text-2xl font-semibold mt-1');
        value.textContent = (k.current ?? '—') + ' ';
        const target = document.createElement('span');
        target.className = 'text-sm text-slate-400';
        target.textContent = '/ ' + (k.target ?? '');
        value.appendChild(target);
        card.appendChild(value);

        card.appendChild(makeDiv('text-sm mt-1', k.status ?? ''));
        strip.appendChild(card);
      }
    }

    function renderGantt(phases) {
      const tasks = [];
      for (const phase of phases) {
        for (const item of phase.items) {
          if (!item.timeline) continue;
          tasks.push({
            id: item.id,
            name: '[' + phase.id + '] ' + item.name,
            start: item.timeline.start,
            end: item.timeline.end,
            progress: item.progress_pct ?? 0,
            dependencies: (item.dependencies ?? []).join(','),
          });
        }
      }
      const host = document.getElementById('gantt-host');
      const ganttEl = document.getElementById('gantt');
      if (tasks.length === 0) {
        clearChildren(host);
        host.appendChild(makeDiv('text-slate-400 p-6', 'No items with a Timeline set yet.'));
        return;
      }
      // ensure the SVG host is present
      if (!ganttEl) {
        clearChildren(host);
        const newSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        newSvg.id = 'gantt';
        host.appendChild(newSvg);
      }
      new Gantt('#gantt', tasks, { view_mode: 'Month', readonly: true });
    }

    function renderTable(phases) {
      const tbody = document.getElementById('items-tbody');
      clearChildren(tbody);
      for (const phase of phases) {
        for (const item of phase.items) {
          const tr = document.createElement('tr');
          tr.className = 'border-t border-slate-100';

          tr.appendChild(makeTd('px-4 py-2 font-medium', phase.id));

          const tdName = document.createElement('td');
          tdName.className = 'px-4 py-2';
          const link = document.createElement('a');
          link.className = 'underline';
          link.href = item.monday_url || '#';
          link.target = '_blank';
          link.rel = 'noopener';
          link.textContent = item.name;
          tdName.appendChild(link);
          tr.appendChild(tdName);

          tr.appendChild(makeTd('px-4 py-2', item.status ?? ''));
          tr.appendChild(makeTd('px-4 py-2', item.owner ? item.owner.name : ''));

          const tlText = item.timeline
            ? item.timeline.start + ' -> ' + item.timeline.end
            : (item.due ?? '');
          tr.appendChild(makeTd('px-4 py-2 text-slate-500', tlText));

          tr.appendChild(makeTd('px-4 py-2 text-right',
            (item.progress_pct ?? '') + '%'));

          tbody.appendChild(tr);
        }
      }
    }

    load();
  </script>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add web/
git commit -m "feat(web): roadmap.html with KPI strip + Gantt + Table, vendored frappe-gantt"
```

---

### Task 15: Smoke-test the page locally

**Files:** (none modified — execution step)

- [ ] **Step 1: Generate a demo `roadmap.json` next to the HTML**

Either run the real exporter (if items have Phase populated):

```bash
set -a && source .env && set +a
uv run monday export roadmap --board 5096182046 --out web/roadmap.json
```

Or create a hand-crafted demo:

```bash
cat > web/roadmap.json <<'EOF'
{
  "schema_version": "1",
  "generated_at": "2026-05-13T04:00:00Z",
  "source": {
    "account_slug": "rotocon-world",
    "board_id": "5096182046",
    "board_name": "KI Integration",
    "monday_url": "https://rotocon-world.monday.com/boards/5096182046"
  },
  "phases": [
    {
      "id": "M1",
      "label": "Month 1 - Operatives Setup",
      "items": [
        {
          "id": "1",
          "name": "Leads-Board einrichten",
          "status": "In progress",
          "owner": {"id": "103121773", "name": "George"},
          "timeline": {"start": "2026-05-15", "end": "2026-05-30"},
          "due": null, "priority": "High", "progress_pct": 30,
          "dependencies": [], "kpi_link": null, "notes": "",
          "monday_url": "https://rotocon-world.monday.com/boards/5096182046/pulses/1"
        },
        {
          "id": "2",
          "name": "Angebots-Board einrichten",
          "status": "Not started",
          "owner": {"id": "103121773", "name": "George"},
          "timeline": {"start": "2026-06-01", "end": "2026-06-15"},
          "due": null, "priority": "High", "progress_pct": 0,
          "dependencies": ["1"], "kpi_link": null, "notes": "",
          "monday_url": "https://rotocon-world.monday.com/boards/5096182046/pulses/2"
        }
      ]
    }
  ],
  "kpis": [
    {
      "id": "kpi-1", "name": "Leads pro Monat", "target": "60+", "current": 23,
      "owner": {"id": "103121773", "name": "George"}, "status": "On track", "link": null
    }
  ]
}
EOF
```

- [ ] **Step 2: Serve locally and verify in a browser**

```bash
cd web
python3 -m http.server 8000
```

Open `http://localhost:8000/roadmap.html`. Expected:
- Header reads "ROTOCON Cockpit - Roadmap" with "Last updated: ..." text on the right.
- One KPI card: "Leads pro Monat" showing "23 / 60+".
- A Gantt chart with two bars (M1 items) and a dependency arrow.
- A table listing both items.

In the browser DevTools console, expect zero errors. Common failures:
- `frappe-gantt.umd.js` 404 → re-vendor in Task 14 step 1.
- CSP blocks Tailwind CDN → swap to inlining a small static Tailwind build.

- [ ] **Step 3: Kill the dev server and clean up**

```bash
# Ctrl-C in the http.server terminal
rm web/roadmap.json
```

The site-repo deploy step (Part 4) is what populates the real `roadmap.json`. The local fixture was a dev convenience.

- [ ] **Step 4: No commit (verification only).**

---

## Part 4 — Daily pipeline + handoff

### Task 16: Makefile target for one-shot export

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create the Makefile**

Create `Makefile`:

```makefile
.PHONY: install test ping export clean

install:
	uv sync --all-extras

test:
	uv run pytest -v
	uv run mypy src/monday_rotocon/
	uv run ruff check src/monday_rotocon/ tests/

ping:
	uv run monday ping

# `make export` produces out/roadmap.json from the live KI Integration board.
# Requires MONDAY_API_TOKEN in env (or .env in repo root).
export:
	mkdir -p out
	uv run monday export roadmap --board 5096182046 --out out/roadmap.json
	@echo "✅ out/roadmap.json updated"

clean:
	rm -rf out dist .pytest_cache .ruff_cache
```

- [ ] **Step 2: Verify each target**

```bash
make install
make test
set -a && source .env && set +a && make ping
make export
ls -la out/roadmap.json
```

Expected: each runs without error. `out/roadmap.json` exists after `make export`.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "feat: Makefile with install / test / ping / export / clean targets"
```

---

### Task 17: GitHub Action for daily export

**Files:**
- Create: `.github/workflows/daily-roadmap-export.yml`
- Modify: `.gitignore`

- [ ] **Step 1: Reconfigure `.gitignore` to allow `out/roadmap.json` but block the rest of `out/`**

In `.gitignore`, replace the line `out/` (added in Task 6 step 2) with:

```
out/
!out/roadmap.json
```

- [ ] **Step 2: Create the workflow**

```bash
mkdir -p .github/workflows
```

Create `.github/workflows/daily-roadmap-export.yml`:

```yaml
name: daily-roadmap-export

on:
  schedule:
    # 04:00 UTC = 06:00 Europe/Berlin (summer) — before workday starts
    - cron: '0 4 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: '0.4.x'

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Run unit tests (safety net)
        run: uv run pytest tests/unit/ -q

      - name: Export roadmap.json
        env:
          MONDAY_API_TOKEN: ${{ secrets.MONDAY_API_TOKEN }}
        run: |
          mkdir -p out
          uv run monday export roadmap --board 5096182046 --out out/roadmap.json

      - name: Commit if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          if git diff --quiet -- out/roadmap.json; then
            echo "no changes"
          else
            git add out/roadmap.json
            git commit -m "chore(data): refresh roadmap.json [skip ci]"
            git push
          fi

      - name: Upload as workflow artifact
        uses: actions/upload-artifact@v4
        with:
          name: roadmap-json
          path: out/roadmap.json
          retention-days: 30
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore .github/workflows/daily-roadmap-export.yml
git commit -m "feat(ci): daily GitHub Action for roadmap.json export"
```

- [ ] **Step 4: Manual: configure the GitHub secret**

```
1. Open https://github.com/<owner>/monday_rotocon/settings/secrets/actions
2. Click "New repository secret".
3. Name: MONDAY_API_TOKEN
4. Value: the same JWT from .env
5. Save.
```

Then trigger the workflow manually once to verify:
```
GitHub UI -> Actions -> daily-roadmap-export -> Run workflow -> main -> Run workflow
```

Expected: green check; `out/roadmap.json` updated in the repo (or unchanged if no items changed); artifact named `roadmap-json` available for download.

---

### Task 18: README updates

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Overwrite `README.md`**

```markdown
# monday_rotocon

Typed monday.com client + dashboard-export CLI for ROTOCON Europe GmbH.
Implements Phase 1a of the digital-transformation roadmap; see
`docs/superpowers/specs/` for design history.

## Quickstart

```bash
# 1. Copy the env template and add your monday API token.
cp .env.example .env
# edit .env — set MONDAY_API_TOKEN

# 2. Install dependencies into a project-local venv.
make install

# 3. Verify connectivity.
make ping

# 4. Export the roadmap board to JSON.
make export
ls -la out/roadmap.json
```

## Commands

| Command | What it does |
|---|---|
| `make install` | `uv sync --all-extras` |
| `make test` | pytest + mypy + ruff |
| `make ping` | one-shot identity check against monday.com |
| `make export` | writes `out/roadmap.json` from KI Integration board |
| `make clean` | removes `out/`, `dist/`, cache dirs |

The CLI is exposed via `uv run monday <subcommand>`:

```bash
uv run monday --help
uv run monday ping
uv run monday export roadmap --board 5096182046 --out out/roadmap.json
```

## Operational scripts

`scripts/` holds one-shot operational tooling that uses stdlib only
(no dependency on the package itself):

| Script | When to run |
|---|---|
| `scripts/bootstrap_ki_integration.py` | Once, to create the KI Integration board (already executed 2026-05-10) |
| `scripts/extend_ki_integration_columns.py` | Idempotent; adds 12 columns to KI Integration. Re-run anytime. |

## Daily export pipeline

A GitHub Action (`.github/workflows/daily-roadmap-export.yml`) runs each
day at 04:00 UTC:

1. Installs deps via `uv sync`
2. Runs `uv run monday export roadmap --board 5096182046 --out out/roadmap.json`
3. Commits the new JSON to `main` if changed
4. Uploads as workflow artifact (30-day retention)

The `george.rotocon.world/roadmap` page reads `out/roadmap.json` via raw
GitHub URL (or its CI pulls the artifact). See
`docs/site-integration.md` for binding options.

## Frontend

`web/roadmap.html` is a self-contained page that renders the JSON:

- KPI strip (cards for each `kpis[]` entry)
- Gantt timeline (via vendored frappe-gantt MIT)
- Filterable items table

Serve it locally with:
```
cd web
python3 -m http.server 8000
# open http://localhost:8000/roadmap.html
```

The page expects `roadmap.json` next to it; override via:
```html
<meta name="roadmap-url" content="https://example.com/roadmap.json">
```

## Repository layout

```
.
├── .github/workflows/    # daily export cron
├── scripts/              # stdlib-only operational tooling
├── src/monday_rotocon/   # Python package
├── tests/                # pytest (unit + integration)
├── web/                  # static frontend (HTML + vendored frappe-gantt)
├── Makefile
└── docs/superpowers/{specs,plans}/
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for Phase 1a workflow (CLI + Makefile + CI + web)"
```

---

### Task 19: Manual data-entry checklist for George

**Files:**
- Create: `docs/data-entry-29-items.md`

The 29 existing items have only `name` populated. For the page to be useful, each item needs at minimum `Phase`, `Status`, `Owner`, `Timeline`. One-time human task.

- [ ] **Step 1: Create the checklist**

Create `docs/data-entry-29-items.md`:

```markdown
# Data-entry checklist — KI Integration items (29)

After `scripts/extend_ki_integration_columns.py` adds the 12 columns,
each of the 29 existing items needs at minimum these 4 fields populated:

- `Phase` (status) — one of M1, M2, M3, M4, M5, M6, Onboarding, Ongoing
- `Status` (status) — Not started / In progress / Blocked / Done / Deferred
- `Owner` (people) — the DRI
- `Timeline` (date range) — start + end dates

The roadmap page silently drops any item without a `Phase` value, so
these four are the gating fields for a useful page.

Optional but high-value (for the Gantt to look right):
- `Priority` — Critical/High/Medium/Low
- `% Progress` — 0-100
- `Dependency` — for items that must wait on another

## How to do it fast — CSV import

monday supports CSV import that updates existing items by ID.

1. Export current items as CSV from the board: monday UI -> board menu (...)
   -> Export board -> CSV.
2. Open in a spreadsheet (Google Sheets / Excel).
3. Fill in Phase / Status / Owner / Timeline for each row.
4. Re-import via board menu -> Import -> CSV. Match by Item ID.

Recommended starting allocations:

| Existing group | Default Phase suggestion | Default Status |
|---|---|---|
| Onboarding (Tag 1) | Onboarding | mix (most Done by now) |
| Operatives Setup monday.com | M1 | In progress |
| 4-Wochen Execution-Plan (Woche 1-2) | M1 | In progress |
| 4-Wochen Execution-Plan (Woche 3-4) | M2 | Not started |
| KPI Tracking | Ongoing | mix |
| AI Initiatives (M4-M6) — items with (M4) suffix | M4 | Not started |
| AI Initiatives (M4-M6) — items with (M5) suffix | M5 | Not started |
| AI Initiatives (M4-M6) — items with (M5-M6) suffix | M6 | Not started |

## After data entry

Run a fresh export to populate the page:

```
make export
```

Inspect `out/roadmap.json` — the `phases[]` array should have items;
the `kpis[]` array should have the 6 KPI items from the KPI Tracking
group with `target` and `current` values.

Then trigger the GitHub Action manually (or wait for the next 04:00 UTC
run) so the JSON propagates to the site.
```

- [ ] **Step 2: Commit**

```bash
git add docs/data-entry-29-items.md
git commit -m "docs: data-entry checklist for the 29 KI Integration items"
```

---

### Task 20: Site-side integration documentation

**Files:**
- Create: `docs/site-integration.md`

- [ ] **Step 1: Create the integration doc**

Create `docs/site-integration.md`:

```markdown
# Site integration — george.rotocon.world/roadmap

This repo produces `out/roadmap.json` daily. The site repo needs to
consume it. Three concrete bindings, pick the one matching the site
stack.

## Binding A — raw.githubusercontent fetch (easiest)

If the site can run client-side JavaScript and you trust GitHub Raw:

1. Drop `web/roadmap.html` (from this repo) into the site as
   `/roadmap.html` (or whatever URL the site uses).
2. Add to the `<head>`:
   ```html
   <meta name="roadmap-url"
         content="https://raw.githubusercontent.com/<owner>/monday_rotocon/main/out/roadmap.json">
   ```
3. Done. The page fetches the JSON live; the daily cron updates the
   JSON in this repo.

Caveat: raw.githubusercontent has rate limits (~60 req/h
unauthenticated). For exec-only traffic this is fine; a CDN proxy is
safer for public pages.

## Binding B — site repo CI pulls on schedule

If the site has its own build pipeline:

1. Add a step to the site's CI that runs daily (or before each deploy):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/<owner>/monday_rotocon/main/out/roadmap.json \
     > public/roadmap.json
   ```
2. The site's `roadmap.html` reads `./roadmap.json` (the default in
   `web/roadmap.html`).

## Binding C — Webflow custom code embed

If the site is on Webflow:

1. Create a new Page or section called `/roadmap`.
2. Use the Embed element to paste the body content of `web/roadmap.html`
   (minus the outer html/body wrappers).
3. Upload `frappe-gantt.umd.js` and `frappe-gantt.css` as Webflow assets;
   update the link/script URLs in the embed accordingly.
4. Set `roadmap-url` to a stable CDN URL (Binding A) or a Webflow asset.

## Verifying the integration

After integration is live:

```bash
curl -fsSL https://george.rotocon.world/roadmap | grep "ROTOCON Cockpit"
curl -fsSL https://george.rotocon.world/roadmap.json | python3 -m json.tool | head
```

The first should match the page; the second should be a valid JSON with
`schema_version: "1"`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/site-integration.md
git commit -m "docs: site-integration guide with raw.gh / CI / Webflow bindings"
```

---

### Task 21: End-to-end smoke + plan completion

**Files:** (none modified — verification step)

- [ ] **Step 1: Re-run the full test suite**

```bash
cd /Users/rotocondemo/monday_rotocon
make test
```

Expected: ~23 tests pass; mypy clean; ruff clean. If any failure: stop and fix before declaring done.

- [ ] **Step 2: Run the live exporter**

```bash
set -a && source .env && set +a
make export
```

Expected: writes `out/roadmap.json`. Either a populated JSON (if George has done data entry) or one with empty `phases`/`kpis` (if not). Schema validates either way.

- [ ] **Step 3: Render the page locally with the live JSON**

```bash
cp out/roadmap.json web/roadmap.json
cd web && python3 -m http.server 8000 &
SERVE_PID=$!
sleep 1
curl -fsSL http://localhost:8000/roadmap.html | grep -q "ROTOCON Cockpit" && echo "✅ page served"
kill $SERVE_PID
rm web/roadmap.json
```

Expected: prints `✅ page served`.

- [ ] **Step 4: Verify the spec's acceptance criteria**

Read `docs/superpowers/specs/2026-05-13-ki-integration-roadmap-design.md` §8 and tick off each:

1. Board has 12 columns + 3 views (Task 5 + manual view creation)
2. `scripts/extend_ki_integration_columns.py` idempotent (Task 5 step 3)
3. 29 items have minimum 4 fields populated (Task 19 — George's data entry)
4. `monday export roadmap` produces valid JSON (Task 13 step 6)
5. `roadmap.html` renders KPI + Gantt + Table (Task 15 step 2)
6. Daily cron exists (Task 17)
7. Site CI consumes JSON (Task 20 — integration document)
8. README documents the workflow (Task 18)

Items #3 and partly #7 are gated on manual work, not engineering. The engineering work itself is complete.

- [ ] **Step 5: Final commit (if anything pending)**

```bash
git status
```

If nothing pending: Phase 1a engineering is done. If anything dangling: commit with a `chore:` prefix.

---

## Self-review (skill-mandated)

### Spec coverage scan

| Spec section | Task(s) | Notes |
|---|---|---|
| §2 Goals 1 — Board schema | 2-6 | All 12 columns; views are manual (documented in task 4) |
| §2 Goals 2 — Export contract | 11, 12, 13 | Pydantic `RoadmapDoc`; `build_roadmap_doc`; `monday export roadmap` |
| §2 Goals 3 — Web consumption | 14, 15 | `web/roadmap.html` + smoke test |
| §2 Goals 4 — Daily sync | 16, 17 | Makefile + GitHub Action |
| §4.1 12 columns | 3 | All 12 in `COLUMNS_PLAN` |
| §4.3 3 views | 4 | Documented; created manually in monday UI |
| §5.1 JSON contract | 11 | Tested via `test_roadmap_doc_serializes_to_expected_shape` |
| §5.2 Binding A/B | 20 | Both documented + Binding C for Webflow |
| §6.2 stack-agnostic HTML | 14 | Single self-contained HTML + vendored gantt + DOM-only JS |
| §8 acceptance criteria | 21 | Final smoke verifies each |

No gaps found.

### Placeholder scan

Searched the plan for: TBD, TODO, "implement later", "fill in details", "add appropriate error handling", "similar to Task N".

Findings: zero. Every code block contains actual code.

### Type / signature consistency

Cross-checked: `MondayClient.me()` / `MondayClient.fetch_roadmap(board_id)` signatures appear identically in tests and implementation. `build_roadmap_doc(*, board, items, account_slug, generated_at)` is called the same way in CLI and tests. `Settings` constructor signature consistent. `Transport.execute(query, variables=None)` consistent. `compute_missing_columns(existing, desired)` signature consistent between script and unit tests.

No mismatches.

### Scope check

This plan covers four subsystems (board script / Python package / HTML / pipeline) — but they form a single pipeline, not independent products. Per writing-plans scope guidance, that's correct as one plan.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-05-13-ki-integration-roadmap-phase1a.md`. Two execution options:

**1. Subagent-Driven (recommended)** — A fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session via `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
