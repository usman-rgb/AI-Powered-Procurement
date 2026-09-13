"""
Flask Application Factory
Initializes Flask, applies configuration, sets up logging, and registers blueprints.
"""

import logging
import os
from flask import Flask

from config import get_config
from app.routes import register_blueprints
from app.services.firebase_init import initialize_firebase, FirebaseInitializationError


def create_app(config_name: str = None) -> Flask:
    """
    Application Factory Pattern for Flask.
    
    Args:
        config_name: 'development', 'testing', or 'production'.
        
    Returns:
        Flask: Configured application instance.
    """
    # Setup structured logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger = logging.getLogger("procurement_app")

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    # Load configuration
    cfg = get_config(config_name)
    app.config.from_object(cfg)

    logger.info(f"Starting application in '{app.config.get('FLASK_ENV', 'development')}' mode.")

    # Register Blueprints
    register_blueprints(app)

    # Attempt to initialize Firebase Admin SDK eagerly
    with app.app_context():
        try:
            initialize_firebase()
            logger.info("Firebase Firestore client verified on startup.")
        except FirebaseInitializationError as fie:
            logger.warning(
                f"[Firebase Notice] {fie} "
                "(The application will run, but Firestore calls will require valid credentials.)"
            )
        except Exception as e:
            logger.error(f"Unexpected error during startup Firebase check: {e}")

    return app
