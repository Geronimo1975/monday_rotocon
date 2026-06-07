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

test('extracts labels from the monday array-of-objects settings shape', () => {
  // monday's real GraphQL settings_str for status columns is an array of
  // {id,label,index,...} objects, not an {id: "label"} map. Empty labels filtered.
  const boards = [{
    id: 1, name: 'B',
    columns: [{
      id: 'color_x', title: 'Project Status', type: 'status',
      settings_str: JSON.stringify({ labels: [
        { id: 2, label: 'critical', index: 2 },
        { id: 3, label: 'ok', index: 0 },
        { id: 4, label: '', index: 3 },
      ] }),
    }],
  }];
  const col = buildCatalog(boards).boards['1'].columns['color_x'];
  assert.deepStrictEqual(col.labels.sort(), ['critical', 'ok']);
});

test('survives malformed settings_str without throwing', () => {
  const col = buildCatalog(BOARDS).boards['5086438002'].columns['bad'];
  assert.strictEqual(col.labels, undefined);
});

test('excludes auto-generated subitem boards', () => {
  const boards = [
    { id: 1, name: 'Europe Machine Overview', columns: [] },
    { id: 2, name: 'Subitems of Europe Machine Overview', columns: [] },
    { id: 3, name: 'Unterelemente von Leads', columns: [] },
  ];
  const c = buildCatalog(boards);
  assert.deepStrictEqual(Object.keys(c.boards), ['1']);
});

test('empty input yields empty catalog', () => {
  assert.deepStrictEqual(buildCatalog([]), { boards: {} });
});
