"""Runtime configuration (environment-driven, prefix ``F1_``)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="F1_")

    data_dir: Path = Path("./data")
    jolpica_base_url: str = "https://api.jolpi.ca/ergast/f1"
    page_size: int = 100  # Jolpica's maximum
    hourly_limit: int = 500  # Jolpica sustained limit
    burst_per_second: int = 4  # Jolpica burst limit
    user_agent: str = "f1-data-platform/0.1 (open-source F1 data portfolio)"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def staging_dir(self) -> Path:
        return self.data_dir / "staging"

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "f1.duckdb"
