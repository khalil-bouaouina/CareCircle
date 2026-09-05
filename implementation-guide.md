# Implementation guide

Codebase structure, module split, and file-by-file instructions. No code — enough detail that three people can work in parallel without colliding.

---

## Stack decision

**Backend: Python — FastAPI + SQLite.** No ORM, no migrations. Raw `sqlite3` with a thin helper layer. Lists (`applies_to_tasks`, `hidden_from`) are stored as JSON text columns. Resetting the database is deleting a file.

**Frontend: Jinja2 templates served by the same FastAPI app, styled with Tailwind via CDN, with a few lines of vanilla JS.**

That choice needs one sentence of justification: a separate React app costs you CORS, a build step, an API client layer, state management, and a second dev server — roughly three hours of the fifteen — and buys nothing, because every screen here is a list, a form, or six lines of text. Server-rendered HTML forms post directly to the routes that already exist. There is no build step at all.

Use Alpine.js from a CDN only if you want the visibility toggles to feel instant. It's optional.

---

## Codebase structure

```
carecircle/
├── app/
│   ├── main.py                 FastAPI app, mounts routers, static, templates
│   ├── config.py               Env vars, constants, closed lists
│   ├── db.py                   SQLite connection + query helpers
│   ├── schema.sql              Full DDL, run once at startup
│   ├── seed.py                 Loads the demo elder, people, statements, past visits
│   ├── models.py               Dataclasses mirroring the tables
│   │
│   ├── repositories/           Every SQL statement in the project lives here
│   │   ├── people.py
│   │   ├── statements.py
│   │   ├── visits.py
│   │   ├── checkouts.py
│   │   ├── proposals.py
│   │   └── access_log.py
│   │
│   ├── services/               Business logic, no SQL, no HTTP
│   │   ├── visibility.py       THE RESOLVER — single read choke point
│   │   ├── tokens.py           Token generation, hashing, validation
│   │   ├── brief.py            Brief pipeline orchestration
│   │   └── foldback.py         Check-out → proposal → statement
│   │
│   ├── ai/                     The AI module, fully isolated
│   │   ├── client.py           HTTP call to the model provider
│   │   ├── prompt.py           Prompt construction
│   │   ├── selector.py         Call + JSON parse
│   │   └── validator.py        Enforcement + fallback rendering
│   │
│   ├── routes/                 HTTP layer, thin
│   │   ├── home.py             Demo role picker
│   │   ├── caregiver.py
│   │   ├── elder.py
│   │   └── worker.py
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── caregiver/
│   │   │   ├── record.html
│   │   │   ├── visits.html
│   │   │   ├── visit_created.html
│   │   │   └── proposals.html
│   │   ├── elder/
│   │   │   ├── record.html
│   │   │   ├── access_log.html
│   │   │   └── proposals.html
│   │   └── worker/
│   │       ├── brief.html
│   │       ├── checkout.html
│   │       └── done.html
│   │
│   └── static/
│       └── app.js              QR rendering, copy-to-clipboard, chip toggles
│
├── data/carecircle.db          Gitignored
├── .env.example
├── requirements.txt
└── README.md
```

### What each file does

| File | Responsibility |
|---|---|
| `main.py` | Creates the FastAPI app, calls `init_db()` and optionally `seed()` on startup, mounts the four routers, configures Jinja and static files |
| `config.py` | Reads env vars. Holds the closed lists: `TASK_TYPES`, `CATEGORIES`, `OBSERVATION_CODES`, `MAX_BRIEF_LINES = 6`, token window constants |
| `db.py` | Opens the SQLite connection with `row_factory` set to return dicts; exposes `query`, `execute`, `init_db` |
| `schema.sql` | Every `CREATE TABLE`. Run with `executescript` |
| `seed.py` | Inserts one elder, four people, ~30 statements, three completed past visits with check-outs. This file is why the demo looks lived-in |
| `models.py` | Dataclasses. No behaviour, just typed shapes so functions have honest signatures |
| `repositories/*` | Every `SELECT`/`INSERT`/`UPDATE`. Nothing outside this folder writes SQL |
| `services/visibility.py` | The single function every read passes through |
| `services/tokens.py` | Random token, SHA-256 hash, window validation |
| `services/brief.py` | Cache check → resolve → AI → validate → persist |
| `services/foldback.py` | Turns check-out observations into pending proposals; promotes approved proposals into statements |
| `ai/*` | Everything that touches the model. Deletable — the app still works without it |
| `routes/*` | Parse request, call a service, render a template. No logic |
| `templates/*` | Server-rendered HTML |

