#!/usr/bin/env python3
"""Idempotent enrichment: add the 12 columns + 3 views needed for the
roadmap page to the KI Integration board (id 5096182046).

This is operational tooling, NOT part of the monday_rotocon skeleton.
Runs anytime; safe to re-run — existing columns / views are detected
by title and skipped.

Uses only the Python stdlib so it works before `uv sync` has been run.
"""

from __future__ import annotations

import functools
import json
import sys
import time

from _monday_rest import gql as _gql
from _monday_rest import load_token

BOARD_ID = 5096182046
ACCOUNT_SLUG = "rotocon-world"

# Bind this script's User-Agent once; call sites stay `gql(token, query, vars)`.
gql = functools.partial(_gql, user_agent="monday_rotocon-extend/0.1")


# Column specs from spec §4.1 — title, type, defaults (JSON string for monday)
COLUMNS_PLAN: list[dict] = [
    {
        "title": "Status",
        "type": "status",
        "defaults": json.dumps(
            {
                "labels": {
                    "0": "Not started",
                    "1": "In progress",
                    "2": "Blocked",
                    "3": "Done",
                    "4": "Deferred",
                }
            }
        ),
    },
    {
        "title": "Phase",
        "type": "status",
        "defaults": json.dumps(
            {
                "labels": {
                    "0": "M1",
                    "1": "M2",
                    "2": "M3",
                    "3": "M4",
                    "4": "M5",
                    "5": "M6",
                    "6": "Onboarding",
                    "7": "Ongoing",
                }
            }
        ),
    },
    {"title": "Owner", "type": "people", "defaults": "{}"},
    {"title": "Timeline", "type": "timeline", "defaults": "{}"},
    {"title": "Due", "type": "date", "defaults": "{}"},
    {
        "title": "Priority",
        "type": "status",
        "defaults": json.dumps(
            {
                "labels": {
                    "0": "Critical",
                    "1": "High",
                    "2": "Medium",
                    "3": "Low",
                }
            }
        ),
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
    print_view_setup_instructions()
    return 0


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


if __name__ == "__main__":
    sys.exit(main())
