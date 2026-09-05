# Eldercare

Consent-gated care briefs for elderly people receiving in-home care. See
[architecture.md](architecture.md) for the design and
[new-architecture-implementation-guide.md](new-architecture-implementation-guide.md)
for the module split this code follows.

## Layout

```
app/                FastAPI + raw sqlite3 (guide Module 2)
  schema.sql        the nine tables
  repositories/     every SQL statement in the project
  services/         visibility (THE resolver), tokens, brief, foldback
  routes/           caregiver, elder, worker -- thin
brief_builder/      the AI module (guide Module 3), pure Python, deletable
data/               seed_data.json, observation_codes.json, eldercare.db (gitignored)
```

Templates (guide Module 1) are not built yet. Routes already use the guide's
paths and form field names and return JSON, so the Jinja layer can be added
without changing the backend.

## Setup (Windows, PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
uvicorn app.main:app --reload          # from the repo root
```

API at `http://127.0.0.1:8000`, interactive docs at `/docs`. On first start
`data/eldercare.db` is created and seeded. `POST /reset` deletes and reseeds it.
Settings are env vars, see `.env.example`. Nothing crashes when
`ANTHROPIC_API_KEY` is unset -- every brief takes the deterministic fallback.

For a phone on the same wifi run with `--host 0.0.0.0`; test that early.

## Demo identity

No real auth (architecture.md section 11). Caregiver routes act as the primary
caregiver (Leila) by default; add `X-Actor-Person-Id: 2` to browse as the
family member (Karim) and see `hidden_from` at work. Elder routes are always the
elder. Workers send nothing -- only the token in the URL.

## API

POST bodies are `application/x-www-form-urlencoded` (list fields repeat the key).

**Caregiver** (`/caregiver`)
```
GET  /caregiver/record                       statements grouped by category (via resolve)
GET  /caregiver/people
POST /caregiver/statements                   statement, category, applies_to_tasks*, excluded_tasks*,
                                             time_start, time_end, hidden_from*
POST /caregiver/statements/{id}/visibility   visible_to*  -> hidden_from by set difference
GET  /caregiver/visits                       with check-outs; sweeps expired
POST /caregiver/visits                       worker_name, worker_role, worker_language, task_type,
                                             scheduled_start, scheduled_end  -> token + link (shown once)
GET  /caregiver/visits/{id}
GET  /caregiver/proposals?status=pending
POST /caregiver/proposals/{id}/decide        decision=approve|reject [, category]
```

**Elder** (`/elder`)
```
GET  /elder                                  own record (via resolve)
POST /elder/statements/{id}/visibility       visible_to*
GET  /elder/access-log                       plain sentences, newest first
GET  /elder/proposals                        first pending + the rest
POST /elder/proposals/{id}/decide            decision=approve|reject
```

**Worker** (`/v`, token-scoped -- the whole surface a stranger can reach)
```
GET  /v/{token}                              the brief; invalid/expired/burned -> 200 {"expired": true}
POST /v/{token}/checkout                     completion=yes|partial|no, observation_codes*, note_text
                                             -> completes the visit, burns the token, may create proposals
```

**Meta**: `GET /health`, `POST /reset`

## Quick loop

```powershell
$b = "http://127.0.0.1:8000"
$start = (Get-Date).AddMinutes(-5).ToString("yyyy-MM-ddTHH:mm:ss"); $end = (Get-Date).AddMinutes(55).ToString("yyyy-MM-ddTHH:mm:ss")
$v = Invoke-RestMethod -Method Post "$b/caregiver/visits" -Body @{worker_name="Marie-Ève Tremblay";worker_role="personal_support_worker";task_type="bathing";scheduled_start=$start;scheduled_end=$end}
Invoke-RestMethod "$b/v/$($v.token)"                                                          # the brief
Invoke-RestMethod -Method Post "$b/v/$($v.token)/checkout" -Body @{completion="partial";observation_codes="refused_bath"}
Invoke-RestMethod "$b/v/$($v.token)"                                                          # -> expired
Invoke-RestMethod "$b/elder/access-log" | Select-Object -First 3 -ExpandProperty sentence
```

The seeded visits already carry `refused_bath` twice; the check-out above is the
third occurrence and creates a pending proposal (`PROPOSAL_THRESHOLD = 3`).

## Fold-back and the model

`services/foldback.py` is rules-only: an observation code seen 3 times in the
last 5 check-outs becomes a pending proposal using the template on the
observation code. A human approves it into the record; nothing writes a
statement autonomously.

`brief_builder/select.py` holds the `ModelClient` seam. Until a provider is
plugged into `get_default_client()`, every brief takes the Stage 3 fallback
(filtered statements verbatim, safety first) and `fallback_used` is `true`.
