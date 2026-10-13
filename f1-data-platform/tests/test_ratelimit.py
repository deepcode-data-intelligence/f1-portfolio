import pytest

from f1_data_platform.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_burst_limit_spaces_requests() -> None:
    clock = FakeClock()
    rl = RateLimiter(hourly_limit=1000, burst_per_second=4, clock=clock, sleep=clock.sleep)
    assert rl.acquire() == 0.0
    assert rl.acquire() == pytest.approx(0.25)
    assert rl.acquire() == pytest.approx(0.25)


def test_hourly_limit_blocks_until_window_slides() -> None:
    clock = FakeClock()
    rl = RateLimiter(hourly_limit=3, burst_per_second=1000, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        rl.acquire()
    slept = rl.acquire()  # 4th request must wait for the first one to leave the 1 h window
    assert slept == pytest.approx(3600 - 0.002, abs=0.01)
    assert clock.now >= 3600


def test_window_slides_without_sleeping() -> None:
    clock = FakeClock()
    rl = RateLimiter(hourly_limit=2, burst_per_second=1000, clock=clock, sleep=clock.sleep)
    rl.acquire()
    rl.acquire()
    clock.now = 4000.0
    assert rl.acquire() == 0.0


def test_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        RateLimiter(0, 1)
