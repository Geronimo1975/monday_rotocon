# Design — Sub-proiect A: `monday_core` + dashboard export CLI

| Field | Value |
|---|---|
| Date | 2026-05-10 |
| Author | George Sebastian Cucuiet (via Claude brainstorming) |
| Status | **APPROVED** (2026-05-10) |
| Supersedes | — |
| Implements | M1 of `Tasks/ROTOCON_Job_Description_6_Month_Roadmap_English[94].pdf` |

---

## 1. Context

ROTOCON Europe GmbH runs a 6-month digital-transformation program owned by the Head of Digital Transformation. The strategic source-of-truth lives in `Tasks/`:

- `ROTOCON_Job_Description_6_Month_Roadmap_English[94].pdf` — month-by-month roadmap (M1–M6), KPIs, weekly CEO reporting.
- `ROTOCON_Onboarding_DE.docx` — Day-1 onboarding, 4-week execution plan, target monday.com board layout, leitprinzipien.

The end-to-end target flow is:

```
Lead → Angebot (quote) → Auftrag (order) → Einkauf (purchase) → Produktion → Lieferung → Reporting
```

across **monday.com (CRM)**, **Quick & Easy ERP**, a **Configurator** (currently Excel, owned by Markus), and future **AI assistants**. This repo will progressively host the integration glue.

### Program decomposition (out of scope here, recorded for traceability)

| Sub-project | Scope | Roadmap month |
|---|---|---|
| **A** *(this spec)* | `monday_core` library + dashboard-export CLI | M1 |
| B | Webhook receiver + sync workers (Q&E ERP ↔ monday) | M2–M3 |
| C | Configurator replacement + AI quotation/reporting assistants | M4 |
| D | Smart-machine telemetry + predictive maintenance | M5–M6 |

B/C/D get their own spec → plan → implementation cycles when their month arrives.

## 2. Goals & non-goals

**Goals.** Sub-project A must deliver:

1. A typed, reusable monday.com client (sync + async) that every future sub-project can depend on without modification.
2. A CLI tool that exports monday board/item data into a structured format suitable for **CEO Dashboard V1** (an M1 deliverable).
3. A foundation that is *test-covered*, *type-checked*, and *observable* — so it scales to B/C/D without rewrites.

**Non-goals (deferred).**

- No HTTP server, no webhook receiving, no background workers (→ B).
- No database / persistence (the CLI is read-only and stateless).
- No mutations in the `monday_rotocon` package. The package is **read-only**; one-shot operational tooling that mutates monday state (e.g., bootstrapping boards, seeding items) lives in **`scripts/`** as standalone Python files using only stdlib. `scripts/` is *not* part of the package import path; consumers of `monday_rotocon` never see it. *Concrete example:* `scripts/bootstrap_ki_integration.py` was used on 2026-05-10 to create the KI Integration board — it shipped before the skeleton existed and intentionally bypasses it.
- No GraphQL schema code-generation (rejected during brainstorming as over-engineering at this stage; revisit if `monday_core` is ever published).
- No CI configuration (will be authored as a follow-up; not part of skeleton).
- No PyPI publishing.

## 3. Architecture

Three logical layers; dependencies flow strictly inward.

```
┌──────────────────────────────────────────────────────────────┐
│ Applications                                                  │
│   cli.py  (Typer)  — `monday ping | boards list | export ...`│
└──────────────────────┬───────────────────────────────────────┘
                       │ depends on
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Domain                                                        │
│   models/     (Pydantic v2, discriminated unions on column_values)
│   queries/    (.graphql files, loaded at import)              │
└──────────────────────┬───────────────────────────────────────┘
                       │ depends on
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Transport                                                     │
│   _transport.py  (generic _BaseClient[T] over httpx.Client/AsyncClient)
│   client.py      (MondayClient + AsyncMondayClient public API)
│   _complexity.py (budget tracker + WARNING < 10% remaining)   │
│   _errors.py     (MondayAPIError, RateLimited, ComplexityExhausted)
│   settings.py    (pydantic-settings: token, region, API version)
└──────────────────────────────────────────────────────────────┘
```

Cross-layer rules:

- CLI never imports `httpx` directly.
- Transport never imports `pydantic` (it returns parsed JSON `dict`); parsing into models happens in `client.py` (the boundary between transport and domain).
- Models never make I/O.

