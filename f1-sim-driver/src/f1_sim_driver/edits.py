"""Segment edits: the vocabulary the AI lap editor uses to derive a new script from a lap.

Editing one or two corners per iteration is far more robust than rewriting the whole lap,
so edits are expressed as local, distance-bounded operations and applied in order.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from f1_sim_driver.script import ControlPoint, LapScript


class ShiftSegment(BaseModel):
    """Move every control point in [start_m, end_m] by delta_m along the lap (e.g. brake later)."""

    op: Literal["shift"] = "shift"
    start_m: float
    end_m: float
    delta_m: float


class ScaleChannel(BaseModel):
    """Multiply one input channel in [start_m, end_m] by factor (clamped to the valid range)."""

    op: Literal["scale"] = "scale"
    channel: Literal["steer", "throttle", "brake"]
    start_m: float
    end_m: float
    factor: float = Field(gt=0)


class OffsetLateral(BaseModel):
    """Request a lateral offset (metres, +left) in [start_m, end_m], e.g. a wider entry."""

    op: Literal["lateral"] = "lateral"
    start_m: float
    end_m: float
    offset_m: float


Edit = ShiftSegment | ScaleChannel | OffsetLateral


def apply_edits(script: LapScript, edits: list[Edit], author: str, notes: str = "") -> LapScript:
    points = [p.model_copy() for p in script.points]
    for edit in edits:
        for p in points:
            if not (edit.start_m <= p.distance_m <= edit.end_m):
                continue
            match edit:
                case ShiftSegment():
                    p.distance_m = max(0.0, p.distance_m + edit.delta_m)
                case ScaleChannel():
                    v = getattr(p, edit.channel) * edit.factor
                    lo = -1.0 if edit.channel == "steer" else 0.0
                    setattr(p, edit.channel, min(1.0, max(lo, v)))
                case OffsetLateral():
                    p.lateral_m = (p.lateral_m or 0.0) + edit.offset_m
    points.sort(key=lambda p: p.distance_m)
    points = _dedupe(points)
    return LapScript(
        track=script.track,
        car_index=script.car_index,
        author=author,
        iteration=script.iteration + 1,
        parent_id=f"{script.author}#{script.iteration}",
        notes=notes,
        points=points,
    )


def _dedupe(points: list[ControlPoint]) -> list[ControlPoint]:
    """Drop points that collided in distance after a shift; keep the later one in file order."""
    out: list[ControlPoint] = []
    for p in points:
        if out and p.distance_m <= out[-1].distance_m:
            out[-1] = p
        else:
            out.append(p)
    return out
