"""
Firestore Database Service Module (firebase_db.py)
Provides high-level CRUD operations, queries, and business logic for the 4 core collections:
1. Users
2. Purchase_Requests
3. Inventory (Multi-Warehouse Stock)
4. Budgets

Schema Specifications:
--------------------------------------------------------------------------------
1. Users:
   - document_id: str (user_id, e.g., "USR-101")
   - name: str
   - email: str
   - role: str ("requester", "approver", "procurement_manager", "admin")
   - department: str ("Engineering", "Marketing", "Operations", "IT", "Finance")
   - spending_limit: float (max purchase amount approvable or requestable without escalate)
   - is_active: bool
   - created_at: timestamp

2. Purchase_Requests:
   - document_id: str (request_id, e.g., "PR-2026-001")
   - title: str
   - requester_id: str (reference to Users.user_id)
   - requester_name: str
   - department: str
   - category: str ("Hardware", "Software", "Office Supplies", "Services", "Raw Materials")
   - items: list[dict]
       [{"sku": str, "item_name": str, "quantity": int, "unit_price": float, "total_price": float}]
   - total_amount: float
   - currency: str (default "USD")
   - priority: str ("low", "medium", "high", "urgent")
   - status: str ("draft", "submitted", "approved", "rejected", "fulfilled", "cancelled")
   - budget_id: str (reference to Budgets.budget_id)
   - ai_risk_score: float (0.0 to 1.0; e.g. 0.12 = low risk, 0.85 = anomalous/high risk)
   - ai_notes: str (AI explanation, e.g., price variance, vendor reliability, duplication check)
   - approval_trail: list[dict]
       [{"step": str, "actor_id": str, "decision": str, "timestamp": timestamp, "comment": str}]
   - created_at: timestamp
   - updated_at: timestamp

3. Inventory (Multi-Warehouse):
   - document_id: str (sku, e.g., "SKU-LAPTOP-X1")
   - name: str
   - category: str
   - unit_cost: float
   - reorder_threshold: int
   - total_stock: int (computed sum of stock across all warehouse hubs)
   - warehouses: dict[warehouse_code, dict]
       {
           "WH-NORTH": {"location_name": "Chicago Hub", "stock": 45, "bin_shelf": "A-12"},
           "WH-WEST":  {"location_name": "Seattle Hub", "stock": 20, "bin_shelf": "W-04"},
           "WH-EAST":  {"location_name": "New York Hub", "stock": 60, "bin_shelf": "E-08"}
       }
   - created_at: timestamp
   - updated_at: timestamp

4. Budgets:
   - document_id: str (budget_id, e.g., "BUD-ENG-2026-Q3")
   - department: str
   - fiscal_year: int
   - quarter: str ("Q1", "Q2", "Q3", "Q4")
   - allocated_amount: float
   - committed_amount: float (allocated for approved / in-progress purchase orders)
   - spent_amount: float (actually invoiced / settled)
   - remaining_amount: float (allocated - committed - spent)
   - currency: str (default "USD")
   - status: str ("active", "closed", "over_budget")
   - updated_at: timestamp
--------------------------------------------------------------------------------
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.services.firebase_init import get_db

logger = logging.getLogger(__name__)

# Collection Names
COLLECTION_USERS = "Users"
COLLECTION_REQUESTS = "Purchase_Requests"
COLLECTION_INVENTORY = "Inventory"
COLLECTION_BUDGETS = "Budgets"
COLLECTION_STOCK_MOVEMENTS = "Stock_Movements"


# ==============================================================================
# Helper Functions
# ==============================================================================

def _utc_now() -> datetime:
    """Return the current UTC datetime with timezone awareness."""
    return datetime.now(timezone.utc)


def serialize_firestore_data(data: Any) -> Any:
    """
    Recursively serialize Firestore data structures, converting non-standard objects
    like DatetimeWithNanoseconds and datetime instances to standard ISO 8601 strings.
    """
    if isinstance(data, dict):
        return {k: serialize_firestore_data(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [serialize_firestore_data(v) for v in data]
    elif hasattr(data, "isoformat"):
        return data.isoformat()
    elif hasattr(data, "to_datetime"):
        return data.to_datetime().isoformat()
    return data


# ==============================================================================
# 1. Users Operations
# ==============================================================================

def create_user(user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create or update a user document in Firestore.
    
    Args:
        user_id: Unique string identifier for the user.
        user_data: User properties dictionary.
        
    Returns:
        dict: The persisted user data including timestamps.
    """
    db = get_db()
    data = user_data.copy()
    data["user_id"] = user_id
    if "created_at" not in data:
        data["created_at"] = _utc_now()
    data["updated_at"] = _utc_now()
    
    try:
        doc_ref = db.collection(COLLECTION_USERS).document(user_id)
        doc_ref.set(data, merge=True)
        logger.info(f"User '{user_id}' saved successfully.")
        return data
    except Exception as e:
        logger.error(f"Error saving user '{user_id}': {e}")
        raise


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user document by ID.
    
    Args:
        user_id: User identifier.
        
    Returns:
        Optional[dict]: User data dictionary or None if not found.
    """
    db = get_db()
    try:
        doc_ref = db.collection(COLLECTION_USERS).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error fetching user '{user_id}': {e}")
        raise


def update_user_profile(user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an authenticated user's profile and preferences in Firestore.
    
    Args:
        user_id: User identifier document ID.
        profile_data: Fields to update (e.g., name, department, job_title, spending_limit).
        
    Returns:
        dict: The updated user profile dictionary.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION_USERS).document(user_id)
    
    try:
        doc = doc_ref.get()
        existing = doc.to_dict() if doc.exists else {"uid": user_id, "user_id": user_id}
        
        updates = profile_data.copy()
        updates["updated_at"] = _utc_now()
        
        # If name is updated, recalculate avatar initials
        if "name" in updates and updates["name"]:
            name_parts = updates["name"].strip().split()
            updates["initials"] = "".join([p[0].upper() for p in name_parts[:2]]) if name_parts else "US"
            
        doc_ref.set(updates, merge=True)
        existing.update(updates)
        logger.info(f"User profile '{user_id}' updated successfully.")
        return existing
    except Exception as e:
        logger.error(f"Error updating user profile '{user_id}': {e}")
        raise


def list_users(
    role: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    List users with optional filtering by role and department.
    """
    db = get_db()
    try:
        query = db.collection(COLLECTION_USERS)
        if role:
            query = query.where(filter=FieldFilter("role", "==", role))
        if department:
            query = query.where(filter=FieldFilter("department", "==", department))
        
        docs = query.limit(limit).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Error querying users: {e}")
        raise


