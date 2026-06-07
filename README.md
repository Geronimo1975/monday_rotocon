# monday_rotocon

Typed monday.com client and dashboard-export CLI for ROTOCON Europe GmbH.
Implements sub-project A of the digital-transformation roadmap; spec at
`docs/superpowers/specs/2026-05-10-monday-core-skeleton-design.md`.

## Quickstart

```bash
# 1. Copy the env template and add your monday API token.
cp .env.example .env
# edit .env — set MONDAY_API_TOKEN

# 2. Install dependencies into a project-local venv.
uv sync --all-extras

# 3. Verify connectivity.
uv run monday ping
```

See the spec and `docs/superpowers/plans/` for design and implementation
detail.

## Testing

```bash
# Fast unit suite (network is mocked; no credentials needed).
uv run pytest

# With the coverage gate (fails under 90%; enforced in CI).
uv run pytest --cov --cov-report=term-missing

# Opt-in live integration test — hits the real monday.com API and the
# n8n test-echo workflow. Never sends mail. Requires:
#   MONDAY_API_TOKEN, N8N_WEBHOOK_URL_TEST, N8N_WEBHOOK_TOKEN, REPORT_RECIPIENT
uv run pytest -m integration

# Lint + type-check (same checks CI runs).
uv run ruff check .
uv run mypy
```

CI (`.github/workflows/ci.yml`) runs ruff, mypy, and the coverage-gated test
suite on every push and pull request. The `integration`-marked test is skipped
automatically when its environment variables are absent.
