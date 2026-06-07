// Treat an email as a question only when its subject contains the @ask_george token
// AND is not a reply (Re:) or forward (Fwd:). The Re:/Fwd: check drops the bot's
// own threaded reply and forwarded copies, preventing an infinite loop or
// duplicate answers when listening + replying on the same mailbox.
function isQuestion(subject) {
  const s = (subject || '').toString().trim();
  if (s === '') return false;
  if (/^(re|fwd):/i.test(s)) return false;
  return s.toLowerCase().includes('@ask_george');
}

module.exports = { isQuestion };
