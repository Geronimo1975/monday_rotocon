# Prompt: Build Weekly Machine Progress HTML Email Report (Step 1)

> Reusable brief. Feed this to a Claude Code session (or read it yourself) to implement the weekly HTML email report.

---

## 1. Context — what already exists

- **Monday board**: `Europe Machine Overview` (id `5086438002`), 74 machines, terminology "Machine #".
- **Phase column** (`status`) with 15 labels (Backlog → Order → ... → Done → Warranty).
- **3 numeric progress columns**, populated automatically by n8n every 30 min:
  - `Phase Progress %` — `numeric_mm3xhrbf` — milestone-weighted from Phase.
  - `Subtask Done %` — `numeric_mm3xgyyw` — % of subitems with status `Done`.
  - `Overall Progress` — `numeric_mm3x30na` — `0.6 * Phase + 0.4 * Subtask`.
- **Other useful columns**:
  - `text_mkxvf3xh` Machine Type
  - `text_mkxvxap2` Client
  - `country_mkxvqhys` Client Country
  - `person` Responsible
  - `color_mm06k0h1` Project Status (ok / critical / late delivery / on hold / open procurement)
  - `color_mm06wr1p` Procurement (All on Order / open orders / critical)
  - `timerange_mkxw4hgt` Timeline (start–end)
  - `formula_mkxw3x4k` Calc Deliver Date
  - `date_mky7mk4f` FAT Date / `date_mky785fe` SAT Date
- **n8n instance**: `https://n8n.rotocon.world`. Existing workflow `monday-machine-progress-sync` (id `dDmItkGhLfb1xNvJ`) handles the progress columns. Credentials available:
  - `Monday API Token` (httpHeaderAuth, id `NvEH5iJQgsGArHfy`)
  - `Gmail account` (gmailOAuth2, id `ahEoxGuMkBRjQ9YF`)
  - `Postgres account` (id `l5HHFXvW5o8FdBkj`)
  - `Slack account` (id `oA7AGPiL2Xb8q0E8`)

## 2. Goal

Build an n8n workflow that on a weekly schedule:

1. Pulls current state of all machines from `Europe Machine Overview`.
2. Renders a single HTML email summarising overall portfolio + per-machine table + exception highlights.
3. Sends the email via the existing Gmail credential to a configured distribution list.

**Out of scope for Step 1**: Obsidian integration, per-machine deep-dives, attachments, Postgres history snapshot. Those land in later steps.

## 3. Open inputs — confirm with user before building

If unspecified, fall back to the defaults marked `(default)`:

