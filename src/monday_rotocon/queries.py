"""GraphQL query strings for monday.com API v2.

Cursor-based pagination via items_page / next_items_page (post-2024 API).
"""

Q_BOARDS = """
query Boards($board_ids: [ID!]!) {
  boards(ids: $board_ids) {
    id
    name
    workspace_id
    columns {
      id
      title
      type
      settings_str
    }
  }
}
""".strip()

Q_ITEMS_PAGE = """
query ItemsPage($board_id: ID!, $limit: Int!, $cursor: String) {
  boards(ids: [$board_id]) {
    items_page(limit: $limit, cursor: $cursor) {
      cursor
      items {
        id
        name
        state
        created_at
        updated_at
        group {
          id
          title
        }
        column_values {
          id
          type
          value
          text
        }
      }
    }
  }
}
""".strip()

Q_NEXT_ITEMS_PAGE = """
query NextItemsPage($cursor: String!, $limit: Int!) {
  next_items_page(cursor: $cursor, limit: $limit) {
    cursor
    items {
      id
      name
      state
      created_at
      updated_at
      group {
        id
        title
      }
      column_values {
        id
        type
        value
        text
      }
    }
  }
}
""".strip()
