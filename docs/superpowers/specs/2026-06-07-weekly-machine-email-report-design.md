# Weekly Machine Progress Email Report — Design

**Date:** 2026-06-07
**Status:** Approved (design phase)
**Author:** george@rotocon.world + Claude Code
**Source brief:** `prompt_email.md` (repo root)

## Goal

An n8n workflow that, on a weekly schedule, reads the current state of all
machines from the `Europe Machine Overview` board, renders a single HTML email
(portfolio KPIs + per-machine table + exception highlights), sends it via the
existing Gmail credential, and appends one history row to Postgres.

This is **Step 1** of the email-reporting track. Out of scope for Step 1:
Obsidian integration, per-machine deep-dives, attachments, multi-channel
(Slack) fan-out.

## Confirmed decisions

| Decision | Choice | Rationale |
|---|---|---|
| First-run audience | **george@rotocon.world only** | Validate rendering + data before the email reaches the internal team. The recipient list lives in one configurable node, trivial to expand to Marco + Matthias + Renelda + Metin + Nicole later. |
| Sender | **george@rotocon.world** | Existing authenticated Gmail credential (`Gmail account`, id `ahEoxGuMkBRjQ9YF`). Zero setup. A dedicated `reports@` sender with SPF/DKIM is a later option. |
| Postgres history | **Included from the start** | `report_history` row per run, in the existing `rotocon_finance` schema. |
| Send day/time | **Monday 07:00 Europe/Bucharest** (default) | The value is the weekly rhythm. |
| Content scope | **Hybrid** — KPI header + full table sorted by Overall + exceptions section | Default from brief. |
| Subject line | **Dynamic** — `Rotocon · Machine Progress · KW{week} · {n_critical} critical` | Default from brief. |
| Language | **English** | Multilingual team. |
| Included machines | **Current Machines group (`topics`) only** | Exclude Demo / Installed / Template groups. |

## Verified ground truth (monday + n8n, 2026-06-07)

**Board** `Europe Machine Overview` (`5086438002`), workspace `Rotocon`
(`5292504`), 74 machines, item terminology "Machine #". Target group `topics`
= "Current Machines". Other groups (`group_mm36dsc2` Demo, `group_mkxwr53d`
Installed, `group_mkz9xkz6` Template) are excluded.

**Columns used** (all confirmed present):

| Column ID | Title | Type | Use |
|---|---|---|---|
| `status` | Phase | status (15 labels Backlog→Warranty) | phase label |
| `numeric_mm3xhrbf` | Phase Progress % | numbers | KPI, discrepancy |
| `numeric_mm3xgyyw` | Subtask Done % | numbers | discrepancy |
| `numeric_mm3x30na` | Overall Progress | numbers | sort key, avg KPI |
| `color_mm06k0h1` | Project Status | status (critical/ok/late delivery/on hold/open procurement) | exception buckets |
| `color_mm06wr1p` | Procurement | status | display |
| `text_mkxvf3xh` | Machine Type | text | display |
| `text_mkxvxap2` | Client | text | display |
| `country_mkxvqhys` | Client's Country/Destination | country | display |
| `person` | Responsible | people | display |
| `timerange_mkxw4hgt` | Timeline | timeline | display |
| `formula_mkxw3x4k` | Calc Deliver Date | formula | delivery-30d bucket |
| `date_mky7mk4f` | FAT Date | date | display |
| `date_mky785fe` | SAT Date | date | display |
| `text_mm3x6tqs` | DATEV Project ID | text | (optional) join key for future finance reporting |

**n8n landscape:** instance `https://n8n.rotocon.world`.
- `monday-machine-progress-sync` (`dDmItkGhLfb1xNvJ`, active) populates the three
  numeric progress columns every 30 min. Our report only **reads** these.
- `Rotocon Finance: Bootstrap Postgres Schema` (`CEuPrVdKK3FTkJMb`) confirms the
  `rotocon_finance` Postgres schema exists. We add a `report_history` table to it.
- Credentials available: `Gmail account` (gmailOAuth2, `ahEoxGuMkBRjQ9YF`),
  `Postgres account` (`l5HHFXvW5o8FdBkj`), `Monday API Token`
  (httpHeaderAuth, `NvEH5iJQgsGArHfy`).

## Architecture

Single linear workflow `monday-machine-weekly-report`, two Code nodes
separating data shaping from presentation so the shape node can later feed a
Slack digest without change.

