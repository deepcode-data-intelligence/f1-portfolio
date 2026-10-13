"""The lap-script format: the unit of exchange between the AI lap editor and the executor.

A script is a sequence of control points indexed by **lap distance in metres**, never by
time. Between points the executor interpolates linearly. Each point may carry the lateral
position the car is expected to be at, which the executor uses for a minimal position hold.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class ControlPoint(BaseModel):
    distance_m: float = Field(ge=0)
    steer: float = Field(ge=-1, le=1, description="-1 full left .. +1 full right")
    throttle: float = Field(ge=0, le=1)
    brake: float = Field(ge=0, le=1)
    gear: int | None = Field(default=None, ge=-1, le=8, description="None = leave automatic")
    # Expected world position at this distance (metres). Optional; enables position hold.
    pos_x: float | None = None
    pos_y: float | None = None
    # Lateral offset from the reference path, +left in car frame. Optional; written by the editor.
    lateral_m: float | None = None


class LapScript(BaseModel):
    track: str
    car_index: int = Field(ge=0, lt=22)
    author: str = Field(description="who produced it: 'human', 'claude', 'chatgpt', ...")
    iteration: int = Field(ge=0)
    parent_id: str | None = Field(default=None, description="script this one was derived from")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str = ""
    points: list[ControlPoint]

    @field_validator("points")
    @classmethod
    def _strictly_increasing_distance(cls, points: list[ControlPoint]) -> list[ControlPoint]:
        if len(points) < 2:
            raise ValueError("a lap script needs at least two control points")
        for a, b in zip(points, points[1:], strict=False):
            if b.distance_m <= a.distance_m:
                raise ValueError("control points must be strictly increasing in distance")
        return points

    @property
    def length_m(self) -> float:
        return self.points[-1].distance_m
