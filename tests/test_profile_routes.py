"""
Unit Tests for Manager Profile Management & Customization (test_profile_routes.py)
Tests access control, Firestore persistence, and live session synchronization.
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


class TestProfileRoutes(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            from app.services.firebase_init import get_db
            db = get_db()
            for uid in ["USR-TEST-MGR-01", "USR-TEST-MGR-02", "USR-TEST-MGR-03", "USR-TEST-MGR-04"]:
                doc_ref = db.collection("Users").document(uid)
                if doc_ref.get().exists:
                    doc_ref.delete()
        except Exception as e:
            print(f"[tearDown] Profile cleanup note: {e}")

    def test_profile_page_unauthenticated_redirect(self):
        """Test that unauthenticated access to /profile redirects to /login."""
        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_profile_page_authenticated_success(self):
        """Test that an authenticated user can access the profile management screen."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "USR-TEST-MGR-01"
            sess["user_email"] = "manager@procureai.enterprise"
            sess["user_name"] = "Alex Morgan"
            sess["user_role"] = "Procurement Director"
            sess["user_initials"] = "AM"
            sess["user_department"] = "Supply Chain & Procurement"

        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 200)
        content = response.data.decode("utf-8")
        self.assertIn("Manager Profile & Authority Center", content)
        self.assertIn("Alex Morgan", content)

    def test_api_get_profile_unauthenticated(self):
        """Test that unauthenticated API call returns 401."""
        response = self.client.get("/api/user/profile")
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_api_get_profile_authenticated(self):
        """Test fetching profile details via GET /api/user/profile."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "USR-TEST-MGR-02"
            sess["user_email"] = "director.ops@procureai.enterprise"
            sess["user_name"] = "Sarah Jenkins"
            sess["user_role"] = "Procurement Director"
            sess["user_initials"] = "SJ"
            sess["user_department"] = "Operations"

        response = self.client.get("/api/user/profile")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["user_id"], "USR-TEST-MGR-02")
        self.assertEqual(data["data"]["name"], "Sarah Jenkins")

    def test_api_update_profile_success_and_session_sync(self):
        """Test modifying profile fields via PATCH /api/user/profile and verifying session sync."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "USR-TEST-MGR-03"
            sess["user_email"] = "custom.mgr@procureai.enterprise"
            sess["user_name"] = "Old Manager Name"
            sess["user_role"] = "Procurement Director"
            sess["user_initials"] = "OM"
            sess["user_department"] = "Engineering"

        update_payload = {
            "name": "Marcus Vance Executive",
            "job_title": "Global Procurement Director",
            "department": "Finance",
            "phone": "+1 (555) 999-8888",
            "office_location": "Building A, Floor 5",
            "bio": "Leading financial compliance and multi-warehouse optimization.",
            "spending_limit": 75000.0,
            "preferred_warehouse": "NORTH",
            "ai_autopilot_enabled": True
        }

        response = self.client.patch(
            "/api/user/profile",
            json=update_payload,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["name"], "Marcus Vance Executive")
        self.assertEqual(data["data"]["initials"], "MV")
        self.assertEqual(data["data"]["department"], "Finance")

        # Verify Flask session was synchronized
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_name"), "Marcus Vance Executive")
            self.assertEqual(sess.get("user_initials"), "MV")
            self.assertEqual(sess.get("user_department"), "Finance")

    def test_api_update_profile_empty_payload(self):
        """Test submitting empty payload returns 400 error."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "USR-TEST-MGR-04"

        response = self.client.patch(
            "/api/user/profile",
            json={},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])


if __name__ == "__main__":
    unittest.main()
