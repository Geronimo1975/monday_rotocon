# Weekly Machine Progress PDF Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A weekly, GitHub-Actions-scheduled Python job that reads the `Europe Machine Overview` board via `monday_rotocon`, renders an engineering-style PDF report, and POSTs it to an n8n webhook that emails it (short HTML body + PDF attachment) and logs a row to Postgres.

**Architecture:** GitHub = compute (run library, render PDF with WeasyPrint); n8n = delivery (Gmail) + persistence (Postgres `report_history`). The Python script mirrors the existing `scripts/smoke_ki_integration_report.py` conventions. WeasyPrint is imported lazily so the rest of the test suite runs without its system libraries.

**Tech Stack:** Python 3.12, `monday_rotocon` (in-repo library), `httpx`, `weasyprint` (optional extra), `pytest` + `respx` (mocked HTTP), n8n (self-hosted), GitHub Actions, Postgres.

**Spec:** `docs/superpowers/specs/2026-06-07-weekly-machine-email-report-design.md`

**Conventions:**
- Every code-changing task ends with running tests + a git commit (`type(scope): subject`).
- `uv run` prefix for every Python / pytest / mypy / ruff invocation.
- TDD: failing test → minimal impl → green → commit.

---

## File Map

**Script (new):**
- `scripts/weekly_machine_report.py` — env loader, fetch+parse, aggregate, render HTML/PDF, payload, POST, `main()`.

**Tests (new):**
- `tests/test_weekly_report.py` — unit tests (respx-mocked, no real network; WeasyPrint test guarded by `importorskip`).
- `tests/integration/test_weekly_report_live.py` — opt-in live test under the `integration` marker.

**Config (modify):**
- `pyproject.toml` — add `[project.optional-dependencies] report = ["weasyprint>=62"]`.

**CI (new):**
- `.github/workflows/weekly-machine-report.yml` — scheduled + manual workflow.
- `SECRETS.md` — lists the four GitHub secrets to configure.

**n8n (via MCP, not files):**
- Credential `Report Webhook Token` (`httpHeaderAuth`, header `X-Report-Token`).
- Workflow `monday-machine-weekly-report-delivery`: Webhook → Convert to File → Gmail → Postgres ensure → Postgres insert → Respond.

**Postgres (via n8n):**
- Table `rotocon_finance.report_history`.

---

## Constants (used across tasks — define once in Task 2)

```python
BOARD_ID = "5086438002"            # Europe Machine Overview
CURRENT_GROUP_ID = "topics"        # "Current Machines" group

COL_PHASE = "status"               # Phase status label
COL_PHASE_PCT = "numeric_mm3xhrbf" # Phase Progress %
COL_SUBTASK_PCT = "numeric_mm3xgyyw"
COL_OVERALL = "numeric_mm3x30na"
COL_PROJECT_STATUS = "color_mm06k0h1"
COL_PROCUREMENT = "color_mm06wr1p"
COL_MACHINE_TYPE = "text_mkxvf3xh"
COL_CLIENT = "text_mkxvxap2"
COL_COUNTRY = "country_mkxvqhys"
COL_RESPONSIBLE = "person"
COL_TIMELINE = "timerange_mkxw4hgt"
COL_CALC_DELIVER = "formula_mkxw3x4k"
COL_FAT = "date_mky7mk4f"
COL_SAT = "date_mky785fe"
```

---

## Task 1: Add the `report` optional dependency

**Files:**
- Modify: `pyproject.toml:17-25`

- [ ] **Step 1: Add the `report` extra**

In `pyproject.toml`, under `[project.optional-dependencies]`, add a `report` group after the `dev` group (keep `dev` unchanged):

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
    "respx>=0.21",
    "mypy>=1.10",
    "ruff>=0.5",
]
report = [
    "weasyprint>=62",
]
```

- [ ] **Step 2: Install with the new extra**

Run: `uv sync --all-extras`
Expected: resolves and installs `weasyprint`. If it fails to import later for lack of system libraries, install them:
- macOS: `brew install pango gdk-pixbuf libffi`
- Debian/Ubuntu: `sudo apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev`

- [ ] **Step 3: Verify WeasyPrint imports**

Run: `uv run python -c "import weasyprint; print(weasyprint.__version__)"`
Expected: prints a version (e.g. `62.3`). If it raises `OSError` about `libgobject`/`pango`, install the system libs above and retry.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build(report): add weasyprint optional extra for PDF rendering"
```

---

## Task 2: Script skeleton — env loader, constants, column helpers, dataclasses

**Files:**
- Create: `scripts/weekly_machine_report.py`
- Create: `tests/test_weekly_report.py`

- [ ] **Step 1: Write failing tests for env loader and column helpers**

