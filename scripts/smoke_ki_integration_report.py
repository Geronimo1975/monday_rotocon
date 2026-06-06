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
from collections import OrderedDict
from dataclasses import dataclass

from monday_rotocon import Item


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


def group_items_by_title(items: list[Item]) -> list[tuple[str, int]]:
    """Count items per group title, preserving first-seen order.

    Items without a group are bucketed under "(ungrouped)".
    """
    counts: OrderedDict[str, int] = OrderedDict()
    for item in items:
        title = item.group.title if item.group is not None else "(ungrouped)"
        counts[title] = counts.get(title, 0) + 1
    return list(counts.items())


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
