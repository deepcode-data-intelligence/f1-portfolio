import math

from f1_sim_driver.executor import CarState, ScriptExecutor
from f1_sim_driver.script import LapScript


def test_interpolates_between_points(straight_then_corner: LapScript) -> None:
    ex = ScriptExecutor(straight_then_corner)
    mid = ex.scripted_inputs(225)  # halfway between 200 (no brake) and 250 (full brake)
    assert math.isclose(mid.brake, 0.5)
    assert math.isclose(mid.throttle, 0.5)
    assert math.isclose(mid.steer, -0.2)
    assert mid.gear == 7  # gear holds the last control point's value


def test_clamps_outside_script_range(straight_then_corner: LapScript) -> None:
    ex = ScriptExecutor(straight_then_corner)
    assert ex.scripted_inputs(-50) == ex.scripted_inputs(0)
    assert ex.scripted_inputs(10_000) == ex.scripted_inputs(300)


def test_position_hold_steers_toward_scripted_path(straight_then_corner: LapScript) -> None:
    ex = ScriptExecutor(straight_then_corner, hold_gain=0.02, hold_max=0.15)
    on_path = CarState(lap_distance_m=100, pos_x=100, pos_y=0, yaw_rad=0)
    assert ex.inputs(on_path).steer == 0

    # Heading +x, car is 2 m to the right (y=-2) of the path: target is to the left -> steer left.
    right_of_path = CarState(lap_distance_m=100, pos_x=100, pos_y=-2, yaw_rad=0)
    assert math.isclose(ex.lateral_error_m(right_of_path), 2)
    assert math.isclose(ex.inputs(right_of_path).steer, -0.04)

    # Correction is capped so the script stays in charge.
    far = CarState(lap_distance_m=100, pos_x=100, pos_y=-50, yaw_rad=0)
    assert math.isclose(ex.inputs(far).steer, -0.15)


def test_no_positions_means_no_hold() -> None:
    from f1_sim_driver.script import ControlPoint

    script = LapScript(
        track="t",
        car_index=0,
        author="x",
        iteration=0,
        points=[
            ControlPoint(distance_m=0, steer=0.1, throttle=1, brake=0),
            ControlPoint(distance_m=100, steer=0.1, throttle=1, brake=0),
        ],
    )
    ex = ScriptExecutor(script)
    state = CarState(lap_distance_m=50, pos_x=999, pos_y=999, yaw_rad=1)
    assert math.isclose(ex.inputs(state).steer, 0.1)
