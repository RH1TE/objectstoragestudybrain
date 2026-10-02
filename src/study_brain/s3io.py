from __future__ import annotations

from pathlib import Path, PurePosixPath

import boto3

from .converters import SUPPORTED
from .settings import Settings


class ObjectStore:
    def __init__(self, settings: Settings):
        session = boto3.Session(
            profile_name=settings.profile,
            region_name=settings.region,
        )
        self.client = session.client("s3", endpoint_url=settings.endpoint_url)
        self.settings = settings

    def relative_key(self, key: str) -> str | None:
        prefix = self.settings.source_prefix.strip("/")
        if not prefix:
            return key
        marker = prefix + "/"
        if not key.startswith(marker):
            return None
        return key[len(marker):]

    @staticmethod
    def safe_path(key: str) -> Path:
        path = PurePosixPath(key)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("unsafe object key")
        return Path(*path.parts)

    def list_sources(self) -> dict[str, dict]:
        paginator = self.client.get_paginator("list_objects_v2")
        args = {"Bucket": self.settings.bucket}
        if self.settings.source_prefix:
            args["Prefix"] = self.settings.source_prefix.strip("/") + "/"

        derived = (
            self.settings.derived_prefix.strip("/") + "/"
            if self.settings.derived_prefix
            else None
        )
        result: dict[str, dict] = {}

        for page in paginator.paginate(**args):
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith("/") or (derived and key.startswith(derived)):
                    continue
                rel = self.relative_key(key)
                if rel is None or Path(rel).suffix.lower() not in SUPPORTED:
                    continue
                modified = item.get("LastModified")
                result[key] = {
                    "etag": str(item.get("ETag", "")),
                    "size": int(item.get("Size", 0)),
                    "last_modified": modified.isoformat() if modified else "",
                }
        return result

    def download(self, key: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.settings.bucket, key, str(destination))

    def upload_markdown(self, source_key: str, path: Path) -> str | None:
        prefix = self.settings.derived_prefix
        if not prefix:
            return None
        rel = self.relative_key(source_key)
        if rel is None:
            return None
        destination = f"{prefix.strip('/')}/{PurePosixPath(rel).as_posix()}.md"
        self.client.upload_file(
            str(path),
            self.settings.bucket,
            destination,
            ExtraArgs={"ContentType": "text/markdown; charset=utf-8"},
        )
        return destination
