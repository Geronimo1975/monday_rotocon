# HTML Reply with Signature — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `monday-email-assistant` bot reply as a polished HTML email — greeting by derived first name, minimal-clean body with the key value bolded, a source line only when provenance exists (fixing `Sursa: null`), then George's ROTOCON HTML signature.

**Architecture:** The LLM writes only the answer prose. A new tested module `lib/render-html.js` (embedded into the `Build Reply` Code node) composes all "chrome" — greeting, escaped paragraphs, key-value bolding, optional source line, closing, and the signature fragment. `Send Reply` is swapped from the plain-text Outlook `reply` node to a Microsoft Graph HTTP `reply` call with `contentType: HTML`.

**Tech Stack:** Node.js (CommonJS, `node --test`), n8n Code + HTTP Request nodes, Microsoft Graph API, Anthropic Messages API.

**Spec:** `docs/superpowers/specs/2026-06-24-assistant-html-reply-design.md`

**Live workflow:** `monday-email-assistant` (`nVN78RTzTmYRVLLK`) on `n8n.rotocon.world`, edited via the n8n MCP.

---

## File Structure

- Create `n8n/monday-email-assistant/lib/render-html.js` — pure render logic + signature constant (no `require`s; embeddable in a Code node).
- Create `n8n/monday-email-assistant/lib/render-html.test.js` — unit + anti-drift tests.
- Move `george_sebastian_cucuiet.html` → `n8n/monday-email-assistant/sig/signature.html` — canonical signature (lives with the workflow that uses it).
- Modify `n8n/monday-email-assistant/prompts/phrase-system.md` — trim to prose-only.
- Modify live nodes `Build Phrase Request`, `Build Reply`, and replace `Send Reply` (via n8n MCP).
- Modify `n8n/monday-email-assistant/README.md` — reflect HTML reply + new files/nodes.

---

## Task 1: Pure render helpers + `renderReplyHtml`

**Files:**
- Create: `n8n/monday-email-assistant/lib/render-html.js`
- Test: `n8n/monday-email-assistant/lib/render-html.test.js`

- [ ] **Step 1: Write the failing tests for the pure helpers**

Create `n8n/monday-email-assistant/lib/render-html.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert');
const { renderReplyHtml, greetingName, escapeHtml } = require('./render-html');

test('escapeHtml neutralizes HTML metacharacters', () => {
  assert.strictEqual(escapeHtml('a & b < c > d "e"'), 'a &amp; b &lt; c &gt; d &quot;e&quot;');
});

test('greetingName capitalizes a single-token local-part', () => {
  assert.strictEqual(greetingName('george@rotocon.world'), 'George');
});

test('greetingName returns null for dotted/numeric/empty local-parts', () => {
  assert.strictEqual(greetingName('c.steinroex@rotocon.world'), null);
  assert.strictEqual(greetingName('marco2@rotocon.world'), null);
  assert.strictEqual(greetingName(''), null);
});

test('greeting uses the name when present, falls back otherwise', () => {
  const withName = renderReplyHtml({ answerText: 'x', result: {}, provenance: '', from: 'george@rotocon.world' });
  assert.match(withName, /Bună ziua George,/);
  const noName = renderReplyHtml({ answerText: 'x', result: {}, provenance: '', from: 'c.steinroex@rotocon.world' });
  assert.match(noName, /Bună ziua,/);
  assert.doesNotMatch(noName, /Bună ziua [A-Z]/);
});

test('answer text is split into <p> blocks and escaped', () => {
  const html = renderReplyHtml({ answerText: 'Prima.\n\nA doua cu <tag>.', result: {}, provenance: '', from: 'george@rotocon.world' });
  assert.match(html, /<p style="[^"]*">Prima\.<\/p>/);
  assert.match(html, /A doua cu &lt;tag&gt;\./);
});

test('the key numeric value is bolded on its first occurrence', () => {
  const html = renderReplyHtml({ answerText: 'Sunt 42 de items deschise.', result: { aggregation: 'count', value: 42 }, provenance: '', from: 'george@rotocon.world' });
  assert.match(html, /Sunt <b>42<\/b> de items/);
});

test('no bolding for lists, group_count, empty, or answerable:false', () => {
  const list = renderReplyHtml({ answerText: 'Lista are 3 rânduri.', result: { aggregation: 'list', rows: [] }, provenance: '', from: 'george@rotocon.world' });
  assert.doesNotMatch(list, /<b>/);
  const cannot = renderReplyHtml({ answerText: 'Răspund doar la 1 subiect.', result: { answerable: false, value: 1 }, provenance: '', from: 'george@rotocon.world' });
  assert.doesNotMatch(cannot, /<b>/);
});

test('source line is present only when provenance is non-empty', () => {
  const withSrc = renderReplyHtml({ answerText: 'x', result: {}, provenance: 'board 123 · 24.06.2026', from: 'george@rotocon.world' });
  assert.match(withSrc, /Sursa: board 123 · 24\.06\.2026/);
  const noSrc = renderReplyHtml({ answerText: 'x', result: {}, provenance: '', from: 'george@rotocon.world' });
  assert.doesNotMatch(noSrc, /Sursa:/);
});

test('closing line is always present', () => {
  const html = renderReplyHtml({ answerText: 'x', result: {}, provenance: '', from: 'george@rotocon.world' });
  assert.match(html, /Cu stimă,/);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test n8n/monday-email-assistant/lib/render-html.test.js`
