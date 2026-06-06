# KI Integration Smoke Report — Design

**Date:** 2026-06-06
**Author:** george@rotocon.world (drafted with Claude Code)
**Status:** Design approved, pending implementation plan
**Project:** `monday_rotocon` (sub-project A)

## 1. Purpose

End-to-end smoke test that proves `monday_rotocon` v0.2.1 — including the
v0.2.0 `MondayClient.boards()` / `items_for_board()` pagination work and the
v0.2.1 `httpx.TransportError` retry — functions against the real monday.com
API and delivers a professional report by email through the existing n8n
infrastructure.

The smoke test exercises:
- The pinned client version end-to-end with a live `MONDAY_API_TOKEN`.
- Cursor pagination across `items_page` / `next_items_page`.
- Pydantic model parsing with `extra="ignore"`.
- The n8n bridge (`https://n8n.rotocon.world`) as a delivery channel for
  outbound notifications, using the already-provisioned Microsoft Outlook
  OAuth2 credential (`7JEAzAMCDjKqDX3F`).

The smoke test is **not** a recurring business report and **not** a CLI
feature. It is a one-shot harness scheduled by hand to validate releases.

## 2. Scope and non-goals

**In scope**

- New script `scripts/smoke_ki_integration_report.py` that uses `monday_rotocon`.
- New n8n workflow `monday-smoke-report-email` (created via `n8n-mcp`).
- New `reports/` directory (gitignored) for the local Markdown copy.
- New env vars: `N8N_WEBHOOK_URL`, `N8N_WEBHOOK_TOKEN`, `REPORT_RECIPIENT`.
- Unit tests for the rendering helpers; opt-in integration test.
- `.env.example` updated with placeholders.

**Out of scope**

- CLI subcommands (`monday smoke-report`, `monday export …`) — stay on the
  roadmap untouched.
- Any mutation of monday state. The library's read-only invariant holds; the
  script only reads from monday. Sending mail is not a monday mutation.
- Scheduled / cron execution. The user triggers the script manually.
- Caching, persistent storage of past reports beyond the local Markdown file.
- Logging framework. `print` + non-zero exit codes are sufficient.

## 3. Architecture

```
.env  (MONDAY_API_TOKEN, N8N_WEBHOOK_URL, N8N_WEBHOOK_TOKEN, REPORT_RECIPIENT)
  │
  ▼
scripts/smoke_ki_integration_report.py
  │
  ▼
MondayClient.boards()       ─►  locate "KI Integration" in workspace 5528271
  │
  ▼
MondayClient.items_for_board(board_id)  ─►  all items via cursor pagination
  │
  ▼
group_items_by_title()                  ─►  {group_title: count}
  │
  ├──►  render_markdown(...)  ─►  reports/<ts>-ki-integration.md   (local file)
  │                           └►  base64-encoded for attachment
  └──►  render_html(...)      +  QuickChart URL  (bar chart)
                                  │
                                  ▼
                         POST n8n webhook (HTML body + .md attachment)
                                  │
                                  ▼
                         n8n workflow → M365 Outlook node → recipient
                                  │
                                  ▼
                         HTTP 200 / non-200  ─►  exit 0 / exit 3
```

### 3.1 Component placement

