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
