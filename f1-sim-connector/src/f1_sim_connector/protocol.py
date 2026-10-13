"""Binary layout of the game's UDP telemetry.

Only the packet header is modelled for now. The header layout below is the one used by
the F1 2023+ titles (29 bytes, little-endian). Full packet bodies are added per packet id,
and the 2026 title's layout must be verified against the official UDP specification
before live use — hence the ``packet_format`` check at parse time.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum

SUPPORTED_FORMATS = frozenset({2023, 2024, 2025})

_HEADER = struct.Struct("<HBBBBBQfIIBB")
HEADER_SIZE = _HEADER.size  # 29


class PacketId(IntEnum):
    MOTION = 0
    SESSION = 1
    LAP_DATA = 2
    EVENT = 3
    PARTICIPANTS = 4
    CAR_SETUPS = 5
    CAR_TELEMETRY = 6
    CAR_STATUS = 7
    FINAL_CLASSIFICATION = 8
    LOBBY_INFO = 9
    CAR_DAMAGE = 10
    SESSION_HISTORY = 11
    TYRE_SETS = 12
    MOTION_EX = 13


class ProtocolError(ValueError):
    """Raised when a datagram cannot be interpreted."""


@dataclass(frozen=True, slots=True)
class PacketHeader:
    packet_format: int
    game_year: int
    game_major_version: int
    game_minor_version: int
    packet_version: int
    packet_id: PacketId
    session_uid: int
    session_time: float
    frame_identifier: int
    overall_frame_identifier: int
    player_car_index: int
    secondary_player_car_index: int

    @classmethod
    def parse(cls, data: bytes) -> "PacketHeader":
        if len(data) < HEADER_SIZE:
            raise ProtocolError(f"datagram too short for header: {len(data)} < {HEADER_SIZE}")
        fields = _HEADER.unpack_from(data)
        if fields[0] not in SUPPORTED_FORMATS:
            raise ProtocolError(f"unsupported packet format: {fields[0]}")
        try:
            packet_id = PacketId(fields[5])
        except ValueError as exc:
            raise ProtocolError(f"unknown packet id: {fields[5]}") from exc
        return cls(*fields[:5], packet_id, *fields[6:])

    def pack(self) -> bytes:
        """Inverse of :meth:`parse`; used to synthesise datagrams in tests and replays."""
        return _HEADER.pack(
            self.packet_format,
            self.game_year,
            self.game_major_version,
            self.game_minor_version,
            self.packet_version,
            int(self.packet_id),
            self.session_uid,
            self.session_time,
            self.frame_identifier,
            self.overall_frame_identifier,
            self.player_car_index,
            self.secondary_player_car_index,
        )
