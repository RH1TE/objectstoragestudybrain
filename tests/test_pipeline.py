from pathlib import Path

from study_brain import pipeline
from study_brain.index import search
from study_brain.settings import Settings


class FakeStore:
    def __init__(self):
        self.etag = "one"
        self.size = 10

    def list_sources(self):
        return {
            "topic.txt": {
                "etag": self.etag,
                "size": self.size,
                "last_modified": "2026-01-01T00:00:00+00:00",
            }
        }

    def relative_key(self, key):
        return key

    def safe_path(self, key):
        return Path(key)

    def download(self, key, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("source")

    def upload_markdown(self, key, path):
        return None


def test_failed_replacement_removes_stale_markdown(tmp_path, monkeypatch):
    settings = Settings(bucket="example-bucket", work_dir=tmp_path)
    store = FakeStore()
    monkeypatch.setattr(pipeline, "ObjectStore", lambda _settings: store)
    monkeypatch.setattr(pipeline, "convert", lambda _path: ("old searchable text", "ok"))

    first = pipeline.sync(settings)
    assert first["converted"] == 1
    assert search(settings.index_path, "searchable")

    store.etag = "two"
    store.size = 11

    def fail(_path):
        raise ValueError("broken input")

    monkeypatch.setattr(pipeline, "convert", fail)
    second = pipeline.sync(settings)

    assert second["failed"] == 1
    assert not (settings.markdown_dir / "topic.txt.md").exists()
    assert search(settings.index_path, "searchable") == []
