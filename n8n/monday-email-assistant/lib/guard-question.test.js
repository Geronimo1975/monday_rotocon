const test = require('node:test');
const assert = require('node:assert');
const { isQuestion } = require('./guard-question');

test('plain @ask_George subject is a question', () => {
  assert.strictEqual(isQuestion('Câte mașini @ask_George'), true);
});

test('@ask_George anywhere in subject counts', () => {
  assert.strictEqual(isQuestion('@ask_George how many machines'), true);
});

test('the token is case-insensitive', () => {
  assert.strictEqual(isQuestion('totals @ASK_GEORGE'), true);
});

test('subject without the token is not a question', () => {
  assert.strictEqual(isQuestion('weekly report'), false);
});

test('the bare old @ask token alone is no longer enough', () => {
  assert.strictEqual(isQuestion('Câte mașini @ask'), false);
});

test('the bot reply (Re: ... @ask_George) is ignored to break the loop', () => {
  assert.strictEqual(isQuestion('Re: Câte mașini @ask_George'), false);
});

test('case-insensitive Re: prefix is still ignored', () => {
  assert.strictEqual(isQuestion('RE: x @ask_George'), false);
});

test('a forwarded subject (Fwd:) is also ignored', () => {
  assert.strictEqual(isQuestion('Fwd: x @ask_George'), false);
});

test('missing/empty subject is not a question', () => {
  assert.strictEqual(isQuestion(undefined), false);
  assert.strictEqual(isQuestion(''), false);
});
