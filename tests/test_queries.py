from monday_rotocon import queries


def test_q_boards_is_graphql_string():
    assert "boards(ids:" in queries.Q_BOARDS
    assert "columns" in queries.Q_BOARDS


def test_q_items_page_has_cursor_and_limit():
    assert "items_page" in queries.Q_ITEMS_PAGE
    assert "$cursor" in queries.Q_ITEMS_PAGE
    assert "$limit" in queries.Q_ITEMS_PAGE
    assert "column_values" in queries.Q_ITEMS_PAGE


def test_q_next_items_page_uses_cursor():
    assert "next_items_page" in queries.Q_NEXT_ITEMS_PAGE
    assert "cursor:" in queries.Q_NEXT_ITEMS_PAGE