The script lives in `scripts/` because it is a one-shot ad-hoc operation
(matching the directory's intent in CLAUDE.md). Unlike
`bootstrap_ki_integration.py`, which is stdlib-only because it must run
before the package is installable, the smoke script's whole purpose is to
exercise the installed library. It therefore depends on `uv sync` having run
and imports `monday_rotocon` directly. This deviation from the "stdlib-only"
convention is intentional and documented in the script's docstring.

### 3.2 n8n workflow

Name: `monday-smoke-report-email`

| Node | Type | Configuration |
|---|---|---|
| 1. Webhook | Webhook trigger | Path: `/webhook/monday-smoke-report`, method `POST`, header auth `X-Smoke-Token` matching `N8N_WEBHOOK_TOKEN` |
| 2. Send Email | Microsoft Outlook → Send | Credential `7JEAzAMCDjKqDX3F`; `to`, `subject`, `bodyContent` (HTML), and one attachment all mapped from `{{ $json }}` |
| 3. Respond | Respond to Webhook | Body `{ "status": "sent", "messageId": "{{ $node['Send Email'].json.id }}" }`, status 200 |

The webhook is unauthenticated at the network layer; the `X-Smoke-Token`
header is the only access control. If the header is missing or mismatched,
the workflow short-circuits to a 401 response (configured via an `IF` node
between Webhook and Send Email, OR via Webhook's built-in header auth — to
be picked at implementation time, whichever requires less wiring).

### 3.3 Payload contract

```json
{
  "subject": "KI Integration smoke test — 2026-06-06",
  "recipient": "george@rotocon.world",
  "html_body": "<html>…</html>",
  "markdown_attachment": {
    "filename": "2026-06-06-ki-integration-smoke.md",
    "content_base64": "…",
    "mime_type": "text/markdown"
  }
}
```

The Python side builds this dict; the n8n workflow consumes it without
transformation. Schema stability is enforced by a small `TypedDict` in the
script.

## 4. Report content

### 4.1 Source of truth

Both Markdown and HTML are rendered from the same Python dict:

```python
{
  "board_id": int,
  "board_name": str,
  "workspace_id": int,
  "generated_at": datetime,    # UTC
  "client_version": str,       # "monday_rotocon vX.Y.Z" from __version__
  "run_id": str,               # uuid4 hex
  "group_counts": list[tuple[str, int]],   # ordered by board group order
  "total_items": int,
}
```

Two pure functions, `render_markdown(report) -> str` and
`render_html(report) -> str`, are independently unit-testable.

### 4.2 Markdown (Obsidian-flavored)

- YAML frontmatter (`title`, `date`, `client`, `board_id`, `tags`).
- `> [!info]` callout block with run metadata.
- Mermaid `pie` block with one slice per group.
- GFM table: `Grup | Itemi | % din total`, with bold `Total` row.
- GFM checklist of the verifications the run completed.
- Footer line: `*Generated by scripts/smoke_ki_integration_report.py · run id <uuid>*`

Saved to `reports/<YYYY-MM-DD-HHMM>-ki-integration-smoke.md`. The `reports/`
directory is created on demand and added to `.gitignore`.

### 4.3 HTML email

Plain inline-styled HTML compatible with Outlook / M365 web client:

- `<header>` with title and meta line.
- `<table>` with two columns (`Grup`, `Itemi`) and a bold Total row.
- `<img>` referencing a QuickChart URL:
  ```
  https://quickchart.io/chart?w=600&h=300&c=<URL-encoded JSON>
  ```
  Chart config: `horizontalBar`, single dataset, legend off, title "Itemi per
  grup", color `#2563eb`.
- `<footer>` with `monday_rotocon` version, run id, link to local Markdown
  filename (informational only — recipient does not have access to the local
  file, the `.md` attachment is the canonical copy).

QuickChart was chosen over server-side matplotlib because (a) zero new Python
dependency, (b) zero binary in the payload, (c) QuickChart is a free public
service. If QuickChart becomes unavailable at run time, the email still
renders cleanly — the `<img>` shows a broken icon but the table stays
readable.

## 5. Configuration

New variables added to `.env` and `.env.example`:

```
N8N_WEBHOOK_URL=https://n8n.rotocon.world/webhook/monday-smoke-report
N8N_WEBHOOK_TOKEN=<64-char hex string, 32 random bytes>
REPORT_RECIPIENT=george@rotocon.world
```

`N8N_WEBHOOK_TOKEN` is generated once at setup time:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

…which prints 64 hex chars (32 bytes / 256 bits of entropy). The same
value is pasted both into local `.env` and into the n8n Webhook node's
expected header value. `.env.example` ships with the placeholder shown
above, never real values.

## 6. Error handling

| Cause | Exit | Stdout/stderr |
|---|---:|---|
| Missing required env var | 1 | "Missing required env: <NAME>" |
| `MondayAPIError` (auth, persistent 5xx, GraphQL error) | 2 | `repr(exc)` only, no stacktrace |
| Board "KI Integration" not found in workspace 5528271 | 4 | List of board names found, as hint |
| n8n webhook non-2xx | 3 | Status + first 500 chars of response body |
| n8n webhook transport error (DNS / refused / timeout) | 3 | 3-attempt retry with 1s/2s/4s backoff before giving up |
| Success | 0 | board id, total items, n8n `messageId`, path to local Markdown |

The script does **not** add retries on top of `MondayClient` — the client
already retries 5xx/429 and transport errors internally. The webhook retry
is local because the n8n hop is not in the client's scope.

## 7. Testing

### 7.1 Unit (`tests/test_smoke_report.py`)

Default marker (runs in `uv run pytest`):

- `test_group_items_by_title`: given a synthetic list of 7 `Item` models
  across 3 groups, returns a correctly-ordered list of tuples.
- `test_render_markdown_includes_frontmatter_and_mermaid`: output starts
  with `---`, contains a `pie title` block, contains a row with bold
  `**Total**`.
- `test_render_html_includes_quickchart_url`: output contains
  `quickchart.io/chart?` with a URL-encoded `horizontalBar` config and a
  decoded JSON body that matches the report's group counts.
- `test_build_payload_attachment_roundtrips`: base64-decoding
  `markdown_attachment.content_base64` reproduces the Markdown string
  byte-for-byte.

### 7.2 Integration (`tests/integration/test_smoke_report.py`)

Marker `integration` (opt-in via `uv run pytest -m integration`):

- Runs the script as a subprocess with real `MONDAY_API_TOKEN`.
- Points `N8N_WEBHOOK_URL` at a **dedicated test workflow** in n8n that
  responds 200 without sending email. (This workflow is created once,
  manually, as part of the rollout. It is NOT created by the script.)
- Asserts exit code 0, asserts a Markdown file appears under `reports/`,
  asserts that file contains the board name.

### 7.3 Dry-run flag

```bash
python scripts/smoke_ki_integration_report.py --dry-run
```

Performs fetch + rendering + local Markdown save, but skips the n8n POST.
Returns 0 on success. Intended for local iteration on report formatting.

## 8. Build sequence (implementation outline)

1. Create n8n workflow `monday-smoke-report-email` via `n8n-mcp` (Webhook →
   M365 Outlook → Respond). Validate via `n8n_validate_workflow`. Activate.
2. Create the n8n test workflow used by integration tests (200-OK echo,
   same path namespace).
3. Generate `N8N_WEBHOOK_TOKEN`; populate `.env`; update `.env.example`.
4. Add `reports/` to `.gitignore`.
5. Implement `scripts/smoke_ki_integration_report.py`:
   - env loading + validation
   - `MondayClient` context manager
   - `group_items_by_title`
   - `render_markdown`, `render_html`
   - `build_payload`
   - `post_to_n8n` (with local 3-attempt retry)
   - `main()` with `--dry-run`
6. Add unit tests (`tests/test_smoke_report.py`).
7. Add integration test (`tests/integration/test_smoke_report.py`) — opt-in
   via marker.
8. Run `uv run ruff format . && uv run ruff check . && uv run mypy src &&
   uv run pytest` and fix any issues.
9. Manual end-to-end: live `--dry-run` first, inspect the local Markdown
   and decoded HTML, then full run.
10. Commit.

## 9. Open questions

None. All decisions resolved during brainstorming (see also the conversation
transcript for context):

- Smoke test purpose, not business report (A).
- Board: KI Integration, located by name (A).
- Channel: n8n webhook, not direct SMTP (n8n workflow).
- Split: Python fetches, n8n sends (A).
- n8n workflow: built fresh by us (A).
- Email node: Microsoft 365 Outlook (b), existing credential.
- Report content: metadata + group breakdown (B).
- Format: two artifacts — Obsidian Markdown + HTML email with chart (A).
- Markdown destination: local + attached (C).
- Chart: QuickChart.

## 10. Risks

- **QuickChart availability** — third-party free service. If down at send
  time, email body still readable but bar chart shows as broken image.
  Mitigation: documented; no fallback planned.
- **n8n webhook token leakage** — if `.env` or n8n workflow export leaks,
  an attacker can spam the M365 mailbox of the recipient via this
  endpoint. Mitigation: token rotated if the script source or the n8n
  workflow are ever shared publicly.
- **Board structure changes** — if the "KI Integration" board is renamed
  or moved out of workspace 5528271, the script fails fast (exit 4) and
  prints the list of boards seen as a hint.
