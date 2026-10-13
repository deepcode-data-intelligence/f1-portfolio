import math

from f1_sim_driver.edits import OffsetLateral, ScaleChannel, ShiftSegment, apply_edits
from f1_sim_driver.script import LapScript


def test_shift_moves_braking_point_later(straight_then_corner: LapScript) -> None:
    new = apply_edits(
        straight_then_corner,
        [ShiftSegment(start_m=240, end_m=260, delta_m=8)],
        author="claude",
        notes="brake 8 m later into T1",
    )
    assert [p.distance_m for p in new.points] == [0, 200, 258, 300]
    assert new.iteration == 1 and new.parent_id == "human#0" and new.author == "claude"


def test_scale_is_clamped(straight_then_corner: LapScript) -> None:
    new = apply_edits(
        straight_then_corner,
        [ScaleChannel(channel="throttle", start_m=290, end_m=310, factor=3)],
        author="chatgpt",
    )
    assert new.points[-1].throttle == 1.0


def test_lateral_offset_accumulates(straight_then_corner: LapScript) -> None:
    edits = [
        OffsetLateral(start_m=240, end_m=260, offset_m=1.5),
        OffsetLateral(start_m=240, end_m=260, offset_m=0.5),
    ]
    new = apply_edits(straight_then_corner, edits, author="claude")
    assert math.isclose(new.points[2].lateral_m, 2.0)
    assert new.points[1].lateral_m is None


def test_shift_collision_keeps_a_valid_script(straight_then_corner: LapScript) -> None:
    new = apply_edits(
        straight_then_corner,
        [ShiftSegment(start_m=240, end_m=260, delta_m=-50)],  # 250 -> 200 collides
        author="claude",
    )
    distances = [p.distance_m for p in new.points]
    assert distances == sorted(set(distances))
