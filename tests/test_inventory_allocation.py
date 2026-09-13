"""
Test Automated Inventory Stock Allocation on AI 'REDUCE' Approval (test_inventory_allocation.py)
Verifies:
1. auto_allocate_inventory() deducts from first available warehouse(s) with idle stock.
2. update_status route automatically detects AI 'REDUCE' decision and triggers auto_allocate_inventory().
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
    auto_allocate_inventory,
    upsert_inventory_item,
    get_inventory_item,
    create_purchase_request,
    get_db,
    COLLECTION_INVENTORY,
    COLLECTION_REQUESTS,
    COLLECTION_STOCK_MOVEMENTS,
)


class TestInventoryAllocation(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        self.test_sku = f"SKU-TEST-ALLOC-{int(datetime.now(timezone.utc).timestamp())}"
        self.test_pr_id = f"PR-TEST-ALLOC-{int(datetime.now(timezone.utc).timestamp())}"

        # Create a test SKU with multi-warehouse stock
        initial_inventory = {
            "sku": self.test_sku,
            "name": "High-Speed Ethernet Spool 1000ft",
            "category": "Networking",
            "unit_cost": 50.0,
            "reorder_threshold": 5,
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 10, "bin_shelf": "N-01"},
                "WH-EAST": {"location_name": "New York Hub", "stock": 15, "bin_shelf": "E-05"},
                "WH-WEST": {"location_name": "Seattle Hub", "stock": 0, "bin_shelf": "W-02"},
            },
        }
        upsert_inventory_item(self.test_sku, initial_inventory)

    def tearDown(self):
        # Clean up test documents in Firestore
        try:
            db = get_db()
            db.collection(COLLECTION_INVENTORY).document(self.test_sku).delete()
            db.collection(COLLECTION_REQUESTS).document(self.test_pr_id).delete()
            # Clean up any stock movements generated during allocation test
            movs = db.collection(COLLECTION_STOCK_MOVEMENTS).where("sku", "==", self.test_sku).stream()
            for m in movs:
                db.collection(COLLECTION_STOCK_MOVEMENTS).document(m.id).delete()
        except Exception as e:
            print(f"[tearDown] Cleanup note: {e}")

    def test_01_auto_allocate_inventory_directly(self):
        """Test auto_allocate_inventory() directly exhausts first warehouse and spills to second."""
        # Request 12 units -> Exhausts WH-NORTH (10) and takes 2 from WH-EAST (remaining 13)
        alloc_res = auto_allocate_inventory(self.test_sku, 12)
        self.assertEqual(alloc_res["quantity_allocated"], 12)
        self.assertEqual(alloc_res["new_total_stock"], 13)
        self.assertEqual(len(alloc_res["allocations"]), 2)

        # Verify in Firestore
        item_after = get_inventory_item(self.test_sku)
        whs = item_after["warehouses"]
        self.assertEqual(whs["WH-NORTH"]["stock"], 0)
        self.assertEqual(whs["WH-EAST"]["stock"], 13)

    def test_02_manager_approval_with_ai_reduce_triggers_allocation(self):
        """Test manager approval route detects AI REDUCE and triggers auto_allocate_inventory."""
        self.client.post("/api/auth/simulate-role", json={"role": "Procurement Director"})

        # Allocate 12 first so WH-NORTH has 0 and WH-EAST has 13
        auto_allocate_inventory(self.test_sku, 12)

        # Create PR requiring 5 units with AI REDUCE recommendation
        pr_data = {
            "request_id": self.test_pr_id,
            "title": "Need 5 Spools Ethernet Cable",
            "department": "Engineering",
            "requester_id": "USR-TEST-002",
            "requester_name": "Network Eng",
            "items": [
                {
                    "sku": self.test_sku,
                    "item_name": "High-Speed Ethernet Spool 1000ft",
                    "quantity": 5,
                    "unit_price": 50.0,
                    "total_price": 250.0,
                }
            ],
            "total_amount": 250.0,
            "status": "Action Required: Reduction Suggested",
            "ai_decision": {
                "Decision": "REDUCE",
                "Criticality_Score": 60,
                "Priority_Level": "MEDIUM",
                "Reasoning": "Internal idle stock available in New York Hub. Recommend internal warehouse transfer.",
                "Estimated_Savings": 250.0,
            },
        }
        create_purchase_request(pr_data)

        # Manager approves request via PATCH
        resp = self.client.patch(
            f"/api/procurement/requests/{self.test_pr_id}/status",
            json={
                "status": "approved",
                "actor_id": "Procurement Director",
                "comment": "Approved internal warehouse transfer as recommended by AI.",
            },
        )
        self.assertEqual(resp.status_code, 200)
        resp_json = resp.get_json()
        self.assertTrue(resp_json.get("success"))
        self.assertIn("inventory_action", resp_json)

        # Verify inventory deducted 5 more units from WH-EAST (13 - 5 = 8)
        item_final = get_inventory_item(self.test_sku)
        whs_final = item_final["warehouses"]
        self.assertEqual(whs_final["WH-EAST"]["stock"], 8)
        self.assertEqual(item_final["total_stock"], 8)


    def test_03_allocation_records_history(self):
        """Test auto_allocate_inventory() automatically creates a Stock_Movements audit record."""
        from app.services.firebase_db import get_inventory_history

        # Allocate 5 units from WH-NORTH
        auto_allocate_inventory(
            self.test_sku, 
            5, 
            actor="AI-Procurement-Agent", 
            reference_id="PR-TEST-AUDIT-999", 
            notes="Automated internal fulfillment test"
        )

        # Retrieve history for test_sku
        history = get_inventory_history(sku=self.test_sku, limit=10)
        self.assertGreaterEqual(len(history), 1)

        allocation_records = [
            h for h in history if h.get("movement_type") == "auto_allocation"
        ]
        self.assertGreaterEqual(len(allocation_records), 1)
        rec = allocation_records[0]
        self.assertEqual(rec["sku"], self.test_sku)
        self.assertEqual(rec["initiated_by"], "AI-Procurement-Agent")
        self.assertEqual(rec["reference_id"], "PR-TEST-AUDIT-999")
        self.assertEqual(rec["quantity_delta"], -5)

    def test_04_inventory_history_and_analytics_endpoints(self):
        """Test GET /api/inventory/analytics and GET /api/inventory/history REST endpoints."""
        # 1. Test Analytics Endpoint
        resp_an = self.client.get("/api/inventory/analytics")
        self.assertEqual(resp_an.status_code, 200)
        data_an = resp_an.get_json()
        self.assertTrue(data_an.get("success"))
        self.assertIn("data", data_an)

        analytics = data_an["data"]
        self.assertIn("summary", analytics)
        self.assertIn("warehouses", analytics)
        self.assertIn("categories", analytics)
        self.assertIn("top_assets", analytics)
        self.assertGreater(analytics["summary"]["total_skus"], 0)
        self.assertGreater(analytics["summary"]["total_asset_value"], 0)

        # 2. Test General History Endpoint
        resp_hist = self.client.get("/api/inventory/history?limit=10")
        self.assertEqual(resp_hist.status_code, 200)
        data_hist = resp_hist.get_json()
        self.assertTrue(data_hist.get("success"))
        self.assertIsInstance(data_hist.get("data"), list)

        # 3. Test SKU-specific History Endpoint
        resp_sku_hist = self.client.get(f"/api/inventory/{self.test_sku}/history")
        self.assertEqual(resp_sku_hist.status_code, 200)
        data_sku_hist = resp_sku_hist.get_json()
        self.assertTrue(data_sku_hist.get("success"))
        self.assertIsInstance(data_sku_hist.get("data"), list)


if __name__ == "__main__":
    unittest.main()

