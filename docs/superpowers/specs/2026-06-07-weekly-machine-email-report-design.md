# Weekly Machine Progress PDF Report — Design

**Date:** 2026-06-07
**Status:** Approved (design phase)
**Author:** george@rotocon.world + Claude Code
**Source brief:** `prompt_email.md` (repo root), revised after PDF decision.

## Goal

Every week, read the current state of all machines from the `Europe Machine
Overview` board, render an **engineering-style PDF report** (portfolio KPIs +
per-machine table + exception highlights), and email it as an **attachment**
with a short HTML summary in the body. Persist one history row to Postgres.

This is **Step 1** of the email-reporting track. Out of scope: Obsidian
integration, per-machine deep-dives, multi-channel (Slack) fan-out, raw-data
exports.

## Confirmed decisions

| Decision | Choice |
|---|---|
| Delivery format | **PDF attachment** + short HTML summary in the email body |
| PDF style | **Engineering-document** — dense, tabular, monospace accents, header/footer with metadata (date, KW, version) |
| PDF engine | **Python + WeasyPrint** (in-house), reusing the `monday_rotocon` library |
| Scheduler | **GitHub Actions cron** (no new server) |
| First-run audience | **george@rotocon.world only** (recipient list in one config point, easy to expand) |
| Sender | **george@rotocon.world** via the existing n8n `Gmail account` credential |
| Postgres history | **Included from the start** — `report_history` row per run in `rotocon_finance` |
| Send time | **Monday ~07:00 Europe/Bucharest** (GitHub cron is UTC — see Scheduling) |
| Content scope | Hybrid — KPI header + full table sorted by Overall + exceptions section |
| Subject | Dynamic — `Rotocon · Machine Progress · KW{week} · {n_critical} critical` |
| Language | English |
| Included machines | Current Machines group (`topics`) only |

## Architecture

Clean split of responsibilities: **GitHub = compute**, **n8n = delivery + persistence**.

```
GitHub Actions (cron, weekly + manual workflow_dispatch)
   → uv run scripts/weekly_machine_report.py
        · monday_rotocon reads board 5086438002 (group topics)
        · compute aggregates (KPIs, exceptions, sort)
        · render engineering HTML → PDF (WeasyPrint)
        · build short HTML email summary
        · POST { subject, recipient, html_summary, pdf_base64, stats } to n8n webhook
                ↓
n8n workflow  monday-machine-weekly-report-delivery
   → Webhook (header auth, X-Report-Token)
   → Convert to File (base64 pdf → binary attachment)
   → Gmail: send (HTML summary body + PDF attachment → recipient)
   → Postgres: CREATE TABLE IF NOT EXISTS report_history
   → Postgres: INSERT one history row
   → Respond to Webhook (200 { status, messageId })
```

**Why route email through n8n instead of sending from GitHub Actions:** Gmail
OAuth and Postgres credentials already live in n8n (used by other workflows).
Sending from Actions would mean managing an SMTP app-password / OAuth refresh
token in GitHub secrets. Routing the finished artifact to n8n keeps all delivery
credentials in one place and reuses the proven smoke-report webhook pattern.

**Why GitHub Actions as scheduler:** the repo is already on GitHub; a scheduled
workflow needs zero new infrastructure, runs Python 3.12 + uv natively, and
manages `MONDAY_API_TOKEN` / webhook token as encrypted secrets. WeasyPrint's
system libraries (cairo, pango, gdk-pixbuf) install via `apt-get` in the runner.

**Considered & rejected:** n8n-native HTML→PDF (no core node; needs Gotenberg or
a community node — the user chose Python to reuse the library). SaaS PDF API
(report data would leave the company). Cron on the n8n host (more infra to own).

## Components

### 1. `scripts/weekly_machine_report.py` (new, read-only)
Importable module, same shape and conventions as `scripts/smoke_ki_integration_report.py`
(env loader, pure render helpers, `main()` with `--dry-run`). Read-only: only
reads monday, never mutates — consistent with the library invariant and the
existing smoke-report precedent (`pythonpath = ["scripts"]` already set).

