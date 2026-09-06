# Implementation guide

Codebase structure, module split, and file-by-file instructions. No code — enough detail that three people can work in parallel without colliding.

**The problem this builds for:** care worker turnover. Families repeat the same history to every new worker, each worker interprets the situation differently and arrives at their own approach, and the same mistakes recur. Knowledge about an elderly person accumulates inside individual workers and leaves when they do.

**The product:** every visit gets a short brief before it and a short check-out after it. The brief carries forward what previous workers learned. The check-out captures what this worker learned before she disappears. A seventh worker should arrive knowing what the first six figured out.

---

## Stack decision

**Backend: Python — FastAPI + SQLite.** No ORM, no migrations. Raw `sqlite3` with a thin helper layer. Lists are stored as JSON text columns. Resetting the database is deleting a file.

**Frontend: Jinja2 templates served by the same FastAPI app, styled with Tailwind via CDN, with a few lines of vanilla JS.**

That choice needs one sentence of justification: a separate React app costs you CORS, a build step, an API client layer, state management, and a second dev server — roughly three hours of the fifteen — and buys nothing, because every screen here is a list, a form, or six lines of text. Server-rendered HTML forms post directly to the routes that already exist. There is no build step at all.

Use Alpine.js from a CDN only if you want the visibility toggles to feel instant. It's optional.

**No Docker.** Docker solves "my machine differs from production." There is no production, one process, and a database that is a single file.

---

## Codebase structure

```
carecircle/
├── app/
│   ├── main.py                 FastAPI app, mounts routers, static, templates
│   ├── config.py               Env vars, constants, closed lists
│   ├── db.py                   SQLite connection + query helpers
│   ├── schema.sql              Full DDL, run once at startup
│   ├── reset_db.py             Drop, recreate, reseed — one command
│   ├── seed.py                 Demo elder, workers, statements, visit history
│   ├── models.py               Dataclasses mirroring the tables
│   │
│   ├── repositories/           Every SQL statement in the project lives here
│   │   ├── people.py
│   │   ├── workers.py
│   │   ├── statements.py
│   │   ├── visits.py
│   │   ├── checkouts.py
│   │   ├── proposals.py
│   │   └── access_log.py
│   │
│   ├── services/               Business logic, no SQL, no HTTP
│   │   ├── visibility.py       THE RESOLVER — single read choke point
│   │   ├── tokens.py           Token generation, hashing, validation
│   │   ├── familiarity.py      How much this worker already knows
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
│       └── app.js              QR rendering, copy-to-clipboard
│
├── data/carecircle.db          Gitignored
├── .env.example
├── requirements.txt
└── README.md
```

### What each file does

| File | Responsibility |
|---|---|
| `main.py` | Creates the FastAPI app, calls `init_db()` and conditionally `seed()` on startup, mounts the four routers, configures Jinja and static files |
| `config.py` | Reads env vars. Holds the closed lists: `TASK_TYPES`, `CATEGORIES`, `OBSERVATION_CODES`, `MAX_BRIEF_LINES`, token window constants |
| `db.py` | Opens the SQLite connection returning dict rows; exposes `query`, `query_one`, `execute`, `init_db` |
| `schema.sql` | Every `CREATE TABLE`. Run with `executescript` |
| `reset_db.py` | Deletes the db file, re-runs schema and seed. The team's answer to schema drift |
| `seed.py` | Builds the demo history: one elder, four family members, six workers, ~30 statements, and past visits by *different* workers. This file is why the continuity claim is visible |
| `models.py` | Dataclasses. No behaviour, just typed shapes so functions have honest signatures |
| `repositories/*` | Every `SELECT`/`INSERT`/`UPDATE`. Nothing outside this folder writes SQL |
| `services/visibility.py` | The single function every read passes through |
| `services/familiarity.py` | Computes what a given worker has already been told |
| `services/brief.py` | Cache check → resolve → familiarity → AI → validate → persist |
| `services/foldback.py` | Turns handover notes, repeated observations, and caregiver corrections into pending proposals; promotes approved proposals into statements |
| `ai/*` | Everything that touches the model. Deletable — the app still works without it |
| `routes/*` | Parse request, call a service, render a template. No logic |

**The one rule that keeps this clean:** routes never call repositories directly for statement reads. They call `visibility.resolve()`. If you find yourself importing `repositories.statements` inside a route, stop.

---

# Module 1 — Frontend

## Interface design

Nine screens. Three visual languages, because three very different people use them.

### Design language

**Caregiver console** — dense, desktop-first, functional. Neutral grays, one accent colour. This person is busy and competent; don't decorate.

**Elder view** — large type (minimum 20px body), high contrast, generous spacing, few elements per screen, no icons without labels.

**Worker page** — mobile only. Assume a phone held one-handed in a hallway by someone who has never seen this before and may never see it again. Large text, big tap targets, no navigation chrome, one screen at a time. This is the screen judges will remember; give it the polish budget.

---

### Screen 0 — Demo role picker (`home.html`)

Not a product screen. Three large buttons: *Caregiver console*, *Elder view*, *Worker link*. Exists so you can switch roles on stage in one tap instead of editing URLs. Delete it in production.

---

### Screen 1 — Caregiver: the record (`caregiver/record.html`)

The main working screen. Two sections, and the split between them is the product's core idea made visible.

**Header** — elder's name, capacity mode as a small labelled pill (*"Amina decides"* / *"Amina decides, with confirmation"* / *"Represented"*). Beside it, a continuity line: *"31 notes · contributed by 6 workers and 2 family members."*

**Section A — Preferences.** What she wants. Written by the family. Grouped by category (Care, Communication, Routine, Observance, Safety).

