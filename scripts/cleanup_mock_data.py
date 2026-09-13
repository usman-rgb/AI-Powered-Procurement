"""
Database Sanitization & Mock Data Cleanup Script (scripts/cleanup_mock_data.py)
Removes all mock, sample, and testing data from Firestore:
- Cleans dummy SKUs (SKU-TEST-* and injected sample catalog items)
- Cleans dummy stock movements (MOV-* referring to test/mock SKUs)
- Cleans fake test users (USR-001..004, login_test@*, USR-TEST-*)
- Resets dummy test purchase requests and uncommits budget
- Preserves genuine registered users and real items (e.g. 1455 / Iphone)
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.firebase_init import get_db
from app.services.firebase_db import (
    COLLECTION_INVENTORY,
    COLLECTION_STOCK_MOVEMENTS,
    COLLECTION_REQUESTS,
    COLLECTION_USERS,
    COLLECTION_BUDGETS,
    record_stock_movement,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("cleanup_mock_data")


def purge_mock_and_dummy_data():
    db = get_db()
    logger.info("Starting complete mock and dummy data cleanup from Firestore...")

    # 1. Purge Dummy & Mock Inventory Items
    mock_skus_set = {
        "SKU-CBL-CAT6A",
        "SKU-CHAIR-ERGO",
        "SKU-DESK-STAND",
        "SKU-LAPTOP-PRO16",
        "SKU-MON-4K27",
        "SKU-SVR-RACK1U",
    }
    
    deleted_inventory_count = 0
    inv_docs = list(db.collection(COLLECTION_INVENTORY).stream())
    for doc in inv_docs:
        sku = doc.id
        if sku.startswith("SKU-TEST-") or sku in mock_skus_set:
            db.collection(COLLECTION_INVENTORY).document(sku).delete()
            logger.info(f"Deleted mock/test inventory item: '{sku}'")
            deleted_inventory_count += 1
            
    logger.info(f"Purged {deleted_inventory_count} mock/test inventory items.")

    # 2. Purge Dummy Stock Movements
    deleted_movements_count = 0
    mov_docs = list(db.collection(COLLECTION_STOCK_MOVEMENTS).stream())
    for doc in mov_docs:
        data = doc.to_dict()
        sku = data.get("sku", "")
        if sku.startswith("SKU-TEST-") or sku in mock_skus_set:
            db.collection(COLLECTION_STOCK_MOVEMENTS).document(doc.id).delete()
            logger.info(f"Deleted mock stock movement: '{doc.id}' for SKU '{sku}'")
            deleted_movements_count += 1
            
    logger.info(f"Purged {deleted_movements_count} mock stock movement records.")

    # Ensure genuine item '1455' has its legitimate audit trail record if empty
    real_movs = list(db.collection(COLLECTION_STOCK_MOVEMENTS).where("sku", "==", "1455").stream())
    if len(real_movs) == 0:
        doc_1455 = db.collection(COLLECTION_INVENTORY).document("1455").get()
        if doc_1455.exists:
            d = doc_1455.to_dict()
            total_stock = d.get("total_stock", 71)
            record_stock_movement(
                sku="1455",
                item_name=d.get("name", "Iphone"),
                movement_type="creation",
                quantity_change=total_stock,
                warehouse_code="ALL",
                new_stock=total_stock,
                previous_stock=0,
                actor_id="Muhammad Usman",
                reason=f"Initial genuine catalog registration of {total_stock} units across regional hubs.",
            )
            logger.info("Recorded genuine initial movement for SKU '1455' (Iphone).")

    # 3. Purge Fake Test Users
    genuine_emails = {
        "manoousman469@gmail.com",
        "aiengineer735@gmail.com",
        "techflarehub@gmail.com",
    }
    mock_user_ids = {"USR-001", "USR-002", "USR-003", "USR-004"}

    deleted_users_count = 0
    user_docs = list(db.collection(COLLECTION_USERS).stream())
    for doc in user_docs:
        uid = doc.id
        data = doc.to_dict()
        email = (data.get("email") or "").strip().lower()
        
        is_mock = (
            uid in mock_user_ids
            or uid.startswith("USR-TEST")
            or "acme-corp.com" in email
            or "login_test" in email
            or (uid.startswith("USR-") and email not in genuine_emails)
        )
        
        if is_mock:
            db.collection(COLLECTION_USERS).document(uid).delete()
            logger.info(f"Deleted mock/test user: '{uid}' ({email})")
            deleted_users_count += 1

    logger.info(f"Purged {deleted_users_count} mock/test user accounts.")

    # 4. Clean Test Purchase Requests & Reset Committed Budgets
    test_request_ids = ["PR-202609-00C109", "PR-202609-55F7C4"]
    deleted_requests_count = 0
    for pr_id in test_request_ids:
        doc = db.collection(COLLECTION_REQUESTS).document(pr_id).get()
        if doc.exists:
            db.collection(COLLECTION_REQUESTS).document(pr_id).delete()
            logger.info(f"Deleted test purchase request: '{pr_id}'")
            deleted_requests_count += 1
            
    # Reset committed budget on BUD-FIN-2026-Q3
    fin_doc = db.collection(COLLECTION_BUDGETS).document("BUD-FIN-2026-Q3").get()
    if fin_doc.exists:
        fin_data = fin_doc.to_dict()
        allocated = float(fin_data.get("allocated_amount", 150000.0))
        spent = float(fin_data.get("spent_amount", 0.0))
        db.collection(COLLECTION_BUDGETS).document("BUD-FIN-2026-Q3").update({
            "committed_amount": 0.0,
            "remaining_amount": allocated - spent,
            "updated_at": datetime.now(timezone.utc),
        })
        logger.info("Reset BUD-FIN-2026-Q3 committed budget to $0.00.")

    logger.info(
        f"\n========================================\n"
        f"MOCK & DUMMY CLEANUP COMPLETED:\n"
        f"- Deleted Mock Inventory Items: {deleted_inventory_count}\n"
        f"- Deleted Mock Movements: {deleted_movements_count}\n"
        f"- Deleted Mock Users: {deleted_users_count}\n"
        f"- Deleted Test Purchase Requests: {deleted_requests_count}\n"
        f"========================================"
    )


if __name__ == "__main__":
    purge_mock_and_dummy_data()
