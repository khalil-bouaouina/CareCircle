"""A9 -- the whole loop over HTTP, standing in for frontend integration."""

from datetime import datetime, timedelta

from .conftest import ELDER, KARIM, LEILA


def _window():
    now = datetime.now().replace(microsecond=0)
    return (now - timedelta(minutes=10)).isoformat(), (now + timedelta(minutes=50)).isoformat()


def _create_visit(client, task_type, worker_name, worker_role):
    start, end = _window()
    r = client.post(
        "/visits",
        headers=LEILA,
        json={
            "worker_name": worker_name,
            "worker_role": worker_role,
            "worker_language": "fr",
            "task_type": task_type,
            "scheduled_start": start,
            "scheduled_end": end,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_reset_and_seed(fresh):
    r = fresh.post("/reset").json()
    assert r["statements"] == 31 and r["visits"] == 3
    assert len(fresh.get("/observation-codes").json()) == 20


def test_auth_headers_required(fresh):
    assert fresh.get("/statements").status_code == 401
    assert fresh.get("/statements", headers={"X-Actor-Person-Id": "3"}).status_code == 403  # workers have no account
    assert fresh.post("/visits", headers=KARIM, json={}).status_code == 403  # family can't create visits
    assert fresh.get("/me/statements", headers=LEILA).status_code == 403


def test_full_loop(fresh):
    client = fresh

    # -- caregiver creates a bathing visit; the link carries the raw token once
    created = _create_visit(client, "bathing", "Marie-Ève Tremblay", "personal_support_worker")
    token = created["token"]
    assert created["link"].endswith(f"/v/{token}")
    assert created["visit"]["state"] == "scheduled"

    # -- worker opens the brief: scheduled -> briefed, brief generated via fallback
    brief = client.get(f"/v/{token}")
    assert brief.status_code == 200, brief.text
    brief = brief.json()
    ids = [l["statement_id"] for l in brief["lines"]]
    assert 1 in ids  # female worker for bathing
    assert 2 not in ids and 8 not in ids  # nursing-only rows never appear
    assert brief["fallback_used"] is True and brief["model"] is None
    assert brief["elder_first_name"] == "Fatima"
    assert brief["lines"][0]["critical"] is True  # safety first
    assert client.get("/visits", headers=LEILA).json()[0]["state"] == "briefed"

    # -- second open serves from cache (same generated_at)
    again = client.get(f"/v/{token}").json()
    assert again["generated_at"] == brief["generated_at"]
    assert again["lines"] == brief["lines"]

    # -- a nursing visit for the same elder flips the brief
    nursing = _create_visit(client, "nursing_visit", "Jonathan Roy", "nurse")
    n_ids = [l["statement_id"] for l in client.get(f"/v/{nursing['token']}").json()["lines"]]
    assert 1 not in n_ids and 14 not in n_ids  # bathing-only rows gone
    assert 2 in n_ids and 8 in n_ids  # nursing rows present

    # -- worker checks out with a code already seen in the seed history -> proposal
    before = len(client.get("/proposals", headers=LEILA).json())
    r = client.post(
        f"/v/{token}/checkout",
        json={"completion": "partial", "observation_codes": ["agreed_then_declined"], "note_text": "Said yes, then no."},
    )
    assert r.status_code == 201, r.text
    assert r.json()["visit_state"] == "completed" and r.json()["proposal_created"] is True
    proposals = client.get("/proposals", headers=LEILA).json()
    assert len(proposals) == before + 1
    new_proposal = proposals[0]
    assert "polite" in new_proposal["suggested_statement"]

    # -- the token is burned: nothing further reachable
    assert client.get(f"/v/{token}").status_code == 404
    assert client.post(f"/v/{token}/checkout", json={"completion": "yes"}).status_code == 404
    visit = client.get(f"/visits/{created['visit']['id']}", headers=LEILA).json()
    assert visit["state"] == "completed" and visit["checkout"]["completion"] == "partial"

    # -- capacity_mode = assisted: caregiver cannot approve, elder can
    r = client.post(f"/proposals/{new_proposal['id']}/decide", headers=LEILA, json={"decision": "approve"})
    assert r.status_code == 403
    r = client.post(f"/proposals/{new_proposal['id']}/decide", headers=ELDER, json={"decision": "approve"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert r.json()["decided_by"] == "Fatima"

    # -- approval created a new active statement with source_checkout_id set
    mine = client.get("/me/statements", headers=ELDER).json()
    promoted = [s for s in mine if s["source_checkout_id"] == r.json()["source_checkout_id"] and s["status"] == "active"]
    assert len(promoted) == 1
    assert promoted[0]["statement"] == new_proposal["suggested_statement"]
    assert promoted[0]["applies_to_tasks"] == ["bathing"]

    # -- deciding twice is refused
    assert client.post(f"/proposals/{new_proposal['id']}/decide", headers=ELDER, json={"decision": "reject"}).status_code == 403

    # -- the elder's access log shows who looked
    log = client.get("/me/access-log", headers=ELDER).json()
    sentences = [row["sentence"] for row in log]
    assert any(s.startswith("Marie-Ève Tremblay was briefed on your bathing preferences") for s in sentences)
    assert any(s.startswith("Jonathan Roy was briefed on your nursing visit preferences") for s in sentences)
    assert any("approved a proposed statement" in s for s in sentences)
    assert any(s.startswith("Fatima viewed your preferences") for s in sentences)


def test_checkout_requires_brief_first_and_known_codes(fresh):
    created = _create_visit(fresh, "meal", "Marie-Ève Tremblay", "personal_support_worker")
    token = created["token"]
    assert fresh.post(f"/v/{token}/checkout", json={"completion": "yes"}).status_code == 409
    fresh.get(f"/v/{token}")
    r = fresh.post(f"/v/{token}/checkout", json={"completion": "yes", "observation_codes": ["made_up"]})
    assert r.status_code == 422
    r = fresh.post(f"/v/{token}/checkout", json={"completion": "yes", "observation_codes": ["good_day"]})
    assert r.status_code == 201 and r.json()["proposal_created"] is False


def test_visibility_toggle_hides_from_one_person_only(fresh):
    # Karim can see statement 5 today; the elder hides it from him
    assert 5 in {s["id"] for s in fresh.get("/statements", headers=KARIM).json()}
    r = fresh.patch("/me/statements/5/visibility", headers=ELDER, json={"hidden_from": [2]})
    assert r.status_code == 200 and r.json()["hidden_from"] == [2]
    assert 5 not in {s["id"] for s in fresh.get("/statements", headers=KARIM).json()}
    assert 5 in {s["id"] for s in fresh.get("/statements", headers=LEILA).json()}
    assert 5 in {s["id"] for s in fresh.get("/me/statements", headers=ELDER).json()}

    # ...and from the worker with a matching Person row
    created = _create_visit(fresh, "companionship", "Marie-Ève Tremblay", "personal_support_worker")
    fresh.patch("/me/statements/5/visibility", headers=ELDER, json={"hidden_from": [2, 3]})
    ids = {l["statement_id"] for l in fresh.get(f"/v/{created['token']}").json()["lines"]}
    assert 5 not in ids
    # hidden data never reaches the brief builder, so it is not in the cached brief either
    assert 5 not in {l["statement_id"] for l in fresh.get(f"/v/{created['token']}").json()["lines"]}


def test_caregiver_statement_crud(fresh):
    r = fresh.post(
        "/statements",
        headers=LEILA,
        json={"statement": "She likes the window open a crack at night.", "category": "routine", "applies_to_tasks": ["housekeeping"]},
    )
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    r = fresh.patch(f"/statements/{sid}", headers=LEILA, json={"status": "retired"})
    assert r.status_code == 200 and r.json()["status"] == "retired"
    assert sid not in {s["id"] for s in fresh.get("/statements", headers=LEILA).json()}
    assert sid in {s["id"] for s in fresh.get("/me/statements", headers=ELDER).json()}
    # bad time window
    r = fresh.post("/statements", headers=LEILA, json={"statement": "x y z", "category": "care", "time_start": "25:00", "time_end": "26:00"})
    assert r.status_code == 422
    r = fresh.post("/statements", headers=LEILA, json={"statement": "x y z", "category": "care", "time_start": "10:00"})
    assert r.status_code == 422


def test_expired_visit_shows_no_checkout(fresh):
    start = (datetime.now() - timedelta(days=1)).replace(microsecond=0)
    r = fresh.post(
        "/visits",
        headers=LEILA,
        json={"worker_name": "X", "worker_role": "nurse", "task_type": "nursing_visit",
              "scheduled_start": start.isoformat(), "scheduled_end": (start + timedelta(hours=1)).isoformat()},
    )
    token = r.json()["token"]
    assert fresh.get(f"/v/{token}").status_code == 410
    visit = fresh.get(f"/visits/{r.json()['visit']['id']}", headers=LEILA).json()
    assert visit["state"] == "expired" and visit["checkout"] is None