**The one rule that keeps this clean:** routes never call repositories directly for statement reads. They call `visibility.resolve()`. If you find yourself importing `repositories.statements` inside a route, stop.

---

# Module 1 — Frontend

## Interface design

Nine screens. Three visual languages, because three very different people use them.

### Design language

**Caregiver console** — dense, desktop-first, functional. Neutral grays, one accent colour. This person is busy and competent; don't decorate.

**Elder view** — large type (minimum 20px body), high contrast, generous spacing, few elements per screen, no icons without labels. Every action has a confirmation step.

**Worker page** — mobile only. Assume a phone held one-handed in a hallway. Large text, big tap targets, no navigation chrome, one screen at a time. This is the screen judges will remember; give it the polish budget.

---

### Screen 0 — Demo role picker (`home.html`)

Not a product screen. Three large buttons: *Caregiver console*, *Elder view*, *Worker link*. Exists so you can switch roles on stage in one tap instead of editing URLs. Delete it in production.

---

### Screen 1 — Caregiver: the record (`caregiver/record.html`)

The main working screen.

**Layout:** single column, max width ~800px.

**Header** — elder's name, capacity mode shown as a small labelled pill (*"Amina decides"* / *"Amina decides, with confirmation"* / *"Represented"*). Not a dropdown; it's a state, not a setting you flip casually.

**Statement list** — grouped by category (Care, Communication, Routine, Observance, Safety) with the category as a subheading. Each statement renders as a row:

- The sentence, in normal weight, full width
- Below it, a line of small scope chips: the tasks it applies to, the time window if any, and a lock icon plus name if it's hidden from someone
- On the right, an edit affordance

Statements with no scope show a muted *"applies to all visits"* chip so the absence of scope is visible rather than implied.

**Add statement form** — collapsed behind a button, expands inline. Five inputs:

1. Statement — a single-line text input, with placeholder showing the expected register: *"Female worker required for bathing"*
2. Category — select, from the closed list
3. Applies to — multi-select checkboxes of task types, with an "all tasks" default
4. Time window — two optional time inputs, labelled *"only relevant between"*
5. Hidden from — checkbox list of family members, collapsed by default

**Critical UI decision:** there is no religion field, no "cultural preferences" section, and no Muslim-specific anything on this form. Every statement is entered the same way. If a judge asks how you handle the "Muslim-friendly is not one setting" constraint, this screen is the answer — you point at it and say *there's nowhere to put it, by design.*

---

### Screen 2 — Caregiver: create a visit (`caregiver/visits.html`)

A form above the visit list.

**Form fields:** worker name, worker role (select), worker language (select), task type (select from closed list), date, start time, end time. Submit button reads *"Create visit and generate link"*.

**Visit list below** — reverse chronological. Each row: date and time, task, worker name, and a state badge — `Scheduled` (gray) / `Briefed` (blue) / `Completed` (green) / `Expired` (amber). Completed rows expand to show the check-out: completion status, the observation chips that were tapped, and the note.

The expired state matters. It shows the family *"no check-out"* rather than silence, which is itself information.

---

### Screen 3 — Caregiver: visit created (`caregiver/visit_created.html`)

Deliberately its own page, because this is a demo beat.

Centre of the screen: the URL in a monospace box, a copy button, and a QR code beneath it rendered client-side. Below, in smaller text: *"Sent by SMS in production. Valid from 9:30 to 13:00 today."*

A secondary button: *"Preview what the worker will see"* — opens the brief in a new tab. Useful for you during development and reassuring for the caregiver.

---

### Screen 4 — Caregiver: proposals inbox (`caregiver/proposals.html`)

A list of pending proposals. Each card shows:

- The suggested statement, in quotes
- Why it was proposed: *"Refused equipment noted on 3 of the last 5 visits"*
- A link to the source check-out
- Two buttons: **Add to record** / **Dismiss**

Empty state matters here and it should say something honest: *"Nothing pending. Proposals appear here when workers report something that looks durable."*

---

### Screen 5 — Elder: my record (`elder/record.html`)

Same data as Screen 1, completely different presentation.

Large type, one statement per card, no category grouping — just a flat list, because grouping is an organizational convenience for the caregiver, not for the person the statements are about.

Each card has one control: **Who can see this.** Tapping it opens a list of names with toggles. Default all on. The wording is plain: *"Nadia can see this"* with a switch, not a permissions matrix.

A prominent link at the top: *"See who has looked at my information"*.

---

