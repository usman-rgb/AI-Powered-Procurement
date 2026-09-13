"""
Inventory Routes Blueprint
Handles REST API endpoints for Multi-Warehouse inventory management, stock adjustments, and reorder alerts.
"""

import logging
from flask import Blueprint, jsonify, request

from app.services.firebase_db import (
    upsert_inventory_item,
    get_inventory_item,
    update_warehouse_stock,
    list_inventory,
    get_low_stock_items,
    get_all_inventory,
    add_new_inventory_item,
    update_manual_stock,
    get_inventory_history,
    get_inventory_analytics,
)

logger = logging.getLogger(__name__)

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


@inventory_bp.route("", methods=["GET"])
def get_inventory_items():
    """List inventory items, optionally filtered by category."""
    category = request.args.get("category")
    limit = int(request.args.get("limit", 500))

    try:
        items = get_all_inventory(category=category, limit=limit)
        return jsonify({"success": True, "count": len(items), "data": items}), 200
    except Exception as e:
        logger.error(f"Error in GET /api/inventory: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("", methods=["POST"])
def post_inventory_item():
    """
    Accept data from the 'Add Item Modal' and create a new document in Firebase.
    """
    data = request.get_json() or {}
    try:
        new_item = add_new_inventory_item(data)
        return jsonify({
            "success": True,
            "message": f"Inventory item '{new_item['sku']}' created successfully.",
            "data": new_item
        }), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error creating inventory item: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/analytics", methods=["GET"])
def get_inventory_analytics_api():
    """Retrieve full inventory analytics, asset valuation, and warehouse distribution."""
    try:
        analytics = get_inventory_analytics()
        return jsonify({"success": True, "data": analytics}), 200
    except Exception as e:
        logger.error(f"Error generating inventory analytics: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/history", methods=["GET"])
def get_inventory_history_api():
    """Retrieve stock movement history across all regional warehouses."""
    sku = request.args.get("sku")
    movement_type = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    
    try:
        history = get_inventory_history(sku=sku, movement_type=movement_type, limit=limit)
        return jsonify({"success": True, "count": len(history), "data": history}), 200
    except Exception as e:
        logger.error(f"Error fetching stock movement history: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/alerts/low-stock", methods=["GET"])
def get_alerts_low_stock():
    """Get items currently below their reorder threshold."""
    try:
        alerts = get_low_stock_items()
        return jsonify({"success": True, "count": len(alerts), "data": alerts}), 200
    except Exception as e:
        logger.error(f"Error checking low stock items: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/<sku>", methods=["GET"])
def get_single_item(sku: str):
    """Retrieve an item's detail along with its multi-warehouse breakdown."""
    try:
        item = get_inventory_item(sku)
        if not item:
            return jsonify({"success": False, "error": f"Item with SKU '{sku}' not found."}), 404
        return jsonify({"success": True, "data": item}), 200
    except Exception as e:
        logger.error(f"Error fetching SKU '{sku}': {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/<sku>/history", methods=["GET"])
def get_sku_history_api(sku: str):
    """Retrieve stock movement timeline for a specific item SKU."""
    limit = int(request.args.get("limit", 50))
    try:
        history = get_inventory_history(sku=sku, limit=limit)
        return jsonify({
            "success": True,
            "sku": sku,
            "count": len(history),
            "data": history
        }), 200
    except Exception as e:
        logger.error(f"Error fetching history for SKU '{sku}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/<sku>", methods=["PUT"])
def put_inventory_item(sku: str):
    """
    Accept updated warehouse quantities and item attributes from 'Edit Stock Modal'
    and update the specific document in Firebase.
    """
    data = request.get_json() or {}
    try:
        updated = update_manual_stock(sku, data)
        return jsonify({
            "success": True,
            "message": f"Inventory item '{sku}' updated successfully.",
            "data": updated
        }), 200
    except ValueError as ve:
        status_code = 404 if "not found" in str(ve).lower() else 400
        return jsonify({"success": False, "error": str(ve)}), status_code
    except Exception as e:
        logger.error(f"Error updating inventory item '{sku}': {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@inventory_bp.route("/<sku>/stock-adjustment", methods=["POST"])
def post_stock_adjustment(sku: str):
    """
    Adjust stock at a specific warehouse location.
    Payload:
    {
        "warehouse_code": "WH-NORTH",
        "delta_qty": 5,        # positive to add, negative to deduct
        "location_name": "Chicago Hub",
        "bin_shelf": "A-01-2"
    }
    """
    data = request.get_json() or {}
    warehouse_code = data.get("warehouse_code")
    delta_qty = data.get("delta_qty")
    location_name = data.get("location_name")
    bin_shelf = data.get("bin_shelf")

    if not warehouse_code or delta_qty is None:
        return jsonify({
            "success": False,
            "error": "Both 'warehouse_code' and integer 'delta_qty' are required."
        }), 400

    try:
        updated = update_warehouse_stock(
            sku=sku,
            warehouse_code=warehouse_code,
            delta_qty=int(delta_qty),
            location_name=location_name,
            bin_shelf=bin_shelf
        )
        return jsonify({
            "success": True,
            "message": f"Stock adjusted for SKU '{sku}' in warehouse '{warehouse_code}'.",
            "data": updated
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error adjusting stock for '{sku}': {e}")
        return jsonify({"success": False, "error": str(e)}), 500
