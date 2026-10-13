"""Runtime configuration (environment-driven)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIM_")

    udp_host: str = "0.0.0.0"
    udp_port: int = 20777  # the game's default telemetry port
    boxbox_url: str = "http://localhost:8081"
    buffer_dir: Path = Path("./data/buffer")
    # Default exception deviation per tag family, in engineering units. Overridable per tag.
    default_exception_deviation: float = 0.0


settings = Settings()