### Screen 6 — Elder: access log (`elder/access_log.html`)

The most important screen in the product, and the simplest.

A reverse-chronological list of plain sentences, large type, one per line:

> Marie-Ève viewed your bathing preferences at 9:52 today
> Fatima viewed your record yesterday at 8:14 PM
> Marie-Ève viewed your bathing preferences on Tuesday at 10:03

No filters, no search, no pagination beyond a "show more" button. The value is that it's legible to an 82-year-old, not that it's queryable.

---

### Screen 7 — Elder: confirm changes (`elder/proposals.html`)

Same proposals as Screen 4, rendered large, one at a time, with two big buttons: **Yes, add this** / **No**. Shown only when `capacity_mode` is `self` or `assisted`.

---

### Screen 8 — Worker: the brief (`worker/brief.html`)

The screen that carries the pitch.

**Above the fold, in order:**

- A one-line context header: *"Amina · Bathing · 10:00"*. First name only.
- Six lines. Each is a single sentence, ~18px, with generous line spacing. Lines flagged `critical` render with a left border in the accent colour and slightly heavier weight. No bullets, no icons, no cards — just readable lines, because this is read while walking to a door.
- A footer line, small and gray: *"6 of 31 notes, chosen for this visit."* This is the sentence that explains the entire product to anyone who glances at the phone.

**At the bottom, fixed:** a full-width button, *"Finished — 1 minute"*.

**Error state:** if the token is invalid or expired, a single centred line — *"This link has expired."* — and nothing else. No login prompt, no navigation, no hint that anything else exists.

---

### Screen 9 — Worker: check-out (`worker/checkout.html`)

Three blocks, one screen, no scrolling on a normal phone if you're disciplined.

**Block 1 — Did the task happen?** Three large segmented buttons: *Yes* / *Partly* / *No*.

**Block 2 — Anything you noticed?** A grid of chips from the seeded observation codes, two per row, large tap targets. Tapping toggles a filled state. Nothing is required.

Seed roughly: *didn't finish meal, ate well, seemed more tired, in good spirits, unsteady on feet, refused equipment, skin looks irritated, confused about the date, low on supplies, family member present, needed more time than usual, seemed in pain.*

**Block 3 — Anything else?** One textarea, three rows, placeholder *"Optional"*.

Submit button: *"Send"*.

**Constraint to enforce in the UI:** the observation chips are a fixed vocabulary. A worker cannot invent a code. This is what makes the visit log countable later, and it's also what keeps a care worker from typing something that reads like a clinical judgement.

---

### Screen 10 — Worker: done (`worker/done.html`)

One line of thanks, and the statement *"This link is now closed."* No further navigation. The token is dead.

---

## Frontend task list

| # | Task |
|---|---|
| F1 | Base template, Tailwind CDN, three layout variants |
| F2 | Demo role picker |
| F3 | Caregiver record page — list rendering |
| F4 | Caregiver record page — add statement form |
| F5 | Statement visibility editing UI |
| F6 | Create-visit form |
| F7 | Visit list with states and expandable check-outs |
| F8 | Visit-created page with link and QR |
| F9 | Caregiver proposals inbox |
| F10 | Elder record view |
| F11 | Elder access log |
| F12 | Elder proposals confirmation |
| F13 | Worker brief page |
| F14 | Worker check-out page with chip grid |
| F15 | Worker done + expired states |
| F16 | `app.js` — QR, copy, chip toggles |

---

## Frontend implementation guidance

### F1 — Base template

**File:** `templates/base.html`

Define three Jinja blocks: `title`, `head`, `content`. Pull Tailwind from the CDN in `head`. Define a `layout` variable that the extending template sets to `console`, `elder`, or `worker`, and switch the `<body>` classes on it:

- `console` — `max-w-3xl mx-auto p-6 text-base`
- `elder` — `max-w-2xl mx-auto p-8 text-xl leading-relaxed`
- `worker` — `max-w-md mx-auto p-5 text-lg`, plus `<meta name="viewport" content="width=device-width, initial-scale=1">`

Do not build a shared navigation bar. The three surfaces should not link to each other; the worker surface especially must have no way to reach anything else.

### F2 — Role picker

**File:** `templates/home.html`

Three anchor tags styled as large blocks, linking to `/caregiver`, `/elder`, and the most recent visit link. For the third, have the route pass in the latest scheduled visit's token so the button works without copy-paste on stage.

### F3 — Record list rendering

**File:** `templates/caregiver/record.html`

