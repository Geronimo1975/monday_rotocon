import httpx
import pytest
import respx

from monday_rotocon.transport import MondayAPIError, MondayClient


def test_client_requires_token():
    with pytest.raises(ValueError, match="api_token is required"):
        MondayClient(api_token="")


def test_client_raises_on_non_retryable_status():
    # A 401/400 is not in the retry set — it must surface immediately with the body.
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").respond(401, text="Not authenticated")
        client = MondayClient(api_token="bad", max_retries=3, backoff_base=0)
        with pytest.raises(MondayAPIError, match="401"):
            client.execute("q", variables={})
        assert route.call_count == 1  # no retry on a 4xx


def test_client_retries_on_429_then_succeeds():
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(200, json={"data": {"ok": True}}),
            ]
        )
        client = MondayClient(api_token="t", max_retries=2, backoff_base=0)
        assert client.execute("q", variables={}) == {"ok": True}
        assert route.call_count == 2


def test_client_backoff_doubles_each_retry(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("monday_rotocon.transport.time.sleep", lambda s: sleeps.append(s))
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(503)
        client = MondayClient(api_token="t", max_retries=3, backoff_base=1.0)
        with pytest.raises(MondayAPIError):
            client.execute("q", variables={})
        # base * 2**attempt for attempts 0,1,2 → 1, 2, 4
        assert sleeps == [1.0, 2.0, 4.0]


def test_close_is_idempotent_and_closes_underlying_client():
    client = MondayClient(api_token="t")
    assert client._client.is_closed is False
    client.close()
    assert client._client.is_closed is True
    client.close()  # second call must not raise


def test_context_manager_closes_on_exit():
    with MondayClient(api_token="t") as client:
        assert client._client.is_closed is False
    assert client._client.is_closed is True


def test_boards_yields_nothing_when_no_boards_key():
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(json={"data": {}})
        client = MondayClient(api_token="t")
        assert list(client.boards(ids=["1"])) == []


def test_items_for_board_empty_board_returns_nothing():
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(json={"data": {"boards": []}})
        client = MondayClient(api_token="t")
        assert list(client.items_for_board(board_id="1")) == []


def test_items_for_board_single_page_null_cursor_makes_one_call():
    page = {
        "data": {
            "boards": [
                {
                    "items_page": {
                        "cursor": None,
                        "items": [
                            {"id": "1", "name": "Only", "state": "active", "column_values": []}
                        ],
                    }
                }
            ]
        }
    }
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").respond(json=page)
        client = MondayClient(api_token="t")
        items = list(client.items_for_board(board_id="1"))
        assert [i.id for i in items] == ["1"]
        assert route.call_count == 1  # null cursor → no next_items_page call


def test_items_for_board_null_items_page_yields_nothing():
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(json={"data": {"boards": [{"items_page": None}]}})
        client = MondayClient(api_token="t")
        assert list(client.items_for_board(board_id="1")) == []


def test_client_sends_auth_header():
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").respond(json={"data": {}})
        client = MondayClient(api_token="secret-token")
        client.execute("{ me { id } }", variables={})
        assert route.called
        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "secret-token"
        assert sent.headers["API-Version"] == "2024-01"


def test_client_raises_on_graphql_error():
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(json={"errors": [{"message": "Unauthorized"}]}, status_code=200)
        client = MondayClient(api_token="bad-token")
        with pytest.raises(MondayAPIError, match="Unauthorized"):
            client.execute("{ me { id } }", variables={})


def test_client_retries_on_5xx_then_succeeds():
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json={"data": {"ok": True}}),
            ]
        )
        client = MondayClient(api_token="t", max_retries=2, backoff_base=0)
        result = client.execute("q", variables={})
        assert result == {"ok": True}
        assert route.call_count == 2


def test_client_gives_up_after_max_retries():
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").respond(503)
        client = MondayClient(api_token="t", max_retries=2, backoff_base=0)
        with pytest.raises(MondayAPIError, match="503"):
            client.execute("q", variables={})


def test_client_retries_on_network_error_then_succeeds():
    with respx.mock(base_url="https://api.monday.com") as router:
        route = router.post("/v2").mock(
            side_effect=[
                httpx.ConnectError("simulated"),
                httpx.Response(200, json={"data": {"ok": True}}),
            ]
        )
        client = MondayClient(api_token="t", max_retries=2, backoff_base=0)
        result = client.execute("q", variables={})
        assert result == {"ok": True}
        assert route.call_count == 2


def test_client_wraps_network_error_after_retries():
    with respx.mock(base_url="https://api.monday.com") as router:
        router.post("/v2").mock(side_effect=httpx.ReadTimeout("slow"))
        client = MondayClient(api_token="t", max_retries=1, backoff_base=0)
        with pytest.raises(MondayAPIError, match="network error"):
            client.execute("q", variables={})
