"""
AI Decision Service (ai_decision_service.py)
--------------------------------------------------------------------------------
Architectural Role:
Integrates LLM APIs (Groq / Grok / xAI) into the Procurement Pipeline.
Formulates dynamic contextual prompts from the 4-Layer Validation Engine
and enforces strictly structured JSON output:
  - Decision: APPROVE | REDUCE | HOLD | REJECT
  - Criticality_Score: 1 to 100
  - Priority_Level: CRITICAL | HIGH | MEDIUM | LOW
  - Reasoning: Concise, human-readable justification
  - Estimated_Savings: Quantified savings from warehouse transfers or volume trim
--------------------------------------------------------------------------------
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from google.cloud import firestore

from app.services.firebase_init import get_db
from app.services.firebase_db import COLLECTION_REQUESTS
from app.services.validation_engine import ValidationEngine, ValidationReport

logger = logging.getLogger("ai_decision_service")

# Default LLM configurations
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

GROK_API_URL = "https://api.x.ai/v1/chat/completions"
GROK_DEFAULT_MODEL = "grok-beta"


class AIDecisionServiceError(Exception):
    """Custom exception for AI Decision Service failures."""
    pass


def _extract_json_from_llm_response(raw_text: str) -> Dict[str, Any]:
    """
    Robust JSON parser for LLM responses.
    Handles Markdown code fences (```json ... ```) and leading/trailing chatter.
    """
    cleaned = raw_text.strip()
    
    # Strip markdown code blocks if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()

    try:
        data = json.loads(cleaned)
        return data
    except json.JSONDecodeError:
        # Secondary fallback: find the first { and last }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            return json.loads(cleaned[start : end + 1])
        raise ValueError(f"Could not parse valid JSON from LLM output: {raw_text[:200]}...")


def build_procurement_prompt(
    request_data: Dict[str, Any],
    validation_report: Dict[str, Any]
) -> tuple[str, str]:
    """
    Formulate system and user prompts injecting the purchase request details
    and the 4-layer validation engine findings.
    """
    system_prompt = (
        "You are the Chief AI Procurement Risk & Allocation Officer for a Fortune 500 enterprise. "
        "Your duty is to review incoming purchase requests against rigorous financial controls, "
        "multi-warehouse supply chain inventory, duplicate requisition records, and consumption patterns.\n\n"
        "EVALUATION CRITERIA & ACTIONS:\n"
        "1. REJECT:\n"
        "   - The requested amount exceeds available department budget headroom (Layer 1 Overdraft).\n"
        "   - An identical active/pending purchase request is already in-flight (Layer 3 Duplicate).\n"
        "   - Pricing is severely inflated or purpose is non-compliant.\n"
        "2. REDUCE:\n"
        "   - Sufficient or partial idle stock exists in another internal warehouse (Layer 2).\n"
        "     Instruct the requester to utilize inter-warehouse transfer and reduce/cancel external purchase.\n"
        "   - Volume spike is excessive (Layer 4 Anomaly), recommend scaling down quantity to monthly baseline.\n"
        "   - ALWAYS calculate 'Estimated_Savings' = (Reduced Quantity * Unit Price) when REDUCE is selected.\n"
        "3. HOLD:\n"
        "   - Requisition consumes >60% of department remaining budget, requiring CFO escalation.\n"
        "   - Item was fulfilled very recently (within 30 days) and physical delivery audit is advised.\n"
        "4. APPROVE:\n"
        "   - Budget is healthy, internal warehouse stock is zero, no duplicates, and volume conforms to run-rate.\n\n"
        "CRITICAL INSTRUCTION: You must respond ONLY with a strictly structured JSON object. "
        "Do NOT include any introduction, conversational greetings, or markdown outside the JSON.\n"
        "Required JSON schema:\n"
        "{\n"
        '  "Decision": "APPROVE" | "REDUCE" | "HOLD" | "REJECT",\n'
        '  "Criticality_Score": <integer between 1 and 100>,\n'
        '  "Priority_Level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",\n'
        '  "Reasoning": "<concise 1-3 sentence explanation with specific figures>",\n'
        '  "Estimated_Savings": <float amount saved in USD, 0.0 if not applicable>\n'
        "}"
    )

    user_payload = {
        "purchase_request": {
            "request_id": request_data.get("request_id"),
            "title": request_data.get("title") or request_data.get("item_name"),
            "requester": request_data.get("requester_name") or request_data.get("requester_id"),
            "department": request_data.get("department"),
            "category": request_data.get("category"),
            "total_amount": request_data.get("total_amount"),
            "currency": request_data.get("currency", "USD"),
            "items": request_data.get("items", []),
            "purpose": request_data.get("purpose", ""),
            "priority": request_data.get("priority", "medium")
        },
        "pre_ai_validation_report": {
            "overall_status": validation_report.get("overall_status"),
            "flags_count": validation_report.get("flags_count"),
            "suggested_action": validation_report.get("suggested_ai_action"),
            "layer_1_budget": validation_report.get("layers", {}).get("layer1_budget"),
            "layer_2_warehouse_stock": validation_report.get("layers", {}).get("layer2_warehouse_stock"),
            "layer_3_duplicate_check": validation_report.get("layers", {}).get("layer3_duplicate_check"),
            "layer_4_historical_usage": validation_report.get("layers", {}).get("layer4_historical_usage"),
        }
    }

    user_prompt = (
        "Analyze the following Purchase Request and Deterministic Validation Findings, "
        "and produce your authoritative JSON procurement decision:\n\n"
        f"{json.dumps(user_payload, indent=2)}"
    )

    return system_prompt, user_prompt


def _generate_fallback_heuristic_decision(
    request_data: Dict[str, Any],
    validation_report: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic rule-based fallback decision engine.
    Ensures application continuity if no external LLM API key is provided
    or if network/API limits are encountered.
    """
    layers = validation_report.get("layers", {})
    l1 = layers.get("layer1_budget", {})
    l2 = layers.get("layer2_warehouse_stock", {})
    l3 = layers.get("layer3_duplicate_check", {})
    l4 = layers.get("layer4_historical_usage", {})

    total_amount = float(request_data.get("total_amount", 0.0))
    qty = int(request_data.get("quantity") or 1)
    unit_price = float(request_data.get("estimated_price") or (total_amount / max(1, qty)))

    # 1. Check Layer 1 (Budget failure)
    if l1.get("status") == "FAILED":
        return {
            "Decision": "REJECT",
            "Criticality_Score": 92,
            "Priority_Level": "CRITICAL",
            "Reasoning": f"Budget Exceeded: {l1.get('message', 'Request surpasses departmental budget.')}",
            "Estimated_Savings": total_amount,
            "_mode": "heuristic_fallback"
        }

    # 2. Check Layer 3 (Duplicate request failure)
    if l3.get("status") == "FAILED":
        return {
            "Decision": "REJECT",
            "Criticality_Score": 88,
            "Priority_Level": "HIGH",
            "Reasoning": f"Duplicate In-Flight: {l3.get('message', 'An active duplicate requisition was detected.')}",
            "Estimated_Savings": total_amount,
            "_mode": "heuristic_fallback"
        }

    # 3. Check Layer 2 (Warehouse stock available)
    l2_details = l2.get("details", {})
    idle_stock = int(l2_details.get("total_internal_stock", 0))
    if l2.get("status") == "WARNING" and idle_stock > 0:
        transferable = min(qty, idle_stock)
        savings = round(transferable * unit_price, 2)
        if transferable >= qty:
            return {
                "Decision": "REDUCE",
                "Criticality_Score": 68,
                "Priority_Level": "MEDIUM",
                "Reasoning": f"Internal Stock Available: All {qty} units can be fulfilled via inter-warehouse transfer. Cancel external purchase.",
                "Estimated_Savings": savings,
                "_mode": "heuristic_fallback"
            }
        else:
            return {
                "Decision": "REDUCE",
                "Criticality_Score": 60,
                "Priority_Level": "MEDIUM",
                "Reasoning": f"Partial Stock Available: Transfer {transferable} units internally; purchase remaining {qty - transferable} units externally.",
                "Estimated_Savings": savings,
                "_mode": "heuristic_fallback"
            }

    # 4. Check Layer 4 (Severe Anomaly)
    if l4.get("status") == "FAILED":
        return {
            "Decision": "HOLD",
            "Criticality_Score": 75,
            "Priority_Level": "HIGH",
            "Reasoning": f"Volume Anomaly: {l4.get('message', 'Order quantity is significantly higher than historical baseline.')}",
            "Estimated_Savings": 0.0,
            "_mode": "heuristic_fallback"
        }

    # 5. Check Budget Warning (Consumption > 60%)
    if l1.get("status") == "WARNING":
        return {
            "Decision": "HOLD",
            "Criticality_Score": 55,
            "Priority_Level": "MEDIUM",
            "Reasoning": f"High Budget Drawdown: {l1.get('message', 'Request draws heavily on remaining balance. CFO sign-off advised.')}",
            "Estimated_Savings": 0.0,
            "_mode": "heuristic_fallback"
        }

    # Default: Safe to Approve
    return {
        "Decision": "APPROVE",
        "Criticality_Score": 15,
        "Priority_Level": "LOW",
        "Reasoning": "Budget verified, zero internal idle inventory, no duplicates, and volume conforms to historical run-rates.",
        "Estimated_Savings": 0.0,
        "_mode": "heuristic_fallback"
    }


