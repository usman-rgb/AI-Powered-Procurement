"""
Main Routes Blueprint
Serves the web dashboard, system overview, and API health checks.
"""

import logging
import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, render_template, request, session

from app.services.firebase_init import (
    is_firebase_initialized, 
    get_db, 
    FirebaseInitializationError
)
from app.services.firebase_db import (
    list_purchase_requests,
    list_inventory,
    get_low_stock_items,
    list_budgets,
    list_users,
    get_dynamic_budget_id
)
from app.services.validation_engine import ValidationEngine
from app.services.ai_decision_service import evaluate_and_update_firestore_request
from app.routes.auth_routes import login_required

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)


@main_bp.route("/", methods=["GET"])
@main_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    """Render the Purchase Manager Dashboard & Explainable AI Decision Center."""
    firebase_connected = is_firebase_initialized()
    return render_template("dashboard.html", firebase_connected=firebase_connected)


@main_bp.route("/inventory", methods=["GET"])
@main_bp.route("/inventory-management", methods=["GET"])
@login_required
def inventory_management_page():
    """Render the Manual Inventory Management Module & Stock Editor."""
    firebase_connected = is_firebase_initialized()
    initial_tab = request.args.get("tab", "catalog")
    return render_template("inventory_management.html", firebase_connected=firebase_connected, initial_tab=initial_tab)


@main_bp.route("/analytics", methods=["GET"])
@login_required
def analytics_page():
    """Render the Inventory Analytics, Asset Valuation, and Real-Time Graphs Command Center."""
    firebase_connected = is_firebase_initialized()
    return render_template("inventory_management.html", firebase_connected=firebase_connected, initial_tab="analytics")


@main_bp.route("/history", methods=["GET"])
@main_bp.route("/audit-trail", methods=["GET"])
@login_required
def history_page():
    """Render the Stock Movement Audit Trail page."""
    firebase_connected = is_firebase_initialized()
    return render_template("inventory_management.html", firebase_connected=firebase_connected, initial_tab="history")


@main_bp.route("/overview", methods=["GET"])
@login_required
def overview_page():
    """Render the high-level procurement command center (budgets & multi-warehouse)."""
    firebase_connected = False
    stats = {
        "total_requests": 0,
        "pending_approval": 0,
        "low_stock_count": 0,
        "total_budget": 0.0,
        "committed_budget": 0.0,
        "spent_budget": 0.0,
        "remaining_budget": 0.0,
    }
    recent_requests = []
    low_stock_items = []
    budgets = []
    users = []

    try:
        db = get_db()
        firebase_connected = True

        requests = list_purchase_requests(limit=10)
        recent_requests = requests
        stats["total_requests"] = len(requests)
        stats["pending_approval"] = sum(1 for r in requests if r.get("status") == "submitted")

        low_stock_items = get_low_stock_items()
        stats["low_stock_count"] = len(low_stock_items)

        budgets = list_budgets()
        stats["total_budget"] = sum(b.get("allocated_amount", 0.0) for b in budgets)
        stats["committed_budget"] = sum(b.get("committed_amount", 0.0) for b in budgets)
        stats["spent_budget"] = sum(b.get("spent_amount", 0.0) for b in budgets)
        stats["remaining_budget"] = sum(b.get("remaining_amount", 0.0) for b in budgets)

        users = list_users(limit=10)
    except Exception as e:
        logger.warning(f"Overview loaded with offline/uninitialized state: {e}")

    return render_template(
        "index.html",
        firebase_connected=firebase_connected,
        stats=stats,
        recent_requests=recent_requests,
        low_stock_items=low_stock_items,
        budgets=budgets,
        users=users
    )


@main_bp.route("/system-health", methods=["GET"])
def system_health_page():
    """Render the interactive System Health & AI Engine Diagnostics Command Center."""
    import os
    firebase_connected = is_firebase_initialized()
    project_id = os.getenv("FIREBASE_PROJECT_ID", "procureai-c4588")
    server_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    llm_model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    groq_configured = bool(os.getenv("GROQ_API_KEY"))

    return render_template(
        "system_health.html",
        firebase_connected=firebase_connected,
        project_id=project_id,
        llm_model=llm_model,
        groq_configured=groq_configured,
        server_time=server_time
    )


@main_bp.route("/api/health", methods=["GET"])
def health_check():
    """
    API Health Check endpoint.
    Tests if the Flask application and Firebase Firestore connection are operational.
    If requested by a browser (Accept: text/html and not format=json),
    renders the rich system diagnostics UI. Otherwise returns JSON.
    """
    format_param = request.args.get("format", "").lower()
    accepts_html = "text/html" in request.headers.get("Accept", "")

    if format_param == "html" or (accepts_html and format_param != "json"):
        return system_health_page()

    status = {
        "status": "healthy",
        "app": "AI-Powered Procurement Backend",
        "firebase_connected": False,
        "details": {}
    }
    try:
        db = get_db()
        status["firebase_connected"] = True
        status["details"]["message"] = "Connected to Google Cloud Firestore successfully."
        return jsonify(status), 200
    except Exception as e:
        status["status"] = "degraded"
        status["firebase_connected"] = False
        status["details"]["error"] = str(e)
        return jsonify(status), 503


@main_bp.route("/submit-request", methods=["GET"])
@login_required
def submit_request_page():
    """Render the Purchase Request submission form page."""
    firebase_connected = is_firebase_initialized()
    return render_template("request_form.html", firebase_connected=firebase_connected)


