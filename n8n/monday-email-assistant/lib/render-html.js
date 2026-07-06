// Composes the final HTML email reply: greeting, answer paragraphs (key value
// bolded), an optional source line, a closing, and George's ROTOCON signature.
// Self-contained (no requires) so the whole file can be pasted verbatim into the
// n8n "Build Reply" Code node. The test reads the canonical signature file; this
// module must never touch the filesystem.

const ANSWER_STYLE = 'font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#403E3D;';
const SOURCE_STYLE = 'font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.4;color:#888888;padding-top:6px;border-top:1px solid #C2BCB2;margin-top:14px;';

// Filled in Task 2 from sig/signature.html via extractSignatureFragment.
const SIGNATURE_FRAGMENT = "<style type=\"text/css\">\n    /* Reset email-client defaults. */\n    body, table, td, div, p, a { -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }\n    table, td { mso-table-lspace:0pt; mso-table-rspace:0pt; border-collapse:collapse; }\n    img { -ms-interpolation-mode:bicubic; border:0; outline:none; text-decoration:none; display:block; }\n\n    /* Dark-mode override: clients that respect prefers-color-scheme (Apple Mail desktop+iOS,\n       newer iOS Mail, Outlook 365 web) keep a white card and dark text instead of inverting. */\n    @media (prefers-color-scheme: dark) {\n      .rc-card, .rc-card-td { background-color:#ffffff !important; }\n      .rc-text, .rc-text a { color:#403E3D !important; }\n      .rc-muted, .rc-muted a { color:#555555 !important; }\n      .rc-red, .rc-red a { color:#FF0000 !important; }\n      .rc-divider { border-color:#C2BCB2 !important; background-color:#C2BCB2 !important; }\n    }\n    /* Outlook iOS / Android dark-mode override (Microsoft injects [data-ogs*] attrs in dark mode). */\n    [data-ogsc] .rc-text, [data-ogsc] .rc-text a { color:#403E3D !important; }\n    [data-ogsc] .rc-muted, [data-ogsc] .rc-muted a { color:#555555 !important; }\n    [data-ogsc] .rc-red, [data-ogsc] .rc-red a { color:#FF0000 !important; }\n    [data-ogsb] .rc-card, [data-ogsb] .rc-card-td { background-color:#ffffff !important; }\n\n    /* Responsive stack: below 640px the three table cells switch to display:block\n       so they stack vertically, contact aligns left, machine fits viewport.\n       Breakpoint is 640px (not 520) because the card is a 600px table + 2x20px\n       padding = 640px wide: any viewport or compose/reading pane narrower than\n       that clips the right-hand contact column — which holds the e-mail address\n       and postal address. Stacking before that point keeps both fully visible. */\n    @media only screen and (max-width:640px) {\n      .rc-col { display:block !important; width:100% !important; max-width:100% !important; padding:0 !important; }\n      /* Drop the medallion entirely when the signature stacks (narrow clients and\n         the narrow preview iframe). Stacked, it would sit mid-column between the\n         wordmark and the contact block — the \"floating in the middle\" look. The\n         mobile signature omits the medallion for the same reason; this keeps the\n         narrow desktop view consistent with it. The wide (>640px) layout still\n         shows it, top-aligned beside the name. */\n      .rc-col-mid { display:none !important; }\n      .rc-col-right { padding:14px 0 0 0 !important; }\n      .rc-contact-tbl { margin:0 !important; text-align:left !important; float:none !important; }\n      .rc-medallion { margin:0 auto !important; }\n      .rc-footer-cell { display:block !important; width:100% !important; text-align:left !important; padding:14px 0 0 0 !important; }\n      .rc-machine { max-width:100% !important; height:auto !important; width:auto !important; }\n      .rc-banner { width:100% !important; height:auto !important; }\n    }\n  </style>\n\n\n<!-- White card wrapper — explicit bgcolor attribute + inline background-color so Gmail Android\n     and Outlook mobile don't repaint to black under their forced dark-mode skin. -->\n<!--[if mso]>\n<v:rect xmlns:v=\"urn:schemas-microsoft-com:vml\" fill=\"true\" stroke=\"false\" style=\"width:640px;mso-width-percent:1000;\">\n  <v:fill type=\"solid\" color=\"#ffffff\"/>\n  <v:textbox inset=\"0,0,0,0\">\n<![endif]-->\n<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" bgcolor=\"#ffffff\" class=\"rc-card\" style=\"background-color:#ffffff;mso-color-alt:none;max-width:640px;\">\n<tr><td bgcolor=\"#ffffff\" align=\"left\" class=\"rc-card-td\" style=\"padding:20px;background-color:#ffffff;mso-color-alt:none;max-width:640px;\">\n\n<!-- 3-COLUMN ROW: name | medallion | contact. Real <table> for ALL clients\n     (not just Outlook Windows via MSO) so Outlook for Mac, Apple Mail, and the\n     Outlook signature-editor preview render the columns side-by-side instead of\n     stacking. table-layout:fixed locks the cell widths against client reflow. -->\n<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"600\" bgcolor=\"#ffffff\" style=\"width:100%;max-width:600px;background-color:#ffffff;font-family:Arial,Helvetica,sans-serif;table-layout:fixed;\">\n  <tr>\n    <!-- LEFT: name, title, wordmark, tagline -->\n    <td class=\"rc-col\" valign=\"top\" width=\"253\" style=\"width:253px;vertical-align:top;padding-right:8px;font-family:Arial,Helvetica,sans-serif;color:#403E3D;\">\n      <div class=\"rc-text\" style=\"font-family:Arial,Helvetica,sans-serif;font-size:21px;line-height:24px;color:#403E3D;mso-color-alt:none;mso-line-height-rule:exactly;\"><span class=\"rc-red\" style=\"color:#FF0000;mso-color-alt:none;\">George Sebastian</span> <span class=\"rc-text\" style=\"color:#403E3D;mso-color-alt:none;\">Cucuiet</span></div>\n      <div class=\"rc-muted\" style=\"font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:16px;color:#555555;mso-color-alt:none;padding:4px 0 0 0;mso-line-height-rule:exactly;\">Head of Digital Transformation</div>\n      <!-- Spacer pushes the wordmark + tagline below the 96px-tall medallion in the middle\n           column so any client that misaligns cells can't render them overlapping.\n           Table-based (not <div>) and zero-width space (not &nbsp;) because Outlook\n           for Mac / Outlook Web ignore font-size:1px on inline non-breaking spaces\n           and render the &nbsp; at the inherited font-size, leaving a visible \"|\"\n           artifact above the wordmark. Reported in compose-window screenshots\n           2026-05-26 (george). -->\n      <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" style=\"border-collapse:collapse;\"><tr><td height=\"50\" style=\"height:50px;line-height:0;font-size:0;mso-line-height-rule:exactly;\">&#8203;</td></tr></table>\n      <div style=\"line-height:0;font-size:0;\"><a href=\"https://www.rotocon.world/\" style=\"display:inline-block;line-height:0;text-decoration:none;border:0;\"><img src=\"https://assets.rotocon.world/sig/wordmark.png\" width=\"162\" height=\"26\" alt=\"ROTOCON\" border=\"0\" style=\"display:block;width:162px;height:26px;border:0;outline:none;text-decoration:none;\"></a></div>\n      <div class=\"rc-muted\" style=\"font-family:Arial,Helvetica,sans-serif;padding:7px 0 0 0;font-size:9px;color:#555555;mso-color-alt:none;letter-spacing:1px;mso-line-height-rule:exactly;\">USA&nbsp;&nbsp;&bull;&nbsp;&nbsp;Europe&nbsp;&nbsp;&bull;&nbsp;&nbsp;Africa&nbsp;&nbsp;&bull;&nbsp;&nbsp;Asia</div>\n    </td>\n\n    <!-- CENTER: brand symbol. Top-aligned (not vertical-align:middle) so the\n         medallion sits up beside the name/wordmark instead of floating in the\n         vertical centre of the taller contact column. -->\n    <td class=\"rc-col rc-col-mid\" valign=\"top\" align=\"center\" width=\"78\" style=\"width:78px;vertical-align:top;text-align:center;\">\n      <img src=\"https://assets.rotocon.world/sig/medallion.png\" width=\"78\" height=\"96\" alt=\"ROTOCON\" border=\"0\" class=\"rc-medallion\" style=\"display:block;width:78px;height:96px;border:0;margin:0 auto;outline:none;text-decoration:none;\">\n    </td>\n\n    <!-- RIGHT: contact block -->\n    <td class=\"rc-col rc-col-right\" valign=\"middle\" width=\"247\" style=\"width:247px;vertical-align:middle;padding-left:14px;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.7;color:#403E3D;\">\n      <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" align=\"right\" class=\"rc-contact-tbl\" style=\"text-align:left;\">\n        <tr><td class=\"rc-text\" style=\"padding-bottom:5px;line-height:1.5;white-space:nowrap;font-size:12px;color:#403E3D;mso-color-alt:none;\">\n          <span class=\"rc-muted\" style=\"color:#555555;mso-color-alt:none;\">Mobile</span>&nbsp;&nbsp;<a href=\"tel:+4915155684849\" class=\"rc-text\" style=\"color:#403E3D;mso-color-alt:none;text-decoration:none;\">+49 151 55684849</a>\n        </td></tr>\n        <tr><td class=\"rc-text\" style=\"padding-bottom:5px;line-height:1.5;white-space:nowrap;font-size:12px;color:#403E3D;mso-color-alt:none;\">\n          <span class=\"rc-muted\" style=\"color:#555555;mso-color-alt:none;\">E-mail</span>&nbsp;&nbsp;<a href=\"mailto:george@rotocon.world\" class=\"rc-text\" style=\"color:#403E3D;mso-color-alt:none;text-decoration:none;\">george@rotocon.world</a>\n        </td></tr>\n        <tr><td class=\"rc-red\" style=\"line-height:1.5;white-space:nowrap;font-size:12px;color:#FF0000;mso-color-alt:none;\">\n          <a href=\"https://www.rotocon.world/\" class=\"rc-red\" style=\"color:#FF0000;mso-color-alt:none;text-decoration:none;font-weight:bold;\">www.rotocon.world</a>\n        </td></tr>\n        <tr><td class=\"rc-muted\" style=\"padding-top:12px;font-size:10.5px;color:#555555;mso-color-alt:none;line-height:1.55;\">ROTOCON EUROPE GmbH<br>Jacobsrade 71<br>D-22962 Siek, Germany</td></tr>\n      </table>\n    </td>\n  </tr>\n</table>\n\n<!-- FOOTER divider -->\n<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" bgcolor=\"#ffffff\" style=\"width:100%;background-color:#ffffff;margin-top:16px;\">\n  <tr><td class=\"rc-divider\" bgcolor=\"#C2BCB2\" style=\"border-bottom:1px solid #C2BCB2;background-color:#C2BCB2;font-size:1px;line-height:1px;height:1px;\">&nbsp;</td></tr>\n</table>\n\n<!-- FOOTER ROW: press image on the left, social icons on the right, same row.\n     Press is sized via MEDIA_MAX_W so they share the ~600px inner area. -->\n<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\" style=\"width:100%;margin-top:14px;\">\n  <tr>\n    <td class=\"rc-footer-cell\" align=\"left\" valign=\"top\" style=\"padding:0;text-align:left;vertical-align:top;\">\n      <a href=\"https://magazine.rotocon.world/\" style=\"text-decoration:none;border:0;\"><img src=\"https://assets.rotocon.world/sig/machine.png\" class=\"rc-machine\" width=\"380\" height=\"146\" alt=\"ROTOCON RFP 460\" border=\"0\" style=\"display:block;height:146px;width:380px;border:0;\"></a>\n    </td>\n    <td class=\"rc-footer-cell\" align=\"right\" valign=\"top\" style=\"padding:30px 0 0 12px;vertical-align:top;\">\n      <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" align=\"right\" style=\"border-collapse:collapse;\">\n        <tr>\n                  <td align=\"center\" valign=\"middle\" style=\"padding-left:10px;line-height:0;font-size:0;\"><a href=\"https://www.rotocon.world/\" style=\"text-decoration:none;border:0;line-height:0;\"><img src=\"https://assets.rotocon.world/sig/icon-web.png\" width=\"24\" height=\"24\" alt=\"rotocon.world\" border=\"0\" style=\"display:block;width:24px;height:24px;border:0;outline:none;text-decoration:none;\"></a></td>\n                  <td align=\"center\" valign=\"middle\" style=\"padding-left:10px;line-height:0;font-size:0;\"><a href=\"https://www.linkedin.com/company/rotocon/\" style=\"text-decoration:none;border:0;line-height:0;\"><img src=\"https://assets.rotocon.world/sig/icon-linkedin.png\" width=\"24\" height=\"24\" alt=\"LinkedIn\" border=\"0\" style=\"display:block;width:24px;height:24px;border:0;outline:none;text-decoration:none;\"></a></td>\n                  <td align=\"center\" valign=\"middle\" style=\"padding-left:10px;line-height:0;font-size:0;\"><a href=\"https://www.youtube.com/@rotoconworld\" style=\"text-decoration:none;border:0;line-height:0;\"><img src=\"https://assets.rotocon.world/sig/icon-youtube.png\" width=\"29\" height=\"20\" alt=\"YouTube\" border=\"0\" style=\"display:block;width:29px;height:20px;border:0;outline:none;text-decoration:none;\"></a></td>\n                  <td align=\"center\" valign=\"middle\" style=\"padding-left:10px;line-height:0;font-size:0;\"><a href=\"https://www.instagram.com/rotoconworld/\" style=\"text-decoration:none;border:0;line-height:0;\"><img src=\"https://assets.rotocon.world/sig/icon-instagram.png\" width=\"24\" height=\"24\" alt=\"Instagram\" border=\"0\" style=\"display:block;width:24px;height:24px;border:0;outline:none;text-decoration:none;\"></a></td>\n                  <td align=\"center\" valign=\"middle\" style=\"padding-left:10px;line-height:0;font-size:0;\"><a href=\"https://www.facebook.com/Rotocon/\" style=\"text-decoration:none;border:0;line-height:0;\"><img src=\"https://assets.rotocon.world/sig/icon-facebook.png\" width=\"13\" height=\"24\" alt=\"Facebook\" border=\"0\" style=\"display:block;width:13px;height:24px;border:0;outline:none;text-decoration:none;\"></a></td>\n        </tr>\n      </table>\n    </td>\n  </tr>\n</table>\n<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"600\" style=\"width:100%;max-width:600px;margin-top:14px;\"><tr><td style=\"padding:0;line-height:0;font-size:0;\"><a href=\"https://magazine.rotocon.world/\" style=\"text-decoration:none;border:0;line-height:0;\"><img src=\"https://assets.rotocon.world/sig/banner.jpg\" class=\"rc-banner\" width=\"600\" height=\"138\" alt=\"ROTOCON at LOUPE Americas 2026 — Visit us @ Booth 719\" border=\"0\" style=\"display:block;width:600px;height:138px;border:0;outline:none;text-decoration:none;\"></a></td></tr></table>\n</td></tr>\n</table>\n<!--[if mso]>\n  </v:textbox>\n</v:rect>\n<![endif]-->";

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
