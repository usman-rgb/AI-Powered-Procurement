"""
Budget Routes Blueprint
Handles REST API endpoints for Departmental Budgets, committed spend, and balance tracking.
"""

import logging
from flask import Blueprint, jsonify, request

from app.services.firebase_db import (
    upsert_budget,
    get_budget,
    list_budgets,
    check_and_commit_budget,
    deduct_actual_spend
)

logger = logging.getLogger(__name__)

budget_bp = Blueprint("budgets", __name__, url_prefix="/api/budgets")


@budget_bp.route("", methods=["GET"])
def get_all_budgets():
    """List budgets, optionally filtered by fiscal_year and department."""
    fiscal_year = request.args.get("fiscal_year")
    department = request.args.get("department")

    try:
        budgets = list_budgets(fiscal_year=fiscal_year, department=department)
        return jsonify({"success": True, "count": len(budgets), "data": budgets}), 200
    except Exception as e:
        logger.error(f"Error listing budgets: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@budget_bp.route("/<budget_id>", methods=["GET"])
def get_single_budget(budget_id: str):
    """Retrieve details and remaining balance of a budget."""
    try:
        budget = get_budget(budget_id)
        if not budget:
            return jsonify({"success": False, "error": f"Budget '{budget_id}' not found."}), 404
        return jsonify({"success": True, "data": budget}), 200
    except Exception as e:
        logger.error(f"Error fetching budget '{budget_id}': {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@budget_bp.route("", methods=["POST"])
def post_budget():
    """Create or update a departmental budget."""
    data = request.get_json() or {}
    budget_id = data.get("budget_id")

    if not budget_id:
        return jsonify({"success": False, "error": "Field 'budget_id' is required."}), 400

    try:
        saved = upsert_budget(budget_id, data)
        return jsonify({"success": True, "message": "Budget updated successfully.", "data": saved}), 200
    except Exception as e:
        logger.error(f"Error creating/updating budget '{budget_id}': {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@budget_bp.route("/<budget_id>/commit", methods=["POST"])
def post_commit_budget(budget_id: str):
    """Commit funds from budget for an approved purchase request."""
    data = request.get_json() or {}
    amount = data.get("amount")
    allow_overdraft = bool(data.get("allow_overdraft") or data.get("override_budget"))

    if amount is None or float(amount) <= 0:
        return jsonify({"success": False, "error": "Field 'amount' must be greater than 0."}), 400

    try:
        updated = check_and_commit_budget(budget_id, float(amount), allow_overdraft=allow_overdraft)
        return jsonify({"success": True, "message": f"${float(amount):,.2f} committed successfully.", "data": updated}), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error committing to budget '{budget_id}': {e}")
        return jsonify({"success": False, "error": str(e)}), 500
