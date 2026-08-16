# NEXORA Brain — Installation

## Requirements

- Python 3.11 or later
- `pip`
- Git (when cloning the repository)

SQLite is sufficient for the default local development environment.

## 1. Create a virtual environment

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 2. Install development dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## 3. Create local configuration

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

The provided example configuration uses local/development values. Keep `.env` private; it is excluded from Git.

## 4. Apply database migrations

```bash
python -m alembic upgrade head
```

Schema changes are managed through Alembic, so migrations should be applied before the application starts.

## 5. Run tests

```bash
python -m pytest
```

## 6. Start the API

```bash
uvicorn nexora_knowledge.api:app --reload
```

Then open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Development database

The default example configuration uses a local SQLite database. Generated database files are excluded by `.gitignore`.

## Troubleshooting

### Migration errors

Confirm the virtual environment is active, dependencies are installed and the database URL is valid, then rerun:

```bash
python -m alembic upgrade head
```

### Import errors

Run commands from the repository root and verify the active interpreter:

```bash
python --version
python -m pip --version
```

### Test isolation

The core suite should not require production external services. CI uses temporary SQLite database files.

## Production note

This guide describes local development. A production deployment would additionally require a production database/storage design, secret management, authentication integration, TLS/reverse proxying, monitoring, backup/recovery and other infrastructure controls.
