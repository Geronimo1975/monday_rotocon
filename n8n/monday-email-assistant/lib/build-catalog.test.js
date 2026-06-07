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
