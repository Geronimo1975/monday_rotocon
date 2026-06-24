const test = require('node:test');
const assert = require('node:assert');
const { renderReplyHtml, greetingName, escapeHtml, extractSignatureFragment } = require('./render-html');

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

test('extractSignatureFragment pulls style + body inner HTML', () => {
  const html = '<html><head><style>.x{color:red}</style></head><body class="e"><p>sig</p></body></html>';
  const fragment = extractSignatureFragment(html);
  assert.match(fragment, /<style>\.x\{color:red\}<\/style>/);
  assert.match(fragment, /<p>sig<\/p>/);
  assert.doesNotMatch(fragment, /<body/);
});

test('extractSignatureFragment concatenates multiple style blocks', () => {
  const html = '<html><head><style>.a{}</style><style>.b{}</style></head><body><p>x</p></body></html>';
  const fragment = extractSignatureFragment(html);
  assert.match(fragment, /<style>\.a\{\}<\/style>/);
  assert.match(fragment, /<style>\.b\{\}<\/style>/);
});

test('extractSignatureFragment returns empty string for input with no body or style', () => {
  assert.strictEqual(extractSignatureFragment('<p>no body no style</p>'), '');
});
