"""
Routes Package
Registers all application Blueprints.
"""

from flask import Flask
from .main_routes import main_bp
from .procurement_routes import procurement_bp
from .inventory_routes import inventory_bp
from .budget_routes import budget_bp
from .auth_routes import auth_bp, login_required, role_required


def register_blueprints(app: Flask) -> None:
    """Register all Blueprints on the Flask application instance."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(budget_bp)
