# CareCircle

**A seventh care worker should arrive knowing what the first six figured out.**

Every visit gets a short brief before it and a short check-out after it. The brief
carries forward what previous workers learned. The check-out captures what this
worker learned, before she disappears.

Built for MuslimHacks. FastAPI + SQLite + server-rendered HTML, no build step,
runs offline with no API key.

---

## 1. The problem

Home care runs on people who leave. Agencies rotate staff, contracts end, workers
change employer — and an elderly person meets a stranger, again.

Everything that stranger needs to know is held in three places, none of which
survive the handover:

| Where the knowledge lives | What happens to it |
|---|---|
| In the family's memory | The daughter re-explains the same fifteen things to every new worker, on the phone, at the door, while she is at work |
| In the previous worker's head | She learned it over eleven visits. She leaves. It goes with her |
| In an agency care plan | Written once at intake, task-shaped ("assist with bathing"), never updated by the people who actually visit |

So the same mistakes recur. The second worker offers the shower chair the way
the first one did, and gets refused the same way. Nobody is at fault: the
knowledge was never written anywhere a stranger could read it in ninety seconds
on a phone in a hallway.

**Three things make this specifically hard, and they are why an off-the-shelf
notes app does not solve it:**

1. **The knowledge is not neutral.** "She will agree to anything to be polite,
   so check twice before you leave" is intimate. Writing it down means it can be
   read by the wrong person. Any system that fixes continuity by making
   everything visible has traded one harm for another.
2. **Relevance is task-shaped and time-shaped.** A worker doing a 20-minute meal
   visit does not need the thirty-item record. She needs the four lines that
   apply to *meals*, *this morning*, *her role*. A wall of text is read by nobody.
3. **Practice knowledge and preference are different things.** "Female worker for
   bathing" is the elder's decision. "Lay the clothes out in the order she puts
   them on, then she dresses herself" is a worker's discovery. Both need to
   survive turnover; only the first one is anybody's to declare.

> **Evidence to cite in the pitch.** The mechanism above is the argument. Add the
> team's sources here before submission — home-care turnover rate, the local
> agency numbers, and any interview notes from the research phase. Do not present
> unsourced figures; the mechanism stands without them.

### Why "Muslim-friendly" is not a feature in this repo

There is no religion field, no "cultural preferences" section, and no
Muslim-specific branch anywhere in the schema. Prayer times, gendered care
preferences, Ramadan meal shifts and halal requirements are all entered as
ordinary scoped statements — the same table, the same visibility control, the
same time windows as "she takes her coffee at 7."

That is the design position: a Muslim elder is not a configuration flag. The
things her family needs the system to carry are *scoped preferences with a time
window and an audience*, which is exactly what every other elder needs too. A
non-Muslim elder uses the identical structure. **If a judge asks where the
Muslim-specific handling is, the caregiver record screen is the answer: there is
nowhere to put it, by design.**

---

## 2. The solution

Two screens on a phone, wrapped around one visit.

```
   BEFORE THE VISIT                 AFTER THE VISIT
   ────────────────                 ───────────────
   The brief                        The check-out
   ≤ 6 lines                        Closed-vocabulary observations
   corrections first                + one handover note
   scoped to this task,                      │
   this time window,                         │  repeated 3× → a pattern
   this worker                               ▼
        ▲                            A proposal, waiting
        │                                    │
        └──── a human approved it ───────────┘
```

**The brief** is at most six lines. It is not the record; it is the part of the
record that applies to *this* task in *this* time window for *this* worker. A
returning worker gets a delta — what changed since her last visit — not the same
six lines again. If nothing changed, she gets zero lines, and that is the correct
answer.

**The check-out** takes 20 seconds: completion, a few taps from a closed list of
12 observation codes, and optionally a note to the next worker. Free text is
never turned into a clinical assessment; the closed vocabulary is what makes the
visit history countable later.

