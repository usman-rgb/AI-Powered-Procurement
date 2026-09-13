"""
Shared pytest fixtures and test configuration for AI-Powered Procurement.
"""

import os
import sys
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment
os.environ["FLASK_ENV"] = "testing"

from app import create_app


@pytest.fixture
def app():
    """Create and configure a Flask application instance for testing."""
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-procurement-secret-key-2026"
    return app


@pytest.fixture
def client(app):
    """Test client for unauthenticated requests."""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Test client authenticated as Procurement Director."""
    with client.session_transaction() as sess:
        sess["user_id"] = "USR-MGR-TEST"
        sess["user_email"] = "manager@procureai.enterprise"
        sess["user_name"] = "Procurement Director"
        sess["user_role"] = "Procurement Director"
        sess["user_department"] = "Supply Chain & Procurement"
    return client
