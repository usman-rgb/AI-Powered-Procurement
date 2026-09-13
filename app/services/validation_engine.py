"""
Procurement Validation Engine (validation_engine.py)
--------------------------------------------------------------------------------
Architectural Role:
Serves as the Pre-AI Deterministic Rule & Validation Pipeline for incoming
Purchase Requests before forwarding context to the LLM / AI Screening Agent.

Executes 4 Sequential Verification Layers against Google Cloud Firestore:
- Layer 1 (Budget Check): Compares (Quantity * Price) against Department Budget.
- Layer 2 (Multi-Warehouse Stock): Checks idle stock across regional warehouse hubs.
- Layer 3 (Duplicate PR Detector): Scans for identical / overlapping PRs in last 30 days.
- Layer 4 (Historical Usage Anomaly): Computes monthly baseline run-rate vs requested volume.

Returns a standardized compiled JSON payload (PASSED, WARNINGS, FAILED) structured
for immediate consumption by the AI Reasoning Engine.
--------------------------------------------------------------------------------
"""

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path for standalone script execution
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.services.firebase_init import get_db
from app.services.firebase_db import (
    COLLECTION_BUDGETS,
    COLLECTION_INVENTORY,
    COLLECTION_REQUESTS,
    COLLECTION_USERS,
)

logger = logging.getLogger("validation_engine")