Create `tests/test_weekly_report.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: `ModuleNotFoundError: No module named 'weekly_machine_report'`.

- [ ] **Step 3: Create the script skeleton**

Create `scripts/weekly_machine_report.py`:

```python
"""Weekly machine-progress PDF report for ROTOCON.

Reads the "Europe Machine Overview" board via `monday_rotocon`, renders an
engineering-style PDF (portfolio KPIs + per-machine table + exceptions), and
POSTs it to an n8n webhook that emails it as an attachment and logs a row to
Postgres. Read-only: never mutates monday state.

Run locally:

    uv run python scripts/weekly_machine_report.py [--dry-run]

`--dry-run` writes the PDF to `reports/` and skips the n8n POST.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html import escape
from pathlib import Path
from typing import TypedDict

import httpx

from monday_rotocon import Item, MondayAPIError, MondayClient

# ------------------------------ constants --------------------------------------

BOARD_ID = "5086438002"            # Europe Machine Overview
CURRENT_GROUP_ID = "topics"        # "Current Machines" group

COL_PHASE = "status"
COL_PHASE_PCT = "numeric_mm3xhrbf"
COL_SUBTASK_PCT = "numeric_mm3xgyyw"
COL_OVERALL = "numeric_mm3x30na"
COL_PROJECT_STATUS = "color_mm06k0h1"
COL_PROCUREMENT = "color_mm06wr1p"
COL_MACHINE_TYPE = "text_mkxvf3xh"
COL_CLIENT = "text_mkxvxap2"
COL_COUNTRY = "country_mkxvqhys"
COL_RESPONSIBLE = "person"
COL_TIMELINE = "timerange_mkxw4hgt"
COL_CALC_DELIVER = "formula_mkxw3x4k"
COL_FAT = "date_mky7mk4f"
COL_SAT = "date_mky785fe"

DISCREPANCY_THRESHOLD = 40.0
DELIVERY_HORIZON_DAYS = 30
DELIVERY_OVERALL_FLOOR = 70.0

# ------------------------------ env --------------------------------------------


@dataclass(frozen=True)
class RequiredEnv:
    monday_token: str
    webhook_url: str
    webhook_token: str
    recipient: str


def load_env() -> RequiredEnv:
    """Read required env vars. Exits with code 1 if any are missing."""
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


# ------------------------------ column helpers ---------------------------------


def col_text(item: Item, column_id: str) -> str | None:
    """Return the `text` of a column value by id, or None if absent/empty."""
    for cv in item.column_values:
        if cv.column_id == column_id:
            text = (cv.text or "").strip()
            return text or None
    return None


def col_number(item: Item, column_id: str) -> float | None:
    """Return a column's numeric text parsed to float, or None if absent/blank."""
    raw = col_text(item, column_id)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly machine PDF report")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + render + save PDF locally; do not POST to n8n.",
    )
    args = parser.parse_args()
    _ = load_env()
    # Orchestration is wired up in Task 11.
    _ = args
    raise SystemExit(0)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests — expect green**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: the three tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): script skeleton — env loader + column helpers"
```

---

## Task 3: `MachineRow` + `fetch_current_machines`

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_weekly_report.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: ImportError on `MachineRow` / `fetch_current_machines`.

- [ ] **Step 3: Implement `MachineRow` and `fetch_current_machines`**

Add to `scripts/weekly_machine_report.py` (after `col_number`):

```python
@dataclass(frozen=True)
class MachineRow:
    machine_no: str
    machine_type: str | None
    client: str | None
    country: str | None
    responsible: str | None
    phase: str | None
    project_status: str | None
    procurement: str | None
    phase_pct: float | None
    subtask_pct: float | None
    overall: float | None
    deliver_text: str | None
    fat_date: str | None
    sat_date: str | None

    @classmethod
    def from_item(cls, item: Item) -> MachineRow:
        return cls(
            machine_no=item.name,
            machine_type=col_text(item, COL_MACHINE_TYPE),
            client=col_text(item, COL_CLIENT),
            country=col_text(item, COL_COUNTRY),
            responsible=col_text(item, COL_RESPONSIBLE),
            phase=col_text(item, COL_PHASE),
            project_status=col_text(item, COL_PROJECT_STATUS),
            procurement=col_text(item, COL_PROCUREMENT),
            phase_pct=col_number(item, COL_PHASE_PCT),
            subtask_pct=col_number(item, COL_SUBTASK_PCT),
            overall=col_number(item, COL_OVERALL),
            deliver_text=col_text(item, COL_CALC_DELIVER),
            fat_date=col_text(item, COL_FAT),
            sat_date=col_text(item, COL_SAT),
        )


def fetch_current_machines(client: MondayClient) -> list[MachineRow]:
    """Fetch all items on the board, keep only the Current Machines group."""
    rows: list[MachineRow] = []
    for item in client.items_for_board(board_id=BOARD_ID):
        if item.group is not None and item.group.id == CURRENT_GROUP_ID:
            rows.append(MachineRow.from_item(item))
    return rows
```

- [ ] **Step 4: Run tests — expect green**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): MachineRow + fetch_current_machines (group filter)"
```

---

## Task 4: `parse_deliver_date` + `PortfolioSummary` + `compute_summary`

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_weekly_report.py`:

```python
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
```

Also add a `_row` helper near the top of the test file (after `_item`):

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: ImportError on `parse_deliver_date` / `compute_summary`.

- [ ] **Step 3: Implement**

Add to `scripts/weekly_machine_report.py`:

```python
def parse_deliver_date(text: str | None) -> date | None:
    """Parse monday's Calc Deliver Date formula text (e.g. '15-Aug-2026')."""
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


@dataclass(frozen=True)
class PortfolioSummary:
    total: int
    avg_overall: float | None
    critical_count: int
    late_count: int
    discrepancy_count: int
    delivery_30d_count: int
    week: int
    generated_at: datetime
    by_phase: dict[str, int] = field(default_factory=dict)


def _is_discrepant(row: MachineRow) -> bool:
    if row.phase_pct is None or row.subtask_pct is None:
        return False
    return (row.phase_pct - row.subtask_pct) >= DISCREPANCY_THRESHOLD


def _delivers_within_horizon(row: MachineRow, *, today: date) -> bool:
    d = parse_deliver_date(row.deliver_text)
    if d is None:
        return False
    delta = (d - today).days
    return 0 <= delta <= DELIVERY_HORIZON_DAYS


def compute_summary(rows: list[MachineRow], *, generated_at: datetime) -> PortfolioSummary:
    today = generated_at.date()
    overalls = [r.overall for r in rows if r.overall is not None]
    by_phase: dict[str, int] = {}
    for r in rows:
        key = r.phase or "(none)"
        by_phase[key] = by_phase.get(key, 0) + 1
    return PortfolioSummary(
        total=len(rows),
        avg_overall=round(sum(overalls) / len(overalls), 1) if overalls else None,
        critical_count=sum(1 for r in rows if r.project_status == "critical"),
        late_count=sum(1 for r in rows if r.project_status == "late delivery"),
        discrepancy_count=sum(1 for r in rows if _is_discrepant(r)),
        delivery_30d_count=sum(1 for r in rows if _delivers_within_horizon(r, today=today)),
        week=generated_at.isocalendar().week,
        generated_at=generated_at,
        by_phase=by_phase,
    )
