"""Runtime configuration (environment-driven)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DRIVER_")

    udp_host: str = "0.0.0.0"
    udp_port: int = 20778  # second listener; the game can broadcast or the connector can fan out
    boxbox_url: str = "http://localhost:8081"
    scripts_dir: Path = Path("./data/scripts")
    # Position hold: steering correction per metre of lateral error (dimensionless steer units/m).
    position_hold_gain: float = 0.02
    position_hold_max: float = 0.15  # cap on the correction so the script stays in charge
