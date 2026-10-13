"""Exception compression at the edge (the PI Interface "exception deviation" test).

A sample is forwarded only when it differs from the last *forwarded* value by more than
the configured deviation, or when the quality changes. The historian then applies
swinging-door compression on top of this.
"""

from f1_sim_connector.model import Sample


class ExceptionFilter:
    def __init__(self, deviation: float = 0.0) -> None:
        if deviation < 0:
            raise ValueError("deviation must be >= 0")
        self.deviation = deviation
        self._last: dict[str, Sample] = {}

    def accept(self, sample: Sample) -> bool:
        last = self._last.get(sample.tag)
        if (
            last is None
            or last.quality != sample.quality
            or abs(sample.value - last.value) > self.deviation
        ):
            self._last[sample.tag] = sample
            return True
        return False
