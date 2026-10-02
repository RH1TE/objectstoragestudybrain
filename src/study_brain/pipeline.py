from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .converters import convert
from .index import refresh
from .s3io import ObjectStore
from .settings import Settings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "objects": {}}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "objects": {}}
    if not isinstance(data.get("objects"), dict):
        return {"version": 1, "objects": {}}
    return data


def _save_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["version"] = 1
    data["updated_at"] = datetime.now(UTC).isoformat()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)

def _frontmatter(source_key: str, metadata: dict, digest: str, status: str) -> str:
    values = [
        "---",
        "study_source: true",
        f"source_key: {json.dumps(source_key)}",
        f"source_etag: {json.dumps(metadata.get('etag', ''))}",
        f"source_last_modified: {json.dumps(metadata.get('last_modified', ''))}",
        f"source_sha256: {json.dumps(digest)}",
        f"conversion_status: {json.dumps(status)}",
        f"converted_at: {json.dumps(datetime.now(UTC).isoformat())}",
        "---",
        "",
    ]
    return "\n".join(values)


def _remove_local(entry: dict, work_dir: Path) -> None:
    root = work_dir.resolve()
    for field in ("source_local", "markdown_local"):
        value = entry.get(field)
        if not value:
            continue
        path = Path(value)
        try:
            path.resolve().relative_to(root)
        except (OSError, ValueError):
            continue
        if path.is_file():
            path.unlink()


def sync(settings: Settings, write_back: bool = False) -> dict:
    settings.source_dir.mkdir(parents=True, exist_ok=True)
    settings.markdown_dir.mkdir(parents=True, exist_ok=True)
    settings.state_dir.mkdir(parents=True, exist_ok=True)

    store = ObjectStore(settings)
    manifest = _load_manifest(settings.manifest_path)
    current = store.list_sources()
    converted = 0
    failed = 0
    for key, metadata in current.items():
        prior = manifest["objects"].get(key, {})
        fingerprint = (metadata["etag"], metadata["size"])
        same = (prior.get("etag"), prior.get("size")) == fingerprint

        if same and str(prior.get("status", "")).startswith("error:"):
            continue
        markdown_local = prior.get("markdown_local")
        if same and markdown_local and Path(markdown_local).is_file():
            continue

        rel = store.safe_path(store.relative_key(key) or key)
        source_path = settings.source_dir / rel
        markdown_path = settings.markdown_dir / Path(str(rel) + ".md")

        try:
            store.download(key, source_path)
            body, status = convert(source_path)
            digest = _sha256(source_path)
            title = rel.stem.replace("_", " ").replace("-", " ").strip() or rel.name
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(
                _frontmatter(key, metadata, digest, status)
                + f"# {title}\n\n"
                + body.strip()
                + "\n",
                encoding="utf-8",
            )

            derived_key = store.upload_markdown(key, markdown_path) if write_back else None
            manifest["objects"][key] = {
                **metadata,
                "sha256": digest,
                "source_local": str(source_path),
                "markdown_local": str(markdown_path),
                "derived_key": derived_key,
                "status": status,
                "converted_at": datetime.now(UTC).isoformat(),
            }
            converted += 1
        except Exception as exc:  # noqa: BLE001 - keep one bad file from stopping the sync
            name = type(exc).__name__
            if markdown_path.is_file():
                markdown_path.unlink()
            manifest["objects"][key] = {
                **metadata,
                "source_local": str(source_path),
                "markdown_local": str(markdown_path),
                "status": f"error:{name}",
                "error": name,
                "failed_at": datetime.now(UTC).isoformat(),
            }
            failed += 1

    removed = 0
    for key in list(manifest["objects"]):
        if key in current:
            continue
        _remove_local(manifest["objects"][key], settings.work_dir)
        del manifest["objects"][key]
        removed += 1

    _save_manifest(settings.manifest_path, manifest)
    indexed = refresh(settings.markdown_dir, settings.index_path)

    return {
        "sources": len(manifest["objects"]),
        "converted": converted,
        "failed": failed,
        "removed_local": removed,
        "index_changes": indexed,
    }
