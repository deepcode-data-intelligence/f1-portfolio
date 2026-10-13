import pytest

from f1_sim_connector.protocol import HEADER_SIZE, PacketHeader, PacketId, ProtocolError


def make_header(**overrides) -> PacketHeader:
    base = dict(
        packet_format=2024,
        game_year=24,
        game_major_version=1,
        game_minor_version=0,
        packet_version=1,
        packet_id=PacketId.CAR_TELEMETRY,
        session_uid=0xDEADBEEF,
        session_time=12.5,
        frame_identifier=100,
        overall_frame_identifier=100,
        player_car_index=0,
        secondary_player_car_index=255,
    )
    return PacketHeader(**{**base, **overrides})


def test_header_round_trip() -> None:
    header = make_header()
    data = header.pack()
    assert len(data) == HEADER_SIZE == 29
    assert PacketHeader.parse(data + b"\x00" * 10) == header


def test_short_datagram_is_rejected() -> None:
    with pytest.raises(ProtocolError):
        PacketHeader.parse(b"\x00" * 5)


def test_unsupported_format_is_rejected() -> None:
    with pytest.raises(ProtocolError, match="unsupported packet format"):
        PacketHeader.parse(make_header(packet_format=2019).pack())
