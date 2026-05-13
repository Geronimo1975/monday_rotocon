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
