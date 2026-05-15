import json

import pytest
import respx

from monday_rotocon import MondayAPIError, MondayClient


def test_change_values_returns_refreshed_item():
    data = {
        "data": {
            "change_multiple_column_values": {
                "id": "999",
                "name": "Renamed lead",
                "state": "active",
                "updated_at": "2026-05-15T11:00:00Z",
                "column_values": [
                    {"id": "status_1", "type": "status", "value": '{"index":1}', "text": "Working"},
                ],
            }
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").respond(json=data)
        client = MondayClient(api_token="t")
        item = client.change_values(
            item_id="999",
            board_id="5091815342",
            column_values={"name": "Renamed lead", "status_1": "Working"},
        )
        assert item.id == "999"
        assert item.name == "Renamed lead"
        sent = json.loads(route.calls.last.request.content)
        assert sent["variables"]["item_id"] == "999"
        assert sent["variables"]["board_id"] == "5091815342"


def test_change_values_raises_on_graphql_error():
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(json={"errors": [{"message": "Invalid column value"}]})
        client = MondayClient(api_token="t")
        with pytest.raises(MondayAPIError, match="Invalid column value"):
            client.change_values(
                item_id="1",
                board_id="1",
                column_values={"x": "y"},
            )
