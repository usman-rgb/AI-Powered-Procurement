"""
Test Budget Commitment and Rollback Workflow (test_budget_workflow.py)
Verifies:
1. Dynamic budget ID calculation using datetime.
2. Manager approval commits funds to the department's budget in Firestore.
3. Subsequent rejection rolls back (refunds) the funds to the budget.
"""

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.services.firebase_db import (
    get_dynamic_budget_id,
    get_budget,
    create_purchase_request,
    get_db,
    COLLECTION_REQUESTS,
)


class TestBudgetWorkflow(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.created_pr_ids = []

    def tearDown(self):
        # Clean up any created test purchase requests
        if self.created_pr_ids:
            try:
                db = get_db()
                for pr_id in self.created_pr_ids:
                    db.collection(COLLECTION_REQUESTS).document(pr_id).delete()
            except Exception as e:
                print(f"[tearDown] Cleanup note: {e}")

    def test_01_dynamic_budget_id_calculation(self):
        """Test get_dynamic_budget_id calculates correct quarter and year codes."""
        current_q_budget = get_dynamic_budget_id("Engineering")
        self.assertEqual(current_q_budget, "BUD-ENG-2026-Q3")

        q1_test = get_dynamic_budget_id("IT", datetime(2026, 1, 15, tzinfo=timezone.utc))
        self.assertEqual(q1_test, "BUD-IT-2026-Q1")

        q4_test = get_dynamic_budget_id("Operations", datetime(2026, 11, 25, tzinfo=timezone.utc))
        self.assertEqual(q4_test, "BUD-OPS-2026-Q4")

    def test_02_budget_approval_and_rollback_workflow(self):
        """Test approval commits budget funds and subsequent rejection rolls back funds."""
        self.client.post("/api/auth/simulate-role", json={"role": "Procurement Director"})

        budget_id = "BUD-ENG-2026-Q3"
        budget_before = get_budget(budget_id)
        if not budget_before:
            self.skipTest(f"Budget '{budget_id}' not found in Firestore.")

        committed_initial = float(budget_before.get("committed_amount", 0.0))
        remaining_initial = float(budget_before.get("remaining_amount", 0.0))

        test_amount = 250.00
        test_pr_id = f"PR-TEST-BUDGET-{int(datetime.now(timezone.utc).timestamp())}"
        self.created_pr_ids.append(test_pr_id)

        test_pr_data = {
            "request_id": test_pr_id,
            "title": "Automated QA Budget Test Item",
            "department": "Engineering",
            "requester_id": "USR-TEST",
            "requester_name": "QA Robot",
            "items": [
                {
                    "sku": "SKU-QA-TEST-001",
                    "item_name": "QA Test Component",
                    "quantity": 1,
                    "unit_price": test_amount,
                    "total_price": test_amount,
                }
            ],
            "total_amount": test_amount,
            "status": "submitted",
        }
        create_purchase_request(test_pr_data)

        # 1. Trigger manager approval
        patch_resp = self.client.patch(
            f"/api/procurement/requests/{test_pr_id}/status",
            json={
                "status": "approved",
                "actor_id": "QA Manager",
                "comment": "Approved during automated budget verification test.",
            },
        )
        self.assertEqual(patch_resp.status_code, 200)
        resp_json = patch_resp.get_json()
        self.assertTrue(resp_json.get("success"))

        # Verify budget committed
        budget_after_approve = get_budget(budget_id)
        committed_after_approve = float(budget_after_approve.get("committed_amount", 0.0))
        remaining_after_approve = float(budget_after_approve.get("remaining_amount", 0.0))

        expected_committed = committed_initial + test_amount
        expected_remaining = remaining_initial - test_amount
        self.assertAlmostEqual(committed_after_approve, expected_committed, places=2)
        self.assertAlmostEqual(remaining_after_approve, expected_remaining, places=2)

        # 2. Trigger manager rejection & rollback
        reject_resp = self.client.patch(
            f"/api/procurement/requests/{test_pr_id}/status",
            json={
                "status": "rejected",
                "actor_id": "QA Manager",
                "comment": "Rejection test to verify rollback of committed funds.",
            },
        )
        self.assertEqual(reject_resp.status_code, 200)
        reject_json = reject_resp.get_json()
        self.assertTrue(reject_json.get("success"))

        # Verify rollback
        budget_after_reject = get_budget(budget_id)
        committed_after_reject = float(budget_after_reject.get("committed_amount", 0.0))
        remaining_after_reject = float(budget_after_reject.get("remaining_amount", 0.0))

        self.assertAlmostEqual(committed_after_reject, committed_initial, places=2)
        self.assertAlmostEqual(remaining_after_reject, remaining_initial, places=2)


if __name__ == "__main__":
    unittest.main()