def call_llm_api(
    system_prompt: str,
    user_prompt: str,
    timeout_sec: int = 25
) -> Dict[str, Any]:
    """
    Dispatch request to Groq or Grok (xAI) API.
    Auto-detects API key from GROQ_API_KEY, GROK_API_KEY, or XAI_API_KEY.
    """
    groq_key = os.getenv("GROQ_API_KEY")
    grok_key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
    provider = os.getenv("LLM_PROVIDER", "").lower()

    endpoint = None
    api_key = None
    model_name = None

    # Priority 1: Groq API
    if groq_key and (provider == "groq" or not provider):
        endpoint = os.getenv("GROQ_API_URL", GROQ_API_URL)
        api_key = groq_key
        model_name = os.getenv("LLM_MODEL", GROQ_DEFAULT_MODEL)
        provider_name = "Groq"

    # Priority 2: Grok / xAI API
    elif grok_key:
        endpoint = os.getenv("GROK_API_URL", GROK_API_URL)
        api_key = grok_key
        model_name = os.getenv("LLM_MODEL", GROK_DEFAULT_MODEL)
        provider_name = "Grok"

    else:
        logger.info("Neither GROQ_API_KEY nor GROK_API_KEY found in environment. Using heuristic intelligence fallback.")
        return {}

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    logger.info(f"Calling {provider_name} API ({model_name})...")
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_sec)

    if resp.status_code != 200:
        raise AIDecisionServiceError(
            f"{provider_name} API returned status {resp.status_code}: {resp.text}"
        )

    resp_json = resp.json()
    choices = resp_json.get("choices", [])
    if not choices:
        raise AIDecisionServiceError(f"No choices returned from {provider_name} API.")

    raw_content = choices[0].get("message", {}).get("content", "")
    parsed = _extract_json_from_llm_response(raw_content)
    parsed["_provider"] = provider_name
    parsed["_model"] = model_name
    return parsed


