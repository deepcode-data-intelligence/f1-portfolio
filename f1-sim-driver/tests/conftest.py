import pytest

from f1_sim_driver.script import ControlPoint, LapScript


@pytest.fixture
def straight_then_corner() -> LapScript:
    """Straight along +x for 200 m at full throttle, brake and turn left at 200..300 m."""
    pts = [
        ControlPoint(distance_m=0, steer=0, throttle=1, brake=0, gear=5, pos_x=0, pos_y=0),
        ControlPoint(distance_m=200, steer=0, throttle=1, brake=0, gear=7, pos_x=200, pos_y=0),
        ControlPoint(distance_m=250, steer=-0.4, throttle=0, brake=1, gear=3, pos_x=250, pos_y=5),
        ControlPoint(
            distance_m=300, steer=-0.2, throttle=0.5, brake=0, gear=4, pos_x=290, pos_y=30
        ),
    ]
    return LapScript(track="test", car_index=0, author="human", iteration=0, points=pts)
