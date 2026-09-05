# Eldercare

Consent-gated care briefs for elderly people receiving in-home care. See
[architecture.md](architecture.md) for the design and
[codebase-and-tasks.md](codebase-and-tasks.md) for the task split.

## Layout

```
backend/        FastAPI app (SQLite)       -- Person A
brief_builder/  pure-Python brief pipeline  -- Person C
data/           seed data + observation codes
frontend/       Vite + React + Tailwind     -- Person B (not built yet)
```

## Setup (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

## Run the backend

```powershell
cd backend
uvicorn app.main:app --reload
```

API at `http://127.0.0.1:8000`, interactive docs at `/docs`. On first start the
SQLite file `backend/eldercare.db` is created and seeded from `data/`.
`POST /reset` wipes and reseeds it at any time (demo runs).

Settings are env vars prefixed `ELDERCARE_` (see `backend/app/config.py`), e.g.
`ELDERCARE_FRONTEND_BASE_URL=http://localhost:5173` controls the visit link.

## Run the tests

```powershell
python -m pytest            # both packages, from the repo root
python -m pytest brief_builder/tests
python -m pytest backend/tests
```

## Demo "sessions"

There is no real auth (deliberately, see architecture.md section 11). Callers
identify themselves with headers:

| Who | Header |
|---|---|
| Elder (Fatima) | `X-Actor: elder` |
| Primary caregiver (Leila) | `X-Actor-Person-Id: 1` |
| Family (Karim) | `X-Actor-Person-Id: 2` |
| Worker | none -- only the token in the URL |

## API

Caregiver / family: `GET /persons`, `GET|POST /statements`, `PATCH /statements/{id}`,
`GET|POST /visits`, `GET /visits/{id}`, `GET /proposals`, `POST /proposals/{id}/decide`

Elder: `GET /me/statements`, `PATCH /me/statements/{id}/visibility`,
`GET /me/access-log`, `GET /me/proposals`, `POST /proposals/{id}/decide`

Worker (token-scoped): `GET /v/{token}`, `POST /v/{token}/checkout`

Meta: `GET /health`, `GET /observation-codes`, `POST /reset`

### Quick loop

```powershell
$h = @{"X-Actor-Person-Id"="1"}
$start = (Get-Date).AddMinutes(-5).ToString("s"); $end = (Get-Date).AddMinutes(55).ToString("s")
$v = Invoke-RestMethod -Method Post http://127.0.0.1:8000/visits -Headers $h -ContentType application/json `
  -Body (@{worker_name="Marie-Ève Tremblay";worker_role="personal_support_worker";task_type="bathing";scheduled_start=$start;scheduled_end=$end} | ConvertTo-Json)
Invoke-RestMethod "http://127.0.0.1:8000/v/$($v.token)"                       # the brief
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/v/$($v.token)/checkout" -ContentType application/json `
  -Body '{"completion":"partial","observation_codes":["refused_bath"]}'      # burns the token
Invoke-RestMethod http://127.0.0.1:8000/me/access-log -Headers @{"X-Actor"="elder"}
```

## Model provider

None is wired in yet. `brief_builder/select.py` defines the `ModelClient` seam;
until a provider is plugged into `get_default_client()`, every brief takes the
Stage 3 fallback (filtered statements rendered verbatim, safety first) and
`fallback_used` is `true`. `suggest_statement()` is rules-only: an observation
code repeated across check-outs becomes a proposal using the template in
`data/observation_codes.json`.