Each row renders the sentence, then a row of small scope chips: the tasks it applies to, the time window if any, and a lock icon plus name if hidden from someone. Statements with no scope show a muted *"applies to all visits"* chip, so the absence of scope is visible rather than implied.

**Section B — Approaches.** What works. Mostly written by workers.

Same row shape, plus two extra affordances:
- A small attribution line: *"From Marie-Ève, 12 March"*
- A confirmation count when greater than zero: *"3 workers confirmed this"*

Rows sourced as corrections render with the accent border and a small **Correction** tag. These are the "don't do this again" entries and they must look different at a glance.

**Add statement form** — collapsed inside a `<details>`. Six inputs: statement text, kind (Preference / Approach), category, applies-to tasks (checkboxes, default all), optional time window, hidden-from (collapsed).

**Critical UI decision:** there is no religion field, no "cultural preferences" section, no Muslim-specific anything. Every statement is entered the same way. If a judge asks how you handle the *"Muslim-friendly is not one setting"* constraint, this screen is the answer — you point at it and say *there is nowhere to put it, by design.*

---

### Screen 2 — Caregiver: visits (`caregiver/visits.html`)

A create form above a history list.

**Form fields:** worker (a select over known workers, plus a *"someone new"* option that reveals name / role / language inputs), task type, date, start time, end time. Submit reads *"Create visit and generate link"*.

The "someone new" path is not an edge case — it is the problem. Make it a first-class option, not a fallback.

**Visit list below** — reverse chronological. Each row shows date and time, task, worker name, a small familiarity tag (*"1st visit"*, *"4th visit"*), and a state badge: `Scheduled` (gray) / `Briefed` (blue) / `Completed` (green) / `Expired` (amber).

Completed rows expand to show the check-out: completion status, observation chips, note, and — set apart with a left border — the **handover note**, labelled *"For the next person."*

Each expanded check-out carries one button: **"This shouldn't happen again."** It opens a single-line form and creates a correction.

The expired state matters. It shows the family *"no check-out"* rather than silence, which is itself information.

---

### Screen 3 — Caregiver: visit created (`caregiver/visit_created.html`)

Deliberately its own page, because this is a demo beat.

Centre of screen: the URL in a monospace box, a copy button, and a QR code rendered client-side. Below it, in smaller text: *"Sent by SMS in production. Valid from 9:30 to 13:00 today."*

Above the link, one line that frames what's about to happen: *"Marie-Ève has never visited Amina. Her brief carries 14 notes from 6 previous workers."*

A secondary button: *"Preview what the worker will see."*

---

### Screen 4 — Caregiver: proposals inbox (`caregiver/proposals.html`)

Pending record changes. Three sources feed this queue and each card states which:

- **From a handover note** — quotes the worker and the visit date
- **From a pattern** — *"Refused equipment noted on 3 of the last 5 visits"*
- **From a correction** — the caregiver's own words, usually auto-approved

Each card shows the suggested statement, its origin, a link to the source check-out, and two buttons: **Add to record** / **Dismiss**.

Empty state should be honest: *"Nothing pending. Proposals appear here when a worker leaves a note for the next person."*

---

### Screen 5 — Elder: my record (`elder/record.html`)

Same data as Screen 1, completely different presentation.

Large type, one statement per card, flat list, no category grouping — grouping is an organizational convenience for the caregiver, not for the person the statements are about. Approaches show their attribution in plain words: *"Marie-Ève suggested this."*

Each card has one control: **Who can see this.** Tapping it opens a list of names with toggles, default all on, worded plainly — *"Nadia can see this"* with a switch, not a permissions matrix.

A prominent link at the top: *"See who has looked at my information."*

---

### Screen 6 — Elder: access log (`elder/access_log.html`)

The most important screen in the product, and the simplest.

Reverse-chronological plain sentences, large type, one per line:

> Marie-Ève viewed your bathing preferences at 9:52 today
> Fatima viewed your record yesterday at 8:14 PM

No filters, no search, no pagination beyond a *show more* button. The value is that it's legible to an 82-year-old, not that it's queryable.

---

### Screen 7 — Elder: confirm changes (`elder/proposals.html`)

Same proposals as Screen 4, rendered large, one at a time, two big buttons: **Yes, add this** / **No**. Shown when `capacity_mode` is `self` or `assisted`.

---

### Screen 8 — Worker: the brief (`worker/brief.html`)

The screen that carries the pitch.

**Top line — the continuity counter.** This single line is the entire product argument rendered on a phone:

> **First visit · 14 notes from 6 previous workers**

For a returning worker it reads differently:

> **Your 5th visit · 2 things have changed**

**Context header** — *"Amina · Bathing · 10:00"*. First name only.

**The lines.** Up to six single sentences at ~18px with generous spacing. No bullets, no icons, no cards — this is read while walking to a door.

Three visual tiers:
- **Corrections** — accent left border, heavier weight, always first
- **Critical** — accent left border
- **Everything else** — plain

Approach lines carry a small trailing attribution when confirmed by more than one worker: *"— 3 workers"*. That tag is what makes the accumulated knowledge feel real rather than generated.

**A valid brief may be nearly empty.** For a returning worker with nothing changed, the correct render is the counter plus one line: *"Nothing has changed since your last visit."* Do not pad it. Showing this on stage is more convincing than showing six lines.

**Fixed bottom:** full-width button, *"Finished — 1 minute"*.

**Error state:** invalid or expired token renders one centred line — *"This link has expired."* — and nothing else. No login prompt, no navigation, no hint that anything else exists.

---

### Screen 9 — Worker: check-out (`worker/checkout.html`)

Four blocks, one screen.

**Block 1 — Did the task happen?** Three large segmented buttons: *Yes* / *Partly* / *No*.

**Block 2 — Anything you noticed?** A grid of chips from the seeded observation codes, two per row, large tap targets. Tapping toggles a filled state. Nothing is required.

