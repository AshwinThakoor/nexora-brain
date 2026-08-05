# NEXORA Brain

![CI](https://img.shields.io/badge/ci-checks-passing-brightgreen)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-important)

NEXORA Brain is a knowledge ingestion and knowledge-graph component. This repository contains the brain service, API, database schema and supporting utilities. The README focuses on the features that are implemented and tested in this export; unsupported or unverified claims (for example EPUB support or "production-ready") have been removed.

## Highlights

- FastAPI-based HTTP API for ingestion, search and knowledge management.
- SQLAlchemy models and Alembic migrations manage the database schema.
- Source Registry and Document Registry to track document provenance and source metadata.
- Secure storage abstraction (pluggable providers) for uploaded content and artifacts.
- Ingestion orchestration: deterministic parsing pipelines for TXT, PDF, DOCX, Markdown and HTML inputs.
- Persistent ParseResult storage for parsed documents and extracted metadata.
- Deterministic chunking with provenance metadata for downstream indexing and reasoning.
- Academy: curriculum, learner progress, assessments, grading and review primitives.
- Test suite covering core services, migrations and API routes.

## Architecture

```mermaid
graph TD
	subgraph Ingestion
		A[Upload/API] --> B[Parsers: TXT, PDF, DOCX, Markdown, HTML]
		B --> C[Deterministic Chunking]
	end
	C --> D[Persistent ParseResult Storage]
	D --> E[Knowledge Graph (Source & Document Registry)]
	E --> F[FastAPI API Layer]
	F --> G[SQLAlchemy + Alembic (Relational DB)]
	H[Secure Storage Provider] --> D
	F --> I[Academy: curriculum & grading]
	style A fill:#f9f,stroke:#333,stroke-width:1px
```

## API

- FastAPI app is exposed via `nexora_knowledge.api`.
- OpenAPI / Swagger UI: `/docs`
- ReDoc: `/redoc`

Key route groups (examples):

- `/api/v1/ingest` — document upload and ingestion orchestration.
- `/api/v1/documents` — document registry access, metadata and ParseResult retrieval.
- `/api/v1/sources` — source registry management.
- `/api/v1/knowledge` — knowledge graph endpoints (queries, relationships).
- `/api/v1/academy` — curriculum, learner progress, assessments and grading endpoints.

See `API_DOCUMENTATION.md` for a full route listing.

## Authentication & Authorization

- The API includes authorization hooks (dependency-injected guards) for protected endpoints. Review the security configuration in `CONFIGURATION.md` and the FastAPI dependency providers to enable OAuth2 / API-key based auth for your deployment.

## Parsing & Ingestion

- Supported input formats (verified): TXT, PDF, DOCX, Markdown and HTML.
- Parsers produce a `ParseResult` object which is stored persistently and linked to the Document Registry entry.
- Ingestion orchestration coordinates parsing, deterministic chunking, metadata extraction and storage.

## Deterministic Chunking and Provenance

- Chunking is deterministic: identical inputs produce identical chunk boundaries and chunk IDs.
- Each chunk carries provenance metadata linking it back to the source document, parser version and ingestion event.

## Storage and Registries

- Source Registry: canonicalizes and tracks upstream sources (URLs, providers, uploads).
- Document Registry: tracks ingested document records and links to ParseResults.
- Secure Storage: an abstraction layer for provider-backed secure storage; backends are configured via `CONFIGURATION.md`.

## Academy (Learning & Grading)

- Curriculum and learner-tracking primitives exist to model courses, lessons and assessments.
- Learner progress, assessment results and grading flows are available through API endpoints; see `PROJECT_STRUCTURE.md` and `API_DOCUMENTATION.md` for implementation details.

## Database & Migrations

- SQLAlchemy is the ORM used across models.
- Alembic manages migrations; migration scripts live in `alembic/versions`.

Common Alembic commands (quick reference):

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic heads
```

## Testing

- Tests are implemented with `pytest` under `tests/`.
- Recommended: create a virtual environment, install `requirements-dev.txt` and run `python -m pytest`.

## Quick start

Windows (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest
uvicorn nexora_knowledge.api:app --reload
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -m alembic upgrade head
python -m pytest
uvicorn nexora_knowledge.api:app --reload
```

Swagger UI: `http://127.0.0.1:8000/docs`
ReDoc: `http://127.0.0.1:8000/redoc`

## Configuration

Configuration is environment-driven. Copy `.env.example` to `.env` and update `DATABASE_URL`, storage provider keys and auth settings. See `CONFIGURATION.md` for all supported variables.

## Known limitations

- EPUB support and other unverified features were removed from this README: only formats explicitly handled in parsers are documented here (TXT, PDF, DOCX, Markdown, HTML).
- This export is a component-focused package and may require configuration for production deployments (storage backends, secret management, TLS, authentication).

## Roadmap

- Improve parser coverage and performance profiling.
- Add pluggable ML-backed document classifiers as an optional component.
- Harden production operational guidance (secrets, rotation, SSO integration).

## Security

- Do not commit secrets. Use environment variables or a secret manager for credentials.
- Restrict access to storage backends and database instances.
- Review `SECURITY.md` for responsible disclosure and known vulnerabilities.

## License

This repository is released under the MIT License.

Author: Ashwin Thakoor

## Documentation links

- `API_DOCUMENTATION.md`
- `CONFIGURATION.md`
- `INSTALLATION.md`
- `TESTING.md`
- `DATABASE_SCHEMA.md`

---