**The fold-back** is the part that compounds. A handover note becomes a pending
proposal. Three occurrences of the same observation code become a pending
proposal ("she has refused the equipment several times — offer it once, then let
it go"). A *human* — the caregiver, or the elder herself — accepts or rejects it
before it becomes part of the permanent record. **The model never writes.**

### The three properties worth demonstrating

**One read path.** [`services/visibility.py`](app/services/visibility.py) is the
only function in the codebase that returns statement data. Identity filter, then
purpose filter, then time filter, then an access-log row — unconditionally, with
no `if should_log` and no `skip_filters` bypass. There is exactly one function to
audit, which is what makes the privacy claim demonstrable rather than aspirational.

**The model cannot invent facts.** [`ai/validator.py`](app/ai/validator.py) drops
any line whose `statement_id` is not in the candidate set a human wrote. It never
repairs a malformed line, because repairing means inventing. The correction and
confirmation flags are set from the database record, not from the model's
response — the model may suggest something is critical, but it cannot demote a
correction.

**Hidden data never reaches the model.** [`services/brief.py`](app/services/brief.py)
calls `visibility.resolve()` *before* the model call. The provider is handed only
statements that already passed the consent gate, so hidden data cannot leak
through a model response, a prompt injection, or a logging accident. This
ordering is the whole privacy argument, not an optimization.

And the elder can see all of it: *"Nour Haddad viewed your bathing preferences at
9:52 today."* She can see who looked. She cannot be quietly written out of her
own care.

---

## 3. Features

### The brief — six lines, chosen for this task and this worker

The record may hold thirty sentences. Only some apply to bathing. Only some apply
at 10am. Only some are new to this worker. Every sentence carries its task and its
hours from the moment it is written, so choosing the right ones is a matter of
checking which ones match. A model then picks the six that matter most and rewrites
each as one clean line.

The model can only choose from the sentences it is handed. Every line it returns
must carry the number of the sentence it came from, and a line without a valid
number is thrown away before it reaches the screen. It picks and rewords. It never
adds.

If the model is slow or broken, the filtered sentences show exactly as they were
written. The brief still works.

### The check-out — three parts, one minute

Twelve observation buttons, a fixed list. Workers cannot type their own. That is
what makes them countable: three workers tapping *didn't finish meal* is a number,
not three separate comments nobody compares.

One free text box, for one thing only: what the next person should know.

### The handover — a worker's note is an opinion until the family says otherwise

A note written at check-out does not go into the record. It becomes a suggestion.
The family reads it and taps approve or dismiss. Approved, it becomes a permanent
sentence with her name on it.

### Confirmation — how many workers backed this

When several workers are given the same tip and it works, the tip shows how many
of them confirmed it. A tip three people confirmed is stronger than one person's
guess, and the brief says so.

### Corrections — one button, one line, top of every brief

When something goes wrong, the family clicks one button on that visit and writes
one line. That line goes to the top of every future brief, marked, for every
worker, whether she has been here before or not.

This is how *the same mistake keeps happening* becomes *it happened once and then
it was written down*.

### Repeat detection — three times in five visits

The observation buttons are counted across visits. When the same one is tapped
three times in the last five visits, the system suggests adding it to the record.
Three different workers each noticing something once now adds up to something the
family sees.

### First visit or fifth — the brief knows the difference

The system counts how many times each worker has been to this home. A new worker
gets the full brief. A returning worker gets only what changed since she was last
here — every sentence records when it was last edited, and every visit records
when it happened.

Her brief can be one line. It can be zero lines, saying nothing has changed. That
is a correct brief, and it is shown as one.

### The counter — the product in one line

At the top of every brief:

> **First visit · 30 notes from 6 previous workers**

Normally the seventh worker knows nothing. Here she starts with what six people
learned.

### Access control — the elderly person owns the record

She can hide any sentence from any specific person. A worker sees only what her
task requires: she cannot look at anything else, cannot see other visits, cannot
see who else has been here.

Every time anyone reads any part of the record, a line is written. She can read
those lines:

> Marie-Ève viewed your bathing preferences at 9:52 today.

She can see who looked. Nobody can quietly cut her out of her own care.

### Capacity — three settings, not a yes or no

She decides. Or she decides, and changes are shown to her to confirm. Or someone
legally appointed decides, and she can still see that it happened.

Most people have good days and bad days. Every other system makes you pick one.

---

## 4. Architecture

**Dominant pattern: a layered monolith with one enforced choke point.** Four
layers, strict one-directional dependencies, and every statement read funnelled
through a single function.

```
  routes/          parse request → call a service → render.  No business rules.
     │             caregiver (/caregiver)   elder (/elder)   worker (/v/{token})
     ▼
  services/        business logic. No SQL, no HTTP.
     │             visibility ← THE RESOLVER, the only read path
     │             brief · familiarity · foldback · tokens
     ▼
  repositories/    every SQL statement in the project. No policy.
     │             returns dataclasses, never sqlite3.Row
     ▼
  db.py            sqlite3 + JSON helpers          schema.sql — 10 tables

  ai/              isolated. Receives strings, returns data. No HTTP, no DB.
                   Delete the folder and the app still runs.
```

`templates/` are presentation only — readable strings are built in Python, not
in Jinja, so they can be tested.

### Three surfaces, deliberately not one app

| Surface | Who | Access | Design language |
|---|---|---|---|
| `/caregiver` | The daughter running the record | Session (demo: no login) | Dense desktop console |
| `/elder` | Amina herself | Session (demo: no login) | 20px minimum, high contrast, confirmations |
| `/v/{token}` | The care worker | One signed token, one visit | Mobile-first, one-handed, no navigation chrome |

There is no shared navigation between them — especially not on the worker pages.
The worker surface has **two endpoints total**: read the brief, submit the
check-out. That is the entire attack surface a stranger can reach.

### The brief pipeline — the order is load-bearing

```
build_brief(visit_id)
   │
   ├─ 1. cache          served from the `brief` table if generated already
   │                    (fast, cheap, and survives a dead network mid-demo)
   │
   ├─ 2. CONSENT GATE   visibility.resolve(elder, actor, purpose)
   │                    deterministic WHERE clause — hidden_from, task scope,
   │                    excluded tasks, time-window overlap → + access-log row
   │
   ├─ 3. familiarity    first visit → everything;  returning worker → delta only
   │
   ├─ 4. THE MODEL      receives only what survived step 2.
   │                    Job: rank and compress 30 → 6.  8-second timeout.
   │
   ├─ 5. VALIDATION     every line must carry an id from the candidate set;
   │                    unknown ids dropped, never repaired.  Hard cap at 6.
   │
   └─ 6. persist        lines + model + fallback_used → `brief`
```

Step 2 is plain code because it is the part that must never be wrong, and
deterministic code is the only thing we can prove is never wrong. Step 4 is a
model because "which six of these thirty matter for a morning bathing visit" is
real judgment that is miserable to express as rules.

### Every failure still produces a usable brief

| Failure | Behaviour |
|---|---|
| No `ANTHROPIC_API_KEY` at all | Fallback: permitted statements rendered verbatim, corrections first, sliced to six |
| Model down, slow, or > 8s | Same fallback path |
| Malformed JSON back | Same fallback path |
| Model returns unknown ids | Those lines dropped, the rest renders |
| Network dies after generation | Served from the `brief` cache |
| Worker never checks out | Visit expires; the family sees "no check-out" rather than silence |
| Worker link leaked | One brief, one time window, nothing else reachable |

**Nothing in the critical path depends on the model succeeding.** The whole
product demos with the API key removed.

### Token lifecycle

```
create visit   → secrets.token_urlsafe(32); only the SHA-256 hash is stored
               → valid from (start − 30 min) to (end + 2 h)
worker opens   → validate hash, window, state → visit: scheduled → briefed
worker submits → visit: briefed → completed → token burned
window passes  → expired, token dead
```

An invalid link renders the neutral expired page with **HTTP 200** and no hint
that anything else exists. The token carries no data; it is a lookup key into a
scope the server owns.

### Data model — 10 tables

`elder` · `person` · `worker` · `preference_statement` · `visit` · `brief` ·
`checkout` · `observation_code` · `proposed_update` · `access_log`

Three things worth defending at Q&A:

- **Scope lives on the statement, not in the query.** `applies_to_tasks`,
  `excluded_tasks` and the time window are columns. That is what makes "a female
  worker for bathing, but a male nurse is fine for a blood draw" one row instead
  of application logic.
- **`capacity_mode` is three-valued, not boolean.** `self` / `assisted` /
  `mandated`. Every existing system models decision-making capacity as a
  switch; every family experiences it as a spectrum with good days and bad days.
- **Logs are append-only.** Access logs and check-outs are never edited or
  deleted. Corrections are new rows, not mutations.

Full reasoning: [architecture.md](architecture.md). File-by-file build
instructions: [implementation-guide.md](implementation-guide.md). Working rules
for contributors and agents: [AGENTS.md](AGENTS.md).

---

## 5. Run it for the first time

**Requires Python 3.12+.** Nothing else — no Node, no build step, no Docker, no
API key.

```bash
git clone <this-repo> && cd CareCircle

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m app.reset_db      # creates data/carecircle.db and seeds the demo history
python run.py               # → http://127.0.0.1:8000
```

Open <http://127.0.0.1:8000> and pick a role. `GET /health` returns
`{"ok": true}`.

<details>
<summary>Using <code>uv</code> instead</summary>

```bash
uv sync
uv run python -m app.reset_db
uv run python run.py
```
</details>

### The demo on a real phone

The worker brief is the screen judges remember, and it belongs on a phone. Serve
on the LAN:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then set `ELDERCARE_BASE_URL` to your machine's LAN address (e.g.
`http://192.168.1.42:8000`) so the QR code on the visit-created page points
somewhere the phone can reach.

