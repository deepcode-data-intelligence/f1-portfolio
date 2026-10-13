import pytest

from f1_data_platform.jolpica import JolpicaClient, JolpicaError


def test_iter_pages_follows_offset(client: JolpicaClient, fake_api) -> None:
    pages = list(client.iter_pages("2024/results.json"))
    assert [p for p, _ in pages] == [0, 1]
    assert [int(m["offset"]) for _, m in pages] == [0, 2]
    assert len(fake_api.calls) == 2
    assert "limit=100" in fake_api.calls[0]


def test_retries_on_429_then_succeeds(client: JolpicaClient, fake_api) -> None:
    fake_api.fail_next = [429, 503]
    mrdata = client.get_page("seasons.json")
    assert mrdata["total"] == "2"
    assert client.requests_made == 3


def test_gives_up_after_max_attempts(client: JolpicaClient, fake_api) -> None:
    client.max_attempts = 2
    fake_api.fail_next = [500, 500, 500]
    with pytest.raises(JolpicaError):
        client.get_page("seasons.json")


def test_non_retryable_status_raises(client: JolpicaClient) -> None:
    with pytest.raises(JolpicaError, match="HTTP 404"):
        client.get_page("1899/races.json")