## 4. Project layout

```
/Users/rotocondemo/monday_rotocon/
├── pyproject.toml
├── README.md
├── .env                            # local; git-ignored
├── .env.example                    # committed; documents required vars
├── .gitignore                      # already exists
├── Tasks/                          # strategic source docs — unchanged
├── docs/
│   └── superpowers/specs/
├── scripts/
│   └── smoke_test.sh               # equivalent to the curl probe we ran
├── src/
│   └── monday_rotocon/
│       ├── __init__.py             # public re-exports + __version__
│       ├── py.typed                # PEP 561 marker
│       ├── settings.py
│       ├── _transport.py
│       ├── client.py
│       ├── _complexity.py
│       ├── _errors.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── _base.py
│       │   ├── account.py
│       │   ├── user.py
│       │   ├── board.py
│       │   ├── item.py
│       │   └── column_values.py
│       ├── queries/
│       │   ├── __init__.py         # loader
│       │   ├── me.graphql
│       │   ├── boards.graphql
│       │   └── items.graphql
│       └── cli.py
└── tests/
    ├── conftest.py
    ├── fixtures/                   # sanitized real-response JSON
    ├── unit/
    │   ├── test_client.py
    │   ├── test_models.py
    │   ├── test_complexity.py
    │   └── test_cli.py
    └── integration/
        └── test_smoke.py           # opt-in: `pytest -m integration`
```

**Why `src/`-layout:** prevents accidental imports from CWD before the package is installed; catches packaging mistakes (missing files in `pyproject.toml`) in local development rather than in CI / production.

## 5. Components

### 5.1 `settings.py` — configuration

Pydantic-Settings `BaseSettings` subclass. Reads from environment + `.env`. Fields:

| Field | Env var | Default | Notes |
|---|---|---|---|
| `monday_api_token` | `MONDAY_API_TOKEN` | required | JWT issued in monday account settings |
| `monday_api_version` | `MONDAY_API_VERSION` | `2024-10` | sent as `API-Version` header |
| `monday_region` | `MONDAY_REGION` | `euc1` | informational; API URL is fixed |
| `monday_api_url` | `MONDAY_API_URL` | `https://api.monday.com/v2` | escape hatch for proxies / tests |
| `request_timeout_s` | `MONDAY_REQUEST_TIMEOUT_S` | `30.0` | httpx timeout |
| `complexity_warn_threshold` | `MONDAY_COMPLEXITY_WARN` | `0.10` | log WARNING when remaining/total < threshold |

### 5.2 `_transport.py` — generic GraphQL transport

Internal-only. Defines `_BaseClient` generic over an underlying httpx client. Two thin subclasses live in `client.py`. The transport handles:

- POST `{ "query": ..., "variables": ... }` to `monday_api_url`.
- Sets `Authorization`, `Content-Type: application/json`, `API-Version`, `User-Agent: monday-rotocon/<version>`.
- Parses response JSON.
- Hands `extensions.complexity` to `_complexity.track(...)`.
- Maps `data.errors[*]` and HTTP status to typed errors via `_errors.raise_for(...)`.
- Retries `RateLimited` with exponential backoff (base 2 s, jitter, max 3 attempts).
- Returns `data` dict.

### 5.3 `client.py` — public client API

Two classes with identical surface, differing only in sync vs async:

```python
class MondayClient:
    def __init__(self, token: str | None = None, *, settings: Settings | None = None) -> None: ...
    @property
    def me(self) -> MeResource: ...
    @property
    def boards(self) -> BoardsResource: ...
    @property
    def items(self) -> ItemsResource: ...
    def close(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, *exc): ...

class AsyncMondayClient:
    # same shape, async resources, __aenter__/__aexit__, aclose
```

Resource objects (`MeResource`, `BoardsResource`, `ItemsResource`) expose narrow methods:

- `me.get() -> User`
- `boards.list(limit: int = 100, ids: list[int] | None = None, state: Literal["active","archived","deleted"] = "active") -> list[Board]`
- `boards.get(board_id: int) -> Board`
- `items.list(board_id: int, *, since: datetime | None = None) -> Iterable[Item]` on `MondayClient`; `AsyncIterable[Item]` on `AsyncMondayClient`. Paginated (cursor-based via monday's `items_page`); yields one item at a time so callers can stream without buffering an entire board in memory.

Each method:
1. Loads its query from `queries/`.
2. Calls transport with variables.
3. Parses result into Pydantic models.

### 5.4 `_complexity.py` — budget tracking

Monday's GraphQL has a complexity budget (10 M points / minute on Pro tier). Each query reports `complexity.before / after / query` in `extensions`. The tracker:

- Stores last-seen `after` and `query`.
- Emits `WARNING` via `logging.getLogger("monday_rotocon.complexity")` when `after / 10_000_000 < complexity_warn_threshold`.
- Exposes `get_last_budget() -> ComplexitySnapshot | None` for CLI to display in `--verbose` mode.
- Does **not** make decisions — retry logic lives in `_transport.py`.

### 5.5 `_errors.py` — typed exception hierarchy

```
MondayError                 (base)
 ├── MondayAPIError         (GraphQL errors[] or generic 4xx)
 ├── RateLimited            (429 or rate-limit error_code; carries retry_after_s)
 └── ComplexityExhausted    (ComplexityException error_code; carries reset_in_s, budget)
```

All carry `request_id: str | None` (from `extensions.request_id`) — surfaced for monday support tickets.

### 5.6 `models/` — typed domain entities

Pydantic v2. Public models: `Account`, `User` (also exported as `Me`), `Workspace`, `Board`, `Group`, `Item`, `ColumnValue` (discriminated union).

`column_values.py` uses Pydantic's discriminated unions on the `type` field:

```python
ColumnValue = Annotated[
    Union[StatusColumnValue, MirrorColumnValue, DateColumnValue, PersonColumnValue, TextColumnValue, ...],
    Field(discriminator="type"),
]
```

This is forced by monday's API shape — `column_values` arrays mix payloads keyed by `type`. Pydantic v2 discriminated unions are the only clean way to model this; dataclasses or attrs would force runtime `isinstance` ladders.

Models opt-in to `model_config = ConfigDict(populate_by_name=True, extra="ignore")` so monday's frequent schema additions don't break parsing.

### 5.7 `queries/` — GraphQL operations as files

Why files instead of inline strings:

- IDE syntax highlight for `.graphql`.
- Copy-paste directly into monday's GraphQL Playground for debugging.
- Diff-friendly when queries evolve.

Loader (`queries/__init__.py`):

```python
QUERIES: dict[str, str] = {
    path.stem: path.read_text(encoding="utf-8")
    for path in (Path(__file__).parent).glob("*.graphql")
}
```

Loaded once at import; no I/O at call time.

### 5.8 `cli.py` — Typer application

```
$ monday --help

  ping            Verify token and print account/user identity.
  boards list     List boards (table or JSON).
  items list      List items in a board.
  export dashboard
                  Produce JSON snapshot for CEO Dashboard V1.
                  Flags: --since DATE, --boards ID,ID,... --out PATH
```

Global flags: `--verbose`, `--json` (force machine output even for `ping`).

`monday ping` is the equivalent of the curl smoke test — confirms the integration end-to-end in < 1 s.

## 6. Data flow — example

```
$ monday export dashboard --since 2026-04-01 --out dashboard.json

cli.py
 ├─ Settings()                                ← env + .env
 ├─ MondayClient(...)
 │   ├─ boards.list()
 │   │   ├─ queries/boards.graphql            ← loaded once at import
 │   │   ├─ _transport.execute(query, vars)
 │   │   │   ├─ httpx.post(...)
 │   │   │   ├─ _complexity.track(extensions) → WARN if budget low
 │   │   │   └─ _errors.raise_for(json, http_status)
 │   │   └─ [Board.model_validate(b) for b in data["boards"]]
 │   └─ items.list(board_id, since)           ← paginated iterator
 ├─ aggregate into {boards:[{id,name,items:[…]}, …]}
 └─ Path("dashboard.json").write_text(json.dumps(payload, indent=2))
```

## 7. Error model

| Exception | Triggered by | CLI behavior |
|---|---|---|
| `MondayAPIError` | `errors[]` populated; 4xx (non-rate-limit) | exit 1; print error + `request_id` |
| `RateLimited` | 429; `error_code: Minute_Limit_Exceeded` | transport retries 3× w/ backoff; if exhausted → exit 3 |
| `ComplexityExhausted` | `error_code: ComplexityException` | no retry; exit 2; print "wait Ns, budget=X/10M" |
| `httpx.HTTPError` | DNS, TLS, connect timeout | bubbles up after transport-level retries; exit 4 |

All log records include `request_id` when present. CLI exit codes are stable so future automations can react.

## 8. Testing

| Suite | Command | Coverage gate | What it asserts |
|---|---|---|---|
| Unit | `pytest -m "not integration"` (default) | 80% on `client.py` + `_transport.py` + `_complexity.py` | request shape, response parsing, error mapping, paginator, CLI argument parsing |
| Integration | `pytest -m integration` (opt-in) | none (smoke) | real `me` + `boards(limit:1)` against `api.monday.com/v2` |
| Static | `mypy --strict src/monday_rotocon/` + `ruff check` + `ruff format --check` | clean | typing, lint, style |

**Fixtures.** `tests/fixtures/*.json` are sanitized real responses (emails, names replaced; account/user IDs replaced with `0`). Generated once by running `scripts/regen_fixtures.py` against a dev token; committed.

**Integration token.** `MONDAY_INTEGRATION_TOKEN` (separate from prod `MONDAY_API_TOKEN`) — read-only scope preferred. Skipped automatically when absent.

## 9. Tooling & dependencies

`pyproject.toml` (uv-managed) declares:

```toml
[project]
name = "monday-rotocon"
version = "0.1.0"
requires-python = ">=3.12"
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
```

`uv` workflow:

```
uv sync                  # install deps + create .venv
uv run pytest            # run tests
uv run monday ping       # invoke CLI
```

## 10. Acceptance criteria (M1 demo definition)

The skeleton is "done" when **all** of the following hold:

1. `uv sync && uv run monday ping` prints user + account identity in < 1 s. (Already proven manually; this is the contractual smoke test.)
2. `uv run monday boards list --json` returns a valid JSON array of boards.
3. `uv run monday export dashboard --out demo.json` produces a non-empty JSON snapshot covering at least: boards, groups, items, column values for the 5 existing boards (Aufgaben, Warteliste der Bugs, Epics, Sprints, Retrospektive).
4. `uv run pytest` passes with ≥ 80% coverage on `client.py` + `_transport.py` + `_complexity.py`.
5. `uv run mypy --strict src/monday_rotocon/` is clean.
6. `README.md` includes a 5-line quickstart.

## 11. Open questions / risks

- **Q1.** Dashboard output format — JSON is the default; do we also need CSV / Parquet for the CEO dashboard? Decision: deliver JSON in M1; revisit when the dashboard consumer (Looker? Notion? Sheets?) is chosen.
- **Q2.** Should `monday export dashboard` also pull updates/activity_logs? Decision: out of scope for skeleton; add a `--include-updates` flag in a follow-up if needed.
- **Risk R1.** monday API version bumps (`2024-10` → `2025-x`) historically introduce breaking changes (e.g., paginated boards / items). Mitigation: `API-Version` header pinned in `settings.py`; integration test gates upgrade. *Evidence:* during the Pre-A bootstrap on 2026-05-10, a verification query failed with `Cannot query field "items_count" on type "Group"` — monday silently removed that field from the `Group` type while keeping it on `Board`. The pinned `API-Version` did not insulate against it (deprecation on a leaf field). The integration suite is the only safety net for this class of regression.
- **Risk R2.** Token in `.env` has scope `me:write`; broader access (`boards:read`, `items:read`) is implicit because monday personal API tokens currently bypass scopes. If monday tightens this, several queries break. Mitigation: integration test catches it; document in README.

## 12. Future hooks (informational; not implemented in A)

- `AsyncMondayClient` is built now so sub-project B (FastAPI webhook server) can depend on it without rewrites.
- `_transport.execute` returns a `dict` so a future tracing middleware (OpenTelemetry / Sentry) can wrap it without touching domain code.
- `queries/` directory layout already accommodates mutations (`create_item.graphql`, `change_column_value.graphql`) — these will be added in sub-project B for the ERP-sync direction.

---

## Approval

Status: **APPROVED**. Next step: invoke `writing-plans` to author the implementation plan.

| Reviewer | Decision | Date | Notes |
|---|---|---|---|
| George S. Cucuiet | ✅ Approved | 2026-05-10 | After 3 advisor-driven refinements (§2 scripts/ boundary, §5.3 sync/async return types, §11 R1 schema-removal evidence) |
