"""GraphQL mutation strings for monday.com API v2.

We deliberately use change_multiple_column_values for ALL edits (including
renames via {"name": "new"}) so a single round-trip handles any combination
of fields. monday's column_values JSON shape is identical between create
and edit, giving consumers one mental model.
"""

M_CREATE_ITEM = """
mutation CreateItem($board_id: ID!, $item_name: String!, $column_values: JSON) {
  create_item(board_id: $board_id, item_name: $item_name, column_values: $column_values) {
    id
    name
    state
    created_at
    updated_at
    column_values { id type value text }
  }
}
""".strip()

M_CHANGE_VALUES = """
mutation ChangeValues($item_id: ID!, $board_id: ID!, $column_values: JSON!) {
  change_multiple_column_values(item_id: $item_id, board_id: $board_id,
                                 column_values: $column_values) {
    id
    name
    state
    updated_at
    column_values { id type value text }
  }
}
""".strip()
