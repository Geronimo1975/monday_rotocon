// Composes the final HTML email reply: greeting, answer paragraphs (key value
// bolded), an optional source line, a closing, and George's ROTOCON signature.
// Self-contained (no requires) so the whole file can be pasted verbatim into the
// n8n "Build Reply" Code node. The test reads the canonical signature file; this
// module must never touch the filesystem.

const ANSWER_STYLE = 'font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#403E3D;';
const SOURCE_STYLE = 'font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.4;color:#888888;padding-top:6px;border-top:1px solid #C2BCB2;margin-top:14px;';

// Filled in Task 2 from sig/signature.html via extractSignatureFragment.
const SIGNATURE_FRAGMENT = '';

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function greetingName(from) {
  const local = String(from == null ? '' : from).trim().toLowerCase().split('@')[0];
  if (local.length > 0 && /^[a-zà-ÿ]+$/i.test(local)) {
    return local.charAt(0).toUpperCase() + local.slice(1);
  }
  return null;
}

// The bot-computed scalar value (count/sum/avg). Returns null for lists,
// group_count, empty results, or non-answerable questions so we never bold the
// wrong token.
function keyValueString(result) {
  if (!result || typeof result !== 'object') return null;
  if (result.answerable === false) return null;
  if (result.aggregation && result.aggregation !== 'count' && result.aggregation !== 'sum' && result.aggregation !== 'avg') return null;
  if (result.value == null) return null;
  if (typeof result.value === 'number') return String(result.value);
  if (typeof result.value === 'string' && result.value.trim() !== '') return result.value;
  return null;
}

function boldFirst(escapedText, rawValue) {
  if (!rawValue) return escapedText;
  const esc = escapeHtml(rawValue);
  const idx = escapedText.indexOf(esc);
  if (idx === -1) return escapedText;
  return escapedText.slice(0, idx) + '<b>' + esc + '</b>' + escapedText.slice(idx + esc.length);
}

// Extract the embeddable signature fragment (the <style> block + the inner markup
// of <body>) from the canonical full HTML document. Used by Task 2's generator
// and by the anti-drift test.
function extractSignatureFragment(fullHtml) {
  const allStyles = [...String(fullHtml).matchAll(/<style[\s\S]*?<\/style>/gi)];
  const bodyMatch = String(fullHtml).match(/<body[^>]*>([\s\S]*)<\/body>/i);
  const style = allStyles.map((m) => m[0]).join('\n');
  const body = bodyMatch ? bodyMatch[1] : '';
  return (style + '\n' + body).trim();
}

function renderReplyHtml({ answerText, result, provenance, from }) {
  const name = greetingName(from);
  const greeting = name ? ('Bună ziua ' + name + ',') : 'Bună ziua,';
  const kv = keyValueString(result);

  const paragraphs = String(answerText == null ? '' : answerText)
    .split(/\n\s*\n|\r?\n/)
    .map((p) => p.trim())
    .filter(Boolean);

  let bolded = false;
  const pHtml = paragraphs.map((p) => {
    let esc = escapeHtml(p);
    if (!bolded && kv) {
      const next = boldFirst(esc, kv);
      if (next !== esc) bolded = true;
      esc = next;
    }
    return '<p style="margin:0 0 12px 0;">' + esc + '</p>';
  }).join('');

  const source = (provenance != null && String(provenance).trim() !== '')
    ? '<div style="' + SOURCE_STYLE + '">Sursa: ' + escapeHtml(provenance) + '</div>'
    : '';

  const closing = '<p style="margin:18px 0 4px 0;">Cu stimă,</p>';

  return '<div style="' + ANSWER_STYLE + '">'
    + '<p style="margin:0 0 12px 0;">' + escapeHtml(greeting) + '</p>'
    + pHtml
    + source
    + closing
    + '</div>'
    + SIGNATURE_FRAGMENT;
}

module.exports = { renderReplyHtml, greetingName, keyValueString, boldFirst, escapeHtml, extractSignatureFragment };
