# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Typed monday.com client + dashboard-export CLI for ROTOCON Europe GmbH. This is **sub-project A** of a multi-month digital-transformation program; the contract for downstream sub-projects (B/C/D — webhook sync, configurator/AI, telemetry) is fixed by the spec at `docs/superpowers/specs/2026-05-10-monday-core-skeleton-design.md`. Read that spec before any architectural change.

## Commands

Dependency + venv manager is `uv` (project pins Python 3.12 via `.python-version`).

```bash
uv sync --all-extras            # install runtime + dev deps into .venv
uv run pytest                   # full test suite (unit by default)
uv run pytest tests/test_client.py::test_name  # single test
uv run pytest -m integration    # opt-in: hits real monday.com API
uv run mypy src                 # strict typecheck (configured in pyproject)
uv run ruff check .             # lint
uv run ruff format .            # format
uv run monday <subcmd>          # CLI entrypoint (Typer)
```

`MONDAY_API_TOKEN` must be set (via `.env`) for the CLI and integration tests.

## Architecture

Three-layer library with strictly inward-flowing dependencies; CLI sits on top.

- **`transport.py`** — `MondayClient` wraps `httpx.Client`, owns the retry policy (5xx/429 + `httpx.TransportError` → exponential backoff, configurable via `max_retries`/`backoff_base`). Raises `MondayAPIError` on persistent failure or GraphQL errors. **No global state** — instantiate per use, or use as a context manager. Exposes high-level `boards(ids=...)` and `items_for_board(board_id=...)` iterators that handle pagination internally.
- **`queries.py`** — GraphQL query strings. Uses cursor-based pagination via `items_page` / `next_items_page` (the post-2024 monday API; the older `items(...)` field is gone).
- **`models.py`** — Pydantic models with `extra="ignore"` so monday API additions don't break parsing. `ColumnValue.column_id` is aliased from `id`.

### Read-only invariant

The `monday_rotocon` package is **read-only by design** — it never mutates monday state. Anything that creates/updates boards or items belongs in **`scripts/`** as a standalone Python file using only stdlib (so it can run before `uv sync`). `scripts/` is not part of the package import path. Don't add mutation helpers to the library; if a workflow needs them, write a script.

Concrete example: `scripts/bootstrap_ki_integration.py` was a one-shot board creator and intentionally bypasses the library.

### CLI status

`src/monday_rotocon/cli.py` is currently a stub. The roadmap's real subcommands (`ping`, `boards list`, `export dashboard`) are scheduled for later tasks. Don't assume the `monday` command does anything beyond return a "not yet implemented" exit code today.

## Testing notes

- `pytest-asyncio` is configured with `asyncio_mode = "auto"`; mark sync-only tests if needed.
- HTTP is mocked via `respx` — do not let unit tests make real network calls. The `integration` marker is the only path that hits real monday.com.
- Strict pytest config: `--strict-markers --strict-config`; new markers must be declared in `pyproject.toml`.
- `tests/conftest.py` provides `fixture_loader` (loads `tests/fixtures/<name>.json`) and `dummy_token`.

## MCP

`.mcp.json` configures the official monday MCP server (`@mondaydotcomorg/monday-api-mcp`) and reads `MONDAY_API_TOKEN` from the environment. Use it for exploratory monday queries instead of writing one-off scripts.
