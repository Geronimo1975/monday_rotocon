# monday-email-assistant — n8n build artifacts

Versioned source for the n8n workflow **`monday-email-assistant`** (id
`nVN78RTzTmYRVLLK`, on `n8n.rotocon.world`). The JS in `lib/` is unit-tested here,
then embedded into n8n **Code** nodes (function bodies are self-contained; no requires).

Email a question with `@ask_George` in the subject → the bot replies in-thread, in the
question's language, answering from live monday.com data with deterministic counts.

## Architecture (as built)

Single workflow, 14 nodes. **No Postgres** (n8n can't reach the DB — see
`memory/n8n_postgres_host_unreachable`) so the board/column catalog is built **live
from monday** each request. **Microsoft Outlook**, not Gmail, for trigger + reply (the
Gmail credential's OAuth is broken — see `memory/n8n_email_use_outlook_not_gmail`).

```
Outlook Trigger → Guard → Fetch Boards (monday) → Build Plan Request
  → Claude Plan (HTTP api.anthropic.com) → Validate Plan → IF Run Query?
    ├ true  → Fetch Items (monday) → Aggregate ┐
    └ false → Cannot Answer ─────────────────────┴→ Build Phrase Request
  → Claude Phrase (HTTP) → Build Reply (HTML + signature) → Send Reply (HTTP Graph reply, To asker, Cc george@)
```

| File | Where it is used |
|---|---|
| `lib/build-catalog.js` | embedded in Code node "Build Plan Request" |
| `lib/guard-question.js` | logic embedded in Code node "Guard" (`isQuestion`) |
| `lib/validate-plan.js` | embedded in Code node "Validate Plan" |
| `lib/aggregate.js` | embedded in Code node "Aggregate" (incl. `aggregateActivity`) |
| `lib/render-html.js` | embedded in Code node "Build Reply" (HTML reply + signature) |
| `prompts/plan-system.md` | system prompt sent by "Build Plan Request" → Claude Plan |
| `prompts/phrase-system.md` | system prompt sent by "Build Phrase Request" → Claude Phrase |
| `graphql/list-boards.graphql` | reference for the "Fetch Boards" query |
| `graphql/fetch-items.graphql` | reference for the "Fetch Items" query |

`sql/monday_schema_catalog.sql` is **retained for reference only** — unused while
Postgres is unreachable. If DB connectivity is restored, a cached catalog could
replace the live fetch.

Credentials used: Microsoft Outlook `7JEAzAMCDjKqDX3F`, Monday API Token
`NvEH5iJQgsGArHfy`, Anthropic `X1bQ9CnmsrWCLNte` (model `claude-sonnet-4-6`).

Run tests: `node --test n8n/monday-email-assistant/lib/*.test.js`

## HTML reply (2026-07-06)

Per `docs/superpowers/specs/2026-06-24-assistant-html-reply-design.md`:

- **Build Reply** embeds `lib/render-html.js`: greeting from the sender's
  local-part, escaped paragraphs, key-value bolding, `Sursa:` line only when
  provenance is non-empty (fixes `Sursa: null`), `Cu stimă,` + the ROTOCON
  signature (`SIGNATURE_FRAGMENT`, anti-drift-tested against
  `george_sebastian_cucuiet.html`).
- **Send Reply** is now an HTTP Request node:
  `POST graph.microsoft.com/v1.0/me/messages/{messageId}/reply` with
  `body.contentType = HTML` (the old `microsoftOutlook` node sent Text only).
- **Build Phrase Request** passes `result` + `provenance` through and its prompt
  no longer asks the LLM for a `Sursa:` line (chrome is deterministic).

## recent_activity aggregation (2026-07-06)

Questions like "ce s-a întâmplat săptămâna asta pe X?" plan to
`aggregation: recent_activity` (+ optional `activity_days`, default 7, clamp
1–90). Validate Plan builds `boards { updates(limit:100) { … } }` instead of
`items_page`; Aggregate windows/caps via `aggregateActivity` (30-row cap,
200-char bodies). Provenance becomes `<board> / updates`.