@main_bp.route("/api/submit_request", methods=["POST"])
@login_required
def submit_request_api():
    """
    Handle AJAX Purchase Request submission.
    Validates input, generates a unique PR ID, saves to Firestore 'Purchase_Requests'
    with status 'Pending Validation', and returns a JSON response.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Request body must be valid JSON."}), 400

    # 1. Validation of required fields
    required_fields = [
        "item_name",
        "sku",
        "category",
        "quantity",
        "estimated_price",
        "required_date",
        "department",
        "purpose",
    ]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({
            "success": False,
            "error": f"Missing required fields: {', '.join(missing)}"
        }), 400

    try:
        qty = int(data["quantity"])
        if qty < 1:
            raise ValueError("Quantity must be at least 1 unit.")
    except (ValueError, TypeError) as ve:
        return jsonify({"success": False, "error": f"Invalid quantity: {ve}"}), 400

    try:
        price = float(data["estimated_price"])
        if price <= 0:
            raise ValueError("Estimated price must be greater than $0.00.")
    except (ValueError, TypeError) as ve:
        return jsonify({"success": False, "error": f"Invalid price: {ve}"}), 400

    total_amount = round(qty * price, 2)
    now = datetime.now(timezone.utc)

    # 2. Generate a unique, professional PR ID (e.g. PR-202609-A1B2C3)
    pr_id = f"PR-{now.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

    # 3. Construct the Purchase_Requests Firestore document
    department = data["department"].strip()
    dept_code = department[:3].upper() if len(department) >= 3 else "GEN"
    requester_name = (
        data.get("requester_name", "").strip()
        or session.get("user_name")
        or session.get("user_email")
        or "Authenticated Requester"
    )
    requester_id = (
        data.get("requester_id", "").strip()
        or session.get("user_id")
        or session.get("user_email")
        or f"USR-{uuid.uuid4().hex[:6].upper()}"
    )

    request_doc = {
        "request_id": pr_id,
        "title": f"{data['item_name'].strip()} ({data['sku'].strip()})",
        "requester_id": requester_id,
        "requester_name": requester_name,
        "department": department,
        "category": data["category"].strip(),
        "items": [
            {
                "sku": data["sku"].strip(),
                "item_name": data["item_name"].strip(),
                "category": data["category"].strip(),
                "quantity": qty,
                "unit_price": price,
                "total_price": total_amount,
            }
        ],
        "total_amount": total_amount,
        "currency": "USD",
        "required_date": data["required_date"],
        "purpose": data["purpose"].strip(),
        "priority": data.get("priority", "medium"),
        "status": "Pending Validation",  # Set to 'Pending Validation' per specification
        "budget_id": get_dynamic_budget_id(department),
        "ai_risk_score": 0.0,
        "ai_notes": "Queued for automated AI price variance validation and policy audit.",
        "approval_trail": [
            {
                "step": "Submission",
                "actor_id": requester_name,
                "decision": "Submitted for validation",
                "comment": data["purpose"].strip(),
                "timestamp": now,
            }
        ],
        "created_at": now,
        "updated_at": now,
    }

    # 4. Save to Firebase Firestore & Run 4-Layer Validation Pipeline
    try:
        db = get_db()
        validation_report = None

        # Execute 4-Layer Pre-AI Validation Engine
        try:
            engine = ValidationEngine(db)
            report_obj = engine.validate_request_payload(request_doc, request_id=pr_id)
            validation_report = report_obj.to_dict()
            request_doc["validation_report"] = validation_report
            request_doc["ai_notes"] = report_obj.ai_context_summary

            # Assign preliminary risk score based on rule violations
            if report_obj.overall_status == "FAILED":
                request_doc["ai_risk_score"] = 0.85
            elif report_obj.overall_status == "WARNINGS":
                request_doc["ai_risk_score"] = 0.45
            else:
                request_doc["ai_risk_score"] = 0.05

            logger.info(f"Pre-AI Validation for '{pr_id}': Status = {report_obj.overall_status}")
        except Exception as ve_err:
            logger.warning(f"Pre-AI Validation non-fatal error on '{pr_id}': {ve_err}", exc_info=True)

        db.collection("Purchase_Requests").document(pr_id).set(request_doc)
        logger.info(f"Purchase Request '{pr_id}' successfully saved to Firestore with status 'Pending Validation'.")

        return jsonify({
            "success": True,
            "message": "Purchase request submitted and pre-AI validation completed successfully.",
            "pr_id": pr_id,
            "validation_report": validation_report,
            "data": {
                "request_id": pr_id,
                "title": request_doc["title"],
                "total_amount": total_amount,
                "status": request_doc["status"],
                "ai_risk_score": request_doc.get("ai_risk_score", 0.0),
                "created_at": now.isoformat(),
            }
        }), 201

    except FirebaseInitializationError as fie:
        logger.warning(f"Firebase credentials not active when submitting '{pr_id}': {fie}")
        return jsonify({
            "success": False,
            "error": "Firebase Firestore credentials not configured. Please place 'serviceAccountKey.json' in the project directory."
        }), 503
    except Exception as e:
        logger.error(f"Error persisting purchase request '{pr_id}' to Firestore: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Failed to save purchase request to Firestore: {str(e)}"
        }), 500


@main_bp.route("/api/ai_decision/<request_id>", methods=["POST"])
@login_required
def trigger_ai_decision_api(request_id: str):
    """
    Trigger the AI Decision Service for a given purchase request.
    Evaluates 4 validation layers, queries Groq/Grok LLM, and updates Firestore.
    """
    try:
        result = evaluate_and_update_firestore_request(request_id)
        return jsonify({
            "success": True,
            "message": f"AI Decision generated: {result['ai_decision']['Decision']}",
            "request_id": request_id,
            "ai_decision": result["ai_decision"],
            "new_status": result["new_status"],
            "validation_report": result["validation_report"]
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 404
    except Exception as e:
        logger.error(f"Error executing AI decision on '{request_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


