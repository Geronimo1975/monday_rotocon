from datetime import datetime

import pytest
from pydantic import ValidationError

from monday_rotocon.models import Board, Column, ColumnValue, Group, Item


def test_unknown_fields_are_ignored():
    # monday.com routinely adds fields; extra="ignore" must drop them, not fail.
    raw = {
        "id": "1",
        "name": "Lead",
        "state": "active",
        "column_values": [],
        "brand_new_api_field": {"nested": True},
        "another_unexpected": 123,
    }
    item = Item.model_validate(raw)
    assert item.id == "1"
    assert not hasattr(item, "brand_new_api_field")


def test_column_value_aliases_id_to_column_id():
    # The API field is "id"; we expose it as column_id via alias.
    cv = ColumnValue.model_validate({"id": "status_1", "type": "status"})
    assert cv.column_id == "status_1"


def test_column_value_populate_by_name_accepts_column_id():
    # populate_by_name=True lets internal code construct by the field name too.
    cv = ColumnValue(column_id="status_1", type="status")
    assert cv.column_id == "status_1"


def test_item_missing_required_field_raises():
    with pytest.raises(ValidationError):
        Item.model_validate({"name": "no id here"})


def test_board_missing_required_field_raises():
    with pytest.raises(ValidationError):
        Board.model_validate({"name": "no id"})


def test_item_parses_iso_datetimes_into_datetime():
    item = Item.model_validate(
        {
            "id": "1",
            "name": "x",
            "created_at": "2026-05-10T12:00:00Z",
            "column_values": [],
        }
    )
    assert isinstance(item.created_at, datetime)
    assert item.created_at.year == 2026


def test_item_invalid_datetime_raises():
    with pytest.raises(ValidationError):
        Item.model_validate(
            {"id": "1", "name": "x", "created_at": "not-a-date", "column_values": []}
        )


def test_column_settings_str_defaults_to_empty():
    col = Column.model_validate({"id": "c1", "title": "Status", "type": "status"})
    assert col.settings_str == ""


def test_group_rejects_missing_title():
    with pytest.raises(ValidationError):
        Group.model_validate({"id": "g1"})


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


def test_group_model_parses_id_and_title():
    from monday_rotocon import Group

    g = Group.model_validate({"id": "topics", "title": "Onboarding (Tag 1)"})
    assert g.id == "topics"
    assert g.title == "Onboarding (Tag 1)"


def test_item_group_field_optional_and_parses_when_present():
    from monday_rotocon import Item

    item_no_group = Item.model_validate(
        {"id": "1", "name": "x", "state": "active", "column_values": []}
    )
    assert item_no_group.group is None

    item_with_group = Item.model_validate(
        {
            "id": "2",
            "name": "y",
            "state": "active",
            "column_values": [],
            "group": {"id": "topics", "title": "Onboarding (Tag 1)"},
        }
    )
    assert item_with_group.group is not None
    assert item_with_group.group.title == "Onboarding (Tag 1)"
