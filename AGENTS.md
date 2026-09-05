# CareCircle — agent instructions

## Product and stack

Build CareCircle as a single FastAPI application using SQLite, Jinja2 templates,
Tailwind loaded from a CDN, and only small amounts of vanilla JavaScript. Do not
introduce React, an ORM, migrations, a separate frontend, or a build step.

The application manages sensitive elder-care preferences. Privacy, consent,
traceability, and graceful degradation are product requirements, not optional
enhancements.

## Ownership and module boundaries

Keep the following boundaries strict.

- `repositories/` contains every SQL statement. Repositories accept/return
  dataclasses or primitives, never `sqlite3.Row`, and contain no policy logic.
- `services/` contains business logic only: no SQL and no HTTP concerns.
- `routes/` parses requests, invokes a service, and renders/redirects. Keep each
  handler short; routes must not contain business rules.
- `ai/` is isolated from the rest of the app. It may receive strings/models and
  return data, but must not access HTTP routes or persistence directly.
- `templates/` are server-rendered presentation only. Build readable strings and
  other testable logic in Python, not Jinja.

Create or update typed, frozen dataclasses in `models.py` before using new
cross-module shapes. Repositories should use the shared JSON helpers in `db.py`
so JSON-text columns are never exposed beyond the persistence layer.

## Non-negotiable privacy rules

`services.visibility.resolve(elder_id, actor, purpose)` is the sole read path
for preference statements. All statement reads in routes and brief generation
must use it; never import `repositories.statements` in a route to read
statements, and never add a bypass or `skip_filters` option.

The resolver must, in order:

1. Load active statements.
2. Apply identity visibility (`hidden_from`), except that the elder sees all of
   their own statements.
3. Apply task scope and exclusions.
4. Apply overlapping time-window scope.
5. Unconditionally write an access-log entry.
6. Return only surviving statements.

Access logs and check-outs are append-only: do not add delete behavior. Store
who is *hidden* in `hidden_from`, but present users with the positive wording
of who can see a statement.

## Worker token and visit handling

- Generate raw worker tokens with `secrets.token_urlsafe(32)` and persist only
  their SHA-256 hash.
- Validate a token on both worker GET and checkout POST. It is invalid outside
  its configured time window and once completed/expired.
- An invalid worker link renders only the neutral expired state with HTTP 200;
  do not reveal whether a token ever existed.
- Completing a checkout immediately marks the visit completed, burning its
  token. Never trust that an earlier GET was valid.
- The worker may select only the closed `OBSERVATION_CODES` vocabulary. Do not
  turn free-text notes into clinical assessments.

## Brief and AI safety

`services.brief.build_brief()` must resolve consent-filtered candidates before
calling the AI; the model must never receive statements that did not pass the
resolver. Preserve its public return contract:
`(lines, fallback_used, total_active_statements)`.

AI calls have an eight-second timeout and must fail safely when no API key,
network, response, or parsing is unavailable. Validation must discard malformed
or out-of-candidate IDs, cap output at `MAX_BRIEF_LINES` (6), and never raise.
Fallback lines render permitted source statements verbatim, sorted by configured
category, with no invented content. The application must work with no API key.

AI never decides what enters the permanent record. Foldback creates proposals
from repeated structured observations; a caregiver or eligible elder explicitly
accepts or rejects them before a statement is created.

## UI requirements

There are three deliberately separate surfaces. Do not add shared navigation
between them, especially not to worker pages.

- Caregiver: dense, desktop-oriented console; forms use normal POST/redirect
  behavior. Use `<details>` for simple disclosures.
- Elder: minimum 20px body text, high contrast, generous spacing, labelled
  controls, confirmations for changes, and simple access-log language.
- Worker: mobile-first, one-handed, minimal chrome, large tap targets. The
  brief is at most six readable lines with a fixed checkout action; expired and
  done pages are intentionally nearly empty.

Prefer semantic HTML and CSS/Tailwind over JavaScript. `static/app.js` should be
limited to QR rendering and copy-to-clipboard behavior; checkbox/radio toggles
should work without JavaScript. Do not add Muslim-specific or religion fields:
all preferences are entered as ordinary scoped statements.

## Data, configuration, and seed behavior

- Use raw SQLite and ISO-8601 text timestamps. Database reset means deleting the
  database file; do not add a migration framework.
- Keep fixed task types, categories, observation codes, token constants, and
  `MAX_BRIEF_LINES` in `config.py` as module-level constants.
- Seed idempotently only when data is absent. Preserve a believable demo: one
  assisted elder, several people, roughly 30 varied scoped statements, completed
  visits/check-outs, and repeat observations that can trigger a proposal.
- Keep `GET /health` returning `{"ok": true}`.

## Change discipline and verification

Before changing a cross-module contract, inspect all callers and templates.
Preserve the form names `completion`, repeated `observation_codes`, and
`note_text`, unless every producer and consumer is updated together. Keep the
brief template compatible with `BriefLine(text, statement_id, critical)`.

For meaningful changes, run the smallest relevant checks: syntax/import checks,
the test suite if present, and a manual path covering the affected route. Test
the no-API-key fallback whenever altering AI or brief behavior. Do not expose
raw tokens in logs, persistence, or error pages.