Expected: FAIL — `Cannot find module './render-html'`.

- [ ] **Step 3: Implement the module (signature constant left empty for now)**

Create `n8n/monday-email-assistant/lib/render-html.js`:

```js
// Composes the final HTML email reply: greeting, answer paragraphs (key value
// bolded), an optional source line, a closing, and George's ROTOCON signature.
// Self-contained (no requires) so the whole file can be pasted verbatim into the
// n8n "Build Reply" Code node. The test reads the canonical signature file; this
// module must never touch the filesystem.

const ANSWER_STYLE = 'font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#403E3D;';
const SOURCE_STYLE = 'font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.4;color:#888888;padding-top:6px;border-top:1px solid #C2BCB2;margin-top:14px;';

// Filled in Task 2 from sig/signature.html via extractSignatureFragment.
const SIGNATURE_FRAGMENT = '';

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function greetingName(from) {
  const local = String(from == null ? '' : from).trim().toLowerCase().split('@')[0];
  if (local.length > 0 && /^[a-zà-ÿ]+$/i.test(local)) {
    return local.charAt(0).toUpperCase() + local.slice(1);
  }
  return null;
}

// The bot-computed scalar value (count/sum/avg). Returns null for lists,
// group_count, empty results, or non-answerable questions so we never bold the
// wrong token.
function keyValueString(result) {
  if (!result || typeof result !== 'object') return null;
  if (result.answerable === false) return null;
  if (result.aggregation && result.aggregation !== 'count' && result.aggregation !== 'sum' && result.aggregation !== 'avg') return null;
  if (result.value == null) return null;
  if (typeof result.value === 'number') return String(result.value);
  if (typeof result.value === 'string' && result.value.trim() !== '') return result.value;
  return null;
}

function boldFirst(escapedText, rawValue) {
  if (!rawValue) return escapedText;
  const esc = escapeHtml(rawValue);
  const idx = escapedText.indexOf(esc);
  if (idx === -1) return escapedText;
  return escapedText.slice(0, idx) + '<b>' + esc + '</b>' + escapedText.slice(idx + esc.length);
}

// Extract the embeddable signature fragment (the <style> block + the inner markup
// of <body>) from the canonical full HTML document. Used by Task 2's generator
// and by the anti-drift test.
function extractSignatureFragment(fullHtml) {
  const styleMatch = String(fullHtml).match(/<style[\s\S]*?<\/style>/i);
  const bodyMatch = String(fullHtml).match(/<body[^>]*>([\s\S]*)<\/body>/i);
  const style = styleMatch ? styleMatch[0] : '';
  const body = bodyMatch ? bodyMatch[1] : '';
  return (style + '\n' + body).trim();
}

function renderReplyHtml({ answerText, result, provenance, from }) {
  const name = greetingName(from);
  const greeting = name ? ('Bună ziua ' + name + ',') : 'Bună ziua,';
  const kv = keyValueString(result);

  const paragraphs = String(answerText == null ? '' : answerText)
    .split(/\n\s*\n|\r?\n/)
    .map((p) => p.trim())
    .filter(Boolean);

  let bolded = false;
  const pHtml = paragraphs.map((p) => {
    let esc = escapeHtml(p);
    if (!bolded && kv) {
      const next = boldFirst(esc, kv);
      if (next !== esc) bolded = true;
      esc = next;
    }
    return '<p style="margin:0 0 12px 0;">' + esc + '</p>';
  }).join('');

  const source = (provenance != null && String(provenance).trim() !== '')
    ? '<div style="' + SOURCE_STYLE + '">Sursa: ' + escapeHtml(provenance) + '</div>'
    : '';

  const closing = '<p style="margin:18px 0 4px 0;">Cu stimă,</p>';

  return '<div style="' + ANSWER_STYLE + '">'
    + '<p style="margin:0 0 12px 0;">' + escapeHtml(greeting) + '</p>'
    + pHtml
    + source
    + closing
    + '</div>'
    + SIGNATURE_FRAGMENT;
}

module.exports = { renderReplyHtml, greetingName, keyValueString, boldFirst, escapeHtml, extractSignatureFragment };
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test n8n/monday-email-assistant/lib/render-html.test.js`
Expected: PASS (all helper/render tests green; signature is empty, which these tests don't assert on).

- [ ] **Step 5: Commit**

```bash
git add n8n/monday-email-assistant/lib/render-html.js n8n/monday-email-assistant/lib/render-html.test.js
git commit -m "feat(assistant): render-html module for HTML reply body"
```

---

## Task 2: Canonical signature + fragment constant + anti-drift test

**Files:**
- Move: `george_sebastian_cucuiet.html` → `n8n/monday-email-assistant/sig/signature.html`
- Modify: `n8n/monday-email-assistant/lib/render-html.js` (set `SIGNATURE_FRAGMENT`)
- Test: `n8n/monday-email-assistant/lib/render-html.test.js` (add anti-drift test)

- [ ] **Step 1: Move the signature into the workflow dir**

```bash
mkdir -p n8n/monday-email-assistant/sig
git mv george_sebastian_cucuiet.html n8n/monday-email-assistant/sig/signature.html 2>/dev/null \
  || mv george_sebastian_cucuiet.html n8n/monday-email-assistant/sig/signature.html
```
(If `git mv` fails because the file is untracked, the fallback `mv` runs; it gets added in Step 5.)

- [ ] **Step 2: Add the failing anti-drift test**

Append to `n8n/monday-email-assistant/lib/render-html.test.js`:

```js
const fs = require('node:fs');
const path = require('node:path');
const { extractSignatureFragment } = require('./render-html');
const render = require('./render-html');

test('SIGNATURE_FRAGMENT matches the canonical signature file (anti-drift)', () => {
  const file = fs.readFileSync(path.join(__dirname, '..', 'sig', 'signature.html'), 'utf8');
  const expected = extractSignatureFragment(file);
  // Re-render with a known input and assert the fragment is embedded verbatim.
  const html = render.renderReplyHtml({ answerText: 'x', result: {}, provenance: '', from: 'george@rotocon.world' });
  assert.ok(expected.length > 0, 'extracted fragment must be non-empty');
  assert.ok(html.endsWith(expected), 'rendered reply must end with the exact signature fragment');
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `node --test n8n/monday-email-assistant/lib/render-html.test.js`
Expected: FAIL — rendered reply ends with `''` (empty `SIGNATURE_FRAGMENT`), not the extracted fragment.

- [ ] **Step 4: Generate the fragment and paste it into the module**

Run (from repo root) to print the exact fragment:
```bash
node -e "const {extractSignatureFragment}=require('./n8n/monday-email-assistant/lib/render-html.js');const fs=require('fs');process.stdout.write(extractSignatureFragment(fs.readFileSync('n8n/monday-email-assistant/sig/signature.html','utf8')))" > /tmp/sig-fragment.txt
```
Then in `render-html.js` replace the line `const SIGNATURE_FRAGMENT = '';` with a backtick template literal containing the file's contents verbatim:
```js
const SIGNATURE_FRAGMENT = `<PASTE THE EXACT CONTENTS OF /tmp/sig-fragment.txt HERE>`;
```
The signature contains no backticks and no `${`, so a template literal is safe. Do not reformat or re-indent the pasted markup.

- [ ] **Step 5: Run the full lib suite to verify it passes**

Run: `node --test n8n/monday-email-assistant/lib/*.test.js`
Expected: PASS — all render tests plus the anti-drift test green; existing `guard`/`aggregate`/`validate-plan`/`build-catalog` suites still green.

- [ ] **Step 6: Commit**

```bash
git add n8n/monday-email-assistant/sig/signature.html n8n/monday-email-assistant/lib/render-html.js n8n/monday-email-assistant/lib/render-html.test.js
git commit -m "feat(assistant): embed ROTOCON signature fragment with anti-drift test"
```

---

## Task 3: Trim the phrase prompt to prose-only

**Files:**
- Modify: `n8n/monday-email-assistant/prompts/phrase-system.md`

- [ ] **Step 1: Replace the prompt body**

Overwrite `n8n/monday-email-assistant/prompts/phrase-system.md` with:

```markdown
You write the body of an email reply to a user question about monday.com data. You receive the QUESTION, a LANGUAGE code, and a RESULT that was computed deterministically from real rows. Never invent numbers; use exactly the values given in RESULT.

Write a short, direct answer of two to four sentences in the given language. State the number or list exactly as provided. If result.truncated is true, say the list was capped. If the result is empty, say so plainly. If answerable is false, say briefly that you only answer questions about monday.com data and, when present, mention the reason.

Do NOT write a greeting, a closing, a signature, or a source note — those are added automatically afterwards. Plain text only, no markdown, no asterisks for emphasis.
```

- [ ] **Step 2: Commit**

```bash
git add n8n/monday-email-assistant/prompts/phrase-system.md
git commit -m "feat(assistant): phrase prompt writes prose only (no greeting/source/signature)"
```

---

## Task 4: Update the `Build Phrase Request` node (pass-through metadata)

**Files:**
- Modify (live, via n8n MCP): node `Build Phrase Request` in workflow `nVN78RTzTmYRVLLK`.

The node must stop sending PROVENANCE to the LLM, use the trimmed prompt, and emit `result`, `provenance`, `from`, and `messageId` alongside `phraseBody` so `Build Reply` can read them from one node.

- [ ] **Step 1: Set the node's `jsCode` to**

```js
const result=$json.result;
const g=$('Guard').first().json;
const question=g.question;
const language=$('Validate Plan').first().json.language||'en';
const provenance=$('Validate Plan').first().json.provenance||'';
const system='You write the body of an email reply to a user question about monday.com data. You receive the QUESTION, a LANGUAGE code, and a RESULT that was computed deterministically from real rows. Never invent numbers; use exactly the values given in RESULT. Write a short, direct answer of two to four sentences in the given language. State the number or list exactly as provided. If result.truncated is true, say the list was capped. If the result is empty, say so plainly. If answerable is false, say briefly that you only answer questions about monday.com data and, when present, mention the reason. Do NOT write a greeting, a closing, a signature, or a source note — those are added automatically afterwards. Plain text only, no markdown, no asterisks for emphasis.';
const phraseBody={ model:'claude-sonnet-4-6', max_tokens:1024, system, messages:[{ role:'user', content: 'QUESTION: ' + question + ' === LANGUAGE: ' + language + ' === RESULT: ' + JSON.stringify(result) }] };
return [{ json: { phraseBody, result, provenance, from: g.from, messageId: g.messageId } }];
```

Apply via the n8n MCP `n8n_update_partial_workflow` (updateNode operation on `Build Phrase Request`, setting `parameters.jsCode`). Verify with `n8n_get_workflow` mode=filtered nodeNames=["Build Phrase Request"].

- [ ] **Step 2: Verify the node still feeds Claude Phrase**

Run: `n8n_validate_workflow` on `nVN78RTzTmYRVLLK`.
Expected: no new connection/expression errors introduced by this node.

---

## Task 5: Verification gate — confirm Graph `reply` renders HTML

**Files:** none (a throwaway probe against the live mailbox).

- [ ] **Step 1: Send a one-off HTML reply probe**

Using the n8n MCP, temporarily add (or use n8n's manual execution) an HTTP Request to Graph against the most recent `@ask_george` message id, with body:
```json
{ "message": { "body": { "contentType": "HTML", "content": "<p>probe <b>BOLD</b> <i>italic</i></p>" } } }
```
`POST https://graph.microsoft.com/v1.0/me/messages/{messageId}/reply`, auth `microsoftOutlookOAuth2Api`.

Alternatively run the probe directly with a Graph token if available. The goal is only to observe rendering.

- [ ] **Step 2: Inspect the received reply in george@'s mailbox**

Expected: `BOLD` renders bold and `italic` italic — i.e. the `reply` action honours `message.body` HTML.

- [ ] **Step 3: Decide the send path**

- If the probe rendered HTML → use the single-call `reply` node in Task 6 (the plan's default).
- If it rendered tags literally → in Task 6 use the fallback sequence instead: HTTP `POST …/createReply` → capture draft `id` → HTTP `PATCH …/messages/{id}` body `{ "body": { "contentType": "HTML", "content": "{{ html }}" } }` → HTTP `POST …/messages/{id}/send`. Record the chosen path in the README (Task 8).

- [ ] **Step 4: Remove the probe node** if one was added.

---

## Task 6: Update `Build Reply` and swap `Send Reply` to Graph HTML

**Files:**
- Modify (live, via n8n MCP): node `Build Reply`.
- Replace (live, via n8n MCP): node `Send Reply` with an HTTP Request to Graph.

- [ ] **Step 1: Set `Build Reply` `jsCode` to** (render-html.js inlined, then compose the Graph body)

```js
// ===== begin inlined lib/render-html.js =====
const ANSWER_STYLE = 'font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#403E3D;';
const SOURCE_STYLE = 'font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.4;color:#888888;padding-top:6px;border-top:1px solid #C2BCB2;margin-top:14px;';
const SIGNATURE_FRAGMENT = `<PASTE THE SAME FRAGMENT AS IN render-html.js>`;
function escapeHtml(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function greetingName(from){const local=String(from==null?'':from).trim().toLowerCase().split('@')[0];if(local.length>0&&/^[a-zà-ÿ]+$/i.test(local)){return local.charAt(0).toUpperCase()+local.slice(1);}return null;}
function keyValueString(result){if(!result||typeof result!=='object')return null;if(result.answerable===false)return null;if(result.aggregation&&result.aggregation!=='count'&&result.aggregation!=='sum'&&result.aggregation!=='avg')return null;if(result.value==null)return null;if(typeof result.value==='number')return String(result.value);if(typeof result.value==='string'&&result.value.trim()!=='')return result.value;return null;}
function boldFirst(escapedText,rawValue){if(!rawValue)return escapedText;const esc=escapeHtml(rawValue);const idx=escapedText.indexOf(esc);if(idx===-1)return escapedText;return escapedText.slice(0,idx)+'<b>'+esc+'</b>'+escapedText.slice(idx+esc.length);}
function renderReplyHtml(o){const answerText=o.answerText,result=o.result,provenance=o.provenance,from=o.from;const name=greetingName(from);const greeting=name?('Bună ziua '+name+','):'Bună ziua,';const kv=keyValueString(result);const paragraphs=String(answerText==null?'':answerText).split(/\n\s*\n|\r?\n/).map((p)=>p.trim()).filter(Boolean);let bolded=false;const pHtml=paragraphs.map((p)=>{let esc=escapeHtml(p);if(!bolded&&kv){const next=boldFirst(esc,kv);if(next!==esc)bolded=true;esc=next;}return '<p style="margin:0 0 12px 0;">'+esc+'</p>';}).join('');const source=(provenance!=null&&String(provenance).trim()!=='')?'<div style="'+SOURCE_STYLE+'">Sursa: '+escapeHtml(provenance)+'</div>':'';const closing='<p style="margin:18px 0 4px 0;">Cu stimă,</p>';return '<div style="'+ANSWER_STYLE+'">'+'<p style="margin:0 0 12px 0;">'+escapeHtml(greeting)+'</p>'+pHtml+source+closing+'</div>'+SIGNATURE_FRAGMENT;}
// ===== end inlined lib/render-html.js =====

const c=$json.content;
const answerText=(c && c[0] && c[0].text)?c[0].text:'(no reply generated)';
const meta=$('Build Phrase Request').first().json;
const cc=(String(meta.from).trim().toLowerCase()==='george@rotocon.world')?'':'george@rotocon.world';
const html=renderReplyHtml({ answerText, result: meta.result, provenance: meta.provenance, from: meta.from });
const message={ body:{ contentType:'HTML', content: html } };
if(cc){ message.ccRecipients=[{ emailAddress:{ address: cc } }]; }
return [{ json: { graphBody: { message }, messageId: meta.messageId } }];
```
Keep `SIGNATURE_FRAGMENT` byte-identical to `render-html.js` (the anti-drift test guards the file copy; this node copy must match it).

- [ ] **Step 2: Replace `Send Reply` with an HTTP Request node**

Configure (default single-call path from Task 5):
- Type: `n8n-nodes-base.httpRequest` (v4.4)
- Method: `POST`
- URL: `https://graph.microsoft.com/v1.0/me/messages/{{ $json.messageId }}/reply`
- Authentication: `predefinedCredentialType` → `microsoftOutlookOAuth2Api`, credential `7JEAzAMCDjKqDX3F`
- Send Body: on, `specifyBody: json`, `jsonBody`: `={{ JSON.stringify($json.graphBody) }}`
- `retryOnFail`: true

If Task 5 selected the fallback, wire `Build Reply → createReply (HTTP) → PATCH (HTTP) → send (HTTP)` instead, threading the draft `id` and using `{{ $json.graphBody.message.body.content }}` as the PATCH body content.

Apply via n8n MCP, keeping the connection `Build Reply → <new send node>`.

- [ ] **Step 3: Validate the workflow**

Run: `n8n_validate_workflow` on `nVN78RTzTmYRVLLK`.
Expected: no errors; the trigger→guard→…→send chain is intact.

---

## Task 7: Live smoke test

**Files:** none.

- [ ] **Step 1: Send a real answerable query**

From `george@rotocon.world`, email yourself: subject `@ask_george câte items sunt pe board <known board>`, with the question in the body.

- [ ] **Step 2: Inspect the execution**

Run: `n8n_executions` action=get on the newest execution, mode=full.
Expected: nodes past `Guard` execute (Plan → Validate → Fetch/Aggregate → Phrase → Build Reply → Send); `Send` returns 2xx.

- [ ] **Step 3: Inspect the received email**

Expected: greeting `Bună ziua George,`, the count bolded, a `Sursa:` line, `Cu stimă,`, then the ROTOCON signature card rendered (logo/medallion/contact).

- [ ] **Step 4: Send an unanswerable query** (e.g. the earlier "cash receipts per machine") and confirm **no** `Sursa: null` line appears.

---

## Task 8: Docs

**Files:**
- Modify: `n8n/monday-email-assistant/README.md`

- [ ] **Step 1: Update the README**

- State that the reply is now **HTML** (greeting + minimal-clean body + signature), not plain text.
- Add `lib/render-html.js` to the file table (embedded in `Build Reply`) and `sig/signature.html` as the canonical signature (anti-drift tested).
- Note `Send Reply` is now a Graph HTTP `reply` (record the path chosen in Task 5).
- Update the ASCII pipeline if node names changed.

- [ ] **Step 2: Commit**

```bash
git add n8n/monday-email-assistant/README.md
git commit -m "docs(assistant): README reflects HTML reply + signature"
```

---

## Self-Review notes

- **Spec coverage:** HTML reply (T6), greeting-from-email (T1), key-value bold (T1), `Sursa: null` fix — prompt no longer emits it (T3) and the source line is conditional (T1), signature embed + anti-drift (T2), Graph HTML send + verification gate (T5/T6), tests (T1/T2), README (T8). All spec sections mapped.
- **Type consistency:** `renderReplyHtml({ answerText, result, provenance, from })` and the `Build Reply`/`Build Phrase Request` pass-through keys (`result`, `provenance`, `from`, `messageId`, `graphBody`) are used identically across T1, T4, T6.
- **No placeholders:** the only "paste here" is the signature fragment, which is a deterministic extraction generated by an exact command and guarded by the anti-drift test — not an unspecified TODO.
