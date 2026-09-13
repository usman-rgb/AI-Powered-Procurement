"""
Services Package
Contains database operations, external integrations, and business logic.
"""

from .firebase_init import get_db, initialize_firebase, is_firebase_initialized
from .firebase_db import (
    # User service methods
    create_user,
    get_user,
    update_user_profile,
    list_users,
    # Purchase Request service methods
    create_purchase_request,
    get_purchase_request,
    update_purchase_request_status,
    list_purchase_requests,
    # Inventory service methods
    get_inventory_item,
    upsert_inventory_item,
    update_warehouse_stock,
    auto_allocate_inventory,
    list_inventory,
    get_low_stock_items,
    get_all_inventory,
    add_new_inventory_item,
    update_manual_stock,
    record_stock_movement,
    get_inventory_history,
    get_inventory_analytics,
    # Budget service methods
    get_budget,
    upsert_budget,
    list_budgets,
    check_and_commit_budget,
    rollback_committed_budget,
    deduct_actual_spend,
    get_dynamic_budget_id,
)
from .validation_engine import ValidationEngine, run_pre_ai_validation

__all__ = [
    "get_db",
    "initialize_firebase",
    "is_firebase_initialized",
    "create_user",
    "get_user",
    "update_user_profile",
    "list_users",
    "create_purchase_request",
    "get_purchase_request",
    "update_purchase_request_status",
    "list_purchase_requests",
    "get_inventory_item",
    "upsert_inventory_item",
    "update_warehouse_stock",
    "auto_allocate_inventory",
    "list_inventory",
    "get_low_stock_items",
    "get_all_inventory",
    "add_new_inventory_item",
    "update_manual_stock",
    "record_stock_movement",
    "get_inventory_history",
    "get_inventory_analytics",
    "get_budget",
    "upsert_budget",
    "list_budgets",
    "check_and_commit_budget",
    "rollback_committed_budget",
    "deduct_actual_spend",
    "get_dynamic_budget_id",
    "ValidationEngine",
    "run_pre_ai_validation",
]
