"""
Unit Tests for Manual Inventory Management Module (test_inventory_management.py)
Tests access control, REST API endpoints (GET, POST, PUT), and stock calculations.
"""

import os
import sys
import unittest
import uuid
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


class TestInventoryManagement(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.created_skus = []

    def tearDown(self):
        if hasattr(self, "created_skus") and self.created_skus:
            try:
                from app.services.firebase_init import get_db
                db = get_db()
                for sku in self.created_skus:
                    db.collection("Inventory").document(sku).delete()
                    # Clean up any movements created for this sku
                    mov_docs = db.collection("Stock_Movements").where("sku", "==", sku).stream()
                    for m in mov_docs:
                        db.collection("Stock_Movements").document(m.id).delete()
            except Exception as e:
                print(f"[tearDown] Inventory cleanup note: {e}")

    def test_inventory_page_unauthenticated_redirect(self):
        """Test that unauthenticated access to /inventory redirects to /login."""
        response = self.client.get("/inventory")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_inventory_page_authenticated_success(self):
        """Test that an authenticated user can view the inventory management page."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "USR-MGR-TEST"
            sess["user_email"] = "manager@procureai.enterprise"
            sess["user_name"] = "Inventory Director"
            sess["user_role"] = "Procurement Director"

        response = self.client.get("/inventory")
        self.assertEqual(response.status_code, 200)
        content = response.data.decode("utf-8")
        self.assertIn("Manual Inventory Management & Warehouse Stock", content)
        self.assertIn("Warehouse Inventory Catalog", content)
        self.assertIn("Register New Inventory Item", content)
        self.assertIn("Manual Stock Adjustment", content)

    def test_api_get_inventory_success(self):
        """Test GET /api/inventory returns JSON list with success: True."""
        response = self.client.get("/api/inventory")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

    def test_api_post_inventory_item_success_and_total_calculation(self):
        """Test POST /api/inventory creates item, sets warehouses, and computes total_stock."""
        unique_sku = f"SKU-TEST-{uuid.uuid4().hex[:6].upper()}"
        self.created_skus.append(unique_sku)
        payload = {
            "sku": unique_sku,
            "name": "Automated Testing Drone Model X",
            "category": "Hardware",
            "unit_cost": 850.00,
            "reorder_threshold": 15,
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 10, "bin_shelf": "D-01"},
                "WH-WEST": {"location_name": "Seattle Hub", "stock": 25, "bin_shelf": "D-02"},
                "WH-EAST": {"location_name": "New York Hub", "stock": 15, "bin_shelf": "D-03"}
            }
        }

        response = self.client.post("/api/inventory", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        created = data.get("data")
        self.assertEqual(created["sku"], unique_sku)
        self.assertEqual(created["name"], "Automated Testing Drone Model X")
        # 10 + 25 + 15 = 50 total units
        self.assertEqual(created["total_stock"], 50)

    def test_api_post_inventory_item_validation_error(self):
        """Test POST /api/inventory fails with 400 when required fields are missing."""
        # Missing SKU and Name
        response = self.client.post("/api/inventory", json={"category": "Hardware"})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("required", data.get("error", "").lower())

    def test_api_put_inventory_item_success(self):
        """Test PUT /api/inventory/<sku> adjusts stock quantities and recalculates total_stock."""
        unique_sku = f"SKU-TEST-{uuid.uuid4().hex[:6].upper()}"
        self.created_skus.append(unique_sku)
        initial_payload = {
            "sku": unique_sku,
            "name": "Warehouse Router Enterprise",
            "category": "Networking",
            "unit_cost": 450.00,
            "reorder_threshold": 8,
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 5, "bin_shelf": "R-01"},
                "WH-WEST": {"location_name": "Seattle Hub", "stock": 5, "bin_shelf": "R-02"}
            }
        }
        create_res = self.client.post("/api/inventory", json=initial_payload)
        self.assertEqual(create_res.status_code, 201)

        # Update stock: add WH-EAST with 20 and update WH-NORTH to 15
        update_payload = {
            "warehouses": {
                "WH-NORTH": {"stock": 15},
                "WH-WEST": {"stock": 5},
                "WH-EAST": {"location_name": "New York Hub", "stock": 20, "bin_shelf": "R-03"}
            },
            "unit_cost": 420.00,
            "reorder_threshold": 12
        }

        put_res = self.client.put(f"/api/inventory/{unique_sku}", json=update_payload)
        self.assertEqual(put_res.status_code, 200)
        put_data = put_res.get_json()
        self.assertTrue(put_data.get("success"))
        updated = put_data.get("data")
        # 15 + 5 + 20 = 40
        self.assertEqual(updated["total_stock"], 40)
        self.assertEqual(updated["reorder_threshold"], 12)
        self.assertEqual(updated["unit_cost"], 420.00)

    def test_api_put_inventory_item_not_found(self):
        """Test PUT /api/inventory/<sku> returns 404 for unknown item."""
        response = self.client.put(
            "/api/inventory/SKU-DEFINITELY-DOES-NOT-EXIST-XYZ",
            json={"warehouses": {"WH-NORTH": {"stock": 5}}}
        )
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertIn("not found", data.get("error", "").lower())

    def test_analytics_page_authenticated(self):
        """Test that /analytics renders the charts canvas elements."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "USR-MGR-TEST"
            sess["user_email"] = "manager@procureai.enterprise"
            sess["user_name"] = "Inventory Director"
            sess["user_role"] = "Procurement Director"

        response = self.client.get("/analytics")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("chartWarehouseHubs", html)
        self.assertIn("chartCategoryShare", html)
        self.assertIn("chartTopAssets", html)
        self.assertIn("chartStockHealth", html)

    def test_api_get_inventory_analytics_success(self):
        """Test GET /api/inventory/analytics returns 200 with summary, warehouses, and top assets."""
        response = self.client.get("/api/inventory/analytics")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        payload = data.get("data", {})
        self.assertIn("summary", payload)
        self.assertIn("total_asset_value", payload["summary"])
        self.assertIn("warehouses", payload)
        self.assertIn("categories", payload)
        self.assertIn("top_assets", payload)

    def test_api_get_inventory_history_success(self):
        """Test GET /api/inventory/history returns 200 with movements list."""
        response = self.client.get("/api/inventory/history?limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)


if __name__ == "__main__":
    unittest.main()
