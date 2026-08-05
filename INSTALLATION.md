# Installation

## Requirements

- Python 3.11 or later
- `pip`

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Setup

```bash
cp .env.example .env
python -m alembic upgrade head
```
