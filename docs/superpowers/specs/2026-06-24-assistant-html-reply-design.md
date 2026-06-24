# monday-email-assistant — HTML reply with signature

**Date:** 2026-06-24
**Status:** Approved (design)
**Scope:** `n8n/monday-email-assistant` workflow (`nVN78RTzTmYRVLLK` on `n8n.rotocon.world`)

## Problem

The bot's `@ask_george` reply is sent as **plain text** with no greeting and no
signature (commit `7420f22` forbade markdown because plain-text email rendered
`**` literally). George wants the reply to look like a polished, professional
email: a greeting addressed to the asker, a clean answer body, and his full
ROTOCON HTML signature.

A secondary bug is visible in production: when a question is *not* answerable the
reply ends with `Sursa: null`, because the phrase prompt always appends
`Sursa: <provenance>` even when `provenance` is empty.

## Goals

1. Bot replies are **HTML**, rendered correctly in the recipient's client.
2. Reply structure:
   ```
   Bună ziua <Prenume>,

   <answer: 2–4 sentences, key value bold>

   Sursa: <provenance>          ← only when provenance is non-empty

   Cu stimă,
   <ROTOCON HTML signature card>
   ```
3. Greeting name derived from the sender's email local-part, capitalized
   (`george@…` → `George`); fallback to bare `Bună ziua,` when the local-part is
   not name-like (contains a separator such as `.`, digits, or is empty).
4. Fix `Sursa: null` deterministically.
5. Visual richness is **minimal-clean**: sans-serif, airy paragraphs, the key
   value emphasised, a subtle source line. No lists, no tables in the body.

## Non-goals

- Widening the `ALLOW` sender list (tracked separately).
- Rich body formatting (lists, tables, headings) — explicitly out per YAGNI.
- Multipart/alternative (text + html). Graph `body` carries a single
  `contentType`; the recipient mailbox is Outlook, which renders HTML. Not needed.

## Design

### Separation of concerns

The robustness comes from moving all "chrome" off the LLM and onto deterministic
code:

- **`prompts/phrase-system.md` (and the inline copy in the `Build Phrase Request`
  Code node)** — the LLM writes **only** the answer prose: 2–4 sentences in the
  given language, stating numbers/lists exactly from `RESULT`, no greeting, no
  `Sursa:` line, no signature, plain text. This is a *reduction* of the current
  prompt's responsibilities.
- **`Build Reply` Code node** — composes the final HTML: greeting, escaped
  paragraphs, key-value bolding, the source line (only if provenance present),
  closing, and signature. Logic lives in `lib/render-html.js` (self-contained,
  no `require`s) and is embedded into the node, matching the repo pattern used by
  `aggregate.js` / `validate-plan.js` / `build-catalog.js`.

This also **fixes `Sursa: null`**: the source line is emitted by `Build Reply`
only when `provenance` is a non-empty string.

### `lib/render-html.js`

Exports `renderReplyHtml({ answerText, result, provenance, from })` → HTML string.

Responsibilities:
- **Greeting:** derive first name from `from` local-part. If the local-part is a
  single alphabetic token, capitalize it → `Bună ziua George,`. Otherwise emit
  `Bună ziua,`.
- **Body paragraphs:** split `answerText` on blank lines / newlines, HTML-escape
  each, wrap in `<p style="…">`. Escaping happens before any tag insertion.
- **Key-value bold:** when `result` carries a single scalar value (a count /
  number), wrap the first verbatim occurrence of that value's string in `<b>`
  *after* escaping. Skip when the result is empty, a list, or `answerable:false`.
  Best-effort — no bold if the value is not found.
- **Source line:** if `provenance` is non-empty, render
  `Sursa: <escaped provenance>` as a small muted line preceded by a thin divider.
- **Closing + signature:** `Cu stimă,` followed by `SIGNATURE_FRAGMENT`.
- Wrap the answer block in a minimal inline-styled container
  (`font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#403E3D;
  line-height:1.5`) consistent with the signature's palette.

### Signature handling

`george_sebastian_cucuiet.html` (repo root) is the **single source of truth**.
It is a complete HTML document; we cannot nest `<!DOCTYPE>/<html>/<head>` inside a
reply body. `render-html.js` holds `SIGNATURE_FRAGMENT` = the `<style>` block from
`<head>` plus the inner markup of `<body>`.

**Anti-drift guard:** a test reads `george_sebastian_cucuiet.html`, extracts the
same fragment (style + body inner), and asserts it equals `SIGNATURE_FRAGMENT`.
If the canonical file changes, the test fails until the constant is regenerated.

### Send Reply → Microsoft Graph (HTTP)

Production evidence (screenshot 2026-06-24: newlines preserved in the reply) shows
the current `microsoftOutlook` `reply` node sends body as **Text**. Feeding it
HTML would render tags literally. Replace `Send Reply` with an **HTTP Request**
node:

- `POST https://graph.microsoft.com/v1.0/me/messages/{{ $json.messageId }}/reply`
- Auth: `predefinedCredentialType` → `microsoftOutlookOAuth2Api` (existing
  credential `7JEAzAMCDjKqDX3F`), as the Anthropic nodes already do for their API.
- Body:
  ```json
  {
    "message": {
      "body": { "contentType": "HTML", "content": "<rendered html>" },
      "ccRecipients": [{ "emailAddress": { "address": "george@rotocon.world" } }]
    }
  }
  ```
  `ccRecipients` included only when the asker is not george@ (preserves current
  `Build Reply` cc logic). `reply` (not `replyAll`) keeps reply-to-sender-only.

**Verification gate (first implementation step):** send one reply containing a
known tag (e.g. `<b>test</b>`) via this node and confirm it renders as HTML in the
client. If the `reply` action does not honour `message.body`, fall back to the
documented sequence: `POST …/createReply` (draft) → `PATCH …/messages/{draftId}`
with `{ body: { contentType: "HTML", content } }` → `POST …/messages/{draftId}/send`
(2–3 nodes). Threading is preserved by `conversationId` in both paths.

## Testing

`lib/render-html.test.js` (`node --test`):
- HTML-escapes `& < > "` in answer text and provenance.
- Splits multi-paragraph answers into `<p>` blocks.
- Bolds the key value's first occurrence; no bold when value absent / list / empty.
- Omits the source line when `provenance` is empty/null; includes it otherwise.
- Greeting: capitalizes a single-token local-part; falls back to `Bună ziua,` for
  dotted/numeric/empty local-parts.
- `SIGNATURE_FRAGMENT` equals the fragment extracted from
  `george_sebastian_cucuiet.html` (anti-drift).

Existing suites (`guard`, `aggregate`, `validate-plan`, `build-catalog`) must stay
green.

## Rollout

1. Implement + test `lib/render-html.js` locally.
2. Trim `phrase-system.md` and the `Build Phrase Request` inline prompt.
3. Verification gate on Send Reply HTML rendering (pick node path).
4. Update `Build Reply` node with `render-html.js` body; swap Send Reply node.
5. Live smoke test: a real `@ask_george` self-query renders greeting + bold value +
   signature, and an unanswerable query no longer shows `Sursa: null`.
6. Update `README.md` (reply is now HTML; new files/nodes).

## Risks

- **Graph `reply`-with-body may not render HTML** → mitigated by the verification
  gate and the `createReply`→`PATCH`→`send` fallback.
- **Signature fragment drift** → mitigated by the anti-drift test.
- **Production workflow edit** on `n8n.rotocon.world` → apply via n8n MCP, smoke
  test immediately, keep the prompt/LLM contract unchanged beyond the trim.
