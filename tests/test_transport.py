import httpx
import pytest
import respx

from monday_rotocon.transport import MondayAPIError, MondayClient


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
        router.post("/v2").respond(
            json={"errors": [{"message": "Unauthorized"}]}, status_code=200
        )
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