Functions:
- `load_env() -> RequiredEnv` — `MONDAY_API_TOKEN`, `N8N_WEBHOOK_URL`,
  `N8N_WEBHOOK_TOKEN`, `REPORT_RECIPIENT`. Exits 1 if any missing.
- `fetch_current_machines(client) -> list[Item]` — `items_for_board(5086438002)`
  filtered to `item.group.id == "topics"`.
- `compute_summary(machines) -> PortfolioSummary` — `total`, `avg_overall`,
  `critical_count`, `late_count`, `discrepancy_count` (`phase_pct - subtask_pct
  >= 40`), `delivery_30d_count`, ISO `week`, `generated_at`.
- `build_exceptions(machines) -> list[ExceptionRow]` — `critical | late delivery
  | discrepancy >= 40 | (delivery <= 30d AND overall < 70)`, sorted by urgency,
  each with a `why` string.
- `render_report_html(summary, exceptions, machines) -> str` — full engineering
  layout (print CSS: `@page` size A4, margins, header/footer with KW + version +
  page numbers; monospace for IDs/numbers; dense tables).
- `render_pdf(html) -> bytes` — WeasyPrint `HTML(string=html).write_pdf()`.
- `render_email_summary_html(summary) -> str` — short inline-styled KPI strip +
  "Full report attached as PDF".
- `build_payload(...)` — `{ subject, recipient, html_summary, pdf:
  {filename, content_base64, mime_type:"application/pdf"}, stats: {...} }`.
- `post_to_n8n(...)` — header-auth POST with 3-attempt backoff (reuse the
  smoke-report implementation).
- `main(--dry-run)` — dry-run writes the PDF locally to `reports/` and skips the
  POST; full run POSTs to n8n.

Column IDs used (all verified present on the board, 2026-06-07): `status`,
`numeric_mm3xhrbf` (Phase %), `numeric_mm3xgyyw` (Subtask %), `numeric_mm3x30na`
(Overall), `color_mm06k0h1` (Project Status), `color_mm06wr1p` (Procurement),
`text_mkxvf3xh` (Machine Type), `text_mkxvxap2` (Client), `country_mkxvqhys`,
`person`, `timerange_mkxw4hgt`, `formula_mkxw3x4k` (Calc Deliver Date),
`date_mky7mk4f` (FAT), `date_mky785fe` (SAT).

### 2. Dependency: WeasyPrint
Add to `pyproject.toml` as an optional extra: `[project.optional-dependencies]
report = ["weasyprint>=62"]`. Runtime system libs (cairo, pango, gdk-pixbuf,
libffi) are documented for both local dev (macOS: `brew install pango`) and the
GitHub runner (`apt-get install libpango-1.0-0 libpangocairo-1.0-0
libgdk-pixbuf2.0-0 libffi-dev`). WeasyPrint is **not** added to the default
runtime deps so the read-only library stays lightweight.

### 3. n8n workflow `monday-machine-weekly-report-delivery`
Webhook (POST `/webhook/monday-weekly-report`, header auth `X-Report-Token`,
responseMode `responseNode`) → **Convert to File** (decode `body.pdf.content_base64`
to a binary property `report_pdf`) → **Gmail** send (to `body.recipient`,
subject `body.subject`, HTML `body.html_summary`, attach `report_pdf`) →
**Postgres** ensure-table → **Postgres** insert → **Respond** 200.

> ⚠ Known payload-shape gotcha: once the **Convert to File** node is in the
> chain, downstream nodes must read webhook fields via
> `$('Webhook').first().json.body.X`, **not** `$json.body.X` (the binary node
> changes the active item shape). This is recorded in MEMORY
> (`n8n_webhook_payload_after_convert_to_file`).

Credentials: header-auth credential `Report Webhook Token` (new, reuse the
smoke-report token convention), `Gmail account` (`ahEoxGuMkBRjQ9YF`),
`Postgres account` (`l5HHFXvW5o8FdBkj`).

