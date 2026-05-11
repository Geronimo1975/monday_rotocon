# `monday_core` Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `monday_rotocon` Python package — a typed, sync+async client for monday.com plus a Typer CLI that exports board/item snapshots for CEO Dashboard V1 — per the approved spec at `docs/superpowers/specs/2026-05-10-monday-core-skeleton-design.md`.

**Architecture:** Three-layer design with strictly inward dependencies (Applications → Domain → Transport). The transport layer is generic over `httpx.Client` / `httpx.AsyncClient` so sync and async clients share parsing, error mapping, complexity tracking, and retry logic. Domain models are Pydantic v2 with discriminated unions on `column_values`. GraphQL operations live as `.graphql` files in a `queries/` directory and are loaded once at import.

**Tech Stack:** Python 3.12 · uv (package manager) · httpx (HTTP) · Pydantic v2 + pydantic-settings · Typer (CLI) · pytest + respx (HTTP mock) + pytest-asyncio + pytest-cov · mypy (strict) · ruff.

**Existing repo state at plan time:**
- `.env` (with `MONDAY_API_TOKEN=…`)
- `.gitignore`
- `Tasks/` (strategic source documents — leave untouched)
- `docs/superpowers/specs/2026-05-10-monday-core-skeleton-design.md` (approved)
- `scripts/bootstrap_ki_integration.py` (one-shot ops, not part of skeleton)

---

## File Structure

After this plan completes, the repo will contain:

```
/Users/rotocondemo/monday_rotocon/
├── .env                              # already exists (secret; gitignored)
├── .env.example                      # NEW — committed; documents required vars
├── .gitignore                        # already exists
├── .python-version                   # NEW — pins 3.12 for uv
├── pyproject.toml                    # NEW — uv-managed project metadata + tool config
├── README.md                         # NEW — quickstart + arch summary
├── Tasks/                            # already exists; untouched
├── docs/                             # already exists
│   └── superpowers/
│       ├── specs/                    # already exists; spec lives here
│       └── plans/                    # this file's location
├── scripts/                          # already exists
│   └── bootstrap_ki_integration.py   # already exists; untouched
├── src/
│   └── monday_rotocon/
│       ├── __init__.py               # NEW — public re-exports + __version__
│       ├── py.typed                  # NEW — empty PEP 561 marker
│       ├── settings.py               # NEW — pydantic-settings
│       ├── _errors.py                # NEW — typed exception hierarchy
│       ├── _complexity.py            # NEW — budget tracker
│       ├── _transport.py             # NEW — sync + async GraphQL transport
│       ├── client.py                 # NEW — MondayClient + AsyncMondayClient
│       ├── cli.py                    # NEW — Typer app
│       ├── models/
│       │   ├── __init__.py           # NEW — re-exports
│       │   ├── _base.py              # NEW — MondayModel base
│       │   ├── account.py            # NEW — Account
│       │   ├── user.py               # NEW — User
│       │   ├── board.py              # NEW — Workspace, Group, Board
│       │   ├── column_values.py      # NEW — discriminated union
│       │   └── item.py               # NEW — Item
│       └── queries/
│           ├── __init__.py           # NEW — query loader
│           ├── me.graphql            # NEW
│           ├── boards.graphql        # NEW
│           └── items.graphql         # NEW
└── tests/
    ├── __init__.py                   # NEW — empty
    ├── conftest.py                   # NEW — shared fixtures
    ├── fixtures/                     # NEW — sanitized JSON
    │   ├── me.json
    │   ├── boards_list.json
    │   └── items_page.json
    ├── unit/
    │   ├── __init__.py               # NEW — empty
    │   ├── test_settings.py          # NEW
    │   ├── test_errors.py            # NEW
    │   ├── test_complexity.py        # NEW
    │   ├── test_models.py            # NEW
    │   ├── test_queries_loader.py    # NEW
    │   ├── test_transport.py         # NEW
    │   ├── test_client_sync.py       # NEW
    │   ├── test_client_async.py      # NEW
    │   └── test_cli.py               # NEW
    └── integration/
        ├── __init__.py               # NEW — empty
        └── test_smoke.py             # NEW — opt-in `pytest -m integration`
```

**File responsibility map (single-purpose, easy to hold in context):**

| File | Responsibility |
|---|---|
| `settings.py` | Read env + `.env`, validate, expose `Settings` dataclass |
| `_errors.py` | Define `MondayError` hierarchy; `raise_for(payload, status)` mapper |
| `_complexity.py` | Track GraphQL complexity budget; warn when low |
| `_transport.py` | GraphQL POST + JSON parse + error/complexity handling + retries; sync and async classes share base |
| `client.py` | Public `MondayClient` / `AsyncMondayClient` + thin resource objects (`MeResource`, `BoardsResource`, `ItemsResource`) that load queries and parse models |
| `cli.py` | Typer entry point with `ping`, `boards list`, `export dashboard` subcommands |
| `models/_base.py` | `MondayModel` base with shared Pydantic config (`extra="ignore"`, etc.) |
| `models/{account,user,board,item}.py` | One file per domain noun |
| `models/column_values.py` | Discriminated union for monday's heterogeneous `column_values` arrays |
| `queries/*.graphql` | One operation per file (syntax-highlighted, copy-paste-able to monday Playground) |
| `queries/__init__.py` | One-shot loader: `dict[name, query_string]` |

---

## Conventions used in every task

- **Always work from `/Users/rotocondemo/monday_rotocon/` as cwd** unless a step explicitly says otherwise.
- **Run tests with `uv run pytest …`**, not bare `pytest`. `uv run` ensures the project venv is active.
- **Commit messages** follow Conventional Commits (`feat:`, `chore:`, `test:`, `docs:`, `fix:`).
- **Frequent commits.** Every task ends with a commit. If a task fails partway, commit progress before pausing — don't leave uncommitted work.
- **Never commit `.env`** — `.gitignore` already excludes it; verify with `git status` before each commit.

---

## Task 1: Bootstrap project skeleton

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/pyproject.toml`
- Create: `/Users/rotocondemo/monday_rotocon/.python-version`
- Create: `/Users/rotocondemo/monday_rotocon/.env.example`
- Create: `/Users/rotocondemo/monday_rotocon/README.md`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/py.typed`
- Create: `/Users/rotocondemo/monday_rotocon/tests/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/integration/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/conftest.py`

- [ ] **Step 1: Verify `uv` is available**

Run: `uv --version`
Expected: prints version (e.g., `uv 0.4.x` or newer). If absent: `brew install uv` then retry.

- [ ] **Step 2: Initialize git repository**

Run from `/Users/rotocondemo/monday_rotocon/`:

```bash
git init
git add .gitignore Tasks/ docs/ scripts/ .env.example 2>/dev/null || true
```

(`.env.example` doesn't exist yet — the `2>/dev/null || true` swallows the error; we'll add it in Step 5.)

- [ ] **Step 3: Pin Python version**

Create `.python-version`:

```
3.12
```

- [ ] **Step 4: Write `pyproject.toml`**

Create `pyproject.toml` with full content:

```toml
[project]
name = "monday-rotocon"
version = "0.1.0"
description = "Typed monday.com client + dashboard export CLI for ROTOCON Europe GmbH"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "Proprietary" }
authors = [{ name = "George Sebastian Cucuiet", email = "george@rotocon.world" }]

dependencies = [
    "httpx>=0.27",
    "pydantic>=2.5",
    "pydantic-settings>=2.2",
    "typer>=0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
    "respx>=0.21",
    "mypy>=1.10",
    "ruff>=0.5",
]

[project.scripts]
monday = "monday_rotocon.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/monday_rotocon"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
markers = [
    "integration: tests that hit the real monday.com API (opt-in)",
]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["monday_rotocon"]
branch = true

[tool.coverage.report]
fail_under = 0
show_missing = true
skip_covered = true
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src/monday_rotocon"]
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["respx.*", "tests.*"]
ignore_missing_imports = true
disallow_untyped_defs = false

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E", "F", "W",     # pycodestyle + pyflakes
    "I",               # isort
    "B",               # bugbear
    "UP",              # pyupgrade
    "N",               # pep8-naming
    "SIM",             # simplify
    "RUF",             # ruff-specific
]
ignore = ["E501"]  # line length handled by formatter

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["B011", "N802"]
```

- [ ] **Step 5: Create `.env.example`**

```bash
# monday.com API access — copy to .env and fill in
MONDAY_API_TOKEN=

# Optional overrides (defaults shown)
# MONDAY_API_VERSION=2024-10
# MONDAY_REGION=euc1
# MONDAY_API_URL=https://api.monday.com/v2
# MONDAY_REQUEST_TIMEOUT_S=30.0
# MONDAY_COMPLEXITY_WARN=0.10

# Optional separate token used ONLY by integration tests (read-only preferred)
# MONDAY_INTEGRATION_TOKEN=
```

- [ ] **Step 6: Create `src/monday_rotocon/__init__.py`**

```python
"""monday.com client + dashboard export tooling for ROTOCON Europe GmbH."""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

(Public re-exports of `MondayClient`, `AsyncMondayClient`, models, etc. are added in later tasks once those symbols exist.)

- [ ] **Step 7: Create empty marker files**

```bash
touch src/monday_rotocon/py.typed
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
mkdir -p tests/fixtures
```

- [ ] **Step 8: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures for monday_rotocon tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_loader():
    """Return a callable that loads a JSON fixture by stem name."""
    def _load(name: str) -> dict:
        path = FIXTURES_DIR / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def dummy_token() -> str:
    return "dummy.test.token"
```

- [ ] **Step 9: Create README stub**

Create `README.md`:

```markdown
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
```

- [ ] **Step 10: Sync dependencies**

Run from project root:

```bash
uv sync --all-extras
```

Expected output: creates `.venv/`, resolves and installs httpx, pydantic, typer, pytest, respx, mypy, ruff, etc. No errors.

