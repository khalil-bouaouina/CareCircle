# Codebase structure and task split

Python everywhere except the frontend. Three people, fifteen hours.

---

# Part 1 — Repository structure

One repo, three top-level folders. The folder boundaries match the person boundaries, so merge conflicts are rare by construction.

```
eldercare/
│
├── backend/                      # Person A — FastAPI
│   ├── app/
│   │   ├── main.py               # app, CORS, router mounting
│   │   ├── config.py             # env vars
│   │   ├── db.py                 # engine, session, init
│   │   ├── models.py             # SQLAlchemy tables
│   │   ├── schemas.py            # Pydantic request/response
│   │   ├── seed.py               # loads seed_data.json
│   │   │
│   │   ├── security/
│   │   │   ├── tokens.py         # generate, hash, validate visit tokens
│   │   │   └── resolver.py       # THE visibility resolver
│   │   │
│   │   ├── services/
│   │   │   ├── statements.py
│   │   │   ├── visits.py         # state machine
│   │   │   ├── checkouts.py
│   │   │   ├── proposals.py
│   │   │   └── access_log.py
│   │   │
│   │   └── routers/
│   │       ├── caregiver.py
│   │       ├── elder.py
│   │       └── worker.py         # the only token-scoped router
│   │
│   ├── eldercare.db              # SQLite, gitignored
│   └── requirements.txt
│
├── brief_builder/                # Person C — pure Python package
│   ├── __init__.py               # exposes build_brief()
│   ├── contract.py               # the dataclasses A and C both import
│   ├── scope.py                  # stage 1: task + time filtering
│   ├── prompts.py
│   ├── select.py                 # stage 2: model call
│   ├── validate.py               # stage 3: id check, slice, cache-ready
│   ├── fallback.py               # deterministic render when the model fails
│   ├── proposals.py              # check-out → suggested statement
│   ├── fixtures/
│   │   └── cases.json            # test visits + expected behaviour
│   └── tests/
│       ├── test_scope.py
│       ├── test_validate.py
│       └── test_build_brief.py
│
├── data/
│   ├── seed_data.json            # Person C authors, Person A loads
│   └── observation_codes.json
│
├── frontend/                     # Person B — Vite + React + Tailwind
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx               # routes
│   │   ├── api.js                # all fetch calls live here
│   │   ├── mocks.js              # used until the backend lands
│   │   └── pages/
│   │       ├── Landing.jsx       # demo role switcher
│   │       ├── CaregiverConsole.jsx
│   │       ├── CreateVisit.jsx
│   │       ├── ElderView.jsx
│   │       ├── WorkerBrief.jsx
│   │       └── WorkerCheckout.jsx
│   └── package.json
│
└── README.md                     # how to run both halves
```

**Why `brief_builder` sits outside `backend/`.** It's a pure package with no database, no HTTP, and no FastAPI import. Person C can build and test it entirely from fixtures without ever running the backend, and Person A can call it with a one-line import. This is the single most important structural decision for parallel work.

**SQLite, not Postgres.** A file. No container, no connection string, no one blocked on someone else's database being up. Nothing in the schema needs Postgres.

---

# Part 2 — The contract

Written in hour one, by all three people together, in `brief_builder/contract.py`. Nobody starts coding until this file exists and is committed.

```python
from dataclasses import dataclass

@dataclass
class Statement:
    id: int
    statement: str
    category: str              # care|communication|routine|observance|safety
    applies_to_tasks: list[str]   # empty = all tasks
    excluded_tasks: list[str]
    time_start: str | None        # "13:00"
    time_end: str | None

@dataclass
class VisitContext:
    task_type: str
    scheduled_start: str          # "10:00"
    scheduled_end: str
    worker_role: str
    worker_language: str

@dataclass
class BriefLine:
    statement_id: int
    text: str
    critical: bool

@dataclass
class BriefResult:
    lines: list[BriefLine]
    fallback_used: bool
    model: str | None


def build_brief(
    statements: list[Statement],
    visit: VisitContext,
) -> BriefResult:
    ...
```

Person A guarantees: the statements passed in are **already consent-filtered** — hidden rows never reach this function. Person C guarantees: every returned `statement_id` appears in the input list.

Second contract, same file:

```python
def suggest_statement(
    observation_codes: list[str],
    note_text: str | None,
    recent_checkouts: list[dict],
) -> str | None:
    """Returns a suggested statement, or None if nothing durable."""
```

---

# Part 3 — Task list

## Person A — Backend

| # | Task | Est |
|---|---|---|
| A1 | Repo, FastAPI skeleton, CORS, `uvicorn` run script | 0.5h |
| A2 | SQLAlchemy models for all nine tables + SQLite init | 1.5h |
| A3 | Seed loader reading `data/seed_data.json` + a `/reset` endpoint for demo runs | 0.5h |
| A4 | **Visibility resolver** — `resolve(elder_id, actor, purpose)`, plus the access-log write on every call | 1.5h |
| A5 | Token module — generate, hash, validate; visit state machine (`scheduled → briefed → completed → expired`) | 1h |
| A6 | Caregiver router — statements CRUD, create visit returning the link, list visits | 1.5h |
| A7 | Elder router — own statements, per-item visibility toggle, access log, proposal decisions | 1h |
| A8 | Worker router — `GET /v/{token}` (resolve → `build_brief` → cache to `brief` table) and `POST /v/{token}/checkout` (append, burn token, call `suggest_statement`, create proposal) | 2h |
| A9 | Integration with frontend, bug fixing | 2h |

