"""Shared stdlib-only monday.com REST helpers for operational scripts.

`bootstrap_ki_integration.py` and `extend_ki_integration_columns.py` both
need to read the API token from `.env` and POST GraphQL with nothing but the
Python standard library (they may run before `uv sync`). This module is the
single home for that logic so it is written — and tested — exactly once.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.monday.com/v2"
API_VERSION = "2024-10"


def load_token(env_path: Path | None = None) -> str:
    """Read ``MONDAY_API_TOKEN`` from a ``.env`` file.

    Exits the process (code 1) if the file or the key is missing. ``env_path``
    defaults to ``<repo-root>/.env``; it is injectable for tests.
    """
    env_path = env_path or Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        sys.exit(f"FATAL: no .env at {env_path}")
    for line in env_path.read_text().splitlines():
        if line.startswith("MONDAY_API_TOKEN="):
            return line.split("=", 1)[1].strip()
    sys.exit("FATAL: MONDAY_API_TOKEN not found in .env")


def gql(
    token: str,
    query: str,
    variables: dict | None = None,
    *,
    user_agent: str = "monday_rotocon-scripts/0.1",
) -> dict:
    """POST a GraphQL query with stdlib ``urllib``; return the ``data`` payload.

    Exits the process on an HTTP error or any GraphQL ``errors`` array — these
    scripts are one-shot operational tooling where aborting loudly is correct.
    """
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "API-Version": API_VERSION,
            "User-Agent": user_agent,
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
