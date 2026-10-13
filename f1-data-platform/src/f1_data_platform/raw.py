"""Raw layer: API pages persisted as fetched, one JSON file per page.

Layout: ``raw/<entity>/season=<YYYY|all>/page-<NNNN>.json`` plus a ``_COMPLETE`` marker written
only after every page of that partition has landed, which makes the backfill resumable and
idempotent: complete partitions are skipped unless explicitly refreshed.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path

COMPLETE = "_COMPLETE"


class RawStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def partition(self, entity: str, season: int | None) -> Path:
        return self.root / entity / f"season={season if season is not None else 'all'}"

    def page_path(self, entity: str, season: int | None, page: int) -> Path:
        return self.partition(entity, season) / f"page-{page:04d}.json"

    def is_complete(self, entity: str, season: int | None) -> bool:
        return (self.partition(entity, season) / COMPLETE).exists()

    def begin(self, entity: str, season: int | None) -> None:
        """Start (re)loading a partition: drop stale pages and the completeness marker."""
        part = self.partition(entity, season)
        part.mkdir(parents=True, exist_ok=True)
        for old in part.iterdir():
            old.unlink()

    def write_page(self, entity: str, season: int | None, page: int, mrdata: dict) -> Path:
        path = self.page_path(entity, season, page)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(mrdata, separators=(",", ":")))
        os.replace(tmp, path)  # atomic on POSIX
        return path

    def mark_complete(self, entity: str, season: int | None) -> None:
        (self.partition(entity, season) / COMPLETE).touch()

    def seasons(self, entity: str) -> list[int | None]:
        base = self.root / entity
        if not base.exists():
            return []
        out: list[int | None] = []
        for part in sorted(base.iterdir()):
            value = part.name.removeprefix("season=")
            out.append(None if value == "all" else int(value))
        return out

    def iter_pages(self, entity: str) -> Iterator[tuple[int | None, dict]]:
        """Yield ``(season, MRData)`` for every page of every *complete* partition."""
        for season in self.seasons(entity):
            if not self.is_complete(entity, season):
                continue
            for path in sorted(self.partition(entity, season).glob("page-*.json")):
                yield season, json.loads(path.read_text())
