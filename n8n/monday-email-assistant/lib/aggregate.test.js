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
