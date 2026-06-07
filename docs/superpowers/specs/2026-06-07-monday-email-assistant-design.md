# Monday Email Assistant ("mail chatbot") — Design

**Date:** 2026-06-07
**Status:** Approved (design phase)
**Author:** george@rotocon.world + Claude Code
**Related:** `2026-06-07-weekly-machine-email-report-design.md` (outbound email track;
this is the inbound, on-demand counterpart and reuses the same n8n + monday
infrastructure).

## Goal

An n8n workflow that turns a dedicated mailbox into a natural-language
question-answering service over monday.com. A team member emails a question in
plain language (any language) to `ask@rotocon.world` — e.g. *"Câte mașini am în
Germania?"* — and receives a reply, in the same thread and the same language,
answering from live monday data.

The defining requirement is **trustworthy counting**: aggregation questions
("how many…") must be answered by counting real rows, never by the LLM guessing.
The LLM translates the question into a constrained query plan; n8n executes it
deterministically and computes the aggregate; the LLM only phrases the result.

## Confirmed decisions

| Decision | Choice | Rationale |
|---|---|---|
| Data scope | **Whole monday workspace** | Maximum usefulness; any board is fair game. Handled via a cached board/column catalog the LLM picks from. |
| Answering engine | **LLM → structured plan → deterministic execution → LLM phrasing** | Counts/aggregates computed by n8n on real rows, not by the model. Safer than an agentic free-form loop. |
| Inbound mailbox | **Phased: test on `george+ask@` first, then dedicated `ask@rotocon.world`** | Test reuses george@'s existing mailbox + Gmail credential via a plus-alias (zero admin setup); production graduates to a dedicated mailbox. See "Phased delivery". |
| Authorization | **Explicit allowlist** | Bot returns internal data; only listed addresses get answers. Others ignored (optional polite refusal). Phase 0 allowlist = george@ only. |
| LLM provider | **Claude (Anthropic)** | Strong at structured (JSON) generation and multilingual phrasing. Requires a new Anthropic credential in n8n. |
| Reply language | **Mirror the question** | RO→RO, EN→EN, DE→DE. Natural for the multilingual team. |
| Q&A logging | **None** | No audit/history store for v1; ask-and-answer only. (Re-add later if debugging needs it.) |

## Phased delivery (test on george@ first)

The mailbox is the only piece needing Google Workspace admin work, so it is
deferred. We validate the whole pipeline on george@'s existing inbox first.

