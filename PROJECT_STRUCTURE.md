# NEXORA Brain Pack 1 v2 - Project Structure

## Folder structure

The tree below is limited to the application's meaningful first two to three
levels. Generated `__pycache__/` directories and the contents of `.venv/` are
omitted.

```text
NEXORA_Brain_Pack1_v2/
|-- .venv/                         # Local Python virtual environment
|-- knowledge_sources/
|   `-- raw/
|       `-- test_trading.txt       # Sample source document
|-- nexora_knowledge/
|   |-- api/
|   |   `-- __init__.py            # FastAPI app and route handlers
|   |-- models/
|   |   `-- __init__.py            # SQLAlchemy ORM models
|   |-- schemas/
|   |   `-- __init__.py            # Pydantic request/response schemas
|   |-- services/
|   |   `-- __init__.py            # Search and statistics services
|   |-- __init__.py
|   |-- chunker.py                  # Splits cleaned text into chunks
|   |-- classifier.py               # Rule-based content classification
|   |-- cleaner.py                  # Text normalization
|   |-- cli.py                      # Command-line entry point
|   |-- config.py                   # Environment-backed settings
|   |-- database.py                 # SQLAlchemy base, engine, and session factory
|   |-- ingest.py                   # Document ingestion workflow
|   `-- parsers.py                  # TXT, Markdown, PDF, and EPUB parsing
|-- tests/
|   |-- conftest.py                 # Pytest database fixture
|   `-- test_core.py                # Core unit/integration tests
|-- .env                            # Local environment configuration
|-- .env.example                    # Example environment configuration
|-- pyproject.toml                  # Project metadata and pytest configuration
|-- README.md                       # Setup and usage instructions
`-- requirements.txt                # Pinned Python dependencies
```

## Application and database locations

### FastAPI application start

The ASGI application object is created as `app` in
`nexora_knowledge/api/__init__.py`:

```python
app = FastAPI(title="NEXORA Knowledge Engine", version="2.0.0")
```

The documented development command starts it with:

```powershell
uvicorn nexora_knowledge.api:app --reload
```

The same module also registers a startup handler that calls
`init_database()` to create the database tables.

### SQLAlchemy models

The ORM models are defined in `nexora_knowledge/models/__init__.py`:

- `KnowledgeDocument`
- `KnowledgeChunk`

Their shared declarative base, `Base`, is defined in
`nexora_knowledge/database.py`.

### Database session

`nexora_knowledge/database.py` creates the SQLAlchemy `engine` and the
`SessionLocal` session factory at module load time.

For API requests, `nexora_knowledge/api/__init__.py` creates a session by
calling `SessionLocal()` inside the `get_db()` dependency and closes it after
the request. The CLI also opens sessions from `SessionLocal` in
`nexora_knowledge/cli.py`.

### API routes

All API routes are declared directly in `nexora_knowledge/api/__init__.py`:

- `GET /health`
- `POST /ingest`
- `GET /search`
- `GET /stats`

There are no separate router modules or `APIRouter` instances in the current
project.

### Tests

Tests are located in `tests/`:

- `tests/conftest.py` provides an in-memory SQLite session fixture.
- `tests/test_core.py` tests cleaning, chunking, classification, ingestion,
  duplicate protection, search, and statistics.

Pytest is configured in `pyproject.toml` to use `tests/` as its test path.

## Major folder descriptions

- `.venv/` - Generated local Python environment containing installed
  dependencies and command-line executables; it is not application source.
- `knowledge_sources/` - Input documents intended for ingestion into the
  knowledge database. Its `raw/` subfolder currently contains a sample trading
  document.
- `nexora_knowledge/` - Main Python package. It contains configuration,
  persistence, parsing, cleaning, chunking, classification, ingestion, search,
  API, and CLI functionality.
- `nexora_knowledge/api/` - FastAPI application object, lifecycle hook,
  database dependency, and HTTP route handlers.
- `nexora_knowledge/models/` - SQLAlchemy mappings for stored documents and
  their text chunks.
- `nexora_knowledge/schemas/` - Pydantic request validation and API response
  data structures.
- `nexora_knowledge/services/` - Database-backed search and knowledge-statistics
  operations shared by the API and CLI.
- `tests/` - Pytest fixtures and automated coverage of the core knowledge
  processing and persistence workflow.
