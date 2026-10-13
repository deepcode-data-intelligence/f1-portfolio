"""Core data types shared with the historian's ingestion contract."""

from dataclasses import dataclass

from f1_sim_connector.quality import Quality


@dataclass(frozen=True, slots=True)
class Sample:
    """One historian sample: tag × timestamp (ns since epoch, UTC) × value × quality."""

    tag: str
    timestamp_ns: int
    value: float
    quality: Quality = Quality.GOOD
