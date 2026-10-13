"""Client-side rate limiter honouring both of Jolpica's limits: a burst cap per second and a
sustained cap per rolling hour. Blocking, single-process; the clock is injectable for tests."""

import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        hourly_limit: int,
        burst_per_second: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if hourly_limit <= 0 or burst_per_second <= 0:
            raise ValueError("limits must be positive")
        self.hourly_limit = hourly_limit
        self.min_interval = 1.0 / burst_per_second
        self.clock = clock
        self.sleep = sleep
        self._sent: deque[float] = deque()

    def _wait_time(self, now: float) -> float:
        while self._sent and now - self._sent[0] >= 3600:
            self._sent.popleft()
        wait = 0.0
        if self._sent:
            wait = max(wait, self._sent[-1] + self.min_interval - now)
        if len(self._sent) >= self.hourly_limit:
            wait = max(wait, self._sent[0] + 3600 - now)
        return wait

    def acquire(self) -> float:
        """Block until a request may be sent. Returns the seconds slept."""
        slept = 0.0
        while (wait := self._wait_time(self.clock())) > 0:
            self.sleep(wait)
            slept += wait
        self._sent.append(self.clock())
        return slept
