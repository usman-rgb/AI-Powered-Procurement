"""
Application Entry Point (run.py)
Initializes and serves the Flask AI-Powered Procurement application.
"""

import os
from app import create_app

# Create Flask application instance via Factory
app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1").lower() in ("1", "true", "yes")
    print(f"[*] AI Procurement Application starting on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
