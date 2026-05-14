"""HTTP transport for monday.com GraphQL API.

Sync client with retry on 5xx and rate-limit-aware backoff. The library
keeps no global state — instantiate per use.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx

from monday_rotocon.models import Board, Item
from monday_rotocon.queries import Q_BOARDS, Q_ITEMS_PAGE, Q_NEXT_ITEMS_PAGE

DEFAULT_BASE_URL = "https://api.monday.com"
DEFAULT_API_VERSION = "2024-01"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 1.0  # seconds; doubles each retry


class MondayAPIError(RuntimeError):
    """Raised for any unrecoverable monday.com API failure."""


class MondayClient:
    def __init__(
        self,
        api_token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_version: str = DEFAULT_API_VERSION,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
    ) -> None:
        if not api_token:
            raise ValueError("api_token is required")
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={
                "Authorization": api_token,
                "API-Version": api_version,
                "Content-Type": "application/json",
            },
        )
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MondayClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def execute(self, query: str, *, variables: dict[str, Any]) -> dict[str, Any]:
        """POST a GraphQL query; return the `data` payload.

        Retries on 5xx and 429 with exponential backoff. Raises
        MondayAPIError on persistent failure or GraphQL errors.
        """
        payload = {"query": query, "variables": variables}
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post("/v2", json=payload)
            except httpx.TransportError as exc:
                if attempt < self._max_retries:
                    time.sleep(self._backoff_base * (2**attempt))
                    continue
                raise MondayAPIError(
                    f"network error after {self._max_retries} retries: {exc!r}"
                ) from exc
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < self._max_retries:
                    time.sleep(self._backoff_base * (2**attempt))
                    continue
                raise MondayAPIError(
                    f"monday.com responded {response.status_code} after {self._max_retries} retries"
                )
            if response.status_code != 200:
                raise MondayAPIError(
                    f"monday.com responded {response.status_code}: {response.text[:200]}"
                )
            body: dict[str, Any] = response.json()
            if "errors" in body:
                msgs = "; ".join(err.get("message", "?") for err in body["errors"])
                raise MondayAPIError(msgs)
            result: dict[str, Any] = body.get("data", {})
            return result
        raise MondayAPIError("unreachable")

    def boards(self, *, ids: list[str]) -> Iterator[Board]:
        """Fetch boards by ID. Returns iterator of typed Board models."""
        data = self.execute(Q_BOARDS, variables={"board_ids": ids})
        for raw in data.get("boards") or []:
            yield Board.model_validate(raw)

    def items_for_board(self, *, board_id: str, page_size: int = 100) -> Iterator[Item]:
        """Fetch all items for a board, paginating through cursor."""
        data = self.execute(
            Q_ITEMS_PAGE,
            variables={"board_id": board_id, "limit": page_size, "cursor": None},
        )
        boards = data.get("boards") or []
        if not boards:
            return
        page = boards[0].get("items_page") or {}
        for raw in page.get("items") or []:
            yield Item.model_validate(raw)

        cursor = page.get("cursor")
        while cursor:
            data = self.execute(
                Q_NEXT_ITEMS_PAGE,
                variables={"cursor": cursor, "limit": page_size},
            )
            page = data.get("next_items_page") or {}
            for raw in page.get("items") or []:
                yield Item.model_validate(raw)
            cursor = page.get("cursor")