The route passes `statements` grouped into a dict keyed by category. Loop categories in a fixed order from `config.CATEGORIES` so the page doesn't reshuffle between loads.

For each statement, render the sentence, then a chip row. Write a Jinja macro `scope_chips(statement)` that emits: one chip per task in `applies_to_tasks`, or a single muted "all visits" chip if empty; a time chip if `time_start` is set; a lock chip per name in `hidden_from`.

### F4 — Add statement form

**File:** `templates/caregiver/record.html`

A plain `<form method="post" action="/caregiver/statements">`. No JavaScript submission. Task checkboxes all share `name="applies_to_tasks"` so FastAPI receives a list.

Keep the form collapsed inside a `<details>` element. That is a zero-JS disclosure widget and it's enough.

### F5 — Visibility editing

**File:** `templates/caregiver/record.html`, `templates/elder/record.html`

Per statement, a small form posting to `/statements/{id}/visibility` with a checkbox per person, `name="visible_to"`. The route converts *visible* into *hidden* by set difference — store the negative, present the positive. Storing `hidden_from` is correct for the resolver; showing "who can see this" is correct for the human.

### F6, F7, F8 — Visits

**Files:** `templates/caregiver/visits.html`, `visit_created.html`

The create form is a plain POST. On success the route redirects to `/caregiver/visits/{id}/created` — redirect after POST, so refreshing doesn't create duplicate visits during the demo.

For the state badge, write a Jinja macro `state_badge(state)` mapping the four states to fixed colour classes.

For expandable check-outs, use `<details>` again. No JS.

QR: use a small CDN library that renders into a div from a string. One line in `app.js`.

### F9, F12 — Proposals

**Files:** `templates/caregiver/proposals.html`, `templates/elder/proposals.html`

Same data, two renderings. Both are forms posting to `/proposals/{id}/decide` with a hidden `decision` field, one form per button. The elder version shows one card at a time — slice the list in the route and pass only the first pending proposal.

### F10, F11 — Elder views

**Files:** `templates/elder/record.html`, `templates/elder/access_log.html`

For the access log, the route passes pre-formatted sentences. Do not build the sentence in the template — build it in Python where you can test it. Template just loops and prints.

### F13 — Worker brief

**File:** `templates/worker/brief.html`

Route passes `visit`, `lines` (each with `text` and `critical`), and `total_statements`. Loop the lines; apply `border-l-4 border-amber-500 pl-3 font-medium` when `critical` is true.

The footer sentence is built in Python: `f"{len(lines)} of {total_statements} notes, chosen for this visit."`

Fixed bottom button — `fixed bottom-0 left-0 right-0 p-4` with a matching bottom padding on the content container so nothing hides behind it.

### F14 — Check-out

**File:** `templates/worker/checkout.html`

The chip grid is `<input type="checkbox">` elements with hidden inputs and `<label>` styling via `peer-checked:` Tailwind classes. That gives you toggle behaviour with zero JavaScript — worth the small CSS awkwardness because it can't break on stage.

Completion is three radio inputs styled the same way.

### F15 — Terminal states

**Files:** `templates/worker/done.html`, plus an expired branch inside `brief.html`

Both are near-empty pages. Resist adding anything. The emptiness is the security property being demonstrated.

### F16 — `app.js`

Three functions, roughly ten lines each:

- `renderQR(elementId, text)` — call the CDN QR library
- `copyLink(elementId)` — clipboard write, swap button text to "Copied" for two seconds
- Nothing else. If you're writing a fourth function, ask whether HTML can do it.

---

# Module 2 — Backend

## Backend task list

| # | Task |
|---|---|
| B1 | `config.py` — env and closed lists |
| B2 | `schema.sql` — full DDL |
| B3 | `db.py` — connection and helpers |
| B4 | `models.py` — dataclasses |
| B5 | `repositories/people.py` |
| B6 | `repositories/statements.py` |
| B7 | `repositories/visits.py` |
| B8 | `repositories/checkouts.py` |
| B9 | `repositories/proposals.py` |
| B10 | `repositories/access_log.py` |
| B11 | `services/visibility.py` — the resolver |
| B12 | `services/tokens.py` |
| B13 | `services/foldback.py` |
| B14 | `services/brief.py` — orchestration |
| B15 | `routes/caregiver.py` |
| B16 | `routes/elder.py` |
| B17 | `routes/worker.py` |
| B18 | `seed.py` |
| B19 | `main.py` wiring |

---

## Backend implementation guidance

### B1 — `config.py`

Module-level constants, no class:

```
TASK_TYPES: list[str]        8 values, fixed
CATEGORIES: list[str]        5 values, fixed
OBSERVATION_CODES: list[tuple[str, str]]   (code, label)
MAX_BRIEF_LINES: int = 6
TOKEN_LEAD_MINUTES: int = 30
TOKEN_TRAIL_HOURS: int = 2
ANTHROPIC_API_KEY: str | None
DB_PATH: str
```

Load the key with `os.getenv`, defaulting to `None`. **Nothing in the app may crash when it is `None`** — that's the fallback path and you should be able to demo with the key removed.

### B2 — `schema.sql`

Nine `CREATE TABLE IF NOT EXISTS` statements matching the architecture doc. Notes specific to SQLite:

- List columns (`applies_to_tasks`, `excluded_tasks`, `hidden_from`, `selected_statement_ids`, `observation_codes`) are `TEXT NOT NULL DEFAULT '[]'`, holding JSON.
- Timestamps are `TEXT` in ISO 8601. Don't fight SQLite on dates.
- Index `visit(token_hash)` and `preference_statement(elder_id, status)`. Those are the only two queries that run often enough to matter.
- Foreign keys are worth declaring for documentation value even though you won't enable enforcement.

### B3 — `db.py`

```
get_conn() -> sqlite3.Connection
    Opens DB_PATH, sets row_factory to sqlite3.Row, returns it.
    check_same_thread=False since FastAPI may use a threadpool.

query(sql: str, params: tuple = ()) -> list[dict]
    Executes, fetches all, converts each Row to a plain dict.

query_one(sql: str, params: tuple = ()) -> dict | None

execute(sql: str, params: tuple = ()) -> int
    Executes, commits, returns cursor.lastrowid.

init_db() -> None
    Reads schema.sql and runs executescript. Idempotent.
```

Add two private helpers used by every repository: `_load_json(row, *fields)` which parses the JSON text columns in place, and `_dump(value)` which serializes a list for storage. Every repository calls these so no other file ever sees raw JSON strings.

### B4 — `models.py`

Frozen dataclasses: `Elder`, `Person`, `Statement`, `Visit`, `Brief`, `Checkout`, `Proposal`, `AccessEntry`, and two that aren't tables:

```
@dataclass Actor:      kind: str, person_id: int | None, label: str
@dataclass Purpose:    task_type: str | None, window_start: str | None, window_end: str | None
@dataclass BriefLine:  statement_id: int, text: str, critical: bool
```

`Actor` and `Purpose` exist so `resolve()` has a signature you can read. Give each dataclass a `from_row(cls, row: dict)` classmethod so repositories stay short.

### B5–B10 — Repositories

Rules that apply to all six: every function takes and returns dataclasses or primitives, never `sqlite3.Row`. No function in these files contains an `if` that expresses a policy — policy lives in services.

**`people.py`**
```
list_people(elder_id: int) -> list[Person]
get_person(person_id: int) -> Person | None
get_elder(elder_id: int) -> Elder | None
```

**`statements.py`**
```
create_statement(elder_id: int, statement: str, category: str,
                 applies_to_tasks: list[str], excluded_tasks: list[str],
                 time_start: str | None, time_end: str | None,
                 status: str = "active",
                 source_checkout_id: int | None = None) -> int

get_statement(statement_id: int) -> Statement | None

list_statements(elder_id: int, status: str = "active") -> list[Statement]
    Ordered by category, then id, so pages are stable.

set_hidden_from(statement_id: int, person_ids: list[int]) -> None
set_status(statement_id: int, status: str) -> None
count_active(elder_id: int) -> int
```

`count_active` exists solely for the *"6 of 31 notes"* footer. It earns its place.

**`visits.py`**
```
create_visit(elder_id, worker_name, worker_role, worker_language,
             task_type, scheduled_start, scheduled_end,
             token_hash, token_expires_at) -> int

get_visit(visit_id: int) -> Visit | None
get_visit_by_token_hash(token_hash: str) -> Visit | None
list_visits(elder_id: int) -> list[Visit]
set_state(visit_id: int, state: str) -> None
latest_scheduled(elder_id: int) -> Visit | None      # for the demo role picker

save_brief(visit_id: int, statement_ids: list[int],
           lines: list[BriefLine], model: str | None,
           fallback_used: bool) -> None
get_brief(visit_id: int) -> Brief | None
```

