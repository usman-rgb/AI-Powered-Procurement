"""
Procurement Routes Blueprint
Handles REST API endpoints for Purchase Requests, status approvals, and AI assessments.
"""

import logging
from flask import Blueprint, jsonify, request

from app.services.firebase_db import (
    create_purchase_request,
    get_purchase_request,
    update_purchase_request_status,
    list_purchase_requests,
    update_ai_risk_assessment,
    check_and_commit_budget,
    rollback_committed_budget,
    get_dynamic_budget_id,
    auto_allocate_inventory,
)
from app.services.validation_engine import ValidationEngine, run_pre_ai_validation
from app.services.ai_decision_service import evaluate_and_update_firestore_request
from app.routes.auth_routes import login_required

logger = logging.getLogger(__name__)

procurement_bp = Blueprint("procurement", __name__, url_prefix="/api/procurement")


@procurement_bp.route("/requests", methods=["GET"])
@login_required
def get_requests():
    """List purchase requests with query parameters (department, status, requester_id)."""
    department = request.args.get("department")
    status = request.args.get("status")
    requester_id = request.args.get("requester_id")
    limit = int(request.args.get("limit", 50))

    try:
        results = list_purchase_requests(
            department=department,
            status=status,
            requester_id=requester_id,
            limit=limit
        )
        return jsonify({"success": True, "count": len(results), "data": results}), 200
    except Exception as e:
        logger.error(f"Error in GET /api/procurement/requests: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procurement_bp.route("/requests", methods=["POST"])
@login_required
def post_request():
    """Create a new purchase request."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Request body must be JSON."}), 400

    required_fields = ["title", "requester_id", "department", "items"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"success": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        created = create_purchase_request(data)
        return jsonify({"success": True, "message": "Purchase request created.", "data": created}), 201
    except Exception as e:
        logger.error(f"Error creating purchase request: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procurement_bp.route("/requests/<request_id>", methods=["GET"])
def get_single_request(request_id: str):
    """Retrieve a purchase request by ID."""
    try:
        pr = get_purchase_request(request_id)
        if not pr:
            return jsonify({"success": False, "error": f"Purchase request '{request_id}' not found."}), 404
        return jsonify({"success": True, "data": pr}), 200
    except Exception as e:
        logger.error(f"Error fetching request '{request_id}': {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procurement_bp.route("/requests/<request_id>/status", methods=["PATCH", "POST"])
@login_required
def update_status(request_id: str):
    """
    Update status of a purchase request (approve, reject, hold, etc.).
    - When set to 'approved':
      - If AI decision was 'REDUCE', auto-allocates available stock from warehouses.
      - Dynamically calculates budget ID and commits external funds via check_and_commit_budget.
    - When set to 'rejected' from a previously approved request, rolls back/refunds the committed amount.
    """
    data = request.get_json() or {}
    new_status = data.get("status")
    actor_id = data.get("actor_id", "system")
    comment = data.get("comment", "")
    override_budget = bool(data.get("override_budget") or data.get("allow_overdraft"))

    valid_statuses = {
        "draft", "submitted", "approved", "rejected", "fulfilled", "cancelled",
        "hold", "on_hold", "investigating", "pending validation"
    }
    status_lower = new_status.strip().lower() if new_status else ""
    if not status_lower or status_lower not in valid_statuses:
        return jsonify({
            "success": False,
            "error": f"Invalid status '{new_status}'. Allowed values: {', '.join(sorted(valid_statuses))}"
        }), 400

    try:
        # 1. Fetch current purchase request from Firestore
        pr = get_purchase_request(request_id)
        if not pr:
            return jsonify({"success": False, "error": f"Purchase request '{request_id}' not found."}), 404

        old_status = (pr.get("status") or "").strip().lower()
        department = pr.get("department") or "Engineering"
        total_cost = float(pr.get("total_amount") or 0.0)
        if total_cost <= 0.0 and "items" in pr and pr["items"]:
            total_cost = sum(
                float(item.get("total_price", float(item.get("quantity", 0)) * float(item.get("unit_price", 0.0))))
                for item in pr["items"]
            )

        # 2. Dynamically calculate the budget ID based on department and current quarter
        budget_id = get_dynamic_budget_id(department)

        budget_action_note = None
        inventory_action_note = None

        # 3. Handle 'approved' status
        if status_lower == "approved":
            # Only process commitment / allocation if not already in approved state
            if old_status not in ("approved", "approved by ai"):
                ai_decision = pr.get("ai_decision") or {}
                ai_decision_action = (ai_decision.get("Decision") or "").strip().upper()

                # Automated Inventory Stock Allocation if AI recommended REDUCE
                if ai_decision_action == "REDUCE":
                    items = pr.get("items", [])
                    sku = (items[0].get("sku") if items else pr.get("sku") or "").strip()
                    requested_qty = int(items[0].get("quantity") if items else pr.get("quantity") or 1)

                    if sku:
                        try:
                            alloc_res = auto_allocate_inventory(sku, requested_qty)
                            allocated_units = alloc_res.get("quantity_allocated", 0)
                            wh_details = ", ".join([f"{a['location_name']} ({a['allocated_qty']}u)" for a in alloc_res.get("allocations", [])])
                            inventory_action_note = f"Auto-allocated {allocated_units} unit(s) from {wh_details} for SKU '{sku}'."
                            logger.info(f"Request '{request_id}': {inventory_action_note}")

                            # Calculate external cost to commit (reducing by internal inventory value)
                            unit_price = float(items[0].get("unit_price") if items else (total_cost / max(1, requested_qty)))
                            saved_amount = float(ai_decision.get("Estimated_Savings") or (allocated_units * unit_price))
                            external_cost_to_commit = max(0.0, total_cost - saved_amount)
                        except Exception as inv_err:
                            logger.warning(f"Inventory auto-allocation failed for '{request_id}': {inv_err}")
                            inventory_action_note = f"Inventory allocation notice: {str(inv_err)}"
                            external_cost_to_commit = total_cost
                    else:
                        external_cost_to_commit = total_cost
                else:
                    external_cost_to_commit = total_cost

                # Commit external budget amount (if any external spend remains)
                if external_cost_to_commit > 0:
                    try:
                        check_and_commit_budget(budget_id, external_cost_to_commit, allow_overdraft=override_budget)
                        budget_action_note = f"Committed ${external_cost_to_commit:,.2f} to budget '{budget_id}'."
                        if ai_decision_action == "REDUCE":
                            budget_action_note += f" (Reduced from ${total_cost:,.2f} via warehouse transfer)"
                        if override_budget:
                            budget_action_note += " [Executive Manager Overdraft Authorized]"
                        logger.info(f"Request '{request_id}': {budget_action_note}")
                    except ValueError as ve:
                        # Budget overdraft or not found -> block approval with 400 error
                        logger.warning(f"Failed to commit budget for request '{request_id}': {ve}")
                        return jsonify({
                            "success": False,
                            "error": f"Budget approval failed: {str(ve)}",
                            "requires_override": True,
                            "budget_id": budget_id,
                            "requested_amount": external_cost_to_commit
                        }), 400
                else:
                    budget_action_note = f"External budget commit avoided ($0.00): 100% fulfilled via internal warehouse transfer."
                    logger.info(f"Request '{request_id}': {budget_action_note}")

        # 4. Handle 'rejected' status -> Rollback/refund if previously approved
        elif status_lower == "rejected":
            if old_status in ("approved", "approved by ai"):
                try:
                    rollback_committed_budget(budget_id, total_cost)
                    budget_action_note = f"Refunded ${total_cost:,.2f} back to budget '{budget_id}'."
                    logger.info(f"Request '{request_id}': {budget_action_note}")
                except Exception as re_err:
                    logger.warning(f"Could not refund budget '{budget_id}' on rejection: {re_err}")
                    budget_action_note = f"Budget rollback warning: {str(re_err)}"

        # 5. Append action notes to comment if present
        notes = [n for n in [inventory_action_note, budget_action_note] if n]
        if notes:
            summary_notes = "; ".join(notes)
            full_comment = f"{comment} ({summary_notes})" if comment else summary_notes
        else:
            full_comment = comment

        # 6. Update status in Purchase_Requests collection and append approval trail
        updated = update_purchase_request_status(
            request_id=request_id,
            new_status=new_status,
            actor_id=actor_id,
            comment=full_comment
        )

        return jsonify({
            "success": True,
            "message": f"Status updated to '{new_status}'.",
            "budget_id": budget_id,
            "budget_action": budget_action_note,
            "inventory_action": inventory_action_note,
            "data": updated
        }), 200

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 404
    except Exception as e:
        logger.error(f"Error updating status for '{request_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# Alias for backward compatibility
patch_status = update_status


@procurement_bp.route("/requests/<request_id>/ai-assessment", methods=["POST"])
@login_required
def post_ai_assessment(request_id: str):
    """Record an AI risk score and evaluation notes."""
    data = request.get_json() or {}
    risk_score = data.get("risk_score")
    notes = data.get("notes", "")

    if risk_score is None:
        return jsonify({"success": False, "error": "Field 'risk_score' (float between 0.0 and 1.0) is required."}), 400

    try:
        update_ai_risk_assessment(request_id, float(risk_score), notes)
        return jsonify({"success": True, "message": "AI assessment saved successfully."}), 200
    except Exception as e:
        logger.error(f"Error updating AI assessment: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@procurement_bp.route("/validate", methods=["POST"])
def post_validate_request():
    """
    Execute the 4-layer validation engine on a purchase request payload.
    Payload: { item_name, sku, quantity, estimated_price, department, [request_id] }
    """
    data = request.get_json() or {}
    if not data:
        return jsonify({"success": False, "error": "Request body must be JSON."}), 400

    try:
        engine = ValidationEngine()
        report = engine.validate_request_payload(data, request_id=data.get("request_id"))
        return jsonify({"success": True, "validation_report": report.to_dict()}), 200
    except Exception as e:
        logger.error(f"Error validating request payload: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@procurement_bp.route("/validate/<request_id>", methods=["GET"])
def get_validate_existing_request(request_id: str):
    """
    Run the 4-layer validation engine on an existing purchase request stored in Firestore.
    """
    try:
        engine = ValidationEngine()
        report = engine.validate_existing_request(request_id)
        return jsonify({"success": True, "validation_report": report.to_dict()}), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 404
    except Exception as e:
        logger.error(f"Error validating existing request '{request_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@procurement_bp.route("/requests/<request_id>/ai-decision", methods=["POST"])
@login_required
def post_trigger_ai_decision(request_id: str):
    """
    Trigger the AI Decision Service (Groq/Grok LLM) for a purchase request.
    Executes the 4-layer validation engine, builds dynamic prompt, calls LLM,
    and updates the Firestore document with the AI's structured decision.
    """
    try:
        result = evaluate_and_update_firestore_request(request_id)
        return jsonify({
            "success": True,
            "message": f"AI evaluation completed: {result['ai_decision']['Decision']}",
            "request_id": request_id,
            "ai_decision": result["ai_decision"],
            "new_status": result["new_status"],
            "validation_report": result["validation_report"]
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 404
    except Exception as e:
        logger.error(f"Error in AI decision service for '{request_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


