"""Sample quality, the industrial pattern for trusting a value downstream."""

from enum import StrEnum


class Quality(StrEnum):
    GOOD = "good"
    BAD = "bad"  # parse error, out-of-range, sensor flagged invalid by the game
    STALE = "stale"  # no fresh packet within the expected interval; last value repeated
    SUBSTITUTED = "substituted"  # value filled by the connector (e.g. interpolation)