**`checkouts.py`**
```
create_checkout(visit_id: int, completion: str,
                observation_codes: list[str], note_text: str) -> int
get_checkout(checkout_id: int) -> Checkout | None
get_checkout_for_visit(visit_id: int) -> Checkout | None
list_checkouts(elder_id: int, limit: int = 20) -> list[Checkout]
    Joins visit to filter by elder. Newest first.
count_code_occurrences(elder_id: int, code: str, last_n: int = 5) -> int
    Over the most recent `last_n` check-outs. Drives repeat detection.
```

**`proposals.py`**
```
create_proposal(elder_id: int, source_checkout_id: int,
                suggested_statement: str) -> int
list_pending(elder_id: int) -> list[Proposal]
get_proposal(proposal_id: int) -> Proposal | None
decide(proposal_id: int, status: str, decided_by: str) -> None
```

**`access_log.py`**
```
log_access(elder_id: int, actor_label: str,
           action: str, target_summary: str) -> None
list_access(elder_id: int, limit: int = 50) -> list[AccessEntry]
```

There is deliberately no delete function anywhere in `access_log.py` or `checkouts.py`. Append-only is enforced by absence.

### B11 — `services/visibility.py`

The most important file in the project. One public function.

```
resolve(elder_id: int, actor: Actor, purpose: Purpose) -> list[Statement]
```

Implement in this exact order:

1. Fetch all active statements for the elder via the repository.
2. **Identity filter.** If `actor.kind` is not `"elder"`, drop any statement where `actor.person_id` appears in `hidden_from`. The elder never has anything hidden from her.
3. **Purpose filter.** If `purpose.task_type` is set: drop statements whose `applies_to_tasks` is non-empty and doesn't contain it; drop statements whose `excluded_tasks` contains it.
4. **Time filter.** If `purpose.window_start` is set and the statement has a time window, drop it when the windows don't overlap. Compare as `HH:MM` strings — lexicographic comparison is correct for zero-padded times and saves you a datetime dependency.
5. **Log.** Call `log_access` with `actor.label`, an action string, and a human-readable target summary such as `"bathing preferences"` derived from `purpose.task_type`.
6. Return the survivors.

Two things to hold firm on. **Logging is unconditional** — if the function ran, a row exists; there is no `if should_log` branch. And **there is no bypass parameter**. Nobody gets to pass `skip_filters=True` for a special case. If a caller needs unfiltered statements, that caller is wrong.

Write a docstring at the top stating that this is the only read path for statement data. It will be read by a judge.

### B12 — `services/tokens.py`

```
new_token() -> tuple[str, str]
    Returns (raw, hash). raw = secrets.token_urlsafe(32).
    hash = sha256 hexdigest of raw.

hash_token(raw: str) -> str

compute_window(scheduled_start: str, scheduled_end: str) -> tuple[str, str]
    Returns (valid_from, valid_until) applying TOKEN_LEAD_MINUTES
    and TOKEN_TRAIL_HOURS.

validate(raw: str) -> Visit | None
    Hashes, looks up the visit, returns None if not found,
    if now is outside the window, or if state is 'completed' or 'expired'.
```

Store only the hash. The raw token exists in exactly two places: the URL, and the caregiver's screen at creation time.

### B13 — `services/foldback.py`

Rule-based, no AI. This is important — the AI does not decide what enters the record.

```
proposals_from_checkout(checkout_id: int) -> list[int]
    For each observation code in the check-out:
      - look up count_code_occurrences for that code
      - if the count reaches 3, build a suggested statement from a
        static template map, e.g. "refused_equipment" ->
        "Has been refusing the shower chair — offer, don't insist"
      - skip if an identical pending proposal already exists
    Returns the ids of created proposals.

approve_proposal(proposal_id: int, decided_by: str) -> int
    Marks the proposal accepted, creates an active statement carrying
    source_checkout_id, returns the new statement id.

reject_proposal(proposal_id: int, decided_by: str) -> None
```

Keep the template map in this file as a module-level dict. Three or four entries is enough for the demo; a code with no template simply produces no proposal.

The threshold of three is a product decision, not a technical one — it's what makes the proposal read as *"this is a pattern"* rather than *"this happened once."*

### B14 — `services/brief.py`

Orchestration only. No SQL, no HTTP, no prompt text.

```
build_brief(visit_id: int, force: bool = False) -> tuple[list[BriefLine], bool, int]
    Returns (lines, fallback_used, total_active_statements).
```

Sequence:

1. Unless `force`, check `visits.get_brief`. If a brief exists, return it from cache.
2. Load the visit. Build an `Actor(kind="worker", person_id=None, label=visit.worker_name)` and a `Purpose(task_type=visit.task_type, window_start=..., window_end=...)`.
3. Call `visibility.resolve()`. These are the candidates.
4. If the candidate list is empty, return an empty line list and skip the model entirely.
5. Call `ai.selector.select_lines(visit, candidates)` inside a `try`. On any exception, set `fallback_used = True` and call `ai.validator.fallback_lines(candidates)`.
6. Pass whatever came back through `ai.validator.validate_lines(raw, candidate_ids)`.
7. Persist via `visits.save_brief`, transition the visit state to `briefed`, and return.

Note what step 3 guarantees: **the model is only ever handed statements that already passed the consent gate.** This ordering is the privacy argument. Add a comment saying so, because someone will be tempted to "optimize" by resolving after the call.

### B15 — `routes/caregiver.py`

Router prefixed `/caregiver`. Every handler is under fifteen lines.

```
GET  /                          → redirect to /caregiver/record
GET  /record                    → resolve() as the caregiver actor, group by
                                  category, render
POST /statements                → create, redirect back
POST /statements/{id}/visibility → convert visible_to into hidden_from
                                  by set difference, save, redirect
GET  /visits                    → list visits + attached check-outs
POST /visits                    → new_token, compute_window, create_visit,
                                  redirect to /visits/{id}/created
GET  /visits/{id}/created       → render link; raw token passed through the
                                  redirect via a short-lived query param
GET  /proposals                 → list pending
POST /proposals/{id}/decide     → call foldback, redirect
```

For the created-visit page, the simplest honest approach is to include the raw token in the redirect query string. It never touches the database. Note in the README that production would use a flash message instead.

The caregiver's record view must call `resolve()`, not the repository — she can have things hidden from her too.

### B16 — `routes/elder.py`

```
GET  /elder                          → own record, resolve() with kind="elder"
POST /elder/statements/{id}/visibility
GET  /elder/access-log               → list_access, format sentences here
GET  /elder/proposals                → first pending proposal only
POST /elder/proposals/{id}/decide
```

Write a helper in this file:

```
format_access_sentence(entry: AccessEntry) -> str
    "Marie-Ève viewed your bathing preferences at 9:52 today"
```

Handle *today*, *yesterday*, and weekday names for anything older. Building this in Python rather than Jinja means you can eyeball it in a REPL when it reads wrong at hour thirteen.

### B17 — `routes/worker.py`

Two endpoints. This is the entire attack surface a stranger can reach, so keep it boring.

```
GET  /v/{token}
    validate() → if None, render the expired template with status 200
    (not 404 — don't leak whether the token ever existed)
    build_brief() → render brief.html

POST /v/{token}/checkout
    validate() again — never trust that the GET happened
    Parse completion, observation_codes list, note_text
    create_checkout
    set_state(visit, "completed")     ← this burns the token
    proposals_from_checkout
    render done.html
```

Validate on the POST independently. A form left open past the window must not submit.

### B18 — `seed.py`

Do not undervalue this file. A believable demo dataset is worth more than any single feature.

```
seed(reset: bool = False) -> None
```

Create: one elder (`capacity_mode="assisted"`), four people (primary caregiver, two siblings, one worker record), and **around thirty statements** spread across all five categories with genuinely varied scope — some all-tasks, some single-task, some with time windows, at least two hidden from a specific sibling.

Write the statements as if a real daughter wrote them. *"She agrees to everything to be polite — check twice before leaving"* lands; *"Patient is agreeable"* does not.

Then create three past visits in `completed` state with check-outs attached, including `refused_equipment` on two of them — so that the third one, live on stage, crosses the threshold and fires a proposal. **Rehearse that specific number.** If your threshold is three and your seed has three, the demo produces nothing.

Guard the whole thing so it doesn't double-seed on reload.

### B19 — `main.py`

Create the app. On startup call `init_db()`, then `seed()` if the statement count is zero. Mount `/static`. Configure `Jinja2Templates`. Include the four routers. Add a `GET /health` returning `{"ok": True}` so you can confirm the tunnel works from the phone before the demo.

One development note worth putting in the README: run with `--host 0.0.0.0` and open the phone on the same wifi, or use a tunnel. Conference wifi often blocks client-to-client traffic, so **test the phone hitting the laptop early**, not at hour fourteen.

---

# Module 3 — AI

Four files, fully isolated. Delete this folder and the app still runs — that isn't an accident, it's the fallback guarantee.

## AI task list

