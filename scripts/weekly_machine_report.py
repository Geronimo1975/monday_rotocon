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
