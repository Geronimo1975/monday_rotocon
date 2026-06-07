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
