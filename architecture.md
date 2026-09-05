# System architecture

Companion to the team brief. This document defines the components, the data model, and the two flows that make up the product. Stack choices are deliberately absent — every decision here holds regardless of which framework we pick.

---

## 1. Design principles

Five rules. If a design decision conflicts with one of these, the decision is wrong.

**P1 — One choke point for reads.** No surface, no service, and no query reads preference data directly. Everything goes through the visibility resolver. This is what makes our privacy claim demonstrable rather than aspirational: there is exactly one function to audit.

**P2 — The model selects, it never writes and never invents.** Every line the AI produces must carry the id of a statement a human wrote. Anything without a valid id is discarded before render. The model has no write path to any table.

**P3 — Logs are append-only.** Check-outs and access records are never edited or deleted. They accumulate. Corrections are new rows, not mutations.

**P4 — Nothing changes the record without a human approving it.** Check-outs produce *proposals*. A human turns a proposal into a statement. There is no autonomous write.

**P5 — The worker holds no account and no lasting access.** Their entire relationship with the system is one signed token, scoped to one visit, that dies afterward.

---

## 2. Components

### Client surfaces

| Surface | Who | Access mechanism | Can do |
|---|---|---|---|
| Caregiver console | Primary family caregiver | Session | Manage statements, create visits, approve proposals, view visit log |
| Elder view | The elderly person | Session, large-type UI | View and edit own statements, set per-item visibility, read access log, approve proposals |
| Worker page | Care worker | Signed visit token in URL | Read one brief, submit one check-out |

The worker surface is a different kind of thing from the other two: no account, no navigation, no history, one screen at a time. Treat it as a separate app that happens to share a backend.

### Backend services

These are modules, not deployables. One process is fine.

- **Record service** — CRUD over preference statements. Enforces that every statement carries a scope.
- **Visit service** — creates visits, issues and validates tokens, owns the visit state machine.
- **Visibility resolver** — the choke point. Given (elder, requesting actor, purpose), returns the set of statements that actor is permitted to see. Writes an access-log row every time it runs.
- **Brief builder** — the three-stage pipeline in section 5.
- **Check-out service** — ingests structured observations, burns the token, emits proposals.
- **Proposal service** — holds pending record changes awaiting human approval.
- **Access log service** — append-only writer, elder-readable.

---

## 3. Trust zones

Four zones, with progressively less trust. The boundary crossings are where the security thinking lives.

**Zone A — The elder.** Owner of the record. Can see everything about herself, including the full access log. Only actor who can set visibility rules (unless capacity mode says otherwise).

**Zone B — Family.** Sees the record minus anything the elder has hidden from them specifically. The primary caregiver additionally creates visits and approves proposals. Family members are individually identified — visibility is per-person, not per-role, because "hide this from my brother but not my sister" is a real requirement.

**Zone C — Worker.** Sees only what the resolver returns for this task, this time window, this role. Cannot enumerate, cannot navigate, cannot see history, cannot see who else has visited. Sees the elder's first name only.

**Zone D — Model provider.** Sees the *already-filtered* statement set and the visit context. Never sees the health insurance number, the address, the full name, the financial or legal records, or any statement the elder has hidden.

That last boundary is the important one and it comes free from the ordering: **the consent gate runs before the model call, not after.** Hidden data never leaves the database, so it cannot leak through a model response, a prompt injection, or a logging accident. This ordering is not an optimization — it is the whole privacy argument, and it must not be reversed for convenience.

---

## 4. Data model

