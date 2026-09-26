"""Pytest fixtures for DevPilot test suite."""
import os
import subprocess
import pytest

@pytest.fixture(autouse=True)
def reset_test_repositories():
    """Ensure test repositories are always at clean git baseline before and after tests."""
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    repo_dirs = [
        os.path.join(workspace, "test_repositories/auth_microservice"),
        os.path.join(workspace, "test_repositories/ecommerce_service"),
        os.path.join(workspace, "test_repositories/realtime_stream_service"),
        os.path.join(workspace, "test_repositories/real_test_repo"),
    ]
    for d in repo_dirs:
        if os.path.isdir(d):
            subprocess.run(["git", "checkout", "main"], cwd=d, capture_output=True, check=False)
            subprocess.run(["git", "checkout", "--", "."], cwd=d, capture_output=True, check=False)
    yield
    for d in repo_dirs:
        if os.path.isdir(d):
            subprocess.run(["git", "checkout", "main"], cwd=d, capture_output=True, check=False)
            subprocess.run(["git", "checkout", "--", "."], cwd=d, capture_output=True, check=False)