# ==============================================================================
# 2. Purchase Requests Operations
# ==============================================================================

def create_purchase_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new purchase request in Firestore.
    
    Args:
        request_data: Purchase request dictionary. If 'request_id' is not provided,
                      a random Firestore document ID will be generated.
                      
    Returns:
        dict: The created purchase request data with document ID.
    """
    db = get_db()
    data = request_data.copy()
    now = _utc_now()
    data["created_at"] = data.get("created_at", now)
    data["updated_at"] = now
    
    # Calculate total_amount from items if not explicitly set
    if "total_amount" not in data and "items" in data:
        data["total_amount"] = sum(
            float(item.get("total_price", float(item.get("quantity", 0)) * float(item.get("unit_price", 0.0))))
            for item in data["items"]
        )

    # Default status and AI risk assessment fields
    data.setdefault("status", "submitted")
    data.setdefault("priority", "medium")
    data.setdefault("currency", "USD")
    data.setdefault("ai_risk_score", 0.0)
    data.setdefault("ai_notes", "Awaiting AI procurement screening.")
    data.setdefault("approval_trail", [])
    
    try:
        if "request_id" in data and data["request_id"]:
            req_id = data["request_id"]
            doc_ref = db.collection(COLLECTION_REQUESTS).document(req_id)
            doc_ref.set(data)
        else:
            doc_ref = db.collection(COLLECTION_REQUESTS).document()
            data["request_id"] = doc_ref.id
            doc_ref.set(data)
            
        logger.info(f"Purchase Request '{data['request_id']}' created.")
        return data
    except Exception as e:
        logger.error(f"Error creating purchase request: {e}")
        raise


def get_purchase_request(request_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a purchase request by ID."""
    db = get_db()
    try:
        doc = db.collection(COLLECTION_REQUESTS).document(request_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error fetching purchase request '{request_id}': {e}")
        raise


def update_purchase_request_status(
    request_id: str,
    new_status: str,
    actor_id: Optional[str] = None,
    comment: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update the status of a purchase request and append an entry to the audit approval trail.
    
    Args:
        request_id: ID of the purchase request.
        new_status: New status ("submitted", "approved", "rejected", "fulfilled", "cancelled").
        actor_id: ID of the user performing the action.
        comment: Optional approval or rejection comment.
        
    Returns:
        dict: Updated purchase request data.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION_REQUESTS).document(request_id)
    
    try:
        doc = doc_ref.get()
        if not doc.exists:
            raise ValueError(f"Purchase request '{request_id}' not found.")
        
        current_data = doc.to_dict()
        existing_trail = list(current_data.get("approval_trail") or [])
        
        now = _utc_now()
        trail_entry_firestore = {
            "step": f"Status changed to {new_status}",
            "actor_id": actor_id or "system",
            "decision": new_status,
            "comment": comment or "",
            "timestamp": now
        }
        trail_entry_dict = {
            "step": f"Status changed to {new_status}",
            "actor_id": actor_id or "system",
            "decision": new_status,
            "comment": comment or "",
            "timestamp": now.isoformat()
        }
        
        updates = {
            "status": new_status,
            "updated_at": now,
            "approval_trail": firestore.ArrayUnion([trail_entry_firestore])
        }
        
        doc_ref.update(updates)
        
        existing_trail.append(trail_entry_dict)
        current_data["status"] = new_status
        current_data["updated_at"] = now.isoformat()
        current_data["approval_trail"] = existing_trail
        logger.info(f"Purchase request '{request_id}' status updated to '{new_status}'.")
        return current_data
    except Exception as e:
        logger.error(f"Error updating purchase request '{request_id}': {e}")
        raise


def update_ai_risk_assessment(
    request_id: str,
    risk_score: float,
    ai_notes: str
) -> None:
    """
    Record an AI risk score and automated evaluation note on a purchase request.
    """
    db = get_db()
    try:
        doc_ref = db.collection(COLLECTION_REQUESTS).document(request_id)
        doc_ref.update({
            "ai_risk_score": float(risk_score),
            "ai_notes": ai_notes,
            "updated_at": _utc_now()
        })
        logger.info(f"AI risk assessment updated for request '{request_id}' (score: {risk_score}).")
    except Exception as e:
        logger.error(f"Error updating AI assessment for '{request_id}': {e}")
        raise


def list_purchase_requests(
    department: Optional[str] = None,
    status: Optional[str] = None,
    requester_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """List purchase requests with optional filters."""
    db = get_db()
    try:
        query = db.collection(COLLECTION_REQUESTS)
        if department:
            query = query.where(filter=FieldFilter("department", "==", department))
        if status:
            query = query.where(filter=FieldFilter("status", "==", status))
        if requester_id:
            query = query.where(filter=FieldFilter("requester_id", "==", requester_id))
            
        docs = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        # If Firestore index is not yet built for multiple where + order_by, fallback to unordered query
        logger.warning(f"Ordered query failed ({e}), falling back to simple stream query.")
        try:
            query = db.collection(COLLECTION_REQUESTS)
            if department:
                query = query.where(filter=FieldFilter("department", "==", department))
            if status:
                query = query.where(filter=FieldFilter("status", "==", status))
            if requester_id:
                query = query.where(filter=FieldFilter("requester_id", "==", requester_id))
            docs = query.limit(limit).stream()
            results = [doc.to_dict() for doc in docs]
            # In-memory sort by created_at descending if available
            return sorted(results, key=lambda x: str(x.get("created_at", "")), reverse=True)
        except Exception as inner_e:
            logger.error(f"Error listing purchase requests: {inner_e}")
            raise


# ==============================================================================
# 3. Inventory Operations (Multi-Warehouse Stock)
# ==============================================================================

def upsert_inventory_item(sku: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert or update an inventory item with multi-warehouse quantities.
    Automatically recalculates 'total_stock' as the sum of all warehouse stock.
    
    Args:
        sku: Unique item SKU.
        item_data: Inventory item attributes, including optional 'warehouses' dict.
        
    Returns:
        dict: Persisted inventory document.
    """
    db = get_db()
    data = item_data.copy()
    data["sku"] = sku
    now = _utc_now()
    if "created_at" not in data:
        data["created_at"] = now
    data["updated_at"] = now
    
    warehouses = data.get("warehouses", {})
    # Recalculate total_stock dynamically across all warehouse locations
    data["total_stock"] = sum(
        wh.get("stock", 0) for wh in warehouses.values() if isinstance(wh, dict)
    )
    data.setdefault("reorder_threshold", 10)
    data.setdefault("unit_cost", 0.0)
    
    try:
        doc_ref = db.collection(COLLECTION_INVENTORY).document(sku)
        doc_ref.set(data, merge=True)
        logger.info(f"Inventory item '{sku}' upserted (Total Stock: {data['total_stock']}).")
        return data
    except Exception as e:
        logger.error(f"Error upserting inventory item '{sku}': {e}")
        raise


def get_inventory_item(sku: str) -> Optional[Dict[str, Any]]:
    """Retrieve an inventory item by SKU."""
    db = get_db()
    try:
        doc = db.collection(COLLECTION_INVENTORY).document(sku).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error fetching inventory item '{sku}': {e}")
        raise


def update_warehouse_stock(
    sku: str,
    warehouse_code: str,
    delta_qty: int,
    location_name: Optional[str] = None,
    bin_shelf: Optional[str] = None
) -> Dict[str, Any]:
    """
    Adjust stock quantity for a specific warehouse location and synchronize aggregate total_stock.
    
    Args:
        sku: SKU of the item.
        warehouse_code: Code for the warehouse (e.g. 'WH-NORTH', 'WH-WEST').
        delta_qty: Positive to add stock, negative to consume/deduct stock.
        location_name: Optional human-readable name if warehouse is new.
        bin_shelf: Optional shelf/bin identifier.
        
    Returns:
        dict: Updated inventory item document.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION_INVENTORY).document(sku)
    
    try:
        doc = doc_ref.get()
        if not doc.exists:
            raise ValueError(f"Inventory item with SKU '{sku}' not found.")
            
        data = doc.to_dict()
        warehouses = data.get("warehouses", {})
        
        # Initialize warehouse entry if not present
        if warehouse_code not in warehouses:
            warehouses[warehouse_code] = {
                "location_name": location_name or warehouse_code,
                "stock": 0,
                "bin_shelf": bin_shelf or "UNASSIGNED"
            }
            
        current_wh_stock = warehouses[warehouse_code].get("stock", 0)
        new_wh_stock = current_wh_stock + delta_qty
        
        if new_wh_stock < 0:
            raise ValueError(
                f"Insufficient stock in warehouse '{warehouse_code}' for SKU '{sku}'. "
                f"Available: {current_wh_stock}, Requested deduction: {abs(delta_qty)}"
            )
            
        warehouses[warehouse_code]["stock"] = new_wh_stock
        if bin_shelf:
            warehouses[warehouse_code]["bin_shelf"] = bin_shelf
        if location_name:
            warehouses[warehouse_code]["location_name"] = location_name
            
        # Recalculate total aggregate stock
        data["warehouses"] = warehouses
        data["total_stock"] = sum(wh.get("stock", 0) for wh in warehouses.values())
        data["updated_at"] = _utc_now()
        
        doc_ref.set(data, merge=True)
        logger.info(
            f"Updated stock for SKU '{sku}' in '{warehouse_code}': {current_wh_stock} -> {new_wh_stock}. "
            f"New total: {data['total_stock']}"
        )
        return data
    except Exception as e:
        logger.error(f"Error updating stock for '{sku}' in '{warehouse_code}': {e}")
        raise


def auto_allocate_inventory(
    sku: str, 
    quantity_needed: int,
    actor: str = "ProcureAI-Decision-Agent",
    reference_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query the Inventory collection, inspect the nested 'warehouses' dictionary,
    and deduct quantity_needed from the first available warehouse(s) that have idle stock.
    Automatically recalculates aggregate 'total_stock' and updates Firestore.
    
    Args:
        sku: Unique item SKU.
        quantity_needed: Number of units to allocate/transfer.
        
    Returns:
        dict: Allocation summary including allocated quantities per warehouse.
        
    Raises:
        ValueError: If inventory item is not found or no idle stock is available.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION_INVENTORY).document(sku)
    
    try:
        doc = doc_ref.get()
        if not doc.exists:
            raise ValueError(f"Inventory item with SKU '{sku}' not found in Firestore.")
            
        data = doc.to_dict()
        warehouses = data.get("warehouses", {})
        
        remaining_needed = int(quantity_needed)
        if remaining_needed <= 0:
            return {
                "sku": sku,
                "item_name": data.get("name", sku),
                "quantity_requested": 0,
                "quantity_allocated": 0,
                "remaining_unallocated": 0,
                "allocations": [],
                "new_total_stock": data.get("total_stock", 0)
            }
            
        allocations = []
        total_allocated = 0
        
        # Iterate over warehouses and deduct from those with available idle stock (> 0)
        for wh_code, wh_info in warehouses.items():
            current_stock = int(wh_info.get("stock", 0))
            if current_stock > 0:
                deduct_qty = min(remaining_needed, current_stock)
                new_wh_stock = current_stock - deduct_qty
                wh_info["stock"] = new_wh_stock
                remaining_needed -= deduct_qty
                total_allocated += deduct_qty
                
                allocations.append({
                    "warehouse_code": wh_code,
                    "location_name": wh_info.get("location_name", wh_code),
                    "bin_shelf": wh_info.get("bin_shelf", "UNASSIGNED"),
                    "allocated_qty": deduct_qty,
                    "remaining_wh_stock": new_wh_stock
                })
                
                if remaining_needed == 0:
                    break
                    
        if total_allocated == 0:
            raise ValueError(f"No idle warehouse inventory available to allocate for SKU '{sku}'.")
            
        # Recalculate total aggregate stock across all warehouses
        data["warehouses"] = warehouses
        data["total_stock"] = sum(wh.get("stock", 0) for wh in warehouses.values())
        data["updated_at"] = _utc_now()
        
        doc_ref.set(data, merge=True)
        logger.info(
            f"Auto-allocated {total_allocated}/{quantity_needed} units of '{sku}' across {len(allocations)} warehouse(s). "
            f"New total stock: {data['total_stock']}"
        )

        # Audit Trail: Record stock movement for each warehouse allocation
        for alloc in allocations:
            try:
                record_stock_movement(
                    sku=sku,
                    item_name=data.get("name", sku),
                    movement_type="auto_allocation",
                    quantity_change=-alloc["allocated_qty"],
                    warehouse_code=alloc["warehouse_code"],
                    new_stock=alloc["remaining_wh_stock"],
                    previous_stock=alloc["remaining_wh_stock"] + alloc["allocated_qty"],
                    actor_id=actor or "ProcureAI-Decision-Agent",
                    reason=notes or f"AI Auto-allocated {alloc['allocated_qty']} unit(s) from {alloc['location_name']} to fulfill purchase request.",
                    reference_id=reference_id,
                )
            except Exception as rec_err:
                logger.warning(f"Could not record allocation movement for '{sku}': {rec_err}")
        
        return {
            "sku": sku,
            "item_name": data.get("name", sku),
            "quantity_requested": quantity_needed,
            "quantity_allocated": total_allocated,
            "remaining_unallocated": remaining_needed,
            "allocations": allocations,
            "new_total_stock": data["total_stock"]
        }
    except Exception as e:
        logger.error(f"Error auto-allocating inventory for '{sku}': {e}")
        raise



def list_inventory(
    category: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """List all inventory items with optional category filter."""
    db = get_db()
    try:
        query = db.collection(COLLECTION_INVENTORY)
        if category:
            query = query.where(filter=FieldFilter("category", "==", category))
        docs = query.limit(limit).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Error listing inventory: {e}")
        raise


def get_low_stock_items() -> List[Dict[str, Any]]:
    """Retrieve inventory items where total_stock <= reorder_threshold."""
    items = list_inventory(limit=500)
    return [
        item for item in items 
        if item.get("total_stock", 0) <= item.get("reorder_threshold", 0)
    ]


def get_all_inventory(category: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Fetch all inventory items from Firestore, optionally filtered by category.
    Sorts items alphabetically by category and item name.
    """
    items = list_inventory(category=category, limit=limit)
    items.sort(key=lambda x: (x.get("category", ""), x.get("name", x.get("sku", ""))))
    return items


def add_new_inventory_item(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new inventory item document in the Firestore Inventory collection.
    
    Args:
        data: Item payload containing sku, name, category, unit_cost, reorder_threshold, warehouses.
        
    Returns:
        dict: Persisted inventory document.
        
    Raises:
        ValueError: If required fields are missing, invalid, or SKU already exists.
    """
    if not data or not isinstance(data, dict):
        raise ValueError("Payload must be a non-empty JSON object.")
        
    sku = str(data.get("sku", "")).strip().upper()
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()
    
    if not sku:
        raise ValueError("Field 'sku' is required.")
    if not name:
        raise ValueError("Field 'name' is required.")
    if not category:
        raise ValueError("Field 'category' is required.")
        
    db = get_db()
    doc_ref = db.collection(COLLECTION_INVENTORY).document(sku)
    
    # Check if SKU already exists
    existing = doc_ref.get()
    if existing.exists:
        raise ValueError(f"Inventory item with SKU '{sku}' already exists.")
        
    now = _utc_now()
    
    # Parse warehouses
    raw_warehouses = data.get("warehouses", {})
    clean_warehouses = {}
    if isinstance(raw_warehouses, dict):
        for wh_code, wh_data in raw_warehouses.items():
            wh_code_clean = str(wh_code).strip().upper()
            if not wh_code_clean:
                continue
            if isinstance(wh_data, dict):
                stock = max(0, int(wh_data.get("stock", 0)))
                loc_name = str(wh_data.get("location_name", wh_code_clean)).strip()
                bin_shelf = str(wh_data.get("bin_shelf", "UNASSIGNED")).strip()
            else:
                stock = max(0, int(wh_data or 0))
                loc_name = wh_code_clean
                bin_shelf = "UNASSIGNED"
                
            clean_warehouses[wh_code_clean] = {
                "location_name": loc_name,
                "stock": stock,
                "bin_shelf": bin_shelf
            }
            
    # Default standard warehouses if none provided
    if not clean_warehouses:
        clean_warehouses = {
            "WH-NORTH": {"location_name": "Chicago Hub", "stock": 0, "bin_shelf": "A-01"},
            "WH-WEST": {"location_name": "Seattle Hub", "stock": 0, "bin_shelf": "W-01"},
            "WH-EAST": {"location_name": "New York Hub", "stock": 0, "bin_shelf": "E-01"},
        }
        
    total_stock = sum(wh.get("stock", 0) for wh in clean_warehouses.values())
    
    try:
        unit_cost = max(0.0, float(data.get("unit_cost", 0.0)))
    except (ValueError, TypeError):
        unit_cost = 0.0
        
    try:
        reorder_threshold = max(0, int(data.get("reorder_threshold", 10)))
    except (ValueError, TypeError):
        reorder_threshold = 10
        
    item_doc = {
        "sku": sku,
        "name": name,
        "category": category,
        "unit_cost": unit_cost,
        "reorder_threshold": reorder_threshold,
        "total_stock": total_stock,
        "warehouses": clean_warehouses,
        "created_at": now,
        "updated_at": now,
    }
    
    try:
        doc_ref.set(item_doc)
        logger.info(f"Created new inventory item '{sku}' (Total Stock: {total_stock}).")

        # Audit Trail: Record stock creation movement
        try:
            record_stock_movement(
                sku=sku,
                item_name=name,
                movement_type="creation",
                quantity_change=total_stock,
                warehouse_code="ALL",
                new_stock=total_stock,
                previous_stock=0,
                actor_id="Inventory Manager",
                reason=f"Registered new SKU in catalog with initial stock of {total_stock} units across regional hubs.",
            )
        except Exception as rec_err:
            logger.warning(f"Could not record creation movement for '{sku}': {rec_err}")

        return item_doc
    except Exception as e:
        logger.error(f"Error creating inventory item '{sku}': {e}")
        raise


def update_manual_stock(sku: str, new_stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manually update stock quantities and/or details for an existing SKU in Firestore.
    
    Args:
        sku: SKU of the inventory item.
        new_stock_data: Dict containing updated 'warehouses' stock levels and/or item attributes.
        
    Returns:
        dict: The updated inventory document.
        
    Raises:
        ValueError: If item is not found or payload is invalid.
    """
    sku = str(sku).strip().upper()
    if not sku:
        raise ValueError("Invalid SKU.")
        
    db = get_db()
    doc_ref = db.collection(COLLECTION_INVENTORY).document(sku)
    
    doc = doc_ref.get()
    if not doc.exists:
        raise ValueError(f"Inventory item with SKU '{sku}' not found.")
        
    item = doc.to_dict()
    warehouses = item.get("warehouses", {})
    
    # Update warehouses stock if provided
    raw_warehouses = new_stock_data.get("warehouses")
    if isinstance(raw_warehouses, dict):
        for wh_code, wh_data in raw_warehouses.items():
            wh_code_clean = str(wh_code).strip().upper()
            if not wh_code_clean:
                continue
            if wh_code_clean not in warehouses:
                warehouses[wh_code_clean] = {
                    "location_name": wh_code_clean,
                    "stock": 0,
                    "bin_shelf": "UNASSIGNED"
                }
            if isinstance(wh_data, dict):
                if "stock" in wh_data:
                    warehouses[wh_code_clean]["stock"] = max(0, int(wh_data["stock"]))
                if "location_name" in wh_data:
                    warehouses[wh_code_clean]["location_name"] = str(wh_data["location_name"]).strip()
                if "bin_shelf" in wh_data:
                    warehouses[wh_code_clean]["bin_shelf"] = str(wh_data["bin_shelf"]).strip()
            else:
                warehouses[wh_code_clean]["stock"] = max(0, int(wh_data or 0))
                
    # Update optional metadata fields if provided
    if "name" in new_stock_data and new_stock_data["name"]:
        item["name"] = str(new_stock_data["name"]).strip()
    if "category" in new_stock_data and new_stock_data["category"]:
        item["category"] = str(new_stock_data["category"]).strip()
    if "unit_cost" in new_stock_data:
        try:
            item["unit_cost"] = max(0.0, float(new_stock_data["unit_cost"]))
        except (ValueError, TypeError):
            pass
    if "reorder_threshold" in new_stock_data:
        try:
            item["reorder_threshold"] = max(0, int(new_stock_data["reorder_threshold"]))
        except (ValueError, TypeError):
            pass
            
    old_stock = int(item.get("total_stock", 0))
    item["warehouses"] = warehouses
    item["total_stock"] = sum(wh.get("stock", 0) for wh in warehouses.values())
    item["updated_at"] = _utc_now()
    
    try:
        doc_ref.set(item, merge=True)
        logger.info(f"Updated manual stock for '{sku}'. New total: {item['total_stock']}")

        # Audit Trail: Record manual adjustment movement
        try:
            delta_stock = item["total_stock"] - old_stock
            record_stock_movement(
                sku=sku,
                item_name=item.get("name", sku),
                movement_type="manual_adjustment",
                quantity_change=delta_stock,
                warehouse_code="MULTI",
                new_stock=item["total_stock"],
                previous_stock=old_stock,
                actor_id="Warehouse Supervisor",
                reason=f"Manual stock levels adjustment via Inventory Command Center ({delta_stock:+d} units net change).",
            )
        except Exception as rec_err:
            logger.warning(f"Could not record manual adjustment movement for '{sku}': {rec_err}")

        return item
    except Exception as e:
        logger.error(f"Error updating stock for '{sku}': {e}")
        raise



# ==============================================================================
# Stock Movement Audit & Analytics Operations
# ==============================================================================

def record_stock_movement(
    sku: str,
    item_name: str,
    movement_type: str,
    quantity_change: int,
    warehouse_code: str,
    new_stock: int,
    previous_stock: Optional[int] = None,
    actor_id: str = "system",
    reason: str = "",
    reference_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Persist an audit trail record of stock movements (additions, deductions, auto-allocations).
    """
    db = get_db()
    now = _utc_now()
    movement_id = f"MOV-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    
    movement_doc = {
        "movement_id": movement_id,
        "sku": sku,
        "item_name": item_name,
        "movement_type": movement_type,  # 'creation', 'manual_adjustment', 'auto_allocation', 'transfer'
        "quantity_change": int(quantity_change),
        "quantity_delta": int(quantity_change),
        "previous_stock": previous_stock,
        "new_stock": int(new_stock),
        "warehouse_code": warehouse_code,
        "actor_id": actor_id,
        "initiated_by": actor_id,
        "reason": reason,
        "notes": reason,
        "reference_id": reference_id,
        "created_at": now,
        "timestamp": now,
    }
    
    try:
        db.collection(COLLECTION_STOCK_MOVEMENTS).document(movement_id).set(movement_doc)
        logger.info(f"Recorded stock movement '{movement_id}' for '{sku}': {quantity_change:+d} units in '{warehouse_code}'.")
    except Exception as e:
        logger.warning(f"Could not record stock movement for '{sku}': {e}")
        
    return movement_doc


def get_inventory_history(
    sku: Optional[str] = None,
    movement_type: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Retrieve chronologically ordered stock movement audit logs."""
    db = get_db()
    try:
        query = db.collection(COLLECTION_STOCK_MOVEMENTS)
        if sku:
            query = query.where(filter=FieldFilter("sku", "==", sku.strip().upper()))
        if movement_type and movement_type.lower() != "all":
            query = query.where(filter=FieldFilter("movement_type", "==", movement_type))
            
        docs = list(query.limit(limit * 2).stream())
        movements = [doc.to_dict() for doc in docs]
        
        # Sort by created_at descending
        def _sort_key(m):
            dt = m.get("created_at")
            if isinstance(dt, datetime):
                return dt
            elif hasattr(dt, "to_datetime"):
                return dt.to_datetime()
            return datetime.min.replace(tzinfo=timezone.utc)
            
        movements.sort(key=_sort_key, reverse=True)
        return serialize_firestore_data(movements[:limit])
    except Exception as e:
        logger.error(f"Error retrieving stock movement history: {e}")
        return []


def get_inventory_analytics() -> Dict[str, Any]:
    """
    Aggregate comprehensive inventory intelligence:
    - Total Catalog Asset Valuation ($)
    - Total Physical Units across Regional Hubs
    - Category-level asset breakdown & share
    - Regional Warehouse capacity & unit distribution
    - Top 5 Highest-Valued SKUs in inventory
    - Critical Reorder Radar (items below safety stock)
    - Recent stock movements activity count
    """
    items = list_inventory(limit=1000)
    
    total_skus = len(items)
    total_units = 0
    total_valuation = 0.0
    
    healthy_count = 0
    low_stock_count = 0
    out_of_stock_count = 0
    
    # Warehouses tracker
    warehouse_stats = {
        "WH-NORTH": {"code": "WH-NORTH", "name": "Chicago Hub", "units": 0, "valuation": 0.0, "sku_count": 0},
        "WH-WEST": {"code": "WH-WEST", "name": "Seattle Hub", "units": 0, "valuation": 0.0, "sku_count": 0},
        "WH-EAST": {"code": "WH-EAST", "name": "New York Hub", "units": 0, "valuation": 0.0, "sku_count": 0},
        "WH-SOUTH": {"code": "WH-SOUTH", "name": "Austin Hub", "units": 0, "valuation": 0.0, "sku_count": 0},
    }
    
    # Categories tracker
    category_stats = {}
    
    # Top assets tracker
    valued_items = []
    critical_reorders = []
    
    for item in items:
        sku = item.get("sku", "UNKNOWN")
        name = item.get("name", sku)
        category = item.get("category", "General")
        unit_cost = float(item.get("unit_cost") or 0.0)
        reorder_level = int(item.get("reorder_threshold") or 10)
        stock = int(item.get("total_stock") or 0)
        item_val = round(stock * unit_cost, 2)
        
        total_units += stock
        total_valuation += item_val
        
        if stock == 0:
            out_of_stock_count += 1
            status = "out_of_stock"
        elif stock <= reorder_level:
            low_stock_count += 1
            status = "low_stock"
        else:
            healthy_count += 1
            status = "in_stock"
            
        if stock <= reorder_level:
            restock_cost = round(max(0, reorder_level - stock) * unit_cost, 2)
            critical_reorders.append({
                "sku": sku,
                "name": name,
                "category": category,
                "current_stock": stock,
                "stock": stock,
                "reorder_threshold": reorder_level,
                "deficit": max(0, reorder_level - stock),
                "unit_cost": unit_cost,
                "estimated_restock_cost": restock_cost,
                "restock_cost": restock_cost,
                "status": status,
            })
            
        valued_items.append({
            "sku": sku,
            "name": name,
            "category": category,
            "total_stock": stock,
            "stock": stock,
            "unit_cost": unit_cost,
            "asset_value": item_val,
        })
        
        # Category aggregation
        if category not in category_stats:
            category_stats[category] = {"name": category, "skus": 0, "units": 0, "valuation": 0.0}
        category_stats[category]["skus"] += 1
        category_stats[category]["units"] += stock
        category_stats[category]["valuation"] += item_val
        
        # Warehouse aggregation
        warehouses = item.get("warehouses", {})
        if isinstance(warehouses, dict):
            for wh_code, wh_data in warehouses.items():
                code = str(wh_code).strip().upper()
                wh_stock = int(wh_data.get("stock", 0) if isinstance(wh_data, dict) else (wh_data or 0))
                wh_name = wh_data.get("location_name", code) if isinstance(wh_data, dict) else code
                
                if code not in warehouse_stats:
                    warehouse_stats[code] = {"code": code, "name": wh_name, "units": 0, "valuation": 0.0, "sku_count": 0}
                warehouse_stats[code]["units"] += wh_stock
                warehouse_stats[code]["valuation"] += round(wh_stock * unit_cost, 2)
                if wh_stock > 0:
                    warehouse_stats[code]["sku_count"] += 1

    # Sort valued items desc
    valued_items.sort(key=lambda x: x["asset_value"], reverse=True)
    top_assets = valued_items[:6]
    
    # Sort critical reorders asc by stock
    critical_reorders.sort(key=lambda x: x["current_stock"])
    
    # Calculate category percentages
    for cat in category_stats.values():
        cat["valuation"] = round(cat["valuation"], 2)
        cat["share_pct"] = round((cat["valuation"] / total_valuation * 100), 1) if total_valuation > 0 else 0.0
        
    for wh in warehouse_stats.values():
        wh["valuation"] = round(wh["valuation"], 2)
        wh["share_pct"] = round((wh["units"] / total_units * 100), 1) if total_units > 0 else 0.0
        
    recent_movements = get_inventory_history(limit=8)
    
    warehouses_list = [
        {
            "hub_code": wh["code"],
            "code": wh["code"],
            "name": wh["name"],
            "units": wh["units"],
            "asset_value": wh["valuation"],
            "valuation": wh["valuation"],
            "percentage": wh["share_pct"],
            "share_pct": wh["share_pct"],
            "sku_count": wh["sku_count"],
        }
        for wh in warehouse_stats.values()
    ]
    
    categories_list = [
        {
            "category": cat["name"],
            "name": cat["name"],
            "sku_count": cat["skus"],
            "skus": cat["skus"],
            "units": cat["units"],
            "asset_value": cat["valuation"],
            "valuation": cat["valuation"],
            "percentage": cat["share_pct"],
            "share_pct": cat["share_pct"],
        }
        for cat in category_stats.values()
    ]
    
    return serialize_firestore_data({
        "summary": {
            "total_skus": total_skus,
            "total_units": total_units,
            "total_asset_value": round(total_valuation, 2),
            "average_unit_cost": round(total_valuation / max(1, total_units), 2),
            "healthy_count": healthy_count,
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "health_ratio_pct": round((healthy_count / max(1, total_skus)) * 100, 1),
        },
        "warehouses": warehouses_list,
        "warehouse_stats": warehouse_stats,
        "categories": categories_list,
        "category_stats": list(category_stats.values()),
        "top_assets": top_assets,
        "critical_reorders": critical_reorders[:10],
        "recent_movements": recent_movements,
    })


# ==============================================================================
# 4. Budget Operations
# ==============================================================================

def upsert_budget(budget_id: str, budget_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create or update a departmental budget.
    Ensures remaining_amount is properly calculated.
    
    Args:
        budget_id: Unique identifier (e.g., "BUD-ENG-2026-Q3").
        budget_data: Budget parameters.
        
    Returns:
        dict: Persisted budget document.
    """
    db = get_db()
    data = budget_data.copy()
    data["budget_id"] = budget_id
    data["updated_at"] = _utc_now()
    
    allocated = float(data.get("allocated_amount", 0.0))
    committed = float(data.get("committed_amount", 0.0))
    spent = float(data.get("spent_amount", 0.0))
    
    # Calculate available/remaining balance
    data["remaining_amount"] = allocated - committed - spent
    data.setdefault("currency", "USD")
    data.setdefault("status", "active" if data["remaining_amount"] >= 0 else "over_budget")
    
    try:
        doc_ref = db.collection(COLLECTION_BUDGETS).document(budget_id)
        doc_ref.set(data, merge=True)
        logger.info(f"Budget '{budget_id}' saved. Remaining: ${data['remaining_amount']:,.2f}")
        return data
    except Exception as e:
        logger.error(f"Error upserting budget '{budget_id}': {e}")
        raise


def get_budget(budget_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a budget document by ID."""
    db = get_db()
    try:
        doc = db.collection(COLLECTION_BUDGETS).document(budget_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error fetching budget '{budget_id}': {e}")
        raise


def list_budgets(
    fiscal_year: Optional[int] = None,
    department: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List budgets with optional filters."""
    db = get_db()
    try:
        query = db.collection(COLLECTION_BUDGETS)
        if fiscal_year:
            query = query.where(filter=FieldFilter("fiscal_year", "==", int(fiscal_year)))
        if department:
            query = query.where(filter=FieldFilter("department", "==", department))
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"Error listing budgets: {e}")
        raise


def check_and_commit_budget(budget_id: str, amount: float, allow_overdraft: bool = False) -> Dict[str, Any]:
    """
    Check if adequate budget remains and commit the requested amount.
    Increases committed_amount and decreases remaining_amount.
    
    Args:
        budget_id: Identifier of the budget.
        amount: Amount to commit.
        allow_overdraft: If True, permits manager/executive override even if amount exceeds remaining headroom.
        
    Returns:
        dict: Updated budget document.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION_BUDGETS).document(budget_id)
    
    try:
        doc = doc_ref.get()
        if not doc.exists:
            # Auto-provision a default departmental budget ledger if not previously created
            parts = budget_id.split("-")
            dept_code = parts[1] if len(parts) >= 2 else "GEN"
            year = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else datetime.now(timezone.utc).year
            quarter = parts[3] if len(parts) >= 4 else "Q3"

            dept_name_map = {
                "ENG": "Engineering",
                "MKT": "Marketing",
                "OPS": "Operations",
                "IT": "IT",
                "FIN": "Finance",
                "HR": "Human Resources",
            }
            dept_name = dept_name_map.get(dept_code, dept_code.capitalize())
            default_allocation = 150000.0 if dept_code in ("ENG", "OPS", "FIN") else 100000.0

            data = {
                "budget_id": budget_id,
                "department": dept_name,
                "fiscal_year": year,
                "quarter": quarter,
                "allocated_amount": default_allocation,
                "committed_amount": 0.0,
                "spent_amount": 0.0,
                "remaining_amount": default_allocation,
                "currency": "USD",
                "status": "active",
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
            doc_ref.set(data)
            logger.info(f"Auto-provisioned default baseline budget of ${default_allocation:,.2f} for '{dept_name}' ({budget_id}).")
        else:
            data = doc.to_dict()

        allocated = float(data.get("allocated_amount", 0.0))
        committed = float(data.get("committed_amount", 0.0))
        spent = float(data.get("spent_amount", 0.0))
        remaining = allocated - committed - spent
        
        if amount > remaining and not allow_overdraft:
            raise ValueError(
                f"Budget overcommit! Requested: ${amount:,.2f}, Remaining: ${remaining:,.2f} "
                f"in budget '{budget_id}'."
            )
            
        new_committed = committed + amount
        new_remaining = allocated - new_committed - spent
        
        updates = {
            "committed_amount": new_committed,
            "remaining_amount": new_remaining,
            "status": "active" if new_remaining >= 0 else "over_budget",
            "updated_at": _utc_now()
        }
        
        doc_ref.update(updates)
        data.update(updates)
        if amount > remaining:
            logger.warning(
                f"Executive Overdraft Authorized: Committed ${amount:,.2f} against remaining ${remaining:,.2f} "
                f"on budget '{budget_id}'. New balance: ${new_remaining:,.2f}"
            )
        else:
            logger.info(f"Committed ${amount:,.2f} to budget '{budget_id}'. New remaining: ${new_remaining:,.2f}")
        return data
    except Exception as e:
        logger.error(f"Error committing budget on '{budget_id}': {e}")
        raise


def deduct_actual_spend(budget_id: str, amount: float) -> Dict[str, Any]:
    """
    Transfer committed amount to actual spent amount upon invoice fulfillment.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION_BUDGETS).document(budget_id)
    
    try:
        doc = doc_ref.get()
        if not doc.exists:
            raise ValueError(f"Budget '{budget_id}' not found.")
            
        data = doc.to_dict()
        committed = max(0.0, float(data.get("committed_amount", 0.0)) - amount)
        spent = float(data.get("spent_amount", 0.0)) + amount
        allocated = float(data.get("allocated_amount", 0.0))
        remaining = allocated - committed - spent
        
        updates = {
            "committed_amount": committed,
            "spent_amount": spent,
            "remaining_amount": remaining,
            "updated_at": _utc_now()
        }
        
        doc_ref.update(updates)
        data.update(updates)
        logger.info(f"Actual spend of ${amount:,.2f} recorded on budget '{budget_id}'.")
        return data
    except Exception as e:
        logger.error(f"Error recording actual spend on '{budget_id}': {e}")
        raise


def rollback_committed_budget(budget_id: str, amount: float) -> Dict[str, Any]:
    """
    Release/refund committed funds from a budget back to remaining headroom
    (e.g., when an approved purchase request is cancelled or rejected).
    
    Args:
        budget_id: Identifier of the budget document in Firestore.
        amount: Amount to refund/decommit.
        
    Returns:
        dict: Updated budget document.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION_BUDGETS).document(budget_id)
    
    try:
        doc = doc_ref.get()
        if not doc.exists:
            logger.warning(f"Budget '{budget_id}' not found during rollback, skipping.")
            return {"budget_id": budget_id, "refunded": 0.0, "status": "skipped"}
            
        data = doc.to_dict()
        allocated = float(data.get("allocated_amount", 0.0))
        committed = float(data.get("committed_amount", 0.0))
        spent = float(data.get("spent_amount", 0.0))
        refund_amount = float(amount)
        
        new_committed = max(0.0, committed - refund_amount)
        new_remaining = allocated - new_committed - spent
        
        updates = {
            "committed_amount": new_committed,
            "remaining_amount": new_remaining,
            "status": "active" if new_remaining >= 0 else "over_budget",
            "updated_at": _utc_now()
        }
        
        doc_ref.update(updates)
        data.update(updates)
        logger.info(f"Refunded ${refund_amount:,.2f} back to budget '{budget_id}'. New remaining: ${new_remaining:,.2f}")
        return data
    except Exception as e:
        logger.error(f"Error rolling back budget on '{budget_id}': {e}")
        raise


def get_dynamic_budget_id(dept_code: str, target_date: Optional[datetime] = None) -> str:
    """
    Dynamically calculate the current year and fiscal quarter (Q1, Q2, Q3, Q4)
    using the datetime module and return the standardized budget document ID string.
    
    Format: BUD-<DEPT_CODE>-<YEAR>-<QUARTER> (e.g. 'BUD-ENG-2026-Q3')
    
    Args:
        dept_code: Department code or name (e.g. 'ENG', 'Engineering', 'IT', 'Operations').
        target_date: Optional datetime (defaults to current UTC datetime).
        
    Returns:
        str: Dynamically calculated budget document ID.
    """
    now = target_date or datetime.now(timezone.utc)
    quarter = f"Q{(now.month - 1) // 3 + 1}"
    year = now.year
    
    clean_code = (dept_code or "").strip().upper()
    dept_map = {
        "ENGINEERING": "ENG",
        "MARKETING": "MKT",
        "OPERATIONS": "OPS",
        "INFORMATION TECHNOLOGY": "IT",
        "IT": "IT",
        "FINANCE": "FIN",
        "HUMAN RESOURCES": "HR",
        "HR": "HR",
    }
    normalized_code = dept_map.get(clean_code, clean_code[:3] if len(clean_code) >= 3 else (clean_code or "GEN"))
    return f"BUD-{normalized_code}-{year}-{quarter}"

