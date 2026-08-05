# NEXORA Brain

NEXORA Brain is a standalone knowledge ingestion and knowledge graph engine.
This repository contains only the brain component and its documentation.

## What this repository includes

- Document ingestion for TXT, Markdown, PDF, and EPUB.
- Text cleaning, chunking, and classification.
- Knowledge Graph models for categories, concepts, claims, evidence, and sources.
- FastAPI endpoints for ingestion, search, and knowledge management.
- Alembic migrations for schema evolution.
- Automated tests covering models, services, migrations, and APIs.

## Quick start

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest
```

### Linux and macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -m alembic upgrade head
python -m pytest
```

## Configuration

Copy `.env.example` to `.env` and update environment variables as needed.

## Running the API

```bash
uvicorn nexora_knowledge.api:app --reload
```

Open the API docs at:

```text
http://127.0.0.1:8000/docs
```

## Documentation

- `ARCHITECTURE.md`
- `INSTALLATION.md`
- `CONFIGURATION.md`
- `TESTING.md`
- `API_DOCUMENTATION.md`
- `DATABASE_SCHEMA.md`
- `PROJECT_STRUCTURE.md`
- `KNOWN_ISSUES.md`
- `FAQ.md`
- `RELEASES.md`

## Notes

- This repository is the NEXORA Brain component only.
- Do not commit `.env`, `.venv`, or generated database files.
- Alembic uses `DATABASE_URL` from `.env` or environment variables.
