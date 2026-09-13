"""
Automated Integration Tests for Enterprise Authentication (test_auth_routes.py)
Tests login page rendering, session protection decorators (@login_required),
one-click role simulations, and token verification endpoints.
"""

import os
import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class AuthWorkflowTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.app.config["SECRET_KEY"] = "test-auth-secret-key-2026"
        self.client = self.app.test_client()
        self.test_emails = [
            "qa_test_reg_runner@procureai.enterprise",
            "login_test@procureai.enterprise",
            "alex.morgan@company.com",
        ]

    def tearDown(self):
        try:
            from app.services.firebase_init import get_db
            db = get_db()
            test_emails_set = {e.lower() for e in self.test_emails}
            for doc in db.collection("Users").stream():
                email = (doc.to_dict().get("email") or "").strip().lower()
                if email in test_emails_set:
                    db.collection("Users").document(doc.id).delete()
        except Exception as e:
            print(f"[tearDown] Auth test cleanup note: {e}")

    def test_01_login_page_renders_successfully(self):
        """Verify GET /login returns 200 and includes branding, pipeline, and auth elements."""
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")
        self.assertIn("AI-Powered Purchase Request", html)
        self.assertIn("Data Cleaning", html)
        self.assertIn("Budget Check", html)
        self.assertIn("Inventory Check", html)
        self.assertIn("Usage Analysis", html)
        self.assertIn("Continue with Google", html)
        self.assertIn("ONE-CLICK ROLE SIMULATION", html)
        self.assertIn("Procurement Director", html)
        self.assertIn("Requester", html)

    def test_02_unauthenticated_browser_redirected_to_login(self):
        """Verify accessing protected browser pages without session redirects to /login."""
        resp = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers.get("Location", ""))

        resp_submit = self.client.get("/submit-request", follow_redirects=False)
        self.assertEqual(resp_submit.status_code, 302)
        self.assertIn("/login", resp_submit.headers.get("Location", ""))

    def test_03_unauthenticated_api_request_returns_401(self):
        """Verify accessing protected REST API endpoints without session returns 401 JSON."""
        resp = self.client.get("/api/procurement/requests", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "UNAUTHORIZED")

    def test_04_role_simulation_director(self):
        """Verify one-click role simulation for 'Procurement Director' activates session."""
        resp = self.client.post("/api/auth/simulate-role", json={"role": "Procurement Director"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("role"), "Procurement Director")

        # Verify session is now active by accessing protected /dashboard
        dash_resp = self.client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 200)

        # Verify /api/auth/me returns active session details
        me_resp = self.client.get("/api/auth/me")
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.get_json()
        self.assertTrue(me_data.get("authenticated"))
        self.assertEqual(me_data.get("user", {}).get("role"), "Procurement Director")

    def test_05_role_simulation_requester(self):
        """Verify one-click role simulation for 'Requester' activates session."""
        resp = self.client.post("/api/auth/simulate-role", json={"role": "Requester"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("role"), "Requester")

        # Verify user can access submit-request page
        sub_resp = self.client.get("/submit-request")
        self.assertEqual(sub_resp.status_code, 200)

    def test_06_logout_clears_session(self):
        """Verify GET /logout clears session and redirects to /login."""
        # First simulate login
        self.client.post("/api/auth/simulate-role", json={"role": "Procurement Director"})

        # Verify authenticated
        me_before = self.client.get("/api/auth/me").get_json()
        self.assertTrue(me_before.get("authenticated"))

        # Logout
        logout_resp = self.client.get("/logout", follow_redirects=False)
        self.assertEqual(logout_resp.status_code, 302)
        self.assertIn("/login", logout_resp.headers.get("Location", ""))

        # Verify no longer authenticated
        me_after = self.client.get("/api/auth/me").get_json()
        self.assertFalse(me_after.get("authenticated"))

    def test_07_api_login_validation(self):
        """Verify /api/login handles missing or invalid tokens cleanly."""
        # Missing token
        resp_missing = self.client.post("/api/login", json={})
        self.assertEqual(resp_missing.status_code, 400)
        self.assertFalse(resp_missing.get_json().get("success"))

        # Invalid token
        resp_invalid = self.client.post("/api/login", json={"id_token": "invalid.jwt.token.string"})
        self.assertEqual(resp_invalid.status_code, 401)
        self.assertFalse(resp_invalid.get_json().get("success"))

    def test_08_register_user_creates_account_and_session(self):
        """Verify POST /api/auth/register creates account, hashes credentials, and starts session."""
        reg_payload = {
            "email": "qa_test_reg_runner@procureai.enterprise",
            "password": "Password123!",
            "full_name": "QA Test Specialist",
            "role": "Procurement Director"
        }
        resp = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("email"), "qa_test_reg_runner@procureai.enterprise")
        self.assertEqual(data.get("user", {}).get("name"), "QA Test Specialist")

        # Verify access to dashboard with new session
        dash_resp = self.client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 200)

    def test_09_login_with_password(self):
        """Verify POST /api/auth/login-password authenticates user successfully."""
        # First register/seed user
        self.client.post("/api/auth/register", json={
            "email": "login_test@procureai.enterprise",
            "password": "SecurePassword999!",
            "full_name": "Test Login User"
        })
        # Clear session
        self.client.get("/logout")

        # Now login
        login_payload = {
            "email": "login_test@procureai.enterprise",
            "password": "SecurePassword999!"
        }
        resp = self.client.post("/api/auth/login-password", json=login_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("name"), "Test Login User")

        # Wrong password
        wrong_resp = self.client.post("/api/auth/login-password", json={
            "email": "login_test@procureai.enterprise",
            "password": "WrongPassword!"
        })
        self.assertEqual(wrong_resp.status_code, 401)
        self.assertFalse(wrong_resp.get_json().get("success"))

    def test_10_google_sso(self):
        """Verify POST /api/auth/google-sso establishes corporate session."""
        resp = self.client.post("/api/auth/google-sso", json={
            "email": "alex.morgan@company.com",
            "name": "Alex Morgan"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("user", {}).get("email"), "alex.morgan@company.com")

        # Check authenticated session
        dash_resp = self.client.get("/dashboard")
        self.assertEqual(dash_resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
