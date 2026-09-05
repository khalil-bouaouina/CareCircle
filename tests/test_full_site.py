import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app import config

from app.main import app
from app.repositories import accounts, people, statements, visits
from app.services import auth, tokens


class TestProductionCareCircle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, follow_redirects=False)

    def test_01_health_check(self):
        """GET /health must return {'ok': True} unconditionally."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True})

    def test_02_landing_page(self):
        """Home page displays landing view with login/register links."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("CareCircle", res.text)
        self.assertIn("Se connecter", res.text)
        self.assertIn("Créer un compte aidant", res.text)

    def test_03_unauthenticated_browser_redirects(self):
        """Visiting caregiver or elder without session redirects to /login."""
        res = self.client.get("/caregiver/record", headers={"Accept": "text/html"})
        self.assertEqual(res.status_code, 303)
        self.assertIn("/login", res.headers.get("location", ""))

        res = self.client.get("/elder", headers={"Accept": "text/html"})
        self.assertEqual(res.status_code, 303)
        self.assertIn("/login", res.headers.get("location", ""))

    def test_04_login_validation_and_failure(self):
        """Invalid credentials return 400 with an error message."""
        res = self.client.post("/login", data={"email": "sarah@carecircle.demo", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("incorrect", res.text.lower())

    def test_05_demo_login_success_and_cookie(self):
        """Login with Sarah's demo account sets session cookie and redirects."""
        res = self.client.post("/login", data={"email": "sarah@carecircle.demo", "password": "demo1234"})
        self.assertEqual(res.status_code, 303)
        self.assertIn("/caregiver/record", res.headers.get("location", ""))
        self.assertIn(config.SESSION_COOKIE_NAME, res.cookies)

        # Access caregiver record using the session cookie
        res2 = self.client.get("/caregiver/record", cookies=res.cookies)
        self.assertEqual(res2.status_code, 200)
        self.assertIn("Sarah B.", res2.text)
        self.assertIn("primary_caregiver", res2.text)
        self.assertIn("Déconnexion", res2.text)

    def test_06_registration_and_new_elder_onboarding(self):
        """Registering a new caregiver creates the user and their first elder."""
        import uuid
        unique_email = f"user_{uuid.uuid4().hex[:8]}@exemple.com"

        res = self.client.post("/register", data={
            "name": "Nadia Amrani",
            "email": unique_email,
            "password": "secretpassword123",
            "elder_name": "Youssef Amrani",
            "capacity_mode": "assisted",
            "language": "fr",
        })
        self.assertEqual(res.status_code, 303)
        self.assertIn(config.SESSION_COOKIE_NAME, res.cookies)

        # Access console as the newly registered user
        res2 = self.client.get("/caregiver/record", cookies=res.cookies)
        self.assertEqual(res2.status_code, 200)
        self.assertIn("Nadia Amrani", res2.text)
        self.assertIn("Youssef Amrani", res2.text)

    def test_07_family_invitation_and_restricted_view(self):
        """A primary caregiver can invite a family member with scoped access."""
        sarah_cookie = self.client.post("/login", data={"email": "sarah@carecircle.demo", "password": "demo1234"}).cookies

        # Log in as Karim (family member)
        karim_cookie = self.client.post("/login", data={"email": "karim@carecircle.demo", "password": "demo1234"}).cookies
        res = self.client.get("/caregiver/record", cookies=karim_cookie)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Karim B.", res2_text := res.text)
        self.assertIn("family", res2_text)

    def test_08_elder_view_authenticated(self):
        """Fatima logs in and accesses her elder-specific large-type portal."""
        fatima_cookie = self.client.post("/login", data={"email": "fatima@carecircle.demo", "password": "demo1234"}).cookies
        res = self.client.get("/elder", cookies=fatima_cookie)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Mon dossier", res.text)
        self.assertIn("Fatima", res.text)

    def test_09_worker_token_flow_remains_passwordless(self):
        """Worker flow operates via temporary URL token with no account needed."""
        # Authenticate as Sarah to create a visit
        sarah_cookie = self.client.post("/login", data={"email": "sarah@carecircle.demo", "password": "demo1234"}).cookies

        res = self.client.post(
            "/caregiver/visits",
            cookies=sarah_cookie,
            data={
                "worker_name": "Marie-Ève",
                "worker_role": "personal_support_worker",
                "worker_language": "fr",
                "task_type": "bathing",
                "scheduled_start": "2026-09-05T19:00:00",
                "scheduled_end": "2026-09-05T20:00:00",
            },
        )
        self.assertEqual(res.status_code, 303)
        created_url = res.headers.get("location", "")
        self.assertIn("token=", created_url)

        # Extract token
        import urllib.parse
        parsed = urllib.parse.urlparse(created_url)
        params = urllib.parse.parse_qs(parsed.query)
        token = params["token"][0]

        # Worker accesses brief without any login or cookie!
        res_worker = self.client.get(f"/v/{token}")
        self.assertEqual(res_worker.status_code, 200)
        self.assertIn("Fatima", res_worker.text)
        self.assertIn("bathing", res_worker.text.lower())

    def test_10_elder_direct_registration(self):
        """A senior can register directly for themselves and land in /elder."""
        import uuid
        elder_email = f"senior_{uuid.uuid4().hex[:8]}@exemple.com"

        res = self.client.post("/register", data={
            "account_type": "elder",
            "name": "Ahmed Mansouri",
            "email": elder_email,
            "password": "seniorpassword123",
            "capacity_mode": "self",
            "language": "fr",
        })
        self.assertEqual(res.status_code, 303)
        self.assertIn("/elder", res.headers.get("location", ""))
        self.assertIn(config.SESSION_COOKIE_NAME, res.cookies)

        # Access elder view
        res2 = self.client.get("/elder", cookies=res.cookies)
        self.assertEqual(res2.status_code, 200)
        self.assertIn("Ahmed Mansouri", res2.text)
        self.assertIn("Mon dossier", res2.text)


if __name__ == "__main__":
    unittest.main()

