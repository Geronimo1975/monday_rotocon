import json

import respx

from monday_rotocon import MondayClient


def test_create_item_returns_typed_item():
    data = {
        "data": {
            "create_item": {
                "id": "99999",
                "name": "Brand new lead",
                "state": "active",
                "created_at": "2026-05-15T10:00:00Z",
                "updated_at": "2026-05-15T10:00:00Z",
                "column_values": [
                    {"id": "status_1", "type": "status", "value": '{"index":0}', "text": "New"},
                ],
            }
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").respond(json=data)
        client = MondayClient(api_token="t")
        item = client.create_item(
            board_id="5091815342",
            name="Brand new lead",
            column_values={"status_1": "New"},
        )
        assert item.id == "99999"
        assert item.name == "Brand new lead"
        sent_payload = json.loads(route.calls.last.request.content)
        assert sent_payload["variables"]["board_id"] == "5091815342"
        assert sent_payload["variables"]["item_name"] == "Brand new lead"
        # column_values is JSON-encoded string on the wire (monday API requirement)
        assert sent_payload["variables"]["column_values"] == json.dumps({"status_1": "New"})


def test_create_item_omits_column_values_when_none():
    data = {
        "data": {
            "create_item": {
                "id": "1",
                "name": "x",
                "state": "active",
                "created_at": "2026-05-15T10:00:00Z",
                "updated_at": "2026-05-15T10:00:00Z",
                "column_values": [],
            }
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").respond(json=data)
        client = MondayClient(api_token="t")
        client.create_item(board_id="1", name="x")
        sent = json.loads(route.calls.last.request.content)
        assert sent["variables"]["column_values"] is None