```

- [ ] **Step 4: Run tests — expect green**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): parse_deliver_date + compute_summary KPIs"
```

---

## Task 5: `ExceptionRow` + `build_exceptions`

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_weekly_report.py`:

```python
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
    soon = next(e for e in exceptions if e.machine_no == "SOON")
    assert "overall" in soon.why.lower() or "30d" in soon.why.lower()


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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: ImportError on `build_exceptions`.

- [ ] **Step 3: Implement**

Add to `scripts/weekly_machine_report.py`:

```python
@dataclass(frozen=True)
class ExceptionRow:
    machine_no: str
    client: str | None
    phase: str | None
    overall: float | None
    why: str
    urgency: int   # lower sorts first


def build_exceptions(
    rows: list[MachineRow], *, generated_at: datetime
) -> list[ExceptionRow]:
    """Flag machines needing attention, sorted by urgency (critical first)."""
    today = generated_at.date()
    out: list[ExceptionRow] = []
    for r in rows:
        reasons: list[str] = []
        urgency = 9
        if r.project_status == "critical":
            reasons.append("Project status critical")
            urgency = min(urgency, 0)
        if r.project_status == "late delivery":
            reasons.append("Late delivery")
            urgency = min(urgency, 1)
        if _is_discrepant(r):
            gap = int((r.phase_pct or 0) - (r.subtask_pct or 0))
            reasons.append(f"Phase ahead of subtasks (gap {gap})")
            urgency = min(urgency, 2)
        if _delivers_within_horizon(r, today=today) and (r.overall or 0) < DELIVERY_OVERALL_FLOOR:
            reasons.append(f"Delivers <={DELIVERY_HORIZON_DAYS}d, overall {int(r.overall or 0)}%")
            urgency = min(urgency, 3)
        if reasons:
            out.append(
                ExceptionRow(
                    machine_no=r.machine_no,
                    client=r.client,
                    phase=r.phase,
                    overall=r.overall,
                    why="; ".join(reasons),
                    urgency=urgency,
                )
            )
    out.sort(key=lambda e: (e.urgency, e.machine_no))
    return out
```

- [ ] **Step 4: Run tests — expect green**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): ExceptionRow + build_exceptions with urgency sort"
```

---

## Task 6: `render_report_html` (engineering layout for PDF)

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_weekly_report.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: ImportError on `render_report_html`.

- [ ] **Step 3: Implement**

Add to `scripts/weekly_machine_report.py`:

```python
def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{int(round(value))}%"


def _fmt(value: str | None) -> str:
    return escape(value) if value else "—"


def _progress_bar(value: float | None) -> str:
    pct = 0 if value is None else max(0, min(100, int(round(value))))
    return (
        "<div class='track'>"
        f"<div class='fill' style='width:{pct}%'></div>"
        f"<span class='barlabel'>{_fmt_pct(value)}</span>"
        "</div>"
    )


_REPORT_CSS = """
@page {
  size: A4;
  margin: 16mm 12mm 18mm 12mm;
  @top-left { content: "ROTOCON · Machine Progress"; font-size: 8pt; color: #888; }
  @top-right { content: "KW" string(kw); font-size: 8pt; color: #888; }
  @bottom-right { content: "Page " counter(page) " / " counter(pages); font-size: 8pt; color: #888; }
  @bottom-left { content: string(genstamp); font-size: 8pt; color: #888; }
}
* { box-sizing: border-box; }
body { font-family: "Helvetica Neue", Arial, sans-serif; color: #111; font-size: 9pt; }
h1 { font-size: 16pt; margin: 0 0 2mm 0; }
h2 { font-size: 11pt; margin: 6mm 0 2mm 0; border-bottom: 1.5pt solid #0073EA; padding-bottom: 1mm; }
.meta { color: #555; font-size: 8pt; }
.kpis { display: flex; gap: 4mm; margin: 4mm 0; }
.kpi { flex: 1; border: 0.5pt solid #ccc; border-top: 2.5pt solid #0073EA; padding: 2mm 3mm; }
.kpi .num { font-size: 15pt; font-weight: bold; font-family: "Courier New", monospace; }
.kpi .lbl { font-size: 7.5pt; color: #666; text-transform: uppercase; letter-spacing: 0.3pt; }
table { width: 100%; border-collapse: collapse; font-size: 8pt; }
th { background: #f2f4f7; text-align: left; padding: 1.5mm 2mm; border-bottom: 1pt solid #ccc; }
td { padding: 1.5mm 2mm; border-bottom: 0.5pt solid #e6e6e6; vertical-align: middle; }
td.mono, th.mono { font-family: "Courier New", monospace; text-align: right; }
.badge { display: inline-block; padding: 0.3mm 1.6mm; border-radius: 2pt; color: #fff; font-size: 7pt; }
.b-critical { background: #df2f4a; } .b-late { background: #ff6d3b; }
.b-ok { background: #037f4c; } .b-hold { background: #c4c4c4; color:#222; }
.b-proc { background: #ff007f; }
.track { position: relative; height: 9pt; background: #eee; border-radius: 2pt; width: 80pt; }
.fill { position: absolute; left:0; top:0; bottom:0; background: #0073EA; border-radius: 2pt; }
.barlabel { position: absolute; right: 2pt; top: 0.5pt; font-size: 6.5pt; font-family: "Courier New", monospace; }
.empty { color: #037f4c; font-style: italic; padding: 2mm 0; }
"""

_BADGE_CLASS = {
    "critical": "b-critical",
    "late delivery": "b-late",
    "ok": "b-ok",
    "on hold": "b-hold",
    "open procurement": "b-proc",
}


def _status_badge(status: str | None) -> str:
    if not status:
        return "—"
    cls = _BADGE_CLASS.get(status, "b-hold")
    return f"<span class='badge {cls}'>{escape(status)}</span>"


