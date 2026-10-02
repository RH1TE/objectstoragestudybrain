from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    bucket: str
    work_dir: Path
    source_prefix: str = ""
    derived_prefix: str | None = None
    endpoint_url: str | None = None
    region: str | None = None
    profile: str | None = None

    def __post_init__(self) -> None:
        if not self.bucket.strip():
            raise ValueError("bucket is required")
        if self.derived_prefix is not None and not self.derived_prefix.strip("/"):
            object.__setattr__(self, "derived_prefix", None)

    @property
    def source_dir(self) -> Path:
        return self.work_dir / "source"

    @property
    def markdown_dir(self) -> Path:
        return self.work_dir / "markdown"

    @property
    def state_dir(self) -> Path:
        return self.work_dir / "state"

    @property
    def manifest_path(self) -> Path:
        return self.state_dir / "manifest.json"

    @property
    def index_path(self) -> Path:
        return self.work_dir / "index.sqlite3"
