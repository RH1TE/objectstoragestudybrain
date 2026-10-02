from pathlib import Path

from study_brain.index import refresh, search


def test_index_and_search(tmp_path: Path):
    notes = tmp_path / "markdown"
    notes.mkdir()
    (notes / "waves.md").write_text(
        "# Waves\n\nDiffraction becomes important when the aperture is small."
    )
    database = tmp_path / "index.sqlite3"

    assert refresh(notes, database) == 1

    results = search(database, "diffraction aperture")

    assert results
    assert results[0]["heading"] == "Waves"
    assert "Diffraction" in results[0]["text"]


def test_refresh_removes_deleted_files(tmp_path: Path):
    notes = tmp_path / "markdown"
    notes.mkdir()
    note = notes / "temporary.md"
    note.write_text("# Topic\n\nTemporary searchable material.")
    database = tmp_path / "index.sqlite3"

    refresh(notes, database)
    note.unlink()
    assert refresh(notes, database) == 1
    assert search(database, "Temporary") == []
