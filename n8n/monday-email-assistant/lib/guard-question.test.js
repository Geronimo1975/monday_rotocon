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

test('a forwarded subject (Fwd:) is also ignored', () => {
  assert.strictEqual(isQuestion('Fwd: x @ask'), false);
});

test('missing/empty subject is not a question', () => {
  assert.strictEqual(isQuestion(undefined), false);
  assert.strictEqual(isQuestion(''), false);
});
