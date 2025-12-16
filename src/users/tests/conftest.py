"""
Pytest configuration for users app tests
"""

import pytest


def pytest_addoption(parser):
    """Add custom pytest command line options"""
    parser.addoption(
        "--run-real-email",
        action="store_true",
        default=False,
        help="Run real email tests (sends actual emails)"
    )


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "real_email: marks tests that send real emails (deselect with '-m \"not real_email\"')"
    )

pytestmark = pytest.mark.real_email