### 4. `.github/workflows/weekly-machine-report.yml`
Triggers: `schedule` (weekly cron) + `workflow_dispatch` (manual). Steps:
checkout → setup Python 3.12 → install uv → `apt-get` WeasyPrint libs →
`uv sync --extra report` → `uv run python scripts/weekly_machine_report.py`.
Secrets: `MONDAY_API_TOKEN`, `N8N_WEBHOOK_URL`, `N8N_WEBHOOK_TOKEN`,
`REPORT_RECIPIENT`.

### 5. Postgres `rotocon_finance.report_history`
```sql
CREATE TABLE IF NOT EXISTS rotocon_finance.report_history (
  id            SERIAL PRIMARY KEY,
  sent_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  report_type   TEXT NOT NULL,           -- 'weekly_machine_progress'
  board_id      BIGINT NOT NULL,
  machine_count INT NOT NULL,
  avg_overall   NUMERIC(5,2),
  critical_n    INT,
  late_n        INT,
  recipient     TEXT,
  pdf_size_kb   INT
);
```
One `INSERT` per run, downstream of a successful Gmail send.

## Scheduling detail

GitHub cron is **UTC with no DST**. Bucharest is UTC+2 (winter) / UTC+3
(summer). `cron: "0 5 * * 1"` fires 07:00 in winter and 08:00 in summer — close
enough for a weekly report; the exact minute is immaterial. `workflow_dispatch`
allows on-demand runs for testing and ad-hoc sends. (GitHub may delay scheduled
runs by a few minutes under load — acceptable here.)

## Error handling

| Failure | Behaviour |
|---|---|
| monday API 5xx / rate limit | Library retry (exponential backoff) handles transient errors; persistent failure exits non-zero → Actions run fails, no email. |
| WeasyPrint render error | Script exits non-zero before POST → no partial email; Actions surfaces the failure. |
| n8n webhook unreachable | `post_to_n8n` retries 3× (1s/2s/4s) then exits non-zero. |
| Gmail send fails | Workflow stops at Gmail node; Postgres nodes don't run → no false "sent" row. |
| Machine with null Overall / no Responsible | Rendered as `—` / blank; never crashes. |
| Empty exception list | "No exceptions this week ✅", not an empty table. |

## Testing & rollout

1. **Unit tests** (`respx`-mocked, no network): `compute_summary`,
   `build_exceptions`, `render_report_html` (asserts key sections/edge cases),
   `render_pdf` (asserts output starts with `%PDF`), `build_payload`
   (base64 round-trip), `post_to_n8n` (success / retry / non-2xx).
2. **Local dry-run**: `uv run python scripts/weekly_machine_report.py --dry-run`
   writes the PDF to `reports/` — open and eyeball the engineering layout.
3. **n8n workflow** created **inactive**, validated, manually curl-tested with a
   tiny PDF (auth + attach + Postgres insert work).
4. **End-to-end manual run** via `workflow_dispatch` → email with PDF lands in
   george@'s inbox; one row in `report_history`.
5. **Spot-check**: 2 machines, KPI numbers and exception membership vs the board.
6. Activate the weekly cron only after george@ signs off on the rendered PDF.
   Expanding the recipient list to the internal team is a one-line edit, done
   separately.

## Deliverables

1. `scripts/weekly_machine_report.py` + unit tests + opt-in integration test.
2. `weasyprint` extra in `pyproject.toml`; system-deps documented.
3. n8n workflow `monday-machine-weekly-report-delivery` — inactive, validated,
   test-run.
4. `report_history` table in `rotocon_finance`.
5. `.github/workflows/weekly-machine-report.yml` + a `SECRETS.md` note listing
   the four required GitHub secrets.
6. Sample PDF saved as `reports/sample-weekly-machine-report.pdf` for sign-off.
7. `MEMORY.md` entry for any non-obvious build decision.
</content>
