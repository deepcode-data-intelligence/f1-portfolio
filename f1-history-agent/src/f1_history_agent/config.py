"""Runtime configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="F1_")

    data_dir: Path = Path("./data")

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "f1.duckdb"


settings = Settings()
