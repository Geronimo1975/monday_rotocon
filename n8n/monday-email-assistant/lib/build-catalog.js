// Turn monday's board+column listing into a compact catalog the LLM picks from.
// For label-bearing column types, include the allowed values so the model emits
// stored values ("Germany") rather than user phrasing ("Germania").
const LABELLED = new Set(['status', 'color', 'dropdown', 'country']);

function buildCatalog(boards) {
  const out = { boards: {} };
  for (const b of boards || []) {
    const columns = {};
    for (const c of b.columns || []) {
      const col = { id: c.id, title: c.title, type: c.type };
      if (LABELLED.has(c.type) && c.settings_str) {
        try {
          const s = JSON.parse(c.settings_str);
          if (s && s.labels) {
            // monday returns labels either as an array of {id,label,...} objects
            // (modern API) or as an {id: "label"} string map (classic). Normalise
            // both to a flat list of label strings.
            const raw = Array.isArray(s.labels) ? s.labels : Object.values(s.labels);
            col.labels = raw
              .map((v) => (v && typeof v === 'object' ? v.label : v))
              .filter(Boolean);
          }
        } catch (e) {
          // malformed settings — skip labels, keep the column usable
        }
      }
      columns[c.id] = col;
    }
    out.boards[String(b.id)] = { id: String(b.id), name: b.name, columns };
  }
  return out;
}

module.exports = { buildCatalog };
