from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..cleaner import clean_text
from ..parsers import SUPPORTED_EXTENSIONS, parse_document
from .pipeline import build_knowledge
from .utils import KnowledgeBuildResult


def import_document(
    path: str | Path,
    metadata: Mapping[str, Any] | None = None,
    *,
    db: Session | None = None,
) -> KnowledgeBuildResult:
    document_path = Path(path).expanduser().resolve()
    if not document_path.is_file():
        raise ValueError(f"Document does not exist: {document_path}")
    if document_path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {document_path.suffix.casefold()}")

    text = clean_text(parse_document(str(document_path)))
    if len(text) < 20:
        raise ValueError("No usable text was extracted from the document")

    source_metadata = dict(metadata or {})
    source_metadata.setdefault("title", document_path.stem)
    source_metadata.setdefault(
        "source_type",
        document_path.suffix.casefold().lstrip(".") or "document",
    )
    return build_knowledge(text, source_metadata, db=db)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build structured NEXORA knowledge from a document."
    )
    parser.add_argument("path", help="TXT, Markdown, PDF, or EPUB document path")
    parser.add_argument("--title")
    parser.add_argument("--author")
    parser.add_argument("--publisher")
    parser.add_argument("--publication-year", type=int)
    parser.add_argument("--url")
    parser.add_argument("--license")
    parser.add_argument("--source-type")
    return parser


def main() -> None:
    arguments = build_argument_parser().parse_args()
    metadata = {
        key: value
        for key, value in {
            "title": arguments.title,
            "author": arguments.author,
            "publisher": arguments.publisher,
            "publication_year": arguments.publication_year,
            "url": arguments.url,
            "license": arguments.license,
            "source_type": arguments.source_type,
        }.items()
        if value is not None
    }
    report = import_document(arguments.path, metadata)
    print(json.dumps(report.to_report(), indent=2, ensure_ascii=False))
    if report.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