```
elder
  id, display_name, primary_language, capacity_mode
  capacity_mode ∈ { self, assisted, mandated }

person
  id, elder_id, name, role, language
  role ∈ { primary_caregiver, family, worker }

preference_statement
  id, elder_id
  statement            -- one plain sentence, written by a human
  category             -- care | communication | routine | observance | safety
  applies_to_tasks[]   -- empty means all tasks
  excluded_tasks[]
  time_start, time_end -- null means always
  hidden_from[]        -- person ids
  status               -- active | proposed | rejected | retired
  source_checkout_id   -- null if entered by hand
  created_at, updated_at

visit
  id, elder_id
  worker_name, worker_role, worker_language
  task_type
  scheduled_start, scheduled_end
  token_hash, token_expires_at
  state                -- scheduled | briefed | completed | expired

brief
  id, visit_id
  selected_statement_ids[]
  rendered_lines_json
  model, generated_at, fallback_used

checkout
  id, visit_id
  completion           -- yes | partial | no
  observation_codes[]
  note_text
  submitted_at

observation_code           -- seed table, ~20 rows
  code, label_en, label_fr, category

proposed_update
  id, elder_id, source_checkout_id
  suggested_statement, status
  decided_by, decided_at

access_log
  id, elder_id, actor_label, action, target_summary, at
```

### Three things worth defending

**There is no religion column.** Nothing in this schema branches on the elder being Muslim. A non-Muslim elder uses the identical structure. Religion is a source of statements; it is not a field.

**`capacity_mode` is three-valued, not boolean.** `self` — she decides. `assisted` — she decides, but changes are proposed for her to confirm, which is how "good days and bad days" actually works. `mandated` — a legal representative decides, and the fact of that transfer is visible in the record rather than silent. Every existing system models this as a boolean and every family experiences it as a spectrum.

**Scope lives on the statement, not in the query.** `applies_to_tasks`, `excluded_tasks`, and the time window are attributes of the statement itself. This is what makes "female worker for bathing but a male nurse is fine for a blood draw" expressible as one row instead of as application logic.

`task_type` is a closed list: `bathing, dressing, meal, medication_support, housekeeping, nursing_visit, transport, companionship`. Closed lists are what make scoping tractable — an open text field here would push the filtering work onto the model, which is exactly backwards.

---

## 5. The brief pipeline

Three stages, in this order. The order is load-bearing.

### Stage 1 — Consent gate and deterministic filter

Plain code. No model involved.

```
candidates = statements WHERE
     elder_id = visit.elder_id
 AND status = 'active'
 AND requesting_person_id NOT IN hidden_from
 AND (applies_to_tasks is empty OR contains visit.task_type)
 AND visit.task_type NOT IN excluded_tasks
 AND (time window is null OR overlaps visit window)
```

This is a `WHERE` clause. It runs first because it is the part that must never be wrong, and deterministic code is the only thing we can prove is never wrong.

### Stage 2 — Selection and phrasing

The model receives the surviving candidates, each with an id, plus the visit context (task, time, worker role, worker language). It returns:

```json
{ "lines": [ { "statement_id": 7,
               "text": "Female worker required for bathing",
               "critical": true } ] }
```

Three constraints in the prompt: every line carries an id from the supplied set; the text is a rephrasing of that statement introducing no new fact; six lines maximum, criticals first.

The model's actual job is relevance ranking and compression — picking the six that matter out of thirty, and turning "she agrees to everything to be polite so you have to check twice before leaving" into one clean line. That is real judgment, and it is difficult to express as rules, which is precisely why it belongs to a model.

### Stage 3 — Validation, cache, fallback

Plain code again.

- Any line whose `statement_id` is not in the Stage 1 candidate set is **dropped**. This is the enforcement point for P2.
- Hard-slice to six lines regardless of what came back.
- Persist the result in `brief`. Repeat requests for the same visit serve from cache — faster, cheaper, and it survives a dead network mid-demo.
- If the response fails to parse or the call errors, render the Stage 1 candidates verbatim in category order and set `fallback_used = true`.

The fallback matters more than it looks. It means we have a working product with the API key removed. Build it early and test it by deliberately unsetting the key.

---

## 6. The check-out and fold-back path

```
worker submits check-out
        │
        ├─ append row to checkout            (immutable)
        ├─ transition visit → completed
        ├─ burn the token
        │
        └─ if the check-out contains something durable
                 │
                 └─ create proposed_update    (status = pending)
                          │
                          └─ human approves
                                   │
                                   └─ new preference_statement
                                        (status = active,
                                         source_checkout_id set)
```

