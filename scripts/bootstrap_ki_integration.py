#!/usr/bin/env python3
"""One-shot bootstrap: create the 'KI Integration' board in monday.com
and populate with items derived from Tasks/ROTOCON_Onboarding_DE.docx.

This is operational tooling, NOT part of the monday_rotocon skeleton.
Run once. Idempotency: refuses to run if a board with the same name already
exists in the target workspace (archive it manually first to re-run).

Uses only the Python stdlib so it works before `uv sync` has been run.
"""

from __future__ import annotations

import functools
import sys
import time

from _monday_rest import gql as _gql
from _monday_rest import load_token

# Bind this script's User-Agent once; call sites stay `gql(token, query, vars)`.
gql = functools.partial(_gql, user_agent="monday_rotocon-bootstrap/0.1")

WORKSPACE_ID = 5528271  # ROTOCON EU SERVICE
BOARD_NAME = "KI Integration"
ACCOUNT_SLUG = "rotocon-world"

GROUPS_PLAN: dict[str, list[str]] = {
    "Onboarding (Tag 1)": [
        "4.1 Setup & Systemzugang — Pouya / IT-Support",
        "4.2 Business- & Strategie-Briefing — Michael",
        "4.3 Teamvorstellung — Michael & Pouya",
        "4.4 System-Deep-Dive (CRM, ERP) — Pouya & Metin",
        "4.5 Angebots- & Preislogik — Metin",
        "4.6 End-to-End Prozess-Walkthrough — Metin",
        "4.7 Optimierungs-Session — Metin, Michael & Pouya",
        "4.8 Abstimmung & nächste Schritte — Metin & Michael",
    ],
    "4-Wochen Execution-Plan": [
        "Woche 1 — Analyse & Architektur",
        "Woche 2 — Integration (Datenmodell, CRM↔ERP, Automatisierungen)",
        "Woche 3 — Konfigurator-MVP",
        "Woche 4 — End-to-End Execution",
    ],
    "Operatives Setup monday.com": [
        "Leads-Board einrichten",
        "Angebots-Board einrichten",
        "Auftrags-Board einrichten",
        "Projekt-Board einrichten",
        "Automatisierungen zwischen allen Phasen aufbauen",
    ],
    "KPI Tracking": [
        "Leads pro Monat (Ziel: 60+)",
        "Opportunities pro Monat (Ziel: 20+)",
        "Konversionsrate (Ziel: > 25%)",
        "Angebotslaufzeit (Ziel: < 48h)",
        "Einsparung durch Automatisierung (Ziel: 30%)",
        "Pipeline-Transparenz (Ziel: 100%)",
    ],
    "AI Initiatives (M4-M6)": [
        "AI Quotation Assistant (M4)",
        "AI Reporting Assistant (M4)",
        "Internal Knowledge Base (M4)",
        "Smart Machine Pilot (M5)",
        "Live Machine Data Collection (M5)",
        "Predictive Maintenance Concept (M5–M6)",  # noqa: RUF001
    ],
}


def find_existing_board(token: str, name: str, workspace_id: int) -> int | None:
    data = gql(
        token,
        """
        query($ws: [ID!]) {
          boards(workspace_ids: $ws, limit: 200, state: active) { id name }
        }
        """,
        {"ws": [str(workspace_id)]},
    )
    for b in data["boards"]:
        if b["name"] == name:
            return int(b["id"])
    return None


def main() -> int:
    token = load_token()

    existing = find_existing_board(token, BOARD_NAME, WORKSPACE_ID)
    if existing is not None:
        print(
            f"⚠️  Board '{BOARD_NAME}' already exists (id={existing}) in workspace {WORKSPACE_ID}."
        )
        print("    Aborting to avoid duplicates. Archive it in monday UI first to re-run.")
        return 1

    data = gql(
        token,
        """
        mutation($ws: ID!, $name: String!) {
          create_board(workspace_id: $ws, board_name: $name, board_kind: public) {
            id name
            groups { id title }
          }
        }
        """,
        {"ws": str(WORKSPACE_ID), "name": BOARD_NAME},
    )
    board = data["create_board"]
    board_id = int(board["id"])
    print(f"✅ Board created: '{board['name']}' (id={board_id})")
    default_group_id = board["groups"][0]["id"]
    print(f"   Default group: '{board['groups'][0]['title']}' (id={default_group_id})")

    plan_titles = list(GROUPS_PLAN.keys())
    first_title = plan_titles[0]
    gql(
        token,
        """
        mutation($board: ID!, $group: String!, $title: String!) {
          update_group(board_id: $board, group_id: $group,
                       group_attribute: title, new_value: $title) { id }
        }
        """,
        {"board": str(board_id), "group": default_group_id, "title": first_title},
    )
    group_ids: dict[str, str] = {first_title: default_group_id}
    print(f"   Renamed default group → '{first_title}'")

    for title in plan_titles[1:]:
        d = gql(
            token,
            """
            mutation($board: ID!, $title: String!) {
              create_group(board_id: $board, group_name: $title) { id title }
            }
            """,
            {"board": str(board_id), "title": title},
        )
        gid = d["create_group"]["id"]
        group_ids[title] = gid
        print(f"   Group created: '{title}' (id={gid})")
        time.sleep(0.1)

    total_items = 0
    for title, items in GROUPS_PLAN.items():
        gid = group_ids[title]
        print(f"\n📋 {title}")
        for item_name in items:
            d = gql(
                token,
                """
                mutation($board: ID!, $group: String!, $name: String!) {
                  create_item(board_id: $board, group_id: $group,
                              item_name: $name) { id }
                }
                """,
                {"board": str(board_id), "group": gid, "name": item_name},
            )
            iid = d["create_item"]["id"]
            total_items += 1
            print(f"   • [{iid}] {item_name}")
            time.sleep(0.05)

    print(
        f"\n🎉 Done. Board '{BOARD_NAME}' (id={board_id}) — "
        f"{len(group_ids)} groups, {total_items} items."
    )
    print(f"   URL: https://{ACCOUNT_SLUG}.monday.com/boards/{board_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
