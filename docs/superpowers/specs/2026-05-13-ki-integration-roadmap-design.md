# Design — KI Integration Board ↔ Public Roadmap Page (Phase 1a)

| Field | Value |
|---|---|
| Date | 2026-05-13 |
| Author | George Sebastian Cucuiet (via Claude brainstorming) |
| Status | **APPROVED** (pending final read-through by George) |
| Relates to | [`docs/superpowers/specs/2026-05-10-monday-core-skeleton-design.md`](2026-05-10-monday-core-skeleton-design.md) (sub-project A) |
| Implements | The concrete consumer for sub-project A's "CEO Dashboard V1" deliverable (§10 acceptance criterion 3 of A's spec). Roadmap month: M1. |
| Successor specs | A future *Sub-project B* spec will cover Phases 1b/1c/1d (real-time webhooks, two-way edits, Q&E ERP integration). Not authored yet. |

---

## 0. Decisions log

The Q&A phase was bypassed at George's request; he answered Q1–Q7 inline on 2026-05-13.

| Q | Topic | Answer | Effect on this spec |
|---|---|---|---|
| Q1 | Sync direction | (B) two-way edits | **Deferred to Phase 1c / sub-project B.** Phase 1a is read-only. |
| Q2 | Refresh cadence | (A) real-time webhooks | **Deferred to Phase 1b / sub-project B.** Phase 1a uses daily cron. |
| Q3 | Page audience | (C) exec only | Resolved. Page is exec-only; no new auth introduced beyond what the domain already provides. |
| Q4 | Items in scope | (A) all 29, enriched | Resolved. Full KI Integration board (Onboarding + Execution Plan + Operatives Setup + KPI + AI Initiatives). |
| Q5 | Frontend stack | URL-only answer (`/roadmap`); stack not specified | Provisionally resolved — see §6.2. Stack picked to be stack-agnostic; can be re-targeted to Webflow / Astro / plain static after Phase 1a UX is reviewed. |
| Q6 | JSON delivery to site | (A) site repo CI pulls | Resolved. Site repo's CI is the integrator; this repo just produces JSON. |
| Q7 | KPI numerator source | (C) Q&E ERP | **Deferred to Phase 1d / sub-project B.** Phase 1a uses manual entry in a `KPI current` column on the board. |

**Phased delivery (chosen 2026-05-13 over single-step and mega-spec alternatives):**

| Phase | Scope | Roadmap month | Status |
|---|---|---|---|
| **1a** | Board enriched + daily JSON export + static read-only `/roadmap` page (Gantt + Table + KPI strip, KPIs manual) | M1 | **This spec** |
| 1b | monday → page real-time via webhooks | M2 | Deferred (sub-project B spec) |
| 1c | Page → monday two-way edit | M2 | Deferred (sub-project B spec) |
| 1d | KPI numerator from Q&E ERP | M3 | Deferred (sub-project B spec) |

---

## 1. Context

### 1.1 Where we are today

**Artifact 1 — KI Integration board** (monday.com, id `5096182046`, workspace `ROTOCON EU SERVICE` / id `5528271`):
- Created on 2026-05-10 by `scripts/bootstrap_ki_integration.py`, sourcing item titles from `Tasks/ROTOCON_Onboarding_DE.docx`.
- 5 groups × 29 items: `Onboarding (Tag 1)` (8 items), `4-Wochen Execution-Plan` (4), `Operatives Setup monday.com` (5), `KPI Tracking` (6), `AI Initiatives (M4–M6)` (6).
- **One column only**: `name` (the default). No `Status`, no `Date`, no `Owner`, no `Priority`, no `Dependency`. No views beyond the default Table. Gantt is impossible without temporal columns.
- This is **by design** — the bootstrap script intentionally created the structure first, leaving columns as a follow-up step. This spec fills that follow-up.