def render_report_html(
    summary: PortfolioSummary,
    exceptions: list[ExceptionRow],
    machines: list[MachineRow],
) -> str:
    stamp = summary.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    css = _REPORT_CSS

    if exceptions:
        exc_rows = "".join(
            f"<tr><td class='mono'>{escape(e.machine_no)}</td>"
            f"<td>{_fmt(e.client)}</td><td>{_fmt(e.phase)}</td>"
            f"<td class='mono'>{_fmt_pct(e.overall)}</td>"
            f"<td>{escape(e.why)}</td></tr>"
            for e in exceptions
        )
        exc_block = (
            "<table><thead><tr><th class='mono'>Machine</th><th>Client</th>"
            "<th>Phase</th><th class='mono'>Overall</th><th>Why</th></tr></thead>"
            f"<tbody>{exc_rows}</tbody></table>"
        )
    else:
        exc_block = "<p class='empty'>No exceptions this week ✅</p>"

    machine_rows = "".join(
        f"<tr><td class='mono'>{escape(m.machine_no)}</td>"
        f"<td>{_fmt(m.client)}</td><td>{_fmt(m.machine_type)}</td>"
        f"<td>{_fmt(m.responsible)}</td><td>{_fmt(m.phase)}</td>"
        f"<td>{_status_badge(m.project_status)}</td>"
        f"<td>{_progress_bar(m.overall)}</td></tr>"
        for m in sorted(machines, key=lambda r: (r.overall is None, -(r.overall or 0)))
    )

    return f"""\
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><style>{css}
.meta {{ string-set: kw "{summary.week}", genstamp "{stamp}"; }}
</style></head>
<body>
  <h1>Machine Progress Report</h1>
  <div class="meta">Rotocon · Europe Machine Overview · KW{summary.week} · generated {stamp} · board {BOARD_ID}</div>

  <div class="kpis">
    <div class="kpi"><div class="num">{summary.total}</div><div class="lbl">Total machines</div></div>
    <div class="kpi"><div class="num">{_fmt_pct(summary.avg_overall)}</div><div class="lbl">Avg overall</div></div>
    <div class="kpi"><div class="num">{summary.critical_count}</div><div class="lbl">Critical</div></div>
    <div class="kpi"><div class="num">{summary.late_count}</div><div class="lbl">Late delivery</div></div>
  </div>

  <h2>Needs attention</h2>
  {exc_block}

  <h2>Full portfolio (sorted by overall progress)</h2>
  <table>
    <thead><tr><th class='mono'>Machine</th><th>Client</th><th>Type</th>
      <th>Responsible</th><th>Phase</th><th>Status</th><th>Overall</th></tr></thead>
    <tbody>{machine_rows}</tbody>
  </table>
</body>
</html>
"""
```

- [ ] **Step 4: Run tests — expect green**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: all `render_report_html` tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): render_report_html engineering layout"
```

---

## Task 7: `render_pdf` (WeasyPrint, lazy import)

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write a failing test (guarded by importorskip)**

Append to `tests/test_weekly_report.py`:

```python
def test_render_pdf_produces_pdf_bytes() -> None:
    import pytest

    pytest.importorskip("weasyprint")  # skip if system libs absent
    from weekly_machine_report import render_pdf

    pdf = render_pdf("<html><body><h1>hi</h1></body></html>")
    assert isinstance(pdf, bytes)
    assert pdf[:5] == b"%PDF-"
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_weekly_report.py::test_render_pdf_produces_pdf_bytes -v`
Expected: ImportError on `render_pdf` (the function), OR SKIPPED if weasyprint missing — implement anyway.

- [ ] **Step 3: Implement with a lazy import**

Add to `scripts/weekly_machine_report.py`. The WeasyPrint import lives **inside** the function so importing the module never requires its system libraries:

```python
def render_pdf(html: str) -> bytes:
    """Render an HTML string to PDF bytes via WeasyPrint.

    WeasyPrint is imported lazily so the rest of the module (and the unit
    test suite) loads without its system libraries installed.
    """
    from weasyprint import HTML  # noqa: PLC0415  (intentional lazy import)

    pdf = HTML(string=html).write_pdf()
    if pdf is None:  # pragma: no cover - write_pdf() returns bytes when no target
        raise RuntimeError("WeasyPrint returned no PDF bytes")
    return pdf
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_weekly_report.py::test_render_pdf_produces_pdf_bytes -v`
Expected: PASS (or SKIPPED if WeasyPrint system libs are unavailable on this machine — that's acceptable; CI has them).

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): render_pdf via WeasyPrint (lazy import)"
```

---

## Task 8: `render_email_summary_html` (short body)

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write a failing test**

Append to `tests/test_weekly_report.py`:

```python
def test_render_email_summary_is_short_and_mentions_attachment() -> None:
    from weekly_machine_report import render_email_summary_html

    html = render_email_summary_html(_summary(critical_count=2, total=10))
    assert "KW23" in html
    assert "10" in html           # total
    assert "2" in html            # critical
    assert "attached" in html.lower()
    assert "<table" not in html   # body stays short, no full table
```

- [ ] **Step 2: Run it — expect failure**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: ImportError on `render_email_summary_html`.

- [ ] **Step 3: Implement**

Add to `scripts/weekly_machine_report.py`:

```python
def render_email_summary_html(summary: PortfolioSummary) -> str:
    """Short inline-styled email body — KPIs + 'see attached PDF'."""
    stamp = summary.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    chip = (
        "display:inline-block;padding:6px 12px;margin:3px;border-radius:6px;"
        "background:#f2f4f7;font-size:14px;"
    )
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;color:#111;max-width:560px;">
  <h2 style="font-size:17px;margin:0 0 4px;">Rotocon · Machine Progress · KW{summary.week}</h2>
  <div style="color:#666;font-size:12px;margin-bottom:12px;">Generated {stamp}</div>
  <div>
    <span style="{chip}"><b>{summary.total}</b> machines</span>
    <span style="{chip}">Avg <b>{_fmt_pct(summary.avg_overall)}</b></span>
    <span style="{chip}">Critical <b>{summary.critical_count}</b></span>
    <span style="{chip}">Late <b>{summary.late_count}</b></span>
  </div>
  <p style="font-size:14px;margin-top:16px;">
    The full engineering report is <b>attached as a PDF</b>.
  </p>
