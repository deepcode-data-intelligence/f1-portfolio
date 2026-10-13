import itertools
import json
from pathlib import Path

import httpx
import pytest

from f1_data_platform.config import Settings
from f1_data_platform.jolpica import JolpicaClient
from f1_data_platform.ratelimit import RateLimiter
from f1_data_platform.raw import RawStore
from tests import fixtures


class FakeJolpica:
    """httpx transport serving the fixture pages, honouring limit/offset like the real API."""

    def __init__(self, routes: dict[str, list[dict]] | None = None) -> None:
        self.routes = routes or fixtures.ROUTES
        self.calls: list[str] = []
        self.fail_next: list[int] = []  # status codes to return before succeeding

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if self.fail_next:
            status = self.fail_next.pop(0)
            return httpx.Response(status, headers={"Retry-After": "0"} if status == 429 else {})
        path = request.url.path.removeprefix("/ergast/f1/")
        pages = self.routes.get(path)
        if pages is None:
            return httpx.Response(404)
        offset = int(request.url.params.get("offset", "0"))
        for page in pages:
            if int(page["offset"]) == offset:
                return httpx.Response(200, json={"MRData": page})
        return httpx.Response(404)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def fake_api() -> FakeJolpica:
    return FakeJolpica()


@pytest.fixture
def client(settings: Settings, fake_api: FakeJolpica) -> JolpicaClient:
    ticks = itertools.count(0.0, 1.0)
    limiter = RateLimiter(10_000, 10_000, clock=lambda: next(ticks), sleep=lambda _: None)
    http = httpx.Client(transport=httpx.MockTransport(fake_api), base_url=settings.jolpica_base_url)
    return JolpicaClient(settings, limiter=limiter, http=http)


@pytest.fixture
def raw_store(settings: Settings) -> RawStore:
    """A raw store pre-populated with the fixture pages, every partition complete."""
    store = RawStore(settings.raw_dir)
    for path, pages in fixtures.ROUTES.items():
        entity_key = path.split("/")[-1].removesuffix(".json")
        entity = {
            "driverstandings": "driver_standings",
            "constructorstandings": "constructor_standings",
            "sprint": "sprint_results",
        }.get(entity_key, entity_key)
        season = None if "/" not in path else int(path.split("/")[0])
        store.begin(entity, season)
        for i, page in enumerate(pages):
            store.write_page(entity, season, i, json.loads(json.dumps(page)))
        store.mark_complete(entity, season)
    return store
