"""End-to-end tests over the guide's contract: the routes, the resolver, the
fold-back rules, and the no-hallucination guard.

    python -m unittest discover tests
"""

import re
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import config, seed  # noqa: E402
from app.ai import validator  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Actor, Familiarity, Purpose, Statement  # noqa: E402
from app.repositories import checkouts, proposals, statements, visits, workers  # noqa: E402
from app.routes.elder import format_access_sentence  # noqa: E402
from app.services import brief, familiarity, foldback, tokens, visibility  # noqa: E402

ELDER = 1


def _slot(minutes_ahead=10, length=60):
    now = datetime.now().replace(second=0, microsecond=0)
    start = now + timedelta(minutes=minutes_ahead)
    return start.strftime("%Y-%m-%dT%H:%M"), (start + timedelta(minutes=length)).strftime("%Y-%m-%dT%H:%M")


class CareCircleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        """Every test starts from the seeded record. Check-outs slide the pattern
        window and corrections add statements, so shared state makes the
        seed-invariant assertions order-dependent."""
        seed.seed(force=True)

    # --- pages load -----------------------------------------------------------

    def test_health(self):
        self.assertEqual(self.client.get("/health").json(), {"ok": True})

    def test_every_page_renders(self):
        for path in ["/", "/caregiver/record", "/caregiver/visits", "/caregiver/proposals",
                     "/elder", "/elder/access-log", "/elder/proposals"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    # --- the seed is the demo -------------------------------------------------

    def test_seed_supports_the_continuity_counter(self):
        self.assertEqual(statements.count_active(ELDER), 30)
        self.assertEqual(workers.count_contributing_workers(ELDER), 6)

    def test_seed_leaves_room_for_the_pattern_to_fire_live(self):
        """Two occurrences seeded; the third happens on stage."""
        seen = checkouts.count_code_occurrences(ELDER, "refused_equipment", config.PATTERN_WINDOW)
        self.assertEqual(seen, config.PATTERN_THRESHOLD - 1)

    # --- the resolver ---------------------------------------------------------

    def test_resolver_hides_from_the_named_person_but_never_from_the_elder(self):
        hidden = [s for s in statements.list_statements(ELDER) if s.hidden_from]
        self.assertTrue(hidden, "seed must include hidden statements")
        target = hidden[0]
        person_id = target.hidden_from[0]

        as_person = visibility.resolve(ELDER, Actor("person", person_id, "Karim"), Purpose())
        self.assertNotIn(target.id, {s.id for s in as_person})

        as_elder = visibility.resolve(ELDER, Actor("elder", None, "Amina"), Purpose())
        self.assertIn(target.id, {s.id for s in as_elder})

    def test_resolver_scopes_by_task(self):
        rows = visibility.resolve(ELDER, Actor("worker", None, "W"), Purpose(task_type="transport"))
        for s in rows:
            self.assertFalse(s.applies_to_tasks and "transport" not in s.applies_to_tasks)

    def test_resolver_always_logs(self):
        from app.repositories import access_log
        before = len(access_log.list_access(ELDER, limit=500))
        visibility.resolve(ELDER, Actor("worker", None, "Nour"), Purpose(task_type="bathing"))
        self.assertEqual(len(access_log.list_access(ELDER, limit=500)), before + 1)

    def test_access_sentence_reads_like_a_sentence(self):
        from app.models import AccessEntry
        at = datetime.now().replace(hour=9, minute=52).isoformat()
        entry = AccessEntry(1, ELDER, "Marie-Ève", "brief", "your bathing preferences", at)
        self.assertEqual(format_access_sentence(entry),
                         "Marie-Ève viewed your bathing preferences at 9:52 am today")

    # --- the brief ------------------------------------------------------------

    def test_first_visit_brief_puts_corrections_first(self):
        start, end = _slot()
        wid = workers.create_worker("Nour Haddad", "care worker", "fr")
        vid = visits.create_visit(ELDER, wid, "bathing", start, end)
        result = brief.build_brief(vid, force=True)

        self.assertTrue(result.is_first_visit)
        self.assertEqual(result.note_count, statements.count_active(ELDER))
        self.assertEqual(result.contributor_count, 6)
        self.assertTrue(result.lines)
        self.assertTrue(result.lines[0].is_correction)
        self.assertLessEqual(len(result.lines), config.MAX_BRIEF_LINES)

    def test_returning_worker_gets_a_delta_not_the_whole_record(self):
        start, end = _slot()
        vid = visits.create_visit(ELDER, 1, "bathing", start, end)  # Marie-Ève has visited
        result = brief.build_brief(vid, force=True)
        self.assertFalse(result.is_first_visit)
        self.assertLess(result.changed_count, statements.count_active(ELDER))

    def test_returning_worker_with_nothing_changed_gets_zero_lines(self):
        """A valid, correct brief. It must not fall through to the full list."""
        rows = statements.list_statements(ELDER)
        fam = Familiarity(visit_count=4, last_visit_at=datetime.now().isoformat(), is_first_visit=False)
        self.assertEqual(familiarity.changed_since(rows, fam.last_visit_at), set())

    def test_changed_since_returns_everything_when_there_is_no_last_visit(self):
        rows = statements.list_statements(ELDER)
        self.assertEqual(familiarity.changed_since(rows, None), {s.id for s in rows})

    # --- the no-hallucination guard ------------------------------------------

    def _statement(self, sid, source="family"):
        return Statement(id=sid, elder_id=ELDER, statement="Seeded text.", kind="preference",
                         category="care", source=source, created_at="a", updated_at="a")

    def test_validator_drops_ids_outside_the_candidate_set(self):
        by_id = {1: self._statement(1)}
        lines = validator.validate_lines(
            [{"statement_id": 999, "text": "She is diabetic."}, {"statement_id": 1, "text": "Fine."}],
            set(by_id), by_id)
        self.assertEqual([l.statement_id for l in lines], [1])

    def test_validator_never_raises_and_never_repairs(self):
        by_id = {1: self._statement(1)}
        junk = ["not a dict", {"text": "no id"}, {"statement_id": "1", "text": "wrong type"},
                {"statement_id": 1, "text": ""}, {"statement_id": 1, "text": "x" * 200}]
        self.assertEqual(validator.validate_lines(junk, set(by_id), by_id), [])

    def test_the_model_cannot_demote_a_correction(self):
        by_id = {1: self._statement(1, source="correction")}
        line = validator.validate_lines([{"statement_id": 1, "text": "Ok.", "critical": False}],
                                        set(by_id), by_id)[0]
        self.assertTrue(line.critical)
        self.assertTrue(line.is_correction)

    # --- tokens ---------------------------------------------------------------

    def test_only_the_hash_is_stored_and_the_token_burns_on_checkout(self):
        start, end = _slot()
        page = self.client.post("/caregiver/visits", data={
            "task_type": "meal", "scheduled_start": start, "scheduled_end": end, "worker_id": "2"})
        raw = re.search(r"/v/([A-Za-z0-9_-]{20,})", page.text).group(1)

        visit = tokens.validate(raw)
        self.assertIsNotNone(visit)
        self.assertNotEqual(visit.token_hash, raw)

        self.assertEqual(self.client.get(f"/v/{raw}").status_code, 200)
        self.client.post(f"/v/{raw}/checkout", data={"completion": "yes", "handover_note": ""})
        self.assertIsNone(tokens.validate(raw))
        self.assertIn("expired", self.client.get(f"/v/{raw}").text.lower())

    def test_an_unknown_token_looks_exactly_like_an_expired_one(self):
        res = self.client.get("/v/never-issued-at-all")
        self.assertEqual(res.status_code, 200)
        self.assertIn("This link has expired.", res.text)

    # --- fold-back ------------------------------------------------------------

    def test_handover_note_becomes_a_proposal(self):
        start, end = _slot()
        vid = visits.create_visit(ELDER, 3, "meal", start, end)
        cid = checkouts.create_checkout(vid, "yes", [], None, "Warm the plate first. She eats more.")
        pid = foldback.from_handover_note(cid)
        self.assertIsNotNone(pid)
        self.assertEqual(proposals.get_proposal(pid).origin_kind, "handover")
        self.assertIsNone(foldback.from_handover_note(cid), "duplicate guard")

    def test_the_third_occurrence_fires_a_pattern_proposal(self):
        start, end = _slot()
        vid = visits.create_visit(ELDER, 4, "bathing", start, end)
        cid = checkouts.create_checkout(vid, "partial", ["refused_equipment"], None, None)
        created = foldback.from_observation_patterns(cid)
        self.assertEqual(len(created), 1)
        self.assertEqual(proposals.get_proposal(created[0]).origin_kind, "pattern")

    def test_a_correction_skips_the_queue(self):
        pending_before = len(proposals.list_pending(ELDER))
        sid = foldback.from_correction(ELDER, 1, "Never use the side door.", "Leila")
        self.assertEqual(statements.get_statement(sid).source, "correction")
        self.assertEqual(statements.get_statement(sid).status, "active")
        self.assertEqual(len(proposals.list_pending(ELDER)), pending_before)

    def test_approving_a_proposal_creates_a_statement(self):
        pid = proposals.create_proposal(ELDER, None, "handover", "approach", "Leave the lamp on.")
        before = statements.count_active(ELDER)
        sid = foldback.approve_proposal(pid, "Leila")
        self.assertEqual(statements.count_active(ELDER), before + 1)
        self.assertEqual(statements.get_statement(sid).source, "worker")
        self.assertEqual(proposals.get_proposal(pid).status, "accepted")

    # --- forms ----------------------------------------------------------------

    def test_visibility_stores_the_negative_of_what_the_form_shows(self):
        self.client.post("/elder/statements/1/visibility", data={"visible_to": ["1", "3"]})
        self.assertEqual(statements.get_statement(1).hidden_from, [2, 4])

    def test_a_worker_cannot_invent_an_observation_code(self):
        start, end = _slot()
        page = self.client.post("/caregiver/visits", data={
            "task_type": "dressing", "scheduled_start": start, "scheduled_end": end, "worker_id": "5"})
        raw = re.search(r"/v/([A-Za-z0-9_-]{20,})", page.text).group(1)
        visit = tokens.validate(raw)
        self.client.get(f"/v/{raw}")
        self.client.post(f"/v/{raw}/checkout", data={
            "completion": "yes", "observation_codes": ["ate_well", "invented_by_the_worker"]})
        self.assertEqual(checkouts.get_checkout_for_visit(visit.id).observation_codes, ["ate_well"])


if __name__ == "__main__":
    unittest.main()
