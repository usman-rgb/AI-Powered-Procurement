"""
Application Configuration Module
Handles environment-specific configurations for Development, Testing, and Production.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


from datetime import timedelta

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-procurement-secret-key-change-in-production")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    PORT = int(os.getenv("PORT", 5000))
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # Firebase configuration
    FIREBASE_SERVICE_ACCOUNT_KEY = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_KEY", 
        str(BASE_DIR / "serviceAccountKey.json")
    )
    FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON", None)
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "procureai-c4588")
    FIREBASE_CLIENT_API_KEY = os.getenv("FIREBASE_CLIENT_API_KEY", "AIzaSyAWoCv5PuugDdGQiBkEv32BDKi15jJWDuc")
    FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID", "1:377887502646:web:123249e49f82ab7e1b4397")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    SECRET_KEY = "test-procurement-secret-key"


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False


# Map environment names to config classes
CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str = None) -> type[Config]:
    """Retrieve configuration class based on environment name."""
    if not env_name:
        env_name = os.getenv("FLASK_ENV", "development").lower()
    return CONFIG_BY_NAME.get(env_name, DevelopmentConfig)
