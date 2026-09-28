import asyncio
import os
import time

import httpx

LICHESS_EXPLORER_URL = "https://explorer.lichess.org/masters"


class LichessServiceError(Exception):
    """Base error for failures while talking to the Lichess opening explorer."""


class LichessTimeoutError(LichessServiceError):
    """The Lichess opening explorer did not respond in time."""


class LichessRateLimitError(LichessServiceError):
    """The Lichess opening explorer rejected the request due to rate limiting."""


class LichessService:
    """Encapsulates calls to the Lichess opening explorer API."""

    def __init__(
        self,
        base_url: str = LICHESS_EXPLORER_URL,
        timeout: float = 5.0,
        min_interval: float = 1.0,
        max_retries: int = 2,
        api_token: str | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._api_token = api_token if api_token is not None else os.environ.get("LICHESS_API_TOKEN")
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def _throttle(self) -> None:
        # Keep at least `min_interval` seconds between two calls so we stay
        # well under Lichess's rate limits even under concurrent requests.
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            wait = self._min_interval - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    async def explore(self, fen: str) -> dict:
        """Return {"moves", "opening"} for `fen` from the masters database: the
        theoretical moves, and the named opening ({eco, name}) or None."""
        params = {"fen": fen, "moves": 12, "topGames": 0, "recentGames": 0}
        headers = {"Authorization": f"Bearer {self._api_token}"} if self._api_token else {}

        attempt = 0
        while True:
            await self._throttle()
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(self._base_url, params=params, headers=headers)
            except httpx.TimeoutException as exc:
                raise LichessTimeoutError(
                    "Timed out while contacting the Lichess opening explorer."
                ) from exc
            except httpx.HTTPError as exc:
                raise LichessServiceError(
                    f"Failed to contact the Lichess opening explorer: {exc}"
                ) from exc

            if response.status_code == 429:
                if attempt >= self._max_retries:
                    raise LichessRateLimitError(
                        "Lichess opening explorer rate limit exceeded."
                    )
                retry_after = float(response.headers.get("Retry-After", 1.0))
                await asyncio.sleep(retry_after)
                attempt += 1
                continue

            if response.status_code >= 400:
                raise LichessServiceError(
                    f"Lichess opening explorer returned status {response.status_code}."
                )

            data = response.json()
            return {"moves": data.get("moves", []), "opening": data.get("opening")}