**Artifact 2 — `monday_rotocon` Python package** (this repo):
- Sub-project A spec APPROVED 2026-05-10; implementation plan exists in `docs/superpowers/plans/2026-05-10-monday-core-skeleton.md`.
- Defines `monday export dashboard --out PATH` CLI command (§5.8 of A's spec) — meant to produce a JSON snapshot for "CEO Dashboard V1".
- §11 Q1 of A's spec explicitly left **open** what consumes that JSON. This spec resolves that: the consumer is `george.rotocon.world/roadmap`.
- A is **read-only**: mutations (adding columns to KI Integration) happen via standalone scripts in `scripts/`, not via the package.

**Artifact 3 — `https://george.rotocon.world/roadmap`** (web page):
- Currently a stub: returns HTTP 200 but body contains only the title "ROTOCON Cockpit".
- Tech stack not formally confirmed for this domain. The user has Webflow in his bookmark bar; assumed plausible but **not load-bearing** for this design — see §6.2.

**Strategic source** — `Tasks/ROTOCON_Job_Description_6_Month_Roadmap_English[94].pdf`. Defines M1–M6 milestones, KPIs, weekly CEO reporting cadence. The roadmap page mirrors these.

### 1.2 Problem statement (George's words)

> "KI Integration nu are gant tabel. etc... ar trebui sa comunice cu https://george.rotocon.world/roadmap"

Two needs:

| Need | What Phase 1a delivers |
|---|---|
| **N1 — Enrich the board** | KI Integration gains the columns and views needed for native Gantt + Table + KPI Cards inside monday. |
| **N2 — Feed the public page** | `/roadmap` reads a daily-refreshed `roadmap.json` and renders Gantt + Table + KPI strip. Read-only. |

---

## 2. Goals & non-goals

### Goals (Phase 1a — in scope)

1. **Board schema** — columns + groups + views on KI Integration so monday's native Gantt becomes meaningful and the board is the canonical roadmap source-of-truth.
2. **Export contract** — JSON shape that `monday export roadmap` produces (extension of sub-project A's `export dashboard`).
3. **Web consumption** — how `/roadmap` consumes the JSON and what views it renders.
4. **Daily sync cadence** — cron job emits a new `roadmap.json` once per day, site repo CI pulls it.

### Non-goals (deferred to sub-project B / Phases 1b–1d)

- ❌ **Two-way edits from the web.** Page is read-only in 1a. (Phase 1c.)
- ❌ **Real-time updates.** Daily refresh is sufficient for exec reporting. (Phase 1b.)
- ❌ **Q&E ERP integration.** KPI numerator values are entered manually into a board column in 1a. (Phase 1d.)
- ❌ **Webhook receiver / HTTP server.** No service runs from this repo in 1a; the CLI is invoked by cron. (Phase 1b.)
- ❌ **New authentication on the page.** Page is exec-only via whatever access control the domain already provides.
- ❌ **Replacement of A's CEO Dashboard JSON contract.** This extends it (adds `monday export roadmap` as a sibling command); it doesn't replace `monday export dashboard`.
- ❌ **Board mutations from the Python package.** Package stays read-only; board enrichment lives in `scripts/extend_ki_integration_columns.py`. Same boundary as sub-project A §2.

---

## 3. Scope decision — extend sub-project A, don't spin sub-project E

Two framings considered:

**Framing 1 — extends sub-project A.** "CEO Dashboard V1" remained vague in A's spec; this design supplies its concrete consumer. The CLI gains a new sibling command `monday export roadmap` producing a JSON shape tailored to the page.

**Framing 2 — new sub-project E.** "Public roadmap page" gets its own spec/plan, with A as a dependency.

**Choice: Framing 1.** Reason: the page is A's first concrete consumer. Treating it as a new sub-project would force an artificial dependency boundary across a function-level seam. The web-frontend implementation is small enough (one HTML file + one JSON file) to live as a sibling concern under A. Sub-project B will *itself* be the next sub-project, covering Phases 1b–1d.

---

## 4. Proposed board schema — KI Integration v2

### 4.1 New columns

Added by `scripts/extend_ki_integration_columns.py` (idempotent — running it on a board that already has the columns is a no-op).

| # | Title | monday `type` | Purpose | Settings / labels |
|---|---|---|---|---|
| 1 | `Status` | `status` | Workflow state | `Not started` (grey), `In progress` (blue), `Blocked` (red), `Done` (green), `Deferred` (purple) |
| 2 | `Phase` | `status` | Roadmap milestone | `M1`, `M2`, `M3`, `M4`, `M5`, `M6`, `Onboarding`, `Ongoing` |
| 3 | `Owner` | `people` | DRI for the item | — |
| 4 | `Timeline` | `timeline` | Start + end date — drives Gantt | — |
| 5 | `Due` | `date` | Discrete deadline for items without a range | — |
| 6 | `Priority` | `status` | RICE-style priority | `Critical`, `High`, `Medium`, `Low` |
| 7 | `KPI link` | `link` | URL to the metric / dashboard | — |
| 8 | `Dependency` | `dependency` | Other items this blocks / is blocked by | — |
| 9 | `% Progress` | `numbers` | Manual completion % | 0–100 |
| 10 | `Notes` | `long_text` | Free-form notes | — |
| 11 | `KPI target` | `text` | Target string (e.g., `60+ leads/month`) — populated only on KPI items | — |
| 12 | `KPI current` | `numbers` | Current measured value — populated only on KPI items in Phase 1a (manual). Phase 1d replaces with ERP feed. | — |

Per-column justification:

- `Status` + `Phase` + `Owner` + `Timeline` is the **four-field minimum** that any view resembling a roadmap requires.
- `Dependency` enables Gantt arrows (monday's Gantt reads this column natively).
- `KPI link` + `KPI target` + `KPI current` operationalize the KPI Tracking group. In 1a, `KPI current` is manually edited weekly during CEO reporting; in 1d it's replaced by an ERP-fed mirror/formula column.
- `Priority` orders the backlog inside a phase.
- `% Progress` fills the Gantt bar visually.

Column types verified against monday's public schema. Account tier `pro` (confirmed via smoke-test 2026-05-13) — all these column types are available.

### 4.2 Group → phase remapping

Existing groups stay; a `Phase` value is assigned per item:

| Existing group | Default `Phase` for items | Role in views |
|---|---|---|
| `Onboarding (Tag 1)` | `Onboarding` | Collapsed by default in Gantt |
| `Operatives Setup monday.com` | `M1` | Visible in Gantt |
| `4-Wochen Execution-Plan` | `M1`–`M2` (week 1–2 → M1, week 3–4 → M2) | Visible in Gantt |
| `KPI Tracking` | `Ongoing` | Hidden from Gantt; visible in KPI Cards |
| `AI Initiatives (M4–M6)` | `M4`–`M6` (parsed from item-title suffix `(M4)`/`(M5)`) | Visible in Gantt |

Page filters:
- **Gantt + Table sections**: `Phase ∈ {M1, M2, M3, M4, M5, M6}`.
- **KPI strip**: `Phase = Ongoing`.

### 4.3 Board views (created in monday)

Three native views, in addition to the default Table:

| View name | Type | Source | Audience |
|---|---|---|---|
| **Roadmap (Gantt)** | Gantt | `Timeline` + `Dependency` + `Status`; filter `Phase ∈ {M1..M6}` | Exec / page header |
| **Table (full)** | Table | All columns | Operators inside monday |
| **KPI Cards** | Cards or Kanban | Filter `Phase = Ongoing` | Exec / page KPI strip |

---

## 5. Data flow (Phase 1a)

```
KI Integration board (monday.com)
        │
        │ daily cron at 06:00 Europe/Berlin
        ▼
monday export roadmap --board 5096182046 --out roadmap.json
        │   (new CLI sibling of `monday export dashboard`, sub-project A §5.8)
        ▼
roadmap.json                              ← canonical artifact
        │
        │ site repo CI pulls (see §5.2)
        ▼
https://george.rotocon.world/roadmap      ← reads JSON at page load
        │
        ▼
Browser renders: KPI strip + Gantt + Table
```

### 5.1 JSON contract

```json
{
  "schema_version": "1",
  "generated_at": "2026-05-13T04:00:00Z",
  "source": {
    "account_slug": "rotocon-world",
    "board_id": "5096182046",
    "board_name": "KI Integration",
    "monday_url": "https://rotocon-world.monday.com/boards/5096182046"
  },
  "phases": [
    {
      "id": "M1",
      "label": "Month 1 — Operatives Setup",
      "items": [
        {
          "id": "2904971529",
          "name": "Leads-Board einrichten",
          "status": "In progress",
          "owner": { "id": "103121773", "name": "George Sebastian Cucuiet" },
          "timeline": { "start": "2026-05-15", "end": "2026-05-30" },
          "due": null,
          "priority": "High",
          "progress_pct": 30,
          "dependencies": [],
          "kpi_link": null,
          "notes": "",
          "monday_url": "https://rotocon-world.monday.com/boards/5096182046/pulses/2904971529"
        }
      ]
    }
  ],
  "kpis": [
    {
      "id": "kpi-1",
      "name": "Leads pro Monat",
      "target": "60+",
      "current": 23,
      "owner": { "id": "103121773", "name": "George Sebastian Cucuiet" },
      "status": "On track",
      "link": "https://..."
    }
  ]
}
```

`schema_version: "1"` is mandatory — the page consumer pins to it; we can evolve the shape (`"1.1"`, `"2"`) without breaking already-deployed pages.

### 5.2 How JSON reaches the site

Per Q6 = (A): **site repo's CI pulls from this repo on schedule.** Concretely:

1. This repo's CI (or a local cron on a server you own) runs `monday export roadmap` daily, commits the resulting `roadmap.json` to a known path in this repo (e.g., `out/roadmap.json`) or publishes it to a stable URL.
2. The site repo's CI fetches that artifact daily (e.g., before each deploy, or on schedule) and embeds it as a static asset.
3. Page reads the JSON at page-load via plain `fetch()`.

**Two concrete bindings** (pick the one that matches the site stack — decision deferred until §6.2 stack is confirmed):

- **Binding A — `roadmap.json` committed to this repo's `out/` directory.** Site repo pulls via a sparse-checkout or `wget https://raw.githubusercontent.com/...`. Simplest if site is a git-based static host (Cloudflare Pages, Netlify, GitHub Pages, etc.).
- **Binding B — `roadmap.json` uploaded to an asset bucket (S3, Cloudflare R2, Webflow asset).** Site fetches via fixed URL at page load. Simplest if site is Webflow (Webflow custom-code embed can `fetch()` the URL directly).

---

## 6. Roadmap page (frontend) — Phase 1a

### 6.1 Page layout

```
┌───────────────────────────────────────────────────────────┐
│ ROTOCON Cockpit › Roadmap                                 │
│ Last updated: 2026-05-13 04:00 UTC   [source: monday.com] │
├───────────────────────────────────────────────────────────┤
│ KPI strip                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Leads    │ │ Conv.    │ │ Quote    │ │ Auto-    │    │
│  │ 23 / 60+ │ │ 18%      │ │ < 72h    │ │ saving   │    │
│  │ ⚠ behind │ │ ⚠ behind │ │ ✅ ok    │ │ 12%      │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
├───────────────────────────────────────────────────────────┤
│ Gantt    M1 ── M2 ── M3 ── M4 ── M5 ── M6                 │
│  Leads-Board     ▰▰▰                                      │
│  Angebots-Board    ▰▰▰▰▰                                  │
│  Auftrags-Board       ▰▰▰▰                                │
│  AI Quotation                       ▰▰▰▰▰                 │
│  Smart Machine                            ▰▰▰▰▰           │
├───────────────────────────────────────────────────────────┤
│ Items table (filterable by phase, status, owner)          │
│ | Phase | Item                | Status     | Owner | Due |│
│ | M1    | Leads-Board einr…   | In progr.  | GC    | …   |│
│ | M1    | Angebots-Board einr…| Not started| GC    | …   |│
│ | …     | …                   | …          | …     | …   |│
└───────────────────────────────────────────────────────────┘
```

### 6.2 Stack — stack-agnostic deliverable

Q5 left the stack open. Phase 1a deliberately picks a stack-agnostic deliverable so it works regardless of what runs `george.rotocon.world`:

**A single self-contained `roadmap.html` file** (plus its asset folder):
- One HTML file with inline CSS + JS.
- Vendored dependencies: [`frappe-gantt`](https://github.com/frappe/gantt) (MIT, ~12 KB minified), Tailwind via CDN (or inlined).
- Reads `roadmap.json` from a configurable URL via `fetch()` at page load.
- No build step; no framework; no runtime dependencies beyond the browser.

This works as:
- A standalone page on a static host (Cloudflare Pages, S3, GitHub Pages).
- An embed inside Webflow via the Custom Code component or as a page-level embed.
- An iframe inside any other host.

**Decision deferred to implementation time**: which of the three deployment shapes to use, depending on what `george.rotocon.world` is actually serving. Implementation plan will probe the site's stack and pick.

### 6.3 Auth

Per Q3 = (C), audience is exec-only. The page itself adds no auth — relies on whatever access control the domain already provides (e.g., basic auth at the edge, IP allowlist, or no protection if the page is unlisted on a personal domain). Decision deferred to deploy time; calling out as a known gap for the implementation plan to handle.

---

## 7. Approach choice (audit trail)

Three approaches were considered during brainstorming. Choice: **Approach 2 (static export pipeline)**.

| Approach | Why rejected / chosen |
|---|---|
| 1 — Pure monday-native (Public Board View embedded via iframe) | Rejected: loses visual / brand control; monday chrome + watermark; KPI summarization clumsy. |
| **2 — Static export pipeline** ★ | **Chosen.** Full visual control; reuses sub-project A's CLI; page works even if monday API is down (cached JSON); easy to version. Daily cadence is sufficient per Q2's deferral. |
| 3 — Live API backend | Rejected for Phase 1a: requires a server (sub-project B territory). Will be re-evaluated for Phase 1b. |

---

## 8. Acceptance criteria

Phase 1a is "done" when **all** of the following hold:

1. KI Integration board has the 12 columns from §4.1 and the 3 views from §4.3.
2. `scripts/extend_ki_integration_columns.py` is idempotent — running it twice does not duplicate columns; running it on a fresh empty board adds them all.
3. All 29 existing items have at minimum `Phase`, `Status`, `Owner`, `Timeline` populated. (Data entry by George after script runs; a CSV-import template may be provided to speed this up.)
4. `monday export roadmap --board 5096182046 --out roadmap.json` produces a JSON validating against the §5.1 shape (schema-checked by Pydantic).
5. `roadmap.html` renders KPI strip + Gantt + Table against a real export of the board without console errors.
6. A daily cron / GitHub Action produces a fresh `roadmap.json` and makes it available at a known URL or path.
7. The site repo's CI consumes the new JSON and deploys the updated page.
8. `README.md` in this repo documents the end-to-end workflow.

---

## 9. Open follow-ups (for Phase 1b/1c/1d / sub-project B)

These don't gate Phase 1a, but should be captured so they aren't forgotten when sub-project B is brainstormed:

- **Phase 1b — Real-time refresh via monday webhooks.** monday supports webhook subscriptions on column-value changes and item creation. Sub-project B needs a webhook receiver (FastAPI) that invalidates the page's JSON cache.
- **Phase 1c — Two-way edits from the web.** Out of scope; will need authentication, a small write API to monday, and conflict resolution. Largest piece by far.
- **Phase 1d — Q&E ERP integration for KPI numerators.** Needs: (a) Q&E API discovery — does it have a REST/SOAP API, what auth? (b) ETL job that updates `KPI current` in the board on a schedule.

---

## 10. Next steps (after this spec is committed)

1. **You** read this revised spec end-to-end; confirm or request changes.
2. I commit it to git with status `APPROVED`.
3. I invoke `superpowers:writing-plans` skill to produce the implementation plan covering:
   - `scripts/extend_ki_integration_columns.py` (board mutations: 12 columns + 3 views, idempotent).
   - Data-entry checklist for the 29 items (or CSV-import shortcut).
   - `monday export roadmap` CLI command (extends sub-project A's `cli.py`).
   - Pydantic schema models for the JSON contract (in `monday_rotocon.models.roadmap`).
   - `roadmap.html` (vendored frappe-gantt; reads JSON via `fetch()`).
   - Daily cron / GitHub Action.
   - Site-repo integration step (deferred to implementation when site stack is known).
   - README updates.

---

## 11. Appendix — decision trace

| Decision | Reason |
|---|---|
| Path 1 (phased delivery) over single-step or mega-spec | Visible progress in 1-2 weeks; validates board schema before investing in webhooks/ERP; CEO weekly demo has content from day 1 |
| One-way sync, board is source-of-truth (Phase 1a) | monday is the operational tool; teams already edit there. Two-way deferred to 1c |
| Static JSON export over live API (Phase 1a) | Decouples site uptime from monday's; static is friendlier to whatever stack runs the site |
| Approach 2 over Approach 1 (no Public Board View iframe) | Visual / brand control matters for an exec page |
| Extend sub-project A rather than spinning sub-project E | Page is A's first real consumer; artificial decomposition would waste a planning cycle |
| `scripts/` for board enrichment, package stays read-only | Same boundary as sub-project A §2 |
| Schema version field in JSON contract | Allows page-side pinning; safe future evolution |
| Drop Onboarding (Tag 1) from Gantt by default | One-shot items would clutter a 6-month timeline view |
| Stack-agnostic frontend deliverable (single `roadmap.html`) | Q5 left stack open; this choice unblocks Phase 1a regardless of what serves the site |
| KPI numerator manual in 1a, ERP-fed in 1d | Q7 deferral; manual entry takes minutes/week and gives us real values to display now |

---

## Approval

Status: **APPROVED** (pending George's final read-through).

| Reviewer | Decision | Date | Notes |
|---|---|---|---|
| George S. Cucuiet | ⏳ Pending | 2026-05-13 | Path 1 chosen; Q1/Q2/Q7 deferred to sub-project B; Q3/Q4/Q6 resolved inline; Q5 stack provisionally stack-agnostic |

Next step after George's OK: invoke `superpowers:writing-plans` to author the implementation plan.
