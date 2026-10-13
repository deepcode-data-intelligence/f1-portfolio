"""Distance-indexed playback with a minimal position hold.

The executor is deliberately dumb: it has no model of the car and no planning. It reads
the current lap distance and position from telemetry, interpolates the script's inputs at
that distance, and adds a small, capped steering correction toward the scripted position.
All driving intelligence lives in the script and therefore in whoever wrote it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from f1_sim_driver.script import LapScript


@dataclass(frozen=True, slots=True)
class Inputs:
    steer: float
    throttle: float
    brake: float
    gear: int | None = None


@dataclass(frozen=True, slots=True)
class CarState:
    lap_distance_m: float
    pos_x: float
    pos_y: float
    yaw_rad: float  # heading, used to project position error onto the car's lateral axis


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class ScriptExecutor:
    def __init__(self, script: LapScript, hold_gain: float = 0.02, hold_max: float = 0.15) -> None:
        self.script = script
        self.hold_gain = hold_gain
        self.hold_max = hold_max
        pts = script.points
        self._d = np.array([p.distance_m for p in pts])
        self._steer = np.array([p.steer for p in pts])
        self._throttle = np.array([p.throttle for p in pts])
        self._brake = np.array([p.brake for p in pts])
        self._gears = [p.gear for p in pts]
        has_pos = all(p.pos_x is not None and p.pos_y is not None for p in pts)
        self._px = np.array([p.pos_x for p in pts]) if has_pos else None
        self._py = np.array([p.pos_y for p in pts]) if has_pos else None

    def scripted_inputs(self, distance_m: float) -> Inputs:
        """Pure interpolation of the script at a lap distance (clamped to the script range)."""
        d = _clamp(distance_m, float(self._d[0]), float(self._d[-1]))
        idx = int(np.searchsorted(self._d, d, side="right") - 1)
        return Inputs(
            steer=float(np.interp(d, self._d, self._steer)),
            throttle=float(np.interp(d, self._d, self._throttle)),
            brake=float(np.interp(d, self._d, self._brake)),
            gear=self._gears[max(idx, 0)],
        )

    def lateral_error_m(self, state: CarState) -> float:
        """Signed distance from the scripted path, +left of the heading; 0 without positions."""
        if self._px is None or self._py is None:
            return 0.0
        d = _clamp(state.lap_distance_m, float(self._d[0]), float(self._d[-1]))
        ex = float(np.interp(d, self._d, self._px)) - state.pos_x
        ey = float(np.interp(d, self._d, self._py)) - state.pos_y
        # Left unit vector for heading yaw: (-sin, cos)
        return ex * -math.sin(state.yaw_rad) + ey * math.cos(state.yaw_rad)

    def inputs(self, state: CarState) -> Inputs:
        base = self.scripted_inputs(state.lap_distance_m)
        err = self.lateral_error_m(state)
        # Target is to the left -> steer left (negative). Correction is proportional and capped.
        correction = _clamp(-self.hold_gain * err, -self.hold_max, self.hold_max)
        return Inputs(
            steer=_clamp(base.steer + correction, -1.0, 1.0),
            throttle=base.throttle,
            brake=base.brake,
            gear=base.gear,
        )
