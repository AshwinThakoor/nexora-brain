# Pack 2B Sprint 2: Infrastructure Stabilization

This sprint makes the NEXORA Brain reproducible from a clean Python
installation and an empty database. Alembic is now the official schema
management mechanism, dependency roles are separated, migration behavior is
tested, and CI validates both migrations and the full application test suite.

## Why the existing virtual environment broke

A virtual environment is not a portable copy of Python. Its launchers and
`pyvenv.cfg` refer to the base Python installation that created it. The
existing `.venv` was created with Python 3.11, but that interpreter was later
removed or moved. The launcher therefore points to a path that no longer
exists.

Virtual environments also contain machine-specific paths, platform-specific
binaries, and installed third-party packages. They must never be committed.
The project `.gitignore` excludes `.venv` and other common environment names.
If an environment is broken, remove it manually and recreate it; project
commands do not delete it automatically.

## Clean setup

Python 3.11 is the CI-tested version. Copy `.python-version.example` to
`.python-version` only if your Python version manager uses that file.

### Windows PowerShell

Run these commands from the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest
```

If `.venv` is already broken, close programs using it and remove it manually
before running the setup commands:

```powershell
Remove-Item -LiteralPath .venv -Recurse -Force
```

### Linux and macOS

Run these commands from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest
```

If `.venv` is already broken, remove it manually before recreating it:

```bash
rm -rf .venv
```

`requirements.txt` contains application and migration dependencies.
`requirements-dev.txt` includes it and adds the test and API-client tools used
by the suite.

## Database configuration

The application and Alembic both call
`nexora_knowledge.config.get_database_url()`. Configuration precedence is:

1. An explicit URL supplied by application or test code.
2. `DATABASE_URL`.
3. The legacy `NEXORA_DATABASE_URL`.
4. `sqlite:///./nexora_brain.db`.

Create local configuration from the example:

```powershell
Copy-Item .env.example .env
```

For the default local SQLite database:

```env
DATABASE_URL=sqlite:///./nexora_brain.db
```

For MySQL, use a SQLAlchemy PyMySQL URL and percent-encode special characters
in credentials:

```env
DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/nexora_brain?charset=utf8mb4
```

SQLite-only connection arguments are applied only when the selected SQLAlchemy
dialect is SQLite. Tests can provide an explicit engine or point Alembic at a
temporary SQLite URL without touching the development database.

## Alembic architecture

`alembic.ini` points to the migration environment in `alembic/`. `env.py`
loads the shared database URL, imports every model through
`nexora_knowledge.models`, and exposes `Base.metadata` to Alembic. Both online
and offline modes are supported. SQLite migrations enable batch rendering for
future schema changes.

The initial revision, `2b_s2_001`, creates the complete current schema for Pack
1, Pack 2A, and Pack 2B-compatible models. It is a real schema migration, not a
placeholder.

### Create a migration

After changing SQLAlchemy models:

```powershell
python -m alembic revision --autogenerate -m "describe the schema change"
```

Review every generated operation before committing it. Autogeneration is a
review aid; it does not understand application intent.

### Apply and inspect migrations

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

### Downgrade migrations

Downgrade one revision:

```powershell
python -m alembic downgrade -1
```

Return an isolated database to the unmigrated base:

```powershell
python -m alembic downgrade base
```

Do not downgrade a shared or production database without a reviewed backup and
an operational rollback plan.

## Database initialization policy

Alembic is the official mechanism for all persistent, shared, and production
databases. API startup does not call `Base.metadata.create_all()` and does not
silently change the schema.

Initialize a clean configured database with:

```powershell
python -m alembic upgrade head
```

`nexora_knowledge.db_management` provides:

- `check_database_connection()` for a non-mutating connectivity check.
- `get_database_revision()` for reading the applied Alembic revision.
- `initialize_development_database()` as an explicit compatibility helper for
  local/test workflows that still need `Base.metadata.create_all()`.

The existing `python -m nexora_knowledge.cli init-db` command remains available
for local compatibility and delegates to the clearly named development helper.
Use that compatibility path only for disposable local databases; do not mix a
`create_all`-initialized database with Alembic migrations. Production
automation should use Alembic.

## Tests

Run the complete suite from the project root:

```powershell
python -m pytest
```

`tests/test_migrations.py` uses a temporary SQLite database. It validates
configuration loading, empty-to-head upgrade, expected tables, metadata/schema
comparison, downgrade to base, re-upgrade, and the current head revision.

For a manual isolated migration cycle in PowerShell:

```powershell
$env:DATABASE_URL = "sqlite:///./migration-check.sqlite"
python -m alembic upgrade head
python -m alembic current
python -m alembic history
python -m alembic downgrade base
python -m alembic upgrade head
Remove-Item Env:DATABASE_URL
Remove-Item -LiteralPath migration-check.sqlite
```

## CI workflow

`.github/workflows/ci.yml` runs on pushes and pull requests with Python 3.11.
It checks out the repository, installs `requirements-dev.txt`, migrates a
temporary SQLite database to head, and runs `python -m pytest`. A migration or
test failure fails the job.

## Troubleshooting

### PowerShell blocks `Activate.ps1`

Allow scripts only for the current PowerShell process, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

This does not change the machine-wide policy. If organizational policy still
blocks activation, invoke the environment interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### Imports fail

Run commands from the directory containing `pyproject.toml`,
`alembic.ini`, and `nexora_knowledge`. Prefer module invocation:

```powershell
python -m pytest
python -m alembic current
python -c "import nexora_knowledge; print(nexora_knowledge.__file__)"
```

Do not run a test file directly and do not rely on a globally installed
`pytest` executable.

### The Python launcher is missing

On Windows, install a supported Python 3.11 distribution with the Python
launcher enabled. Open a new PowerShell window and verify:

```powershell
py --version
py -0p
```

If `python` exists but `py` does not, use `python -m venv .venv`. On Linux or
macOS, verify `python3 --version` and install the operating system's Python
venv package if `python3 -m venv` is unavailable.
