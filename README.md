# CareCircle

Care worker turnover is the problem. Families repeat the same history to every
new worker, each worker arrives at her own approach, and the same mistakes
recur. Knowledge about an elderly person accumulates inside individual workers
and leaves when they do.

Every visit gets a short brief before it and a short check-out after it. The
brief carries forward what previous workers learned. The check-out captures what
this worker learned before she disappears. **A seventh worker should arrive
knowing what the first six figured out.**

Built to [implementation-guide.md](implementation-guide.md).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.reset_db          # creates data/carecircle.db and seeds the demo history
python run.py                   # http://127.0.0.1:8000
```

For a phone on the same network — **test this by hour four, not hour fourteen;
conference wifi often blocks client-to-client traffic**:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then set `ELDERCARE_BASE_URL` to your machine's LAN address so the QR code on the
visit-created page points somewhere a phone can reach. `GET /health` confirms the
tunnel works before you demo.

### The API key is optional

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` to enable model-written
briefs. With no key the app runs the deterministic fallback: candidates rendered
verbatim, corrections first, sliced to six. **Nothing crashes when the key is
absent** — that is the fallback guarantee, and you can demo the whole product
without it.

## Layout

```
app/
  main.py            app, startup, routers
  config.py          env vars and the closed lists
  db.py              sqlite3 connection + query helpers
  schema.sql         all ten tables, run with executescript
  reset_db.py        drop, recreate, reseed — one command
  seed.py            the demo history: 6 workers, 30 statements, 6 past visits
  models.py          dataclasses mirroring the tables
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
data/carecircle.db   gitignored
```

**The one rule that keeps this clean:** routes never call `repositories.statements`
for a read. They call `visibility.resolve()`. If you find yourself importing
`repositories.statements` inside a route, stop.

## The three properties worth demonstrating

**One read path.** `services/visibility.py` is the only function that returns
statement data. It applies the identity filter, then the purpose filter, then
the time filter, then writes an access-log row — unconditionally, with no
`if should_log` and no `skip_filters` bypass. There is exactly one function to
audit.

**The model cannot invent facts.** `ai/validator.py` drops any line whose
`statement_id` is not in the candidate set. It never repairs a malformed line,
because repairing means inventing. Correction and confirmation flags are set
there from the database record, not taken from the model's response — the model
may suggest something is critical, but it cannot demote a correction.

**Hidden data never reaches the model.** `services/brief.py` calls
`visibility.resolve()` *before* the model, so the model is only ever handed
statements that already passed the consent gate. Do not "optimize" by resolving
after the call.

## Form field names

The check-out posts `completion`, `observation_codes` (repeated),
`note_text`, `handover_note`, and `confirm_{statement_id}` (`worked` / `didnt`).
Statement visibility posts `visible_to` (repeated) — the route converts *visible*
into *hidden* by set difference, because storing `hidden_from` is right for the
resolver while showing "who can see this" is right for the human.

## Demo path

1. `/` — role picker. Not a product screen.
2. **Caregiver → Visits** — create a visit for *someone new*. That path is not an
   edge case; it is the problem.
3. **Visit created** — the link, the QR, and the framing line:
   *"Nour has never visited Amina. Her brief carries 30 notes from 6 previous workers."*
4. **Worker brief** on a phone — corrections first with a red rule, then the
   critical lines, `— 3 workers` on the confirmed approaches.
5. **Check-out** — tick `refused equipment` (the seed carries two; this is the
   third) and leave a handover note.
6. **Caregiver → Proposals** — both proposals are now waiting, one labelled
   *From a handover note*, one *From a pattern*.
7. **Elder → access log** — *"Nour Haddad viewed your bathing preferences at 9:52 today."*

Re-open the same worker link afterwards: *This link has expired.* One line, status
200, no hint that anything else exists.

## Tests

```bash
python -m unittest discover tests
python -m app.ai._manual_test          # six AI scenarios; 3 and 6 are the ones to show
```

Scenario 3 returns **zero lines** for a returning worker with nothing changed —
that proves the delta logic is real rather than cosmetic. Scenario 6 feeds the
validator a fabricated `statement_id`; that line is dropped and the rest render.

## Notes

There is no religion field, no "cultural preferences" section, and no
Muslim-specific anything. Every statement is entered the same way. If a judge
asks how the *"Muslim-friendly is not one setting"* constraint is handled, the
caregiver record screen is the answer: there is nowhere to put it, by design.

The raw visit token exists in exactly two places — the URL, and the caregiver's
screen at creation time. Only the SHA-256 hash is stored. It travels to the
created-visit page in a query string; production would use a flash message.
