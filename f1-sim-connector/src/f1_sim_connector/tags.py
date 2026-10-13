"""Historian tag naming for game telemetry.

Scheme: ``SIM.CAR{index}.{SIGNAL}``, with dotted sub-paths for per-wheel signals,
e.g. ``SIM.CAR0.SPEED`` or ``SIM.CAR0.TYRE.FL.TEMP``.
"""

PREFIX = "SIM"
WHEELS = ("RL", "RR", "FL", "FR")  # order used by the game's per-wheel arrays


def car_tag(car_index: int, *path: str) -> str:
    if not 0 <= car_index < 22:
        raise ValueError(f"car index out of range: {car_index}")
    if not path:
        raise ValueError("a signal path is required")
    return ".".join((PREFIX, f"CAR{car_index}", *(p.upper() for p in path)))


def wheel_tags(car_index: int, *path: str) -> tuple[str, ...]:
    """Expand a per-wheel signal into its four tags, in the game's wheel order."""
    return tuple(car_tag(car_index, *path[:-1], wheel, path[-1]) for wheel in WHEELS)
