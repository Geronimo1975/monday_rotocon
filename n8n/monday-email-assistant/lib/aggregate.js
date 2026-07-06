// Deterministic filter + aggregation over real monday rows. The LLM never produces
// the number — this code does, so counts cannot be hallucinated.
const LIST_CAP = 50;

function normalizeItem(item) {
  const cols = {};
  for (const cv of item.column_values || []) {
    cols[cv.id] = { text: cv.text == null ? '' : String(cv.text), value: cv.value };
  }
  return { id: item.id, name: item.name || '', cols };
}

function cellText(item, columnId) {
  if (columnId === 'name') return item.name || '';
  const cell = item.cols[columnId];
  return cell ? cell.text : '';
}

function matchFilter(item, f) {
  const text = cellText(item, f.column_id);
  const lower = text.toLowerCase();
  const target = (f.value == null ? '' : String(f.value)).toLowerCase();
  const num = parseFloat(text);
  const tnum = parseFloat(target);
  switch (f.op) {
    case 'equals': return lower === target;
    case 'not_equals': return lower !== target;
    case 'contains': return lower.includes(target);
    case 'gt': return !isNaN(num) && num > tnum;
    case 'gte': return !isNaN(num) && num >= tnum;
    case 'lt': return !isNaN(num) && num < tnum;
    case 'lte': return !isNaN(num) && num <= tnum;
    case 'is_empty': return text.trim() === '';
    case 'not_empty': return text.trim() !== '';
    default: return false;
  }
}

function aggregate(items, plan) {
  const filters = plan.filters || [];
  const matched = items.filter((it) => filters.every((f) => matchFilter(it, f)));
  const out = {
    aggregation: plan.aggregation,
    matched: matched.length,
    scanned: items.length,
    truncated: false,
  };

  if (plan.aggregation === 'count') {
    out.value = matched.length;
  } else if (plan.aggregation === 'avg' || plan.aggregation === 'sum') {
    const nums = matched
      .map((it) => parseFloat(cellText(it, plan.aggregation_column)))
      .filter((n) => !isNaN(n));
    out.skipped = matched.length - nums.length;
    const sum = nums.reduce((a, b) => a + b, 0);
    out.value = plan.aggregation === 'sum' ? sum : (nums.length ? sum / nums.length : null);
  } else if (plan.aggregation === 'group_count') {
    const groups = {};
    for (const it of matched) {
      const key = cellText(it, plan.group_by_column) || '(empty)';
      groups[key] = (groups[key] || 0) + 1;
    }
    out.groups = groups;
  } else if (plan.aggregation === 'list') {
    out.truncated = matched.length > LIST_CAP;
    out.rows = matched.slice(0, LIST_CAP).map((it) => {
      const row = { name: it.name };
      for (const c of plan.select_columns || []) {
        if (c !== 'name') row[c] = cellText(it, c);
      }
      return row;
    });
  } else {
    out.error = 'unhandled aggregation: ' + plan.aggregation;
  }
  return out;
}

// Board updates (activity log) → compact rows for the phrase LLM. Deterministic:
// window filter + cap happen here, never in the LLM. `nowMs` is a parameter so
// tests control the clock.
const ACTIVITY_CAP = 30;
const ACTIVITY_DEFAULT_DAYS = 7;
const ACTIVITY_MAX_DAYS = 90;

function aggregateActivity(updates, plan, nowMs) {
  const days = Math.min(
    Math.max(parseInt(plan.activity_days, 10) || ACTIVITY_DEFAULT_DAYS, 1),
    ACTIVITY_MAX_DAYS,
  );
  const cutoff = nowMs - days * 86400000;
  const all = Array.isArray(updates) ? updates : [];
  const recent = all.filter((u) => {
    const t = Date.parse(u && u.created_at);
    return !isNaN(t) && t >= cutoff;
  });
  const out = {
    aggregation: 'recent_activity',
    days,
    matched: recent.length,
    scanned: all.length,
    truncated: recent.length > ACTIVITY_CAP,
  };
  out.updates = recent.slice(0, ACTIVITY_CAP).map((u) => ({
    when: String(u.created_at || '').slice(0, 16).replace('T', ' '),
    who: (u.creator && u.creator.name) || '(unknown)',
    text: String(u.text_body || '').replace(/\s+/g, ' ').trim().slice(0, 200),
  }));
  return out;
}

module.exports = { normalizeItem, cellText, matchFilter, aggregate, aggregateActivity };
