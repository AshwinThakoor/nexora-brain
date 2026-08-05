from __future__ import annotations
import argparse, json, sys
from pydantic import ValidationError
from .database import SessionLocal
from .db_management import initialize_development_database
from .ingest import ingest_document
from .schemas import IngestRequest, LICENSES
from .services import knowledge_stats, search_knowledge

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NEXORA Knowledge Engine")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init-db", help="Create database tables.")
    ingest = subs.add_parser("ingest", help="Ingest a document.")
    ingest.add_argument("file_path")
    ingest.add_argument("--title")
    ingest.add_argument("--author")
    ingest.add_argument("--publisher")
    ingest.add_argument("--source-name")
    ingest.add_argument("--source-url")
    ingest.add_argument("--license-status", default="UNKNOWN", choices=sorted(LICENSES))
    ingest.add_argument("--license-notes")
    ingest.add_argument("--commercial-use-allowed", action="store_true")
    ingest.add_argument("--quality-score", type=int, default=50)
    search = subs.add_parser("search", help="Search knowledge.")
    search.add_argument("query")
    search.add_argument("--category")
    search.add_argument("--limit", type=int, default=10)
    subs.add_parser("stats", help="Show statistics.")
    return parser

def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "init-db":
            initialize_development_database()
            print("Database initialized successfully.")
            return 0
        with SessionLocal() as db:
            if args.command == "ingest":
                document = ingest_document(db, IngestRequest(
                    file_path=args.file_path, title=args.title, author=args.author,
                    publisher=args.publisher, source_name=args.source_name,
                    source_url=args.source_url, license_status=args.license_status,
                    license_notes=args.license_notes,
                    commercial_use_allowed=args.commercial_use_allowed,
                    quality_score=args.quality_score,
                ))
                print(json.dumps({"document_id":document.id,"title":document.title,
                                  "category":document.category,"chunks":len(document.chunks)}, indent=2))
                return 0
            if args.command == "search":
                results = search_knowledge(db, args.query, args.category, args.limit)
                if not results:
                    print("No matching knowledge found.")
                    return 0
                for result in results:
                    print(f"\n[{result.category}] {result.document_title} "
                          f"(chunk={result.chunk_index}, score={result.score})")
                    print("-"*72)
                    print(result.content)
                return 0
            print(json.dumps(knowledge_stats(db), indent=2))
            return 0
    except (ValidationError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
