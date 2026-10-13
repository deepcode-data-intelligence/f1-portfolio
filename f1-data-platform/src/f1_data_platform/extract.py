"""Extraction plan: which Jolpica resources make up each entity, and the resumable backfill."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from f1_data_platform.jolpica import JolpicaClient
from f1_data_platform.raw import RawStore

log = logging.getLogger(__name__)

# Entity -> path template, one partition per season.
SEASON_ENTITIES: dict[str, str] = {
    "races": "{season}/races.json",
    "drivers": "{season}/drivers.json",
    "constructors": "{season}/constructors.json",
    "results": "{season}/results.json",
    "sprint_results": "{season}/sprint.json",
    "driver_standings": "{season}/driverstandings.json",
    "constructor_standings": "{season}/constructorstandings.json",
}
SEASONS_PATH = "seasons.json"
ALL_ENTITIES = ("seasons", *SEASON_ENTITIES)


@dataclass
class BackfillStats:
    partitions_loaded: int = 0
    partitions_skipped: int = 0
    pages: int = 0
    requests: int = 0
    seasons: list[int] = field(default_factory=list)


def _load_partition(
    client: JolpicaClient, store: RawStore, entity: str, season: int | None, path: str
) -> int:
    store.begin(entity, season)
    pages = 0
    for page, mrdata in client.iter_pages(path):
        store.write_page(entity, season, page, mrdata)
        pages += 1
    store.mark_complete(entity, season)
    return pages


def available_seasons(store: RawStore) -> list[int]:
    years: set[int] = set()
    for _, mrdata in store.iter_pages("seasons"):
        for s in mrdata["SeasonTable"]["Seasons"]:
            years.add(int(s["season"]))
    return sorted(years)


def backfill(
    client: JolpicaClient,
    store: RawStore,
    seasons: Iterable[int] | None = None,
    entities: Iterable[str] = ALL_ENTITIES,
    refresh: Iterable[int] | None = None,
) -> BackfillStats:
    """Load every requested (entity, season) partition that is not complete yet.

    ``refresh`` seasons are reloaded even when complete. By default the current year is
    refreshed, because its results keep changing until the season ends.
    """
    stats = BackfillStats()
    entities = tuple(entities)
    refresh_set = set(refresh) if refresh is not None else {datetime.now(UTC).year}

    if "seasons" in entities or not store.is_complete("seasons", None):
        stats.pages += _load_partition(client, store, "seasons", None, SEASONS_PATH)
        stats.partitions_loaded += 1
    season_list = sorted(seasons) if seasons is not None else available_seasons(store)
    stats.seasons = season_list

    for entity in entities:
        if entity == "seasons":
            continue
        template = SEASON_ENTITIES[entity]
        for season in season_list:
            if store.is_complete(entity, season) and season not in refresh_set:
                stats.partitions_skipped += 1
                continue
            log.info("loading %s season=%s", entity, season)
            stats.pages += _load_partition(
                client, store, entity, season, template.format(season=season)
            )
            stats.partitions_loaded += 1
    stats.requests = client.requests_made
    return stats
