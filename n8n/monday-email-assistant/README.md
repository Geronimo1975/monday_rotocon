# monday-email-assistant — n8n build artifacts

Versioned source for two n8n workflows. The JS in `lib/` is unit-tested here, then
pasted into n8n **Code** nodes (function bodies are self-contained; no requires).

| File | n8n node it feeds |
|---|---|
| `sql/monday_schema_catalog.sql` | Postgres node in `monday-schema-catalog-refresh` |
| `graphql/list-boards.graphql` | HTTP Request (monday) in `monday-schema-catalog-refresh` |
| `lib/build-catalog.js` | Code node "Build Catalog" |
| `graphql/fetch-items.graphql` | HTTP Request (monday) in `monday-email-assistant` |
| `lib/guard-question.js` | IF/Code "Guard Question" |
| `lib/validate-plan.js` | Code node "Validate Plan" |
| `lib/aggregate.js` | Code node "Filter + Aggregate" |
| `prompts/plan-system.md` | Claude #1 (Plan) system prompt |
| `prompts/phrase-system.md` | Claude #2 (Phrase) system prompt |

Run tests: `node --test n8n/monday-email-assistant/lib/*.test.js`