**Check-outs never touch the record directly.** A check-out is an observation about one moment; a statement is a durable fact about a person. Only a human promotes one to the other. This is P4, and it's also the answer to "what if the AI gets it wrong" — a wrong proposal is a rejected proposal, not a corrupted record.

Who approves depends on `capacity_mode`: `self` → the elder; `assisted` → the elder, with the caregiver able to queue it; `mandated` → the representative, and the elder still sees that it happened.

---

## 7. The visibility resolver

Single function, single responsibility:

```
resolve(elder_id, actor, purpose) -> statements[]
```

Every path in — brief generation, the elder's own view, a family member browsing, an export — calls this. There is no second way to read statements.

It applies, in order: capacity mode, actor identity, per-statement `hidden_from`, purpose scoping (task and time for workers; unrestricted for the elder), and then it writes an access-log row.

**Access logging is not optional and not conditional.** If the resolver ran, a row exists. This is what lets the elder's view show *"Marie-Ève viewed your bathing preferences at 9:52"* — and that single line is what distinguishes this product from surveillance of her. She can see who looked. She cannot be quietly written out of her own care.

---

## 8. Token lifecycle

```
create visit
   → generate 32 random bytes, store only the hash
   → valid from (scheduled_start − 30 min) to (scheduled_end + 2 h)

worker opens link
   → validate hash, window, and visit state
   → visit: scheduled → briefed
   → brief renders (generated, or served from cache)

worker submits check-out
   → visit: briefed → completed
   → token burned

window passes with no check-out
   → visit: → expired, token dead
```

The token carries no data. It is a lookup key into a scope that the server owns. A leaked link exposes one brief for a few hours and nothing else — no navigation, no other visits, no other elders.

Delivery is a text message in production. For anything short of that, a link plus a QR code is functionally identical and avoids the entire telephony dependency.

---

## 9. API surface

Small enough to hold in your head.

**Caregiver**
```
POST   /statements
PATCH  /statements/:id
POST   /visits                     → returns link
GET    /visits/:id
POST   /proposals/:id/decide
```

**Elder**
```
GET    /me/statements
PATCH  /me/statements/:id/visibility
GET    /me/access-log
POST   /proposals/:id/decide
```

**Worker (token-scoped)**
```
GET    /v/:token                   → the brief
POST   /v/:token/checkout          → burns the token
```

Two endpoints on the worker side. That's the whole surface a stranger can reach.

---

## 10. Failure and degradation

| Failure | Behaviour |
|---|---|
| Model API down or slow | Stage 3 fallback renders filtered statements verbatim; brief still useful |
| Model returns malformed JSON | Same fallback path |
| Model returns unknown ids | Those lines dropped; the rest renders |
| Network dies after brief generated | Served from `brief` cache |
| Worker never checks out | Visit expires; family sees "no check-out" rather than silence |
| Token leaked | One brief, one time window, nothing else reachable |

Every degraded path still produces a usable brief. Nothing in the critical path depends on the model succeeding.

---

## 11. Deliberately out of scope

Not oversights — decisions, and worth stating as such.

**Real authentication.** Sessions without passwords for the demo. Production needs proper auth plus the obligations that come with handling health information about Quebec residents: express consent for sensitive data, a designated privacy officer, breach reporting. Put it on a slide; don't build it.

**Scheduling and dispatch.** The agency's system owns this. We attach to a visit; we don't create the schedule.

**Real-time anything.** Every flow is request-response. No sockets, no push.

**Multi-elder households, service-provider accounts, offline mode.** All defensible later; none of them change the schema above.

---

## 12. Why this extends

Every roadmap feature is a new view over `preference_statement` or `checkout`. Nothing needs a new core table:

| Feature | Reads |
|---|---|
| Emergency summary for a hospital visit | `preference_statement`, filtered by category |
| "What's changed?" sheet before an appointment | `checkout`, aggregated over a date range |
| Sibling workload visibility | `visit`, grouped by person |
| Caregiver matching | `preference_statement` as a search query |
| Ramadan schedule shift | `time_start` / `time_end` already exist |
| Cost tracking | one column on `visit` |

That is the argument for this architecture in one line: **we are not building a feature, we are building the two structures every feature in this problem space needs.**