Seed roughly: *didn't finish meal, ate well, seemed more tired, in good spirits, unsteady on feet, refused equipment, skin looks irritated, confused about the date, low on supplies, needed more time than usual, seemed in pain, family member present.*

**Block 3 — Anything the next person should know?** One textarea, four rows, placeholder *"Optional — a tip that made this easier."*

Beneath it, one line of guidance in small gray text: *"Practical tips only. Please don't record medical observations here."*

This block is the single highest-value field in the product. It is where a departing worker's knowledge stops leaving with her. Give it visual weight — a light background panel is enough — so it doesn't read as an afterthought.

**Block 4 — Did these tips work?** *(cut this first if you're behind schedule.)*

Lists the approach lines that appeared in this worker's brief, each with a single tap target: *worked* / *didn't*. Taps increment or flag the statement's confirmation count. Optional, skippable, no default selection.

Submit button: *"Send"*.

**Constraint to enforce in the UI:** observation chips are a fixed vocabulary. A worker cannot invent a code. That's what makes the visit log countable later, and what keeps a worker from typing something that reads like a clinical judgement.

---

### Screen 10 — Worker: done (`worker/done.html`)

One line of thanks. If a handover note was submitted, a second line: *"Your note will be passed to the next person."* Then: *"This link is now closed."* No further navigation. The token is dead.

That middle line matters more than it looks — it's the only feedback a worker gets that her contribution went somewhere, and it's why she'll write one again next time.

---

## Frontend task list

| # | Task |
|---|---|
| F1 | Base template, Tailwind CDN, three layout variants |
| F2 | Demo role picker |
| F3 | Caregiver record page — preferences and approaches sections |
| F4 | Caregiver record page — add statement form |
| F5 | Statement visibility editing UI |
| F6 | Create-visit form with known-worker / new-worker paths |
| F7 | Visit list with familiarity tags, states, expandable check-outs |
| F8 | Correction button and form |
| F9 | Visit-created page with link, QR, and continuity line |
| F10 | Caregiver proposals inbox with origin labelling |
| F11 | Elder record view |
| F12 | Elder access log |
| F13 | Elder proposals confirmation |
| F14 | Worker brief page with continuity counter and three visual tiers |
| F15 | Worker check-out — completion, chips, handover note |
| F16 | Worker check-out — tip confirmation block *(cut first)* |
| F17 | Worker done + expired states |
| F18 | `app.js` — QR, copy |

---

## Frontend implementation guidance

### F1 — Base template

**File:** `templates/base.html`

Define Jinja blocks `title`, `head`, `content`. Pull Tailwind from the CDN in `head`. Define a `layout` variable that extending templates set to `console`, `elder`, or `worker`, and switch `<body>` classes on it:

- `console` — `max-w-3xl mx-auto p-6 text-base`
- `elder` — `max-w-2xl mx-auto p-8 text-xl leading-relaxed`
- `worker` — `max-w-md mx-auto p-5 text-lg`, plus the mobile viewport meta tag

Do not build a shared navigation bar. The three surfaces must not link to each other; the worker surface especially needs no way to reach anything else.

### F2 — Role picker

**File:** `templates/home.html`

Three anchors styled as large blocks, linking to `/caregiver`, `/elder`, and the newest scheduled visit link. The route passes the latest token so the third button works without copy-paste on stage.

### F3 — Record sections

**File:** `templates/caregiver/record.html`

The route passes `preferences` (grouped by category) and `approaches` (flat, newest first). Loop categories in the fixed order from `config.CATEGORIES` so the page doesn't reshuffle between loads.

Write three Jinja macros:

- `scope_chips(statement)` — one chip per task in `applies_to_tasks`, or a single muted "all visits" chip if empty; a time chip if `time_start` is set; a lock chip per hidden name
- `attribution(statement)` — renders *"From {worker name}, {date}"* when `source == "worker"`, and the confirmation count when above zero
- `source_tag(statement)` — the **Correction** tag and accent border when `source == "correction"`

### F4 — Add statement form

**File:** `templates/caregiver/record.html`

A plain `<form method="post" action="/caregiver/statements">`. No JavaScript submission. Task checkboxes share `name="applies_to_tasks"` so FastAPI receives a list. Kind is two radio buttons, defaulting to Preference.

Keep the form collapsed inside `<details>`. That's a zero-JS disclosure widget and it's enough.

### F5 — Visibility editing

**Files:** `templates/caregiver/record.html`, `templates/elder/record.html`

Per statement, a small form posting to `/statements/{id}/visibility` with a checkbox per person, `name="visible_to"`. The route converts *visible* into *hidden* by set difference — store the negative, present the positive. Storing `hidden_from` is right for the resolver; showing "who can see this" is right for the human.

### F6, F7 — Visits

**File:** `templates/caregiver/visits.html`

The worker select lists known workers with their visit counts (*"Marie-Ève — 4 visits"*) plus a *"Someone new"* option. Choosing it reveals three inputs via a `<details>` block or three lines of JS — either is fine.

For the state badge and the familiarity tag, write macros `state_badge(state)` and `familiarity_tag(n)` mapping to fixed colour classes. `familiarity_tag(0)` should render *"1st visit"* with the accent colour — first visits are the interesting case and should stand out in the list.

Expandable check-outs use `<details>`. The handover note renders inside a bordered panel labelled *"For the next person"*, visually distinct from the observation chips.

Redirect after POST so refreshing doesn't create duplicate visits during the demo.

### F8 — Correction form

**File:** `templates/caregiver/visits.html`

Inside each expanded completed check-out, a `<details>` containing a one-line text input and a submit button posting to `/caregiver/corrections`, with the visit id in a hidden field. Label the input plainly: *"What should never happen again?"*

### F9 — Visit created

**File:** `templates/caregiver/visit_created.html`

The route passes `raw_token`, the visit, and a `continuity` dict with `note_count` and `contributor_count`. Render the framing line above the link. QR renders client-side from the full URL.

### F10, F13 — Proposals

**Files:** `templates/caregiver/proposals.html`, `templates/elder/proposals.html`

Same data, two renderings. Both are forms posting to `/proposals/{id}/decide` with a hidden `decision` field, one form per button. Origin is a small label above the suggested statement, driven by the proposal's `origin_kind` field. The elder version shows one card at a time — slice the list in the route and pass only the first pending proposal.

### F11, F12 — Elder views

**Files:** `templates/elder/record.html`, `templates/elder/access_log.html`

For the access log, the route passes pre-formatted sentences. Do not build the sentence in the template — build it in Python where you can test it. The template loops and prints.

### F14 — Worker brief

**File:** `templates/worker/brief.html`

The route passes `visit`, `lines` (each with `text`, `critical`, `is_correction`, `confirmations`), and a `continuity` dict with `is_first_visit`, `note_count`, `contributor_count`, `changed_count`.

Render the counter first, branching on `is_first_visit`. Then the context header. Then the lines, applying:

- `is_correction` → `border-l-4 border-red-500 pl-3 font-medium`
- `critical` → `border-l-4 border-amber-500 pl-3 font-medium`
- otherwise → `pl-4`

Append the *"— 3 workers"* tag when `confirmations >= 2`, in small gray text.

Handle the empty-lines case explicitly with the *"Nothing has changed since your last visit"* message. Do not let it fall through to a blank page.

Fixed bottom button — `fixed bottom-0 left-0 right-0 p-4`, with matching bottom padding on the content container so nothing hides behind it.

### F15 — Check-out

**File:** `templates/worker/checkout.html`

The chip grid is `<input type="checkbox">` elements with `<label>` styling via `peer-checked:` Tailwind classes. That gives toggle behaviour with zero JavaScript — worth the small CSS awkwardness because it cannot break on stage. Completion is three radio inputs styled the same way.

The handover textarea is `name="handover_note"`, four rows, inside a `bg-gray-50 rounded-lg p-4` panel with its own heading. Its visual weight should be second only to the submit button.

### F16 — Tip confirmation *(optional)*

**File:** `templates/worker/checkout.html`

The route passes `shown_approaches` — the approach statements that appeared in this worker's brief. For each, two radio inputs named `confirm_{id}` with values `worked` / `didnt`, both unselected by default. Skip the whole block when the list is empty.

Cut this first if you're behind. Nothing else depends on it.

### F17 — Terminal states

**Files:** `templates/worker/done.html`, plus an expired branch inside `brief.html`

Near-empty pages. Resist adding anything. The emptiness is the security property being demonstrated. `done.html` conditionally shows the handover acknowledgement line.

### F18 — `app.js`

Two functions, roughly ten lines each: `renderQR(elementId, text)` calling the CDN QR library, and `copyLink(elementId)` writing to the clipboard and swapping button text to "Copied" for two seconds. If you're writing a third function, ask whether HTML can do it.

---

# Module 2 — Backend

## Backend task list

| # | Task |
|---|---|
| B1 | `config.py` — env and closed lists |
| B2 | `schema.sql` — full DDL |
| B3 | `db.py` — connection and helpers |
| B4 | `reset_db.py` |
| B5 | `models.py` — dataclasses |
| B6 | `repositories/people.py` |
| B7 | `repositories/workers.py` |
| B8 | `repositories/statements.py` |
| B9 | `repositories/visits.py` |
| B10 | `repositories/checkouts.py` |
| B11 | `repositories/proposals.py` |
| B12 | `repositories/access_log.py` |
| B13 | `services/visibility.py` — the resolver |
| B14 | `services/tokens.py` |
| B15 | `services/familiarity.py` |
| B16 | `services/foldback.py` |
| B17 | `services/brief.py` — orchestration |
| B18 | `routes/caregiver.py` |
| B19 | `routes/elder.py` |
| B20 | `routes/worker.py` |
| B21 | `seed.py` |
| B22 | `main.py` wiring |

---

## Backend implementation guidance

### B1 — `config.py`

Module-level constants, no class:

```
TASK_TYPES: list[str]                       8 values, fixed
CATEGORIES: list[str]                       5 values, fixed
OBSERVATION_CODES: list[tuple[str, str]]    (code, label)
STATEMENT_KINDS = ("preference", "approach")
STATEMENT_SOURCES = ("family", "worker", "correction")
MAX_BRIEF_LINES: int = 6
PATTERN_THRESHOLD: int = 3
TOKEN_LEAD_MINUTES: int = 30
TOKEN_TRAIL_HOURS: int = 2
ANTHROPIC_API_KEY: str | None
DB_PATH: str
```

Load the key with `os.getenv`, defaulting to `None`. **Nothing may crash when it is `None`** — that's the fallback path, and you should be able to demo with the key removed.

### B2 — `schema.sql`

Ten `CREATE TABLE IF NOT EXISTS` statements.

```
elder(id, display_name, primary_language, capacity_mode)

person(id, elder_id, name, role)

worker(id, name, role, language, created_at)

preference_statement(
  id, elder_id, statement, kind, category, source,
  applies_to_tasks, excluded_tasks,          -- JSON text
  time_start, time_end,
  hidden_from,                               -- JSON text
  status, origin_visit_id, confirmations,
  source_checkout_id, created_at, updated_at)

visit(id, elder_id, worker_id, task_type,
      scheduled_start, scheduled_end,
      token_hash, token_expires_at, state)

brief(id, visit_id, selected_statement_ids, rendered_lines_json,
      model, generated_at, fallback_used)

checkout(id, visit_id, completion, observation_codes,
         note_text, handover_note, submitted_at)

observation_code(code, label_en, label_fr, category)

proposed_update(id, elder_id, source_checkout_id, origin_kind,
                suggested_kind, suggested_statement,
                status, decided_by, decided_at)

access_log(id, elder_id, actor_label, action, target_summary, at)
```

SQLite specifics:

- List columns are `TEXT NOT NULL DEFAULT '[]'` holding JSON.
- Timestamps are `TEXT` in ISO 8601. Don't fight SQLite on dates.
- `confirmations INTEGER NOT NULL DEFAULT 0`.
- `origin_kind` on proposals is one of `handover | pattern | correction`, and it drives the label on Screen 4.
- Index `visit(token_hash)`, `visit(elder_id, worker_id)`, and `preference_statement(elder_id, status)`. Those are the only queries that run often enough to matter.
- `updated_at` must actually be maintained on every statement update — the delta brief depends on it.

### B3 — `db.py`

```
get_conn() -> sqlite3.Connection
    Opens DB_PATH, row_factory = sqlite3.Row, check_same_thread=False.

query(sql: str, params: tuple = ()) -> list[dict]
query_one(sql: str, params: tuple = ()) -> dict | None
execute(sql: str, params: tuple = ()) -> int      # returns lastrowid
init_db() -> None                                 # executescript on schema.sql, idempotent
```

Add two private helpers every repository uses: `_load_json(row, *fields)` parsing JSON text columns in place, and `_dump(value)` serializing a list. No file outside `repositories/` should ever see a raw JSON string.

### B4 — `reset_db.py`

A `__main__` script: delete the db file if present, call `init_db()`, call `seed(force=True)`, print a one-line confirmation.

This is the team's answer to schema drift. Anyone who edits `schema.sql` or `seed.py` announces it in the group chat, and everyone runs `python -m app.reset_db`. There is no state worth preserving.

### B5 — `models.py`

Frozen dataclasses: `Elder`, `Person`, `Worker`, `Statement`, `Visit`, `Brief`, `Checkout`, `Proposal`, `AccessEntry`. Plus four that aren't tables:

```
@dataclass Actor:       kind: str, person_id: int | None, label: str
@dataclass Purpose:     task_type: str | None, window_start: str | None, window_end: str | None
@dataclass Familiarity: visit_count: int, last_visit_at: str | None, is_first_visit: bool
@dataclass BriefLine:   statement_id: int, text: str, critical: bool,
                        is_correction: bool, confirmations: int
@dataclass BriefResult: lines: list[BriefLine], fallback_used: bool,
                        note_count: int, contributor_count: int,
                        changed_count: int, is_first_visit: bool
```

`BriefResult` is a dataclass rather than a tuple because it now carries six things and the frontend reads five of them. Give each table-backed dataclass a `from_row(cls, row: dict)` classmethod so repositories stay short.

### B6–B12 — Repositories

Rules for all seven: functions take and return dataclasses or primitives, never `sqlite3.Row`. No function here contains an `if` expressing a policy — policy lives in services.

**`people.py`**
```
list_people(elder_id: int) -> list[Person]
get_person(person_id: int) -> Person | None
get_elder(elder_id: int) -> Elder | None
```

**`workers.py`**
```
create_worker(name: str, role: str, language: str) -> int
get_worker(worker_id: int) -> Worker | None
list_workers_for_elder(elder_id: int) -> list[tuple[Worker, int]]
    Each worker plus their visit count with this elder. Powers the
    select on Screen 2 and the contributor count.
count_contributing_workers(elder_id: int) -> int
    Distinct workers who authored at least one active statement,
    via origin_visit_id. This is the "6 previous workers" number.
```

**`statements.py`**
```
create_statement(elder_id, statement, kind, category, source,
                 applies_to_tasks, excluded_tasks,
                 time_start, time_end,
                 status="active", origin_visit_id=None,
                 source_checkout_id=None) -> int

get_statement(statement_id: int) -> Statement | None
list_statements(elder_id: int, status: str = "active",
                kind: str | None = None) -> list[Statement]
    Ordered by category then id, so pages are stable.

set_hidden_from(statement_id: int, person_ids: list[int]) -> None
set_status(statement_id: int, status: str) -> None
increment_confirmations(statement_id: int) -> None
count_active(elder_id: int) -> int
```

`count_active` and `count_contributing_workers` exist solely for the continuity counter. They earn their place — that counter is the pitch.

Every write path must set `updated_at`. The delta brief is only as good as this field.

**`visits.py`**
```
create_visit(elder_id, worker_id, task_type,
             scheduled_start, scheduled_end,
             token_hash, token_expires_at) -> int

get_visit(visit_id) -> Visit | None
get_visit_by_token_hash(token_hash) -> Visit | None
list_visits(elder_id) -> list[Visit]
set_state(visit_id, state) -> None
latest_scheduled(elder_id) -> Visit | None

count_visits_by_worker(elder_id: int, worker_id: int) -> int
last_completed_visit_at(elder_id: int, worker_id: int) -> str | None
    The two queries familiarity is built on.

save_brief(visit_id, statement_ids, lines, model, fallback_used) -> None
get_brief(visit_id) -> Brief | None
```

**`checkouts.py`**
```
create_checkout(visit_id, completion, observation_codes,
                note_text, handover_note) -> int
get_checkout(checkout_id) -> Checkout | None
get_checkout_for_visit(visit_id) -> Checkout | None
list_checkouts(elder_id, limit=20) -> list[Checkout]
    Joins visit to filter by elder. Newest first.
count_code_occurrences(elder_id, code, last_n=5) -> int
    Over the most recent last_n check-outs. Drives pattern detection.
```

**`proposals.py`**
```
create_proposal(elder_id, source_checkout_id, origin_kind,
                suggested_kind, suggested_statement) -> int
list_pending(elder_id) -> list[Proposal]
get_proposal(proposal_id) -> Proposal | None
decide(proposal_id, status, decided_by) -> None
exists_pending_like(elder_id, suggested_statement) -> bool
    Cheap duplicate guard — exact-match is sufficient.
```

**`access_log.py`**
```
log_access(elder_id, actor_label, action, target_summary) -> None
list_access(elder_id, limit=50) -> list[AccessEntry]
```

There is deliberately no delete function in `access_log.py` or `checkouts.py`. Append-only is enforced by absence.

### B13 — `services/visibility.py`

The most important file in the project. One public function.

```
resolve(elder_id: int, actor: Actor, purpose: Purpose) -> list[Statement]
```

Implement in this exact order:

1. Fetch all active statements for the elder via the repository.
2. **Identity filter.** If `actor.kind` is not `"elder"`, drop any statement where `actor.person_id` appears in `hidden_from`. The elder never has anything hidden from her.
3. **Purpose filter.** If `purpose.task_type` is set: drop statements whose `applies_to_tasks` is non-empty and doesn't contain it; drop statements whose `excluded_tasks` contains it.
4. **Time filter.** If `purpose.window_start` is set and the statement has a time window, drop it when the windows don't overlap. Compare `HH:MM` as strings — lexicographic comparison is correct for zero-padded times and saves a datetime dependency.
5. **Log.** Call `log_access` with `actor.label`, an action string, and a human-readable target summary such as `"bathing preferences"` derived from `purpose.task_type`.
6. Return the survivors.

Two things to hold firm on. **Logging is unconditional** — if the function ran, a row exists; there is no `if should_log` branch. And **there is no bypass parameter.** Nobody gets to pass `skip_filters=True`. If a caller needs unfiltered statements, that caller is wrong.

Note that corrections and approaches pass through this filter exactly like preferences. Worker-authored knowledge is subject to the elder's visibility control the same as anything else — there is no privileged class of statement.

Write a docstring at the top stating this is the only read path for statement data. It will be read by a judge.

### B14 — `services/tokens.py`

```
new_token() -> tuple[str, str]
    (raw, hash). raw = secrets.token_urlsafe(32); hash = sha256 hexdigest.

hash_token(raw: str) -> str

compute_window(scheduled_start: str, scheduled_end: str) -> tuple[str, str]
    Applies TOKEN_LEAD_MINUTES and TOKEN_TRAIL_HOURS.

validate(raw: str) -> Visit | None
    Hashes, looks up, returns None if not found, outside the window,
    or state is 'completed' or 'expired'.
```

Store only the hash. The raw token exists in exactly two places: the URL, and the caregiver's screen at creation time.

### B15 — `services/familiarity.py`

New service, small, and it's what makes the brief adaptive.

```
assess(elder_id: int, worker_id: int) -> Familiarity
    visit_count      = visits.count_visits_by_worker(...)
    last_visit_at    = visits.last_completed_visit_at(...)
    is_first_visit   = visit_count == 0

changed_since(statements: list[Statement], since: str | None) -> set[int]
    Ids of statements whose updated_at is later than `since`.
    Returns every id when `since` is None.
```

Keep both functions pure and free of SQL beyond the two repository calls. They're trivially unit-testable, which matters because the whole delta-brief behaviour rests on them.

### B16 — `services/foldback.py`

Three input paths, one output shape. Rule-based, no AI — **the model does not decide what enters the record.**

```
from_handover_note(checkout_id: int) -> int | None
    If handover_note is non-empty, create a proposal with
    origin_kind="handover" and suggested_kind="approach".
    The suggested statement is the note text, trimmed.
    Skip when exists_pending_like matches. Returns proposal id.

from_observation_patterns(checkout_id: int) -> list[int]
    For each observation code in the check-out, look up
    count_code_occurrences. When it reaches PATTERN_THRESHOLD, build a
    suggested statement from a static template map and create a
    proposal with origin_kind="pattern". Skip duplicates.

from_correction(elder_id: int, visit_id: int, text: str,
                decided_by: str) -> int
    Creates an active statement directly — source="correction",
    kind="preference", origin_visit_id=visit_id — bypassing the
    proposal queue. The caregiver already decided; a second
    approval step is friction with no purpose.

approve_proposal(proposal_id: int, decided_by: str) -> int
    Marks accepted, creates an active statement carrying source="worker",
    the proposal's suggested_kind, origin_visit_id from the source
    check-out's visit, and source_checkout_id. Returns statement id.

reject_proposal(proposal_id: int, decided_by: str) -> None
```

Keep the pattern template map as a module-level dict — three or four entries is enough; a code with no template produces no proposal.

Two product decisions embedded here, worth naming so nobody "fixes" them later. The threshold of three is what makes a proposal read as *"this is a pattern"* rather than *"this happened once."* And corrections skip the queue because the caregiver writing *"this must never happen again"* has already given approval.

### B17 — `services/brief.py`

Orchestration only. No SQL, no HTTP, no prompt text.

```
build_brief(visit_id: int, force: bool = False) -> BriefResult
```

Sequence:

1. Unless `force`, check `visits.get_brief`. If a brief exists, rehydrate and return it.
2. Load the visit and its worker. Build `Actor(kind="worker", person_id=None, label=worker.name)` and `Purpose(task_type=visit.task_type, window_start=..., window_end=...)`.
3. Call `visibility.resolve()`. These are the candidates.
4. Call `familiarity.assess()`, then `familiarity.changed_since(candidates, fam.last_visit_at)`.
5. **Split by familiarity.** First visit → all candidates go to the model. Returning worker → send corrections, plus statements in the changed set, plus any approach with `confirmations >= 2` created since her last visit. If that set is empty, return a `BriefResult` with no lines and `changed_count = 0` — this is a valid, correct brief and must not fall through to the full list.
6. If the resulting set is empty, skip the model entirely.
7. Call `ai.selector.select_lines(visit, candidates, familiarity)` inside a `try`. On any exception, set `fallback_used = True` and call `ai.validator.fallback_lines(candidates)`.
8. Pass whatever came back through `ai.validator.validate_lines(raw, candidate_ids, statements_by_id)`.
9. Compute `note_count` from `statements.count_active` and `contributor_count` from `workers.count_contributing_workers`.
10. Persist via `visits.save_brief`, transition the visit to `briefed`, return the `BriefResult`.

Note what step 3 guarantees: **the model is only ever handed statements that already passed the consent gate.** This ordering is the privacy argument. Add a comment saying so, because someone will be tempted to "optimize" by resolving after the call.

### B18 — `routes/caregiver.py`

Router prefixed `/caregiver`. Every handler under fifteen lines.

```
GET  /                            → redirect to /caregiver/record
GET  /record                      → resolve() as caregiver actor, split into
                                    preferences and approaches, render
POST /statements                  → create, redirect back
POST /statements/{id}/visibility  → visible_to → hidden_from by set
                                    difference, save, redirect
GET  /visits                      → visits + check-outs + familiarity tags
POST /visits                      → resolve or create worker, new_token,
                                    compute_window, create_visit, redirect
                                    to /visits/{id}/created
GET  /visits/{id}/created         → render link, QR, continuity line
POST /corrections                 → foldback.from_correction, redirect
GET  /proposals                   → list pending with origin labels
POST /proposals/{id}/decide       → foldback approve/reject, redirect
```

The `POST /visits` handler branches on whether `worker_id` or a new worker name arrived. Create the worker row first, then the visit.

For the created-visit page, include the raw token in the redirect query string — it never touches the database. Note in the README that production would use a flash message.

The caregiver's record view must call `resolve()`, not the repository. She can have things hidden from her too.

### B19 — `routes/elder.py`

```
GET  /elder                             → own record, resolve() with kind="elder"
POST /elder/statements/{id}/visibility
GET  /elder/access-log                  → list_access, format sentences here
GET  /elder/proposals                   → first pending proposal only
POST /elder/proposals/{id}/decide
```

Write a helper in this file:

```
format_access_sentence(entry: AccessEntry) -> str
    "Marie-Ève viewed your bathing preferences at 9:52 today"
```

Handle *today*, *yesterday*, and weekday names for anything older. Building this in Python rather than Jinja means you can eyeball it in a REPL at hour thirteen when it reads wrong.

### B20 — `routes/worker.py`

Two endpoints. The entire attack surface a stranger can reach, so keep it boring.

```
GET  /v/{token}
    validate() → if None, render the expired template with status 200
    (not 404 — don't leak whether the token ever existed)
    build_brief() → render brief.html with lines and continuity

POST /v/{token}/checkout
    validate() again — never trust that the GET happened
    Parse completion, observation_codes list, note_text, handover_note,
    and any confirm_{id} fields
    create_checkout
    increment_confirmations for each confirmed approach
    set_state(visit, "completed")          ← this burns the token
    foldback.from_handover_note
    foldback.from_observation_patterns
    render done.html, passing whether a handover note was left
```

Validate on the POST independently. A form left open past the window must not submit.

### B21 — `seed.py`

Do not undervalue this file. A believable history is worth more than any single feature, and for this problem the history *is* the demo.

```
seed(force: bool = False) -> None
```

Create one elder (`capacity_mode="assisted"`), four family members, and **six workers with distinct names**. Six matters — it's the number in the continuity counter, and a counter that says "6 previous workers" is only honest if six workers exist.

Then **~30 statements**, split roughly:

- ~18 preferences, `source="family"`, spread across all five categories, with genuinely varied scope — some all-tasks, some single-task, some with time windows, at least two hidden from a specific family member
- ~10 approaches, `source="worker"`, each with a real `origin_visit_id` pointing at a past visit by a different worker, and two or three carrying `confirmations = 2` or `3`
- 1–2 corrections, `source="correction"`

Write them the way a real daughter and real workers would. *"She agrees to everything to be polite — check twice before leaving"* lands. *"Patient is agreeable"* does not. For approaches: *"Sit down at the table with her — she won't eat if you stand over her."*

Then create **five or six past visits across at least four different workers**, all in `completed` state with check-outs attached. Two should carry `refused_equipment` so the third occurrence — live on stage — crosses `PATTERN_THRESHOLD` and fires a proposal. **Rehearse that specific number.** If the threshold is three and your seed already has three, the demo produces nothing.

Guard against double-seeding unless `force` is set.

### B22 — `main.py`

Create the app. On startup call `init_db()`, then `seed()` if the statement count is zero. Mount `/static`. Configure `Jinja2Templates`. Include the four routers. Add `GET /health` returning `{"ok": True}` so you can confirm the tunnel works from a phone before the demo.

Put this in the README: run with `--host 0.0.0.0` and open the phone on the same network, or deploy to Render with auto-deploy on push. Conference wifi often blocks client-to-client traffic, so **test the phone hitting the server by hour four**, not hour fourteen.

---

# Module 3 — AI

Four files, fully isolated. Delete this folder and the app still runs — that isn't an accident, it's the fallback guarantee.

The model's job has two axes now: which statements matter for *this task*, and which matter given *what this worker already knows*. The second axis is what makes the feature hard to fake with rules.

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
    Sends one message, returns the raw text of the first content block.
    Raises ModelUnavailable on: missing API key, HTTP error, timeout,
    or unexpected response shape.
```

The eight-second timeout is deliberate. A brief arriving in nine seconds is a failed demo; the fallback renders instantly. Prefer a slightly worse brief over a stalled screen.

This file must not know what a statement or a visit is. Two strings in, one string out.

### A2 — `ai/prompt.py`

```
SYSTEM_PROMPT: str        module constant

build_user_prompt(visit: Visit, worker: Worker,
                  candidates: list[Statement],
                  familiarity: Familiarity,
                  changed_ids: set[int]) -> str
```

The system prompt needs to state eight things:

1. The role: preparing a short briefing card for a care worker arriving at an elderly person's home, in a system where workers change often.
2. Select from the supplied notes only. Do not add information. Do not infer.
3. Every returned line must include the `statement_id` it came from.
4. Never give medical advice, never interpret symptoms, never suggest a diagnosis or a dose. Report what the notes say and nothing more.
5. Notes marked `correction` always appear first and always as critical.
6. For a first visit, prioritize what would cause distress or harm if got wrong, then the approaches most likely to make the visit go smoothly.
7. For a returning worker, include only what has changed. Returning zero lines is correct and expected when nothing has changed. Do not repeat what she was told last time.
8. At most six lines. Return only JSON in the given shape — no prose, no markdown fences.

Point four is not a formality. A model handed *"seemed more tired on three visits"* will otherwise volunteer a possible cause.

Point seven is the one to test hardest. Models are strongly biased toward producing output, and a correct empty response feels to them like failure. State it twice if you have to.

The user prompt renders the visit context (task, time, worker role, worker language), the familiarity line (*"This is Marie-Ève's 5th visit. Last visit: 12 March."*), and then the candidates as a numbered list of `id: statement`, each tagged with its kind, its source, whether it changed since her last visit, and its confirmation count when above one. Plain text — no JSON input. Models handle a labelled list well and it's far easier to eyeball when debugging.

### A3 — `ai/selector.py`

```
select_lines(visit: Visit, candidates: list[Statement],
             familiarity: Familiarity,
             changed_ids: set[int]) -> list[dict]
    Builds prompts, calls the client, strips any markdown fences,
    json.loads, returns the raw "lines" array unvalidated.
    Raises ModelUnavailable or ValueError on failure.
```

This function does **not** validate. Separating "get a response" from "decide whether to trust it" means the enforcement logic is testable without a network call. Keep it that way. Strip fences defensively even though the prompt forbids them.

### A4 — `ai/validator.py`

The enforcement point for the whole no-hallucination guarantee.

```
validate_lines(raw_lines: list[dict],
               candidate_ids: set[int],
               statements_by_id: dict[int, Statement]) -> list[BriefLine]
    For each entry:
      - drop unless statement_id is present, is an int, and is in candidate_ids
      - drop unless text is a non-empty string under ~120 chars
      - coerce critical to bool, defaulting False
      - force critical=True and is_correction=True when the source
        statement has source == "correction"
      - carry confirmations across from the source statement
    Stable-sort: corrections first, then criticals, preserving model
    order within groups. Hard-slice to MAX_BRIEF_LINES.
    Never raises — always returns a list, possibly empty.

fallback_lines(candidates: list[Statement]) -> list[BriefLine]
    Renders candidates verbatim: corrections first, then by
    config.CATEGORIES order, sliced to MAX_BRIEF_LINES.
    critical=True only for corrections.
```

Note that the correction and confirmation flags are set **here, from the database record**, not taken from the model's response. The model may suggest that something is critical; it cannot demote a correction. Deriving these from the source statement rather than trusting the response is what keeps the "don't do this again" guarantee independent of model behaviour.

Three properties to hold: this file never raises, so a bad response degrades rather than crashes; it never repairs a malformed line, it drops it, because repairing means inventing; and the id membership check is the single line that makes *"the model cannot invent facts"* a true statement about the system rather than a claim about the prompt.

### A5 — Test harness

**File:** `ai/_manual_test.py` (not imported by the app)

A `__main__` script that seeds a fake visit and a dozen fake statements, runs the pipeline, and prints the lines with their source ids. It should let you flip six scenarios from the command line:

1. First visit, normal operation → full orientation brief
2. Returning worker with two changed statements → two-line delta brief
3. Returning worker with nothing changed → **zero lines**
4. `ANTHROPIC_API_KEY` unset → fallback path
5. A stubbed malformed response → validator drops everything, fallback fires
6. A stubbed response containing an id not in the candidate set → that line is dropped, the rest render

Scenarios three and six are the ones to demo if a judge probes. Three proves the delta logic is real rather than cosmetic; six proves the hallucination guard is structural. Being able to show them working is worth more than describing them.

---

## Parallelization and integration points

The three modules meet in exactly four places. Agree on these in hour one and the parallel work won't collide.

**`models.py`** — all three modules import it. Write it first, together, before anyone else starts.

**`build_brief()` returns a `BriefResult`** — frontend needs only that dataclass to build the brief template against a stub.

**Form field names** — the check-out posts `completion`, `observation_codes` (repeated), `note_text`, `handover_note`, and `confirm_{id}`. Write these into the README before either side implements them.

**File ownership is disjoint.** Backend owns everything in `app/` except `templates/`, `static/`, and `ai/`. Frontend owns `templates/` and `static/`. AI owns `ai/`. Nobody edits another person's directory; if backend needs a new template variable, they ask rather than edit.

Work on `main` directly, commit small, `git pull --rebase && git push` every twenty minutes. Branches and PRs cost more than they save at this scale.

Whoever takes the frontend should stub `build_brief` to return a hardcoded `BriefResult` — build one first-visit variant and one empty-delta variant — and build all nine screens against it. Whoever takes the AI module should work entirely through `_manual_test.py` and never open a browser until integration.
