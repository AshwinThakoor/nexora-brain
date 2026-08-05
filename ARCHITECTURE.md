# Architecture

NEXORA Brain is a standalone knowledge ingestion and knowledge graph engine.

## Components

- `nexora_knowledge` package: core ingestion, chunking, knowledge graph, and API services.
- `alembic/`: database migrations for schema evolution.
- `tests/`: automated tests for models, services, APIs, and migrations.
- `docs/`: architectural and sprint documentation.
- `knowledge_sources/`: sample documents used by tests and ingestion examples.

## Data model

- Documents are ingested and cleaned into canonical text chunks.
- Categories, concepts, claims, evidence, and sources form the knowledge graph.
- The system supports optional curriculum and academy entities.