**A4 and A8 are the two that matter.** A4 is the privacy story the judges will ask about. A8 is where the whole loop closes. Everything else is plumbing.

**Warning on A8:** the resolver must run before `build_brief`, never after. If that ordering flips, hidden statements reach the model and the privacy argument is gone.

## Person B — Frontend

Mobile-first for the worker pages, desktop for the rest. No component library, no design system, no state management library. `useState` and `fetch`.

| # | Task | Est |
|---|---|---|
| B1 | Vite + React + Tailwind + router, `api.js`, `mocks.js` with hardcoded responses | 1h |
| B2 | Landing page — three buttons to enter as caregiver, elder, or worker (demo only) | 0.5h |
| B3 | Caregiver console — statement list grouped by category, add-statement form with the five scope fields | 2h |
| B4 | Create-visit form + result screen showing the link and a QR code | 1h |
| B5 | **Worker brief page** — six lines, mobile, criticals visually distinct, "Done" button at the bottom | 1.5h |
| B6 | Worker check-out — completion selector, observation chip grid, optional note, submit | 1.5h |
| B7 | Elder view — large type, statement list with per-person hide toggles, access log as plain sentences | 1.5h |
| B8 | Proposal inbox — approve/reject, shown in both caregiver and elder views | 1h |
| B9 | Polish pass, focused on B5 and B6 | 1.5h |

**Build against `mocks.js` from hour one.** Do not wait for the backend. Swap the import in `api.js` when A's endpoints land.

**B5 is the screen the judges will remember.** It gets the polish budget. Everything else can look plain.

## Person C — AI engineer

| # | Task | Est |
|---|---|---|
| C1 | `contract.py` + `fixtures/cases.json` — at minimum the 10am bathing case and the 4pm nursing case | 1h |
| C2 | `scope.py` — deterministic task and time filtering, with unit tests | 1h |
| C3 | `prompts.py` + `select.py` — model call returning strict JSON with statement ids | 2h |
| C4 | `validate.py` — drop unknown ids, hard-slice to six, criticals first; `fallback.py` — deterministic render by category | 1.5h |
| C5 | **`data/seed_data.json`** — one elder, ~30 realistic scoped statements, 20 observation codes, 3 past visits with check-outs already recorded | 2h |
| C6 | `proposals.py` — `suggest_statement()`, mostly rules over repeated observation codes with the model only for phrasing | 1.5h |
| C7 | **Tuning pass** — run both fixture cases until the task-flip is crisp and the six lines read well | 2h |
| C8 | Demo script + pitch slides | 1.5h |

**C5 is not busywork.** Thirty statements that sound like a real person are what make the demo land; thirty lorem-ipsum rows make it look like a school project. Write them as if a real daughter typed them. Mix categories — some observance, some safety, some pure routine, and several that have nothing to do with religion at all. That mix is itself the proof that we didn't build a "Muslim mode."

**C7 is the demo's centre of gravity.** The moment where the same elder, same record, different visit produces a visibly different brief — the female-worker line disappearing for a nursing visit, the prayer line jumping to the top at 4pm — is the thing that proves the thesis. Budget real time to make it crisp.

**Test the fallback path deliberately.** Unset the API key and confirm the brief still renders. Do this at hour six, not hour fourteen.

---

# Part 4 — Hour-by-hour

**H0–1 — everyone together.** Write `contract.py`. Agree the nine tables field by field. Create the repo, get both halves running locally for all three people. Nobody codes alone before this is done.

**H1–5 — parallel, no dependencies.**
A: A1, A2, A3, start A4 · B: B1, B2, B3 (on mocks) · C: C1, C2, start C3

**H5–9 — parallel, still no dependencies.**
A: finish A4, A5, A6 · B: B4, B5, B6 · C: finish C3, C4, C5

First integration checkpoint at **H9**: A and C connect `build_brief` to the worker router. This is the first real dependency in the project and it should take twenty minutes if the contract held.

**H9–12 — integration.**
A: A7, A8 · B: B7, B8, then switch `api.js` off mocks · C: C6, start C7

**H12 — feature freeze.** No new features. No exceptions. Anything unfinished gets cut, not rushed.

**H12–14.** A: A9 bug fixing · B: B9 polish · C: C7 tuning, then C8

**H14–15.** Load the demo dataset, rehearse end to end twice, buffer.

---

# Part 5 — Risks

**The contract drifts.** If A and C edit `contract.py` independently, the H9 integration turns into an hour of debugging. Rule: changes to that file get announced out loud.

**B waits for the backend.** The mocks file exists specifically to prevent this. If B is ever blocked on A, something has gone wrong with the plan.

**Scope creep at hour ten.** Someone will notice the emergency summary is easy and want to add it. Don't. A complete loop beats two half-features, and the loop is the entire pitch.

**The demo depends on a live API call.** Brief results are cached in the `brief` table by A8. Generate the demo briefs before presenting, so the presentation reads from cache and survives bad conference wifi.