```
Schedule Trigger (cron 0 7 * * 1, TZ Europe/Bucharest)
   ↓
Fetch Machines (HTTP POST monday GraphQL — items + selected columns, group topics)
   ↓
Compute Aggregates (Code #1 — KPI totals, exception buckets, sort, ISO week)
   ↓
Render HTML (Code #2 — inline-styled string template, no external deps)
   ↓
Send Email (Gmail node — to: configurable list, subject: dynamic, html)
   ↓
Postgres: ensure table (CREATE TABLE IF NOT EXISTS report_history)
   ↓
Postgres: insert one history row
```

Postgres writes execute **only after** a successful Gmail send (downstream of
the Send node), so a failed send produces no history row.

**Considered alternatives (rejected):**
- *Shared fetch sub-workflow* with `monday-machine-progress-sync` — more DRY but
  couples two currently-independent workflows; premature.
- *Single mega Code node* — fewer nodes but not reusable and hard to debug.

## Component detail

### Fetch Machines
GraphQL query against board `5086438002`, `items_page(limit: 100)` filtered to
group `topics`, requesting only the 13 columns above (id, text, value each).
74 items fit in one page — no pagination needed.

### Compute Aggregates (Code #1)
Normalises each machine into a flat object, then emits `{ summary, exceptions,
machines }`:
- **summary**: `total`, `by_phase`, `avg_overall`, `critical_count`,
  `late_count`, `discrepancy_count` (`phase_pct - subtask_pct >= 40`),
  `delivery_30d_count` (Calc Deliver Date within next 30 days), ISO `week`,
  generated timestamp.
- **exceptions**: machines matching `critical | late delivery | discrepancy >= 40
  | (delivery <= 30d AND overall < 70)`, sorted by urgency.
- **machines**: all current machines sorted by `overall_progress` desc.

### Render HTML (Code #2)
Inline-styled HTML (most clients strip `<link>`), max width 720px, centred,
system font stack. Header band `#0073EA`; KPI strip (Total / Avg / Critical /
Late); exceptions table with a "Why" column; full portfolio table with an inline
progress-bar `<div>`. Status badges colour-coded (critical `#df2f4a`, late
`#ff6d3b`, ok `#037f4c`, on hold `#c4c4c4`, open procurement `#ff007f`). No JS,
no external images except the chart is dropped for v1. Output a single `html`
string. Edge cases:
- null Overall → render `—`, not `null`.
- no Responsible → blank cell, no crash.
- empty exception list → "No exceptions this week ✅", not an empty table.

### Send Email (Gmail)
Credential `Gmail account`. From: authenticated user (george@). Recipient list
held in a single upstream Set/config node — initial value `george@rotocon.world`.
Subject: `Rotocon · Machine Progress · KW{week} · {critical_count} critical`.
Body: `html`, HTML mode. Plain-text fallback auto-generated or HTML-only for v1.

### Postgres history
Schema `rotocon_finance`. Table:

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
  html_size_kb  INT
);
```

One `INSERT` per run, downstream of the Send node.

## Error handling

| Failure | Behaviour |
|---|---|
| monday API rate limit / 5xx on fetch | Single small query; n8n node retry (3×) handles transient errors. Persistent failure aborts the run — no email, no history row. |
| Gmail send fails | Workflow stops at Send node; Postgres nodes do not execute, so no false "sent" row. n8n surfaces the failed execution in its log. |
| Machine with null/empty progress | Rendered as `—`; never crashes the Code node. |
| Timezone drift | Workflow timezone pinned to `Europe/Bucharest` in settings. |
| Empty week (no changes) | Send anyway; the rhythm is the value. |

## Testing & rollout

1. Create the workflow **inactive**.
2. Validate via `n8n_validate_workflow`; fix until clean.
3. Manual run once → email lands in george@'s inbox within ~60s; one row in
   `report_history`.
4. Spot-check: pick 2 machines, verify KPI numbers and exception membership
   against the board.
5. Render check in Gmail web (primary target for v1).
6. Only after sign-off on the rendered email: activate the schedule. Expanding
   the recipient list to the internal team is a one-node edit, done separately.

## Deliverables

1. n8n workflow `monday-machine-weekly-report` — inactive, validated, manually
   test-run.
2. `report_history` table created in `rotocon_finance`.
3. Sample rendered HTML saved as `prompt_email_sample.html` for design review
   before first send.
4. `MEMORY.md` entry for any non-obvious build decision.
5. Activation only after george@ signs off on the sample.
</content>
</invoke>
