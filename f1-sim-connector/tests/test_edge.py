from f1_sim_connector.buffer import StoreAndForward
from f1_sim_connector.compression import ExceptionFilter
from f1_sim_connector.model import Sample
from f1_sim_connector.quality import Quality
from f1_sim_connector.tags import car_tag, wheel_tags


def s(value: float, t: int = 0, quality: Quality = Quality.GOOD) -> Sample:
    return Sample(car_tag(0, "speed"), t, value, quality)


def test_tag_naming() -> None:
    assert car_tag(0, "speed") == "SIM.CAR0.SPEED"
    assert wheel_tags(3, "tyre", "temp") == (
        "SIM.CAR3.TYRE.RL.TEMP",
        "SIM.CAR3.TYRE.RR.TEMP",
        "SIM.CAR3.TYRE.FL.TEMP",
        "SIM.CAR3.TYRE.FR.TEMP",
    )


def test_exception_filter_forwards_only_meaningful_changes() -> None:
    f = ExceptionFilter(deviation=1.0)
    assert f.accept(s(100.0, 0))
    assert not f.accept(s(100.5, 1))  # within deviation
    assert f.accept(s(101.5, 2))  # beyond deviation from last forwarded (100.0)
    assert f.accept(s(101.5, 3, Quality.STALE))  # quality change always forwarded


def test_store_and_forward_keeps_order_and_retries() -> None:
    buf = StoreAndForward(capacity=10)
    for i in range(5):
        buf.push(s(float(i), i))

    calls: list[list[float]] = []

    def failing_sink(batch):
        calls.append([x.value for x in batch])
        return False

    assert buf.flush(failing_sink, batch_size=2) == 0
    assert len(buf) == 5  # nothing dropped while the historian is down

    def ok_sink(batch):
        calls.append([x.value for x in batch])
        return True

    assert buf.flush(ok_sink, batch_size=2) == 5
    assert len(buf) == 0
    assert calls[-3:] == [[0.0, 1.0], [2.0, 3.0], [4.0]]


def test_store_and_forward_counts_drops_at_capacity() -> None:
    buf = StoreAndForward(capacity=2)
    for i in range(3):
        buf.push(s(float(i), i))
    assert len(buf) == 2 and buf.dropped == 1
