# NEXORA Brain Pack 1 v2

This is the clean replacement for the earlier incomplete Pack 1.

## Included

- MySQL-ready SQLAlchemy database
- CLI: `init-db`, `ingest`, `search`, `stats`
- TXT, Markdown, PDF and EPUB ingestion
- Cleaning, chunking and rule-based classification
- Duplicate-file protection
- Source and licensing metadata
- FastAPI endpoints
- Automated tests

## Setup on Windows PowerShell

```powershell
cd "C:\path\to\NEXORA_Brain_Pack1_v2"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and confirm your MySQL connection:

```env
NEXORA_DATABASE_URL=mysql+pymysql://nexora:NexoraBrain2026@127.0.0.1:3306/nexora_brain?charset=utf8mb4
```

Initialize:

```powershell
python -m nexora_knowledge.cli init-db
```

Ingest the included test file:

```powershell
python -m nexora_knowledge.cli ingest ".\knowledge_sources\raw\test_trading.txt" --title "Trading Basics" --source-name "NEXORA Internal" --author "NEXORA" --license-status OWNED --commercial-use-allowed
```

Search:

```powershell
python -m nexora_knowledge.cli search "Bear Flag"
python -m nexora_knowledge.cli search "Bullish Engulfing"
python -m nexora_knowledge.cli search "risk management"
python -m nexora_knowledge.cli stats
```

Run the API:

```powershell
uvicorn nexora_knowledge.api:app --reload
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```powershell
pytest -q
```

Only ingest documents you own or are permitted to use.
