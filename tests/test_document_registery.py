from datetime import datetime
from pathlib import Path

from persian_enterprise_rag.ingestion.registery import DocumentRegistry


def test_new_document_should_be_processed(tmp_path: Path):
    """A document that has never been seen should be processed."""
    db_path = tmp_path / "documents.db"
    file_path = tmp_path / "report.txt"

    file_path.write_text("Hello world")

    registry = DocumentRegistry(db_path)

    should_process, reason = registry.should_process(file_path)

    assert should_process is True
    assert reason == "new_document"


def test_unchanged_processed_document_should_be_skipped(tmp_path: Path):
    """A previously processed document with the same content should be skipped."""
    db_path = tmp_path / "documents.db"
    file_path = tmp_path / "report.txt"

    file_path.write_text("Hello world")

    registry = DocumentRegistry(db_path)

    # First, record that we successfully processed the document.
    doc_id = registry.compute_hash(file_path)

    registry.record(
        doc_id=doc_id,
        source_path=str(file_path),
        status="processed",
        parser_used="text",
    )

    # Check it again.
    should_process, reason = registry.should_process(file_path)

    assert should_process is False
    assert reason == "unchanged"


def test_changed_document_should_be_processed_again(tmp_path: Path):
    """A document whose content changed should be processed again."""
    db_path = tmp_path / "documents.db"
    file_path = tmp_path / "report.txt"

    file_path.write_text("Original content")

    registry = DocumentRegistry(db_path)

    # Record the original version.
    old_hash = registry.compute_hash(file_path)

    registry.record(
        doc_id=old_hash,
        source_path=str(file_path),
        status="processed",
        parser_used="text",
    )

    # Change the file.
    file_path.write_text("Changed content")

    should_process, reason = registry.should_process(file_path)

    assert should_process is True
    assert reason == "content_changed"


def test_get_by_source_returns_record(tmp_path: Path):
    """The registry should be able to retrieve a document record."""
    db_path = tmp_path / "documents.db"
    file_path = tmp_path / "report.txt"

    file_path.write_text("Hello world")

    registry = DocumentRegistry(db_path)

    doc_id = registry.compute_hash(file_path)

    registry.record(
        doc_id=doc_id,
        source_path=str(file_path),
        status="processed",
        parser_used="text",
    )

    record = registry.get_by_source(str(file_path))

    assert record is not None
    assert record.doc_id == doc_id
    assert record.source_path == str(file_path)
    assert record.status == "processed"
    assert record.parser_used == "text"
    assert isinstance(record.ingested_at, datetime)


def test_failed_document_should_be_processed_again(tmp_path: Path):
    """A document that previously failed should be retried."""
    db_path = tmp_path / "documents.db"
    file_path = tmp_path / "report.txt"

    file_path.write_text("Hello world")

    registry = DocumentRegistry(db_path)

    doc_id = registry.compute_hash(file_path)

    registry.record(
        doc_id=doc_id,
        source_path=str(file_path),
        status="failed",
        parser_used="text",
    )

    should_process, reason = registry.should_process(file_path)

    assert should_process is True
    assert reason == "content_changed"


def test_compute_hash_is_same_for_same_content(tmp_path: Path):
    """The same file content should always produce the same hash."""
    file_path = tmp_path / "report.txt"

    file_path.write_text("Hello world")

    hash1 = DocumentRegistry.compute_hash(file_path)
    hash2 = DocumentRegistry.compute_hash(file_path)

    assert hash1 == hash2


def test_compute_hash_changes_when_content_changes(tmp_path: Path):
    """Changing file content should change its SHA-256 hash."""
    file_path = tmp_path / "report.txt"

    file_path.write_text("Hello world")
    hash1 = DocumentRegistry.compute_hash(file_path)

    file_path.write_text("Something completely different")
    hash2 = DocumentRegistry.compute_hash(file_path)

    assert hash1 != hash2
