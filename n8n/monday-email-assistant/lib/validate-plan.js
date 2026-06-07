// Validate the LLM's query plan against the catalog. This is the injection guard:
// n8n only ever executes plans whose board/columns/ops/aggregation are all known
// and allowed — a crafted email can never steer an arbitrary query.
const OPS = new Set([
  'equals', 'not_equals', 'contains', 'gt', 'gte', 'lt', 'lte', 'is_empty', 'not_empty',
]);
const AGGS = new Set(['count', 'list', 'avg', 'sum', 'group_count']);

function validatePlan(plan, catalog) {
  if (!plan || typeof plan !== 'object') {
    return { ok: false, errors: ['plan is not an object'] };
  }
  if (plan.answerable === false) {
    return { ok: true, errors: [], answerable: false };
  }

  const errors = [];
  const board = catalog.boards[String(plan.board_id)];
  if (!board) errors.push(`unknown board_id ${plan.board_id}`);

  const colOk = (c) => c === 'name' || (board && !!board.columns[c]);

  for (const f of plan.filters || []) {
    if (!colOk(f.column_id)) errors.push(`unknown filter column ${f.column_id}`);
    if (!OPS.has(f.op)) errors.push(`disallowed operator ${f.op}`);
  }

  if (!AGGS.has(plan.aggregation)) {
    errors.push(`disallowed aggregation ${plan.aggregation}`);
  }
  if (plan.aggregation === 'avg' || plan.aggregation === 'sum') {
    if (!plan.aggregation_column) errors.push('aggregation_column required for avg/sum');
    else if (!colOk(plan.aggregation_column)) {
      errors.push(`unknown aggregation_column ${plan.aggregation_column}`);
    }
  }
  if (plan.aggregation === 'group_count') {
    if (!plan.group_by_column) errors.push('group_by_column required for group_count');
    else if (!colOk(plan.group_by_column)) {
      errors.push(`unknown group_by_column ${plan.group_by_column}`);
    }
  }
  for (const c of plan.select_columns || []) {
    if (!colOk(c)) errors.push(`unknown select column ${c}`);
  }

  return { ok: errors.length === 0, errors, answerable: true };
}

module.exports = { validatePlan };
