"""Thin, paginated client for the Jolpica-F1 API (Ergast-compatible JSON)."""

import logging
from collections.abc import Iterator

import httpx

from f1_data_platform.config import Settings
from f1_data_platform.ratelimit import RateLimiter

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class JolpicaError(RuntimeError):
    pass


class JolpicaClient:
    def __init__(
        self,
        settings: Settings,
        limiter: RateLimiter | None = None,
        http: httpx.Client | None = None,
        max_attempts: int = 5,
    ) -> None:
        self.settings = settings
        self.limiter = limiter or RateLimiter(settings.hourly_limit, settings.burst_per_second)
        self.http = http or httpx.Client(
            base_url=settings.jolpica_base_url,
            headers={"User-Agent": settings.user_agent},
            timeout=30.0,
        )
        self.max_attempts = max_attempts
        self.requests_made = 0

    def get_page(self, path: str, offset: int = 0) -> dict:
        """Fetch one page and return the ``MRData`` object."""
        params = {"limit": self.settings.page_size, "offset": offset}
        backoff = 1.0
        for attempt in range(1, self.max_attempts + 1):
            self.limiter.acquire()
            self.requests_made += 1
            response = self.http.get(path, params=params)
            if response.status_code == 200:
                return response.json()["MRData"]
            if response.status_code in RETRY_STATUSES and attempt < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else backoff
                log.warning("GET %s -> %s, retrying in %.1fs", path, response.status_code, delay)
                self.limiter.sleep(delay)
                backoff = min(backoff * 2, 60.0)
                continue
            raise JolpicaError(f"GET {path} offset={offset} -> HTTP {response.status_code}")
        raise JolpicaError(f"GET {path}: exhausted retries")  # pragma: no cover

    def iter_pages(self, path: str) -> Iterator[tuple[int, dict]]:
        """Yield ``(page_index, MRData)`` for every page of a resource."""
        offset, page = 0, 0
        while True:
            mrdata = self.get_page(path, offset)
            yield page, mrdata
            total, limit = int(mrdata["total"]), int(mrdata["limit"])
            offset += limit
            page += 1
            if offset >= total:
                return
