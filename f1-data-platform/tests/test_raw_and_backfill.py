from f1_data_platform.extract import backfill
from f1_data_platform.jolpica import JolpicaClient
from f1_data_platform.raw import RawStore


def test_partition_is_only_complete_after_marker(settings) -> None:
    store = RawStore(settings.raw_dir)
    store.begin("races", 2024)
    store.write_page("races", 2024, 0, {"total": "1"})
    assert not store.is_complete("races", 2024)
    assert list(store.iter_pages("races")) == []  # incomplete partitions are invisible downstream
    store.mark_complete("races", 2024)
    assert store.is_complete("races", 2024)
    assert [s for s, _ in store.iter_pages("races")] == [2024]


def test_begin_drops_stale_pages(settings) -> None:
    store = RawStore(settings.raw_dir)
    store.begin("races", 2024)
    store.write_page("races", 2024, 0, {})
    store.write_page("races", 2024, 1, {})
    store.mark_complete("races", 2024)
    store.begin("races", 2024)
    assert not store.is_complete("races", 2024)
    assert list(store.partition("races", 2024).iterdir()) == []


def test_backfill_is_resumable_and_idempotent(settings, client: JolpicaClient, fake_api) -> None:
    store = RawStore(settings.raw_dir)
    first = backfill(client, store, seasons=[2024], refresh=[])
    assert first.partitions_loaded == 8  # seasons + 7 season entities
    assert first.pages == 9  # results take two pages
    assert store.is_complete("results", 2024)

    calls_before = len(fake_api.calls)
    second = backfill(client, store, seasons=[2024], refresh=[])
    assert second.partitions_loaded == 1  # only the seasons list is refreshed
    assert second.partitions_skipped == 7
    assert len(fake_api.calls) - calls_before == 1


def test_backfill_refreshes_requested_seasons(settings, client: JolpicaClient) -> None:
    store = RawStore(settings.raw_dir)
    backfill(client, store, seasons=[2024], refresh=[])
    again = backfill(client, store, seasons=[2024], entities=["results"], refresh=[2024])
    assert again.partitions_loaded == 1 and again.partitions_skipped == 0


def test_backfill_discovers_seasons_from_api(settings, client: JolpicaClient) -> None:
    store = RawStore(settings.raw_dir)
    stats = backfill(client, store, entities=["seasons"], refresh=[])
    assert stats.seasons == [2023, 2024]