@dataclass
class LayerResult:
    """Individual validation layer outcome."""
    layer_name: str
    status: str  # "PASSED", "WARNING", "FAILED"
    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Compiled validation context payload for the AI Engine."""
    request_id: str
    item_name: str
    sku: str
    department: str
    quantity: int
    estimated_price: float
    total_amount: float
    overall_status: str  # "PASSED", "WARNINGS", "FAILED"
    flags_count: Dict[str, int]
    layers: Dict[str, Dict[str, Any]]
    ai_context_summary: str
    suggested_ai_action: str
    evaluated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ValidationEngine:
    """
    Deterministic 4-Layer Verification Engine for Purchase Requests.
    """

    def __init__(self, db: Optional[firestore.Client] = None):
        self.db = db or get_db()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ==========================================================================
    # LAYER 1: Departmental Budget Check
    # ==========================================================================
    def check_department_budget(
        self,
        department: str,
        total_amount: float,
        fiscal_year: Optional[int] = None
    ) -> LayerResult:
        """
        Verify whether the requesting department has sufficient uncommitted budget.
        """
        fy = fiscal_year or self._now().year
        try:
            # Query active budgets for department and current fiscal year
            query = (
                self.db.collection(COLLECTION_BUDGETS)
                .where(filter=FieldFilter("department", "==", department))
                .where(filter=FieldFilter("fiscal_year", "==", fy))
            )
            docs = list(query.stream())

            if not docs:
                # Fallback search by department name only
                docs = list(
                    self.db.collection(COLLECTION_BUDGETS)
                    .where(filter=FieldFilter("department", "==", department))
                    .stream()
                )

            if not docs:
                return LayerResult(
                    layer_name="Layer 1: Budget Check",
                    status="WARNING",
                    title="No Explicit Budget Found",
                    message=f"No active budget record exists for '{department}' in FY{fy}. Manual finance review required.",
                    details={"department": department, "total_requested": total_amount, "available_budget": 0.0}
                )

            # Prioritize current active quarter budget
            budget_data = docs[0].to_dict()
            budget_id = budget_data.get("budget_id", "UNKNOWN")
            allocated = float(budget_data.get("allocated_amount", 0.0))
            committed = float(budget_data.get("committed_amount", 0.0))
            spent = float(budget_data.get("spent_amount", 0.0))
            remaining = float(budget_data.get("remaining_amount", allocated - committed - spent))

            utilization_pct = round(((spent + committed) / allocated * 100), 1) if allocated > 0 else 100.0
            new_remaining = remaining - total_amount
            req_utilization_pct = round((total_amount / allocated * 100), 1) if allocated > 0 else 100.0

            details = {
                "budget_id": budget_id,
                "department": department,
                "allocated_amount": allocated,
                "committed_amount": committed,
                "spent_amount": spent,
                "remaining_amount": remaining,
                "total_requested": total_amount,
                "projected_remaining": new_remaining,
                "current_utilization_pct": utilization_pct,
                "request_cost_pct_of_budget": req_utilization_pct,
            }

            # Hard Failure: Request exceeds remaining budget
            if total_amount > remaining:
                overdraft = total_amount - remaining
                return LayerResult(
                    layer_name="Layer 1: Budget Check",
                    status="FAILED",
                    title="Budget Overdraft Exceeded",
                    message=(
                        f"Requested amount (${total_amount:,.2f}) exceeds remaining departmental budget "
                        f"(${remaining:,.2f}) by ${overdraft:,.2f} in budget '{budget_id}'."
                    ),
                    details=details
                )

            # Warning: Request consumes more than 60% of available headroom or current utilization > 85%
            if remaining > 0 and (total_amount / remaining >= 0.6 or utilization_pct >= 85.0):
                return LayerResult(
                    layer_name="Layer 1: Budget Check",
                    status="WARNING",
                    title="High Budget Consumption",
                    message=(
                        f"Request will consume {round((total_amount / remaining) * 100, 1)}% of remaining available "
                        f"budget (${remaining:,.2f}) in '{budget_id}'."
                    ),
                    details=details
                )

            # Passed
            return LayerResult(
                layer_name="Layer 1: Budget Check",
                status="PASSED",
                title="Budget Verified",
                message=(
                    f"Sufficient budget available (${remaining:,.2f} remaining). "
                    f"Request of ${total_amount:,.2f} leaves ${new_remaining:,.2f} available."
                ),
                details=details
            )

        except Exception as e:
            logger.error(f"Layer 1 error: {e}", exc_info=True)
            return LayerResult(
                layer_name="Layer 1: Budget Check",
                status="WARNING",
                title="Budget Query Error",
                message=f"Could not verify department budget due to database error: {str(e)}",
                details={"error": str(e)}
            )

    # ==========================================================================
    # LAYER 2: Multi-Warehouse Idle Stock Check
    # ==========================================================================
    def check_warehouse_inventory(
        self,
        sku: str,
        requested_quantity: int
    ) -> LayerResult:
        """
        Inspect the multi-warehouse inventory collection to identify idle stock
        sitting in other fulfillment hubs.
        """
        try:
            doc = self.db.collection(COLLECTION_INVENTORY).document(sku).get()
            
            if not doc.exists:
                return LayerResult(
                    layer_name="Layer 2: Multi-Warehouse Stock",
                    status="PASSED",
                    title="No Internal Inventory Found",
                    message=f"SKU '{sku}' is not currently stocked in internal warehouses. External purchase is required.",
                    details={"sku": sku, "total_internal_stock": 0, "warehouses": {}}
                )

            inv_data = doc.to_dict()
            total_stock = int(inv_data.get("total_stock", 0))
            reorder_threshold = int(inv_data.get("reorder_threshold", 10))
            warehouses = inv_data.get("warehouses", {})

            # Identify hubs with idle available stock
            idle_locations = []
            for wh_code, wh_info in warehouses.items():
                stock = int(wh_info.get("stock", 0))
                if stock > 0:
                    idle_locations.append({
                        "warehouse_code": wh_code,
                        "location_name": wh_info.get("location_name", wh_code),
                        "available_stock": stock,
                        "bin_shelf": wh_info.get("bin_shelf", "UNASSIGNED")
                    })

            details = {
                "sku": sku,
                "item_name": inv_data.get("name", sku),
                "total_internal_stock": total_stock,
                "reorder_threshold": reorder_threshold,
                "requested_quantity": requested_quantity,
                "idle_locations": idle_locations
            }

            # Case A: Full internal fulfillment possible from idle warehouse stock!
            if total_stock >= requested_quantity:
                locations_summary = ", ".join([f"{loc['location_name']}: {loc['available_stock']} units" for loc in idle_locations])
                return LayerResult(
                    layer_name="Layer 2: Multi-Warehouse Stock",
                    status="WARNING",
                    title="Internal Stock Available (Avoid External Purchase)",
                    message=(
                        f"Item has {total_stock} units sitting across warehouses ({locations_summary}). "
                        f"Sufficient stock exists to fulfill the entire requested quantity ({requested_quantity} units) via inter-warehouse transfer."
                    ),
                    details=details
                )

            # Case B: Partial stock available
            if total_stock > 0:
                shortfall = requested_quantity - total_stock
                return LayerResult(
                    layer_name="Layer 2: Multi-Warehouse Stock",
                    status="WARNING",
                    title="Partial Internal Stock Available",
                    message=(
                        f"{total_stock} unit(s) are already available in warehouses. "
                        f"Recommend partial transfer and reducing external purchase from {requested_quantity} to {shortfall} units."
                    ),
                    details=details
                )

            # Case C: Stock is 0
            return LayerResult(
                layer_name="Layer 2: Multi-Warehouse Stock",
                status="PASSED",
                title="Zero Internal Stock",
                message=f"Zero inventory in internal warehouses for SKU '{sku}'. External procurement justified.",
                details=details
            )

        except Exception as e:
            logger.error(f"Layer 2 error: {e}", exc_info=True)
            return LayerResult(
                layer_name="Layer 2: Multi-Warehouse Stock",
                status="WARNING",
                title="Inventory Lookup Error",
                message=f"Could not verify warehouse inventory: {str(e)}",
                details={"error": str(e)}
            )

    # ==========================================================================
    # LAYER 3: Duplicate Purchase Request Detector
    # ==========================================================================
    def check_duplicate_requests(
        self,
        sku: str,
        current_request_id: Optional[str] = None,
        days_window: int = 30
    ) -> LayerResult:
        """
        Scan purchase requests created in the last 30 days for duplicate orders of the same SKU.
        """
        try:
            cutoff_date = self._now() - timedelta(days=days_window)
            
            # Query requests created within the time window using server-side filter
            try:
                query = (
                    self.db.collection(COLLECTION_REQUESTS)
                    .where(filter=FieldFilter("created_at", ">=", cutoff_date))
                    .limit(200)
                )
                docs = list(query.stream())
            except Exception as idx_err:
                # Fallback if composite index is not yet built
                logger.warning(f"Layer 3 server-side date filter failed ({idx_err}), falling back to client-side filter.")
                query = self.db.collection(COLLECTION_REQUESTS)
                docs = list(query.limit(200).stream())

            duplicates = []
            for doc in docs:
                data = doc.to_dict()
                req_id = data.get("request_id")
                
                # Skip the current request if validating an existing document
                if current_request_id and req_id == current_request_id:
                    continue

                # Parse created_at timestamp
                created_at = data.get("created_at")
                if isinstance(created_at, datetime):
                    doc_date = created_at
                elif hasattr(created_at, "to_datetime"):
                    doc_date = created_at.to_datetime()
                else:
                    doc_date = None

                # Check if within 30 days window
                if doc_date and doc_date < cutoff_date:
                    continue

                # Exclude explicitly rejected or cancelled requests
                status = data.get("status", "").lower()
                if status in ("rejected", "cancelled"):
                    continue

                # Match against items list by SKU
                items = data.get("items", [])
                matching_items = [it for it in items if it.get("sku", "").strip().upper() == sku.strip().upper()]

                if matching_items:
                    total_qty_matched = sum(it.get("quantity", 0) for it in matching_items)
                    duplicates.append({
                        "request_id": req_id,
                        "title": data.get("title", ""),
                        "status": data.get("status", ""),
                        "department": data.get("department", ""),
                        "requester": data.get("requester_name", ""),
                        "quantity": total_qty_matched,
                        "total_amount": data.get("total_amount", 0.0),
                        "created_at": doc_date.isoformat() if doc_date else "Unknown"
                    })

            details = {
                "sku": sku,
                "days_window": days_window,
                "duplicate_count": len(duplicates),
                "matched_requests": duplicates
            }

            # Check if an active / pending PR is already waiting
            pending_dups = [d for d in duplicates if d["status"].lower() in ("submitted", "pending validation", "draft")]
            approved_dups = [d for d in duplicates if d["status"].lower() in ("approved", "fulfilled")]

            if pending_dups:
                dup = pending_dups[0]
                return LayerResult(
                    layer_name="Layer 3: Duplicate PR Detector",
                    status="FAILED",
                    title="Active Duplicate Purchase Request Found",
                    message=(
                        f"Potential duplicate! An active request ('{dup['request_id']}' - {dup['title']}) "
                        f"for SKU '{sku}' was submitted by {dup['requester']} ({dup['department']}) on {dup['created_at'][:10]} "
                        f"with status '{dup['status']}'. Reject or consolidate to prevent redundant spend."
                    ),
                    details=details
                )

            if approved_dups:
                dup = approved_dups[0]
                return LayerResult(
                    layer_name="Layer 3: Duplicate PR Detector",
                    status="WARNING",
                    title="Recent Duplicate Requisition",
                    message=(
                        f"SKU '{sku}' was already ordered in the last {days_window} days "
                        f"(Request '{dup['request_id']}', Status: '{dup['status']}', Ordered: {dup['created_at'][:10]}). "
                        f"Verify that additional units are genuinely required."
                    ),
                    details=details
                )

            return LayerResult(
                layer_name="Layer 3: Duplicate PR Detector",
                status="PASSED",
                title="No Duplicate Requests",
                message=f"No overlapping purchase requests for SKU '{sku}' detected within the past {days_window} days.",
                details=details
            )

        except Exception as e:
            logger.error(f"Layer 3 error: {e}", exc_info=True)
            return LayerResult(
                layer_name="Layer 3: Duplicate PR Detector",
                status="WARNING",
                title="Duplicate Check Error",
                message=f"Could not verify duplicate requests: {str(e)}",
                details={"error": str(e)}
            )

    # ==========================================================================
    # LAYER 4: Historical Usage & Anomaly Spike Detection
    # ==========================================================================
    def check_historical_consumption_anomaly(
        self,
        sku: str,
        requested_quantity: int,
        history_days: int = 180
    ) -> LayerResult:
        """
        Calculate average monthly consumption of this SKU from historical fulfilled/approved
        orders, and detect quantity anomalies (spike ratio).
        """
        try:
            cutoff = self._now() - timedelta(days=history_days)
            # Query requests created within the history window using server-side filter
            try:
                query = (
                    self.db.collection(COLLECTION_REQUESTS)
                    .where(filter=FieldFilter("created_at", ">=", cutoff))
                    .limit(500)
                )
                docs = list(query.stream())
            except Exception as idx_err:
                # Fallback if composite index is not yet built
                logger.warning(f"Layer 4 server-side date filter failed ({idx_err}), falling back to client-side filter.")
                query = self.db.collection(COLLECTION_REQUESTS)
                docs = list(query.limit(500).stream())

            historical_units = 0
            historical_order_count = 0

            for doc in docs:
                data = doc.to_dict()
                status = data.get("status", "").lower()

                # Include fulfilled and approved purchase orders as historical demand
                if status not in ("fulfilled", "approved"):
                    continue

                items = data.get("items", [])
                matching = [it for it in items if it.get("sku", "").strip().upper() == sku.strip().upper()]
                for it in matching:
                    historical_units += int(it.get("quantity", 0))
                    historical_order_count += 1

            # Months analyzed (default 6 months)
            months_analyzed = max(1.0, history_days / 30.0)
            avg_monthly_consumption = round(historical_units / months_analyzed, 1)

            details = {
                "sku": sku,
                "requested_quantity": requested_quantity,
                "historical_orders_count": historical_order_count,
                "total_historical_units": historical_units,
                "time_window_months": months_analyzed,
                "avg_monthly_consumption": avg_monthly_consumption,
            }

            # Case: No prior history (First-time requisition)
            if historical_order_count == 0 or avg_monthly_consumption <= 0:
                details["anomaly_ratio"] = None
                return LayerResult(
                    layer_name="Layer 4: Historical Usage",
                    status="PASSED",
                    title="New SKU / No Historical Baseline",
                    message=(
                        f"SKU '{sku}' has no prior order history in the past {history_days} days. "
                        "Baseline consumption cannot be calculated; proceeding with new requisition screening."
                    ),
                    details=details
                )

            spike_ratio = round(requested_quantity / avg_monthly_consumption, 2)
            details["spike_ratio"] = spike_ratio

            # Severe Spike: Requested quantity >= 3.5x monthly average
            if spike_ratio >= 3.5 and requested_quantity > 10:
                return LayerResult(
                    layer_name="Layer 4: Historical Usage",
                    status="FAILED",
                    title="Extreme Volume Anomaly Detected",
                    message=(
                        f"Anomalous Volume: Requested {requested_quantity} units is {spike_ratio}x higher "
                        f"than the historical average monthly consumption ({avg_monthly_consumption} units/month). "
                        "High risk of over-purchasing or data-entry error."
                    ),
                    details=details
                )

            # Moderate Spike: Requested quantity >= 2.0x monthly average
            if spike_ratio >= 2.0 and requested_quantity > 5:
                return LayerResult(
                    layer_name="Layer 4: Historical Usage",
                    status="WARNING",
                    title="Unusual Demand Spike",
                    message=(
                        f"Volume Alert: Requested quantity ({requested_quantity}) is {spike_ratio}x higher "
                        f"than standard monthly usage ({avg_monthly_consumption} units/month). "
                        "Requires manager justification for unexpected volume surge."
                    ),
                    details=details
                )

            # Normal volume
            return LayerResult(
                layer_name="Layer 4: Historical Usage",
                status="PASSED",
                title="Volume Conforms to Baseline",
                message=(
                    f"Requested volume ({requested_quantity} units) aligns with historical run-rate "
                    f"(average {avg_monthly_consumption} units/month; ratio: {spike_ratio}x)."
                ),
                details=details
            )

        except Exception as e:
            logger.error(f"Layer 4 error: {e}", exc_info=True)
            return LayerResult(
                layer_name="Layer 4: Historical Usage",
                status="WARNING",
                title="Historical Analysis Error",
                message=f"Could not compute historical usage run-rate: {str(e)}",
                details={"error": str(e)}
            )

    # ==========================================================================
    # Main Orchestrator: Run All 4 Layers
    # ==========================================================================
    def validate_request_payload(
        self,
        request_data: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> ValidationReport:
        """
        Execute all 4 validation layers on a purchase request payload and compile
        a unified JSON report for the downstream AI engine.
        
        Args:
            request_data: Purchase request dictionary containing item_name, sku,
                          quantity, estimated_price, department.
            request_id: Optional ID of the request if already persisted.
            
        Returns:
            ValidationReport: Compiled summary object ready for AI prompt injection.
        """
        req_id = request_id or request_data.get("request_id") or f"PR-TEMP-{self._now().strftime('%H%M%S')}"
        item_name = request_data.get("item_name") or request_data.get("title") or "Unknown Item"
        sku = request_data.get("sku", "").strip()
        department = request_data.get("department", "Engineering").strip()

        # If items is an array, extract from first item if needed
        items = request_data.get("items", [])
        if not sku and items and isinstance(items, list) and len(items) > 0:
            sku = items[0].get("sku", "")
            if item_name == "Unknown Item":
                item_name = items[0].get("item_name", "Unknown Item")

        quantity = int(request_data.get("quantity") or (items[0].get("quantity") if items else 1) or 1)
        estimated_price = float(request_data.get("estimated_price") or (items[0].get("unit_price") if items else 0.0) or 0.0)
        total_amount = float(request_data.get("total_amount") or (quantity * estimated_price))

        logger.info(f"Starting 4-Layer Validation for '{req_id}' ({item_name} - SKU: {sku})...")

        # Execute 4 Validation Layers
        layer1 = self.check_department_budget(department, total_amount)
        layer2 = self.check_warehouse_inventory(sku, quantity)
        layer3 = self.check_duplicate_requests(sku, current_request_id=request_id)
        layer4 = self.check_historical_consumption_anomaly(sku, quantity)

        all_results = [layer1, layer2, layer3, layer4]

        # Determine Overall Status
        has_failed = any(r.status == "FAILED" for r in all_results)
        has_warnings = any(r.status == "WARNING" for r in all_results)

        if has_failed:
            overall_status = "FAILED"
            suggested_action = "REJECT_OR_FLAG_CRITICAL"
        elif has_warnings:
            overall_status = "WARNINGS"
            suggested_action = "AI_REVIEW_AND_PROMPT_JUSTIFICATION"
        else:
            overall_status = "PASSED"
            suggested_action = "AUTO_APPROVE_ELIGIBLE"

        flags_count = {
            "FAILED": sum(1 for r in all_results if r.status == "FAILED"),
            "WARNING": sum(1 for r in all_results if r.status == "WARNING"),
            "PASSED": sum(1 for r in all_results if r.status == "PASSED"),
        }

        # Build concise human-readable AI summary
        summary_sentences = []
        for res in all_results:
            summary_sentences.append(f"[{res.layer_name}: {res.status}] {res.message}")
        ai_context_summary = " | ".join(summary_sentences)

        layers_dict = {
            "layer1_budget": asdict(layer1),
            "layer2_warehouse_stock": asdict(layer2),
            "layer3_duplicate_check": asdict(layer3),
            "layer4_historical_usage": asdict(layer4),
        }

        report = ValidationReport(
            request_id=req_id,
            item_name=item_name,
            sku=sku,
            department=department,
            quantity=quantity,
            estimated_price=estimated_price,
            total_amount=total_amount,
            overall_status=overall_status,
            flags_count=flags_count,
            layers=layers_dict,
            ai_context_summary=ai_context_summary,
            suggested_ai_action=suggested_action,
            evaluated_at=self._now().isoformat()
        )

        logger.info(
            f"Validation complete for '{req_id}': Overall Status = {overall_status} "
            f"(Failed: {flags_count['FAILED']}, Warnings: {flags_count['WARNING']}, Passed: {flags_count['PASSED']})"
        )
        return report

    def validate_existing_request(self, request_id: str) -> ValidationReport:
        """
        Fetch an existing purchase request document from Firestore and validate it.
        """
        doc = self.db.collection(COLLECTION_REQUESTS).document(request_id).get()
        if not doc.exists:
            raise ValueError(f"Purchase Request '{request_id}' does not exist.")
        data = doc.to_dict()
        return self.validate_request_payload(data, request_id=request_id)


def run_pre_ai_validation(request_data: Dict[str, Any], request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to run the 4-layer validation engine and return
    a JSON-serializable dictionary for AI prompts.
    """
    engine = ValidationEngine()
    report = engine.validate_request_payload(request_data, request_id=request_id)
    return report.to_dict()


if __name__ == "__main__":
    import sys
    print("\n--- Running Procurement Validation Engine Self-Test ---\n")
    
    test_pr = {
        "request_id": "PR-TEST-VAL",
        "item_name": "Developer Workstation Laptop 16-inch",
        "sku": "SKU-LAPTOP-PRO16",
        "quantity": 10,
        "estimated_price": 2400.00,
        "department": "Engineering"
    }

    try:
        engine = ValidationEngine()
        result = engine.validate_request_payload(test_pr)
        print(json.dumps(result.to_dict(), indent=2))
        print(f"\n[DONE] Overall Status: {result.overall_status}")
    except Exception as e:
        print(f"[ERROR] Validation failed: {e}")
        sys.exit(1)
