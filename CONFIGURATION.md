# Configuration

Configuration is controlled through environment variables.

## Example

Copy `.env.example` to `.env` and edit values as needed.

## Key variables

- `DATABASE_URL`: SQLAlchemy database URL for SQLite or MySQL.
- `NEXORA_CHUNK_SIZE`: document chunk size.
- `NEXORA_CHUNK_OVERLAP`: chunk overlap amount.
- `NEXORA_DEFAULT_STORAGE_PROVIDER`: storage backend, usually `local`.
- `NEXORA_LOCAL_STORAGE_ROOT`: local upload storage root.