- **Phase 0 — Test (reuse george@):** the assistant listens on george@'s existing
  mailbox via the existing `Gmail account` credential (id `ahEoxGuMkBRjQ9YF`).
  Question emails are addressed to the **plus-alias `george+ask@rotocon.world`**
  (delivered to george@'s inbox); the Gmail Trigger filters on
  `to: george+ask@rotocon.world` so only those emails fire the workflow. The reply
  goes to `george@` (no `+ask`), so the bot's own reply never re-triggers it — no
  loop. Allowlist for the test = `george@rotocon.world` only.
  **Only new prerequisite for Phase 0: an Anthropic credential.** Gmail, Monday API,
  and Postgres credentials already exist.
- **Phase 1 — Production (dedicated mailbox):** swap to `ask@rotocon.world` and its
  own Gmail OAuth2 credential, and expand the allowlist to the team. This is a
  trigger-credential + recipient-filter change only — the plan/execute/phrase core
  is unchanged. The trigger's address filter is kept in one config node so the
  switch is a single edit.

## Prerequisites

**For Phase 0 (test):**
1. Add an **Anthropic** credential in n8n (API key). *Only blocker.*

**For Phase 1 (production), additionally:**
2. Create mailbox `ask@rotocon.world` in Google Workspace.
3. Add a **Gmail OAuth2** credential in n8n authenticated as `ask@rotocon.world`
   (separate from the existing `Gmail account` for george@, id `ahEoxGuMkBRjQ9YF`).

Reused existing credentials: `Gmail account` (gmailOAuth2, `ahEoxGuMkBRjQ9YF`, used
as-is in Phase 0), `Monday API Token` (httpHeaderAuth, `NvEH5iJQgsGArHfy`),
`Postgres account` (`l5HHFXvW5o8FdBkj`, for the schema-catalog cache only).
n8n instance: `https://n8n.rotocon.world`.

## Architecture

Two workflows.

### A. `monday-schema-catalog-refresh` (scheduled)

```
Schedule Trigger (cron: daily, e.g. 0 6 * * *, TZ Europe/Bucharest)
   ↓
List Boards (monday GraphQL — boards { id, name, columns { id, title, type, settings_str } })
   ↓
Build Catalog (Code — compact JSON: per board → columns with id/title/type and,
                for status/dropdown/country columns, the allowed label set)
   ↓
Upsert Catalog (Postgres — single row in rotocon_finance.monday_schema_catalog)
```

The catalog gives Claude the exact `board_id`, `column_id`, and label values it
must produce, so it never invents IDs and maps human terms ("Germania") to the
stored value ("Germany"/"DE"). Refreshed daily so new boards/columns appear
without code changes; the assistant reads the cache, never the live board list,
keeping per-question latency and API cost low.

### B. `monday-email-assistant` (the chatbot)

```
Gmail Trigger (polling; Phase 0: george@ inbox filtered to to:george+ask@,
                         Phase 1: ask@rotocon.world mailbox)
   ↓
Guard Sender (Code/IF — sender ∈ allowlist?)
   ├─ no → (optional) send polite refusal → STOP   (no data leaves)
   ↓ yes
Load Catalog (Postgres — read cached monday_schema_catalog JSON)
   ↓
Claude #1 — Plan (question + catalog → strict JSON query plan; see schema below)
   ↓
Validate Plan (Code — board_id ∈ catalog, column_ids exist, op ∈ allowlist,
                aggregation ∈ allowlist; answerable=false short-circuits to reply)
   ↓
Fetch Items (HTTP monday GraphQL — query BUILT FROM the plan, not from free text;
              board_id + select_columns, group_id if given, cursor pagination)
   ↓
Filter + Aggregate (Code — apply filters to real rows, compute count/avg/sum/list)
   ↓
Claude #2 — Phrase (question + structured result → answer in detected language)
   ↓
Send Reply (Gmail node — reply in the same thread; Phase 0 from george@, Phase 1 from ask@)
```

### Considered alternatives (rejected)

- **Agentic tool-use loop** (LLM calls monday API freely until it answers) — more
  flexible across odd questions, but non-deterministic counts and harder to bound;
  rejected in favour of plan-then-execute.
- **Live full-catalog fetch per request** — always fresh, but re-walking every board
  on each email is slow and costly; rejected in favour of the daily cache.
- **LLM emits raw GraphQL** — most flexible, but lets a crafted email steer arbitrary
  queries (prompt injection → data exfiltration) and reintroduces non-determinism;
  rejected in favour of a constrained, validated JSON plan.

## The query plan (contract between Claude #1 and n8n)

Claude #1 must return **only** this JSON. n8n rejects anything that fails validation.

```jsonc
{
  "answerable": true,                 // false → reply explains the limit, no query runs
  "reason": "",                       // when answerable=false, short human reason
  "language": "ro",                   // detected language of the question (BCP-47-ish)
  "board_id": 5086438002,             // MUST exist in the catalog
  "group_id": "topics",               // optional; null = all groups
  "filters": [                        // ANDed; each validated against catalog
    { "column_id": "country_mkxvqhys", "op": "equals", "value": "Germany" }
  ],
  "aggregation": "count",             // count | list | avg | sum | group_count
  "aggregation_column": null,         // required for avg/sum (must be numeric)
  "group_by_column": null,            // required for group_count
  "select_columns": ["name", "status", "country_mkxvqhys"]  // for list/context
}
```

**Validation rules (Validate Plan node):**
- `board_id` must be a key in the catalog; otherwise → answerable-false reply.
- every `column_id` (filters, aggregation, group_by, select) must exist on that board.
- `op` ∈ `{equals, not_equals, contains, gt, gte, lt, lte, is_empty, not_empty}`.
- `aggregation` ∈ `{count, list, avg, sum, group_count}`; avg/sum require a numeric
  `aggregation_column`; group_count requires `group_by_column`.
- `list` results are capped (e.g. 50 rows) to keep replies readable.

## Component detail

### Guard Sender
Reads the trigger's `from` address, lowercases, compares against an allowlist held
in **one config node** (initial: george@, Marco, Matthias, Renelda, Metin, Nicole).
Non-members: stop silently, or send a one-line "Sorry, this assistant only answers
the Rotocon team" — configurable. No monday call happens for non-members.

### Fetch Items
Builds the GraphQL query from the validated plan: `items_page(limit: 100)` on
`board_id`, requesting only `select_columns` (+ any filter/aggregation columns),
narrowed to `group_id` when present, following `cursor` for boards >100 items up to
a safety cap (e.g. 1000 items / 10 pages) — logged if the cap is hit so a truncated
answer is never silently presented as complete. Filtering is done in code (next
node), not via monday's `query_params`, because rule support varies by column type
and code filtering is uniform and testable.

### Filter + Aggregate
Normalises each item's column values to a flat object, applies the plan's filters,
then:
- `count` → integer.
- `avg`/`sum` → over `aggregation_column`, ignoring null/empty cells (report how many
  were skipped).
- `group_count` → map of `group_by_column` value → count.
- `list` → capped array of `select_columns`.

Emits a compact structured result `{ aggregation, value|rows|groups, matched, scanned,
truncated }`.

### Claude #2 — Phrase
Given the original question + the structured result (never raw board data), writes a
short, direct answer in `language`. Includes light provenance ("based on *Europe
Machine Overview*, Current Machines group"). If `truncated`, says so.

### Send Reply
Gmail node. Replies **in the same thread** (uses the trigger's
`threadId`/`Message-ID` → `In-Reply-To`/`References`). Plain text or light HTML; v1
plain text is fine. In Phase 0 it sends from george@ to george@ (no `+ask`), so the
reply does not match the `to:george+ask@` trigger filter and cannot re-trigger the
workflow. Phase 1 sends from the `ask@` credential.

## Security & safety

| Concern | Mitigation |
|---|---|
| Unauthorized data access | Explicit sender allowlist; non-members get no data. |
| Prompt injection in email body | Claude #1 only ever emits the constrained JSON plan; n8n builds the query itself and validates every field against the catalog. The email body can never become an executed query. |
| Sender spoofing | Out of scope for v1 (allowlist-by-From). If needed later, add SPF/DKIM verification on the mailbox. |
| Over-broad / scraping replies | `list` results capped; `truncated` flag surfaced; pagination cap enforced. |
| Hallucinated counts | Counts/aggregates computed in n8n on real rows; the LLM never produces the number. |

## Error handling

| Failure | Behaviour |
|---|---|
| Question not answerable from monday | `answerable:false` → reply explains what it can/can't do; no query runs. |
| Ambiguous board/column | Claude picks the best match; if genuinely unclear, returns answerable-false asking the user to rephrase (reply asks for clarification). |
| monday API rate limit / 5xx | n8n node retry (3×); persistent failure → reply "couldn't reach monday, try again shortly", thread preserved. |
| Empty result set | Valid answer: "0 machines match" / "none found" — not an error. |
| Catalog stale (board added today) | Daily refresh; a same-day new board may be unknown until next refresh — acceptable for v1. |
| Multiple questions in one email | v1 answers the primary question and notes it handled one; multi-question is a later enhancement. |

## Testing & rollout

1. Build both workflows **inactive**; validate via `n8n_validate_workflow` until clean.
2. Run `monday-schema-catalog-refresh` once; verify the catalog row covers the known
   boards and that `Europe Machine Overview` columns/labels are present.
3. Manual-run `monday-email-assistant` against sample inbound emails:
   - *"Câte mașini am în Germania?"* → integer matching a manual board count; reply in RO.
   - *"How many machines are critical?"* → matches Project Status = critical count; reply in EN.
   - *"Wie viele Maschinen sind in Phase FAT?"* → reply in DE.
   - An unanswerable question (e.g. "what's the weather?") → polite answerable-false reply.
   - A non-allowlisted sender → no data leaves (refusal or silence per config).
4. Verify replies thread correctly (land under the original email).
5. Spot-check 2 counts against the board manually.
6. All of the above runs in **Phase 0** (trigger on `george+ask@`, reusing the
   existing Gmail credential, allowlist = george@).
7. After sign-off on Phase 0: activate the catalog-refresh schedule and the Gmail
   trigger. Graduating to **Phase 1** (dedicated `ask@` mailbox + expanded allowlist)
   is a credential/recipient-filter swap done separately once the mailbox exists.

## Deliverables

1. n8n workflow `monday-schema-catalog-refresh` — inactive, validated, run once.
2. n8n workflow `monday-email-assistant` — inactive, validated, manually test-run on
   the sample questions above.
3. `rotocon_finance.monday_schema_catalog` table created (single-row JSON cache).
4. Allowlist + mailbox/credential wiring documented in the workflow's config node.
5. `MEMORY.md` entry for any non-obvious build decision.
6. Activation only after george@ signs off on the sample replies.

## Out of scope for v1

Multi-question emails; conversational follow-ups / memory across emails; charts or
rich HTML replies; Slack delivery of the same assistant; write actions (the assistant
is read-only over monday); sender-spoofing verification; Q&A audit logging.
