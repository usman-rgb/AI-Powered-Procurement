"""
Mock Data Injection Script (scripts/inject_mock_data.py)
Seeds Firebase Firestore with realistic procurement data:
- Users (Requester, Approver, Procurement Manager, Admin)
- Budgets (Engineering, Marketing, Operations, IT)
- Multi-Warehouse Inventory (IT Hardware, Office Equipment, Industrial Parts)
- Historical & Active Purchase Requests (with AI risk assessments)

Usage:
    python scripts/inject_mock_data.py [--clear]
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to sys.path so we can import app modules
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.firebase_init import get_db, initialize_firebase
from app.services.firebase_db import (
    COLLECTION_USERS,
    COLLECTION_REQUESTS,
    COLLECTION_INVENTORY,
    COLLECTION_BUDGETS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("seed_data")


def get_mock_users():
    now = datetime.now(timezone.utc)
    return [
        {
            "user_id": "USR-001",
            "name": "Sarah Jenkins",
            "email": "sarah.jenkins@acme-corp.com",
            "role": "requester",
            "department": "Engineering",
            "spending_limit": 5000.00,
            "is_active": True,
            "created_at": now - timedelta(days=90),
        },
        {
            "user_id": "USR-002",
            "name": "Marcus Vance",
            "email": "marcus.vance@acme-corp.com",
            "role": "approver",
            "department": "Engineering",
            "spending_limit": 50000.00,
            "is_active": True,
            "created_at": now - timedelta(days=120),
        },
        {
            "user_id": "USR-003",
            "name": "Elena Rostova",
            "email": "elena.rostova@acme-corp.com",
            "role": "procurement_manager",
            "department": "Operations",
            "spending_limit": 250000.00,
            "is_active": True,
            "created_at": now - timedelta(days=150),
        },
        {
            "user_id": "USR-004",
            "name": "David Kim",
            "email": "david.kim@acme-corp.com",
            "role": "admin",
            "department": "IT",
            "spending_limit": 100000.00,
            "is_active": True,
            "created_at": now - timedelta(days=200),
        }
    ]


def get_mock_budgets():
    now = datetime.now(timezone.utc)
    return [
        {
            "budget_id": "BUD-ENG-2026-Q3",
            "department": "Engineering",
            "fiscal_year": 2026,
            "quarter": "Q3",
            "allocated_amount": 150000.00,
            "committed_amount": 28450.00,
            "spent_amount": 64200.00,
            "remaining_amount": 150000.00 - 28450.00 - 64200.00,
            "currency": "USD",
            "status": "active",
            "updated_at": now,
        },
        {
            "budget_id": "BUD-MKT-2026-Q3",
            "department": "Marketing",
            "fiscal_year": 2026,
            "quarter": "Q3",
            "allocated_amount": 80000.00,
            "committed_amount": 12000.00,
            "spent_amount": 45000.00,
            "remaining_amount": 80000.00 - 12000.00 - 45000.00,
            "currency": "USD",
            "status": "active",
            "updated_at": now,
        },
        {
            "budget_id": "BUD-OPS-2026-Q3",
            "department": "Operations",
            "fiscal_year": 2026,
            "quarter": "Q3",
            "allocated_amount": 220000.00,
            "committed_amount": 35000.00,
            "spent_amount": 115000.00,
            "remaining_amount": 220000.00 - 35000.00 - 115000.00,
            "currency": "USD",
            "status": "active",
            "updated_at": now,
        },
        {
            "budget_id": "BUD-IT-2026-Q3",
            "department": "IT",
            "fiscal_year": 2026,
            "quarter": "Q3",
            "allocated_amount": 110000.00,
            "committed_amount": 18500.00,
            "spent_amount": 71000.00,
            "remaining_amount": 110000.00 - 18500.00 - 71000.00,
            "currency": "USD",
            "status": "active",
            "updated_at": now,
        },
        {
            "budget_id": "BUD-FIN-2026-Q3",
            "department": "Finance",
            "fiscal_year": 2026,
            "quarter": "Q3",
            "allocated_amount": 150000.00,
            "committed_amount": 0.00,
            "spent_amount": 25000.00,
            "remaining_amount": 150000.00 - 0.00 - 25000.00,
            "currency": "USD",
            "status": "active",
            "updated_at": now,
        },
        {
            "budget_id": "BUD-HR-2026-Q3",
            "department": "Human Resources",
            "fiscal_year": 2026,
            "quarter": "Q3",
            "allocated_amount": 75000.00,
            "committed_amount": 0.00,
            "spent_amount": 10000.00,
            "remaining_amount": 75000.00 - 0.00 - 10000.00,
            "currency": "USD",
            "status": "active",
            "updated_at": now,
        }
    ]


def get_mock_inventory():
    now = datetime.now(timezone.utc)
    return [
        {
            "sku": "SKU-LAPTOP-PRO16",
            "name": "Developer Workstation Laptop 16-inch",
            "category": "Hardware",
            "unit_cost": 2400.00,
            "reorder_threshold": 15,
            "total_stock": 42,
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 18, "bin_shelf": "A-01-2"},
                "WH-WEST":  {"location_name": "Seattle Hub", "stock": 10, "bin_shelf": "W-05-1"},
                "WH-EAST":  {"location_name": "New York Hub", "stock": 14, "bin_shelf": "E-02-4"},
            },
            "created_at": now - timedelta(days=60),
            "updated_at": now,
        },
        {
            "sku": "SKU-MON-4K27",
            "name": "UltraSharp 27-inch 4K USB-C Monitor",
            "category": "Hardware",
            "unit_cost": 550.00,
            "reorder_threshold": 25,
            "total_stock": 68,
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 25, "bin_shelf": "A-03-1"},
                "WH-WEST":  {"location_name": "Seattle Hub", "stock": 20, "bin_shelf": "W-02-2"},
                "WH-EAST":  {"location_name": "New York Hub", "stock": 23, "bin_shelf": "E-04-1"},
            },
            "created_at": now - timedelta(days=75),
            "updated_at": now,
        },
        {
            "sku": "SKU-CHAIR-ERGO",
            "name": "Ergonomic Mesh Task Chair",
            "category": "Office Supplies",
            "unit_cost": 380.00,
            "reorder_threshold": 20,
            "total_stock": 18,  # Below reorder threshold!
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 6, "bin_shelf": "B-10-1"},
                "WH-WEST":  {"location_name": "Seattle Hub", "stock": 4, "bin_shelf": "W-12-1"},
                "WH-EAST":  {"location_name": "New York Hub", "stock": 8, "bin_shelf": "E-09-3"},
            },
            "created_at": now - timedelta(days=45),
            "updated_at": now,
        },
        {
            "sku": "SKU-SVR-RACK1U",
            "name": "1U Enterprise Edge Compute Node",
            "category": "Hardware",
            "unit_cost": 4200.00,
            "reorder_threshold": 5,
            "total_stock": 7,
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 3, "bin_shelf": "S-01-1"},
                "WH-WEST":  {"location_name": "Seattle Hub", "stock": 2, "bin_shelf": "S-02-1"},
                "WH-EAST":  {"location_name": "New York Hub", "stock": 2, "bin_shelf": "S-03-1"},
            },
            "created_at": now - timedelta(days=80),
            "updated_at": now,
        },
        {
            "sku": "SKU-DESK-STAND",
            "name": "Motorized Height Adjustable Desk",
            "category": "Office Supplies",
            "unit_cost": 620.00,
            "reorder_threshold": 12,
            "total_stock": 11,  # Below reorder threshold!
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 5, "bin_shelf": "B-04-2"},
                "WH-WEST":  {"location_name": "Seattle Hub", "stock": 3, "bin_shelf": "W-08-3"},
                "WH-EAST":  {"location_name": "New York Hub", "stock": 3, "bin_shelf": "E-07-2"},
            },
            "created_at": now - timedelta(days=40),
            "updated_at": now,
        },
        {
            "sku": "SKU-CBL-CAT6A",
            "name": "Shielded Cat6A Network Cable 500ft Spool",
            "category": "Networking",
            "unit_cost": 115.00,
            "reorder_threshold": 30,
            "total_stock": 85,
            "warehouses": {
                "WH-NORTH": {"location_name": "Chicago Hub", "stock": 35, "bin_shelf": "N-01-1"},
                "WH-WEST":  {"location_name": "Seattle Hub", "stock": 25, "bin_shelf": "W-01-1"},
                "WH-EAST":  {"location_name": "New York Hub", "stock": 25, "bin_shelf": "E-01-1"},
            },
            "created_at": now - timedelta(days=100),
            "updated_at": now,
        },
    ]


def get_mock_purchase_requests():
    now = datetime.now(timezone.utc)
    return [
        {
            "request_id": "PR-2026-001",
            "title": "Q3 Engineering Team Laptops Upgrade",
            "requester_id": "USR-001",
            "requester_name": "Sarah Jenkins",
            "department": "Engineering",
            "category": "Hardware",
            "budget_id": "BUD-ENG-2026-Q3",
            "priority": "high",
            "status": "approved",
            "total_amount": 12000.00,
            "currency": "USD",
            "items": [
                {
                    "sku": "SKU-LAPTOP-PRO16",
                    "item_name": "Developer Workstation Laptop 16-inch",
                    "quantity": 5,
                    "unit_price": 2400.00,
                    "total_price": 12000.00
                }
            ],
            "ai_risk_score": 0.08,
            "ai_notes": "Low risk. Unit price matches verified vendor catalog. Sufficient budget available in Engineering Q3.",
            "approval_trail": [
                {
                    "step": "Submission",
                    "actor_id": "USR-001",
                    "decision": "submitted",
                    "comment": "New cohort developer laptops",
                    "timestamp": now - timedelta(days=10)
                },
                {
                    "step": "Management Approval",
                    "actor_id": "USR-002",
                    "decision": "approved",
                    "comment": "Approved within Q3 team budget",
                    "timestamp": now - timedelta(days=9)
                }
            ],
            "created_at": now - timedelta(days=10),
            "updated_at": now - timedelta(days=9),
        },
        {
            "request_id": "PR-2026-002",
            "title": "Seattle Hub Ergonomic Furniture Replenishment",
            "requester_id": "USR-003",
            "requester_name": "Elena Rostova",
            "department": "Operations",
            "category": "Office Supplies",
            "budget_id": "BUD-OPS-2026-Q3",
            "priority": "medium",
            "status": "submitted",
            "total_amount": 6900.00,
            "currency": "USD",
            "items": [
                {
                    "sku": "SKU-CHAIR-ERGO",
                    "item_name": "Ergonomic Mesh Task Chair",
                    "quantity": 10,
                    "unit_price": 380.00,
                    "total_price": 3800.00
                },
                {
                    "sku": "SKU-DESK-STAND",
                    "item_name": "Motorized Height Adjustable Desk",
                    "quantity": 5,
                    "unit_price": 620.00,
                    "total_price": 3100.00
                }
            ],
            "ai_risk_score": 0.15,
            "ai_notes": "Stock alert verified: Current chairs (18) and standing desks (11) are below safety reorder threshold.",
            "approval_trail": [
                {
                    "step": "Submission",
                    "actor_id": "USR-003",
                    "decision": "submitted",
                    "comment": "Restocking warehouse depleted items",
                    "timestamp": now - timedelta(days=2)
                }
            ],
            "created_at": now - timedelta(days=2),
            "updated_at": now - timedelta(days=2),
        },
        {
            "request_id": "PR-2026-003",
            "title": "Urgent Production Compute Cluster Extension",
            "requester_id": "USR-001",
            "requester_name": "Sarah Jenkins",
            "department": "Engineering",
            "category": "Hardware",
            "budget_id": "BUD-ENG-2026-Q3",
            "priority": "urgent",
            "status": "submitted",
            "total_amount": 16450.00,
            "currency": "USD",
            "items": [
                {
                    "sku": "SKU-SVR-RACK1U",
                    "item_name": "1U Enterprise Edge Compute Node",
                    "quantity": 3,
                    "unit_price": 4200.00,
                    "total_price": 12600.00
                },
                {
                    "sku": "SKU-MON-4K27",
                    "item_name": "UltraSharp 27-inch 4K USB-C Monitor",
                    "quantity": 7,
                    "unit_price": 550.00,
                    "total_price": 3850.00
                }
            ],
            "ai_risk_score": 0.42,
            "ai_notes": "Moderate variance: 1U server unit price is 4% above past 6-month contracted median. Re-negotiation suggested.",
            "approval_trail": [
                {
                    "step": "Submission",
                    "actor_id": "USR-001",
                    "decision": "submitted",
                    "comment": "Compute burst expansion for AI model serving",
                    "timestamp": now - timedelta(hours=8)
                }
            ],
            "created_at": now - timedelta(hours=8),
            "updated_at": now - timedelta(hours=8),
        },
        {
            "request_id": "PR-2026-004",
            "title": "Marketing Analytics Data Subscription Renewal",
            "requester_id": "USR-003",
            "requester_name": "Elena Rostova",
            "department": "Marketing",
            "category": "Software",
            "budget_id": "BUD-MKT-2026-Q3",
            "priority": "low",
            "status": "fulfilled",
            "total_amount": 12000.00,
            "currency": "USD",
            "items": [
                {
                    "sku": "SVC-MKT-DATAFEED",
                    "item_name": "Enterprise Marketing Intelligence Feed",
                    "quantity": 1,
                    "unit_price": 12000.00,
                    "total_price": 12000.00
                }
            ],
            "ai_risk_score": 0.05,
            "ai_notes": "Verified annual renewal. Pre-negotiated enterprise discount applied.",
            "approval_trail": [
                {
                    "step": "Submission",
                    "actor_id": "USR-003",
                    "decision": "submitted",
                    "comment": "Annual contract renewal",
                    "timestamp": now - timedelta(days=30)
                },
                {
                    "step": "Approval",
                    "actor_id": "USR-002",
                    "decision": "approved",
                    "comment": "Approved according to annual plan",
                    "timestamp": now - timedelta(days=28)
                },
                {
                    "step": "Fulfillment",
                    "actor_id": "USR-004",
                    "decision": "fulfilled",
                    "comment": "Invoice paid and license keys issued",
                    "timestamp": now - timedelta(days=25)
                }
            ],
            "created_at": now - timedelta(days=30),
            "updated_at": now - timedelta(days=25),
        },
        {
            "request_id": "PR-2026-005",
            "title": "High-Volume Unapproved Peripherals Order",
            "requester_id": "USR-001",
            "requester_name": "Sarah Jenkins",
            "department": "Engineering",
            "category": "Hardware",
            "budget_id": "BUD-ENG-2026-Q3",
            "priority": "medium",
            "status": "rejected",
            "total_amount": 28000.00,
            "currency": "USD",
            "items": [
                {
                    "sku": "SKU-MON-4K27",
                    "item_name": "UltraSharp 27-inch 4K USB-C Monitor",
                    "quantity": 40,
                    "unit_price": 700.00,  # Highly inflated price!
                    "total_price": 28000.00
                }
            ],
            "ai_risk_score": 0.89,
            "ai_notes": "HIGH RISK: Unit price ($700) is 27% higher than approved vendor pricing ($550). Excessive quantity for engineering sprint.",
            "approval_trail": [
                {
                    "step": "Submission",
                    "actor_id": "USR-001",
                    "decision": "submitted",
                    "comment": "Monitors for floor expansion",
                    "timestamp": now - timedelta(days=15)
                },
                {
                    "step": "AI Rejection Recommendation",
                    "actor_id": "USR-003",
                    "decision": "rejected",
                    "comment": "Rejected based on AI price anomaly alert. Re-quote with preferred vendor required.",
                    "timestamp": now - timedelta(days=14)
                }
            ],
            "created_at": now - timedelta(days=15),
            "updated_at": now - timedelta(days=14),
        }
    ]


def clear_collection(db, collection_name: str, batch_size: int = 50):
    """Delete all documents in a Firestore collection."""
    logger.info(f"Clearing collection '{collection_name}'...")
    col_ref = db.collection(collection_name)
    docs = col_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        doc.reference.delete()
        deleted += 1

    if deleted >= batch_size:
        # Recurse until all are deleted
        return clear_collection(db, collection_name, batch_size)
    logger.info(f"Collection '{collection_name}' wiped.")


def inject_all_mock_data(clear_existing: bool = False):
    """Seed Firestore with all collections using atomic batch writes."""
    logger.info("Connecting to Firestore...")
    db = get_db()

    if clear_existing:
        logger.warning("Clear flag provided. Wiping collections before injection...")
        for col in [COLLECTION_USERS, COLLECTION_BUDGETS, COLLECTION_INVENTORY, COLLECTION_REQUESTS]:
            clear_collection(db, col)

    # 1. Seed Users
    logger.info("Injecting Users...")
    batch = db.batch()
    users = get_mock_users()
    for user in users:
        ref = db.collection(COLLECTION_USERS).document(user["user_id"])
        batch.set(ref, user)
    batch.commit()
    logger.info(f"Successfully injected {len(users)} users.")

    # 2. Seed Budgets
    logger.info("Injecting Budgets...")
    batch = db.batch()
    budgets = get_mock_budgets()
    for budget in budgets:
        ref = db.collection(COLLECTION_BUDGETS).document(budget["budget_id"])
        batch.set(ref, budget)
    batch.commit()
    logger.info(f"Successfully injected {len(budgets)} departmental budgets.")

    # 3. Seed Inventory
    logger.info("Injecting Multi-Warehouse Inventory...")
    batch = db.batch()
    inventory_items = get_mock_inventory()
    for item in inventory_items:
        ref = db.collection(COLLECTION_INVENTORY).document(item["sku"])
        batch.set(ref, item)
    batch.commit()
    logger.info(f"Successfully injected {len(inventory_items)} multi-warehouse inventory items.")

    # 4. Seed Purchase Requests
    logger.info("Injecting Purchase Requests...")
    batch = db.batch()
    requests = get_mock_purchase_requests()
    for pr in requests:
        ref = db.collection(COLLECTION_REQUESTS).document(pr["request_id"])
        batch.set(ref, pr)
    batch.commit()
    logger.info(f"Successfully injected {len(requests)} purchase requests.")

    print("\n=======================================================")
    print(" [SUCCESS] Firestore Mock Data Injected Successfully!")
    print(f" - Users:             {len(users)} documents")
    print(f" - Budgets:           {len(budgets)} documents")
    print(f" - Inventory Items:   {len(inventory_items)} documents (Multi-Warehouse)")
    print(f" - Purchase Requests: {len(requests)} documents (With AI Risk Scores)")
    print("=======================================================\n")


    parser.add_argument(
        "--force",
        action="store_true",
        help="Required explicit safety confirmation flag to permit mock data injection."
    )
    args = parser.parse_args()

    if not args.force:
        print("\n[SAFETY LOCK] Mock data injection is disabled to protect clean live procurement records.")
        print("If you intentionally need to reseed dummy test data, supply: --force\n")
        sys.exit(0)

    try:
        inject_all_mock_data(clear_existing=args.clear)
    except Exception as e:
        logger.error(f"Failed to inject mock data: {e}", exc_info=True)
        print(f"\n[ERROR] Injection failed: {e}")
        sys.exit(1)
