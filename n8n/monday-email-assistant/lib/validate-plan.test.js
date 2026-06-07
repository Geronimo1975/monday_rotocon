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
