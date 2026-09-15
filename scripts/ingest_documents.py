"""Ingest all PDFs from a directory. Idempotent: skips unchanged files."""
from pathlib import Path

from persian_enterprise_rag.cleaning.normalizer import normalize_document
from persian_enterprise_rag.ingestion.registery import DocumentRegistry
from persian_enterprise_rag.parsing.pymupdf_parser import PyMuPDFParser


def ingest_directory(pdf_dir: Path, registry: DocumentRegistry) -> dict:
    """Ingest all PDFs. Returns summary stats."""
    parser = PyMuPDFParser()
    stats = {"processed": 0, "skipped": 0, "failed": 0, "scanned": 0}

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {pdf_dir}")

    for pdf_path in pdf_files:
        should, reason = registry.should_process(pdf_path)

        if not should:
            print(f"[SKIP] {pdf_path.name} — {reason}")
            stats["skipped"] += 1
            continue

        try:
            parsed = parser.parse(pdf_path)

            if parsed.is_likely_scanned:
                print(f"[WARN] {pdf_path.name} — likely scanned (no text layer)")
                stats["scanned"] += 1

            # Normalize all pages
            normalize_document(parsed.pages)

            # Persist registry record
            doc_hash = registry.compute_hash(pdf_path)
            registry.record(
                doc_id=doc_hash,
                source_path=str(pdf_path),
                status="processed",
                parser_used=parsed.parser_used,
            )

            # For now, just print what we got (Week 2 will chunk + embed)
            total_chars = sum(len(p.text) for p in parsed.pages)
            print(
                f"[OK] {pdf_path.name} — {parsed.total_pages} pages, "
                f"{total_chars} chars, parser={parsed.parser_used}"
            )
            stats["processed"] += 1

        except Exception as e:
            print(f"[FAIL] {pdf_path.name} — {e}")
            stats["failed"] += 1
            # Record failure so we don't retry endlessly
            registry.record(
                doc_id=registry.compute_hash(pdf_path),
                source_path=str(pdf_path),
                status="failed",
            )

    return stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_documents.py <pdf_directory>")
        sys.exit(1)

    pdf_dir = Path(sys.argv[1])
    registry = DocumentRegistry(Path("/home/hossein/Desktop/Projects/persian-enterprise-rag/src/persian_enterprise_rag/db/documents.db"))

    stats = ingest_directory(pdf_dir, registry)
    print(f"\nDone: {stats}")