from pathlib import Path

import pytest

from study_brain.s3io import ObjectStore
from study_brain.settings import Settings


def test_bucket_is_required(tmp_path: Path):
    with pytest.raises(ValueError):
        Settings(bucket="", work_dir=tmp_path)


def test_object_key_cannot_escape_work_directory():
    with pytest.raises(ValueError):
        ObjectStore.safe_path("../outside.pdf")


def test_write_back_is_disabled_by_default(tmp_path: Path):
    settings = Settings(bucket="example-bucket", work_dir=tmp_path)
    assert settings.derived_prefix is None

def test_environment_config_is_used(monkeypatch, tmp_path: Path):
    from study_brain.cli import build_parser

    monkeypatch.setenv("STUDY_BRAIN_BUCKET", "notes-bucket")
    monkeypatch.setenv("STUDY_BRAIN_ENDPOINT_URL", "https://storage.example.test")
    monkeypatch.setenv("STUDY_BRAIN_REGION", "test-region-1")
    monkeypatch.setenv("STUDY_BRAIN_PROFILE", "study")
    monkeypatch.setenv("STUDY_BRAIN_SOURCE_PREFIX", "incoming")
    monkeypatch.setenv("STUDY_BRAIN_DERIVED_PREFIX", "markdown")
    monkeypatch.setenv("STUDY_BRAIN_WORK_DIR", str(tmp_path))

    args = build_parser().parse_args(["sync"])

    assert args.bucket == "notes-bucket"
    assert args.endpoint_url == "https://storage.example.test"
    assert args.region == "test-region-1"
    assert args.profile == "study"
    assert args.source_prefix == "incoming"
    assert args.derived_prefix == "markdown"
    assert args.work_dir == tmp_path


def test_cli_value_overrides_environment(monkeypatch):
    from study_brain.cli import build_parser

    monkeypatch.setenv("STUDY_BRAIN_BUCKET", "from-environment")
    args = build_parser().parse_args(["sync", "--bucket", "from-command-line"])

    assert args.bucket == "from-command-line"

def test_write_back_can_be_enabled_from_environment(monkeypatch):
    from study_brain.cli import build_parser

    monkeypatch.setenv("STUDY_BRAIN_BUCKET", "notes")
    monkeypatch.setenv("STUDY_BRAIN_WRITE_BACK", "true")
    args = build_parser().parse_args(["sync"])

    assert args.write_back is True
