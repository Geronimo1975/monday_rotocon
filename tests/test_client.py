import httpx
import respx

from monday_rotocon import MondayClient


def test_boards_returns_typed_list():
    data = {
        "data": {
            "boards": [
                {
                    "id": "12345",
                    "name": "Sales Pipeline",
                    "workspace_id": "100",
                    "columns": [
                        {
                            "id": "status_1",
                            "title": "Status",
                            "type": "status",
                            "settings_str": "{}",
                        },
                    ],
                },
            ]
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(json=data)
        client = MondayClient(api_token="t")
        boards = list(client.boards(ids=["12345"]))
        assert len(boards) == 1
        assert boards[0].name == "Sales Pipeline"
        assert boards[0].columns[0].type == "status"


def test_items_for_board_paginates_through_cursor():
    page1 = {
        "data": {
            "boards": [
                {
                    "items_page": {
                        "cursor": "next-cursor",
                        "items": [
                            {
                                "id": "1",
                                "name": "Lead A",
                                "state": "active",
                                "created_at": "2026-05-01T10:00:00Z",
                                "updated_at": "2026-05-02T10:00:00Z",
                                "column_values": [],
                            },
                        ],
                    }
                }
            ]
        }
    }
    page2 = {
        "data": {
            "next_items_page": {
                "cursor": None,
                "items": [
                    {
                        "id": "2",
                        "name": "Lead B",
                        "state": "active",
                        "created_at": "2026-05-01T10:00:00Z",
                        "updated_at": "2026-05-02T10:00:00Z",
                        "column_values": [],
                    },
                ],
            }
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").mock(
            side_effect=[
                httpx.Response(200, json=page1),
                httpx.Response(200, json=page2),
            ]
        )
        client = MondayClient(api_token="t")
        items = list(client.items_for_board(board_id="12345", page_size=1))
        assert [i.id for i in items] == ["1", "2"]
        assert route.call_count == 2
