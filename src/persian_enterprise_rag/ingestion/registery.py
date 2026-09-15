"""Document registry: tracks what's been ingested, when, and its content hash."""
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class DocumentRecord:
    doc_id: str          # SHA-256 of file content
    source_path: str
    ingested_at: datetime
    status: str          # "processed" | "failed" | "skipped"
    parser_used: Optional[str] = None


class DocumentRegistry:
    """SQLite-backed registry ensuring idempotent ingestion."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parser_used TEXT
                )
            """)
            # Index on source_path: fast lookup when checking if a file changed
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_path
                ON documents(source_path)
            """)

    @staticmethod
    def compute_hash(file_path: Path) -> str:
        """SHA-256 of file bytes. Content-based, not name-based."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in 64KB chunks for memory efficiency
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def get_by_source(self, source_path: str) -> Optional[DocumentRecord]:
        """Find existing record for a source path (most recent)."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT doc_id, source_path, ingested_at, status, parser_used
                   FROM documents WHERE source_path = ?
                   ORDER BY ingested_at DESC LIMIT 1""",
                (source_path,),
            ).fetchone()
        if row:
            return DocumentRecord(
                doc_id=row[0], source_path=row[1],
                ingested_at=datetime.fromisoformat(row[2]),
                status=row[3], parser_used=row[4],
            )
        return None

    def should_process(self, file_path: Path) -> tuple[bool, str]:
        """Decide: (should_process, reason).
        
        This is the idempotency core:
        - New file → process
        - Same content, already processed → skip
        - Changed content → process (replaces old)
        """
        new_hash = self.compute_hash(file_path)
        existing = self.get_by_source(str(file_path))

        if existing is None:
            return True, "new_document"
        if existing.doc_id == new_hash and existing.status == "processed":
            return False, "unchanged"
        return True, "content_changed"

    def record(
        self, doc_id: str, source_path: str, status: str, parser_used: str | None = None
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO documents
                   (doc_id, source_path, ingested_at, status, parser_used)
                   VALUES (?, ?, ?, ?, ?)""",
                (doc_id, source_path, datetime.now().isoformat(), status, parser_used),
            )