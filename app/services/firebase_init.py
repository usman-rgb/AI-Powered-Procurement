"""
Firebase Admin SDK Initialization Module
Securely initializes Firebase Admin and provides a centralized Firestore client.
Supports multiple credential sources (JSON file path, raw JSON environment variable,
or Application Default Credentials).
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.client import Client as FirestoreClient

# Setup module logger
logger = logging.getLogger(__name__)

# Global cache for Firestore client
_db: Optional[FirestoreClient] = None


class FirebaseInitializationError(Exception):
    """Custom exception raised when Firebase fails to initialize."""
    pass


def initialize_firebase() -> FirestoreClient:
    """
    Initialize Firebase Admin SDK using the configured credentials.
    
    Credential loading priority:
    1. Raw JSON string in FIREBASE_CREDENTIALS_JSON env var (Cloud/Container friendly)
    2. File path in FIREBASE_SERVICE_ACCOUNT_KEY env var or default './serviceAccountKey.json'
    3. Google Application Default Credentials (e.g. running inside GCP / Cloud Run)

    Returns:
        FirestoreClient: Initialized Firestore database client instance.
    
    Raises:
        FirebaseInitializationError: If credentials cannot be loaded or initialization fails.
    """
    global _db

    # Return cached client if already initialized
    if _db is not None:
        return _db

    # Check if a Firebase Admin app already exists (handles Flask reloader / hot reload)
    if firebase_admin._apps:
        logger.info("Firebase app already initialized. Reusing existing app instance.")
        _db = firestore.client()
        return _db

    cred = None

    # Option 1: Load from raw JSON string (e.g., environment secret in production/Docker)
    raw_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if raw_json and raw_json.strip():
        try:
            cert_dict = json.loads(raw_json)
            cred = credentials.Certificate(cert_dict)
            logger.info("Loaded Firebase credentials from FIREBASE_CREDENTIALS_JSON environment variable.")
        except Exception as e:
            raise FirebaseInitializationError(
                f"Failed to parse FIREBASE_CREDENTIALS_JSON: {e}"
            ) from e

    # Option 2: Load from service account file path
    if cred is None:
        key_path_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "serviceAccountKey.json")
        key_path = Path(key_path_str).resolve()
        # If specified path does not exist, search for serviceAccountKey.json or any *firebase-adminsdk*.json
        if not key_path.exists() or not key_path.is_file():
            fallback_default = Path("serviceAccountKey.json").resolve()
            if fallback_default.exists() and fallback_default.is_file():
                key_path = fallback_default
            else:
                sdk_matches = list(Path.cwd().glob("*firebase-adminsdk*.json"))
                if sdk_matches:
                    key_path = sdk_matches[0].resolve()

        if key_path.exists() and key_path.is_file():
            try:
                cred = credentials.Certificate(str(key_path))
                logger.info(f"Loaded Firebase credentials from file: {key_path}")
            except Exception as e:
                raise FirebaseInitializationError(
                    f"Failed to read certificate from '{key_path}': {e}"
                ) from e
        else:
            logger.warning(
                f"Service account key file not found at '{key_path}'."
            )

    # Option 3: Fallback to Application Default Credentials (ADC) if explicitly configured or running in Cloud
    if cred is None:
        has_adc_env = bool(
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            or os.getenv("K_SERVICE")      # Cloud Run
            or os.getenv("GAE_INSTANCE")   # App Engine
            or os.getenv("GCE_METADATA_HOST")
        )
        if has_adc_env:
            try:
                logger.info("Attempting to load Google Application Default Credentials (ADC)...")
                cred = credentials.ApplicationDefault()
            except Exception as e:
                raise FirebaseInitializationError(
                    f"Failed to load Application Default Credentials: {e}"
                ) from e
        else:
            raise FirebaseInitializationError(
                "Firebase initialization failed: No credentials found. "
                "Please place 'serviceAccountKey.json' in the project root, or set "
                "FIREBASE_SERVICE_ACCOUNT_KEY / FIREBASE_CREDENTIALS_JSON in your .env file."
            )

    # Initialize Firebase Admin App
    try:
        project_id = os.getenv("FIREBASE_PROJECT_ID")
        options = {"projectId": project_id} if project_id else None
        
        app = firebase_admin.initialize_app(cred, options=options)
        _db = firestore.client(app=app)
        logger.info("Firebase Admin SDK and Firestore client successfully initialized.")
        return _db
    except Exception as e:
        raise FirebaseInitializationError(f"Failed to initialize Firestore client: {e}") from e


def get_db() -> FirestoreClient:
    """
    Get the Firestore database client. Initializes if not already active.
    
    Returns:
        FirestoreClient: Active Firestore database client.
    """
    global _db
    if _db is None:
        _db = initialize_firebase()
    return _db


def is_firebase_initialized() -> bool:
    """Check if Firebase is currently initialized."""
    return bool(firebase_admin._apps and _db is not None)