| Input | Options | Default |
|---|---|---|
| Audience | Marco only / Rotocon internal core team / extended team / clients | Marco + Matthias + Renelda + Metin + Nicole *(default)* |
| Send day & time | Monday 07:00 / Friday 17:00 / other | **Monday 07:00 Europe/Bucharest** *(default)* |
| Scope of content | Full portfolio status / exceptions only / hybrid | **Hybrid: KPI header + full table sorted by Overall + exceptions section** *(default)* |
| Subject line | static / dynamic (e.g. include date and # critical) | **Dynamic: `Rotocon · Machine Progress · KW{week} · {n_critical} critical`** *(default)* |
| Language | English / German / Romanian | **English** (multilingual team) *(default)* |
| Include Demo/Installed machines? | yes / no | **No — Current Machines group only** *(default)* |

## 4. Architecture

```
Schedule Trigger (cron: 0 7 * * 1, TZ Europe/Bucharest)
   ↓
Fetch Machines (HTTP POST Monday GraphQL — items + selected column values, no subitems)
   ↓
Compute Aggregates (Code node — KPI totals, exception buckets, sort, format)
   ↓
Render HTML (Code node — string template, no external deps)
   ↓
Send Email (Gmail node — to: distribution list, subject: dynamic, html: rendered)
   ↓
(optional) Log to Postgres `report_history` table
```

Why two Code nodes instead of one: separates **data shaping** (reusable for other channels — Slack, future Obsidian) from **presentation**. If we later add a Slack digest, only the render node changes.

## 5. Implementation steps (ordered)

### 5.1 Fetch node

GraphQL query — pull only what's needed for the report:

```graphql
query {
  boards(ids: [5086438002]) {
    items_page(limit: 100, query_params: { rules: [{ column_id: "group", compare_value: ["topics"] }] }) {
      items {
        id
        name
        group { id title }
        column_values(ids: [
          "status",
          "color_mm06k0h1",
          "color_mm06wr1p",
          "text_mkxvf3xh",
          "text_mkxvxap2",
          "country_mkxvqhys",
          "person",
          "timerange_mkxw4hgt",
          "formula_mkxw3x4k",
          "date_mky7mk4f",
          "numeric_mm3xhrbf",
          "numeric_mm3xgyyw",
          "numeric_mm3x30na"
        ]) {
          id
          text
          value
        }
      }
    }
  }
}
```

Filter to group `topics` ("Current Machines") so Demo + Installed + Template groups are excluded.

### 5.2 Compute Aggregates node

Output one item per machine plus one summary object. Logic:

1. Normalise: parse text/value of each column into a flat object per machine.
2. Compute portfolio KPIs:
   - `total` — count
   - `by_phase` — count per Phase
   - `avg_overall` — mean of Overall Progress
   - `critical_count` — Project Status `critical`
   - `late_count` — Project Status `late delivery`
   - `discrepancy_count` — machines where `phase_pct - subtask_pct >= 40` (declared advanced but execution lagging)
   - `delivery_30d_count` — Calc Deliver Date within next 30 days
3. Build buckets:
   - **Exceptions table**: any of `critical | late delivery | discrepancy >= 40 | delivery <= 30d AND overall < 70`. Sorted by urgency.
   - **Main table**: all 74 sorted by `overall_progress` descending.
4. Compute ISO week number and current date for header.

Pass output forward as `{ summary: {...}, exceptions: [...], machines: [...] }`.

### 5.3 Render HTML node

Inline-styled HTML email (no external CSS — most clients strip `<link>`). Layout:

```
┌─────────────────────────────────────────────┐
│  Rotocon · Machine Progress · KW23 2026     │  ← header band, brand color
│  Generated 2026-06-01 07:00                 │
├─────────────────────────────────────────────┤
│  KPI strip (4 tiles):                       │
│   [Total 74] [Avg 45%] [Critical 3] [Late 6]│
├─────────────────────────────────────────────┤
│  ⚠ Needs attention (exceptions table)       │
│  Machine · Client · Phase · Overall · Why   │
│  ROT200E    Valley   LOP    60%    Subtask 2% (gap 97) │
│  ...                                        │
├─────────────────────────────────────────────┤
│  Full portfolio                             │
│  table sorted by Overall desc, with         │
│  inline progress bar div (background        │
│  width % via inline style)                  │
├─────────────────────────────────────────────┤
│  Footer: link to Monday board, n8n run id   │
└─────────────────────────────────────────────┘
```

Visual rules:
- Brand color: `#0073EA` (Monday blue) for header. Replace if Rotocon brand guide says otherwise.
- Use system font stack: `-apple-system, "Segoe UI", Roboto, sans-serif`.
- Tables: `<table cellpadding="8" border="0">` with `border-collapse: collapse` and alternating row backgrounds `#fafafa`.
- Progress bar: nested `<div>` with `style="width:{n}%;background:#0073EA;height:8px;border-radius:4px"` inside a grey track.
- Status badges: small coloured span — critical `#df2f4a`, late `#ff6d3b`, ok `#037f4c`, on hold `#c4c4c4`, open procurement `#ff007f`.
- Total width capped at 720px, centred.
- No JS, no external images. Inline SVG OK but skip for v1.
- Dark mode: don't fight Gmail's auto-dark — use `prefers-color-scheme` media query optionally, but only after v1 works.

Output a single string `html`.

### 5.4 Gmail Send node

- Credential: `Gmail account`
- From: defaults to authenticated user (george@rotocon.world). Verify with user — may want a shared `reports@rotocon.world` sender.
- To: distribution list (configurable — start with the default audience above).
- Subject: `Rotocon · Machine Progress · KW{week} · {critical_count} critical`
- Body: `html` from previous node, in HTML mode.
- Plain text fallback: auto-generated from HTML strip, or accept HTML-only for now.

### 5.5 (Optional) Postgres history

If wanted now: insert one row per run into `rotocon_finance.report_history`:

```sql
CREATE TABLE IF NOT EXISTS report_history (
  id           SERIAL PRIMARY KEY,
  sent_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  report_type  TEXT NOT NULL,           -- 'weekly_machine_progress'
  board_id     BIGINT NOT NULL,
  machine_count INT NOT NULL,
  avg_overall  NUMERIC(5,2),
  critical_n   INT,
  late_n       INT,
  recipient    TEXT,
  html_size_kb INT
);
```

Defer to Step 2 unless user explicitly asks.

## 6. Acceptance criteria

Workflow passes when:

1. Manual run produces an email in Marco's inbox within 60 seconds.
2. Email renders correctly in Gmail web + iOS Gmail app + Outlook desktop (smoke-test these three).
3. KPI numbers match a manual spot-check of the board (pick 2 machines and verify).
4. Exception table contains every machine with `Project Status = critical`. No false positives.
5. Workflow handles edge cases:
   - Machine with null Overall (e.g. just created) → shows `—` not `null`.
   - Machine with no Responsible → shows blank, not crash.
   - Empty Exception list → section shows "No exceptions this week ✅" instead of empty table.
6. Total runtime under 30 seconds (excluding Gmail send latency).
7. Workflow created **inactive**, validated, then run manually once before activation.

## 7. Risks and edge cases

| Risk | Mitigation |
|---|---|
| Monday API rate limit on the fetch | Single query, no batching needed; 74 items fit in one items_page. |
| Gmail strips inline CSS aggressively | Pre-test using a "Send to self" before going to distribution list. |
| Timezone confusion in cron | Set workflow timezone to `Europe/Bucharest` explicitly in settings. |
| Email lands in spam | Send from a domain-authenticated address (SPF/DKIM on rotocon.world). If problems, switch to SMTP via Postmark/Sendgrid. |
| Holidays / weeks with no changes | Send anyway; the value is the rhythm. Add a note "no changes since last week" only if obviously stale. |
| Recipient leaves company | Maintain distribution list in one place (n8n env var or first node), not hardcoded in Gmail node. |

## 8. Concrete deliverables

1. **n8n workflow** `monday-machine-weekly-report` — inactive on creation, validated, manually test-run.
2. **Sample HTML output** — saved alongside this prompt as `prompt_email_sample.html` for design review before first send.
3. **Updated `MEMORY.md` entry** if any non-obvious decisions are made during build (e.g. specific styling that needs explaining later).
4. **Activation** — only after user signs off on the sample HTML and distribution list.

## 9. How to execute this prompt

1. Read the open inputs in §3. Ask user for confirmation or apply defaults.
2. Build the workflow in n8n via MCP (`mcp__n8n-mcp__n8n_create_workflow`).
3. Validate it (`n8n_validate_workflow`).
4. Run it once manually — capture the HTML output into `prompt_email_sample.html`.
5. Show the user the sample. Iterate on layout/data until accepted.
6. Confirm distribution list, then activate the schedule.

---

*Maintained alongside the `monday-machine-progress-sync` workflow. Step 2 (Obsidian integration) will branch from this same skeleton.*