def evaluate_purchase_request_ai(
    request_data: Dict[str, Any],
    validation_report: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main evaluation pipeline:
    1. Pre-validation checks if report is not provided.
    2. Prompt synthesis.
    3. LLM API call with JSON schema validation.
    4. Heuristic fallback if LLM is unconfigured.
    """
    req_id = request_data.get("request_id", "UNKNOWN")

    # Generate validation report if not passed
    if not validation_report:
        engine = ValidationEngine()
        report_obj = engine.validate_request_payload(request_data, request_id=req_id)
        validation_report = report_obj.to_dict()

    system_prompt, user_prompt = build_procurement_prompt(request_data, validation_report)

    decision_data = None
    try:
        decision_data = call_llm_api(system_prompt, user_prompt)
    except Exception as e:
        logger.warning(f"LLM API invocation encountered issue ({e}). Falling back to heuristic reasoning.")

    # If LLM didn't return data (no key or error), execute deterministic heuristic
    if not decision_data:
        decision_data = _generate_fallback_heuristic_decision(request_data, validation_report)

    # Sanitize and guarantee required schema keys
    decision = str(decision_data.get("Decision", "HOLD")).upper()
    if decision not in ("APPROVE", "REDUCE", "HOLD", "REJECT"):
        decision = "HOLD"

    try:
        criticality = int(decision_data.get("Criticality_Score", 50))
        criticality = max(1, min(100, criticality))
    except (ValueError, TypeError):
        criticality = 50

    priority = str(decision_data.get("Priority_Level", "MEDIUM")).upper()
    if priority not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        priority = "MEDIUM"

    reasoning = str(decision_data.get("Reasoning", "Review required by procurement."))
    try:
        savings = float(decision_data.get("Estimated_Savings", 0.0))
    except (ValueError, TypeError):
        savings = 0.0

    sanitized_result = {
        "Decision": decision,
        "Criticality_Score": criticality,
        "Priority_Level": priority,
        "Reasoning": reasoning,
        "Estimated_Savings": round(savings, 2),
        "Source": decision_data.get("_provider", "ProcureAI-HeuristicEngine"),
        "Evaluated_At": datetime.now(timezone.utc).isoformat()
    }

    return sanitized_result


def evaluate_and_update_firestore_request(request_id: str) -> Dict[str, Any]:
    """
    Fetch an existing purchase request from Firestore, execute the AI decision service,
    and persist the AI evaluation directly onto the Firestore document.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION_REQUESTS).document(request_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise ValueError(f"Purchase Request '{request_id}' not found in Firestore.")

    request_data = doc.to_dict()

    # Step 1: Run 4-Layer Validation Engine
    engine = ValidationEngine(db)
    validation_report = engine.validate_request_payload(request_data, request_id=request_id).to_dict()

    # Step 2: Execute AI Evaluation
    ai_decision = evaluate_purchase_request_ai(request_data, validation_report)

    now = datetime.now(timezone.utc)
    risk_score = round(ai_decision["Criticality_Score"] / 100.0, 2)

    # Step 3: Determine new document status & audit entry
    new_status = request_data.get("status", "Pending Validation")
    if ai_decision["Decision"] == "APPROVE":
        new_status = "Approved by AI"
    elif ai_decision["Decision"] == "REJECT":
        new_status = "Rejected by AI"
    elif ai_decision["Decision"] == "REDUCE":
        new_status = "Action Required: Reduction Suggested"
    elif ai_decision["Decision"] == "HOLD":
        new_status = "On Hold: Escalation Required"

    trail_entry = {
        "step": f"AI Decision Engine ({ai_decision.get('Source', 'AI')})",
        "actor_id": "ProcureAI-Decision-Agent",
        "decision": ai_decision["Decision"],
        "comment": f"[{ai_decision['Decision']} - Score {ai_decision['Criticality_Score']}/100 - Priority {ai_decision['Priority_Level']}]: {ai_decision['Reasoning']}",
        "timestamp": now
    }

    # Step 4: Persist updates back to Firestore
    updates = {
        "ai_decision": ai_decision,
        "ai_risk_score": risk_score,
        "ai_notes": ai_decision["Reasoning"],
        "status": new_status,
        "validation_report": validation_report,
        "updated_at": now,
        "approval_trail": firestore.ArrayUnion([trail_entry])
    }

    doc_ref.update(updates)
    logger.info(f"Purchase Request '{request_id}' updated with AI Decision: {ai_decision['Decision']} (Score: {ai_decision['Criticality_Score']})")

    request_data.update(updates)
    return {
        "request_id": request_id,
        "ai_decision": ai_decision,
        "validation_report": validation_report,
        "new_status": new_status
    }