</div>
"""
```

- [ ] **Step 4: Run tests — expect green**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): render_email_summary_html short body"
```

---

## Task 9: `build_payload` (PDF base64) + types

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write a failing test**

Append to `tests/test_weekly_report.py`:

```python
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
```

- [ ] **Step 2: Run it — expect failure**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: ImportError on `build_payload`.

- [ ] **Step 3: Implement**

Add to `scripts/weekly_machine_report.py`:

```python
class PdfAttachment(TypedDict):
    filename: str
    content_base64: str
    mime_type: str


class ReportStats(TypedDict):
    report_type: str
    board_id: str
    machine_count: int
    avg_overall: float | None
    critical_n: int
    late_n: int
    pdf_size_kb: int


class WebhookPayload(TypedDict):
    subject: str
    recipient: str
    html_summary: str
    pdf: PdfAttachment
    stats: ReportStats


def build_payload(
    *,
    summary: PortfolioSummary,
    recipient: str,
    html_summary: str,
    pdf_bytes: bytes,
    pdf_filename: str,
) -> WebhookPayload:
    return WebhookPayload(
        subject=(
            f"Rotocon · Machine Progress · KW{summary.week} · "
            f"{summary.critical_count} critical"
        ),
        recipient=recipient,
        html_summary=html_summary,
        pdf=PdfAttachment(
            filename=pdf_filename,
            content_base64=base64.b64encode(pdf_bytes).decode("ascii"),
            mime_type="application/pdf",
        ),
        stats=ReportStats(
            report_type="weekly_machine_progress",
            board_id=BOARD_ID,
            machine_count=summary.total,
            avg_overall=summary.avg_overall,
            critical_n=summary.critical_count,
            late_n=summary.late_count,
            pdf_size_kb=max(1, round(len(pdf_bytes) / 1024)),
        ),
    )
```

- [ ] **Step 4: Run tests — expect green**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): build_payload with base64 PDF + stats"
```

---

## Task 10: `post_to_n8n` with retry

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_weekly_report.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: ImportError on `post_to_n8n` / `N8nWebhookError`.

- [ ] **Step 3: Implement (header `X-Report-Token`)**

Add to `scripts/weekly_machine_report.py`:

```python
class N8nWebhookError(RuntimeError):
    """Raised when the n8n webhook fails after all retries."""


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def post_to_n8n(
    *,
    url: str,
    token: str,
    payload: WebhookPayload | dict,
    timeout: float = 60.0,
    max_attempts: int = 3,
) -> dict:
    """POST `payload` to the n8n webhook with header auth and bounded retry.

    Retries on `httpx.TransportError` with exponential backoff (1s, 2s).
    A non-2xx response raises immediately without retry. Timeout is generous
    (60s) because the responseNode webhook blocks until the whole workflow
    finishes and the send is NOT idempotent (a premature retry duplicates mail).
    """
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"X-Report-Token": token, "Content-Type": "application/json"},
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
    raise N8nWebhookError(f"unreachable; last exc: {last_exc!r}")
```

- [ ] **Step 4: Run tests — expect green**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): post_to_n8n with 3-attempt retry"
```

---

## Task 11: `main()` orchestration + `--dry-run`

**Files:**
- Modify: `scripts/weekly_machine_report.py`
- Modify: `tests/test_weekly_report.py`

- [ ] **Step 1: Write a failing end-to-end dry-run test**

Append to `tests/test_weekly_report.py`:

```python
def test_main_dry_run_writes_pdf_and_skips_webhook(monkeypatch, tmp_path) -> None:
    import pytest
    import respx

    pytest.importorskip("weasyprint")

    monkeypatch.setenv("MONDAY_API_TOKEN", "t")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example/webhook/x")
    monkeypatch.setenv("N8N_WEBHOOK_TOKEN", "secret")
    monkeypatch.setenv("REPORT_RECIPIENT", "a@b.c")
    monkeypatch.chdir(tmp_path)

    items_data = {
        "data": {
            "boards": [
                {
                    "items_page": {
                        "cursor": None,
                        "items": [
                            {"id": "1", "name": "ROT200E", "state": "active",
                             "group": {"id": "topics", "title": "Current Machines"},
                             "column_values": [
                                 {"id": "numeric_mm3x30na", "type": "numbers",
                                  "text": "55", "value": "55"},
                                 {"id": "color_mm06k0h1", "type": "color",
                                  "text": "ok", "value": None},
                             ]},
                            {"id": "2", "name": "DEMO", "state": "active",
                             "group": {"id": "group_demo", "title": "Demo Machine"},
                             "column_values": []},
                        ],
                    }
                }
            ]
        }
    }
    import sys

    import httpx

    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").mock(side_effect=[httpx.Response(200, json=items_data)])
        from weekly_machine_report import main
        monkeypatch.setattr(sys, "argv", ["weekly", "--dry-run"])
        exit_code = main()
        assert exit_code == 0

    pdfs = list((tmp_path / "reports").glob("*.pdf"))
    assert len(pdfs) == 1
    assert pdfs[0].read_bytes()[:5] == b"%PDF-"
```

- [ ] **Step 2: Run it — expect failure**

Run: `uv run pytest tests/test_weekly_report.py::test_main_dry_run_writes_pdf_and_skips_webhook -v`
Expected: the existing placeholder `main()` exits 0 without writing a PDF → AssertionError on the glob (or SKIPPED if weasyprint absent).

- [ ] **Step 3: Replace `main()` with full orchestration**

In `scripts/weekly_machine_report.py`, replace the placeholder `main()` (and its `__main__` guard stays) with:

```python
def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly machine PDF report")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + render + save PDF locally; do not POST to n8n.",
    )
    args = parser.parse_args()
    env = load_env()

    try:
        with MondayClient(api_token=env.monday_token) as client:
            machines = fetch_current_machines(client)
    except MondayAPIError as exc:
        print(f"monday API error: {exc!r}", file=sys.stderr)
        return 2

    generated_at = _now_utc()
    summary = compute_summary(machines, generated_at=generated_at)
    exceptions = build_exceptions(machines, generated_at=generated_at)

    report_html = render_report_html(summary, exceptions, machines)
    pdf_bytes = render_pdf(report_html)
    email_html = render_email_summary_html(summary)

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    stamp = generated_at.strftime("%Y-%m-%d-%H%M")
    pdf_filename = f"{stamp}-weekly-machine-report.pdf"
    pdf_path = reports_dir / pdf_filename
    pdf_path.write_bytes(pdf_bytes)
    print(f"Wrote {pdf_path} ({len(pdf_bytes) // 1024} KB, {summary.total} machines)")

    if args.dry_run:
        print(f"--dry-run: skipping n8n POST (critical={summary.critical_count})")
        return 0

    payload = build_payload(
        summary=summary,
        recipient=env.recipient,
        html_summary=email_html,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
    )
    try:
        response = post_to_n8n(url=env.webhook_url, token=env.webhook_token, payload=payload)
    except N8nWebhookError as exc:
        print(f"n8n webhook error: {exc!r}", file=sys.stderr)
        return 3

    print(
        f"OK machines={summary.total} critical={summary.critical_count} "
        f"n8n_messageId={response.get('messageId', '?')} pdf={pdf_path}"
    )
    return 0
```

- [ ] **Step 4: Run the full file**

Run: `uv run pytest tests/test_weekly_report.py -v`
Expected: all tests pass (dry-run test PASS, or SKIPPED only if weasyprint absent).

- [ ] **Step 5: Quality gates**

Run:
```bash
uv run ruff format scripts/weekly_machine_report.py tests/test_weekly_report.py
uv run ruff check scripts/weekly_machine_report.py tests/test_weekly_report.py
uv run pytest
```
Expected: format clean, lint clean, whole suite green (prior 38 + new).

- [ ] **Step 6: Commit**

```bash
git add scripts/weekly_machine_report.py tests/test_weekly_report.py
git commit -m "feat(weekly): main() orchestration with --dry-run"
```

---

## Task 12: n8n delivery workflow (via MCP)

**Tools:** `mcp__n8n-mcp__n8n_manage_credentials`, `mcp__n8n-mcp__search_nodes`, `mcp__n8n-mcp__get_node`, `mcp__n8n-mcp__n8n_create_workflow`, `mcp__n8n-mcp__n8n_validate_workflow`, `mcp__n8n-mcp__n8n_update_partial_workflow`.

**No repo files in this task.**

- [ ] **Step 1: Generate the webhook token and add it to local `.env`**

Run:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Add to local `.env` (do NOT commit):
```
N8N_WEBHOOK_URL=https://n8n.rotocon.world/webhook/monday-weekly-report
N8N_WEBHOOK_TOKEN=<paste 64-char hex>
REPORT_RECIPIENT=george@rotocon.world
```

- [ ] **Step 2: Create the header-auth credential**

```
mcp__n8n-mcp__n8n_manage_credentials(action="getSchema", type="httpHeaderAuth")
mcp__n8n-mcp__n8n_manage_credentials(
    action="create", type="httpHeaderAuth", name="Report Webhook Token",
    data={"name": "X-Report-Token", "value": "<same 64-char hex>"})
```
Record the returned credential ID as `<CRED_ID>`.

- [ ] **Step 3: Confirm node parameter names**

```
mcp__n8n-mcp__get_node(nodeType="nodes-base.webhook")
mcp__n8n-mcp__get_node(nodeType="nodes-base.convertToFile")
mcp__n8n-mcp__get_node(nodeType="nodes-base.gmail")
mcp__n8n-mcp__get_node(nodeType="nodes-base.postgres")
mcp__n8n-mcp__get_node(nodeType="nodes-base.respondToWebhook")
```
Confirm: Gmail `message:send` with `options.attachmentsUi` binary attachments; Convert to File `toBinary`/base64 mode and the `binaryPropertyName`; Postgres `executeQuery` operation. Adjust the JSON below to the exact parameter names returned.

- [ ] **Step 4: Create the workflow**

Call `mcp__n8n-mcp__n8n_create_workflow` with this structure (Webhook → Convert to File → Gmail → Postgres ensure → Postgres insert → Respond). **Critical:** because Convert to File produces binary, every node after it must read webhook fields via `$('Webhook').first().json.body.X`, NOT `$json.body.X` (recorded in MEMORY `n8n_webhook_payload_after_convert_to_file`).

```json
{
  "name": "monday-machine-weekly-report-delivery",
  "nodes": [
    {
      "id": "n-webhook", "name": "Webhook", "type": "n8n-nodes-base.webhook",
      "typeVersion": 2, "position": [0, 0],
      "parameters": {
        "httpMethod": "POST", "path": "monday-weekly-report",
        "authentication": "headerAuth", "responseMode": "responseNode", "options": {}
      },
      "credentials": {"httpHeaderAuth": {"id": "<CRED_ID>", "name": "Report Webhook Token"}}
    },
    {
      "id": "n-tofile", "name": "PDF To Binary", "type": "n8n-nodes-base.convertToFile",
      "typeVersion": 1.1, "position": [220, 0],
      "parameters": {
        "operation": "toBinary",
        "sourceProperty": "body.pdf.content_base64",
        "options": {"fileName": "={{ $json.body.pdf.filename }}", "mimeType": "application/pdf"}
      }
    },
    {
      "id": "n-gmail", "name": "Send Gmail", "type": "n8n-nodes-base.gmail",
      "typeVersion": 2.1, "position": [440, 0],
      "parameters": {
        "resource": "message", "operation": "send",
        "sendTo": "={{ $('Webhook').first().json.body.recipient }}",
        "subject": "={{ $('Webhook').first().json.body.subject }}",
        "emailType": "html",
        "message": "={{ $('Webhook').first().json.body.html_summary }}",
        "options": {"attachmentsUi": {"attachmentsBinary": [{"property": "data"}]}}
      },
      "credentials": {"gmailOAuth2": {"id": "ahEoxGuMkBRjQ9YF", "name": "Gmail account"}}
    },
    {
      "id": "n-pg-ddl", "name": "Ensure Table", "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5, "position": [660, 0],
      "parameters": {
        "operation": "executeQuery",
        "query": "CREATE TABLE IF NOT EXISTS rotocon_finance.report_history (id SERIAL PRIMARY KEY, sent_at TIMESTAMPTZ NOT NULL DEFAULT now(), report_type TEXT NOT NULL, board_id BIGINT NOT NULL, machine_count INT NOT NULL, avg_overall NUMERIC(5,2), critical_n INT, late_n INT, recipient TEXT, pdf_size_kb INT);",
        "options": {}
      },
      "credentials": {"postgres": {"id": "l5HHFXvW5o8FdBkj", "name": "Postgres account"}}
    },
    {
      "id": "n-pg-ins", "name": "Insert History", "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5, "position": [880, 0],
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO rotocon_finance.report_history (report_type, board_id, machine_count, avg_overall, critical_n, late_n, recipient, pdf_size_kb) VALUES ($1,$2,$3,$4,$5,$6,$7,$8);",
        "options": {"queryReplacement": "={{ [$('Webhook').first().json.body.stats.report_type, $('Webhook').first().json.body.stats.board_id, $('Webhook').first().json.body.stats.machine_count, $('Webhook').first().json.body.stats.avg_overall, $('Webhook').first().json.body.stats.critical_n, $('Webhook').first().json.body.stats.late_n, $('Webhook').first().json.body.recipient, $('Webhook').first().json.body.stats.pdf_size_kb] }}"}
      },
      "credentials": {"postgres": {"id": "l5HHFXvW5o8FdBkj", "name": "Postgres account"}}
    },
    {
      "id": "n-respond", "name": "Respond", "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1, "position": [1100, 0],
      "parameters": {
        "respondWith": "json",
        "responseBody": "={ \"status\": \"sent\", \"messageId\": $('Send Gmail').first().json.id }"
      }
    }
  ],
  "connections": {
    "Webhook": {"main": [[{"node": "PDF To Binary", "type": "main", "index": 0}]]},
    "PDF To Binary": {"main": [[{"node": "Send Gmail", "type": "main", "index": 0}]]},
    "Send Gmail": {"main": [[{"node": "Ensure Table", "type": "main", "index": 0}]]},
    "Ensure Table": {"main": [[{"node": "Insert History", "type": "main", "index": 0}]]},
    "Insert History": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]}
  },
  "settings": {}
}
```

Note: the Convert to File binary property name (`data` vs custom) and Postgres `queryReplacement` parameter name come from Step 3 — adjust before submitting.

- [ ] **Step 5: Validate**

```
mcp__n8n-mcp__n8n_validate_workflow(<workflow id>)
```
Fix any errors (most likely parameter-name mismatches), re-validate until clean.

- [ ] **Step 6: Curl smoke-test (auth + shape) — keep INACTIVE first**

The workflow is created inactive; activate it first (Step 7), then run:
```bash
TOKEN="<64-char hex>"
# minimal valid PDF base64 ("%PDF-1.0\n%%EOF")
PDF_B64=$(python -c "import base64;print(base64.b64encode(b'%PDF-1.0\n%%EOF\n').decode())")
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "https://n8n.rotocon.world/webhook/monday-weekly-report" \
  -H "X-Report-Token: $TOKEN" -H "Content-Type: application/json" \
  -d "{\"subject\":\"test\",\"recipient\":\"george@rotocon.world\",\"html_summary\":\"<p>test</p>\",\"pdf\":{\"filename\":\"t.pdf\",\"content_base64\":\"$PDF_B64\",\"mime_type\":\"application/pdf\"},\"stats\":{\"report_type\":\"weekly_machine_progress\",\"board_id\":\"5086438002\",\"machine_count\":1,\"avg_overall\":50.0,\"critical_n\":0,\"late_n\":0,\"pdf_size_kb\":1}}"

# wrong token must NOT be 200
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "https://n8n.rotocon.world/webhook/monday-weekly-report" \
  -H "X-Report-Token: wrong" -H "Content-Type: application/json" -d '{}'
```
Expected: first call `200` and an email with a tiny PDF arrives + one `report_history` row; second call `401`/`403`.

- [ ] **Step 7: Activate**

```
mcp__n8n-mcp__n8n_update_partial_workflow(id="<wf id>",
    operations=[{"type": "updateSettings", "settings": {"active": true}}])
```
(Confirm the exact partial-update op via `mcp__n8n-mcp__tools_documentation(topic="n8n_update_partial_workflow")` if it differs.)

- [ ] **Step 8: No git commit (no repo files changed). Record the workflow + credential IDs in a scratch note (not committed).**

---

## Task 13: GitHub Actions scheduler + SECRETS.md

**Files:**
- Create: `.github/workflows/weekly-machine-report.yml`
- Create: `SECRETS.md`

- [ ] **Step 1: Create the workflow file**

Create `.github/workflows/weekly-machine-report.yml`:

```yaml
name: Weekly Machine Report

on:
  schedule:
    # 05:00 UTC Monday ≈ 07:00 Europe/Bucharest (winter) / 08:00 (summer).
    - cron: "0 5 * * 1"
  workflow_dispatch: {}

jobs:
  send-report:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Install WeasyPrint system libraries
        run: |
          sudo apt-get update
          sudo apt-get install -y \
            libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"

      - name: Sync dependencies (with report extra)
        run: uv sync --extra report

      - name: Send weekly report
        env:
          MONDAY_API_TOKEN: ${{ secrets.MONDAY_API_TOKEN }}
          N8N_WEBHOOK_URL: ${{ secrets.N8N_WEBHOOK_URL }}
          N8N_WEBHOOK_TOKEN: ${{ secrets.N8N_WEBHOOK_TOKEN }}
          REPORT_RECIPIENT: ${{ secrets.REPORT_RECIPIENT }}
        run: uv run python scripts/weekly_machine_report.py
```

- [ ] **Step 2: Create SECRETS.md**

Create `SECRETS.md`:

```markdown
# GitHub Actions Secrets — Weekly Machine Report

Configure under **Settings → Secrets and variables → Actions** for
`Geronimo1975/monday_rotocon`:

| Secret | Value |
|---|---|
| `MONDAY_API_TOKEN` | monday.com personal API token (read scope) |
| `N8N_WEBHOOK_URL` | `https://n8n.rotocon.world/webhook/monday-weekly-report` |
| `N8N_WEBHOOK_TOKEN` | the 64-char hex token set on the `Report Webhook Token` n8n credential |
| `REPORT_RECIPIENT` | `george@rotocon.world` (expand to the team later) |

Schedule: `cron: "0 5 * * 1"` (Mondays, ~07:00 Europe/Bucharest).
Manual run: Actions → "Weekly Machine Report" → "Run workflow".
```

- [ ] **Step 3: Verify the workflow YAML parses**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/weekly-machine-report.yml')); print('ok')"`
Expected: prints `ok`. (If PyYAML is unavailable, skip — GitHub validates on push.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/weekly-machine-report.yml SECRETS.md
git commit -m "ci(weekly): GitHub Actions schedule + secrets doc"
```

---

## Task 14: Opt-in live integration test

**Files:**
- Create: `tests/integration/test_weekly_report_live.py`

- [ ] **Step 1: Create the test**

Create `tests/integration/test_weekly_report_live.py`:

```python
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

    from monday_rotocon import MondayClient
    from weekly_machine_report import (
        build_exceptions,
        compute_summary,
        fetch_current_machines,
        render_pdf,
        render_report_html,
    )

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
```

- [ ] **Step 2: Confirm it's deselected on the default run**

Run: `uv run pytest -m "not integration" tests/integration/test_weekly_report_live.py -v`
Expected: `deselected` count = 1.

- [ ] **Step 3: Run it for real (with MONDAY_API_TOKEN set)**

Run: `uv run pytest tests/integration/test_weekly_report_live.py -m integration -v`
Expected: PASS — renders the real board to a PDF (no email sent).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_weekly_report_live.py
git commit -m "test(weekly): opt-in live integration test (renders real board PDF)"
```

---

## Task 15: Manual end-to-end + final gates

**No new files.**

- [ ] **Step 1: Local dry-run, eyeball the PDF**

Ensure `.env` has the four vars. Run:
```bash
uv run python scripts/weekly_machine_report.py --dry-run
```
Expected: `Wrote reports/<stamp>-weekly-machine-report.pdf (...)`. Open the PDF; check KPIs, exceptions section, full table, header/footer with KW + page numbers. Save a copy as `reports/sample-weekly-machine-report.pdf` for sign-off (gitignored — share manually).

- [ ] **Step 2: Full pipeline against the live workflow**

```bash
uv run python scripts/weekly_machine_report.py
```
Expected: ends with `OK machines=... critical=... n8n_messageId=... pdf=...`; email with PDF attachment arrives at george@'s inbox within ~30s; one new row in `rotocon_finance.report_history`.

If the email does not arrive but the script returned 0: check the n8n execution log for `monday-machine-weekly-report-delivery`. Most likely cause is the Gmail attachment binary-property name or a `$json` vs `$('Webhook')` reference after Convert to File — fix per the MEMORY note, re-validate, re-run.

- [ ] **Step 3: Spot-check accuracy**

Pick 2 machines in the board; verify their Overall % and exception membership match the PDF.

- [ ] **Step 4: Full project quality gates**

```bash
uv run ruff format .
uv run ruff check .
uv run mypy src
uv run pytest
```
Expected: format clean, lint clean, mypy strict success (covers `src/` only), all default-marker tests green.

- [ ] **Step 5: Configure GitHub secrets, then trigger one manual run**

Add the four secrets from `SECRETS.md`. Push the branch. In GitHub → Actions → "Weekly Machine Report" → "Run workflow". Confirm a green run and the email arrives.

- [ ] **Step 6: Sign-off gate before activating the schedule**

Show george@ the rendered PDF. Only after sign-off, leave the cron active. Expanding the recipient list to the internal team is a one-line edit to the Gmail node's `sendTo` (or the `REPORT_RECIPIENT` secret) — done separately.

- [ ] **Step 7: Update MEMORY if any non-obvious decision arose**

If the Gmail attachment property or Postgres `queryReplacement` shape needed a non-obvious fix, add a memory file + MEMORY.md pointer.

---

## Self-review notes (cross-check before executing)

- **Spec coverage:** Fetch+filter (T3), KPIs/exceptions (T4–T5), engineering PDF (T6–T7), short email body (T8), payload+stats (T9), retry POST (T10), orchestration (T11), n8n delivery+Postgres (T12), GitHub scheduler (T13), tests (T2–T11, T14), rollout (T15). All spec sections mapped.
- **Lazy WeasyPrint import** keeps the existing 38 tests runnable without system libs; PDF-dependent tests use `importorskip`.
- **Type consistency:** `MachineRow`, `PortfolioSummary`, `ExceptionRow`, `WebhookPayload`/`PdfAttachment`/`ReportStats` defined once and reused; helper names (`col_text`, `col_number`, `_is_discrepant`, `_delivers_within_horizon`, `parse_deliver_date`) consistent across tasks.
- **Convert-to-File gotcha** from MEMORY is called out explicitly in T12.
</content>
