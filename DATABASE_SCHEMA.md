# Database Schema

This project uses SQLAlchemy models and Alembic migrations to manage the database schema.

## Migrations

Migrations are stored in `alembic/versions/`.

The current migration history includes:

- `2b_s2_001_initial_schema.py`
- `2c_s1_001_add_rich_knowledge_foundation.py`
- `2d_s1_001_add_academy_curriculum.py`
- `2d_s2_001_add_learner_engine.py`
- `2d_s3_001_add_academy_grading.py`
- `3a_s1_001_add_source_registry.py`
- `3a_s2_001_add_document_registry.py`
- `3a_s3_001_add_ingestion_orchestration.py`
- `3a_s4_001_add_secure_storage.py`
- `3a_s5_001_add_persistent_parser_results.py`
- `3a_s6_001_add_deterministic_chunking.py`

## SQLite support

The project supports SQLite through SQLAlchemy and uses `alembic` with `render_as_batch` when needed.
