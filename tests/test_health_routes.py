"""
Unit and Integration Tests for System Health and Diagnostic Routes (test_health_routes.py)
Uses Flask test_client to verify HTML and JSON responses without requiring an external server.
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


class HealthRoutesTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        self.app = create_app("testing")
        self.client = self.app.test_client()

    def test_01_system_health_html(self):
        """Test GET /system-health returns 200 HTML page."""
        resp = self.client.get("/system-health")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"System Health", resp.data)

    def test_02_api_health_browser_html(self):
        """Test GET /api/health with browser Accept header renders diagnostic HTML."""
        resp = self.client.get("/api/health", headers={"Accept": "text/html,application/xhtml+xml"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"System Health", resp.data)

    def test_03_api_health_json(self):
        """Test GET /api/health?format=json returns JSON status."""
        resp = self.client.get("/api/health?format=json")
        self.assertIn(resp.status_code, (200, 503))
        data = resp.get_json()
        self.assertIn("status", data)
        self.assertIn("firebase_connected", data)


if __name__ == "__main__":
    unittest.main()