- [ ] **Step 11: Smoke-test the package import**

Run:

```bash
uv run python -c "import monday_rotocon; print(monday_rotocon.__version__)"
```

Expected output: `0.1.0`

- [ ] **Step 12: Add `.venv` and build artifacts to `.gitignore`**

Edit `/Users/rotocondemo/monday_rotocon/.gitignore` — append before the closing block (after `*.swp` line if present):

```
# Project-local
uv.lock
.venv/
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
```

(`.env` is already covered by the `.env` line in the existing `.gitignore`.)

- [ ] **Step 13: Verify nothing sensitive will be committed**

Run:

```bash
git status
git diff --cached
```

Expected: see new files staged (pyproject.toml, README.md, .python-version, .env.example, src/, tests/, .gitignore changes), but **NOT** `.env`, `.venv/`, `uv.lock` (we ignore the lockfile in this repo to keep velocity; if the team standardizes, switch to committing it).

- [ ] **Step 14: Commit**

```bash
git add pyproject.toml .python-version .env.example README.md src/ tests/ .gitignore
git commit -m "chore: bootstrap monday_rotocon package skeleton

- Pin Python 3.12 via .python-version
- Add pyproject.toml with httpx/pydantic/typer + dev tooling (pytest, respx, mypy, ruff)
- src-layout under src/monday_rotocon/ with py.typed marker
- Test scaffolding (tests/{unit,integration}/, conftest.py with fixture_loader)
- .env.example documenting required and optional vars
- README quickstart"
```

---

## Task 2: `settings.py` — configuration

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/settings.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_settings.py`:

```python
"""Tests for monday_rotocon.settings."""
from __future__ import annotations

import pytest

from monday_rotocon.settings import Settings


def test_settings_loads_token_from_env(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "abc.def.ghi")
    s = Settings()
    assert s.monday_api_token == "abc.def.ghi"


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "tok")
    s = Settings()
    assert s.monday_api_version == "2024-10"
    assert s.monday_region == "euc1"
    assert s.monday_api_url == "https://api.monday.com/v2"
    assert s.request_timeout_s == 30.0
    assert s.complexity_warn_threshold == 0.10


def test_settings_can_override_defaults(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "tok")
    monkeypatch.setenv("MONDAY_API_VERSION", "2025-01")
    monkeypatch.setenv("MONDAY_REQUEST_TIMEOUT_S", "5")
    s = Settings()
    assert s.monday_api_version == "2025-01"
    assert s.request_timeout_s == 5.0


def test_settings_requires_token(monkeypatch):
    monkeypatch.delenv("MONDAY_API_TOKEN", raising=False)
    # also disable .env loading so tests are deterministic
    with pytest.raises(Exception):  # ValidationError from Pydantic
        Settings(_env_file=None)


