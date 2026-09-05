# Eldercare

Consent-gated care briefs for elderly people receiving in-home care. See
[architecture.md](architecture.md) for the design and
[codebase-and-tasks.md](codebase-and-tasks.md) for the task split.

## Layout

```
backend/        FastAPI app (SQLite)      -- Person A
brief_builder/  pure-Python brief pipeline -- Person C
data/           seed data + observation codes
frontend/       Vite + React + Tailwind    -- Person B (not built yet)
```

## Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd backend
uvicorn app.main:app --reload
```

The API is then at `http://127.0.0.1:8000` (docs at `/docs`).
