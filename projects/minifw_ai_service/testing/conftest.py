import os

import pytest

# Required by minifw_ai.main module-level guard
os.environ.setdefault("GAMBLING_ONLY", "1")

pytest.register_assert_rewrite("testing")

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
