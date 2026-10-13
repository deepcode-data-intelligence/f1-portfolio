"""Runtime configuration (environment-driven, 12-factor)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    boxbox_url: str = os.environ.get("BOXBOX_URL", "http://localhost:8081")


settings = Settings()
