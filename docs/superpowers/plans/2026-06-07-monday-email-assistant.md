# Monday Email Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an n8n "mail chatbot" — email a natural-language question (subject contains `@ask`) and get a reply, in the same thread and language, answering from live monday.com data with deterministically-counted results.

**Architecture:** Two n8n workflows. (A) `monday-schema-catalog-refresh` walks the workspace daily and caches a compact board/column catalog in Postgres. (B) `monday-email-assistant` reads an inbound question, asks Claude for a *constrained JSON query plan*, validates it against the catalog, fetches matching monday items, **counts/aggregates in code (not in the LLM)**, then asks Claude to phrase the answer. The injection-critical validation and the aggregation are pure JS modules kept in the repo and unit-tested with `node --test`, then pasted into n8n Code nodes.

**Tech Stack:** n8n (built via the n8n MCP SDK), monday GraphQL API, Claude (Anthropic) nodes, Gmail nodes, Postgres; deterministic core in plain JavaScript tested with Node 22's built-in test runner.

**Spec:** `docs/superpowers/specs/2026-06-07-monday-email-assistant-design.md`

---

## Prerequisite gate (human, before Task 8)

- **Anthropic credential** must be added in n8n (API key). This is the only new
  credential and blocks the live test, not the build. Reused as-is: `Gmail account`
  (`ahEoxGuMkBRjQ9YF`), `Monday API Token` (`NvEH5iJQgsGArHfy`), `Postgres account`
  (`l5HHFXvW5o8FdBkj`). n8n instance: `https://n8n.rotocon.world`.

## File structure (repo-versioned artifacts)

All buildable pieces live under `n8n/monday-email-assistant/` so they are reviewable
and the JS logic is testable. The n8n workflows are *assembled* from these.

- `n8n/monday-email-assistant/README.md` — how each file maps to an n8n node.
- `n8n/monday-email-assistant/sql/monday_schema_catalog.sql` — Postgres DDL.
- `n8n/monday-email-assistant/lib/build-catalog.js` (+ `.test.js`) — board list → compact catalog.
- `n8n/monday-email-assistant/lib/validate-plan.js` (+ `.test.js`) — plan validation (injection guard).
- `n8n/monday-email-assistant/lib/aggregate.js` (+ `.test.js`) — filter + count/avg/sum/group_count/list.
- `n8n/monday-email-assistant/lib/guard-question.js` (+ `.test.js`) — `@ask` token + `Re:` loop guard.
- `n8n/monday-email-assistant/prompts/plan-system.md` — Claude #1 system prompt (NL → plan JSON).
- `n8n/monday-email-assistant/prompts/phrase-system.md` — Claude #2 system prompt (result → answer).
- `n8n/monday-email-assistant/graphql/fetch-items.graphql` — templated item fetch.
- `n8n/monday-email-assistant/graphql/list-boards.graphql` — catalog source query.