| # | Task |
|---|---|
| A1 | `client.py` — provider call with timeout |
| A2 | `prompt.py` — system and user prompt construction |
| A3 | `selector.py` — call and JSON parse |
| A4 | `validator.py` — enforcement and fallback |
| A5 | Manual test harness |

---

## AI implementation guidance

### A1 — `ai/client.py`

```
class ModelUnavailable(Exception): ...

call_model(system: str, user: str, timeout: float = 8.0) -> str
    Sends one message to the provider, returns the raw text of the
    first content block.
    Raises ModelUnavailable on: missing API key, HTTP error,
    timeout, or unexpected response shape.
```

The eight-second timeout is deliberate. A brief that arrives in nine seconds is a failed demo; the fallback path renders instantly. Prefer a slightly worse brief over a stalled screen.

This file must not know what a statement or a visit is. It takes two strings and returns one.

### A2 — `ai/prompt.py`

```
SYSTEM_PROMPT: str        module constant

build_user_prompt(visit: Visit, candidates: list[Statement]) -> str
```

The system prompt needs to state six things:

1. The role: preparing a short briefing card for a care worker arriving at an elderly person's home.
2. Select from the supplied notes only. Do not add information. Do not infer.
3. Every returned line must include the `statement_id` it came from.
4. Never give medical advice, never interpret symptoms, never suggest a diagnosis or a dose. Report what the notes say and nothing more.
5. At most six lines. Mark a line `critical` when getting it wrong would cause distress or harm.
6. Return only JSON in the given shape, with no prose and no markdown fences.

The user prompt renders the visit context (task, time, worker role, worker language) and then the candidates as a numbered list of `id: statement`. Keep it plain text — no JSON input. Models handle a labelled list well and it's far easier to eyeball when debugging.

Point four is not a formality. Say it explicitly, because a model handed *"seemed more tired on three visits"* will otherwise volunteer a possible cause.

### A3 — `ai/selector.py`

```
select_lines(visit: Visit, candidates: list[Statement]) -> list[dict]
    Builds prompts, calls the client, strips any markdown fences,
    json.loads, returns the raw "lines" array unvalidated.
    Raises ModelUnavailable or ValueError on failure.
```

This function does **not** validate. Separating "get a response" from "decide whether to trust it" means the enforcement logic is testable without a network call. Keep it that way.

Strip fences defensively even though the prompt forbids them.

### A4 — `ai/validator.py`

The enforcement point for the whole no-hallucination guarantee.

```
validate_lines(raw_lines: list[dict],
               candidate_ids: set[int]) -> list[BriefLine]
    For each entry:
      - drop it unless statement_id is present, is an int,
        and is in candidate_ids
      - drop it unless text is a non-empty string under ~120 chars
      - coerce critical to bool, defaulting False
    Stable-sort criticals first, preserving model order within groups.
    Hard-slice to MAX_BRIEF_LINES.
    Never raises — always returns a list, possibly empty.

fallback_lines(candidates: list[Statement]) -> list[BriefLine]
    Renders candidates verbatim, ordered by config.CATEGORIES,
    sliced to MAX_BRIEF_LINES, all critical=False.
```

Three properties to hold: this file never raises, so a bad response degrades rather than crashes; it never repairs a malformed line, it drops it, because repairing means inventing; and the id membership check is the single line that makes "the model cannot invent facts" a true statement about the system rather than a claim about the prompt.

### A5 — Test harness

**File:** `ai/_manual_test.py` (not imported by the app)

A `__main__` script that seeds a fake visit and a dozen fake statements, runs the pipeline, and prints the lines with their source ids. It should let you flip four scenarios from the command line:

1. Normal operation
2. `ANTHROPIC_API_KEY` unset → fallback path
3. A stubbed malformed response → validator drops everything, fallback fires
4. A stubbed response containing an id that isn't in the candidate set → that line is dropped, the rest render

Scenario four is the one to demo if a judge asks how you prevent hallucination. Being able to show it working is worth more than describing it.

---

## Parallelization and integration points

The three modules meet in exactly three places. Agree on these in hour one and the parallel work won't collide:

**`models.py`** — all three modules import it. Write it first, together, before anyone else starts.

**`build_brief()` returns `(lines, fallback_used, total)`** — frontend needs only this signature to build the brief template against a stub.

**Form field names** — the check-out posts `completion`, `observation_codes` (repeated), and `note_text`. Write these into the README before either side implements them.

Whoever takes the frontend should stub `build_brief` to return three hardcoded `BriefLine` objects and build all nine screens against it. Whoever takes the AI module should work entirely through `_manual_test.py` and never open a browser until integration.
