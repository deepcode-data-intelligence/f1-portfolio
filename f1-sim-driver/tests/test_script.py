import pytest
from pydantic import ValidationError

from f1_sim_driver.script import ControlPoint, LapScript


def test_round_trip_json(straight_then_corner: LapScript) -> None:
    data = straight_then_corner.model_dump_json()
    assert LapScript.model_validate_json(data).points == straight_then_corner.points


def test_distances_must_increase() -> None:
    pts = [
        ControlPoint(distance_m=10, steer=0, throttle=1, brake=0),
        ControlPoint(distance_m=10, steer=0, throttle=1, brake=0),
    ]
    with pytest.raises(ValidationError, match="strictly increasing"):
        LapScript(track="t", car_index=0, author="x", iteration=0, points=pts)


def test_inputs_are_bounded() -> None:
    with pytest.raises(ValidationError):
        ControlPoint(distance_m=0, steer=1.5, throttle=0, brake=0)