Each `lib/*.js` uses `module.exports` so its `.test.js` can require it; the same
function definition is pasted into the matching n8n Code node (the function body is
self-contained — no external requires — so it runs in n8n's sandbox). Run all tests
with: `node --test n8n/monday-email-assistant/lib/*.test.js`.

---

## Task 1: Scaffold the artifact directory

**Files:**
- Create: `n8n/monday-email-assistant/README.md`
- Create: `n8n/monday-email-assistant/.gitignore` (ignore `node_modules`, just in case)

- [ ] **Step 1: Create the README mapping artifacts to nodes**

Create `n8n/monday-email-assistant/README.md`:

```markdown
# monday-email-assistant — n8n build artifacts

Versioned source for two n8n workflows. The JS in `lib/` is unit-tested here, then
pasted into n8n **Code** nodes (function bodies are self-contained; no requires).

| File | n8n node it feeds |
|---|---|
| `sql/monday_schema_catalog.sql` | Postgres node in `monday-schema-catalog-refresh` |
| `graphql/list-boards.graphql` | HTTP Request (monday) in `monday-schema-catalog-refresh` |
| `lib/build-catalog.js` | Code node "Build Catalog" |
| `graphql/fetch-items.graphql` | HTTP Request (monday) in `monday-email-assistant` |
| `lib/guard-question.js` | IF/Code "Guard Question" |
| `lib/validate-plan.js` | Code node "Validate Plan" |
| `lib/aggregate.js` | Code node "Filter + Aggregate" |
| `prompts/plan-system.md` | Claude #1 (Plan) system prompt |
| `prompts/phrase-system.md` | Claude #2 (Phrase) system prompt |

Run tests: `node --test n8n/monday-email-assistant/lib/*.test.js`
```

- [ ] **Step 2: Create the .gitignore**

Create `n8n/monday-email-assistant/.gitignore`:

```
node_modules/
```

- [ ] **Step 3: Commit**

```bash
git add n8n/monday-email-assistant/README.md n8n/monday-email-assistant/.gitignore
git commit -m "chore(assistant): scaffold n8n email-assistant artifact dir"
```

---

## Task 2: Guard-question logic (`@ask` token + `Re:` loop guard)

**Files:**
- Create: `n8n/monday-email-assistant/lib/guard-question.js`
- Test: `n8n/monday-email-assistant/lib/guard-question.test.js`

- [ ] **Step 1: Write the failing test**

Create `n8n/monday-email-assistant/lib/guard-question.test.js`:

```javascript
const test = require('node:test');
const assert = require('node:assert');
const { isQuestion } = require('./guard-question');

test('plain @ask subject is a question', () => {
  assert.strictEqual(isQuestion('Câte mașini @ask'), true);
});

test('@ask anywhere in subject counts', () => {
  assert.strictEqual(isQuestion('@ask how many machines'), true);
});

test('subject without @ask is not a question', () => {
  assert.strictEqual(isQuestion('weekly report'), false);
});

test('the bot reply (Re: ... @ask) is ignored to break the loop', () => {
  assert.strictEqual(isQuestion('Re: Câte mașini @ask'), false);
});

test('case-insensitive Re: prefix is still ignored', () => {
  assert.strictEqual(isQuestion('RE: x @ask'), false);
});

test('missing/empty subject is not a question', () => {
  assert.strictEqual(isQuestion(undefined), false);
  assert.strictEqual(isQuestion(''), false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test n8n/monday-email-assistant/lib/guard-question.test.js`
Expected: FAIL — "Cannot find module './guard-question'".

- [ ] **Step 3: Write minimal implementation**

Create `n8n/monday-email-assistant/lib/guard-question.js`:

```javascript
// Treat an email as a question only when its subject contains the @ask token
// AND is not a reply (Re:). The Re: check drops the bot's own threaded reply,
// preventing an infinite loop when listening + replying on the same mailbox.
function isQuestion(subject) {
  const s = (subject || '').toString().trim();
  if (s === '') return false;
  if (/^re:/i.test(s)) return false;
  return s.toLowerCase().includes('@ask');
}

module.exports = { isQuestion };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test n8n/monday-email-assistant/lib/guard-question.test.js`
Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add n8n/monday-email-assistant/lib/guard-question.js n8n/monday-email-assistant/lib/guard-question.test.js
git commit -m "feat(assistant): guard-question @ask token + Re: loop guard"
```

---

## Task 3: Catalog builder (board list → compact catalog)

**Files:**
- Create: `n8n/monday-email-assistant/lib/build-catalog.js`
- Test: `n8n/monday-email-assistant/lib/build-catalog.test.js`

- [ ] **Step 1: Write the failing test**

Create `n8n/monday-email-assistant/lib/build-catalog.test.js`:

```javascript
const test = require('node:test');
const assert = require('node:assert');
const { buildCatalog } = require('./build-catalog');

const BOARDS = [
  {
    id: 5086438002,
    name: 'Europe Machine Overview',
    columns: [
      { id: 'name', title: 'Name', type: 'name', settings_str: '{}' },
      { id: 'status', title: 'Phase', type: 'status',
        settings_str: JSON.stringify({ labels: { '0': 'Backlog', '1': 'Done' } }) },
      { id: 'country_mkxvqhys', title: 'Country', type: 'country', settings_str: '{}' },
      { id: 'numeric_mm3x30na', title: 'Overall', type: 'numbers', settings_str: '{}' },
      { id: 'bad', title: 'Bad', type: 'status', settings_str: 'not-json' },
    ],
  },
];

test('indexes boards by string id', () => {
  const c = buildCatalog(BOARDS);
  assert.ok(c.boards['5086438002']);
  assert.strictEqual(c.boards['5086438002'].name, 'Europe Machine Overview');
});

test('keeps each column id/title/type', () => {
  const col = buildCatalog(BOARDS).boards['5086438002'].columns['numeric_mm3x30na'];
  assert.deepStrictEqual(col, { id: 'numeric_mm3x30na', title: 'Overall', type: 'numbers' });
});

test('extracts label set for status columns', () => {
  const col = buildCatalog(BOARDS).boards['5086438002'].columns['status'];
  assert.deepStrictEqual(col.labels.sort(), ['Backlog', 'Done']);
});

test('survives malformed settings_str without throwing', () => {
  const col = buildCatalog(BOARDS).boards['5086438002'].columns['bad'];
  assert.strictEqual(col.labels, undefined);
});

test('empty input yields empty catalog', () => {
  assert.deepStrictEqual(buildCatalog([]), { boards: {} });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test n8n/monday-email-assistant/lib/build-catalog.test.js`
Expected: FAIL — "Cannot find module './build-catalog'".

- [ ] **Step 3: Write minimal implementation**

Create `n8n/monday-email-assistant/lib/build-catalog.js`:

```javascript
// Turn monday's board+column listing into a compact catalog the LLM picks from.
// For label-bearing column types, include the allowed values so the model emits
// stored values ("Germany") rather than user phrasing ("Germania").
const LABELLED = new Set(['status', 'color', 'dropdown', 'country']);

function buildCatalog(boards) {
  const out = { boards: {} };
  for (const b of boards || []) {
    const columns = {};
    for (const c of b.columns || []) {
      const col = { id: c.id, title: c.title, type: c.type };
      if (LABELLED.has(c.type) && c.settings_str) {
        try {
          const s = JSON.parse(c.settings_str);
          if (s && s.labels) {
            col.labels = Object.values(s.labels).filter(Boolean);
          }
        } catch (e) {
          // malformed settings — skip labels, keep the column usable
        }
      }
      columns[c.id] = col;
    }
    out.boards[String(b.id)] = { id: String(b.id), name: b.name, columns };
  }
  return out;
}

module.exports = { buildCatalog };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test n8n/monday-email-assistant/lib/build-catalog.test.js`
Expected: PASS — 5 tests.

- [ ] **Step 5: Commit**

```bash
git add n8n/monday-email-assistant/lib/build-catalog.js n8n/monday-email-assistant/lib/build-catalog.test.js
git commit -m "feat(assistant): build-catalog board/column compaction"
```

---

## Task 4: Plan validation (the injection guard)

**Files:**
- Create: `n8n/monday-email-assistant/lib/validate-plan.js`
- Test: `n8n/monday-email-assistant/lib/validate-plan.test.js`

- [ ] **Step 1: Write the failing test**

Create `n8n/monday-email-assistant/lib/validate-plan.test.js`:

```javascript
const test = require('node:test');
const assert = require('node:assert');
const { validatePlan } = require('./validate-plan');

const CATALOG = {
  boards: {
    '5086438002': {
      id: '5086438002', name: 'Europe Machine Overview',
      columns: {
        status: { id: 'status', title: 'Phase', type: 'status' },
        country_mkxvqhys: { id: 'country_mkxvqhys', title: 'Country', type: 'country' },
        numeric_mm3x30na: { id: 'numeric_mm3x30na', title: 'Overall', type: 'numbers' },
      },
    },
  },
};

const okPlan = {
  answerable: true, language: 'ro', board_id: 5086438002, group_id: null,
  filters: [{ column_id: 'country_mkxvqhys', op: 'equals', value: 'Germany' }],
  aggregation: 'count', aggregation_column: null, group_by_column: null,
  select_columns: ['name', 'status'],
};

test('a well-formed count plan validates', () => {
  const r = validatePlan(okPlan, CATALOG);
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.errors.length, 0);
});

test('answerable:false short-circuits as ok (no query runs)', () => {
  const r = validatePlan({ answerable: false, reason: 'not in monday' }, CATALOG);
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.answerable, false);
});

test('unknown board_id is rejected', () => {
  const r = validatePlan({ ...okPlan, board_id: 999 }, CATALOG);
  assert.strictEqual(r.ok, false);
  assert.ok(r.errors.some((e) => e.includes('board')));
});

test('unknown filter column is rejected', () => {
  const r = validatePlan(
    { ...okPlan, filters: [{ column_id: 'evil', op: 'equals', value: 'x' }] }, CATALOG);
  assert.strictEqual(r.ok, false);
  assert.ok(r.errors.some((e) => e.includes('evil')));
});

test('disallowed operator is rejected', () => {
  const r = validatePlan(
    { ...okPlan, filters: [{ column_id: 'status', op: 'DROP', value: 'x' }] }, CATALOG);
  assert.strictEqual(r.ok, false);
});

test('avg without a numeric aggregation_column is rejected', () => {
  const r = validatePlan({ ...okPlan, aggregation: 'avg', aggregation_column: null }, CATALOG);
  assert.strictEqual(r.ok, false);
});

test('avg over a known numeric column validates', () => {
  const r = validatePlan(
    { ...okPlan, aggregation: 'avg', aggregation_column: 'numeric_mm3x30na' }, CATALOG);
  assert.strictEqual(r.ok, true);
});

test('group_count requires group_by_column', () => {
  const r = validatePlan({ ...okPlan, aggregation: 'group_count' }, CATALOG);
  assert.strictEqual(r.ok, false);
});

test('the pseudo-column "name" is always allowed', () => {
  const r = validatePlan(
    { ...okPlan, filters: [{ column_id: 'name', op: 'contains', value: 'ROT' }] }, CATALOG);
  assert.strictEqual(r.ok, true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test n8n/monday-email-assistant/lib/validate-plan.test.js`
Expected: FAIL — "Cannot find module './validate-plan'".

- [ ] **Step 3: Write minimal implementation**

Create `n8n/monday-email-assistant/lib/validate-plan.js`:

```javascript
// Validate the LLM's query plan against the catalog. This is the injection guard:
// n8n only ever executes plans whose board/columns/ops/aggregation are all known
// and allowed — a crafted email can never steer an arbitrary query.
const OPS = new Set([
  'equals', 'not_equals', 'contains', 'gt', 'gte', 'lt', 'lte', 'is_empty', 'not_empty',
]);
const AGGS = new Set(['count', 'list', 'avg', 'sum', 'group_count']);

function validatePlan(plan, catalog) {
  if (!plan || typeof plan !== 'object') {
    return { ok: false, errors: ['plan is not an object'] };
  }
  if (plan.answerable === false) {
    return { ok: true, errors: [], answerable: false };
  }

  const errors = [];
  const board = catalog.boards[String(plan.board_id)];
  if (!board) errors.push(`unknown board_id ${plan.board_id}`);

  const colOk = (c) => c === 'name' || (board && !!board.columns[c]);

  for (const f of plan.filters || []) {
    if (!colOk(f.column_id)) errors.push(`unknown filter column ${f.column_id}`);
    if (!OPS.has(f.op)) errors.push(`disallowed operator ${f.op}`);
  }

  if (!AGGS.has(plan.aggregation)) {
    errors.push(`disallowed aggregation ${plan.aggregation}`);
  }
  if (plan.aggregation === 'avg' || plan.aggregation === 'sum') {
    if (!plan.aggregation_column) errors.push('aggregation_column required for avg/sum');
    else if (!colOk(plan.aggregation_column)) {
      errors.push(`unknown aggregation_column ${plan.aggregation_column}`);
    }
  }
  if (plan.aggregation === 'group_count') {
    if (!plan.group_by_column) errors.push('group_by_column required for group_count');
    else if (!colOk(plan.group_by_column)) {
      errors.push(`unknown group_by_column ${plan.group_by_column}`);
    }
  }
  for (const c of plan.select_columns || []) {
    if (!colOk(c)) errors.push(`unknown select column ${c}`);
  }

  return { ok: errors.length === 0, errors, answerable: true };
}

module.exports = { validatePlan };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test n8n/monday-email-assistant/lib/validate-plan.test.js`
Expected: PASS — 9 tests.

- [ ] **Step 5: Commit**

```bash
git add n8n/monday-email-assistant/lib/validate-plan.js n8n/monday-email-assistant/lib/validate-plan.test.js
git commit -m "feat(assistant): validate-plan injection guard"
```

---

## Task 5: Filter + aggregate (deterministic counting)

**Files:**
- Create: `n8n/monday-email-assistant/lib/aggregate.js`
- Test: `n8n/monday-email-assistant/lib/aggregate.test.js`

- [ ] **Step 1: Write the failing test**

Create `n8n/monday-email-assistant/lib/aggregate.test.js`:

```javascript
const test = require('node:test');
const assert = require('node:assert');
const { normalizeItem, aggregate } = require('./aggregate');

// Raw monday items shape: { id, name, column_values: [{ id, text, value }] }
const RAW = [
  { id: '1', name: 'ROT200E', column_values: [
    { id: 'country_mkxvqhys', text: 'Germany', value: null },
    { id: 'numeric_mm3x30na', text: '60', value: '60' }] },
  { id: '2', name: 'ROT300', column_values: [
    { id: 'country_mkxvqhys', text: 'Germany', value: null },
    { id: 'numeric_mm3x30na', text: '80', value: '80' }] },
  { id: '3', name: 'ROT400', column_values: [
    { id: 'country_mkxvqhys', text: 'France', value: null },
    { id: 'numeric_mm3x30na', text: '', value: null }] },
];
const items = RAW.map(normalizeItem);

const base = { filters: [], aggregation: 'count', select_columns: ['name'] };

test('count of all items', () => {
  const r = aggregate(items, base);
  assert.strictEqual(r.value, 3);
  assert.strictEqual(r.matched, 3);
});

test('count with equals filter (Germany)', () => {
  const r = aggregate(items, {
    ...base, filters: [{ column_id: 'country_mkxvqhys', op: 'equals', value: 'Germany' }] });
  assert.strictEqual(r.value, 2);
});

test('equals is case-insensitive', () => {
  const r = aggregate(items, {
    ...base, filters: [{ column_id: 'country_mkxvqhys', op: 'equals', value: 'germany' }] });
  assert.strictEqual(r.value, 2);
});

test('avg ignores empty numeric cells and reports skipped', () => {
  const r = aggregate(items, {
    filters: [], aggregation: 'avg', aggregation_column: 'numeric_mm3x30na' });
  assert.strictEqual(r.value, 70); // (60 + 80) / 2
  assert.strictEqual(r.skipped, 1);
});

test('sum over numeric column', () => {
  const r = aggregate(items, {
    filters: [], aggregation: 'sum', aggregation_column: 'numeric_mm3x30na' });
  assert.strictEqual(r.value, 140);
});

test('group_count by country', () => {
  const r = aggregate(items, {
    filters: [], aggregation: 'group_count', group_by_column: 'country_mkxvqhys' });
  assert.deepStrictEqual(r.groups, { Germany: 2, France: 1 });
});

test('gt on numeric column', () => {
  const r = aggregate(items, {
    ...base, filters: [{ column_id: 'numeric_mm3x30na', op: 'gt', value: '70' }] });
  assert.strictEqual(r.value, 1); // only 80
});

test('list returns capped rows with selected columns and name', () => {
  const r = aggregate(items, {
    filters: [{ column_id: 'country_mkxvqhys', op: 'equals', value: 'Germany' }],
    aggregation: 'list', select_columns: ['name', 'numeric_mm3x30na'] });
  assert.strictEqual(r.rows.length, 2);
  assert.deepStrictEqual(r.rows[0], { name: 'ROT200E', numeric_mm3x30na: '60' });
  assert.strictEqual(r.truncated, false);
});

test('list truncates above the 50-row cap', () => {
  const many = Array.from({ length: 60 }, (_, i) =>
    normalizeItem({ id: String(i), name: 'M' + i, column_values: [] }));
  const r = aggregate(many, { filters: [], aggregation: 'list', select_columns: ['name'] });
  assert.strictEqual(r.rows.length, 50);
  assert.strictEqual(r.truncated, true);
});

test('filter on the name pseudo-column', () => {
  const r = aggregate(items, {
    ...base, filters: [{ column_id: 'name', op: 'contains', value: 'rot2' }] });
  assert.strictEqual(r.value, 1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test n8n/monday-email-assistant/lib/aggregate.test.js`
Expected: FAIL — "Cannot find module './aggregate'".

- [ ] **Step 3: Write minimal implementation**

Create `n8n/monday-email-assistant/lib/aggregate.js`:

```javascript
// Deterministic filter + aggregation over real monday rows. The LLM never produces
// the number — this code does, so counts cannot be hallucinated.
const LIST_CAP = 50;

function normalizeItem(item) {
  const cols = {};
  for (const cv of item.column_values || []) {
    cols[cv.id] = { text: cv.text == null ? '' : String(cv.text), value: cv.value };
  }
  return { id: item.id, name: item.name || '', cols };
}

function cellText(item, columnId) {
  if (columnId === 'name') return item.name || '';
  const cell = item.cols[columnId];
  return cell ? cell.text : '';
}

function matchFilter(item, f) {
  const text = cellText(item, f.column_id);
  const lower = text.toLowerCase();
  const target = (f.value == null ? '' : String(f.value)).toLowerCase();
  const num = parseFloat(text);
  const tnum = parseFloat(target);
  switch (f.op) {
    case 'equals': return lower === target;
    case 'not_equals': return lower !== target;
    case 'contains': return lower.includes(target);
    case 'gt': return !isNaN(num) && num > tnum;
    case 'gte': return !isNaN(num) && num >= tnum;
    case 'lt': return !isNaN(num) && num < tnum;
    case 'lte': return !isNaN(num) && num <= tnum;
    case 'is_empty': return text.trim() === '';
    case 'not_empty': return text.trim() !== '';
    default: return false;
  }
}

function aggregate(items, plan) {
  const filters = plan.filters || [];
  const matched = items.filter((it) => filters.every((f) => matchFilter(it, f)));
  const out = {
    aggregation: plan.aggregation,
    matched: matched.length,
    scanned: items.length,
    truncated: false,
  };

  if (plan.aggregation === 'count') {
    out.value = matched.length;
  } else if (plan.aggregation === 'avg' || plan.aggregation === 'sum') {
    const nums = matched
      .map((it) => parseFloat(cellText(it, plan.aggregation_column)))
      .filter((n) => !isNaN(n));
    out.skipped = matched.length - nums.length;
    const sum = nums.reduce((a, b) => a + b, 0);
    out.value = plan.aggregation === 'sum' ? sum : (nums.length ? sum / nums.length : null);
  } else if (plan.aggregation === 'group_count') {
    const groups = {};
    for (const it of matched) {
      const key = cellText(it, plan.group_by_column) || '(empty)';
      groups[key] = (groups[key] || 0) + 1;
    }
    out.groups = groups;
  } else if (plan.aggregation === 'list') {
    out.truncated = matched.length > LIST_CAP;
    out.rows = matched.slice(0, LIST_CAP).map((it) => {
      const row = { name: it.name };
      for (const c of plan.select_columns || []) {
        if (c !== 'name') row[c] = cellText(it, c);
      }
      return row;
    });
  }
  return out;
}

module.exports = { normalizeItem, cellText, matchFilter, aggregate };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test n8n/monday-email-assistant/lib/aggregate.test.js`
Expected: PASS — 10 tests.

- [ ] **Step 5: Run the whole suite and commit**

Run: `node --test n8n/monday-email-assistant/lib/*.test.js`
Expected: PASS — all four lib modules (43 tests total after review hardening).

```bash
git add n8n/monday-email-assistant/lib/aggregate.js n8n/monday-email-assistant/lib/aggregate.test.js
git commit -m "feat(assistant): deterministic filter + aggregate"
```

---

## Task 6: Prompts, GraphQL, and DDL artifacts

**Files:**
- Create: `n8n/monday-email-assistant/prompts/plan-system.md`
- Create: `n8n/monday-email-assistant/prompts/phrase-system.md`
- Create: `n8n/monday-email-assistant/graphql/list-boards.graphql`
- Create: `n8n/monday-email-assistant/graphql/fetch-items.graphql`
- Create: `n8n/monday-email-assistant/sql/monday_schema_catalog.sql`

- [ ] **Step 1: Write the Plan system prompt**

Create `n8n/monday-email-assistant/prompts/plan-system.md`:

```markdown
You translate a user's natural-language question about monday.com data into a
STRICT JSON query plan. You do NOT answer the question and you do NOT count.

You receive: (1) the question text, (2) a CATALOG of boards and their columns
(with allowed label values for status/dropdown/country columns).

Return ONLY a JSON object, no prose, with exactly these keys:
{
  "answerable": boolean,        // false if the question cannot be answered from the catalog
  "reason": string,             // when answerable=false, a short human reason
  "language": string,           // the question's language, e.g. "ro", "en", "de"
  "board_id": number,           // MUST be an id present in the catalog
  "group_id": string|null,      // optional group filter, else null
  "filters": [                  // ANDed; [] for none
    { "column_id": string, "op": string, "value": string }
  ],
  "aggregation": string,        // one of: count | list | avg | sum | group_count
  "aggregation_column": string|null,  // required for avg/sum, must be a numbers column
  "group_by_column": string|null,     // required for group_count
  "select_columns": string[]    // columns to show for list/context; may include "name"
}

Rules:
- op is one of: equals, not_equals, contains, gt, gte, lt, lte, is_empty, not_empty.
- Use ONLY column_id values that exist on the chosen board in the catalog. Never invent ids.
- For status/country/dropdown filters, map the user's wording to an EXACT label from
  the catalog (e.g. "Germania"/"Germany" -> the stored value, "în Germania" -> equals that value).
- "How many ..." -> aggregation "count". "Average/medie ..." -> "avg" on the numbers column.
- If the question is not answerable from monday data, set answerable=false and explain in reason.
- Detect the question's language and put it in "language". Output JSON only.
```

- [ ] **Step 2: Write the Phrase system prompt**

Create `n8n/monday-email-assistant/prompts/phrase-system.md`:

```markdown
You write the final email reply to a user's question about monday.com data.

You receive: (1) the original question, (2) a STRUCTURED RESULT computed
deterministically from real rows (never invent numbers — use exactly what is given),
(3) a "language" code and a "provenance" string (board/group the data came from).

Write a short, direct answer (2-4 sentences) in the given language. State the number
or list exactly as provided. If "truncated" is true, say the list was capped. If the
result is empty, say so plainly. End with a one-line provenance note, e.g.
"Sursa: Europe Machine Overview · Current Machines". No greeting boilerplate, no
signature. Plain text.
```

- [ ] **Step 3: Write the list-boards GraphQL**

Create `n8n/monday-email-assistant/graphql/list-boards.graphql`:

```graphql
query ($page: Int!) {
  boards(limit: 50, page: $page, state: active) {
    id
    name
    columns {
      id
      title
      type
      settings_str
    }
  }
}
```

- [ ] **Step 4: Write the fetch-items GraphQL**

Create `n8n/monday-email-assistant/graphql/fetch-items.graphql`:

```graphql
query ($boardId: ID!, $cursor: String, $columnIds: [String!]) {
  boards(ids: [$boardId]) {
    items_page(limit: 100, cursor: $cursor) {
      cursor
      items {
        id
        name
        group { id title }
        column_values(ids: $columnIds) {
          id
          text
          value
        }
      }
    }
  }
}
```

- [ ] **Step 5: Write the catalog DDL**

Create `n8n/monday-email-assistant/sql/monday_schema_catalog.sql`:

```sql
-- Single-row cache of the workspace board/column catalog, refreshed daily.
CREATE TABLE IF NOT EXISTS rotocon_finance.monday_schema_catalog (
  id          INT PRIMARY KEY DEFAULT 1,
  catalog     JSONB NOT NULL,
  board_count INT NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT monday_schema_catalog_singleton CHECK (id = 1)
);
```

- [ ] **Step 6: Commit**

```bash
git add n8n/monday-email-assistant/prompts n8n/monday-email-assistant/graphql n8n/monday-email-assistant/sql
git commit -m "feat(assistant): prompts, GraphQL, and catalog DDL artifacts"
```

---

## Task 7: Build workflow A — `monday-schema-catalog-refresh` (n8n MCP)

This task uses the n8n MCP (claude.ai n8n server). No repo files change; the
deliverable is a validated, manually-run n8n workflow that writes the catalog row.

- [ ] **Step 1: Read the SDK reference**

Call `mcp__claude_ai_n8n__get_sdk_reference` (sections: default, then "guidelines"
and "design"). This is required before writing workflow code.

- [ ] **Step 2: Discover the nodes**

Call `mcp__claude_ai_n8n__search_nodes` with queries:
`["schedule trigger", "http request", "code", "postgres"]`. Note the
resource/operation discriminators returned.

- [ ] **Step 3: Get exact type definitions**

Call `mcp__claude_ai_n8n__get_node_types` with ALL node ids from Step 2 (schedule
trigger, httpRequest, code, postgres). Use the exact parameter names it returns.

- [ ] **Step 4: Write the workflow SDK code**

Build `monday-schema-catalog-refresh` with this node chain:
1. **Schedule Trigger** — cron `0 6 * * *`, timezone `Europe/Bucharest`.
2. **Postgres (ensure table)** — run the DDL from
   `n8n/monday-email-assistant/sql/monday_schema_catalog.sql` (CREATE TABLE IF NOT EXISTS).
   Credential: `Postgres account` (`l5HHFXvW5o8FdBkj`).
3. **HTTP Request → monday (paginate boards)** — POST `https://api.monday.com/v2`,
   header auth `Monday API Token` (`NvEH5iJQgsGArHfy`), body = the query from
   `graphql/list-boards.graphql` with `page` starting at 1; loop pages until an empty
   `boards` array (use a Code-node loop or n8n pagination). Collect all boards.
4. **Code "Build Catalog"** — paste the `buildCatalog` function body from
   `lib/build-catalog.js`; input = the collected boards array; output =
   `{ catalog, board_count }`.
5. **Postgres (upsert)** — `INSERT INTO rotocon_finance.monday_schema_catalog
   (id, catalog, board_count, updated_at) VALUES (1, $1, $2, now())
   ON CONFLICT (id) DO UPDATE SET catalog = EXCLUDED.catalog,
   board_count = EXCLUDED.board_count, updated_at = now();`

Create the workflow **inactive** (do not set active).

- [ ] **Step 5: Validate**

Call `mcp__claude_ai_n8n__validate_workflow` with the full code. Fix every error and
re-validate until clean.

- [ ] **Step 6: Create**

Call `mcp__claude_ai_n8n__create_workflow_from_code` with a `description`:
"Daily cache of the monday workspace board/column catalog for the email assistant."

- [ ] **Step 7: Manual run and verify the cache row**

Trigger one manual execution. Then verify in Postgres:
`SELECT board_count, updated_at, jsonb_object_keys(catalog->'boards') FROM rotocon_finance.monday_schema_catalog;`
Expected: one row; `board_count` > 0; `Europe Machine Overview` (`5086438002`) appears
among the board keys with its columns. Spot-check that `status` has a `labels` array.

- [ ] **Step 8: Record the workflow id**

Note the returned workflow id in `n8n/monday-email-assistant/README.md` under a new
"Deployed workflow ids" section and commit:

```bash
git add n8n/monday-email-assistant/README.md
git commit -m "docs(assistant): record catalog-refresh workflow id"
```

---

## Task 8: Build workflow B — `monday-email-assistant` (n8n MCP)

**Requires the Anthropic credential to exist** (prerequisite gate). Builds the
chatbot workflow. Deliverable: a validated, inactive workflow.

- [ ] **Step 1: Discover the additional nodes**

Call `mcp__claude_ai_n8n__search_nodes` with
`["gmail trigger", "gmail", "anthropic", "if", "code", "http request", "postgres"]`.
Then `mcp__claude_ai_n8n__get_node_types` for all of them. Use exact parameter names.

- [ ] **Step 2: Write the workflow SDK code**

Build `monday-email-assistant` with this chain (create **inactive**):

1. **Gmail Trigger** — credential `Gmail account` (`ahEoxGuMkBRjQ9YF`), poll the inbox.
2. **Code "Guard Question"** — paste `isQuestion` from `lib/guard-question.js`; pass
   the email `subject`. If false → stop (no further nodes). (Use an IF node on
   `isQuestion(subject)` to branch to a NoOp end.)
3. **Code "Guard Sender"** — allowlist array in this node, Phase 0 =
   `['george@rotocon.world']`. If `from` not in allowlist → stop.
4. **Postgres "Load Catalog"** — `SELECT catalog FROM rotocon_finance.monday_schema_catalog WHERE id = 1;`
5. **Anthropic "Claude #1 Plan"** — system prompt from `prompts/plan-system.md`; user
   message = the question + the catalog JSON; model = your chosen Claude model;
   `response_format`/instruction = JSON only. Parse its output to an object `plan`.
6. **Code "Validate Plan"** — paste `validatePlan` from `lib/validate-plan.js`; input
   `plan` + `catalog`. If `answerable === false` OR `ok === false` → route to the
   Phrase step with a structured "cannot answer" result (skip fetch/aggregate).
7. **HTTP Request "Fetch Items"** — POST monday GraphQL using `graphql/fetch-items.graphql`,
   variables `boardId` from the plan, `columnIds` = union of filter/aggregation/
   group_by/select columns (minus `name`), follow `cursor` until null or a 10-page /
   1000-item cap; mark `truncated` if the cap is hit.
8. **Code "Filter + Aggregate"** — paste `normalizeItem` + helpers + `aggregate` from
   `lib/aggregate.js`. First, if `plan.group_id` is set, keep only raw items where
   `item.group.id === plan.group_id` (the fetch query already returns `group { id }`).
   Then map the remaining raw items via `normalizeItem` and call
   `aggregate(items, plan)`. Carry `truncated` from the fetch step into the result.
9. **Anthropic "Claude #2 Phrase"** — system prompt from `prompts/phrase-system.md`;
   user message = question + the structured result + `language` + provenance
   (board name + group). Output = the reply text.
10. **Code "Build Recipients"** — `to = from`; `cc = (from === 'george@rotocon.world')
    ? '' : 'george@rotocon.world'`.
11. **Gmail "Send Reply"** — credential `Gmail account`; reply in the same thread
    (set `In-Reply-To`/`References` / threadId from the trigger), `To` = recipients.to,
    `Cc` = recipients.cc, subject = `Re: <original subject>`, body = the reply text.

- [ ] **Step 3: Validate**

Call `mcp__claude_ai_n8n__validate_workflow`; fix until clean.

- [ ] **Step 4: Create**

Call `mcp__claude_ai_n8n__create_workflow_from_code` with `description`:
"Inbound email chatbot: answers natural-language questions over monday via a
validated query plan and deterministic aggregation."

- [ ] **Step 5: Record the workflow id**

Append the id to the README "Deployed workflow ids" section and commit:

```bash
git add n8n/monday-email-assistant/README.md
git commit -m "docs(assistant): record email-assistant workflow id"
```

---

## Task 9: Live end-to-end test (human-in-the-loop)

Verifies the assembled workflow against real emails. Requires the Anthropic
credential and that you (george@) send the test emails.

- [ ] **Step 1: Pin a sample question and dry-run nodes**

Use `mcp__claude_ai_n8n__prepare_test_pin_data` / `test_workflow` to pin a sample
Gmail-trigger item with subject `Câte mașini @ask` and body
`Câte mașini am în Germania?`, then run the workflow once without waiting for a real
poll. Confirm each node passes data forward.

- [ ] **Step 2: Real email — count question (RO)**

Send (from george@) an email to george@ with subject `Câte mașini @ask`, body
`Câte mașini am în Germania?`. Expected: a threaded reply in Romanian with an integer
matching a manual board count of Current Machines whose Country = Germany. No Cc dup
(asker is george@).

- [ ] **Step 3: Verify the count manually**

In monday, filter `Europe Machine Overview` → Current Machines by Country = Germany.
Confirm the reply's number equals that count.

- [ ] **Step 4: Real email — critical count (EN)**

Subject `@ask critical`, body `How many machines are critical?`. Expected: English
reply; number equals Project Status = critical count.

- [ ] **Step 5: Real email — unanswerable**

Subject `@ask weather`, body `What's the weather in Munich?`. Expected: a polite reply
that it only answers monday questions (answerable=false path). No monday query runs.

- [ ] **Step 6: Loop guard check**

Confirm that after any reply lands (`Re: … @ask`), no second execution is triggered
(check the n8n execution log shows one run per question, not a loop).

- [ ] **Step 7: Non-allowlisted sender (optional)**

If feasible, send from a non-allowlisted address. Expected: no data reply (silence or
the configured refusal).

- [ ] **Step 8: Iterate**

Fix any prompt/logic issues. If a `lib/*.js` function changes, update the repo file,
re-run `node --test n8n/monday-email-assistant/lib/`, re-paste into the node, and
commit the repo change.

---

## Task 10: Activation and memory

- [ ] **Step 1: Activate after sign-off**

Once Task 9 passes and you approve: set both workflows active
(`mcp__claude_ai_n8n__publish_workflow` / the update path). The catalog-refresh runs
daily; the assistant trigger goes live on george@.

- [ ] **Step 2: Write a memory note for non-obvious build decisions**

Create `/Users/get-hub/.claude/projects/-Users-get-hub-Projects-ROTOCON-DevOps-monday-rotocon/memory/monday_email_assistant.md`:

```markdown
---
name: monday-email-assistant
description: Inbound email chatbot over monday — how the @ask flow + loop guard work.
metadata:
  type: project
---

n8n `monday-email-assistant` answers emailed questions over the monday workspace.
Question = subject contains `@ask` and NOT starting with `Re:` (the Re: check is the
loop guard, since the bot replies in-thread keeping `@ask`). LLM emits a constrained
JSON plan validated against a daily Postgres catalog cache
(`rotocon_finance.monday_schema_catalog`, refreshed by `monday-schema-catalog-refresh`);
n8n counts in code, Claude only phrases. Reply To: asker, Cc: george@ (dropped when
asker is george@). Phase 0 listens on george@; Phase 1 swaps to ask@rotocon.world.
See [[n8n_webhook_payload_after_convert_to_file]].
```

Add the pointer line to MEMORY.md:

```markdown
- [monday email assistant](monday_email_assistant.md) — @ask inbound chatbot; subject @ask + Re: loop guard; plan-validate-count-phrase.
```

- [ ] **Step 3: Commit any remaining repo changes**

```bash
git add -A n8n/ docs/
git commit -m "docs(assistant): activation notes"
```

---

## Phase 1 follow-up (separate, after Phase 0 sign-off)

Not part of this plan's tasks — a later one-session change once the mailbox exists:
create `ask@rotocon.world` + its Gmail OAuth credential, point the Gmail Trigger and
Send node at it, and expand the Guard Sender allowlist to the team. Core logic
unchanged.
```
