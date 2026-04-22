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


# Marker `real_email` is registered in src/pytest.ini so it exists before this module
# finishes importing (module-level pytestmark below would otherwise warn).
pytestmark = pytest.mark.real_email
