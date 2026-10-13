"""Store-and-forward buffer.

Samples are appended in arrival order. ``flush`` hands batches to a sink and only drops
them from the buffer once the sink has accepted them, so an unreachable historian never
loses data (up to ``capacity``). Durable on-disk spooling is added in a later iteration.
"""

from collections import deque
from collections.abc import Callable, Sequence

from f1_sim_connector.model import Sample

Sink = Callable[[Sequence[Sample]], bool]  # returns True when the batch was accepted


class StoreAndForward:
    def __init__(self, capacity: int = 1_000_000) -> None:
        self._queue: deque[Sample] = deque(maxlen=capacity)
        self.dropped = 0

    def __len__(self) -> int:
        return len(self._queue)

    def push(self, sample: Sample) -> None:
        if self._queue.maxlen is not None and len(self._queue) == self._queue.maxlen:
            self.dropped += 1  # oldest sample is evicted by the deque
        self._queue.append(sample)

    def flush(self, sink: Sink, batch_size: int = 1000) -> int:
        """Forward queued samples in order; stop at the first batch the sink rejects."""
        sent = 0
        while self._queue:
            batch = list(self._queue)[:batch_size]
            if not sink(batch):
                break
            for _ in batch:
                self._queue.popleft()
            sent += len(batch)
        return sent