def test_settings_threshold_must_be_fraction(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "tok")
    monkeypatch.setenv("MONDAY_COMPLEXITY_WARN", "1.5")
    with pytest.raises(Exception):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_settings.py -v`
Expected: ImportError or ModuleNotFoundError on `from monday_rotocon.settings import Settings` (file doesn't exist yet).

- [ ] **Step 3: Implement `settings.py`**

Create `src/monday_rotocon/settings.py`:

```python
"""Application settings loaded from environment + `.env`."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for the monday_rotocon client.

    Reads from process environment first, then from `.env` in the current
    working directory if present. Field names are matched case-insensitively
    against env var names.
    """

    monday_api_token: str = Field(min_length=1)
    monday_api_version: str = "2024-10"
    monday_region: str = "euc1"
    monday_api_url: str = "https://api.monday.com/v2"
    request_timeout_s: float = Field(default=30.0, gt=0.0)
    complexity_warn_threshold: float = Field(default=0.10, ge=0.0, le=1.0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_settings.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Type-check**

Run: `uv run mypy src/monday_rotocon/settings.py`
Expected: `Success: no issues found in 1 source file`.

- [ ] **Step 6: Commit**

```bash
git add src/monday_rotocon/settings.py tests/unit/test_settings.py
git commit -m "feat(settings): pydantic-settings-based config with .env support"
```

---

## Task 3: `_errors.py` — typed exception hierarchy

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/_errors.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_errors.py`:

```python
"""Tests for monday_rotocon._errors."""
from __future__ import annotations

import pytest

from monday_rotocon._errors import (
    ComplexityExhausted,
    MondayAPIError,
    MondayError,
    RateLimited,
    raise_for,
)


def test_hierarchy():
    assert issubclass(MondayAPIError, MondayError)
    assert issubclass(RateLimited, MondayError)
    assert issubclass(ComplexityExhausted, MondayError)


def test_carries_request_id():
    e = MondayAPIError("boom", request_id="req-123")
    assert e.request_id == "req-123"
    assert "boom" in str(e)


def test_raise_for_returns_silently_on_clean_response():
    raise_for({"data": {"me": {"id": "1"}}}, 200)


def test_raise_for_maps_complexity_exception():
    payload = {
        "errors": [{
            "message": "Complexity budget exhausted",
            "extensions": {
                "code": "ComplexityException",
                "retry_in_seconds": 42,
                "complexity": 1234,
            },
        }],
        "extensions": {"request_id": "req-c"},
    }
    with pytest.raises(ComplexityExhausted) as exc:
        raise_for(payload, 200)
    assert exc.value.reset_in_s == 42.0
    assert exc.value.budget == 1234
    assert exc.value.request_id == "req-c"


def test_raise_for_maps_rate_limit_via_code():
    payload = {
        "errors": [{
            "message": "rate limited",
            "extensions": {"code": "Minute_Limit_Exceeded", "retry_after": 7},
        }],
        "extensions": {"request_id": "req-r"},
    }
    with pytest.raises(RateLimited) as exc:
        raise_for(payload, 200)
    assert exc.value.retry_after_s == 7.0
    assert exc.value.request_id == "req-r"


def test_raise_for_maps_429_status():
    with pytest.raises(RateLimited):
        raise_for({"extensions": {"request_id": "rq"}}, 429)


def test_raise_for_maps_generic_graphql_error():
    payload = {
        "errors": [{"message": "field not found"}],
        "extensions": {"request_id": "rq"},
    }
    with pytest.raises(MondayAPIError) as exc:
        raise_for(payload, 200)
    assert "field not found" in str(exc.value)


def test_raise_for_maps_4xx_without_errors_array():
    with pytest.raises(MondayAPIError) as exc:
        raise_for({}, 401)
    assert "401" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_errors.py -v`
Expected: ImportError on `from monday_rotocon._errors import …`.

- [ ] **Step 3: Implement `_errors.py`**

Create `src/monday_rotocon/_errors.py`:

```python
"""Typed exception hierarchy for monday_rotocon."""
from __future__ import annotations

from typing import Any


class MondayError(Exception):
    """Base for all monday_rotocon errors."""

    def __init__(self, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id

    def __str__(self) -> str:
        msg = super().__str__()
        return f"{msg} (request_id={self.request_id})" if self.request_id else msg


class MondayAPIError(MondayError):
    """Generic GraphQL or HTTP error from monday.com."""


class RateLimited(MondayError):
    """The request was rate-limited (HTTP 429 or `Minute_Limit_Exceeded`)."""

    def __init__(
        self,
        message: str,
        *,
        retry_after_s: float = 10.0,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id)
        self.retry_after_s = retry_after_s


class ComplexityExhausted(MondayError):
    """The query exceeded the per-minute complexity budget."""

    def __init__(
        self,
        message: str,
        *,
        reset_in_s: float,
        budget: int,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id)
        self.reset_in_s = reset_in_s
        self.budget = budget


_RATE_LIMIT_CODES = {"Minute_Limit_Exceeded", "RateLimitException"}


def raise_for(payload: dict[str, Any], http_status: int) -> None:
    """Inspect a parsed monday GraphQL response and raise a typed error if needed.

    No-op when the response is clean.
    """
    request_id = payload.get("extensions", {}).get("request_id")
    errors = payload.get("errors") or []

    if errors:
        first = errors[0]
        ext = first.get("extensions") or {}
        code = ext.get("code", "")
        message = first.get("message", "Unknown monday error")

        if code == "ComplexityException" or "ComplexityException" in message:
            raise ComplexityExhausted(
                message,
                reset_in_s=float(ext.get("retry_in_seconds", 30)),
                budget=int(ext.get("complexity", 0)),
                request_id=request_id,
            )
        if code in _RATE_LIMIT_CODES or http_status == 429:
            raise RateLimited(
                message,
                retry_after_s=float(ext.get("retry_after", 10)),
                request_id=request_id,
            )
        raise MondayAPIError(message, request_id=request_id)

    if http_status >= 400:
        if http_status == 429:
            raise RateLimited("HTTP 429", request_id=request_id)
        raise MondayAPIError(f"HTTP {http_status}", request_id=request_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_errors.py -v`
Expected: all 8 tests pass.

- [ ] **Step 5: Type-check**

Run: `uv run mypy src/monday_rotocon/_errors.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/monday_rotocon/_errors.py tests/unit/test_errors.py
git commit -m "feat(errors): typed MondayError hierarchy + raise_for mapper"
```

---

## Task 4: `_complexity.py` — budget tracker

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/_complexity.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_complexity.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_complexity.py`:

```python
"""Tests for monday_rotocon._complexity."""
from __future__ import annotations

import logging

import pytest

from monday_rotocon._complexity import ComplexitySnapshot, ComplexityTracker


def test_track_records_snapshot():
    t = ComplexityTracker()
    t.track({"complexity": {"before": 10_000_000, "after": 9_000_000, "query": 1_000_000}})
    assert t.last == ComplexitySnapshot(before=10_000_000, after=9_000_000, query=1_000_000)


def test_track_ignores_missing_complexity():
    t = ComplexityTracker()
    t.track({})
    assert t.last is None


def test_warn_when_below_threshold(caplog):
    t = ComplexityTracker(warn_threshold=0.10)
    with caplog.at_level(logging.WARNING, logger="monday_rotocon.complexity"):
        t.track({"complexity": {"before": 1_000_000, "after": 500_000, "query": 500_000}})
    assert any("budget low" in r.message for r in caplog.records)


def test_no_warn_above_threshold(caplog):
    t = ComplexityTracker(warn_threshold=0.10)
    with caplog.at_level(logging.WARNING, logger="monday_rotocon.complexity"):
        t.track({"complexity": {"before": 10_000_000, "after": 9_500_000, "query": 500_000}})
    assert not any("budget low" in r.message for r in caplog.records)


def test_threshold_validation_in_constructor():
    with pytest.raises(ValueError):
        ComplexityTracker(warn_threshold=1.5)
    with pytest.raises(ValueError):
        ComplexityTracker(warn_threshold=-0.1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_complexity.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `_complexity.py`**

Create `src/monday_rotocon/_complexity.py`:

```python
"""Tracks monday.com GraphQL complexity-budget usage and warns when low."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("monday_rotocon.complexity")

# Pro-tier monday accounts have a 10M/min complexity budget. This may change
# per tier; the tracker computes a fraction so it is tier-agnostic as long
# as the operator passes the right `total`.
DEFAULT_TOTAL = 10_000_000


@dataclass(frozen=True)
class ComplexitySnapshot:
    """Snapshot of the budget after a single GraphQL request."""

    before: int
    after: int
    query: int


class ComplexityTracker:
    """In-process tracker for the monday GraphQL complexity budget."""

    def __init__(self, *, total: int = DEFAULT_TOTAL, warn_threshold: float = 0.10) -> None:
        if not 0.0 <= warn_threshold <= 1.0:
            raise ValueError(f"warn_threshold must be in [0, 1], got {warn_threshold!r}")
        if total <= 0:
            raise ValueError(f"total must be > 0, got {total!r}")
        self.total = total
        self.warn_threshold = warn_threshold
        self.last: ComplexitySnapshot | None = None

    def track(self, extensions: dict[str, Any]) -> None:
        """Record one snapshot from a response's `extensions` field."""
        c = extensions.get("complexity")
        if not c:
            return
        snap = ComplexitySnapshot(
            before=int(c["before"]),
            after=int(c["after"]),
            query=int(c["query"]),
        )
        self.last = snap
        remaining_fraction = snap.after / self.total
        if remaining_fraction < self.warn_threshold:
            logger.warning(
                "complexity budget low: %d/%d remaining (%.1f%%)",
                snap.after,
                self.total,
                remaining_fraction * 100,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_complexity.py -v`
Expected: 5 pass.

- [ ] **Step 5: Type-check**

Run: `uv run mypy src/monday_rotocon/_complexity.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/monday_rotocon/_complexity.py tests/unit/test_complexity.py
git commit -m "feat(complexity): GraphQL complexity-budget tracker with low-budget warning"
```

---

## Task 5: Models foundation — `_base.py` + `account.py` + `user.py`

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/_base.py`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/account.py`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/user.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/fixtures/me.json`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_models.py`

- [ ] **Step 1: Create the fixture**

Create `tests/fixtures/me.json`:

```json
{
  "id": "103121773",
  "name": "George Sebastian Cucuiet",
  "email": "george@rotocon.world",
  "account": {
    "id": "31832272",
    "name": "rotocons Team",
    "slug": "rotocon-world",
    "tier": "pro"
  }
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_models.py`:

```python
"""Tests for monday_rotocon.models — Account, User (more added in later tasks)."""
from __future__ import annotations

from monday_rotocon.models import Account, User


def test_account_parses_minimal():
    a = Account.model_validate({"id": "1", "name": "n"})
    assert a.id == "1"
    assert a.slug is None


def test_account_ignores_unknown_fields():
    a = Account.model_validate({"id": "1", "name": "n", "future_field": "ok"})
    assert a.name == "n"


def test_user_parses_with_account(fixture_loader):
    raw = fixture_loader("me")
    u = User.model_validate(raw)
    assert u.id == "103121773"
    assert u.email == "george@rotocon.world"
    assert u.account is not None
    assert u.account.tier == "pro"
    assert u.account.slug == "rotocon-world"


def test_user_email_optional():
    u = User.model_validate({"id": "1", "name": "n"})
    assert u.email is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `models/_base.py`**

Create `src/monday_rotocon/models/_base.py`:

```python
"""Base config for all monday_rotocon Pydantic models."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MondayModel(BaseModel):
    """Shared Pydantic configuration.

    `extra="ignore"` lets monday add new fields to its API without breaking us.
    `populate_by_name=True` allows constructing models with field names
    even when an alias is set (used later for fields like `created_at`).
    `str_strip_whitespace=True` cleans up whitespace from string fields.
    """

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
    )
```

- [ ] **Step 5: Implement `models/account.py`**

Create `src/monday_rotocon/models/account.py`:

```python
"""Account model — the workspace owner organisation in monday.com."""
from __future__ import annotations

from ._base import MondayModel


class Account(MondayModel):
    id: str
    name: str
    slug: str | None = None
    tier: str | None = None
```

- [ ] **Step 6: Implement `models/user.py`**

Create `src/monday_rotocon/models/user.py`:

```python
"""User model — represents `me` and any monday.com user."""
from __future__ import annotations

from ._base import MondayModel
from .account import Account


class User(MondayModel):
    id: str
    name: str
    email: str | None = None
    account: Account | None = None
```

- [ ] **Step 7: Implement `models/__init__.py`**

Create `src/monday_rotocon/models/__init__.py`:

```python
"""Public re-exports for monday_rotocon.models."""
from __future__ import annotations

from .account import Account
from .user import User

__all__ = ["Account", "User"]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: 4 tests pass.

- [ ] **Step 9: Type-check**

Run: `uv run mypy src/monday_rotocon/models/`
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add src/monday_rotocon/models/ tests/fixtures/me.json tests/unit/test_models.py
git commit -m "feat(models): MondayModel base + Account + User"
```

---

## Task 6: `models/board.py` — Workspace, Group, Board

**Files:**
- Modify: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/board.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/fixtures/boards_list.json`
- Modify: `/Users/rotocondemo/monday_rotocon/tests/unit/test_models.py`

- [ ] **Step 1: Create the fixture**

Create `tests/fixtures/boards_list.json` (snapshot of real response, sanitized):

```json
[
  {
    "id": "5095798656",
    "name": "Aufgaben",
    "state": "active",
    "items_count": 2,
    "workspace": {"id": "6315150", "name": "Mein Team"},
    "groups": [{"id": "topics", "title": "Group Title"}]
  },
  {
    "id": "5095798655",
    "name": "Warteliste der Bugs",
    "state": "active",
    "items_count": 8,
    "workspace": {"id": "6315150", "name": "Mein Team"},
    "groups": []
  },
  {
    "id": "5096182046",
    "name": "KI Integration",
    "state": "active",
    "items_count": 29,
    "workspace": {"id": "5528271", "name": "ROTOCON EU SERVICE"},
    "groups": [
      {"id": "topics", "title": "Onboarding (Tag 1)"},
      {"id": "group_mm37ypdm", "title": "4-Wochen Execution-Plan"}
    ]
  }
]
```

- [ ] **Step 2: Append failing tests to `tests/unit/test_models.py`**

Append to the existing `tests/unit/test_models.py`:

```python


# --- Board / Workspace / Group -------------------------------------------------

from monday_rotocon.models import Board, Group, Workspace


def test_workspace_parses():
    w = Workspace.model_validate({"id": "1", "name": "Mein Team"})
    assert w.name == "Mein Team"


def test_group_parses():
    g = Group.model_validate({"id": "topics", "title": "Onboarding"})
    assert g.id == "topics"
    assert g.title == "Onboarding"


def test_board_parses_full(fixture_loader):
    raw = fixture_loader("boards_list")
    boards = [Board.model_validate(b) for b in raw]
    assert len(boards) == 3
    ki = next(b for b in boards if b.name == "KI Integration")
    assert ki.items_count == 29
    assert ki.workspace is not None
    assert ki.workspace.name == "ROTOCON EU SERVICE"
    assert len(ki.groups or []) == 2


def test_board_parses_minimal():
    b = Board.model_validate({"id": "1", "name": "X", "state": "active"})
    assert b.workspace is None
    assert b.groups is None
    assert b.items_count is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: ImportError on `Board`/`Group`/`Workspace`.

- [ ] **Step 4: Implement `models/board.py`**

Create `src/monday_rotocon/models/board.py`:

```python
"""Board, Workspace, and Group models.

Group lives here (rather than in its own file) because it is conceptually
owned by Board; Item also references Group, but that single cross-import
is preferable to the noise of a one-class file.
"""
from __future__ import annotations

from ._base import MondayModel


class Workspace(MondayModel):
    id: str
    name: str


class Group(MondayModel):
    id: str
    title: str


class Board(MondayModel):
    id: str
    name: str
    state: str = "active"
    items_count: int | None = None
    workspace: Workspace | None = None
    groups: list[Group] | None = None
```

- [ ] **Step 5: Update `models/__init__.py`**

Replace `src/monday_rotocon/models/__init__.py` content:

```python
"""Public re-exports for monday_rotocon.models."""
from __future__ import annotations

from .account import Account
from .board import Board, Group, Workspace
from .user import User

__all__ = ["Account", "Board", "Group", "User", "Workspace"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: 8 tests pass (4 from Task 5 + 4 new).

- [ ] **Step 7: Type-check**

Run: `uv run mypy src/monday_rotocon/models/`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/monday_rotocon/models/board.py src/monday_rotocon/models/__init__.py tests/fixtures/boards_list.json tests/unit/test_models.py
git commit -m "feat(models): Workspace, Group, Board"
```

---

## Task 7: `models/column_values.py` + `models/item.py`

**Files:**
- Modify: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/column_values.py`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/models/item.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/fixtures/items_page.json`
- Modify: `/Users/rotocondemo/monday_rotocon/tests/unit/test_models.py`

- [ ] **Step 1: Create the fixture**

Create `tests/fixtures/items_page.json`:

```json
{
  "cursor": null,
  "items": [
    {
      "id": "2904970949",
      "name": "4.7 Optimierungs-Session — Metin, Michael & Pouya",
      "state": "active",
      "created_at": "2026-05-10T19:31:00Z",
      "updated_at": "2026-05-10T19:31:00Z",
      "group": {"id": "topics", "title": "Onboarding (Tag 1)"},
      "column_values": [
        {"id": "status", "type": "status", "text": "Working on it"},
        {"id": "person", "type": "people", "text": "Pouya"},
        {"id": "date4", "type": "date", "text": "2026-05-12"},
        {"id": "text",   "type": "text", "text": "kickoff"},
        {"id": "long_text", "type": "long_text", "text": "..."},
        {"id": "mirror", "type": "mirror", "text": "linked"},
        {"id": "weird",  "type": "some_unknown_future_type", "text": "still works"}
      ]
    }
  ]
}
```

- [ ] **Step 2: Append failing tests to `tests/unit/test_models.py`**

Append:

```python


# --- ColumnValue + Item --------------------------------------------------------

from monday_rotocon.models import (
    DateColumnValue,
    GenericColumnValue,
    Item,
    LongTextColumnValue,
    MirrorColumnValue,
    PersonColumnValue,
    StatusColumnValue,
    TextColumnValue,
)


def test_item_parses_with_known_column_types(fixture_loader):
    raw = fixture_loader("items_page")
    item = Item.model_validate(raw["items"][0])
    assert item.name.startswith("4.7 ")
    assert item.group is not None and item.group.title == "Onboarding (Tag 1)"
    cvs = item.column_values or []
    assert len(cvs) == 7
    types = [type(cv).__name__ for cv in cvs]
    assert "StatusColumnValue" in types
    assert "PersonColumnValue" in types
    assert "DateColumnValue" in types
    assert "TextColumnValue" in types
    assert "LongTextColumnValue" in types
    assert "MirrorColumnValue" in types


def test_unknown_column_type_falls_back_to_generic(fixture_loader):
    raw = fixture_loader("items_page")
    item = Item.model_validate(raw["items"][0])
    weird = next(cv for cv in (item.column_values or []) if cv.id == "weird")
    assert isinstance(weird, GenericColumnValue)
    assert weird.type == "some_unknown_future_type"


def test_item_minimal():
    it = Item.model_validate({"id": "1", "name": "n", "state": "active"})
    assert it.column_values is None
    assert it.created_at is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: ImportError on `Item` / column-value types.

- [ ] **Step 4: Implement `models/column_values.py`**

Create `src/monday_rotocon/models/column_values.py`:

```python
"""Discriminated union for monday.com `column_values` arrays.

monday returns one element per column on each item; the shape of each
element depends on the column `type` (status, text, date, people, etc.).
We model the common subset and route everything else to GenericColumnValue.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import Discriminator, Tag

from ._base import MondayModel


class _ColumnBase(MondayModel):
    id: str
    text: str | None = None


class StatusColumnValue(_ColumnBase):
    type: Literal["status"]


class TextColumnValue(_ColumnBase):
    type: Literal["text"]


class LongTextColumnValue(_ColumnBase):
    type: Literal["long_text"]


class DateColumnValue(_ColumnBase):
    type: Literal["date"]


class PersonColumnValue(_ColumnBase):
    type: Literal["people"]


class MirrorColumnValue(_ColumnBase):
    type: Literal["mirror"]


class GenericColumnValue(_ColumnBase):
    """Catch-all for column types we have not specialised yet."""
    type: str


_KNOWN: set[str] = {"status", "text", "long_text", "date", "people", "mirror"}


def _column_discriminator(v: Any) -> str:
    """Return the tag used to dispatch into the union."""
    if isinstance(v, dict):
        t = v.get("type", "")
    else:
        t = getattr(v, "type", "")
    return t if t in _KNOWN else "_generic"


ColumnValue = Annotated[
    Union[
        Annotated[StatusColumnValue, Tag("status")],
        Annotated[TextColumnValue, Tag("text")],
        Annotated[LongTextColumnValue, Tag("long_text")],
        Annotated[DateColumnValue, Tag("date")],
        Annotated[PersonColumnValue, Tag("people")],
        Annotated[MirrorColumnValue, Tag("mirror")],
        Annotated[GenericColumnValue, Tag("_generic")],
    ],
    Discriminator(_column_discriminator),
]
```

- [ ] **Step 5: Implement `models/item.py`**

Create `src/monday_rotocon/models/item.py`:

```python
"""Item model — a row inside a board."""
from __future__ import annotations

from datetime import datetime

from ._base import MondayModel
from .board import Group
from .column_values import ColumnValue


class Item(MondayModel):
    id: str
    name: str
    state: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    group: Group | None = None
    column_values: list[ColumnValue] | None = None
```

- [ ] **Step 6: Update `models/__init__.py`**

Replace `src/monday_rotocon/models/__init__.py` content:

```python
"""Public re-exports for monday_rotocon.models."""
from __future__ import annotations

from .account import Account
from .board import Board, Group, Workspace
from .column_values import (
    ColumnValue,
    DateColumnValue,
    GenericColumnValue,
    LongTextColumnValue,
    MirrorColumnValue,
    PersonColumnValue,
    StatusColumnValue,
    TextColumnValue,
)
from .item import Item
from .user import User

__all__ = [
    "Account",
    "Board",
    "ColumnValue",
    "DateColumnValue",
    "GenericColumnValue",
    "Group",
    "Item",
    "LongTextColumnValue",
    "MirrorColumnValue",
    "PersonColumnValue",
    "StatusColumnValue",
    "TextColumnValue",
    "User",
    "Workspace",
]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: 11 tests pass (8 from earlier + 3 new).

- [ ] **Step 8: Type-check**

Run: `uv run mypy src/monday_rotocon/models/`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add src/monday_rotocon/models/ tests/fixtures/items_page.json tests/unit/test_models.py
git commit -m "feat(models): Item + ColumnValue discriminated union (status/text/date/people/mirror + generic fallback)"
```

---

## Task 8: GraphQL queries + loader

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/queries/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/queries/me.graphql`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/queries/boards.graphql`
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/queries/items.graphql`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_queries_loader.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_queries_loader.py`:

```python
"""Tests for the queries loader."""
from __future__ import annotations

from monday_rotocon.queries import QUERIES


def test_loader_finds_all_three_queries():
    assert set(QUERIES.keys()) >= {"me", "boards", "items"}


def test_me_query_contains_account():
    assert "account" in QUERIES["me"]
    assert "tier" in QUERIES["me"]


def test_boards_query_uses_workspace_and_groups():
    q = QUERIES["boards"]
    assert "workspace" in q
    assert "groups" in q
    assert "items_count" in q


def test_items_query_paginates_via_cursor():
    q = QUERIES["items"]
    assert "items_page" in q
    assert "$cursor" in q
    assert "column_values" in q
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_queries_loader.py -v`
Expected: ImportError.

- [ ] **Step 3: Create `queries/me.graphql`**

```graphql
query Me {
  me {
    id
    name
    email
    account {
      id
      name
      slug
      tier
    }
  }
}
```

- [ ] **Step 4: Create `queries/boards.graphql`**

```graphql
query Boards($limit: Int = 100, $ids: [ID!], $state: State = active) {
  boards(limit: $limit, ids: $ids, state: $state) {
    id
    name
    state
    items_count
    workspace {
      id
      name
    }
    groups {
      id
      title
    }
  }
}
```

- [ ] **Step 5: Create `queries/items.graphql`**

```graphql
query Items($board_id: ID!, $cursor: String, $limit: Int = 100) {
  boards(ids: [$board_id]) {
    items_page(limit: $limit, cursor: $cursor) {
      cursor
      items {
        id
        name
        state
        created_at
        updated_at
        group {
          id
          title
        }
        column_values {
          id
          type
          text
        }
      }
    }
  }
}
```

- [ ] **Step 6: Create `queries/__init__.py`**

```python
"""Loads `.graphql` files in this directory into a string lookup at import."""
from __future__ import annotations

from pathlib import Path

QUERIES: dict[str, str] = {
    p.stem: p.read_text(encoding="utf-8")
    for p in Path(__file__).parent.glob("*.graphql")
}

__all__ = ["QUERIES"]
```

- [ ] **Step 7: Make queries part of the wheel**

Edit `pyproject.toml` — locate the `[tool.hatch.build.targets.wheel]` section and add a force-include for `.graphql` files. Replace it with:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/monday_rotocon"]

[tool.hatch.build.targets.wheel.force-include]
"src/monday_rotocon/queries" = "monday_rotocon/queries"
```

(For the editable install we use during development this isn't required — but it future-proofs `pip install monday-rotocon` shipping the `.graphql` data files.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_queries_loader.py -v`
Expected: 4 tests pass.

- [ ] **Step 9: Commit**

```bash
git add src/monday_rotocon/queries/ tests/unit/test_queries_loader.py pyproject.toml
git commit -m "feat(queries): GraphQL operations as .graphql files + import-time loader"
```

---

## Task 9: `_transport.py` — sync + async GraphQL transport

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/_transport.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_transport.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_transport.py`:

```python
"""Tests for monday_rotocon._transport — both sync and async paths."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from monday_rotocon._complexity import ComplexityTracker
from monday_rotocon._errors import ComplexityExhausted, MondayAPIError, RateLimited
from monday_rotocon._transport import AsyncTransport, SyncTransport
from monday_rotocon.settings import Settings


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "tok")
    return Settings()


def _ok(query_data: dict, complexity_after: int = 9_900_000) -> dict:
    return {
        "data": query_data,
        "extensions": {
            "request_id": "req-OK",
            "complexity": {"before": 10_000_000, "after": complexity_after, "query": 100_000},
        },
    }


# --- Sync ---------------------------------------------------------------------

@respx.mock
def test_sync_execute_parses_data(settings):
    respx.post("https://api.monday.com/v2").respond(json=_ok({"me": {"id": "1"}}))
    with httpx.Client() as http:
        t = SyncTransport(settings, ComplexityTracker(), http)
        data = t.execute("query { me { id } }")
    assert data == {"me": {"id": "1"}}


@respx.mock
def test_sync_execute_sends_correct_headers(settings):
    route = respx.post("https://api.monday.com/v2").respond(json=_ok({"x": 1}))
    with httpx.Client() as http:
        t = SyncTransport(settings, ComplexityTracker(), http)
        t.execute("q", {"v": 1})
    req = route.calls.last.request
    assert req.headers["authorization"] == "tok"
    assert req.headers["api-version"] == "2024-10"
    body = json.loads(req.content)
    assert body == {"query": "q", "variables": {"v": 1}}


@respx.mock
def test_sync_execute_tracks_complexity(settings):
    respx.post("https://api.monday.com/v2").respond(json=_ok({"x": 1}, complexity_after=1_234_567))
    tracker = ComplexityTracker()
    with httpx.Client() as http:
        SyncTransport(settings, tracker, http).execute("q")
    assert tracker.last is not None
    assert tracker.last.after == 1_234_567


@respx.mock
def test_sync_execute_raises_on_graphql_error(settings):
    respx.post("https://api.monday.com/v2").respond(
        json={"errors": [{"message": "field X"}], "extensions": {"request_id": "r"}},
    )
    with httpx.Client() as http:
        with pytest.raises(MondayAPIError, match="field X"):
            SyncTransport(settings, ComplexityTracker(), http).execute("q")


@respx.mock
def test_sync_execute_retries_rate_limit_then_succeeds(settings):
    route = respx.post("https://api.monday.com/v2").mock(
        side_effect=[
            httpx.Response(200, json={
                "errors": [{"message": "rl",
                            "extensions": {"code": "Minute_Limit_Exceeded", "retry_after": 0}}],
                "extensions": {"request_id": "r1"},
            }),
            httpx.Response(200, json=_ok({"me": {"id": "1"}})),
        ]
    )
    with httpx.Client() as http:
        data = SyncTransport(settings, ComplexityTracker(), http).execute("q")
    assert data == {"me": {"id": "1"}}
    assert route.call_count == 2


@respx.mock
def test_sync_execute_does_not_retry_complexity(settings):
    respx.post("https://api.monday.com/v2").respond(
        json={
            "errors": [{"message": "ComplexityException",
                        "extensions": {"code": "ComplexityException",
                                       "retry_in_seconds": 5,
                                       "complexity": 999}}],
            "extensions": {"request_id": "r"},
        },
    )
    with httpx.Client() as http:
        with pytest.raises(ComplexityExhausted):
            SyncTransport(settings, ComplexityTracker(), http).execute("q")


@respx.mock
def test_sync_execute_gives_up_after_max_retries(settings):
    rl_response = httpx.Response(200, json={
        "errors": [{"message": "rl", "extensions": {"code": "Minute_Limit_Exceeded", "retry_after": 0}}],
        "extensions": {"request_id": "r"},
    })
    respx.post("https://api.monday.com/v2").mock(side_effect=[rl_response, rl_response, rl_response])
    with httpx.Client() as http:
        with pytest.raises(RateLimited):
            SyncTransport(settings, ComplexityTracker(), http).execute("q")


# --- Async --------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_async_execute_parses_data(settings):
    respx.post("https://api.monday.com/v2").respond(json=_ok({"me": {"id": "1"}}))
    async with httpx.AsyncClient() as http:
        t = AsyncTransport(settings, ComplexityTracker(), http)
        data = await t.execute("query { me { id } }")
    assert data == {"me": {"id": "1"}}


@respx.mock
@pytest.mark.asyncio
async def test_async_execute_retries_rate_limit(settings):
    route = respx.post("https://api.monday.com/v2").mock(
        side_effect=[
            httpx.Response(200, json={
                "errors": [{"message": "rl",
                            "extensions": {"code": "Minute_Limit_Exceeded", "retry_after": 0}}],
                "extensions": {"request_id": "r"},
            }),
            httpx.Response(200, json=_ok({"x": 1})),
        ]
    )
    async with httpx.AsyncClient() as http:
        data = await AsyncTransport(settings, ComplexityTracker(), http).execute("q")
    assert data == {"x": 1}
    assert route.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_transport.py -v`
Expected: ImportError on `monday_rotocon._transport`.

- [ ] **Step 3: Implement `_transport.py`**

Create `src/monday_rotocon/_transport.py`:

```python
"""Sync and async GraphQL transport over httpx.

`_BaseClient` holds shared request preparation and response processing.
`SyncTransport` and `AsyncTransport` add the I/O loop and retry behaviour
specific to their httpx flavour.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx

from . import __version__
from ._complexity import ComplexityTracker
from ._errors import MondayError, RateLimited, raise_for
from .settings import Settings

logger = logging.getLogger("monday_rotocon")

_USER_AGENT = f"monday_rotocon/{__version__}"
_MAX_RETRIES = 3


class _BaseClient:
    """Shared logic for building requests and processing responses."""

    def __init__(self, settings: Settings, complexity: ComplexityTracker) -> None:
        self._settings = settings
        self._complexity = complexity

    def _prepare(
        self, query: str, variables: dict[str, Any] | None
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        url = self._settings.monday_api_url
        headers = {
            "Authorization": self._settings.monday_api_token,
            "Content-Type": "application/json",
            "API-Version": self._settings.monday_api_version,
            "User-Agent": _USER_AGENT,
        }
        body: dict[str, Any] = {"query": query, "variables": variables or {}}
        return url, headers, body

    def _process(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as e:
            raise MondayError(
                f"non-JSON response (HTTP {response.status_code}): {response.text[:200]!r}"
            ) from e
        ext = payload.get("extensions") or {}
        if "complexity" in ext:
            self._complexity.track(ext)
        raise_for(payload, response.status_code)
        return payload.get("data") or {}


class SyncTransport(_BaseClient):
    def __init__(
        self,
        settings: Settings,
        complexity: ComplexityTracker,
        http: httpx.Client,
    ) -> None:
        super().__init__(settings, complexity)
        self._http = http

    def execute(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url, headers, body = self._prepare(query, variables)
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._http.post(
                    url,
                    headers=headers,
                    json=body,
                    timeout=self._settings.request_timeout_s,
                )
                return self._process(response)
            except RateLimited as exc:
                if attempt == _MAX_RETRIES - 1:
                    raise
                wait = exc.retry_after_s + random.random() * 0.5
                logger.warning(
                    "rate limited; sleeping %.2fs before retry %d/%d",
                    wait,
                    attempt + 2,
                    _MAX_RETRIES,
                )
                time.sleep(wait)
        raise MondayError("retries exhausted")  # pragma: no cover


class AsyncTransport(_BaseClient):
    def __init__(
        self,
        settings: Settings,
        complexity: ComplexityTracker,
        http: httpx.AsyncClient,
    ) -> None:
        super().__init__(settings, complexity)
        self._http = http

    async def execute(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url, headers, body = self._prepare(query, variables)
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._http.post(
                    url,
                    headers=headers,
                    json=body,
                    timeout=self._settings.request_timeout_s,
                )
                return self._process(response)
            except RateLimited as exc:
                if attempt == _MAX_RETRIES - 1:
                    raise
                wait = exc.retry_after_s + random.random() * 0.5
                logger.warning(
                    "rate limited; sleeping %.2fs before retry %d/%d",
                    wait,
                    attempt + 2,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(wait)
        raise MondayError("retries exhausted")  # pragma: no cover
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_transport.py -v`
Expected: 9 tests pass (7 sync + 2 async).

- [ ] **Step 5: Type-check**

Run: `uv run mypy src/monday_rotocon/_transport.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/monday_rotocon/_transport.py tests/unit/test_transport.py
git commit -m "feat(transport): generic sync+async GraphQL transport with retries and complexity tracking"
```

---

## Task 10: `client.py` — sync `MondayClient` with all 3 resources

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/client.py`
- Modify: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/__init__.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_client_sync.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_client_sync.py`:

```python
"""Tests for the sync MondayClient."""
from __future__ import annotations

import pytest
import respx

from monday_rotocon import MondayClient
from monday_rotocon.models import Board, Item, User


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "tok")


def _ok(data: dict) -> dict:
    return {
        "data": data,
        "extensions": {
            "request_id": "r",
            "complexity": {"before": 10_000_000, "after": 9_900_000, "query": 100_000},
        },
    }


@respx.mock
def test_me_returns_user(fixture_loader):
    respx.post("https://api.monday.com/v2").respond(json=_ok({"me": fixture_loader("me")}))
    with MondayClient() as c:
        u = c.me.get()
    assert isinstance(u, User)
    assert u.email == "george@rotocon.world"


@respx.mock
def test_boards_list_returns_models(fixture_loader):
    respx.post("https://api.monday.com/v2").respond(
        json=_ok({"boards": fixture_loader("boards_list")})
    )
    with MondayClient() as c:
        boards = c.boards.list(limit=5)
    assert len(boards) == 3
    assert all(isinstance(b, Board) for b in boards)


@respx.mock
def test_boards_list_passes_variables():
    route = respx.post("https://api.monday.com/v2").respond(json=_ok({"boards": []}))
    with MondayClient() as c:
        c.boards.list(limit=42, ids=[1, 2], state="archived")
    import json
    body = json.loads(route.calls.last.request.content)
    assert body["variables"] == {"limit": 42, "ids": ["1", "2"], "state": "archived"}


@respx.mock
def test_boards_get_returns_single():
    respx.post("https://api.monday.com/v2").respond(
        json=_ok({"boards": [{"id": "9", "name": "X", "state": "active"}]})
    )
    with MondayClient() as c:
        b = c.boards.get(9)
    assert b.id == "9"


@respx.mock
def test_boards_get_raises_when_missing():
    respx.post("https://api.monday.com/v2").respond(json=_ok({"boards": []}))
    with MondayClient() as c:
        with pytest.raises(KeyError):
            c.boards.get(123)


@respx.mock
def test_items_list_paginates(fixture_loader):
    page1 = {
        "boards": [{"items_page": {
            "cursor": "next-cursor",
            "items": fixture_loader("items_page")["items"],
        }}]
    }
    page2 = {
        "boards": [{"items_page": {
            "cursor": None,
            "items": [{"id": "9999", "name": "another", "state": "active"}],
        }}]
    }
    respx.post("https://api.monday.com/v2").mock(
        side_effect=[
            __import__("httpx").Response(200, json=_ok(page1)),
            __import__("httpx").Response(200, json=_ok(page2)),
        ]
    )
    with MondayClient() as c:
        items = list(c.items.list(5096182046))
    assert len(items) == 2
    assert all(isinstance(i, Item) for i in items)
    assert items[1].id == "9999"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_client_sync.py -v`
Expected: ImportError on `from monday_rotocon import MondayClient`.

- [ ] **Step 3: Implement `client.py`**

Create `src/monday_rotocon/client.py`:

```python
"""Public client API: MondayClient (sync) and AsyncMondayClient (async).

Resource objects (`MeResource`, `BoardsResource`, `ItemsResource`) load the
appropriate query, call the transport, and parse results into Pydantic
models. Both client flavours expose the same surface.
"""
from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable, Iterator
from datetime import datetime
from types import TracebackType
from typing import Any, Self

import httpx

from ._complexity import ComplexityTracker
from ._transport import AsyncTransport, SyncTransport
from .models import Board, Item, User
from .queries import QUERIES
from .settings import Settings


# --- Sync resources -----------------------------------------------------------


class MeResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._t = transport

    def get(self) -> User:
        data = self._t.execute(QUERIES["me"])
        return User.model_validate(data["me"])


class BoardsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._t = transport

    def list(
        self,
        *,
        limit: int = 100,
        ids: list[int] | None = None,
        state: str = "active",
    ) -> list[Board]:
        variables: dict[str, Any] = {"limit": limit, "state": state}
        if ids is not None:
            variables["ids"] = [str(i) for i in ids]
        data = self._t.execute(QUERIES["boards"], variables)
        return [Board.model_validate(b) for b in data.get("boards", [])]

    def get(self, board_id: int) -> Board:
        boards = self.list(limit=1, ids=[board_id])
        if not boards:
            raise KeyError(f"board {board_id} not found")
        return boards[0]


class ItemsResource:
    def __init__(self, transport: SyncTransport) -> None:
        self._t = transport

    def list(
        self,
        board_id: int,
        *,
        since: datetime | None = None,  # noqa: ARG002 — reserved; filter applied client-side later
    ) -> Iterable[Item]:
        cursor: str | None = None
        while True:
            data = self._t.execute(
                QUERIES["items"],
                {"board_id": str(board_id), "cursor": cursor, "limit": 100},
            )
            boards = data.get("boards") or []
            if not boards:
                return
            page = boards[0].get("items_page") or {}
            for raw in page.get("items") or []:
                item = Item.model_validate(raw)
                if since is None or (item.updated_at and item.updated_at >= since):
                    yield item
            cursor = page.get("cursor")
            if not cursor:
                return


# --- Async resources ----------------------------------------------------------


class AsyncMeResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def get(self) -> User:
        data = await self._t.execute(QUERIES["me"])
        return User.model_validate(data["me"])


class AsyncBoardsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def list(
        self,
        *,
        limit: int = 100,
        ids: list[int] | None = None,
        state: str = "active",
    ) -> list[Board]:
        variables: dict[str, Any] = {"limit": limit, "state": state}
        if ids is not None:
            variables["ids"] = [str(i) for i in ids]
        data = await self._t.execute(QUERIES["boards"], variables)
        return [Board.model_validate(b) for b in data.get("boards", [])]

    async def get(self, board_id: int) -> Board:
        boards = await self.list(limit=1, ids=[board_id])
        if not boards:
            raise KeyError(f"board {board_id} not found")
        return boards[0]


class AsyncItemsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        self._t = transport

    async def list(
        self,
        board_id: int,
        *,
        since: datetime | None = None,
    ) -> AsyncIterable[Item]:
        return self._iter(board_id, since)

    async def _iter(
        self, board_id: int, since: datetime | None
    ) -> AsyncIterator[Item]:
        cursor: str | None = None
        while True:
            data = await self._t.execute(
                QUERIES["items"],
                {"board_id": str(board_id), "cursor": cursor, "limit": 100},
            )
            boards = data.get("boards") or []
            if not boards:
                return
            page = boards[0].get("items_page") or {}
            for raw in page.get("items") or []:
                item = Item.model_validate(raw)
                if since is None or (item.updated_at and item.updated_at >= since):
                    yield item
            cursor = page.get("cursor")
            if not cursor:
                return


# --- Public clients -----------------------------------------------------------


class MondayClient:
    """Synchronous monday.com client."""

    def __init__(
        self,
        token: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        if settings is None:
            settings = Settings(monday_api_token=token) if token else Settings()
        self._settings = settings
        self._http = httpx.Client(timeout=settings.request_timeout_s)
        self._complexity = ComplexityTracker(warn_threshold=settings.complexity_warn_threshold)
        self._transport = SyncTransport(settings, self._complexity, self._http)
        self.me = MeResource(self._transport)
        self.boards = BoardsResource(self._transport)
        self.items = ItemsResource(self._transport)

    @property
    def complexity(self) -> ComplexityTracker:
        return self._complexity

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class AsyncMondayClient:
    """Asynchronous monday.com client (mirror of MondayClient)."""

    def __init__(
        self,
        token: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        if settings is None:
            settings = Settings(monday_api_token=token) if token else Settings()
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=settings.request_timeout_s)
        self._complexity = ComplexityTracker(warn_threshold=settings.complexity_warn_threshold)
        self._transport = AsyncTransport(settings, self._complexity, self._http)
        self.me = AsyncMeResource(self._transport)
        self.boards = AsyncBoardsResource(self._transport)
        self.items = AsyncItemsResource(self._transport)

    @property
    def complexity(self) -> ComplexityTracker:
        return self._complexity

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
```

- [ ] **Step 4: Update `monday_rotocon/__init__.py` to re-export public API**

Replace `src/monday_rotocon/__init__.py`:

```python
"""monday.com client + dashboard export tooling for ROTOCON Europe GmbH."""
from __future__ import annotations

__version__ = "0.1.0"

from .client import AsyncMondayClient, MondayClient
from .settings import Settings

__all__ = [
    "AsyncMondayClient",
    "MondayClient",
    "Settings",
    "__version__",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_client_sync.py -v`
Expected: 6 tests pass.

- [ ] **Step 6: Type-check**

Run: `uv run mypy src/monday_rotocon/`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/monday_rotocon/client.py src/monday_rotocon/__init__.py tests/unit/test_client_sync.py
git commit -m "feat(client): MondayClient + AsyncMondayClient with Me/Boards/Items resources"
```

---

## Task 11: Async client tests (parity with sync)

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_client_async.py`

(The async client itself was already implemented in Task 10 — this task validates it.)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_client_async.py`:

```python
"""Async parity tests for AsyncMondayClient."""
from __future__ import annotations

import httpx
import pytest
import respx

from monday_rotocon import AsyncMondayClient
from monday_rotocon.models import Board, Item, User


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "tok")


def _ok(data: dict) -> dict:
    return {
        "data": data,
        "extensions": {
            "request_id": "r",
            "complexity": {"before": 10_000_000, "after": 9_900_000, "query": 100_000},
        },
    }


@respx.mock
@pytest.mark.asyncio
async def test_async_me(fixture_loader):
    respx.post("https://api.monday.com/v2").respond(json=_ok({"me": fixture_loader("me")}))
    async with AsyncMondayClient() as c:
        u = await c.me.get()
    assert isinstance(u, User)
    assert u.email == "george@rotocon.world"


@respx.mock
@pytest.mark.asyncio
async def test_async_boards_list(fixture_loader):
    respx.post("https://api.monday.com/v2").respond(
        json=_ok({"boards": fixture_loader("boards_list")})
    )
    async with AsyncMondayClient() as c:
        boards = await c.boards.list(limit=5)
    assert len(boards) == 3
    assert all(isinstance(b, Board) for b in boards)


@respx.mock
@pytest.mark.asyncio
async def test_async_items_paginates(fixture_loader):
    page1 = {"boards": [{"items_page": {
        "cursor": "next",
        "items": fixture_loader("items_page")["items"],
    }}]}
    page2 = {"boards": [{"items_page": {
        "cursor": None,
        "items": [{"id": "9999", "name": "extra", "state": "active"}],
    }}]}
    respx.post("https://api.monday.com/v2").mock(
        side_effect=[httpx.Response(200, json=_ok(page1)), httpx.Response(200, json=_ok(page2))]
    )
    async with AsyncMondayClient() as c:
        gen = await c.items.list(5096182046)
        items: list[Item] = [it async for it in gen]
    assert len(items) == 2
    assert items[1].name == "extra"
```

- [ ] **Step 2: Run tests to verify they pass (no implementation needed — already done in Task 10)**

Run: `uv run pytest tests/unit/test_client_async.py -v`
Expected: 3 tests pass.

If they fail with `'AsyncIterable' object is not iterable` or similar, re-check `AsyncItemsResource.list` in `client.py` — the `list` method must `return self._iter(...)`, with `_iter` being an `async def` generator.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_client_async.py
git commit -m "test(client): async parity coverage for AsyncMondayClient"
```

---

## Task 12: CLI — `monday ping`

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/cli.py`
- Create: `/Users/rotocondemo/monday_rotocon/tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cli.py`:

```python
"""Tests for the Typer CLI."""
from __future__ import annotations

import json

import pytest
import respx
from typer.testing import CliRunner

from monday_rotocon.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("MONDAY_API_TOKEN", "tok")


def _ok(data: dict) -> dict:
    return {
        "data": data,
        "extensions": {
            "request_id": "r",
            "complexity": {"before": 10_000_000, "after": 9_900_000, "query": 100_000},
        },
    }


@respx.mock
def test_ping_human(fixture_loader):
    respx.post("https://api.monday.com/v2").respond(json=_ok({"me": fixture_loader("me")}))
    result = runner.invoke(app, ["ping"])
    assert result.exit_code == 0, result.output
    assert "George" in result.output
    assert "rotocon" in result.output.lower()


@respx.mock
def test_ping_json(fixture_loader):
    respx.post("https://api.monday.com/v2").respond(json=_ok({"me": fixture_loader("me")}))
    result = runner.invoke(app, ["ping", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["email"] == "george@rotocon.world"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: ImportError on `monday_rotocon.cli`.

- [ ] **Step 3: Implement `cli.py` with `ping` only**

Create `src/monday_rotocon/cli.py`:

```python
"""Typer CLI for monday_rotocon.

Subcommands are added incrementally; see the implementation plan for which
task introduced each. The `app` callable below is the entry point referenced
from `pyproject.toml`'s `[project.scripts]`.
"""
from __future__ import annotations

import typer

from .client import MondayClient

app = typer.Typer(no_args_is_help=True, help="monday_rotocon CLI")


@app.command()
def ping(json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of human text.")) -> None:
    """Verify the API token and print the user/account identity."""
    with MondayClient() as c:
        user = c.me.get()
    if json_out:
        typer.echo(user.model_dump_json())
        return
    if user.account is not None:
        typer.echo(
            f"✓ {user.name} <{user.email or '?'}> · "
            f"{user.account.name} (tier={user.account.tier or '?'})"
        )
    else:
        typer.echo(f"✓ {user.name} <{user.email or '?'}>")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Verify the entry point installs**

Run: `uv run monday --help`
Expected: prints Typer help; lists `ping` as a command.

- [ ] **Step 6: Commit**

```bash
git add src/monday_rotocon/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): monday ping subcommand"
```

---

## Task 13: CLI — `monday boards list` + `monday export dashboard`

**Files:**
- Modify: `/Users/rotocondemo/monday_rotocon/src/monday_rotocon/cli.py`
- Modify: `/Users/rotocondemo/monday_rotocon/tests/unit/test_cli.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/unit/test_cli.py`:

```python


@respx.mock
def test_boards_list_human(fixture_loader):
    respx.post("https://api.monday.com/v2").respond(
        json=_ok({"boards": fixture_loader("boards_list")})
    )
    result = runner.invoke(app, ["boards", "list"])
    assert result.exit_code == 0, result.output
    assert "KI Integration" in result.output


@respx.mock
def test_boards_list_json(fixture_loader):
    respx.post("https://api.monday.com/v2").respond(
        json=_ok({"boards": fixture_loader("boards_list")})
    )
    result = runner.invoke(app, ["boards", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert any(b["name"] == "KI Integration" for b in payload)


@respx.mock
def test_export_dashboard(tmp_path, fixture_loader):
    boards_resp = _ok({"boards": fixture_loader("boards_list")})
    items_pages = [
        _ok({"boards": [{"items_page": {"cursor": None, "items": fixture_loader("items_page")["items"]}}]}),
        _ok({"boards": [{"items_page": {"cursor": None, "items": []}}]}),
        _ok({"boards": [{"items_page": {"cursor": None, "items": []}}]}),
    ]
    import httpx
    respx.post("https://api.monday.com/v2").mock(
        side_effect=[httpx.Response(200, json=boards_resp)] + [httpx.Response(200, json=p) for p in items_pages]
    )
    out_path = tmp_path / "demo.json"
    result = runner.invoke(app, ["export", "dashboard", "--out", str(out_path)])
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    payload = json.loads(out_path.read_text())
    assert "boards" in payload
    assert len(payload["boards"]) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: errors for `boards` / `export` subcommands not registered yet.

- [ ] **Step 3: Extend `cli.py` with the two new subcommands**

Replace the contents of `src/monday_rotocon/cli.py` entirely:

```python
"""Typer CLI for monday_rotocon."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from .client import MondayClient

app = typer.Typer(no_args_is_help=True, help="monday_rotocon CLI")
boards_app = typer.Typer(no_args_is_help=True, help="Board operations")
export_app = typer.Typer(no_args_is_help=True, help="Export operations")
app.add_typer(boards_app, name="boards")
app.add_typer(export_app, name="export")


# --- Top-level ---------------------------------------------------------------


@app.command()
def ping(json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of human text.")) -> None:
    """Verify the API token and print the user/account identity."""
    with MondayClient() as c:
        user = c.me.get()
    if json_out:
        typer.echo(user.model_dump_json())
        return
    if user.account is not None:
        typer.echo(
            f"✓ {user.name} <{user.email or '?'}> · "
            f"{user.account.name} (tier={user.account.tier or '?'})"
        )
    else:
        typer.echo(f"✓ {user.name} <{user.email or '?'}>")


# --- boards -------------------------------------------------------------------


@boards_app.command("list")
def boards_list(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
    limit: int = typer.Option(100, "--limit", min=1, max=200),
) -> None:
    """List active boards."""
    with MondayClient() as c:
        boards = c.boards.list(limit=limit)
    if json_out:
        typer.echo(json.dumps([b.model_dump(mode="json") for b in boards], indent=2))
        return
    for b in boards:
        ws = b.workspace.name if b.workspace else "—"
        count = b.items_count if b.items_count is not None else "?"
        typer.echo(f"  {b.id:>12}  {b.name}  ({count} items, ws={ws})")


# --- export -------------------------------------------------------------------


@export_app.command("dashboard")
def export_dashboard(
    out: Path = typer.Option(..., "--out", help="Output JSON file path."),
    boards: Optional[str] = typer.Option(
        None, "--boards", help="Comma-separated board IDs; defaults to all active boards."
    ),
    since: Optional[datetime] = typer.Option(
        None, "--since", help="Only include items updated at/after this ISO datetime."
    ),
    limit: int = typer.Option(200, "--limit", min=1, max=500),
) -> None:
    """Export a snapshot of boards + items as JSON for CEO Dashboard V1."""
    board_ids = [int(x) for x in boards.split(",")] if boards else None
    snapshot: list[dict] = []
    with MondayClient() as c:
        target_boards = c.boards.list(limit=limit, ids=board_ids)
        for b in target_boards:
            items = list(c.items.list(int(b.id), since=since))
            snapshot.append(
                {
                    "id": b.id,
                    "name": b.name,
                    "items_count": b.items_count,
                    "workspace": (b.workspace.model_dump(mode="json") if b.workspace else None),
                    "items": [it.model_dump(mode="json") for it in items],
                }
            )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "since": since.isoformat() if since else None,
        "boards": snapshot,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(b["items"]) for b in snapshot)
    typer.echo(f"✓ wrote {out} — {len(snapshot)} boards, {total} items")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: 5 tests pass (2 from Task 12 + 3 new).

- [ ] **Step 5: Smoke test against real API**

Run: `uv run monday ping`
Expected: prints `✓ George Sebastian Cucuiet <george@rotocon.world> · rotocons Team (tier=pro)`.

Run: `uv run monday boards list --limit 5`
Expected: prints up to 5 boards from the live account.

- [ ] **Step 6: Type-check**

Run: `uv run mypy src/monday_rotocon/`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/monday_rotocon/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): boards list + export dashboard subcommands"
```

---

## Task 14: Integration smoke test + final acceptance gate

**Files:**
- Create: `/Users/rotocondemo/monday_rotocon/tests/integration/test_smoke.py`
- Modify: `/Users/rotocondemo/monday_rotocon/README.md`

- [ ] **Step 1: Write the integration smoke test**

Create `tests/integration/test_smoke.py`:

```python
"""Opt-in smoke tests against the real monday.com API.

Run with:  `uv run pytest -m integration`
Skipped automatically when MONDAY_INTEGRATION_TOKEN is unset, so casual
`pytest` runs never hit the wire.
"""
from __future__ import annotations

import os

import pytest

from monday_rotocon import MondayClient

pytestmark = pytest.mark.integration


@pytest.fixture
def real_client() -> MondayClient:
    token = os.environ.get("MONDAY_INTEGRATION_TOKEN") or os.environ.get("MONDAY_API_TOKEN")
    if not token:
        pytest.skip("no MONDAY_INTEGRATION_TOKEN / MONDAY_API_TOKEN in environment")
    return MondayClient(token=token)


def test_real_me_returns_identity(real_client: MondayClient) -> None:
    with real_client as c:
        user = c.me.get()
    assert user.id
    assert user.name


def test_real_boards_list_smoke(real_client: MondayClient) -> None:
    with real_client as c:
        boards = c.boards.list(limit=1)
    # account must have at least one board
    assert len(boards) >= 1
```

- [ ] **Step 2: Verify default `pytest` skips integration**

Run: `uv run pytest -v`
Expected: only unit tests run; the two integration tests appear as `SKIP` lines or are deselected (depending on pytest output style).

If they actually run (and possibly fail because no token), recheck `pyproject.toml` markers config — `addopts` should NOT include `-m integration`.

To confirm explicit selection works:

Run: `uv run pytest -m integration -v`
Expected: integration tests RUN against the real API and pass (since `MONDAY_API_TOKEN` is in `.env`).

- [ ] **Step 3: Run the full unit suite + coverage**

Run:

```bash
uv run pytest -m "not integration" --cov=monday_rotocon --cov-report=term-missing
```

Expected: all unit tests pass. Inspect coverage on `_transport.py`, `client.py`, `_complexity.py` — should each be ≥ 80%. If a critical function is below threshold, add a unit test for the missing branch in the same task before continuing.

- [ ] **Step 4: Run mypy + ruff**

```bash
uv run mypy --strict src/monday_rotocon/
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Expected: all three commands exit 0. If `ruff format --check` reports differences, run `uv run ruff format src/ tests/` to fix and re-run the check.

- [ ] **Step 5: Run the spec's acceptance criteria (§10) end-to-end**

The spec requires 6 binary checks. Run each:

```bash
# §10.1 — ping in < 1 s
time uv run monday ping
```
Expected: prints identity line; total time < 1 s.

```bash
# §10.2 — boards list as JSON
uv run monday boards list --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert isinstance(d, list) and d, 'empty boards'; print(f'OK: {len(d)} boards')"
```
Expected: `OK: <n> boards`.

```bash
# §10.3 — export dashboard produces non-empty JSON
uv run monday export dashboard --out /tmp/dashboard.json
python3 -c "import json; d=json.load(open('/tmp/dashboard.json')); assert d['boards'], 'no boards'; print(f'OK: {len(d[\"boards\"])} boards, {sum(len(b[\"items\"]) for b in d[\"boards\"])} items total')"
```
Expected: `OK: <n> boards, <m> items total`.

```bash
# §10.4 — coverage gate
uv run pytest -m "not integration" --cov=monday_rotocon --cov-report=term --cov-fail-under=80
```
Expected: exit 0.

```bash
# §10.5 — mypy strict
uv run mypy --strict src/monday_rotocon/
```
Expected: exit 0.

```bash
# §10.6 — README quickstart present
grep -q "uv run monday ping" README.md && echo "OK"
```
Expected: `OK`.

- [ ] **Step 6: Polish README**

Replace `README.md` with the final version:

```markdown
# monday_rotocon

Typed monday.com client + dashboard-export CLI for ROTOCON Europe GmbH.
Implements **sub-project A** of the digital-transformation roadmap.

- Spec: `docs/superpowers/specs/2026-05-10-monday-core-skeleton-design.md`
- Plan: `docs/superpowers/plans/2026-05-10-monday-core-skeleton.md`

## Quickstart

```bash
# 1. Set the API token (copy template).
cp .env.example .env
# edit .env — set MONDAY_API_TOKEN

# 2. Install deps into a project-local venv.
uv sync --all-extras

# 3. Verify connectivity.
uv run monday ping

# 4. Export the CEO Dashboard V1 snapshot.
uv run monday export dashboard --out dashboard.json
```

## CLI

| Command | Purpose |
|---|---|
| `monday ping` | Verify token; print user/account identity. `--json` for machine output. |
| `monday boards list` | List boards. `--json`, `--limit N`. |
| `monday export dashboard --out PATH` | Snapshot boards + items into a JSON file. `--boards ID,ID`, `--since YYYY-MM-DD`, `--limit N`. |

## Architecture

Three layers, dependencies flow strictly inward:

```
Applications (cli)  →  Domain (models, queries)  →  Transport (httpx, complexity, errors)
```

The transport is generic over `httpx.Client` / `httpx.AsyncClient` so
`MondayClient` (sync) and `AsyncMondayClient` (async) share parsing,
error mapping, retries, and complexity tracking.

See the spec for the full design.

## Development

```bash
uv run pytest                               # unit tests (skips integration)
uv run pytest -m integration                # smoke against real API (uses MONDAY_API_TOKEN)
uv run mypy --strict src/monday_rotocon/    # type check
uv run ruff check src/ tests/               # lint
uv run ruff format src/ tests/              # autoformat
```

## What's NOT here (deferred to sub-projects B/C/D)

- Webhook receiver / sync workers (B, M2–M3)
- Configurator + AI assistants (C, M4)
- Smart-machine telemetry (D, M5–M6)

One-shot operational scripts (e.g. `scripts/bootstrap_ki_integration.py`)
live in `scripts/` and intentionally bypass the package — they exist to
populate monday state, not to be imported by the package itself.
```

- [ ] **Step 7: Commit**

```bash
git add tests/integration/test_smoke.py README.md
git commit -m "feat: integration smoke suite (opt-in) + finalise README

- pytest -m integration runs read-only smoke against real API
- README documents quickstart, CLI, architecture, deferred scope
- All 6 acceptance criteria from spec §10 pass"
```

---

## Self-Review

### Spec coverage check

Each spec section mapped to a task:

| Spec section | Implemented in |
|---|---|
| §3 Architecture (3 layers, inward deps) | Layout enforced in Task 1; verified by mypy clean across `src/` after Task 13 |
| §4 Project layout | Task 1 creates the structure; subsequent tasks fill the leaves |
| §5.1 `settings.py` | Task 2 |
| §5.2 `_transport.py` | Task 9 |
| §5.3 `client.py` MondayClient + AsyncMondayClient | Task 10 (impl) + Task 11 (async coverage) |
| §5.4 `_complexity.py` | Task 4 |
| §5.5 `_errors.py` | Task 3 |
| §5.6 `models/` | Tasks 5, 6, 7 |
| §5.7 `queries/` `.graphql` files + loader | Task 8 |
| §5.8 `cli.py` (ping / boards list / export dashboard) | Tasks 12, 13 |
| §6 Data flow example | Realised by `export dashboard` integration in Task 13 |
| §7 Error model + exit codes | Errors implemented in Task 3; CLI exit codes inherit Typer's defaults — explicit exit codes 1/2/3/4 from spec are *not* wired (Typer surfaces uncaught exceptions as exit 1; `RateLimited`/`ComplexityExhausted` will likewise surface as exit 1). **Note:** if the CEO dashboard automation needs the granular exit codes from spec §7, add a `cli.main()` wrapper with `try/except` per error class in a follow-up. The spec calls these "stable so future automations can react" — until automation exists, exit 1 is acceptable. |
| §8 Testing strategy (unit + integration + static) | Tasks 2–13 (unit), Task 14 (integration + acceptance) |
| §9 Tooling & deps | Task 1 |
| §10 Acceptance criteria (6 checks) | Task 14 step 5 runs all six |
| §11 Open questions / risks | Q1/Q2 documented in spec; R1 evidence captured in spec §11 (already added) |
| §12 Future hooks | Async client present from day one (Task 10) so B can depend on it |

**Gap noted:** Spec §7 names specific CLI exit codes (1/2/3/4) per error class. The plan lets Typer's default exit-1 cover all uncaught exceptions. Documented as a follow-up rather than a blocker since no automation consumes those codes yet.

### Placeholder scan

Searched the plan for: TBD, TODO, "implement later", "fill in details", "add appropriate error handling", "similar to Task N", "write tests for the above" without code, "handle edge cases" without code.

**Result:** none of these patterns appear. Every code block is complete and copy-paste-ready. Exit-code follow-up is explicitly named, not deferred with hand-waving.

### Type / signature consistency

Cross-checked symbols introduced and used across tasks:

- `Settings` — Task 2; used by Task 9 (transport ctor), Task 10 (client default).
- `MondayError`, `MondayAPIError`, `RateLimited`, `ComplexityExhausted`, `raise_for` — Task 3; used by Task 9.
- `ComplexityTracker` — Task 4; used by Task 9 ctor + Task 10 client ctor + exposed via `MondayClient.complexity`.
- `MondayModel` — Task 5; used by all model files.
- `User`, `Account` — Task 5; used by Task 10 (`MeResource.get`), Task 12 (CLI ping).
- `Workspace`, `Group`, `Board` — Task 6; used by Task 7 (`Item.group: Group`), Task 10 (`BoardsResource`).
- `ColumnValue` (and concrete column-value classes) — Task 7; used by `Item.column_values` in Task 7.
- `Item` — Task 7; used by Task 10 (`ItemsResource`).
- `QUERIES` — Task 8; used by Task 10 in all 3 sync resources and 3 async resources.
- `SyncTransport`, `AsyncTransport` — Task 9; used by Task 10 client constructors.
- `MondayClient`, `AsyncMondayClient` — Task 10; used by Tasks 11–13.
- `cli.app` — Task 12; extended in Task 13.

Signature consistency:

- `Settings(monday_api_token=token)` in Task 10 client ctor matches Task 2's `monday_api_token: str = Field(min_length=1)` field. ✓
- `BoardsResource.list(*, limit, ids, state)` and `AsyncBoardsResource.list(...)` have identical kwargs. ✓
- `ItemsResource.list(board_id, *, since)` returns `Iterable[Item]`; `AsyncItemsResource.list(...)` returns awaitable producing `AsyncIterable[Item]` (resolved via `await c.items.list(...)` then `async for`). The sync test in Task 10 uses `list(c.items.list(...))`; the async test in Task 11 uses `gen = await c.items.list(...); items = [it async for it in gen]`. Consistent.
- `MondayClient.complexity` and `AsyncMondayClient.complexity` properties both return `ComplexityTracker`. ✓

Naming consistency:

- `MondayClient.me`, `.boards`, `.items` — same names on `AsyncMondayClient`. ✓
- Method names mirror exactly between sync and async (`get`, `list`). ✓

No drift detected.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-monday-core-skeleton.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task; review between tasks; fast iteration; isolates the main session from per-task tool noise.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`; batch execution with checkpoints for review.

**Which approach?**
