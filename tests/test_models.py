from monday_rotocon.models import Board, ColumnValue, Item


def test_board_parses_minimal():
    raw = {"id": "12345", "name": "Sales Pipeline", "workspace_id": "100"}
    board = Board.model_validate(raw)
    assert board.id == "12345"
    assert board.name == "Sales Pipeline"
    assert board.workspace_id == "100"
    assert board.columns == []


def test_board_parses_with_columns():
    raw = {
        "id": "12345",
        "name": "Sales",
        "columns": [
            {"id": "status_1", "title": "Status", "type": "status", "settings_str": "{}"},
            {"id": "people_1", "title": "Owner", "type": "people", "settings_str": "{}"},
        ],
    }
    board = Board.model_validate(raw)
    assert len(board.columns) == 2
    assert board.columns[0].type == "status"


def test_column_value_parses_with_text():
    raw = {"id": "status_1", "type": "status", "value": '{"index":1}', "text": "Working on it"}
    cv = ColumnValue.model_validate(raw)
    assert cv.column_id == "status_1"
    assert cv.text == "Working on it"


def test_item_parses_with_column_values():
    raw = {
        "id": "999",
        "name": "Lead from website",
        "state": "active",
        "created_at": "2026-05-10T12:00:00Z",
        "updated_at": "2026-05-12T08:30:00Z",
        "column_values": [
            {"id": "status_1", "type": "status", "value": '{"index":2}', "text": "Done"},
        ],
    }
    item = Item.model_validate(raw)
    assert item.id == "999"
    assert item.state == "active"
    assert len(item.column_values) == 1
    assert item.column_values[0].text == "Done"


def test_item_unknown_state_falls_back():
    raw = {"id": "1", "name": "x", "state": "weird_state", "column_values": []}
    item = Item.model_validate(raw)
    assert item.state == "weird_state"  # we accept any string; mapping decides
