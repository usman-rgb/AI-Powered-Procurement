"""
Seed missing Finance and HR budgets into Firestore.
"""
from datetime import datetime, timezone
from app.services.firebase_init import get_db

def seed_missing_budgets():
    db = get_db()
    now = datetime.now(timezone.utc)
    
    budgets = [
        {
            "budget_id": "BUD-FIN-2026-Q3",
            "department": "Finance",
            "fiscal_year": 2026,
            "quarter": "Q3",
            "allocated_amount": 150000.00,
            "committed_amount": 0.00,
            "spent_amount": 25000.00,
            "remaining_amount": 125000.00,
            "currency": "USD",
            "status": "active",
            "created_at": now,
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
            "remaining_amount": 65000.00,
            "currency": "USD",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    ]
    
    for b in budgets:
        doc_ref = db.collection("Budgets").document(b["budget_id"])
        doc_ref.set(b, merge=True)
        print(f"Successfully saved budget document: {b['budget_id']}")

if __name__ == "__main__":
    seed_missing_budgets()
