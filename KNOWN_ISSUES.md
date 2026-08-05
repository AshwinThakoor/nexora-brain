# Known Issues

- Some edge cases in document ingestion may produce duplicate chunks.
- The database schema migration history is stable, but local SQLite file paths should be configured explicitly.
- The package currently assumes Python 3.11 or later.