> **Test this by hour four, not hour fourteen.** Conference wifi very often
> blocks client-to-client traffic. Hit `http://<lan-ip>:8000/health` from the
> phone's browser to confirm the tunnel before you rely on it. If it is blocked,
> fall back to a phone hotspot with the laptop joined to it.

### The API key is optional

```bash
cp .env.example .env      # then set ANTHROPIC_API_KEY to enable model-written briefs
```

Every variable has a safe default and none is required. With no key, the app runs
the deterministic fallback path: permitted statements rendered verbatim,
corrections first, sliced to six. **Nothing crashes when the key is absent** —
that is the fallback guarantee, and the whole product demos without it.

| Variable | Default | Purpose |
|---|---|---|
| `ELDERCARE_DB_PATH` | `data/carecircle.db` | The database *is* this file. Deleting it is a reset |
| `ELDERCARE_BASE_URL` | `http://127.0.0.1:8000` | Base for the worker link and QR code |
| `ANTHROPIC_API_KEY` | *(empty)* | Empty → deterministic fallback |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` | Swappable; the client takes the first text block |

Reset to a clean demo state at any time with `python -m app.reset_db`.

---

## 6. The scripted demo path

Seven steps, ~3 minutes, tested end to end. The seed is built so that step 5
fires a real proposal live rather than a staged one.

1. **`/`** — the role picker. Say out loud that it is not a product screen.
2. **Caregiver → Visits** — create a visit for *someone who has never been here*.
   That path is not an edge case; it is the problem.
3. **Visit created** — the link, the QR code, and the framing line:
   *"Nour has never visited Amina. Her brief carries 30 notes from 6 previous
   workers."*
4. **The worker brief, on a phone** — corrections first under a red rule, then
   the critical lines, and `— 3 workers` on the confirmed approaches.
5. **Check-out** — tick `refused equipment` (the seed carries two occurrences;
   this is the third and crosses the pattern threshold) and leave a handover note.
6. **Caregiver → Proposals** — both proposals are now waiting, one labelled
   *From a handover note*, one *From a pattern*. Approve one; it becomes a
   statement in the record.
7. **Elder → Access log** — *"Nour Haddad viewed your bathing preferences at 9:52
   today."*

**The closer:** re-open the same worker link. *This link has expired.* One line,
HTTP 200, no hint that anything else ever existed there.

The seeded history is 1 elder, 4 family members, 7 workers, 30 statements,
6 completed visits with check-outs, and 12 observation codes.

---

## 7. Tests

```bash
python -m unittest discover tests      # 23 tests
python -m app.ai._manual_test          # six AI scenarios; 3 and 6 are the ones to show
```

23 automated tests, all passing, covering the parts where being wrong is
expensive:

| Area | What is asserted |
|---|---|
| Resolver | Hides from the named person but never from the elder; scopes by task; **always** logs |
| Tokens | Only the hash is stored; the token burns on check-out; an unknown token is indistinguishable from an expired one |
| Validator | Drops ids outside the candidate set; never raises; never repairs; the model cannot demote a correction |
| Delta briefs | A returning worker with nothing changed gets **zero** lines |
| Fold-back | Handover note → proposal; the third occurrence fires a pattern proposal; corrections skip the queue; approval creates a statement |
| Visibility UI | The form shows *who can see this*; the database stores *hidden from* — the set difference is tested |
| Vocabulary | A worker cannot invent an observation code |
| Smoke | Every page renders; `/health` |

Two manual scenarios are worth running live: **scenario 3** returns zero lines
for a returning worker with nothing changed, which proves the delta logic is real
rather than cosmetic; **scenario 6** feeds the validator a fabricated
`statement_id` and that line is dropped while the rest render.

---

## 8. Cost and sustainability

The running cost of this system is close to the floor, on purpose.

- **One process, one file.** FastAPI + SQLite. No database server, no Redis, no
  queue, no object storage. It runs on the smallest VPS tier available.
- **No frontend build, no frontend hosting.** Server-rendered Jinja with Tailwind
  from a CDN. There is no `node_modules`, no bundler, no second deploy target.
- **One model call per visit, then cached.** The brief is persisted in the
  `brief` table and re-served from it. A visit costs one request of roughly
  1–2k input tokens capped at 1024 output tokens — and re-opening the link costs
  zero.
- **The model is optional infrastructure.** Remove the key and the product still
  works. Cost floor is therefore *hosting only*; the AI is an upgrade, not a
  dependency. That also makes it deployable inside an agency that cannot send
  data to a third party.
- **Swappable model.** `ANTHROPIC_MODEL` is one env var and the client reads the
  first text block, so moving to a cheaper or self-hosted model is a config
  change, not a refactor.

**Who would pay:** home-care agencies, for whom turnover is already a line item —
onboarding a replacement worker to a client costs supervisor hours today, and
that is the budget this competes for. Families are the beneficiaries; the agency
is the buyer.

---

## 9. Deliberate scope decisions

Not oversights — decisions, and worth stating as such at Q&A.

| Not built | Why |
|---|---|
| Real authentication | Sessions without passwords for the demo. Production needs proper auth plus the obligations that come with health information about Quebec residents: express consent, a designated privacy officer, breach reporting. It is a slide, not a hackathon build |
| Scheduling and dispatch | The agency's system owns the schedule. We attach to a visit; we do not create it |
| SMS delivery of the worker link | A link plus a QR code is functionally identical for the demo and avoids an entire telephony dependency |
| Real-time anything | Every flow is request/response. No sockets, no push |
| Multi-elder households, offline mode | Defensible later; none of them change the schema |

### Why this extends without new core tables

Every roadmap feature is a new view over `preference_statement` or `checkout`:

| Feature | Reads |
|---|---|
| Emergency summary for a hospital visit | `preference_statement`, filtered by category |
| "What's changed?" sheet before an appointment | `checkout`, aggregated over a date range |
| Sibling workload visibility | `visit`, grouped by person |
| Ramadan schedule shift | `time_start` / `time_end` already exist |
| Cost tracking | one column on `visit` |

That is the argument for this architecture in one line: **we are not building a
feature, we are building the two structures every feature in this problem space
needs.**

---

## 10. Repo map

```
app/
  main.py            app, startup, routers
  config.py          env vars and the closed lists
  db.py              sqlite3 connection + query helpers
  schema.sql         all ten tables, run with executescript
  reset_db.py        drop, recreate, reseed — one command
  seed.py            the demo history: 6 workers, 30 statements, 6 past visits
  models.py          frozen dataclasses mirroring the tables
  repositories/      every SQL statement in the project lives here
  services/
    visibility.py    THE RESOLVER — the single read choke point
    tokens.py        generation, hashing, window, validation
    familiarity.py   how much this worker already knows
    brief.py         cache → resolve → familiarity → AI → validate → persist
    foldback.py      check-out → proposal → statement
  ai/                the model, fully isolated. Delete it and the app still runs
  routes/            home, caregiver, elder, worker — thin
  templates/         Jinja2 + Tailwind CDN, no build step
  static/app.js      QR rendering and copy-to-clipboard, nothing else
data/carecircle.db   gitignored — deleting it is a database reset
tests/               23 unittest cases
```

**The one rule that keeps this clean:** routes never call
`repositories.statements` for a read. They call `visibility.resolve()`. If you
find yourself importing `repositories.statements` inside a route, stop.

### Contributor notes

The check-out posts `completion`, `observation_codes` (repeated), `note_text`,
`handover_note`, and `confirm_{statement_id}` (`worked` / `didnt`). Statement
visibility posts `visible_to` (repeated) — the route converts *visible* into
*hidden* by set difference, because storing `hidden_from` is right for the
resolver while showing "who can see this" is right for the human.

The raw visit token exists in exactly two places: the URL, and the caregiver's
screen at creation time. Only the SHA-256 hash is stored. It reaches the
created-visit page in a query string; production would use a flash message.
