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
