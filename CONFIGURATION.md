# NEXORA Brain — Configuration

NEXORA Brain uses environment-backed configuration through `pydantic-settings`.

## Local setup

Copy the example file and keep the resulting `.env` local:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

`.env` is excluded by `.gitignore` and must not contain values intended for source control.

## Configuration groups

### Database

`DATABASE_URL` selects the SQLAlchemy database connection. The development default is local SQLite. A `NEXORA_DATABASE_URL` value is retained as a compatibility fallback.

### Chunking

The application supports environment settings for the selected chunk strategy plus target, maximum, minimum and overlap sizing. Defaults live in application configuration so behavior is reproducible in local development.

### Ingestion

Configuration includes ingestion retry limits and upload-session lifetime.

### Upload policy

Maximum upload size, allowed extensions and allowed MIME types are configurable rather than being hard-coded into route handlers.

### Storage

The default provider is local storage and the storage root is configurable. Storage behavior is accessed through an application abstraction so additional providers can be implemented without rewriting the domain layer.

## Example configuration safety

`.env.example` contains only development/example values. Do not place API keys, access tokens, passwords, production database credentials, private endpoints or personal data in the example file.

If a real secret is accidentally committed, removing it in a later commit is not sufficient: revoke/rotate the credential first, then clean repository history if required.

## Production note

A production deployment should supply configuration through its deployment platform or secret-management system rather than committing a populated `.env` file. Deployment hardening is outside the current repository's portfolio scope.
